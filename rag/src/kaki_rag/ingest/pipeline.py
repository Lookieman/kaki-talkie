# v1.1 | 10-Sep-2026 | Read manual sources from seeded markdown snapshots; route cleaning by type.
# v1.0 | 10-Sep-2026 | Run the corpus ingestion: fetch, snapshot, clean, chunk, provenance.
"""End-to-end corpus ingestion for the WP3 grounded-knowledge corpus.

`capture: manual` sources (the MVP corpus, design.md 7.2 v1.2) are never
fetched: each reads its newest owner-seeded snapshot and reports status
`manual`; a manual source with no usable snapshot fails the run with
`no seeded snapshot`. `capture: auto` sources fetch the official page and
keep or reuse a dated snapshot under `KAKI_DATA_ROOT/corpus/snapshots/`.
Snapshots whose content type is text/markdown are cleaned with the markdown
cleaner; others with the HTML cleaner. Every chunk carries full provenance,
and the processed store (`corpus/processed/chunks.jsonl` plus one inspection
markdown file per source) is rewritten atomically from the current snapshots
each run, so it can never hold duplicate chunks and an unchanged
re-ingestion reproduces it byte-for-byte (WP3-AT-01/02).

A failed fetch of one auto source never blocks the others: the source keeps
its most recent good snapshot when one exists and is reported as failed, and
the run's report marks the whole run unsuccessful.
"""  #v1.1

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kaki_rag.ingest.chunk import Chunk, chunk_blocks
from kaki_rag.ingest.clean import blocks_to_markdown, clean_html, clean_markdown  #v1.1
from kaki_rag.ingest.fetch import (
    MARKDOWN_CONTENT_TYPE,  #v1.1
    Allowlist,
    AllowlistedSource,
    FetchError,
    SnapshotRecord,
    SnapshotStore,
    SourceFetcher,
    load_allowlist,
)
from kaki_rag.ingest.metadata import Provenance, chunk_identifier, content_sha256

STATUS_FETCHED = "fetched"
STATUS_UNCHANGED = "unchanged"
STATUS_MANUAL = "manual"  #v1.1
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class SourceResult:
    """The outcome for one allowlisted source in one ingestion run."""

    source_id: str
    status: str
    content_hash: str | None
    snapshot_path: str | None
    chunk_count: int
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the printable per-source summary."""
        return {
            "source_id": self.source_id,
            "status": self.status,
            "content_hash": self.content_hash,
            "snapshot_path": self.snapshot_path,
            "chunk_count": self.chunk_count,
            "error": self.error,
        }


@dataclass(frozen=True)
class IngestionReport:
    """The printable outcome of one ingestion run."""

    run_at: str
    allowlist_path: str
    data_root: str
    results: tuple[SourceResult, ...]
    processed_path: str
    total_chunks: int
    duplicate_chunk_ids: int

    @property
    def succeeded(self) -> bool:
        """True only when every source ingested and no duplicate identity exists."""
        return self.duplicate_chunk_ids == 0 and all(
            result.status != STATUS_FAILED for result in self.results
        )

    def as_dict(self) -> dict[str, object]:
        """Return the printable run summary."""
        return {
            "run_at": self.run_at,
            "allowlist": self.allowlist_path,
            "data_root": self.data_root,
            "sources": [result.as_dict() for result in self.results],
            "processed_path": self.processed_path,
            "total_chunks": self.total_chunks,
            "duplicate_chunk_ids": self.duplicate_chunk_ids,
            "succeeded": self.succeeded,
        }


def _chunk_records(
    source: AllowlistedSource, record: SnapshotRecord, chunks: list[Chunk],
) -> list[dict[str, object]]:
    """Build the stored chunk records with full provenance for one source."""
    provenance = Provenance(
        source_url=source.url,
        page_title=source.page_title,
        scheme=source.scheme,
        captured_at=record.captured_at,
        content_hash=record.content_hash,
        freshness_class=source.freshness_class,
        source_updated_at=record.source_updated_at,
        valid_until=source.valid_until,
    )
    return [
        {
            "chunk_id": chunk_identifier(source.source_id, record.content_hash, chunk.index),
            "source_id": source.source_id,
            "chunk_index": chunk.index,
            "heading_path": list(chunk.heading_path),
            "word_count": chunk.word_count,
            "text": chunk.text,
            "provenance": provenance.as_dict(),
        }
        for chunk in chunks
    ]


def _write_atomically(path: Path, text: str) -> None:
    """Replace the file content in one step so readers never see a partial store."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary_name, path)
    except OSError:
        os.unlink(temporary_name)
        raise


def run_ingestion(
    allowlist_path: Path | str,
    data_root: Path | str,
    *,
    fetcher: SourceFetcher | None = None,
    allowlist: Allowlist | None = None,
    today: str | None = None,
) -> IngestionReport:
    """Ingest every allowlisted source and rewrite the processed store.

    Side effects: writes dated snapshots and the processed store under
    `<data_root>/corpus/`. Raises AllowlistError for an unusable allowlist
    and ValueError for a relative data root; per-source fetch and cleaning
    failures are reported in the result rather than raised. `fetcher`,
    `allowlist` and `today` are injectable for deterministic tests.
    """
    resolved_allowlist = load_allowlist(allowlist_path) if allowlist is None else allowlist
    root = Path(data_root)
    store = SnapshotStore(root)
    active_fetcher = fetcher if fetcher is not None else SourceFetcher()
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    capture_date = today if today is not None else run_at[:10]

    results: list[SourceResult] = []
    all_records: list[dict[str, object]] = []
    processed_directory = root / "corpus" / "processed"
    pages_directory = processed_directory / "pages"
    for source in resolved_allowlist.sources:
        record, status, error = _capture_source(
            source, store, active_fetcher, resolved_allowlist.allowed_domains, capture_date,
        )
        chunk_count = 0
        if record is not None:
            content_text = store.read_content(record).decode("utf-8", errors="replace")  #v1.1
            if record.content_type == MARKDOWN_CONTENT_TYPE:  #v1.1
                blocks = clean_markdown(content_text)  #v1.1
            else:  #v1.1
                blocks = clean_html(content_text)  #v1.1
            if not blocks:
                status, error, record = STATUS_FAILED, "cleaning produced no content", None
            else:
                chunks = chunk_blocks(blocks)
                source_records = _chunk_records(source, record, chunks)
                chunk_count = len(source_records)
                all_records.extend(source_records)
                _write_atomically(
                    pages_directory / f"{source.source_id}.md", blocks_to_markdown(blocks)
                )
        results.append(
            SourceResult(
                source_id=source.source_id,
                status=status,
                content_hash=record.content_hash if record else None,
                snapshot_path=str(record.snapshot_path) if record else None,
                chunk_count=chunk_count,
                error=error,
            )
        )

    processed_path = processed_directory / "chunks.jsonl"
    lines = [json.dumps(record, ensure_ascii=False) for record in all_records]
    _write_atomically(processed_path, "\n".join(lines) + ("\n" if lines else ""))
    chunk_ids = [str(record["chunk_id"]) for record in all_records]
    return IngestionReport(
        run_at=run_at,
        allowlist_path=str(allowlist_path),
        data_root=str(root),
        results=tuple(results),
        processed_path=str(processed_path),
        total_chunks=len(all_records),
        duplicate_chunk_ids=len(chunk_ids) - len(set(chunk_ids)),
    )


def _capture_source(
    source: AllowlistedSource,
    store: SnapshotStore,
    fetcher: SourceFetcher,
    allowed_domains: tuple[str, ...],
    capture_date: str,
) -> tuple[SnapshotRecord | None, str, str | None]:
    """Resolve one source to the snapshot to process, its status and any error.

    Manual sources are never fetched: their newest seeded snapshot is used
    (status `manual`), and a missing snapshot is a failure. Auto sources
    fetch and reconcile with their newest existing snapshot: unchanged
    content reuses the existing snapshot so `captured_at` keeps meaning the
    capture that holds the content, and a failed fetch falls back to the
    newest good snapshot. Returns None for the record only when nothing
    usable exists.
    """  #v1.1
    existing = store.latest(source.source_id)
    if source.capture == "manual":  #v1.1
        if existing is None:  #v1.1
            return None, STATUS_FAILED, "no seeded snapshot"  #v1.1
        return existing, STATUS_MANUAL, None  #v1.1
    try:
        result = fetcher.fetch(source, allowed_domains)
    except FetchError as failure:
        return existing, STATUS_FAILED, failure.reason
    fetched_hash = content_sha256(result.content)
    if existing is not None and existing.content_hash == fetched_hash:
        return existing, STATUS_UNCHANGED, None
    record = store.write(source.source_id, result, fetched_hash, capture_date)
    return record, STATUS_FETCHED, None
