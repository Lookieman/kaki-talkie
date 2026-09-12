# v1.0 | 10-Sep-2026 | Load and validate processed corpus chunks for retrieval.
"""Read the WP3.1 processed chunk store into typed retrieval records.

`corpus/processed/chunks.jsonl` is the single retrieval text source: clean
markdown-derived chunks with stable identifiers and full provenance
(runbook 8.2 WP3.1). Loading validates every record loudly rather than
letting a malformed store degrade retrieval quality silently. Provenance is
carried through unchanged so answer sources and dates stay
application-derived, never generated.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from kaki_rag.ingest.metadata import PROVENANCE_FIELDS, REQUIRED_PROVENANCE_FIELDS

REQUIRED_CHUNK_FIELDS = ("chunk_id", "source_id", "chunk_index", "heading_path", "text")
PROCESSED_RELATIVE_PATH = Path("corpus/processed/chunks.jsonl")


class CorpusError(ValueError):
    """The processed corpus store is missing or malformed."""


@dataclass(frozen=True)
class CorpusChunk:
    """One processed retrieval chunk with its stable identity and provenance."""

    chunk_id: str
    source_id: str
    chunk_index: int
    heading_path: tuple[str, ...]
    text: str
    provenance: dict[str, str | None]


def load_chunks(processed_path: Path | str) -> list[CorpusChunk]:
    """Load every chunk record from the processed store, validated.

    Raises CorpusError when the file is absent (WP3.1 ingestion has not run),
    when a line is not valid JSON, when a required field or provenance field
    is missing or empty, or when chunk identifiers are duplicated.
    """
    path = Path(processed_path)
    if not path.is_file():
        raise CorpusError(
            f"processed corpus not found at {path}; run WP3.1 ingestion first (runbook 8.2)."
        )
    chunks: list[CorpusChunk] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            raise CorpusError(f"{path}:{line_number}: not valid JSON.") from None
        for field in REQUIRED_CHUNK_FIELDS:
            if field not in record or record[field] in ("", None):
                raise CorpusError(f"{path}:{line_number}: missing chunk field {field}.")
        provenance = record.get("provenance")
        if not isinstance(provenance, dict) or set(provenance) != set(PROVENANCE_FIELDS):
            raise CorpusError(
                f"{path}:{line_number}: provenance must hold exactly the eight fields."
            )
        for field in REQUIRED_PROVENANCE_FIELDS:
            if not provenance[field]:
                raise CorpusError(
                    f"{path}:{line_number}: provenance field {field} must be non-empty."
                )
        chunk_id = str(record["chunk_id"])
        if chunk_id in seen_ids:
            raise CorpusError(f"{path}:{line_number}: duplicate chunk_id {chunk_id}.")
        seen_ids.add(chunk_id)
        chunks.append(
            CorpusChunk(
                chunk_id=chunk_id,
                source_id=str(record["source_id"]),
                chunk_index=int(record["chunk_index"]),
                heading_path=tuple(str(part) for part in record["heading_path"]),
                text=str(record["text"]),
                provenance=dict(provenance),
            )
        )
    if not chunks:
        raise CorpusError(f"{path} holds no chunks; run WP3.1 ingestion first (runbook 8.2).")
    return chunks
