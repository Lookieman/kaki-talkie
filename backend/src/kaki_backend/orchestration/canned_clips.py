# v1.0 | 24-Sep-2026 | WP6.8 voice revision: play pre-rendered clips for canned replies.
"""Speak fixed canned replies from pre-rendered clips, falling back to the wrapped port.

The booking reply, the refusals and the action confirmations are authored
text, never model output, so each one can be recorded once in a better voice
than run-time `say` and played back verbatim. `CannedClipTts` wraps whichever
TTS port the configuration built and consults a registry first:

- the registry maps a message ID and language to the exact text of that
  message, taken from the catalogues that own the wording
  (`book_action.BOOKING_REPLIES`, `intent_router.REFUSAL_MESSAGES`,
  `intent_router.ACTION_MESSAGES`), so the copy lives in one place;
- a `synthesize` call whose `(text, language)` pair matches an entry plays
  that entry's clip, `clips/<message_id>.<language>.wav` in this package;
- anything else - a live answer, a clip that was never recorded, an invalid
  WAV, or copy edited since the clip was recorded - goes to the wrapped port
  unchanged. Matching on the text means a stale clip can never speak words
  the screen does not show: edited copy simply falls back to `say` until the
  clip is recaptured.

Clips skip the WP6.8 spoken-form normaliser: they are recorded in spoken form
already. Every call writes one `tts_source=clip|<fallback>` line to stderr,
with the message ID for a clip; reply text is never written.
"""

import sys
from base64 import b64encode
from dataclasses import dataclass
from importlib.resources import files
from io import BytesIO
from typing import Callable, TextIO
from wave import Error as WaveError
from wave import open as wave_open

from kaki_backend.actions.book_action import BOOKING_REPLIES
from kaki_backend.contracts.ports import TtsPort
from kaki_backend.orchestration.intent_router import ACTION_MESSAGES, REFUSAL_MESSAGES

CLIP_DIRECTORY = "clips"
AUDIO_DATA_URL_PREFIX = "data:audio/wav;base64,"
BOOKING_REPLY_ID = "booking_reply"

ClipReader = Callable[[str], bytes | None]


@dataclass(frozen=True)
class CannedClip:
    """One registry entry: a message ID, its language and the exact text it speaks."""

    message_id: str
    language: str
    text: str

    @property
    def filename(self) -> str:
        """Return the clip's file name, `<message_id>.<language>.wav`."""
        return f"{self.message_id}.{self.language}.wav"


def canned_clip_registry() -> tuple[CannedClip, ...]:
    """Return every canned reply that may have a clip, built from the owning catalogues.

    Message IDs reuse the existing enum values (`no_coverage`,
    `credential_action`, `print_confirmation`, `nothing_to_act_on`) plus
    `booking_reply`. An entry without a recorded file simply falls back.
    """
    entries = [
        CannedClip(BOOKING_REPLY_ID, language, text)
        for language, text in BOOKING_REPLIES.items()
    ]
    for catalogue in (REFUSAL_MESSAGES, ACTION_MESSAGES):
        for language, messages in catalogue.items():
            entries.extend(
                CannedClip(kind.value, language, message.reply_text)
                for kind, message in messages.items()
            )
    return tuple(entries)


def read_packaged_clip(filename: str) -> bytes | None:
    """Return a packaged clip's bytes, or None when it has not been recorded."""
    try:
        return files("kaki_backend").joinpath(CLIP_DIRECTORY, filename).read_bytes()
    except (FileNotFoundError, OSError):
        return None


def is_playable_wav(audio: bytes) -> bool:
    """Accept only non-empty uncompressed 16-bit PCM WAV, as the say adapter does.

    Mono or stereo is accepted; the Pi and the browser both read the header.
    """
    try:
        with wave_open(BytesIO(audio), "rb") as recording:
            return (
                recording.getcomptype() == "NONE"
                and recording.getnchannels() in (1, 2)
                and recording.getsampwidth() == 2
                and recording.getframerate() > 0
                and recording.getnframes() > 0
            )
    except (WaveError, EOFError):
        return False


class CannedClipTts:
    """Play a recorded clip for an exact canned reply; delegate everything else."""

    def __init__(
        self, inner: TtsPort, *, fallback_source: str = "say",
        registry: tuple[CannedClip, ...] | None = None,
        clip_reader: ClipReader = read_packaged_clip,
        log_stream: TextIO | None = None,
    ) -> None:
        """Wrap `inner`; `fallback_source` names it in the log line (`say` or `canned`).

        `registry`, `clip_reader` and `log_stream` exist for tests. Clips are
        read on each hit rather than cached, so a clip copied in while the
        backend runs is used on the next turn.
        """
        self._inner = inner
        self._fallback_source = fallback_source
        entries = canned_clip_registry() if registry is None else registry
        self._by_text = {(entry.language, entry.text): entry for entry in entries}
        self._read = clip_reader
        self._log_stream = log_stream

    def ready(self) -> bool:
        """Report the wrapped port's readiness; clips are optional and never gate it."""
        return self._inner.ready()

    def synthesize(self, reply_text: str, language: str = "en") -> str | None:
        """Return the matching clip as a WAV data URL, or the wrapped port's result.

        Raises whatever the wrapped port raises on the fallback path. Side
        effects: reads at most one packaged file and writes one log line.
        """
        entry = self._by_text.get((language, reply_text))
        if entry is not None:
            audio = self._read(entry.filename)
            if audio and is_playable_wav(audio):
                self._log(f"tts_source=clip message_id={entry.message_id} language={language}")
                return AUDIO_DATA_URL_PREFIX + b64encode(audio).decode("ascii")
        self._log(f"tts_source={self._fallback_source} language={language}")
        if language == "en":
            # Keep the English call exactly as the pipeline makes it.
            return self._inner.synthesize(reply_text)
        return self._inner.synthesize(reply_text, language=language)

    def _log(self, line: str) -> None:
        stream = self._log_stream or sys.stderr
        print(line, file=stream, flush=True)
