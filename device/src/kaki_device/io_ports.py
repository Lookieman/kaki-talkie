# v1.1 | 20-Sep-2026 | WP6.2: the microphone reports progress, for the live countdown.
# v1.0 | 16-Sep-2026 | WP6.1 hardware ports: button, microphone, speaker, printer, display.
"""Describe the kiosk's hardware as ports the loop can talk to.

WP6.1 shipped the mock implementations; WP6.2 adds the GPIO button and ALSA
audio. The ESC/POS printer was withdrawn with WP6.3 on 18-Sep-2026, so no
real printer port will ever exist: real mode ships a printer that refuses,
which the loop already survives. Keeping the hardware behind protocols is
what lets the whole turn loop run and be tested on the Mac, and it keeps the
hardware details out of the state machine.

The LED ring is deliberately absent. The owner dropped it from the MVP on
14-Sep-2026: the display carries all device state, so there is no LED port
and no LED code anywhere in this package.
"""

from typing import Callable, Protocol, runtime_checkable

# Called with the seconds still available while a recording runs, so the
# display can count down live (WP6.1 known limitation, closed by WP6.2).
Progress = Callable[[float], None]


class AudioCaptureError(RuntimeError):
    """Signal that recording failed; the loop shows an error and returns to idle."""


class PlaybackError(RuntimeError):
    """Signal that playback failed; the answer stays on the display."""


class PrinterError(RuntimeError):
    """Signal that printing failed.

    WP6-AT-09 requires a printer failure never to suppress the spoken answer,
    so the loop records this and carries on.
    """


@runtime_checkable
class ButtonPort(Protocol):
    """The dome button on GPIO 17, debounced by its implementation."""

    def wait_for_press(self, timeout_seconds: float | None = None) -> bool:
        """Block until the button is pressed; return False when the wait timed out."""

    def is_pressed(self) -> bool:
        """Report the current physical state without blocking."""


@runtime_checkable
class MicrophonePort(Protocol):
    """Records one utterance as 16 kHz mono PCM WAV bytes."""

    def record(self, max_seconds: float, stop_when_released: bool = True,
               on_progress: Progress | None = None) -> bytes:
        """Return recorded WAV bytes, stopping at `max_seconds` at the latest.

        `on_progress`, when given, receives the remaining seconds while the
        recording runs; a mock may call it once or not at all. Raises
        AudioCaptureError when the capture device is unusable.
        """


@runtime_checkable
class SpeakerPort(Protocol):
    """Plays reply audio through the Jabra Speak."""

    def play(self, audio: bytes) -> None:
        """Play WAV bytes, returning when playback finishes or `stop` interrupts."""

    def stop(self) -> None:
        """Stop playback immediately; safe to call when nothing is playing.

        A button press during playback interrupts the answer and starts a new
        recording, so this must return promptly.
        """

    def is_playing(self) -> bool:
        """Report whether audio is currently playing."""


@runtime_checkable
class PrinterPort(Protocol):
    """Prints a slip. WP6.3 replaces the mock with the ESC/POS implementation."""

    def print_slip(self, slip_text: str) -> None:
        """Print one slip; raises PrinterError when the printer is unavailable."""


@runtime_checkable
class DisplayPort(Protocol):
    """Shows one frame at a time on the kiosk display."""

    def show(self, frame: object) -> None:
        """Render a `display.layout.Frame`; replaces whatever was on screen."""

    def close(self) -> None:
        """Release the display; safe to call more than once."""
