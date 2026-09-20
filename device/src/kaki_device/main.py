#!/usr/bin/env python3
# v1.2 | 20-Sep-2026 | WP6.4: pass the service token and retry schedule to the client.
# v1.1 | 20-Sep-2026 | WP6.2: real mode drives the GPIO button, ALSA audio and the panel.
# v1.0 | 16-Sep-2026 | WP6.1 device entry point; mock I/O runs the loop on the Mac.
"""Start the kiosk loop, with real or mock hardware.

Two ways to run it:

    python -m kaki_device.main --mock            # Mac or Pi, no hardware needed
    python -m kaki_device.main --config ~/kaki-device.toml   # Pi, real hardware

Real mode (WP6.2) needs the dome button on the configured GPIO pin, the Jabra
Speak reachable under the configured ALSA card name, and the panel; it
refuses to start with a clear message when any of those is not configured or
present. There is no printer: the thermal printer was withdrawn on
18-Sep-2026, so real mode ships a printer port that declines every slip,
which the loop records and survives.

`--mock` with `--headless` runs entirely without a display, which is what the
evidence harness and `wp_check.py --unit WP6.1 --tier B` use to drive one
scripted turn against the live backend.
"""

import argparse
import sys
from pathlib import Path

from kaki_device.api_client import ApiError, BackendClient
from kaki_device.config import ConfigError, DeviceConfig, load_config
from kaki_device.mock_io import (
    CollectingDisplay,
    FixtureMicrophone,
    LoggingPrinter,
    RecordingSpeaker,
    ScriptedButton,
    fixed_measure,
)
from kaki_device.io_ports import PrinterError
from kaki_device.state_machine import TurnLoop


def build_parser() -> argparse.ArgumentParser:
    """Describe the device's command line; every option has a safe default."""
    parser = argparse.ArgumentParser(
        prog="kaki-device", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Device TOML file; KAKI_DEVICE_* exports override its values",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Use the mock button, microphone, speaker and printer (no hardware)",
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="With --mock, collect frames instead of opening a display",
    )
    parser.add_argument(
        "--turns", type=int, default=0,
        help="With --mock, run this many scripted turns and exit (0 means run forever)",
    )
    parser.add_argument(
        "--slip-log", type=Path, default=None,
        help="With --mock, append printed slips to this file",
    )
    return parser


class WithdrawnPrinter:
    """Decline every slip: the thermal printer was withdrawn on 18-Sep-2026.

    Raising keeps the outcome honest - `printed` stays False - and the loop
    already records and survives a refusing printer, so the spoken answer is
    never affected.
    """

    def print_slip(self, slip_text: str) -> None:
        """Refuse; no printer is fitted."""
        raise PrinterError("the thermal printer was withdrawn; no slip is printed.")


def _real_ports(config: DeviceConfig):
    """Build the WP6.2 hardware port set: GPIO button, ALSA audio, the panel.

    Imports the hardware-facing modules here so `--mock` never needs gpiozero
    or a display. Raises ConfigError for missing configuration so `run` can
    exit 2 with one clear message.
    """
    if not config.audio.card:
        raise ConfigError(
            "audio.card is not set. Find the stable ALSA name with `arecord -L` "
            "and set [audio] card, or KAKI_DEVICE_AUDIO__CARD (runbook 11.1 WP6.2)."
        )
    from kaki_device.alsa_audio import AlsaMicrophone, AlsaSpeaker
    from kaki_device.display.pygame_backend import PygameDisplay
    from kaki_device.gpio_button import GpioButton

    button = GpioButton(config.button.pin, config.button.debounce_seconds)
    microphone = AlsaMicrophone(
        config.audio.card, config.audio.capture_rate, held=button.is_pressed,
    )
    speaker = AlsaSpeaker(config.audio.card, config.audio.playback_rate)
    screen = PygameDisplay(config.display_width, config.display_height)
    return button, microphone, speaker, WithdrawnPrinter(), screen, screen.measure()


def _mock_ports(config: DeviceConfig, headless: bool, slip_log: Path | None):
    """Build the mock port set and its text-measure function."""
    button = ScriptedButton(config.mock.button_presses)
    microphone = FixtureMicrophone(config.mock.audio_path)
    speaker = RecordingSpeaker(realtime=config.mock.playback_realtime)
    printer = LoggingPrinter(slip_log)
    if headless:
        display, measure = CollectingDisplay(), fixed_measure()
    else:
        from kaki_device.display.pygame_backend import PygameDisplay

        screen = PygameDisplay(config.display_width, config.display_height)
        display, measure = screen, screen.measure()
    return button, microphone, speaker, printer, display, measure


def run(arguments: argparse.Namespace) -> int:
    """Start the loop and return the process exit status."""
    try:
        config = load_config(arguments.config)
    except ConfigError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2

    client = BackendClient(
        config.backend_url, timeout_seconds=config.request_timeout_seconds,
        token=config.token,  #v1.2
        retry_attempts=config.retry_attempts,  #v1.2
        retry_backoff_seconds=config.retry_backoff_seconds,  #v1.2
    )
    try:
        health = client.health()
    except ApiError as error:
        print(f"FAIL: backend {config.backend_url} is not answering ({error.code}).",
              file=sys.stderr)
        return 1
    print(f"backend {config.backend_url} status {health.get('status')!r}", file=sys.stderr)

    try:
        if arguments.mock:
            button, microphone, speaker, printer, display, measure = _mock_ports(
                config, arguments.headless, arguments.slip_log
            )
        else:
            button, microphone, speaker, printer, display, measure = _real_ports(config)
    except (ConfigError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    loop = TurnLoop(
        config, client, button=button, microphone=microphone, speaker=speaker,
        printer=printer, display=display, measure=measure,
    )
    try:
        if arguments.turns > 0:
            for _ in range(arguments.turns):
                outcome = loop.run_turn()
                print(
                    f"turn {outcome.turn_id} state={outcome.state} "
                    f"printed={outcome.printed} error={outcome.error_code}",
                    file=sys.stderr,
                )
            return 1 if any(turn.failed_locally for turn in loop.outcomes) else 0
        loop.show_idle()
        loop.run_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        display.close()


def main() -> int:
    """Parse arguments and run the device."""
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
