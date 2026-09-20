# v1.0 | 20-Sep-2026 | WP6.2 dome button on GPIO 17 through gpiozero, debounced.
"""Drive the dome button as a `ButtonPort`, debounced in hardware terms.

The button is wired from GPIO 17 to ground (setup.md 29.1), so the pin uses
the internal pull-up and a press reads active-low. Debounce is gpiozero's
`bounce_time`: contact rattle inside the window is one press, which is
WP6-AT-01.

gpiozero comes from apt on the Pi (`python3-gpiozero`, setup.md 29.3) and is
deliberately absent from the Mac and from `device/pyproject.toml`. The import
therefore happens at construction, not at module import, so Tier A can test
this module with an injected factory on a machine that has no GPIO at all.

One semantic difference from the scripted mock is worth knowing: the mock
queues press *events*, while a real button reports *level*. A user still
holding the button when the loop returns to idle starts the next recording
immediately, which is the behaviour a hold-to-talk kiosk wants.
"""

from typing import Callable


class GpioButton:
    """The dome button on a GPIO pin; satisfies `io_ports.ButtonPort`."""

    def __init__(self, pin: int, debounce_seconds: float,
                 button_factory: Callable | None = None) -> None:
        """Open the pin with pull-up and debounce; raises when GPIO is unusable.

        `button_factory` exists for tests; the default imports gpiozero here
        so the Mac never needs it. A missing gpiozero raises RuntimeError
        naming the install step rather than a bare ImportError.
        """
        if button_factory is None:
            try:
                from gpiozero import Button as button_factory
            except ImportError as error:
                raise RuntimeError(
                    "gpiozero is not installed; on the Pi run the setup.md 29.3 "
                    "apt install (python3-gpiozero)."
                ) from error
        self._button = button_factory(
            pin, pull_up=True,
            bounce_time=debounce_seconds if debounce_seconds > 0 else None,
        )

    def wait_for_press(self, timeout_seconds: float | None = None) -> bool:
        """Block until pressed; return False when the wait timed out."""
        return bool(self._button.wait_for_press(timeout=timeout_seconds))

    def is_pressed(self) -> bool:
        """Report the current physical state without blocking."""
        return bool(self._button.is_pressed)
