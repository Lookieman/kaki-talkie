# v1.1 | 12-Sep-2026 | Drop redaction expectations; redaction is no longer performed.
# v1.0 | 12-Sep-2026 | Verify the devset runner contract with fake ports and no services.
"""Exercise run_regression deterministically: no model, no network, no stack.

The runner's own decisions are what is tested here - devset validation, the
pass/fail rule, and the report shape. The pipeline behaviour it measures is
covered by `backend/tests/unit/test_refusal_pipeline.py`.
"""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from kaki_test_env import CannedEnvironment

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run_regression.py"

specification = importlib.util.spec_from_file_location("run_regression", SCRIPT)
run_regression = importlib.util.module_from_spec(specification)
specification.loader.exec_module(run_regression)

COMMITTED_DEVSET = ROOT / "agent/data/devset.jsonl"


def write_devset(records: list[dict]) -> Path:
    """Write a temporary devset and return its path."""
    directory = tempfile.mkdtemp()
    path = Path(directory) / "devset.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    return path


def run_main(argv: list[str]) -> tuple[int, str, str]:
    """Invoke the CLI with the given arguments and capture its output."""
    out, err = io.StringIO(), io.StringIO()
    with (
        patch.object(run_regression.sys, "argv", ["run_regression.py", *argv]),
        redirect_stdout(out), redirect_stderr(err),
    ):
        status = run_regression.main()
    return status, out.getvalue(), err.getvalue()


class FakePipeline:
    """Return a scripted execution per utterance, recording the order of calls."""

    def __init__(self, outcomes: dict[str, tuple[str, str, str | None]]) -> None:
        self._outcomes = outcomes
        self.transcripts: list[str] = []

    def execute(self, *, turn_id, audio, **kwargs):
        transcript = self.transcripts[-1]
        intent, state, reason = self._outcomes[transcript]
        sources = [object()] if state == "answered" else []
        response = type("Response", (), {
            "state": type("State", (), {"value": state})(),
            "sources": sources,
        })()
        log = type("Log", (), {
            "intent": intent, "refusal_reason": reason,
            "cited_source_id": "cdc-vouchers-residents" if state == "answered" else None,
            "best_dense_score": 0.8 if state == "answered" else 0.2,
            "evidence_min_dense": 0.5,
        })()
        return type("Execution", (), {"response": response, "log": log})()


class FakeStt:
    """Record each injected transcript so the fake pipeline can key on it."""

    def __init__(self, pipeline: FakePipeline) -> None:
        self._pipeline = pipeline

    def speak(self, transcript: str, language: str) -> None:
        self._pipeline.transcripts.append(transcript)


class DevsetValidationTests(CannedEnvironment, unittest.TestCase):
    """A malformed devset is a usage error, named precisely."""

    def test_help_is_available(self):
        with (
            patch.object(run_regression.sys, "argv", ["run_regression.py", "--help"]),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(SystemExit) as leave:
                run_regression.main()
        self.assertEqual(leave.exception.code, 0)
        self.assertIn("--devset", stdout.getvalue())

    def test_missing_file_is_a_usage_error(self):
        status, _, stderr = run_main(["--devset", "/nowhere/devset.jsonl"])
        self.assertEqual(status, 2)
        self.assertIn("cannot read the devset", stderr)

    def test_malformed_json_names_the_line(self):
        path = Path(tempfile.mkdtemp()) / "bad.jsonl"
        path.write_text(
            '{"id": "a", "utterance": "hello", "expected_intent": "answer"}\n'
            "not json\n",
            encoding="utf-8",
        )
        status, _, stderr = run_main(["--devset", str(path)])
        self.assertEqual(status, 2)
        self.assertIn("line 2", stderr)

    def test_missing_required_fields_are_named(self):
        path = write_devset([{"id": "a", "utterance": "hello"}])
        status, _, stderr = run_main(["--devset", str(path)])
        self.assertEqual(status, 2)
        self.assertIn("expected_intent", stderr)

    def test_empty_devset_is_a_usage_error(self):
        path = write_devset([])
        status, _, stderr = run_main(["--devset", str(path)])
        self.assertEqual(status, 2)
        self.assertIn("no devset items", stderr)

    def test_invalid_target_is_a_usage_error(self):
        status, _, stderr = run_main(["--intent-target", "1.5"])
        self.assertEqual(status, 2)
        self.assertIn("--intent-target", stderr)


class CommittedDevsetTests(unittest.TestCase):
    """The committed devset must satisfy the contract the runner enforces."""

    def test_committed_devset_loads_and_covers_five_golden_paths(self):
        items = run_regression.load_devset(COMMITTED_DEVSET)
        self.assertGreaterEqual(len(items), 14)
        golden = {item["golden_path"] for item in items if item.get("golden_path")}
        self.assertEqual(golden, {"GP1", "GP2", "GP3", "GP4", "GP5"})

    def test_every_item_declares_a_consistent_expectation(self):
        for item in run_regression.load_devset(COMMITTED_DEVSET):
            with self.subTest(item=item["id"]):
                if item["expected_intent"] == "refuse":
                    self.assertEqual(item["expected_state"], "refused")
                    self.assertIsNotNone(item["expected_refusal_reason"])
                    self.assertIsNone(item["expected_source_id"])
                else:
                    self.assertEqual(item["expected_state"], "answered")
                    self.assertIsNone(item["expected_refusal_reason"])

    def test_the_credential_item_expects_a_credential_action_refusal(self):
        items = {item["id"]: item for item in run_regression.load_devset(COMMITTED_DEVSET)}
        credential = items["credential-action"]
        self.assertEqual(credential["expected_intent"], "refuse")
        self.assertEqual(credential["expected_refusal_reason"], "credential_action")
        self.assertEqual(credential["golden_path"], "GP4")

    def test_no_item_carries_a_redaction_expectation(self):
        # Redaction was removed by owner decision; a stale field would be
        # silently ignored by the runner and mislead a later reader.
        for item in run_regression.load_devset(COMMITTED_DEVSET):
            self.assertNotIn("expected_redacted", item, msg=item["id"])


class ScoringTests(CannedEnvironment, unittest.TestCase):
    """Accuracy and golden-path rules decide the exit status."""

    def run_with(self, records, outcomes, argv=None):
        path = write_devset(records)
        pipeline = FakePipeline(outcomes)
        stt = FakeStt(pipeline)
        with (
            patch.object(run_regression, "InjectedStt", lambda: stt),
            patch.object(run_regression, "build_pipeline", lambda _: pipeline),
        ):
            return run_main(["--devset", str(path), *(argv or [])])

    def test_all_correct_passes_and_reports_accuracy(self):
        records = [
            {"id": "a", "utterance": "cdc", "expected_intent": "answer",
             "expected_state": "answered", "expected_source_id": "cdc-vouchers-residents",
             "expected_refusal_reason": None,
             "golden_path": "GP1"},
            {"id": "b", "utterance": "weather", "expected_intent": "refuse",
             "expected_state": "refused", "expected_source_id": None,
             "expected_refusal_reason": "no_coverage",
             "golden_path": "GP3"},
        ]
        outcomes = {
            "cdc": ("answer", "answered", None),
            "weather": ("refuse", "refused", "no_coverage"),
        }
        status, stdout, stderr = self.run_with(records, outcomes)
        report = json.loads(stdout)
        self.assertEqual(status, 0)
        self.assertEqual(report["intent_accuracy"], 1.0)
        self.assertEqual(report["golden_paths_passed"], 2)
        self.assertIn("PASS", stderr)

    def test_a_failing_golden_path_fails_even_at_full_accuracy(self):
        # Intent is right but the wrong source was cited, so GP1 is not proven.
        records = [
            {"id": "a", "utterance": "cdc", "expected_intent": "answer",
             "expected_state": "answered", "expected_source_id": "singpass-support",
             "expected_refusal_reason": None,
             "golden_path": "GP1"},
        ]
        outcomes = {"cdc": ("answer", "answered", None)}
        status, stdout, stderr = self.run_with(records, outcomes)
        report = json.loads(stdout)
        self.assertEqual(status, 1)
        self.assertEqual(report["intent_accuracy"], 1.0)
        self.assertIn("golden-path", stderr)

    def test_accuracy_below_the_target_fails(self):
        records = [
            {"id": f"item-{index}", "utterance": f"u{index}", "expected_intent": "answer",
             "expected_state": "answered", "expected_source_id": None,
             "expected_refusal_reason": None,
             "golden_path": None}
            for index in range(4)
        ]
        # Three of four route to refuse instead of answer: 25% accuracy.
        outcomes = {"u0": ("answer", "answered", None)}
        outcomes.update({
            f"u{index}": ("refuse", "refused", "no_coverage")
            for index in range(1, 4)
        })
        status, stdout, stderr = self.run_with(records, outcomes)
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(stdout)["intent_accuracy"], 0.25)
        self.assertIn("below the", stderr)

    def test_a_wrong_refusal_reason_fails_its_item(self):
        # Refusing for the wrong reason is still a failure: GP4 must be
        # proven by the credential rule, not by the evidence gate.
        records = [
            {"id": "creds", "utterance": "log in for me", "expected_intent": "refuse",
             "expected_state": "refused", "expected_source_id": None,
             "expected_refusal_reason": "credential_action",
             "golden_path": "GP4"},
        ]
        outcomes = {"log in for me": ("refuse", "refused", "no_coverage")}
        status, stdout, _ = self.run_with(records, outcomes)
        self.assertEqual(status, 1)
        result = json.loads(stdout)["results"][0]
        self.assertFalse(result["checks"]["refusal_reason"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
