# v1.0 | 16-Sep-2026 | WP6.1 device configuration: defaults, overrides and rejection.
"""Verify the device refuses to start on bad configuration, and its defaults.

The kiosk runs unattended, so a mistyped backend URL or an unbounded recording
cap must stop start-up rather than surface mid-demo.
"""

import tempfile
import unittest
from pathlib import Path

from kaki_device.config import (
    DEFAULT_PRINT_POLICY,
    DEFAULT_RECORD_SECONDS,
    DEFAULT_SESSION_IDLE_MINUTES,
    MAX_RECORD_SECONDS,
    ConfigError,
    load_config,
)


def write_config(body: str) -> Path:
    """Write a TOML file into a temporary directory and return its path."""
    directory = Path(tempfile.mkdtemp(prefix="kaki-device-config."))
    path = directory / "device.toml"
    path.write_text(body, encoding="utf-8")
    return path


class DefaultsTests(unittest.TestCase):
    def test_defaults_match_the_documented_contract(self):
        config = load_config(None, {})
        self.assertEqual(config.backend_url, "http://127.0.0.1:8000")
        self.assertEqual(config.record_seconds, DEFAULT_RECORD_SECONDS)
        self.assertEqual(config.record_seconds, MAX_RECORD_SECONDS)
        self.assertEqual(config.print_policy, DEFAULT_PRINT_POLICY)
        self.assertEqual(config.session_idle_minutes, DEFAULT_SESSION_IDLE_MINUTES)
        self.assertEqual(config.session_idle_seconds, 600.0)
        self.assertEqual((config.display_width, config.display_height), (1024, 600))
        self.assertIsNone(config.mock.audio_path)

    def test_missing_file_falls_back_to_defaults(self):
        config = load_config(Path("/nonexistent/device.toml"), {})
        self.assertEqual(config.device_id, "kaki-pi-01")


class FileAndOverrideTests(unittest.TestCase):
    def test_file_values_load_including_the_mock_table(self):
        path = write_config(
            'backend_url = "http://192.168.1.50:8000"\n'
            'device_id = "kaki-pi-demo"\n'
            "record_seconds = 10\n"
            "session_idle_minutes = 5\n"
            'print_policy = "on_request"\n'
            "[mock]\n"
            'audio_path = "/tmp/cdc.wav"\n'
            "button_presses = [0.0, 2.5]\n"
            "playback_realtime = true\n"
        )
        config = load_config(path, {})
        self.assertEqual(config.backend_url, "http://192.168.1.50:8000")
        self.assertEqual(config.device_id, "kaki-pi-demo")
        self.assertEqual(config.record_seconds, 10.0)
        self.assertEqual(config.print_policy, "on_request")
        self.assertEqual(config.mock.audio_path, Path("/tmp/cdc.wav"))
        self.assertEqual(config.mock.button_presses, (0.0, 2.5))
        self.assertTrue(config.mock.playback_realtime)

    def test_environment_overrides_the_file(self):
        path = write_config('device_id = "from-file"\nrecord_seconds = 12\n')
        config = load_config(path, {
            "KAKI_DEVICE_DEVICE_ID": "from-env",
            "KAKI_DEVICE_RECORD_SECONDS": "8",
            "KAKI_DEVICE_MOCK__AUDIO_PATH": "/tmp/from-env.wav",
        })
        self.assertEqual(config.device_id, "from-env")
        self.assertEqual(config.record_seconds, 8.0)
        self.assertEqual(config.mock.audio_path, Path("/tmp/from-env.wav"))

    def test_unrelated_environment_variables_are_ignored(self):
        config = load_config(None, {"KAKI_LLM_MODE": "qwen", "PATH": "/usr/bin"})
        self.assertEqual(config.device_id, "kaki-pi-01")


class RejectionTests(unittest.TestCase):
    def test_recording_cap_above_fifteen_seconds_is_rejected(self):
        # WP1-AT-09 and WP6-AT-02 fix the cap at 15 s; configuration cannot raise it.
        with self.assertRaises(ConfigError):
            load_config(None, {"KAKI_DEVICE_RECORD_SECONDS": "30"})

    def test_backend_url_must_be_a_plain_origin(self):
        for url in (
            "ftp://127.0.0.1:8000", "http://user:pw@127.0.0.1:8000",
            "http://127.0.0.1:8000/api/device", "http://127.0.0.1:8000?debug=1",
            "not a url", "",
        ):
            with self.subTest(url=url), self.assertRaises(ConfigError):
                load_config(None, {"KAKI_DEVICE_BACKEND_URL": url})

    def test_unknown_print_policy_blank_id_and_bad_numbers_are_rejected(self):
        cases = (
            {"KAKI_DEVICE_PRINT_POLICY": "always"},
            {"KAKI_DEVICE_DEVICE_ID": "   "},
            {"KAKI_DEVICE_SESSION_IDLE_MINUTES": "0"},
            {"KAKI_DEVICE_REQUEST_TIMEOUT_SECONDS": "soon"},
            {"KAKI_DEVICE_DISPLAY_WIDTH": "-1"},
        )
        for environment in cases:
            with self.subTest(environment=environment), self.assertRaises(ConfigError):
                load_config(None, environment)

    def test_malformed_toml_is_rejected(self):
        path = write_config("backend_url = \n")
        with self.assertRaises(ConfigError):
            load_config(path, {})


if __name__ == "__main__":
    unittest.main()
