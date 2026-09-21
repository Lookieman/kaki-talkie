# v1.2 | 21-Sep-2026 | WP6.8: English voice, speaking rate and the spoken-form normaliser.
# v1.1 | 13-Sep-2026 | WP5.1: speak Malay with the configured voice; English stays unchanged.
# v1.0 | 09-Sep-2026 | Synthesise playable English speech through the local macOS say binary.
"""Use the macOS `say` command behind the backend's TTS port.

The engine is the operating system's bundled speech synthesiser, so there is
no model download, cache, network service or credential. Reply text is passed
to `say` on standard input (never on the command line), synthesis writes
22.05 kHz mono signed 16-bit PCM WAV to a private temporary file, and the
file is deleted on every path. Failures raise sanitised `TtsError` codes;
reply text and engine output are never logged.

WP5.1 adds a language argument, and WP6.8 gives both languages a named voice:
Jamie for English and Amira for Malay (`ms_MY`; Damayanti, `id_ID`, is the
documented fallback, setup.md 10.1.1), both at 150 words per minute. A voice
the host lacks makes `say` exit non-zero, which raises `TtsError` and
degrades the turn to text.

WP6.8 also normalises the text into its spoken form immediately before
synthesis (`spoken_form.to_spoken_form`). That transform is deliberately the
last thing to touch the reply: the contract's `reply_text`, the display text
and the printed slip all keep the written form, and only the bytes handed to
`say` carry list-marker stripping, spoken URLs, spelled acronyms and pauses.
"""

import shutil
import subprocess
import tempfile
from base64 import b64encode
from io import BytesIO
from math import isfinite
from pathlib import Path
from typing import Callable, Sequence
from wave import Error as WaveError
from wave import open as wave_open

from kaki_backend.contracts.ports import TtsError
from kaki_say_tts.spoken_form import to_spoken_form  #v1.2

MAX_TEXT_CHARS = 4096
SAY_DATA_FORMAT = "LEI16@22050"
DEFAULT_MALAY_VOICE = "Amira"  #v1.1
DEFAULT_ENGLISH_VOICE = "Jamie"  #v1.2
DEFAULT_RATE_WPM = 150  #v1.2
MAX_VOICE_NAME_CHARS = 64  #v1.1
# The normaliser adds `[[...]]` commands, so the bound is checked against the
# written text before expansion rather than after.
MIN_RATE_WPM = 80  #v1.2
MAX_RATE_WPM = 300  #v1.2

CommandRunner = Callable[[Sequence[str], str, float], None]


def _validated_voice(name: str, language: str) -> str:  #v1.2
    """Return a usable say voice name or raise; a leading dash would be an argument."""
    voice = name.strip()
    if not voice or len(voice) > MAX_VOICE_NAME_CHARS or voice.startswith("-"):
        raise ValueError(f"The {language} voice name must be a non-blank say voice name.")
    return voice


def _run_say(command: Sequence[str], text: str, timeout_seconds: float) -> None:
    """Run the synthesis command with the text on stdin; raise on any failure."""
    completed = subprocess.run(
        list(command), input=text.encode("utf-8"),
        capture_output=True, timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise TtsError("unavailable")


class SayTts:
    """Call the local `say` binary with bounded input, waits and output checks."""

    def __init__(
        self, *, timeout_seconds: float = 30.0, runner: CommandRunner | None = None,
        malay_voice: str = DEFAULT_MALAY_VOICE,  #v1.1
        english_voice: str = DEFAULT_ENGLISH_VOICE,  #v1.2
        rate_wpm: int = DEFAULT_RATE_WPM,  #v1.2
    ) -> None:
        """Validate the timeout, both voice names and the rate; runner injection supports tests."""
        if not isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 120:
            raise ValueError("TTS timeout must be between 0.1 and 120 seconds.")
        self._voices = {  #v1.2
            "ms": _validated_voice(malay_voice, "Malay"),
            "en": _validated_voice(english_voice, "English"),
        }
        if not MIN_RATE_WPM <= int(rate_wpm) <= MAX_RATE_WPM:  #v1.2
            raise ValueError(
                f"The speaking rate must be between {MIN_RATE_WPM} and {MAX_RATE_WPM} wpm."
            )
        self._rate = int(rate_wpm)  #v1.2
        self._timeout = timeout_seconds
        self._runner = runner or _run_say

    def ready(self) -> bool:
        """Report whether the `say` binary is available without synthesising speech."""
        return shutil.which("say") is not None

    def synthesize(self, reply_text: str, language: str = "en") -> str | None:  #v1.1
        """Return spoken reply audio as a WAV data URL or raise TtsError.

        `language` selects the configured voice (`en` Jamie, `ms` Amira); an
        unknown language falls back to the system voice rather than failing,
        so a new language speaks before it has a configured voice.

        The text is normalised into its spoken form here (WP6.8), so the
        caller's `reply_text` is unchanged and the written form survives in
        the contract. Side effects: creates and always deletes one private
        temporary file.
        """  #v1.2
        if not reply_text.strip() or len(reply_text) > MAX_TEXT_CHARS:
            raise TtsError("invalid_text")
        spoken = to_spoken_form(reply_text)  #v1.2
        if not spoken.strip():
            raise TtsError("invalid_text")
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        output_path = Path(handle.name)
        try:
            voice = self._voices.get(language)  #v1.1
            voice_arguments = ("-v", voice) if voice else ()
            command = (
                "say", "-o", str(output_path), f"--data-format={SAY_DATA_FORMAT}",
                *voice_arguments, "-r", str(self._rate), "-f", "-",  #v1.2
            )
            try:
                self._runner(command, spoken, self._timeout)  #v1.2
            except TtsError:
                raise
            except subprocess.TimeoutExpired:
                raise TtsError("timeout") from None
            except (OSError, ValueError):
                raise TtsError("unavailable") from None
            return _encode_validated_wav(output_path)
        finally:
            output_path.unlink(missing_ok=True)


def _encode_validated_wav(output_path: Path) -> str:
    """Read the synthesised file, require non-zero-duration PCM WAV, and encode it."""
    try:
        audio = output_path.read_bytes()
    except OSError:
        raise TtsError("invalid_output") from None
    try:
        with wave_open(BytesIO(audio), "rb") as recording:
            valid = (
                recording.getcomptype() == "NONE"
                and recording.getnchannels() == 1
                and recording.getsampwidth() == 2
                and recording.getframerate() > 0
                and recording.getnframes() > 0
            )
    except (WaveError, EOFError):
        raise TtsError("invalid_output") from None
    if not valid:
        raise TtsError("invalid_output")
    return "data:audio/wav;base64," + b64encode(audio).decode("ascii")
