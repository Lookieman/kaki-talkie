# v1.2 | 20-Sep-2026 | WP6.4: service token, retry schedule; timeout retuned for retries.
# v1.1 | 20-Sep-2026 | WP6.2: [audio] card and rates, [button] pin and debounce.
# v1.0 | 16-Sep-2026 | WP6.1 device configuration from a TOML file and KAKI_DEVICE_* overrides.
"""Read the device's own settings; the backend keeps its configuration separate.

The Pi is a thin client (design.md 3), so everything here describes local
behaviour: which backend to call, how long to record, how long to wait, when a
session rotates and how the display is sized. Nothing here selects a model,
a corpus or a prompt.

Settings come from a TOML file, then `KAKI_DEVICE_*` environment overrides, so
a demo-day change needs no file edit. Invalid values raise `ConfigError` at
startup rather than failing mid-turn: a kiosk that cannot reach its backend
should refuse to start and say so on the console, not fail silently in front
of a user.
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

# WP1 fixed the recording cap at 15 seconds (WP1-AT-09, WP6-AT-02); the device
# enforces the same bound so a held button cannot post an unbounded upload.
DEFAULT_RECORD_SECONDS = 15.0
MAX_RECORD_SECONDS = 15.0
# A turn covers speech recognition, retrieval, generation and speech. The
# bound comfortably exceeds the worst observed live turn (~12 s; runbook 10.2
# WP5.1 measured 2-8 s) so a retry fires only on a genuine stall, never on a
# merely slow LLM turn (WP6.4, owner amendment 20-Sep-2026).
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
# The WP6-AT-04 retry: total attempts per turn and the pause between them.
# Every attempt reuses the same turn_id, so the backend answers exactly once.
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0
# design.md 9.3: the backend always produces slip_text; the device decides
# whether to print it. `auto` is the demo baseline (execution-plan.md 9).
PRINT_POLICIES = ("auto", "on_request")
DEFAULT_PRINT_POLICY = "auto"
# A session groups turns so "repeat that" resolves (WP4.2). The Pi owns the
# boundary: an idle kiosk starts a fresh session so the next user never
# repeats a stranger's answer.
DEFAULT_SESSION_IDLE_MINUTES = 10.0
# The Waveshare 5DP-CAPLCD-H panel over HDMI (setup.md 30.4).
DEFAULT_DISPLAY_WIDTH = 1024
DEFAULT_DISPLAY_HEIGHT = 600
# design.md 4.3: the Jabra Speak 510 captures 16 kHz mono S16_LE only, and
# plays 16 kHz audio too fast, so every sound is converted to 48 kHz stereo
# before playback. Rates live here, not in code, because the next speaker may
# differ; the WAV header of each sound is still read, never assumed.
DEFAULT_CAPTURE_RATE = 16000
DEFAULT_PLAYBACK_RATE = 48000
# The dome button wiring (setup.md 29.1): GPIO 17 to ground, internal pull-up.
DEFAULT_BUTTON_PIN = 17
DEFAULT_DEBOUNCE_SECONDS = 0.05

ENVIRONMENT_PREFIX = "KAKI_DEVICE_"
# Configuration tables that may be overridden with a double underscore, for
# example KAKI_DEVICE_AUDIO__CARD or KAKI_DEVICE_MOCK__AUDIO_PATH.
NESTED_SECTIONS = ("mock", "audio", "button")


class ConfigError(ValueError):
    """Signal a device configuration this build refuses to start with."""


@dataclass(frozen=True)
class MockSettings:
    """Fixtures the mock I/O backend replays instead of real hardware."""

    audio_path: Path | None = None
    button_presses: tuple[float, ...] = ()
    playback_realtime: bool = False


@dataclass(frozen=True)
class AudioSettings:
    """The Jabra Speak's ALSA identity and rates (design.md 4.3).

    `card` is the stable ALSA device name (for example `plughw:CARD=USB`),
    never a card number: numbers change with boot order. It defaults to empty
    because mock mode needs no hardware; real mode refuses to start without it.
    """

    card: str = ""
    capture_rate: int = DEFAULT_CAPTURE_RATE
    playback_rate: int = DEFAULT_PLAYBACK_RATE


@dataclass(frozen=True)
class ButtonSettings:
    """The dome button's GPIO pin and debounce interval (WP6-AT-01)."""

    pin: int = DEFAULT_BUTTON_PIN
    debounce_seconds: float = DEFAULT_DEBOUNCE_SECONDS


@dataclass(frozen=True)
class DeviceConfig:
    """Everything the device loop needs, validated once at startup."""

    backend_url: str = "http://127.0.0.1:8000"
    device_id: str = "kaki-pi-01"
    # The WP6.4 service credential, sent as a bearer header on every backend
    # call. Lives in /etc/kaki/device.toml (mode 0640); empty means the
    # backend will refuse every request, which the error frame reports.
    token: str = ""
    record_seconds: float = DEFAULT_RECORD_SECONDS
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS
    session_idle_minutes: float = DEFAULT_SESSION_IDLE_MINUTES
    print_policy: str = DEFAULT_PRINT_POLICY
    display_width: int = DEFAULT_DISPLAY_WIDTH
    display_height: int = DEFAULT_DISPLAY_HEIGHT
    mock: MockSettings = field(default_factory=MockSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    button: ButtonSettings = field(default_factory=ButtonSettings)

    @property
    def session_idle_seconds(self) -> float:
        """Return the idle rotation interval in seconds."""
        return self.session_idle_minutes * 60.0


def _bounded_number(values: Mapping[str, Any], name: str, default: float,
                    lower: float, upper: float) -> float:
    """Return a finite number within bounds, or raise ConfigError naming it."""
    raw = values.get(name, default)
    try:
        number = float(raw)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} must be a number between {lower} and {upper}.") from None
    if not lower <= number <= upper:
        raise ConfigError(f"{name} must be between {lower} and {upper}, got {number}.")
    return number


def _positive_integer(values: Mapping[str, Any], name: str, default: int) -> int:
    """Return a positive integer setting, or raise ConfigError naming it."""
    raw = values.get(name, default)
    try:
        number = int(raw)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} must be a positive integer.") from None
    if number <= 0:
        raise ConfigError(f"{name} must be a positive integer, got {number}.")
    return number


def _validated_backend_url(raw: object) -> str:
    """Accept a plain http(s) origin only; reject paths, queries and credentials.

    The device talks to one origin and builds every path itself, so a
    configured path could only smuggle a request somewhere unintended.
    """
    url = str(raw).rstrip("/")
    parsed = urlsplit(url)
    valid = (
        parsed.scheme in {"http", "https"} and parsed.hostname
        and parsed.username is None and parsed.password is None
        and not parsed.path and not parsed.query and not parsed.fragment
    )
    if not valid:
        raise ConfigError(
            "backend_url must be a plain http(s) origin such as "
            f"http://127.0.0.1:8000, got {raw!r}."
        )
    return url


def _non_empty_text(values: Mapping[str, Any], name: str, default: str) -> str:
    """Return a trimmed non-empty setting, or raise ConfigError naming it."""
    text = str(values.get(name, default)).strip()
    if not text:
        raise ConfigError(f"{name} must not be blank.")
    return text


def _mock_settings(values: Mapping[str, Any]) -> MockSettings:
    """Build the mock fixture settings; an absent section means bare defaults."""
    section = values.get("mock", {})
    if not isinstance(section, Mapping):
        raise ConfigError("[mock] must be a table of mock fixture settings.")
    audio = section.get("audio_path")
    presses = section.get("button_presses", [])
    if not isinstance(presses, (list, tuple)):
        raise ConfigError("mock.button_presses must be a list of seconds.")
    try:
        schedule = tuple(float(value) for value in presses)
    except (TypeError, ValueError):
        raise ConfigError("mock.button_presses must be a list of seconds.") from None
    return MockSettings(
        audio_path=Path(str(audio)).expanduser() if audio else None,
        button_presses=schedule,
        playback_realtime=bool(section.get("playback_realtime", False)),
    )


def _environment_overrides(environment: Mapping[str, str]) -> dict[str, Any]:
    """Map `KAKI_DEVICE_*` exports onto configuration keys.

    Settings inside a table use a double underscore, for example
    `KAKI_DEVICE_MOCK__AUDIO_PATH` or `KAKI_DEVICE_AUDIO__CARD`.
    """
    overrides: dict[str, Any] = {}
    for name, value in environment.items():
        if not name.startswith(ENVIRONMENT_PREFIX):
            continue
        key = name[len(ENVIRONMENT_PREFIX):].lower()
        section, _, nested = key.partition("__")
        if nested and section in NESTED_SECTIONS:
            overrides.setdefault(section, {})[nested] = value
        else:
            overrides[key] = value
    return overrides


def _merge(file_values: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Overlay environment overrides on file values, one level deep for tables."""
    merged: dict[str, Any] = {**file_values}
    for key, value in overrides.items():
        if key in NESTED_SECTIONS:
            section = dict(merged.get(key, {}))
            section.update(value)
            merged[key] = section
        else:
            merged[key] = value
    return merged


def _section(values: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Return one configuration table, or raise ConfigError when it is not one."""
    section = values.get(name, {})
    if not isinstance(section, Mapping):
        raise ConfigError(f"[{name}] must be a table of {name} settings.")
    return section


def _audio_settings(values: Mapping[str, Any]) -> AudioSettings:
    """Build the ALSA audio settings; an absent section means bare defaults."""
    section = _section(values, "audio")
    return AudioSettings(
        card=str(section.get("card", "")).strip(),
        capture_rate=int(_bounded_number(
            section, "capture_rate", DEFAULT_CAPTURE_RATE, 8000, 192000
        )),
        playback_rate=int(_bounded_number(
            section, "playback_rate", DEFAULT_PLAYBACK_RATE, 8000, 192000
        )),
    )


def _button_settings(values: Mapping[str, Any]) -> ButtonSettings:
    """Build the dome-button settings; an absent section means bare defaults."""
    section = _section(values, "button")
    return ButtonSettings(
        pin=int(_bounded_number(section, "pin", DEFAULT_BUTTON_PIN, 0, 27)),
        debounce_seconds=_bounded_number(
            section, "debounce_seconds", DEFAULT_DEBOUNCE_SECONDS, 0.0, 1.0
        ),
    )


def load_config(
    path: Path | str | None = None, environment: Mapping[str, str] | None = None
) -> DeviceConfig:
    """Return the validated device configuration.

    Reads `path` when given and present, applies `KAKI_DEVICE_*` overrides,
    then validates every field. Raises ConfigError for an unreadable or
    malformed file and for any value outside its documented range.
    """
    environment = os.environ if environment is None else environment
    file_values: dict[str, Any] = {}
    if path is not None:
        config_path = Path(path).expanduser()
        if config_path.exists():
            try:
                file_values = tomllib.loads(config_path.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError) as error:
                raise ConfigError(f"cannot read {config_path}: {error}") from None
    values = _merge(file_values, _environment_overrides(environment))

    policy = _non_empty_text(values, "print_policy", DEFAULT_PRINT_POLICY)
    if policy not in PRINT_POLICIES:
        raise ConfigError(f"print_policy must be one of {PRINT_POLICIES}, got {policy!r}.")
    return DeviceConfig(
        backend_url=_validated_backend_url(values.get("backend_url", "http://127.0.0.1:8000")),
        device_id=_non_empty_text(values, "device_id", "kaki-pi-01"),
        token=str(values.get("token", "")).strip(),
        record_seconds=_bounded_number(
            values, "record_seconds", DEFAULT_RECORD_SECONDS, 1.0, MAX_RECORD_SECONDS
        ),
        request_timeout_seconds=_bounded_number(
            values, "request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS, 1.0, 600.0
        ),
        retry_attempts=int(_bounded_number(
            values, "retry_attempts", DEFAULT_RETRY_ATTEMPTS, 1, 5
        )),
        retry_backoff_seconds=_bounded_number(
            values, "retry_backoff_seconds", DEFAULT_RETRY_BACKOFF_SECONDS, 0.0, 30.0
        ),
        session_idle_minutes=_bounded_number(
            values, "session_idle_minutes", DEFAULT_SESSION_IDLE_MINUTES, 1.0, 240.0
        ),
        print_policy=policy,
        display_width=_positive_integer(values, "display_width", DEFAULT_DISPLAY_WIDTH),
        display_height=_positive_integer(values, "display_height", DEFAULT_DISPLAY_HEIGHT),
        mock=_mock_settings(values),
        audio=_audio_settings(values),
        button=_button_settings(values),
    )
