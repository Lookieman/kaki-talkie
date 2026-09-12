# v1.1 | 12-Sep-2026 | Give spawned helpers a canned environment instead of the shell's.
# v1.0 | 09-Sep-2026 | Verify stack helper safety rules without starting real services.
"""Deterministic dev-stack helper tests; no service processes are spawned."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kaki_test_env import canned_environment  #v1.1

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dev_stack.py"

specification = importlib.util.spec_from_file_location("dev_stack", SCRIPT)
dev_stack = importlib.util.module_from_spec(specification)
specification.loader.exec_module(dev_stack)


class DevStackCliTests(unittest.TestCase):
    def test_help_documents_the_three_actions(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        for action in (b"up", b"down", b"status"):
            self.assertIn(action, result.stdout)

    def test_missing_data_root_is_a_usage_error(self) -> None:
        # The child must not inherit the shell's KAKI_* switches: with a real
        # data root exported this assertion would silently stop testing.
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "status"], capture_output=True,
            env={**os.environ, **canned_environment(),
                 "KAKI_DATA_ROOT": "relative/path"},  #v1.1
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"KAKI_DATA_ROOT", result.stderr)


class DevStackSafetyTests(unittest.TestCase):
    def test_services_follow_the_documented_start_order_and_ports(self) -> None:
        services = dev_stack.build_services({})
        self.assertEqual([service.name for service in services],
                         ["whisper", "llm", "backend"])
        self.assertEqual([service.port for service in services], [8081, 8082, 8000])
        llm = services[1]
        self.assertIn('{"enable_thinking":false}', llm.command)
        backend = services[2]
        overrides = dict(backend.extra_environment)
        self.assertEqual(overrides["KAKI_STT_MODE"], "whisper")
        self.assertEqual(overrides["KAKI_LLM_MODE"], "qwen")
        self.assertEqual(overrides["KAKI_TTS_MODE"], "say")

    def test_port_is_free_detects_a_bound_listener(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertFalse(dev_stack.port_is_free(port))
        self.assertTrue(dev_stack.port_is_free(port))

    def test_up_refuses_an_occupied_port_without_touching_it(self) -> None:
        service = dev_stack.build_services({})[0]
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", service.port))
            listener.listen(1)
            with tempfile.TemporaryDirectory() as directory:
                started = dev_stack.start_service(
                    service, Path(directory), Path(directory)
                )
            self.assertFalse(started)

    def test_unreadable_and_missing_pidfiles_are_handled_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.pid.json"
            self.assertIsNone(dev_stack.read_pidfile(missing))
            corrupt = Path(directory) / "corrupt.pid.json"
            corrupt.write_text("not json", encoding="utf-8")
            self.assertIsNone(dev_stack.read_pidfile(corrupt))
            wrong_shape = Path(directory) / "wrong.pid.json"
            wrong_shape.write_text(json.dumps({"pid": "text"}), encoding="utf-8")
            self.assertIsNone(dev_stack.read_pidfile(wrong_shape))

    def test_down_with_nothing_recorded_is_a_clean_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            services = dev_stack.build_services({})
            self.assertEqual(dev_stack.command_down(services, Path(directory)), 0)


if __name__ == "__main__":
    unittest.main()
