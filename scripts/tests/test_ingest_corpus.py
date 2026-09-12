# v1.1 | 12-Sep-2026 | Guard the CLI tests against ambient KAKI_* exports.
# v1.0 | 10-Sep-2026 | Verify the ingestion CLI contract without any network access.
"""Exercise the ingest_corpus CLI deterministically; no real fetch is made."""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx

from kaki_test_env import CannedEnvironment  #v1.1

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ingest_corpus.py"

specification = importlib.util.spec_from_file_location("ingest_corpus", SCRIPT)
ingest_corpus = importlib.util.module_from_spec(specification)
specification.loader.exec_module(ingest_corpus)

ALLOWLIST_TEXT = """\
version: 1
allowed_domains:
  - www.example.gov.sg
sources:
  - source_id: example-page
    url: https://www.example.gov.sg/guidance
    page_title: Example guidance
    scheme: example
    freshness_class: stable
"""
PAGE_HTML = b"<html><body><h1>Guidance</h1><p>Useful example content.</p></body></html>"


def run_main(arguments: list[str], respond) -> tuple[int, str, str]:
    """Run the CLI main with a mocked HTTP transport and captured output."""
    real_fetcher = ingest_corpus.SourceFetcher

    def build_fetcher(*, timeout_seconds: float) -> object:
        return real_fetcher(
            timeout_seconds=timeout_seconds, transport=httpx.MockTransport(respond)
        )

    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", ["ingest_corpus.py", *arguments]):
        with patch.object(ingest_corpus, "SourceFetcher", build_fetcher):
            with redirect_stdout(out), redirect_stderr(err):
                status = ingest_corpus.main()
    return status, out.getvalue(), err.getvalue()


class IngestCorpusCliTests(CannedEnvironment, unittest.TestCase):  #v1.1
    def setUp(self) -> None:
        super().setUp()  # sanitise KAKI_* before building the fixtures  #v1.1
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.data_root = Path(self._directory.name)
        self.allowlist = self.data_root / "allowlist.yaml"
        self.allowlist.write_text(ALLOWLIST_TEXT, encoding="utf-8")

    def test_help_documents_arguments_and_side_effects(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"--allowlist", result.stdout)
        self.assertIn(b"--data-root", result.stdout)
        self.assertIn(b"Side effects", result.stdout)

    def test_successful_run_reports_pass_and_writes_snapshot(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=PAGE_HTML,
                                  headers={"content-type": "text/html"})

        status, out, err = run_main(
            ["--allowlist", str(self.allowlist), "--data-root", str(self.data_root)],
            respond,
        )
        self.assertEqual(status, 0)
        self.assertIn("PASS", err)
        summary = json.loads(out)
        self.assertTrue(summary["succeeded"])
        self.assertEqual(summary["sources"][0]["status"], "fetched")
        self.assertTrue((self.data_root / "corpus/snapshots").is_dir())

    def test_failed_source_returns_one(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="down")

        status, out, err = run_main(
            ["--allowlist", str(self.allowlist), "--data-root", str(self.data_root)],
            respond,
        )
        self.assertEqual(status, 1)
        self.assertIn("example-page", err)
        self.assertFalse(json.loads(out)["succeeded"])

    def test_missing_data_root_is_a_usage_error(self) -> None:
        with patch.dict(ingest_corpus.os.environ, {"KAKI_DATA_ROOT": ""}):
            status, _, err = run_main(["--allowlist", str(self.allowlist)],
                                      lambda request: httpx.Response(200))
        self.assertEqual(status, 2)
        self.assertIn("KAKI_DATA_ROOT", err)

    def test_invalid_timeout_is_a_usage_error(self) -> None:
        status, _, err = run_main(
            ["--allowlist", str(self.allowlist), "--data-root", str(self.data_root),
             "--timeout-seconds", "0"],
            lambda request: httpx.Response(200),
        )
        self.assertEqual(status, 2)
        self.assertIn("timeout", err.lower())

    def test_unreadable_allowlist_is_a_usage_error(self) -> None:
        status, _, err = run_main(
            ["--allowlist", str(self.data_root / "absent.yaml"),
             "--data-root", str(self.data_root)],
            lambda request: httpx.Response(200),
        )
        self.assertEqual(status, 2)
        self.assertIn("FAIL", err)


if __name__ == "__main__":
    unittest.main()
