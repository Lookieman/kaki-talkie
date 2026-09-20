# v1.1 | 20-Sep-2026 | WP6.2: the fixture microphone accepts the progress callback.
# v1.0 | 16-Sep-2026 | WP6.1 mock button, microphone, speaker, printer and display.
"""Fake the kiosk hardware so the whole loop runs on the Mac.

These are the WP6.1 deliverable that makes WP6.2 safe: the turn loop, the
state machine and the display can all be exercised, and regressions caught,
before a button or a microphone exists. They are also what the Tier A tests
drive, so the behaviour they encode is the behaviour the real ports must
match.

Every mock is deliberately dumb and observable: it records what it was asked
to do so a test or the evidence harness can assert on it.
"""

import io
import wave
from pathlib import Path
from time import monotonic, sleep
from typing import Callable

from kaki_device.display.layout import Frame
from kaki_device.io_ports import AudioCaptureError

Clock = Callable[[], float]


def silent_wav(seconds: float = 1.0, framerate: int = 16000) -> bytes:
    """Return valid 16 kHz mono PCM WAV silence, the recorder's default output."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(framerate)
        recording.writeframes(b"\x00\x00" * int(framerate * seconds))
    return buffer.getvalue()


class ScriptedButton:
    """Press the button at scheduled times, or on demand from a test.

    `schedule` holds monotonic-clock offsets from construction. An empty
    schedule means the button never fires by itself; `press()` still works,
    which is what the keyboard-driven mock run uses.
    """

    def __init__(self, schedule: tuple[float, ...] = (), clock: Clock = monotonic) -> None:
        """Record the schedule and start the clock this button measures against."""
        self._pending = sorted(schedule)
        self._clock = clock
        self._started = clock()
        self._manual = 0
        self.presses: list[float] = []

    def press(self) -> None:
        """Queue one immediate press; the next wait returns True."""
        self._manual += 1

    def _due(self) -> bool:
        elapsed = self._clock() - self._started
        return bool(self._pending) and self._pending[0] <= elapsed

    def wait_for_press(self, timeout_seconds: float | None = None) -> bool:
        """Return True when a press arrives, False when the wait times out."""
        deadline = None if timeout_seconds is None else self._clock() + timeout_seconds
        while True:
            if self._manual:
                self._manual -= 1
                self.presses.append(self._clock() - self._started)
                return True
            if self._due():
                self._pending.pop(0)
                self.presses.append(self._clock() - self._started)
                return True
            if deadline is not None and self._clock() >= deadline:
                return False
            sleep(0)

    def is_pressed(self) -> bool:
        """Report whether a press is waiting to be consumed."""
        return bool(self._manual) or self._due()


class FixtureMicrophone:
    """Return a fixture WAV instead of recording, and record what was asked."""

    def __init__(self, audio_path: Path | None = None, seconds: float = 1.0) -> None:
        """Use `audio_path` when given, otherwise generated silence."""
        self._audio_path = audio_path
        self._seconds = seconds
        self.recordings: list[float] = []

    def record(self, max_seconds: float, stop_when_released: bool = True,
               on_progress=None) -> bytes:
        """Return the fixture bytes; raises AudioCaptureError for an unusable file.

        A fixture returns instantly, so `on_progress` is accepted and never
        called: the loop has already shown the full allowance, and a mock
        turn's display sequence stays recording -> thinking -> answer.
        """
        self.recordings.append(max_seconds)
        if self._audio_path is None:
            return silent_wav(min(self._seconds, max_seconds))
        try:
            audio = self._audio_path.read_bytes()
        except OSError as error:
            raise AudioCaptureError(f"cannot read {self._audio_path}: {error}") from None
        if not audio:
            raise AudioCaptureError(f"{self._audio_path} is empty")
        return audio


class RecordingSpeaker:
    """Record what would have been played, and honour interruption.

    With `realtime` false, playback returns immediately and reports the audio's
    real duration; the loop's timing logic is exercised without the wait. With
    it true, the mock sleeps for the duration so an owner can interrupt a real
    playback by hand during a mock run.
    """

    def __init__(self, realtime: bool = False, clock: Clock = monotonic) -> None:
        """Choose immediate or real-time playback."""
        self._realtime = realtime
        self._clock = clock
        self._playing = False
        self.played: list[bytes] = []
        self.durations: list[float] = []
        self.interruptions = 0

    @staticmethod
    def duration_seconds(audio: bytes) -> float:
        """Return the WAV's duration, or 0 when the bytes are not readable WAV."""
        try:
            with wave.open(io.BytesIO(audio), "rb") as recording:
                framerate = recording.getframerate()
                return recording.getnframes() / framerate if framerate else 0.0
        except (wave.Error, EOFError):
            return 0.0

    def play(self, audio: bytes) -> None:
        """Play the audio, or pretend to; `stop` ends it early."""
        self.played.append(audio)
        duration = self.duration_seconds(audio)
        self.durations.append(duration)
        if not self._realtime:
            return
        self._playing = True
        deadline = self._clock() + duration
        while self._playing and self._clock() < deadline:
            sleep(0.01)
        self._playing = False

    def stop(self) -> None:
        """Interrupt playback; counted so a test can prove the interruption."""
        if self._playing:
            self.interruptions += 1
        self._playing = False

    def is_playing(self) -> bool:
        """Report whether playback is in progress."""
        return self._playing


class LoggingPrinter:
    """Collect slips instead of printing them; WP6.3 brings the real printer."""

    def __init__(self, log_path: Path | None = None) -> None:
        """Optionally append every slip to `log_path` for owner evidence."""
        self._log_path = log_path
        self.slips: list[str] = []

    def print_slip(self, slip_text: str) -> None:
        """Record one slip, and append it to the log file when configured."""
        self.slips.append(slip_text)
        if self._log_path is not None:
            with self._log_path.open("a", encoding="utf-8") as log:
                log.write(slip_text.rstrip() + "\n---\n")


class CollectingDisplay:
    """Keep every frame it was shown, so tests assert on what the user saw."""

    def __init__(self) -> None:
        """Start with no frames."""
        self.frames: list[Frame] = []
        self.closed = False

    def show(self, frame: Frame) -> None:
        """Record one frame."""
        self.frames.append(frame)

    def close(self) -> None:
        """Mark the display closed."""
        self.closed = True

    @property
    def states(self) -> list[str]:
        """Return the state of each frame shown, in order."""
        return [frame.state.value for frame in self.frames]


def fixed_measure(character_width: float = 0.55) -> Callable[[str, int], int]:
    """Return a deterministic text-measure function for mock and test use.

    Real fonts vary by glyph; a fixed ratio is enough to exercise wrapping and
    the size-step logic, and it keeps Tier A independent of installed fonts.
    """
    def measure(text: str, size: int) -> int:
        return int(len(text) * size * character_width)

    return measure
