# v1.0 | 11-Sep-2026 | Adapt hybrid retrieval to the backend RetrieverPort for WP3.3.
"""The backend-facing retriever: `kaki_rag` retrieval behind the app's port.

`KakiRagRetriever` satisfies `kaki_backend.contracts.ports.RetrieverPort`,
mirroring how the `services/` adapters implement the STT/LLM/TTS ports. It
owns the embedding model in-process behind the port, so splitting it into a
separate service later is a configuration change, not an architecture one.
Encode calls run on a single-worker thread pool: model access is serialised
and heavy work stays off the caller's thread of control.

Construction is cheap; the first `ready()` (or first retrieval) loads the
processed chunks, opens the persistent Chroma collection and warms the
embedding model, so readiness is genuinely slow once and honest afterwards.
User-facing URLs and dates come only from the chunk provenance captured at
ingestion (design.md 7.3).
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from kaki_backend.contracts.ports import EvidenceChunk
from kaki_backend.contracts.responses import SourceRecord

from kaki_rag.retrieve.chunks import PROCESSED_RELATIVE_PATH, CorpusError, load_chunks
from kaki_rag.retrieve.embedding import (
    EmbeddingPort,
    QWEN3_EMBEDDING_MODEL,
    SentenceTransformerEmbedder,
)
from kaki_rag.retrieve.hybrid import DEFAULT_TOP_K, HybridRetriever, RetrievalQuery
from kaki_rag.retrieve.vector_store import COLLECTION_NAME, ChromaVectorStore

MAX_QUERY_CHARS = 2048


class _ExecutorEmbedder:
    """Serialise every encode call of the wrapped embedder onto one worker thread."""

    def __init__(self, inner: EmbeddingPort, executor: ThreadPoolExecutor) -> None:
        self._inner = inner
        self._executor = executor
        self.model_id = inner.model_id

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._executor.submit(self._inner.embed_queries, texts).result()

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._executor.submit(self._inner.embed_passages, texts).result()


def _source_record(provenance: dict[str, str | None]) -> SourceRecord:
    """Build the response-facing source record from stored chunk provenance."""
    updated = provenance.get("source_updated_at")
    return SourceRecord(
        source_url=str(provenance["source_url"]),
        page_title=str(provenance["page_title"]),
        captured_at=datetime.fromisoformat(str(provenance["captured_at"])),
        source_updated_at=date.fromisoformat(str(updated)[:10]) if updated else None,
        content_hash=provenance.get("content_hash"),
    )


def _best_path_score(path_scores: dict[str, float], prefix: str) -> float | None:
    """Return the best raw score among the paths with the given prefix, if any."""
    values = [score for path, score in path_scores.items() if path.startswith(prefix)]
    return max(values) if values else None


class KakiRagRetriever:
    """Hybrid corpus retrieval satisfying the backend's `RetrieverPort`."""

    def __init__(
        self,
        data_root: Path | str,
        *,
        model_id: str = QWEN3_EMBEDDING_MODEL,
        collection_name: str = COLLECTION_NAME,
        embedder: EmbeddingPort | None = None,
        vector_store: ChromaVectorStore | None = None,
    ) -> None:
        """Record configuration only; heavy loading happens on first use.

        `embedder` and `vector_store` are injectable for deterministic tests;
        production uses the sentence-transformers model and the persistent
        collection under `<data_root>/chroma`.
        """
        self._data_root = Path(data_root)
        self._model_id = model_id
        self._collection_name = collection_name
        self._injected_embedder = embedder
        self._injected_store = vector_store
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kaki-embed")
        self._retriever: HybridRetriever | None = None
        self._warmed = False

    def _load(self) -> HybridRetriever:
        """Build the hybrid retriever once; raise loudly when the corpus is unusable."""
        if self._retriever is None:
            chunks = load_chunks(self._data_root / PROCESSED_RELATIVE_PATH)
            store = self._injected_store or ChromaVectorStore.persistent(
                self._data_root, self._collection_name
            )
            if store.count() == 0:
                raise CorpusError(
                    "the vector collection is empty; run scripts/index_corpus.py first."
                )
            inner = self._injected_embedder or SentenceTransformerEmbedder(self._model_id)
            self._retriever = HybridRetriever(
                chunks, _ExecutorEmbedder(inner, self._executor), store
            )
        return self._retriever

    def ready(self) -> bool:
        """Load the corpus, collection and embedding model; true when all are usable.

        The first call is deliberately slow (it warms the model with one tiny
        encode) so that health reports readiness only when a real retrieval
        would succeed promptly. Never raises.
        """
        try:
            retriever = self._load()
            if not self._warmed:
                retriever.retrieve(RetrievalQuery(original="ready"), top_k=1)
                self._warmed = True
            return True
        except Exception:
            return False

    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[EvidenceChunk, ...]:
        """Return the top evidence chunks with provenance for one turn's query.

        Raises CorpusError when the corpus or collection is unusable and
        ValueError for a blank or oversized query; embedding failures
        propagate unchanged for the pipeline to handle.
        """
        if not original_query.strip() or len(original_query) > MAX_QUERY_CHARS:
            raise ValueError("The retrieval query must be non-empty and bounded.")
        if normalized_query is not None and len(normalized_query) > MAX_QUERY_CHARS:
            normalized_query = None
        results = self._load().retrieve(
            RetrievalQuery(original=original_query, normalised=normalized_query),
            top_k=DEFAULT_TOP_K,
        )
        self._warmed = True
        return tuple(
            EvidenceChunk(
                chunk_id=result.chunk.chunk_id,
                source_id=result.chunk.source_id,
                heading_path=result.chunk.heading_path,
                text=result.chunk.text,
                source=_source_record(result.chunk.provenance),
                fused_score=result.fused_score,
                dense_score=_best_path_score(result.path_scores, "dense_"),
                lexical_score=_best_path_score(result.path_scores, "lexical_"),
            )
            for result in results
        )
