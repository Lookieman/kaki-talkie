# v1.0 | 09-Sep-2026 | Verify latency CLI reporting, percentiles and safe failures.
"""Exercise the latency CLI deterministically; no real backend is contacted."""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_latency.py"

specification = importlib.util.spec_from_file_location("check_latency", SCRIPT)
check_latency = importlib.util.module_from_spec(specification)
specification.loader.exec_module(check_latency)


def run_with_transport(arguments: list[str], state: str) -> tuple[int, dict[str, object]]:
    """Run the measurement against a mocked backend returning the given turn state."""
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"state": state})

    args = check_latency.build_parser().parse_args(arguments)
    captured = io.StringIO()
    with redirect_stdout(captured):
        status = check_latency.run_measurement(args, transport=httpx.MockTransport(respond))
    return status, json.loads(captured.getvalue())


class PercentileTests(unittest.TestCase):
    def test_nearest_rank_percentiles(self) -> None:
        values = [float(value) for value in range(1, 11)]
        self.assertEqual(check_latency.percentile(values, 0.50), 5.0)
        self.assertEqual(check_latency.percentile(values, 0.95), 10.0)
        self.assertEqual(check_latency.percentile([7.0], 0.95), 7.0)

    def test_rejects_empty_values_and_bad_fractions(self) -> None:
        with self.assertRaises(ValueError):
            check_latency.percentile([], 0.5)
        with self.assertRaises(ValueError):
            check_latency.percentile([1.0], 0.0)


class LatencyCliTests(unittest.TestCase):
    def test_help_documents_runs_and_input(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"--runs", result.stdout)
        self.assertIn(b"--input", result.stdout)

    def test_answered_runs_report_p50_and_p95_without_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "turn.wav"
            audio.write_bytes(b"RIFF-test-bytes")
            status, report = run_with_transport(
                ["--runs", "3", "--input", str(audio)], state="answered"
            )
        self.assertEqual(status, 0)
        self.assertEqual(len(report["runs"]), 3)
        self.assertGreater(report["p50_ms"], 0)
        self.assertGreaterEqual(report["p95_ms"], report["p50_ms"])
        self.assertEqual(len({run["turn_id"] for run in report["runs"]}), 3)

    def test_non_answered_runs_fail_but_still_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "turn.wav"
            audio.write_bytes(b"RIFF-test-bytes")
            status, report = run_with_transport(
                ["--runs", "2", "--input", str(audio)], state="failed"
            )
        self.assertEqual(status, 1)
        self.assertIn("p95_ms", report)

    def test_invalid_runs_missing_and_empty_input_are_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.wav"
            empty.write_bytes(b"")
            for arguments in (
                ["--runs", "0", "--input", str(empty)],
                ["--runs", "101", "--input", str(empty)],
                ["--input", str(Path(directory) / "missing.wav")],
                ["--input", str(empty)],
            ):
                with self.subTest(arguments=arguments):
                    args = check_latency.build_parser().parse_args(arguments)
                    self.assertEqual(check_latency.run_measurement(args), 2)


if __name__ == "__main__":
    unittest.main()
