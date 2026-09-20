# v1.0 | 20-Sep-2026 | WP6.2 GPIO button: wiring arguments, debounce, delegation.
"""Prove the GPIO button wrapper without GPIO, via an injected factory.

The real proof of WP6-AT-01 is the owner rattling the dome at the Pi
(runbook 11.2 WP6.2); these tests pin what the wrapper asks gpiozero for -
the pin, the pull-up and the debounce window - so the rattle test cannot pass
by accident on an undebounced pin.
"""

import unittest

from kaki_device.gpio_button import GpioButton
from kaki_device.io_ports import ButtonPort


class FakeGpioZeroButton:
    """Stand in for gpiozero.Button and record how it was constructed."""

    instances: list["FakeGpioZeroButton"] = []

    def __init__(self, pin, pull_up=None, bounce_time=None):
        self.pin = pin
        self.pull_up = pull_up
        self.bounce_time = bounce_time
        self.is_pressed = False
        self.waits: list[float | None] = []
        self.wait_result = True
        FakeGpioZeroButton.instances.append(self)

    def wait_for_press(self, timeout=None):
        self.waits.append(timeout)
        return self.wait_result


class GpioButtonTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeGpioZeroButton.instances.clear()

    def build(self, pin: int = 17, debounce: float = 0.05) -> GpioButton:
        return GpioButton(pin, debounce, button_factory=FakeGpioZeroButton)

    def test_opens_the_configured_pin_with_pull_up_and_debounce(self):
        self.build(pin=17, debounce=0.05)
        fake = FakeGpioZeroButton.instances[0]
        self.assertEqual((fake.pin, fake.pull_up, fake.bounce_time), (17, True, 0.05))

    def test_zero_debounce_disables_bounce_time_rather_than_passing_zero(self):
        # gpiozero treats bounce_time=0 differently from None; None means raw.
        self.build(debounce=0.0)
        self.assertIsNone(FakeGpioZeroButton.instances[0].bounce_time)

    def test_wait_for_press_delegates_the_timeout_and_returns_a_bool(self):
        button = self.build()
        fake = FakeGpioZeroButton.instances[0]
        self.assertTrue(button.wait_for_press(timeout_seconds=1.5))
        fake.wait_result = None  # gpiozero returns falsy on timeout
        self.assertFalse(button.wait_for_press(timeout_seconds=0))
        self.assertEqual(fake.waits, [1.5, 0])

    def test_is_pressed_reports_the_level_as_a_bool(self):
        button = self.build()
        fake = FakeGpioZeroButton.instances[0]
        self.assertFalse(button.is_pressed())
        fake.is_pressed = True
        self.assertTrue(button.is_pressed())

    def test_satisfies_the_button_port_protocol(self):
        self.assertIsInstance(self.build(), ButtonPort)

    def test_missing_gpiozero_names_the_install_step(self):
        # On the Mac the default factory import fails; the message must say
        # what to do on the Pi rather than leak a bare ImportError.
        try:
            import gpiozero  # noqa: F401
        except ImportError:
            with self.assertRaises(RuntimeError) as caught:
                GpioButton(17, 0.05)
            self.assertIn("setup.md 29.3", str(caught.exception))
        else:
            self.skipTest("gpiozero is installed here; the Pi path applies")


if __name__ == "__main__":
    unittest.main()
