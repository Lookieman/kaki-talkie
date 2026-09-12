# v1.0 | 10-Sep-2026 | Adapt the persistent Chroma collection behind a small store port.
"""Chroma vector storage for the corpus, always with caller-supplied vectors.

Chroma runs embedded (`PersistentClient`, setup.md 13) with its data under
`<data root>/chroma`; no Chroma server exists. Vectors are always computed
by the application's `EmbeddingPort` - Chroma's built-in English-only
default embedder is never used. Documents are keyed by the WP3.1 stable
chunk identifiers so re-indexing upserts in place, and identifiers absent
from the current processed store are deleted as stale (a re-captured source
changes every one of its chunk identifiers). `chromadb` imports lazily so
ingestion-only installations never load it.
"""

import json
from pathlib import Path

from kaki_rag.retrieve.chunks import CorpusChunk

COLLECTION_NAME = "kaki_corpus"
CHROMA_DIRECTORY = "chroma"


class ChromaVectorStore:
    """One Chroma collection holding the embedded corpus chunks."""

    def __init__(self, client, collection_name: str = COLLECTION_NAME) -> None:
        self._collection = client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        self.collection_name = collection_name

    @classmethod
    def persistent(
        cls, data_root: Path | str, collection_name: str = COLLECTION_NAME
    ) -> "ChromaVectorStore":
        """Open (or create) the persistent store under `<data_root>/chroma`."""
        import chromadb
        client = chromadb.PersistentClient(path=str(Path(data_root) / CHROMA_DIRECTORY))
        return cls(client, collection_name)

    @classmethod
    def ephemeral(cls, collection_name: str = COLLECTION_NAME) -> "ChromaVectorStore":
        """Open an in-memory store for deterministic tests."""
        import chromadb
        client = chromadb.EphemeralClient()
        return cls(client, collection_name)

    def replace_corpus(
        self, chunks: list[CorpusChunk], embeddings: list[list[float]]
    ) -> tuple[int, int]:
        """Upsert every chunk with its embedding and delete stale identifiers.

        Returns `(upserted, removed_stale)`. Raises ValueError when chunks
        and embeddings disagree in length. Idempotent: repeating the call
        with unchanged chunks changes nothing and removes nothing.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("One embedding is required per chunk.")
        current_ids = [chunk.chunk_id for chunk in chunks]
        existing_ids = set(self._collection.get(include=[])["ids"])
        stale = sorted(existing_ids - set(current_ids))
        if stale:
            self._collection.delete(ids=stale)
        if chunks:
            self._collection.upsert(
                ids=current_ids,
                embeddings=embeddings,
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "heading_path": " > ".join(chunk.heading_path),
                        "provenance_json": json.dumps(chunk.provenance, ensure_ascii=False),
                    }
                    for chunk in chunks
                ],
            )
        return len(current_ids), len(stale)

    def query(self, embedding: list[float], top_k: int) -> list[tuple[str, float]]:
        """Return up to `top_k` `(chunk_id, similarity)` pairs, best first.

        Similarity is `1 - cosine distance`, so higher is closer. An empty
        collection returns an empty list.
        """
        available = self.count()
        if available == 0 or top_k <= 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, available),
            include=["distances"],
        )
        return [
            (chunk_id, 1.0 - distance)
            for chunk_id, distance in zip(result["ids"][0], result["distances"][0])
        ]

    def count(self) -> int:
        """Return the number of stored chunks."""
        return self._collection.count()
