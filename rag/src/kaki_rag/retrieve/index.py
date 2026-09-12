# v1.0 | 10-Sep-2026 | Build the persistent vector index from the processed corpus.
"""Embed the processed chunks and reconcile the Chroma collection.

One index build reads `corpus/processed/chunks.jsonl`, embeds every chunk
with the configured `EmbeddingPort` and upserts into the vector store keyed
by the stable chunk identifiers, deleting identifiers no longer present.
Re-running over an unchanged corpus is idempotent (WP3-AT-02 identity
carried into the store); after a source re-capture the changed identifiers
replace the stale ones cleanly.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kaki_rag.retrieve.chunks import load_chunks
from kaki_rag.retrieve.embedding import EmbeddingPort
from kaki_rag.retrieve.vector_store import ChromaVectorStore


@dataclass(frozen=True)
class IndexReport:
    """The printable outcome of one index build."""

    run_at: str
    processed_path: str
    model_id: str
    collection: str
    chunks_read: int
    upserted: int
    removed_stale: int
    collection_count: int
    source_chunk_counts: dict[str, int]

    @property
    def succeeded(self) -> bool:
        """True when the collection holds exactly the current corpus."""
        return self.collection_count == self.chunks_read > 0

    def as_dict(self) -> dict[str, object]:
        """Return the printable build summary."""
        return {
            "run_at": self.run_at,
            "processed_path": self.processed_path,
            "model_id": self.model_id,
            "collection": self.collection,
            "chunks_read": self.chunks_read,
            "upserted": self.upserted,
            "removed_stale": self.removed_stale,
            "collection_count": self.collection_count,
            "source_chunk_counts": dict(self.source_chunk_counts),
            "succeeded": self.succeeded,
        }


def build_index(
    processed_path: Path | str,
    embedder: EmbeddingPort,
    vector_store: ChromaVectorStore,
) -> IndexReport:
    """Run one index build and return its report.

    Side effects: writes to the vector store only. Raises CorpusError for a
    missing or malformed processed store; embedding and store failures
    propagate unchanged.
    """
    chunks = load_chunks(processed_path)
    embeddings = embedder.embed_passages([chunk.text for chunk in chunks])
    upserted, removed_stale = vector_store.replace_corpus(chunks, embeddings)
    source_counts: dict[str, int] = {}
    for chunk in chunks:
        source_counts[chunk.source_id] = source_counts.get(chunk.source_id, 0) + 1
    return IndexReport(
        run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        processed_path=str(processed_path),
        model_id=embedder.model_id,
        collection=vector_store.collection_name,
        chunks_read=len(chunks),
        upserted=upserted,
        removed_stale=removed_stale,
        collection_count=vector_store.count(),
        source_chunk_counts=source_counts,
    )
