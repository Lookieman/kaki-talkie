# v1.0 | 10-Sep-2026 | Package the WP3.2 hybrid multilingual retrieval layer.
"""Hybrid multilingual retrieval over the processed corpus (design.md 7.4).

The retrieval layer turns the WP3.1 processed chunk store into evidence:
chunks are embedded with the approved multilingual model into a persistent
Chroma collection, a lexical BM25 index protects exact Singapore terms such
as `CHAS`, and a hybrid retriever merges dense and lexical candidates for
both the original transcript and the normalised English query. Application
code depends on the `Retriever` interface and `EmbeddingPort`, never on
Chroma or model APIs directly.
"""

from kaki_rag.retrieve.chunks import CorpusChunk, CorpusError, load_chunks
from kaki_rag.retrieve.embedding import (
    EmbeddingPort,
    FALLBACK_EMBEDDING_MODEL,
    QWEN3_EMBEDDING_MODEL,
    SentenceTransformerEmbedder,
)
from kaki_rag.retrieve.hybrid import (
    HybridRetriever,
    RetrievalQuery,
    RetrievedChunk,
    Retriever,
)
from kaki_rag.retrieve.index import IndexReport, build_index
from kaki_rag.retrieve.lexical import BM25Index
from kaki_rag.retrieve.vector_store import COLLECTION_NAME, ChromaVectorStore

__all__ = [
    "BM25Index",
    "COLLECTION_NAME",
    "ChromaVectorStore",
    "CorpusChunk",
    "CorpusError",
    "EmbeddingPort",
    "FALLBACK_EMBEDDING_MODEL",
    "HybridRetriever",
    "IndexReport",
    "QWEN3_EMBEDDING_MODEL",
    "RetrievalQuery",
    "RetrievedChunk",
    "Retriever",
    "SentenceTransformerEmbedder",
    "build_index",
    "load_chunks",
]
