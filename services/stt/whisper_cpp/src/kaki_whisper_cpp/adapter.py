# v1.0 | 07-Sep-2026 | Transcribe bounded PCM WAV through the local Whisper server.
"""Use whisper.cpp v1.7.6 HTTP responses behind the backend's STT port.

The model stays in its own process. This adapter sends anonymous, normalised
audio in memory, never follows redirects or environment proxies, and never
logs audio, transcript text, upstream error bodies or caller filenames.
"""

import io
import ipaddress
import json
import math
import wave
from time import monotonic
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from kaki_backend.contracts.ports import LanguageEvidence, SttError, Transcription

MAX_RESPONSE_BYTES = 256 * 1024
MAX_WAV_BYTES = 16 * 16000 * 2 + 4096
READINESS_TIMEOUT_SECONDS = 2.0


class WhisperStt:
    """Call a loopback-only Whisper server with bounded I/O and typed results."""

    def __init__(
        self, url: str = "http://127.0.0.1:8080", *, timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Validate the local endpoint; transport injection supports deterministic tests."""
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme == "http" and parsed.port is not None
                and ipaddress.ip_address(parsed.hostname or "").is_loopback
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Whisper URL must be a plain HTTP literal loopback address and port.")
        if not math.isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 120:
            raise ValueError("Whisper timeout must be between 0.1 and 120 seconds.")
        self._url = url
        self._timeout = timeout_seconds
        self._transport = transport

    def ready(self) -> bool:
        """Return true only for a valid ready response; never load/restart the model."""
        try:
            return self._request("GET", "/health", READINESS_TIMEOUT_SECONDS) == {"status": "ok"}
        except SttError:
            return False

    def transcribe(self, audio: bytes) -> Transcription:
        """Recognise bounded 16 kHz mono PCM WAV or raise a sanitised SttError."""
        _validate_wav(audio)
        payload = self._request(
            "POST", "/inference", self._timeout,
            files={"file": ("audio.wav", audio, "audio/wav")},
            data={"response_format": "verbose_json", "language": "auto", "temperature": "0"},
        )
        try:
            if not isinstance(payload, dict) or "error" in payload:
                raise SttError("invalid_response")
            text = payload.get("text")
            if not isinstance(text, str):
                raise SttError("invalid_response")
            if not text.strip():
                raise SttError("empty_transcript")
            language = payload.get("detected_language", payload.get("language"))
            evidence = None
            if language is not None:
                if not isinstance(language, str) or not language.strip():
                    raise SttError("invalid_response")
                evidence = LanguageEvidence(
                    language=language.strip(), probability=payload.get("detected_language_probability")
                )
            elif payload.get("detected_language_probability") is not None:
                raise SttError("invalid_response")
            return Transcription(text=text.strip(), evidence=evidence)
        except ValidationError:
            raise SttError("invalid_response") from None

    def _request(self, method: str, path: str, timeout: float, **kwargs: object) -> object:
        """Cap response bytes and network waits, closing request resources on every path."""
        try:
            started = monotonic()
            with httpx.Client(
                timeout=httpx.Timeout(timeout, connect=min(2.0, timeout)),
                trust_env=False, follow_redirects=False, transport=self._transport,
                headers={"Accept-Encoding": "identity"},
            ) as client:
                with client.stream(method, self._url + path, **kwargs) as response:
                    if response.status_code != 200:
                        raise SttError("unavailable")
                    if response.headers.get("content-encoding", "identity") != "identity":
                        raise SttError("invalid_response")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if monotonic() - started > timeout:
                            raise SttError("timeout")
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise SttError("invalid_response")
                        body.extend(chunk)
                    return json.loads(body)
        except httpx.TimeoutException:
            raise SttError("timeout") from None
        except (httpx.HTTPError, OSError):
            raise SttError("unavailable") from None
        except (ValueError, UnicodeError):
            raise SttError("invalid_response") from None


def _validate_wav(audio: bytes) -> None:
    """Reject non-normalised input before it crosses the model service boundary."""
    if not audio or len(audio) > MAX_WAV_BYTES:
        raise SttError("invalid_audio")
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            if (recording.getframerate(), recording.getnchannels(), recording.getsampwidth(),
                recording.getcomptype()) != (16000, 1, 2, "NONE"):
                raise SttError("invalid_audio")
            frames = recording.getnframes()
            if not 0 < frames <= 16 * 16000 or len(recording.readframes(frames)) != frames * 2:
                raise SttError("invalid_audio")
    except (wave.Error, EOFError):
        raise SttError("invalid_audio") from None
