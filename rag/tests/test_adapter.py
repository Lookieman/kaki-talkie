# v1.1 | 13-Sep-2026 | WP5.1: the gate input is the better of the original and normalised legs.
# v1.0 | 11-Sep-2026 | Verify the backend-facing retriever adapter offline with fakes.
"""Exercise KakiRagRetriever with injected fakes; no model, network or backend stack.

Skips loudly when `chromadb` (the retrieve extra) or `kaki-backend` (the
contracts the adapter maps into) is not installed, so an ingestion-only
environment stays green. CI installs both.
"""

import json
import tempfile
import unittest
from pathlib import Path

from test_retrieve import CORPUS, FakeEmbedder

try:
    import chromadb  # noqa: F401  (availability probe only)
    import kaki_backend  # noqa: F401  (availability probe only)
    DEPENDENCIES_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extras
    DEPENDENCIES_AVAILABLE = False


def write_data_root() -> Path:
    """Write the fixture corpus as a processed store under a fresh data root."""
    data_root = Path(tempfile.mkdtemp(prefix="kaki-adapter-test."))
    processed = data_root / "corpus/processed"
    processed.mkdir(parents=True)
    lines = []
    for chunk in CORPUS:
        lines.append(json.dumps({
            "chunk_id": chunk.chunk_id, "source_id": chunk.source_id,
            "chunk_index": chunk.chunk_index, "heading_path": list(chunk.heading_path),
            "word_count": len(chunk.text.split()), "text": chunk.text,
            "provenance": dict(chunk.provenance),
        }))
    (processed / "chunks.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data_root


@unittest.skipUnless(
    DEPENDENCIES_AVAILABLE, "chromadb and kaki-backend are required (CI installs both)"
)
class KakiRagRetrieverTests(unittest.TestCase):
    """The adapter satisfies the backend port with application provenance."""

    def build(self, *, indexed: bool = True):
        from uuid import uuid4

        from kaki_rag.adapter import KakiRagRetriever
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
        embedder = FakeEmbedder()
        # Chroma's ephemeral client is cached per process; a unique collection
        # name keeps each test's store genuinely empty when unindexed.
        store = ChromaVectorStore.ephemeral(
            collection_name=f"kaki_adapter_test_{uuid4().hex[:8]}"
        )
        if indexed:
            store.replace_corpus(
                CORPUS, embedder.embed_passages([chunk.text for chunk in CORPUS])
            )
        data_root = write_data_root()
        return KakiRagRetriever(data_root, embedder=embedder, vector_store=store)

    def test_ready_true_only_with_an_indexed_collection(self):
        self.assertTrue(self.build().ready())
        self.assertFalse(self.build(indexed=False).ready())

    def test_retrieve_returns_evidence_with_source_records_and_scores(self):
        evidence = self.build().retrieve("claim CDC Vouchers SMS", None)
        self.assertTrue(evidence)
        top = evidence[0]
        self.assertEqual(top.source_id, "cdc-vouchers")
        self.assertTrue(top.text)
        self.assertEqual(
            top.source.source_url, "https://www.example.gov.sg/cdc-vouchers"
        )
        self.assertEqual(top.source.captured_at.year, 2026)
        self.assertIsNotNone(top.dense_score)
        self.assertIsNotNone(top.lexical_score)

    def test_normalised_query_is_used_alongside_the_original(self):
        evidence = self.build().retrieve(
            "macam mana claim baucar", "claim CDC Vouchers SMS link"
        )
        self.assertEqual(evidence[0].source_id, "cdc-vouchers")

    def test_dense_score_is_the_better_of_the_original_and_normalised_legs(self):  #v1.1
        # WP5.1 Test 2: a Malay question that scores low on the original leg
        # and high on the normalised leg must reach the gate with the high score.
        from kaki_rag.retrieve.hybrid import RetrievalQuery
        retriever = self.build()
        original, normalised = "macam mana baucar", "claim CDC Vouchers SMS link"
        paths = retriever._load().retrieve(RetrievalQuery(original, normalised))
        evidence = retriever.retrieve(original, normalised)
        original_only = retriever.retrieve(original, None)
        by_chunk = {result.chunk.chunk_id: result.path_scores for result in paths}
        for chunk in evidence:
            dense = [score for path, score in by_chunk[chunk.chunk_id].items()
                     if path.startswith("dense_")]
            self.assertEqual(chunk.dense_score, max(dense))
        self.assertGreater(
            max(chunk.dense_score for chunk in evidence),
            max(chunk.dense_score or 0.0 for chunk in original_only),
        )
        top_paths = by_chunk[evidence[0].chunk_id]
        self.assertGreater(top_paths["dense_normalised"], top_paths.get("dense_original", 0.0))
        self.assertEqual(evidence[0].dense_score, top_paths["dense_normalised"])

    def test_blank_query_is_rejected(self):
        with self.assertRaises(ValueError):
            self.build().retrieve("   ", None)

    def test_ready_never_raises_for_a_missing_corpus(self):
        from kaki_rag.adapter import KakiRagRetriever
        retriever = KakiRagRetriever(
            Path(tempfile.mkdtemp(prefix="kaki-adapter-test.")),
            embedder=FakeEmbedder(),
        )
        self.assertFalse(retriever.ready())


if __name__ == "__main__":
    unittest.main()
