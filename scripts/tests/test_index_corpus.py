# v1.1 | 12-Sep-2026 | Guard the CLI tests against ambient KAKI_* exports.
# v1.0 | 10-Sep-2026 | Verify the index-build CLI contract without model or network use.
"""Exercise the index_corpus CLI deterministically with fake embeddings."""

import hashlib
import importlib.util
import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from kaki_test_env import CannedEnvironment  #v1.1

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/index_corpus.py"

specification = importlib.util.spec_from_file_location("index_corpus", SCRIPT)
index_corpus = importlib.util.module_from_spec(specification)
specification.loader.exec_module(index_corpus)

try:
    import chromadb  # noqa: F401  (availability probe only)
    CHROMADB_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    CHROMADB_AVAILABLE = False


class FakeEmbedder:
    """Deterministic hashed bag-of-words embeddings; no model, no network."""

    def __init__(self, model_id="fake-model"):
        self.model_id = model_id

    def _embed_one(self, text):
        vector = [0.0] * 32
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            vector[digest[0] % 32] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_queries(self, texts):
        return [self._embed_one(text) for text in texts]

    def embed_passages(self, texts):
        return [self._embed_one(text) for text in texts]


def chunk_record(chunk_id: str, source_id: str, text: str) -> dict:
    """Return one valid processed chunk record."""
    return {
        "chunk_id": chunk_id, "source_id": source_id, "chunk_index": 0,
        "heading_path": ["Heading"], "word_count": len(text.split()), "text": text,
        "provenance": {
            "source_url": f"https://www.example.gov.sg/{source_id}",
            "page_title": f"About {source_id}", "scheme": source_id,
            "captured_at": "2026-09-10T08:00:00+00:00", "source_updated_at": None,
            "content_hash": "sha256:" + "0" * 64, "freshness_class": "stable",
            "valid_until": None,
        },
    }


def write_corpus(records: list[dict]) -> Path:
    """Write a processed store under a fresh data root and return the root."""
    data_root = Path(tempfile.mkdtemp(prefix="kaki-index-test."))
    processed = data_root / "corpus/processed"
    processed.mkdir(parents=True)
    lines = [json.dumps(record) for record in records]
    (processed / "chunks.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data_root


def run_main(arguments: list[str], store=None) -> tuple[int, str, str]:
    """Run the CLI main with fake embeddings and an injected store."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch.object(index_corpus, "SentenceTransformerEmbedder", FakeEmbedder),
        patch.object(
            index_corpus.ChromaVectorStore, "persistent",
            classmethod(lambda cls, root, name=None: store),
        ),
        patch.object(index_corpus.sys, "argv", ["index_corpus.py", *arguments]),
        redirect_stdout(stdout), redirect_stderr(stderr),
    ):
        status = index_corpus.main()
    return status, stdout.getvalue(), stderr.getvalue()


class IndexCorpusCliTests(CannedEnvironment, unittest.TestCase):  #v1.1
    """The CLI validates configuration and reports the build accurately."""

    def test_help_is_available(self):
        with (
            patch.object(index_corpus.sys, "argv", ["index_corpus.py", "--help"]),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(SystemExit) as leave:
                index_corpus.main()
        self.assertEqual(leave.exception.code, 0)
        self.assertIn("--data-root", stdout.getvalue())

    def test_missing_data_root_is_a_usage_error(self):
        with patch.dict(index_corpus.os.environ, {"KAKI_DATA_ROOT": ""}):
            status, _, stderr = run_main([])
        self.assertEqual(status, 2)
        self.assertIn("KAKI_DATA_ROOT", stderr)

    def test_relative_data_root_is_a_usage_error(self):
        status, _, stderr = run_main(["--data-root", "relative/path"])
        self.assertEqual(status, 2)
        self.assertIn("absolute", stderr)

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
    def test_build_then_rerun_is_idempotent(self):
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
        data_root = write_corpus([
            chunk_record("chunk-a", "cdc-vouchers", "CDC Vouchers help households."),
            chunk_record("chunk-b", "chas", "CHAS subsidises clinic visits."),
        ])
        store = ChromaVectorStore.ephemeral(collection_name="kaki_corpus_cli_test")
        first_status, first_out, _ = run_main(["--data-root", str(data_root)], store=store)
        second_status, second_out, _ = run_main(["--data-root", str(data_root)], store=store)
        self.assertEqual((first_status, second_status), (0, 0))
        first_report, second_report = json.loads(first_out), json.loads(second_out)
        self.assertTrue(first_report["succeeded"])
        self.assertEqual(first_report["chunks_read"], 2)
        self.assertEqual(second_report["collection_count"], 2)
        self.assertEqual(second_report["removed_stale"], 0)

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
    def test_missing_corpus_is_a_usage_error(self):
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
        data_root = Path(tempfile.mkdtemp(prefix="kaki-index-test."))
        store = ChromaVectorStore.ephemeral(collection_name="kaki_corpus_cli_test2")
        status, _, stderr = run_main(["--data-root", str(data_root)], store=store)
        self.assertEqual(status, 2)
        self.assertIn("WP3.1", stderr)


if __name__ == "__main__":
    unittest.main()
