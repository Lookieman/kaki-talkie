# v1.1 | 11-Sep-2026 | Carry raw per-path scores so WP3.4 can pick thresholds from real numbers.
# v1.0 | 10-Sep-2026 | Merge dense and lexical candidates for original + normalised queries.
"""The hybrid retriever: the `Retriever` interface and its MVP implementation.

Per design.md 7.4 the original transcript is never discarded: retrieval runs
the dense multilingual path and the lexical BM25 path for the original text
and, when supplied, for the normalised English query - up to four candidate
lists - and merges them with reciprocal rank fusion, de-duplicated by the
stable chunk identifier. Each returned chunk records the 1-based rank it
achieved on every path that found it, which is the observable evidence for
WP3-AT-04 (lexical) and WP3-AT-10 (original + normalised both exercised).

Normalised query text is supplied by the caller; generating it at runtime
belongs to WP3.3.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from kaki_rag.retrieve.chunks import CorpusChunk
from kaki_rag.retrieve.embedding import EmbeddingPort
from kaki_rag.retrieve.lexical import BM25Index
from kaki_rag.retrieve.vector_store import ChromaVectorStore

RRF_K = 60
CANDIDATE_DEPTH = 10
DEFAULT_TOP_K = 3

PATH_DENSE_ORIGINAL = "dense_original"
PATH_DENSE_NORMALISED = "dense_normalised"
PATH_LEXICAL_ORIGINAL = "lexical_original"
PATH_LEXICAL_NORMALISED = "lexical_normalised"
ALL_PATHS = (
    PATH_DENSE_ORIGINAL,
    PATH_DENSE_NORMALISED,
    PATH_LEXICAL_ORIGINAL,
    PATH_LEXICAL_NORMALISED,
)


@dataclass(frozen=True)
class RetrievalQuery:
    """One retrieval request: the original transcript plus an optional
    normalised English form. The original is mandatory and never discarded."""

    original: str
    normalised: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    """One evidence candidate: the chunk, its fused score, per-path ranks and
    the raw per-path scores (dense cosine similarity, lexical BM25)."""

    chunk: CorpusChunk
    fused_score: float
    path_ranks: dict[str, int]
    path_scores: dict[str, float]  #v1.1

    def as_dict(self) -> dict[str, object]:
        """Return the printable evidence record with application provenance."""
        return {
            "chunk_id": self.chunk.chunk_id,
            "source_id": self.chunk.source_id,
            "heading_path": list(self.chunk.heading_path),
            "fused_score": self.fused_score,
            "path_ranks": dict(self.path_ranks),
            "path_scores": dict(self.path_scores),  #v1.1
            "provenance": dict(self.chunk.provenance),
            "text": self.chunk.text,
        }


class Retriever(Protocol):
    """Return ranked evidence chunks for one query; the WP3.3 answerer's port."""

    def retrieve(self, query: RetrievalQuery, top_k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
        """Return up to `top_k` evidence chunks, best first."""
        ...


class HybridRetriever:
    """Dense + lexical retrieval with reciprocal rank fusion over the corpus."""

    def __init__(
        self,
        chunks: list[CorpusChunk],
        embedder: EmbeddingPort,
        vector_store: ChromaVectorStore,
        *,
        candidate_depth: int = CANDIDATE_DEPTH,
    ) -> None:
        self._chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        self._embedder = embedder
        self._vector_store = vector_store
        self._lexical = BM25Index(chunks)
        self._depth = candidate_depth

    def retrieve(self, query: RetrievalQuery, top_k: int = DEFAULT_TOP_K) -> list[RetrievedChunk]:
        """Retrieve, fuse and de-duplicate evidence for one query.

        Runs both paths for the original text and again for the normalised
        text when present, then merges the ranked lists with reciprocal rank
        fusion (`1 / (60 + rank)`). Raises ValueError for a blank original.
        Deterministic: score ties break on the chunk identifier.
        """
        if not query.original.strip():
            raise ValueError("The original query text must be non-empty.")
        forms = {"original": query.original}
        if query.normalised and query.normalised.strip():
            forms["normalised"] = query.normalised
        embeddings = self._embedder.embed_queries(list(forms.values()))

        ranked_lists: dict[str, list[tuple[str, float]]] = {}  #v1.1
        for (form, text), embedding in zip(forms.items(), embeddings):
            ranked_lists[f"dense_{form}"] = self._vector_store.query(embedding, self._depth)
            ranked_lists[f"lexical_{form}"] = self._lexical.query(text, self._depth)

        fused: dict[str, float] = defaultdict(float)
        path_ranks: dict[str, dict[str, int]] = defaultdict(dict)
        path_scores: dict[str, dict[str, float]] = defaultdict(dict)  #v1.1
        for path, scored_ids in ranked_lists.items():
            for rank, (chunk_id, score) in enumerate(scored_ids, start=1):
                if chunk_id not in self._chunks_by_id:
                    continue
                fused[chunk_id] += 1.0 / (RRF_K + rank)
                path_ranks[chunk_id][path] = rank
                path_scores[chunk_id][path] = round(score, 6)  #v1.1
        ordered = sorted(fused, key=lambda chunk_id: (-fused[chunk_id], chunk_id))
        return [
            RetrievedChunk(
                chunk=self._chunks_by_id[chunk_id],
                fused_score=round(fused[chunk_id], 6),
                path_ranks=dict(path_ranks[chunk_id]),
                path_scores=dict(path_scores[chunk_id]),  #v1.1
            )
            for chunk_id in ordered[:top_k]
        ]
