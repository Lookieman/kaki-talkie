# v1.0 | 16-Sep-2026 | WP6.1 hardware ports: button, microphone, speaker, printer, display.
"""Describe the kiosk's hardware as ports the loop can talk to.

WP6.1 ships the mock implementations only; WP6.2 adds the GPIO button and
ALSA audio, and WP6.3 the ESC/POS printer. Keeping them behind protocols is
what lets the whole turn loop run and be tested on the Mac, and it keeps the
hardware details out of the state machine.

The LED ring is deliberately absent. The owner dropped it from the MVP on
14-Sep-2026: the display carries all device state, so there is no LED port
and no LED code anywhere in this package.
"""

from typing import Protocol, runtime_checkable


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

    def record(self, max_seconds: float, stop_when_released: bool = True) -> bytes:
        """Return recorded WAV bytes, stopping at `max_seconds` at the latest.

        Raises AudioCaptureError when the capture device is unusable.
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
