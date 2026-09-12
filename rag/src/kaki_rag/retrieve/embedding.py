# v1.0 | 10-Sep-2026 | Define the embedding port and the sentence-transformers adapter.
"""Multilingual embedding behind a small port (design.md 7.4).

The approved model is `Qwen/Qwen3-Embedding-0.6B` (1024-dimensional), with
`BAAI/bge-m3` as the owner-approved fallback. Both run through the
`sentence-transformers` runtime, which this module imports lazily so that
ingestion-only installations and the deterministic offline tests never load
it; offline tests substitute a fake `EmbeddingPort`.

Queries and passages are embedded asymmetrically where the model defines an
instruction prompt: Qwen3-Embedding ships a built-in `query` prompt that the
adapter applies to queries only, per its model card. Models without a
`query` prompt (such as BGE-M3) embed both sides plainly. All embeddings are
L2-normalised, so cosine similarity equals the dot product.
"""

from typing import Protocol, Sequence

QWEN3_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
FALLBACK_EMBEDDING_MODEL = "BAAI/bge-m3"
QUERY_PROMPT_NAME = "query"


class EmbeddingPort(Protocol):
    """Embed retrieval queries and corpus passages into aligned vector spaces."""

    model_id: str

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one normalised embedding per query text, in order."""
        ...

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one normalised embedding per passage text, in order."""
        ...


class SentenceTransformerEmbedder:
    """Lazy-loading sentence-transformers adapter for the approved models.

    The first embedding call loads the model (downloading it into the
    Hugging Face cache when absent, which needs the network once); later
    calls reuse the resident model. Raises the underlying import or load
    error unchanged so a missing runtime or cache is reported loudly.
    """

    def __init__(self, model_id: str = QWEN3_EMBEDDING_MODEL) -> None:
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_id)
        return self._model

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed queries, applying the model's `query` prompt when it has one."""
        model = self._load()
        kwargs = {}
        if QUERY_PROMPT_NAME in (model.prompts or {}):
            kwargs["prompt_name"] = QUERY_PROMPT_NAME
        return model.encode(list(texts), normalize_embeddings=True, **kwargs).tolist()

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed corpus passages without an instruction prompt."""
        return self._load().encode(list(texts), normalize_embeddings=True).tolist()
