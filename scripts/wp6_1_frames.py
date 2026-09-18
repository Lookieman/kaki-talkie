#!/usr/bin/env python3
# v1.0 | 16-Sep-2026 | Print the device's frames as text and prove local recovery (WP6.1).
"""Show what the kiosk display says, and prove the loop recovers, without a screen.

Two owner-facing modes, both used by `scripts/wp6_1_evidence.sh` and both safe
to run by hand:

    python scripts/wp6_1_frames.py --fixture <wav>   # one mock turn, frame by frame
    python scripts/wp6_1_frames.py --recovery        # failure and session checks

The first prints every frame a user would see during one real turn, with the
sizes the renderer would use, so the owner can judge legibility before the
panel exists. It posts one turn to the running backend, like any device turn.

The second needs no backend: it drives the loop with a failing client and a
fake clock to show the error frame, the return to idle, and the idle session
rotation. It prints one `key: yes|no` line per property for the harness.

Neither mode touches hardware: the mock button, microphone, speaker and
printer stand in for the Pi (runbook 11.1 WP6.1).
"""

import argparse
import sys
from itertools import count
from pathlib import Path

DEVICE_SRC = Path(__file__).resolve().parent.parent / "device/src"
if str(DEVICE_SRC) not in sys.path:
    sys.path.insert(0, str(DEVICE_SRC))

from kaki_device.api_client import ApiError, BackendClient  # noqa: E402
from kaki_device.config import DeviceConfig, MockSettings, load_config  # noqa: E402
from kaki_device.display.layout import BODY_SIZES, DisplayState  # noqa: E402
from kaki_device.mock_io import (  # noqa: E402
    CollectingDisplay,
    FixtureMicrophone,
    LoggingPrinter,
    RecordingSpeaker,
    ScriptedButton,
    fixed_measure,
)
from kaki_device.state_machine import TurnLoop  # noqa: E402

RULE = "-" * 72


class FailingClient:
    """Refuse every turn, so the loop's local recovery can be observed."""

    def __init__(self, code: str = "timeout") -> None:
        """Fail with `code` on every submission."""
        self._code = code

    def submit_turn(self, **kwargs) -> None:
        """Always raise; the loop should show the error frame and recover."""
        raise ApiError(self._code)

    def pending(self) -> list:
        """Return no due items, like the MVP backend."""
        return []


class StepClock:
    """A clock the caller advances by hand."""

    def __init__(self) -> None:
        """Start at a fixed point so runs read the same."""
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


def build_loop(config: DeviceConfig, client, clock=None, slip_log: Path | None = None):
    """Assemble a loop from mock ports; returns the loop and its display."""
    display = CollectingDisplay()
    identifiers = count(1)
    loop = TurnLoop(
        config, client, button=ScriptedButton(),
        microphone=FixtureMicrophone(config.mock.audio_path),
        speaker=RecordingSpeaker(), printer=LoggingPrinter(slip_log), display=display,
        measure=fixed_measure(), clock=clock or (lambda: 0.0),
        sleep=lambda seconds: None, new_id=lambda: f"frames-{next(identifiers)}",
    )
    return loop, display


def print_frames(display: CollectingDisplay) -> None:
    """Print each captured frame as the text and sizes the panel would show."""
    for number, frame in enumerate(display.frames, start=1):
        print(RULE)
        print(f"frame {number}: {frame.state.value}"
              + ("  (text truncated to fit)" if frame.truncated else ""))
        for line in frame.lines:
            print(f"  [{line.size:>3} pt] {line.text}")
    print(RULE)


def show_turn(arguments: argparse.Namespace) -> int:
    """Run one mock turn against the backend and print every frame it showed."""
    config = load_config(arguments.config)
    config = DeviceConfig(
        backend_url=config.backend_url, device_id=config.device_id,
        record_seconds=config.record_seconds,
        request_timeout_seconds=config.request_timeout_seconds,
        session_idle_minutes=config.session_idle_minutes,
        print_policy=config.print_policy, display_width=config.display_width,
        display_height=config.display_height,
        mock=MockSettings(audio_path=arguments.fixture),
    )
    client = BackendClient(config.backend_url, timeout_seconds=config.request_timeout_seconds)
    loop, display = build_loop(config, client)
    loop.show_idle()
    outcome = loop.run_turn()
    print(f"turn {outcome.turn_id} state={outcome.state} printed={outcome.printed} "
          f"spoke={outcome.spoke} error={outcome.error_code}")
    print(f"display: {config.display_width}x{config.display_height}, "
          f"body sizes {BODY_SIZES}")
    print_frames(display)
    if outcome.error_code is not None:
        print(f"FAIL: the turn failed locally ({outcome.error_code}).", file=sys.stderr)
        return 1
    return 0


def show_recovery(arguments: argparse.Namespace) -> int:
    """Prove error recovery and session rotation with no backend and a fake clock."""
    clock = StepClock()
    config = DeviceConfig()
    loop, display = build_loop(config, FailingClient(), clock=clock)
    loop.show_idle()
    failed = loop.run_turn()
    error_shown = display.frames[-1].state is DisplayState.ERROR
    loop.show_idle()
    back_to_idle = display.frames[-1].state is DisplayState.IDLE

    clock.advance(config.session_idle_seconds + 1)
    rotated = loop.run_turn()
    session_rotated = rotated.session_id != failed.session_id

    print(f"backend failure code: {failed.error_code}")
    print(f"error frame shown: {'yes' if error_shown else 'no'}")
    print(f"returned to idle: {'yes' if back_to_idle else 'no'}")
    print(f"session rotated: {'yes' if session_rotated else 'no'} "
          f"(idle interval {config.session_idle_minutes:g} min)")
    print(f"turn ids differ: {'yes' if failed.turn_id != rotated.turn_id else 'no'}")
    print_frames(display)
    return 0 if (error_shown and back_to_idle and session_rotated) else 1


def build_parser() -> argparse.ArgumentParser:
    """Describe the two modes; exactly one must be chosen."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--fixture", type=Path,
        help="Spoken WAV the mock microphone replays for one real turn",
    )
    mode.add_argument(
        "--recovery", action="store_true",
        help="Run the offline failure-recovery and session checks instead",
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="Optional device TOML file",
    )
    return parser


def main() -> int:
    """Run the selected mode."""
    arguments = build_parser().parse_args()
    if arguments.recovery:
        return show_recovery(arguments)
    if not arguments.fixture.is_file():
        print(f"FAIL: fixture not found: {arguments.fixture}", file=sys.stderr)
        return 2
    return show_turn(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
