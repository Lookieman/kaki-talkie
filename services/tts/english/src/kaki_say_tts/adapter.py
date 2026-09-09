# v1.0 | 09-Sep-2026 | Synthesise playable English speech through the local macOS say binary.
"""Use the macOS `say` command behind the backend's TTS port.

The engine is the operating system's bundled speech synthesiser, so there is
no model download, cache, network service or credential. Reply text is passed
to `say` on standard input (never on the command line), synthesis writes
22.05 kHz mono signed 16-bit PCM WAV to a private temporary file, and the
file is deleted on every path. Failures raise sanitised `TtsError` codes;
reply text and engine output are never logged.
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

MAX_TEXT_CHARS = 4096
SAY_DATA_FORMAT = "LEI16@22050"

CommandRunner = Callable[[Sequence[str], str, float], None]


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
    ) -> None:
        """Validate the synthesis timeout; runner injection supports deterministic tests."""
        if not isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 120:
            raise ValueError("TTS timeout must be between 0.1 and 120 seconds.")
        self._timeout = timeout_seconds
        self._runner = runner or _run_say

    def ready(self) -> bool:
        """Report whether the `say` binary is available without synthesising speech."""
        return shutil.which("say") is not None

    def synthesize(self, reply_text: str) -> str | None:
        """Return spoken reply audio as a WAV data URL or raise TtsError.

        Side effects: creates and always deletes one private temporary file.
        """
        if not reply_text.strip() or len(reply_text) > MAX_TEXT_CHARS:
            raise TtsError("invalid_text")
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        output_path = Path(handle.name)
        try:
            command = ("say", "-o", str(output_path), f"--data-format={SAY_DATA_FORMAT}", "-f", "-")
            try:
                self._runner(command, reply_text, self._timeout)
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
