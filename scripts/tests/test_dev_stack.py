# v1.4 | 13-Sep-2026 | Occupied-port test binds an OS-assigned port, hermetic with the stack up.
# v1.3 | 13-Sep-2026 | Prove MLX-LM starts with PYTHONUNBUFFERED=1.
# v1.2 | 13-Sep-2026 | Prove storage readiness is required and children inherit the data root.
# v1.1 | 12-Sep-2026 | Give spawned helpers a canned environment instead of the shell's.
# v1.0 | 09-Sep-2026 | Verify stack helper safety rules without starting real services.
"""Deterministic dev-stack helper tests; no service processes are spawned."""

import dataclasses  #v1.4
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch  #v1.2
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

    def test_llm_service_runs_unbuffered(self) -> None:  #v1.3
        # The WP4.2 harness counts llm.log lines around one turn; a buffered
        # log would report "unchanged" for a turn that called the model.
        llm = dev_stack.build_services({})[1]
        self.assertEqual(dict(llm.extra_environment)["PYTHONUNBUFFERED"], "1")

    def test_llm_child_receives_pythonunbuffered(self) -> None:  #v1.3
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"KAKI_DATA_ROOT": directory}), \
                patch.object(dev_stack, "port_is_free", return_value=True), \
                patch.object(dev_stack.subprocess, "Popen") as popen:
            os.environ.pop("PYTHONUNBUFFERED", None)  # patch.dict restores it
            popen.return_value.pid = 4242
            llm = dev_stack.build_services(dict(os.environ))[1]
            self.assertTrue(dev_stack.start_service(llm, Path(directory), Path(directory)))
        self.assertEqual(popen.call_args.kwargs["env"]["PYTHONUNBUFFERED"], "1")

    def test_backend_requires_storage_readiness(self) -> None:  #v1.2
        backend = dev_stack.build_services({})[2]
        self.assertEqual(backend.required_health_flags, ("storage_ready", "retrieval_ready"))
        canned = dev_stack.build_services({"KAKI_RETRIEVAL_MODE": "canned"})[2]
        self.assertEqual(canned.required_health_flags, ("storage_ready",))

    def test_every_child_inherits_the_data_root(self) -> None:  #v1.2
        # `up --only backend` starts the same Service through the same path, so
        # the runbook 9.2 WP4.1 restart cannot lose KAKI_DATA_ROOT.
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"KAKI_DATA_ROOT": directory}), \
                patch.object(dev_stack, "port_is_free", return_value=True), \
                patch.object(dev_stack.subprocess, "Popen") as popen:
            popen.return_value.pid = 4242
            for service in dev_stack.build_services(dict(os.environ)):
                with self.subTest(service=service.name):
                    self.assertTrue(dev_stack.start_service(
                        service, Path(directory), Path(directory)
                    ))
                    child_environment = popen.call_args.kwargs["env"]
                    self.assertEqual(child_environment["KAKI_DATA_ROOT"], directory)

    def test_port_is_free_detects_a_bound_listener(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertFalse(dev_stack.port_is_free(port))
        self.assertTrue(dev_stack.port_is_free(port))

    def test_up_refuses_an_occupied_port_without_touching_it(self) -> None:  #v1.4
        # Bind an OS-assigned port, never a real service port: with the stack
        # running, 8081 is already held and binding it fails with EADDRINUSE,
        # so the result would depend on whether the stack is up.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            occupied_port = listener.getsockname()[1]
            service = dataclasses.replace(dev_stack.build_services({})[0], port=occupied_port)
            with tempfile.TemporaryDirectory() as directory, \
                    patch.object(dev_stack.subprocess, "Popen",
                                 side_effect=AssertionError("must not spawn")) as popen:
                started = dev_stack.start_service(
                    service, Path(directory), Path(directory)
                )
            self.assertFalse(started)
            popen.assert_not_called()

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
