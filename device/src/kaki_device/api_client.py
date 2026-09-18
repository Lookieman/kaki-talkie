# v1.0 | 16-Sep-2026 | WP6.1 backend client for the three device HTTP routes.
"""Call the backend's device contract and nothing else.

Three routes exist for this client (design.md 5): `POST /api/device/turn`,
`GET /api/device/pending` and `GET /api/health`. Their paths are module
constants so the WP6-AT-13 inspection can prove the device never reaches a
model service or any other endpoint.

The response is the WP1 nine-field contract. This module parses it into
`TurnResult` without interpreting it: `state` is carried through as text, and
the device never decides a state itself.

Reply audio deserves its own note, because the contract is deliberately loose.
`TurnResponse.reply_audio` is typed `str | None` with no format in the schema
snapshot, and design.md 5.2 calls it a "spoken response reference or payload".
Every current producer emits one concrete form: an RFC 2397 data URL,
`data:audio/wav;base64,<base64 WAV>`, written by the TTS adapters and by
`persistence.repositories.audio_to_data_url`. So `decode_reply_audio` accepts
exactly that form, validates the base64 strictly and checks the bytes really
are PCM WAV. Any other string is a reference this build cannot play: it raises
`UnplayableAudio` rather than guessing, and the caller degrades to a
text-only turn. A null stays null, which the contract says means no audio.
"""

import io
import wave
from base64 import b64decode
from binascii import Error as BinasciiError
from dataclasses import dataclass
from typing import Any

import httpx

TURN_PATH = "/api/device/turn"
PENDING_PATH = "/api/device/pending"
HEALTH_PATH = "/api/health"

AUDIO_DATA_URL_PREFIX = "data:audio/wav;base64,"
# A generous ceiling on one reply's audio: 22.05 kHz mono 16-bit for a minute
# is about 2.6 MB, and base64 adds a third.
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

RESPONSE_FIELDS = (
    "turn_id", "reply_audio", "reply_text", "display_text", "slip_text",
    "language", "state", "case_id", "sources",
)


class ApiError(RuntimeError):
    """Signal a controlled backend failure with a safe code, never a payload."""

    CODES = frozenset({"unavailable", "timeout", "invalid_response", "rejected"})

    def __init__(self, code: str) -> None:
        """Restrict diagnostics to known codes; unknown ones read `unavailable`."""
        self.code = code if code in self.CODES else "unavailable"
        super().__init__(self.code)


class UnplayableAudio(ValueError):
    """Signal reply audio this build cannot decode into WAV bytes."""


@dataclass(frozen=True)
class TurnResult:
    """The nine response fields, carried as data the device renders and plays."""

    turn_id: str
    reply_audio: str | None
    reply_text: str
    display_text: str
    slip_text: str
    language: str
    state: str
    case_id: str | None
    sources: tuple[dict[str, Any], ...]

    @property
    def has_slip(self) -> bool:
        """True when the backend produced slip text for this turn."""
        return bool(self.slip_text.strip())


def decode_reply_audio(reply_audio: str | None) -> bytes | None:
    """Return playable WAV bytes from the contract's `reply_audio`, or None.

    None in, None out: the contract uses null for "no audio available", and a
    turn without audio is still a complete turn. A `data:audio/wav;base64,`
    payload is decoded and checked for PCM WAV structure. Anything else, and
    any malformed payload, raises `UnplayableAudio`.
    """
    if reply_audio is None:
        return None
    if not isinstance(reply_audio, str) or not reply_audio.startswith(AUDIO_DATA_URL_PREFIX):
        raise UnplayableAudio("reply_audio is not a WAV data URL this build can play")
    encoded = reply_audio[len(AUDIO_DATA_URL_PREFIX):]
    try:
        audio = b64decode(encoded, validate=True)
    except (BinasciiError, ValueError):
        raise UnplayableAudio("reply_audio is not valid base64") from None
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise UnplayableAudio("reply_audio is empty or larger than this build plays")
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            playable = (
                recording.getcomptype() == "NONE"
                and recording.getnchannels() > 0
                and recording.getframerate() > 0
                and recording.getnframes() > 0
            )
    except (wave.Error, EOFError):
        raise UnplayableAudio("reply_audio does not decode as WAV") from None
    if not playable:
        raise UnplayableAudio("reply_audio is not non-empty PCM WAV")
    return audio


def _parsed_turn(payload: object) -> TurnResult:
    """Build a TurnResult from a decoded body, or raise ApiError.

    Every contract field must be present. Extra fields are ignored rather
    than rejected, so a later backend addition cannot stop the kiosk.
    """
    if not isinstance(payload, dict) or not set(RESPONSE_FIELDS) <= set(payload):
        raise ApiError("invalid_response")
    sources = payload["sources"]
    if not isinstance(sources, list):
        raise ApiError("invalid_response")
    try:
        return TurnResult(
            turn_id=str(payload["turn_id"]),
            reply_audio=payload["reply_audio"],
            reply_text=str(payload["reply_text"]),
            display_text=str(payload["display_text"]),
            slip_text=str(payload["slip_text"]),
            language=str(payload["language"]),
            state=str(payload["state"]),
            case_id=payload["case_id"],
            sources=tuple(source for source in sources if isinstance(source, dict)),
        )
    except (KeyError, TypeError):
        raise ApiError("invalid_response") from None


class BackendClient:
    """Speak the device contract over HTTP with bounded waits and safe errors."""

    def __init__(
        self, base_url: str, *, timeout_seconds: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Bind to one backend origin; transport injection supports offline tests."""
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._transport = transport

    def health(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        """Return the health payload, or raise ApiError; used for boot readiness."""
        payload = self._request("GET", HEALTH_PATH, timeout_seconds)
        if not isinstance(payload, dict):
            raise ApiError("invalid_response")
        return payload

    def pending(self, timeout_seconds: float = 10.0) -> list[dict[str, Any]]:
        """Return due follow-up items; the MVP backend always returns an empty list."""
        payload = self._request("GET", PENDING_PATH, timeout_seconds)
        if not isinstance(payload, list):
            raise ApiError("invalid_response")
        return [item for item in payload if isinstance(item, dict)]

    def submit_turn(
        self, *, device_id: str, session_id: str, turn_id: str, audio: bytes,
    ) -> TurnResult:
        """Post one recorded utterance and return the parsed nine-field response.

        `turn_id` is the client's idempotency key (design.md 5.1): a retry of
        the same turn returns the stored result instead of repeating the work.
        Raises ApiError for transport failures, a non-200 status or a body
        that does not match the contract.
        """
        files = {"audio": ("turn.wav", audio, "audio/wav")}
        data = {"device_id": device_id, "session_id": session_id, "turn_id": turn_id}
        return _parsed_turn(
            self._request("POST", TURN_PATH, self._timeout, data=data, files=files)
        )

    def _request(self, method: str, path: str, timeout: float, **kwargs: Any) -> object:
        """Send one bounded request to an allowlisted path and decode its JSON."""
        if path not in {TURN_PATH, PENDING_PATH, HEALTH_PATH}:
            raise ApiError("rejected")
        try:
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=min(5.0, timeout)),
                trust_env=False, follow_redirects=False, transport=self._transport,
            ) as client:
                response = client.request(method, self._base_url + path, **kwargs)
                if response.status_code != 200:
                    raise ApiError("rejected" if response.status_code < 500 else "unavailable")
                if len(response.content) > MAX_RESPONSE_BYTES:
                    raise ApiError("invalid_response")
                return response.json()
        except httpx.TimeoutException:
            raise ApiError("timeout") from None
        except (httpx.HTTPError, OSError):
            raise ApiError("unavailable") from None
        except ValueError:
            raise ApiError("invalid_response") from None
