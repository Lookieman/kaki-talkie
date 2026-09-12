# v1.0 | 10-Sep-2026 | Cover chunk loading, BM25, fusion and store idempotency offline.
"""Deterministic offline tests for the WP3.2 retrieval layer.

Everything here runs without network or model downloads: embeddings come
from a deterministic fake `EmbeddingPort` (hashed bag-of-words vectors), and
the Chroma-backed tests use an in-memory ephemeral client, skipping loudly
when `chromadb` (the `kaki-rag[retrieve]` extra, installed in CI and on the
Mac) is absent so an ingestion-only environment stays green.
`sentence-transformers` is never imported.
"""

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from kaki_rag.ingest.metadata import PROVENANCE_FIELDS
from kaki_rag.retrieve.chunks import CorpusChunk, CorpusError, load_chunks
from kaki_rag.retrieve.hybrid import (
    HybridRetriever,
    PATH_DENSE_NORMALISED,
    PATH_DENSE_ORIGINAL,
    PATH_LEXICAL_NORMALISED,
    PATH_LEXICAL_ORIGINAL,
    RetrievalQuery,
)
from kaki_rag.retrieve.lexical import BM25Index, tokenize

try:
    import chromadb  # noqa: F401  (availability probe only)
    CHROMADB_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    CHROMADB_AVAILABLE = False

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_DIMENSIONS = 64


class FakeEmbedder:
    """A deterministic embedding port: normalised hashed bag-of-words vectors.

    Texts sharing words land near each other, which is enough to exercise
    ranking, fusion and store round-trips without a model.
    """

    model_id = "fake-hashed-bag-of-words"

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * FAKE_DIMENSIONS
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode()).digest()
            vector[digest[0] % FAKE_DIMENSIONS] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_queries(self, texts) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_passages(self, texts) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


def build_chunk(chunk_id: str, source_id: str, index: int, text: str,
                heading: str = "Heading") -> CorpusChunk:
    """Return one valid corpus chunk with full provenance for tests."""
    return CorpusChunk(
        chunk_id=chunk_id, source_id=source_id, chunk_index=index,
        heading_path=(heading,), text=text,
        provenance={
            "source_url": f"https://www.example.gov.sg/{source_id}",
            "page_title": f"About {source_id}", "scheme": source_id,
            "captured_at": "2026-09-10T08:00:00+00:00",
            "source_updated_at": None, "content_hash": "sha256:" + "0" * 64,
            "freshness_class": "stable", "valid_until": None,
        },
    )


CORPUS = [
    build_chunk("chunk-cdc-0", "cdc-vouchers", 0,
                "CDC Vouchers can be claimed by each Singaporean household using the "
                "SMS link and spent at participating hawkers and heartland merchants.",
                heading="Claiming CDC Vouchers"),
    build_chunk("chunk-chas-0", "chas", 0,
                "The Community Health Assist Scheme CHAS subsidises visits to "
                "participating clinics for eligible Singapore residents.",
                heading="About CHAS"),
    build_chunk("chunk-singpass-0", "singpass", 0,
                "Reset your Singpass password online through the Singpass portal "
                "using Face Verification or an SMS one-time password.",
                heading="Reset Singpass password"),
]


class ChunkLoadingTests(unittest.TestCase):
    """load_chunks validates the processed store loudly."""

    def write_store(self, lines: list[str]) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="kaki-rag-test."))
        path = directory / "chunks.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def valid_record(self) -> dict:
        chunk = CORPUS[0]
        return {
            "chunk_id": chunk.chunk_id, "source_id": chunk.source_id,
            "chunk_index": chunk.chunk_index, "heading_path": list(chunk.heading_path),
            "word_count": len(chunk.text.split()), "text": chunk.text,
            "provenance": dict(chunk.provenance),
        }

    def test_valid_store_loads_with_provenance(self):
        path = self.write_store([json.dumps(self.valid_record())])
        chunks = load_chunks(path)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(set(chunks[0].provenance), set(PROVENANCE_FIELDS))

    def test_missing_store_names_wp31(self):
        with self.assertRaises(CorpusError) as failure:
            load_chunks(Path(tempfile.mkdtemp()) / "chunks.jsonl")
        self.assertIn("WP3.1", str(failure.exception))

    def test_incomplete_provenance_is_rejected(self):
        record = self.valid_record()
        del record["provenance"]["valid_until"]
        with self.assertRaises(CorpusError):
            load_chunks(self.write_store([json.dumps(record)]))

    def test_duplicate_chunk_ids_are_rejected(self):
        line = json.dumps(self.valid_record())
        with self.assertRaises(CorpusError):
            load_chunks(self.write_store([line, line]))


class BM25Tests(unittest.TestCase):
    """The lexical path ranks exact terms and stays deterministic."""

    def setUp(self):
        self.index = BM25Index(CORPUS)

    def test_exact_chas_term_ranks_the_chas_chunk_first(self):
        results = self.index.query("CHAS", top_k=3)
        self.assertTrue(results)
        self.assertEqual(results[0][0], "chunk-chas-0")

    def test_headings_are_indexed(self):
        results = self.index.query("claiming", top_k=3)
        self.assertEqual(results[0][0], "chunk-cdc-0")

    def test_non_ascii_query_returns_empty_not_error(self):
        self.assertEqual(self.index.query("我要申请补贴", top_k=3), [])

    def test_scores_are_positive_and_ordered(self):
        results = self.index.query("Singpass password reset", top_k=3)
        scores = [score for _, score in results]
        self.assertTrue(all(score > 0 for score in scores))
        self.assertEqual(scores, sorted(scores, reverse=True))


@unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
class VectorStoreTests(unittest.TestCase):
    """Upserts are idempotent and stale identifiers are removed."""

    def setUp(self):
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
        self.store = ChromaVectorStore.ephemeral(collection_name="kaki_corpus_test")
        self.embedder = FakeEmbedder()

    def embeddings(self, chunks):
        return self.embedder.embed_passages([chunk.text for chunk in chunks])

    def test_reindex_is_idempotent(self):
        first = self.store.replace_corpus(CORPUS, self.embeddings(CORPUS))
        second = self.store.replace_corpus(CORPUS, self.embeddings(CORPUS))
        self.assertEqual(first, (3, 0))
        self.assertEqual(second, (3, 0))
        self.assertEqual(self.store.count(), 3)

    def test_stale_chunks_are_removed_after_recapture(self):
        self.store.replace_corpus(CORPUS, self.embeddings(CORPUS))
        recaptured = [
            build_chunk("chunk-cdc-1", "cdc-vouchers", 0, CORPUS[0].text,
                        heading="Claiming CDC Vouchers"),
            *CORPUS[1:],
        ]
        upserted, removed = self.store.replace_corpus(recaptured, self.embeddings(recaptured))
        self.assertEqual((upserted, removed), (3, 1))
        self.assertEqual(self.store.count(), 3)
        stored_ids = set()
        for chunk_id, _ in self.store.query(self.embeddings(recaptured)[0], top_k=3):
            stored_ids.add(chunk_id)
        self.assertIn("chunk-cdc-1", stored_ids)
        self.assertNotIn("chunk-cdc-0", stored_ids)

    def test_query_returns_similarity_best_first(self):
        self.store.replace_corpus(CORPUS, self.embeddings(CORPUS))
        query = self.embedder.embed_queries(["reset Singpass password portal"])[0]
        results = self.store.query(query, top_k=3)
        self.assertEqual(results[0][0], "chunk-singpass-0")
        similarities = [similarity for _, similarity in results]
        self.assertEqual(similarities, sorted(similarities, reverse=True))


@unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
class HybridRetrieverTests(unittest.TestCase):
    """Fusion merges all exercised paths and de-duplicates by chunk identity."""

    def setUp(self):
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
        self.embedder = FakeEmbedder()
        self.store = ChromaVectorStore.ephemeral(collection_name="kaki_corpus_test")
        self.store.replace_corpus(
            CORPUS, self.embedder.embed_passages([chunk.text for chunk in CORPUS])
        )
        self.retriever = HybridRetriever(CORPUS, self.embedder, self.store)

    def test_original_only_uses_two_paths(self):
        results = self.retriever.retrieve(RetrievalQuery(original="claim CDC Vouchers SMS"))
        self.assertEqual(results[0].chunk.source_id, "cdc-vouchers")
        paths = set().union(*(result.path_ranks for result in results))
        self.assertIn(PATH_DENSE_ORIGINAL, paths)
        self.assertIn(PATH_LEXICAL_ORIGINAL, paths)
        self.assertNotIn(PATH_DENSE_NORMALISED, paths)

    def test_normalised_query_exercises_all_four_paths(self):
        results = self.retriever.retrieve(
            RetrievalQuery(
                original="macam mana claim CDC voucher ah",
                normalised="how to claim CDC Vouchers SMS link household",
            )
        )
        self.assertEqual(results[0].chunk.source_id, "cdc-vouchers")
        top_paths = results[0].path_ranks
        self.assertIn(PATH_DENSE_NORMALISED, top_paths)
        self.assertIn(PATH_LEXICAL_NORMALISED, top_paths)
        self.assertIn(PATH_LEXICAL_ORIGINAL, top_paths)

    def test_results_deduplicate_and_carry_provenance(self):
        results = self.retriever.retrieve(
            RetrievalQuery(original="CHAS clinic subsidy", normalised="CHAS clinic subsidy")
        )
        chunk_ids = [result.chunk.chunk_id for result in results]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        for result in results:
            self.assertEqual(set(result.chunk.provenance), set(PROVENANCE_FIELDS))
            self.assertEqual(set(result.as_dict()["provenance"]), set(PROVENANCE_FIELDS))

    def test_blank_original_is_rejected(self):
        with self.assertRaises(ValueError):
            self.retriever.retrieve(RetrievalQuery(original="   "))

    def test_fusion_is_deterministic(self):
        query = RetrievalQuery(original="Singpass reset", normalised="reset Singpass password")
        first = [result.chunk.chunk_id for result in self.retriever.retrieve(query)]
        second = [result.chunk.chunk_id for result in self.retriever.retrieve(query)]
        self.assertEqual(first, second)


class MultilingualFixtureTests(unittest.TestCase):
    """The committed WP3-AT-10 fixture pairs are well-formed for wp_check."""

    def test_fixture_pairs_are_complete(self):
        lines = (FIXTURES / "multilingual_queries.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertGreaterEqual(len(lines), 3)
        allowlisted = {"singpass-support", "cdc-vouchers-residents", "chas-about",
                       "careshield-life"}
        for line in lines:
            pair = json.loads(line)
            self.assertTrue(pair["original"].strip())
            self.assertTrue(pair["normalised"].strip())
            self.assertIn(pair["expected_source_id"], allowlisted)


if __name__ == "__main__":
    unittest.main()
