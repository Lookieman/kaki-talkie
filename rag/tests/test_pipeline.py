# v1.0 | 10-Sep-2026 | Verify snapshots, provenance and idempotent re-ingestion offline.
"""Exercise the full ingestion pipeline against a mocked HTTP transport."""

import json
import tempfile
import unittest
from pathlib import Path

import httpx

from kaki_rag.ingest.fetch import (
    Allowlist,
    AllowlistedSource,
    FetchError,
    SourceFetcher,
)
from kaki_rag.ingest.metadata import PROVENANCE_FIELDS, REQUIRED_PROVENANCE_FIELDS
from kaki_rag.ingest.pipeline import run_ingestion

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DOMAIN = "www.example.gov.sg"


def build_allowlist() -> Allowlist:
    """Return a two-source allowlist matching the committed fixtures."""
    return Allowlist(
        allowed_domains=(DOMAIN,),
        sources=(
            AllowlistedSource(
                source_id="cdc-vouchers", url=f"https://{DOMAIN}/cdc",
                page_title="About CDC Vouchers", scheme="cdc-vouchers",
                freshness_class="stable",
            ),
            AllowlistedSource(
                source_id="singpass-support", url=f"https://{DOMAIN}/singpass",
                page_title="Singpass support", scheme="singpass",
                freshness_class="stable", valid_until="2027-01-01",
            ),
        ),
    )


def build_fetcher(pages: dict[str, object]) -> SourceFetcher:
    """Return a fetcher whose transport serves the given path -> body/status map."""
    def respond(request: httpx.Request) -> httpx.Response:
        page = pages.get(request.url.path)
        if page is None:
            return httpx.Response(404, text="missing")
        if isinstance(page, int):
            return httpx.Response(page, text="error")
        return httpx.Response(
            200, content=page,
            headers={"content-type": "text/html; charset=utf-8",
                     "last-modified": "Mon, 01 Sep 2026 08:00:00 GMT"},
        )

    return SourceFetcher(transport=httpx.MockTransport(respond))


def read_chunks(report) -> list[dict[str, object]]:
    """Load the processed chunk records the report points at."""
    lines = Path(report.processed_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


CDC_HTML = (FIXTURES / "cdc-vouchers.html").read_bytes()
SINGPASS_HTML = (FIXTURES / "singpass-support.html").read_bytes()
BOTH_PAGES = {"/cdc": CDC_HTML, "/singpass": SINGPASS_HTML}


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.data_root = Path(self._directory.name)

    def run_pipeline(self, pages: dict[str, object], today: str):
        return run_ingestion(
            "allowlist.yaml", self.data_root, allowlist=build_allowlist(),
            fetcher=build_fetcher(pages), today=today,
        )

    def test_first_run_writes_dated_snapshots_and_provenance(self) -> None:
        report = self.run_pipeline(BOTH_PAGES, today="2026-09-10")
        self.assertTrue(report.succeeded)
        self.assertEqual(
            [result.status for result in report.results], ["fetched", "fetched"]
        )
        for result in report.results:
            snapshot = Path(result.snapshot_path)
            self.assertTrue(snapshot.is_file())
            self.assertEqual(snapshot.parent.name, "2026-09-10")
            self.assertTrue(snapshot.with_suffix(".meta.json").is_file())
        chunks = read_chunks(report)
        self.assertEqual(len(chunks), report.total_chunks)
        self.assertGreater(report.total_chunks, 0)
        for record in chunks:
            provenance = record["provenance"]
            self.assertEqual(tuple(provenance), PROVENANCE_FIELDS)
            for field in REQUIRED_PROVENANCE_FIELDS:
                self.assertTrue(provenance[field])
            self.assertTrue(record["text"].strip())
        markdown = self.data_root / "corpus/processed/pages/cdc-vouchers.md"
        self.assertIn("# About CDC Vouchers", markdown.read_text(encoding="utf-8"))

    def test_unchanged_rerun_keeps_hashes_chunks_and_snapshots_stable(self) -> None:
        first = self.run_pipeline(BOTH_PAGES, today="2026-09-10")
        processed_before = Path(first.processed_path).read_bytes()
        second = self.run_pipeline(BOTH_PAGES, today="2026-09-11")
        self.assertTrue(second.succeeded)
        self.assertEqual(
            [result.status for result in second.results], ["unchanged", "unchanged"]
        )
        for before, after in zip(first.results, second.results):
            self.assertEqual(before.content_hash, after.content_hash)
            self.assertEqual(before.snapshot_path, after.snapshot_path)
            self.assertEqual(before.chunk_count, after.chunk_count)
        self.assertEqual(Path(second.processed_path).read_bytes(), processed_before)
        self.assertFalse((self.data_root / "corpus/snapshots/2026-09-11").exists())
        first_ids = [record["chunk_id"] for record in read_chunks(first)]
        second_ids = [record["chunk_id"] for record in read_chunks(second)]
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))

    def test_changed_content_creates_a_new_dated_snapshot_and_identity(self) -> None:
        first = self.run_pipeline(BOTH_PAGES, today="2026-09-10")
        changed = dict(BOTH_PAGES)
        changed["/cdc"] = CDC_HTML.replace(b"participating hawkers", b"updated merchants")
        second = self.run_pipeline(changed, today="2026-09-12")
        cdc_before = first.results[0]
        cdc_after = second.results[0]
        self.assertEqual(cdc_after.status, "fetched")
        self.assertNotEqual(cdc_before.content_hash, cdc_after.content_hash)
        self.assertEqual(Path(cdc_after.snapshot_path).parent.name, "2026-09-12")
        self.assertEqual(second.results[1].status, "unchanged")

    def test_failed_source_keeps_others_and_reuses_its_last_snapshot(self) -> None:
        first = self.run_pipeline(BOTH_PAGES, today="2026-09-10")
        broken = {"/cdc": 500, "/singpass": SINGPASS_HTML}
        second = self.run_pipeline(broken, today="2026-09-11")
        self.assertFalse(second.succeeded)
        cdc = second.results[0]
        self.assertEqual(cdc.status, "failed")
        self.assertEqual(cdc.error, "HTTP 500")
        self.assertEqual(cdc.snapshot_path, first.results[0].snapshot_path)
        self.assertEqual(cdc.chunk_count, first.results[0].chunk_count)
        self.assertEqual(second.results[1].status, "unchanged")
        self.assertEqual(second.total_chunks, first.total_chunks)

    def test_failed_source_without_history_yields_no_chunks(self) -> None:
        report = self.run_pipeline({"/cdc": 500, "/singpass": SINGPASS_HTML}, "2026-09-10")
        self.assertFalse(report.succeeded)
        cdc = report.results[0]
        self.assertEqual((cdc.status, cdc.chunk_count, cdc.snapshot_path),
                         ("failed", 0, None))
        self.assertGreater(report.total_chunks, 0)

    def test_content_without_usable_blocks_is_a_cleaning_failure(self) -> None:
        empty = {"/cdc": b"<html><body><script>x()</script></body></html>",
                 "/singpass": SINGPASS_HTML}
        report = self.run_pipeline(empty, today="2026-09-10")
        self.assertFalse(report.succeeded)
        self.assertEqual(report.results[0].error, "cleaning produced no content")


class FetcherBoundTests(unittest.TestCase):
    def test_rejects_non_html_content_type(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"%PDF-1.7",
                                  headers={"content-type": "application/pdf"})

        fetcher = SourceFetcher(transport=httpx.MockTransport(respond))
        with self.assertRaises(FetchError) as caught:
            fetcher.fetch(build_allowlist().sources[0], (DOMAIN,))
        self.assertIn("content type", caught.exception.reason)

    def test_reports_transport_errors_without_bodies(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("secret internal detail")

        fetcher = SourceFetcher(transport=httpx.MockTransport(respond))
        with self.assertRaises(FetchError) as caught:
            fetcher.fetch(build_allowlist().sources[0], (DOMAIN,))
        self.assertEqual(caught.exception.reason, "ConnectError")

    def test_rejects_unbounded_timeout(self) -> None:
        with self.assertRaises(ValueError):
            SourceFetcher(timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
