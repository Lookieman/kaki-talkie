# v1.1 | 12-Sep-2026 | Guard the CLI tests against ambient KAKI_* exports.
# v1.0 | 10-Sep-2026 | Verify the retrieval-smoke CLI contract without model or network use.
"""Exercise the query_corpus CLI deterministically with fake embeddings."""

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_index_corpus import CHROMADB_AVAILABLE, FakeEmbedder, chunk_record, write_corpus

from kaki_test_env import CannedEnvironment  #v1.1

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/query_corpus.py"

specification = importlib.util.spec_from_file_location("query_corpus", SCRIPT)
query_corpus = importlib.util.module_from_spec(specification)
specification.loader.exec_module(query_corpus)


def run_main(arguments: list[str], store=None) -> tuple[int, str, str]:
    """Run the CLI main with fake embeddings and an injected store."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch.object(query_corpus, "SentenceTransformerEmbedder", FakeEmbedder),
        patch.object(
            query_corpus.ChromaVectorStore, "persistent",
            classmethod(lambda cls, root, name=None: store),
        ),
        patch.object(query_corpus.sys, "argv", ["query_corpus.py", *arguments]),
        redirect_stdout(stdout), redirect_stderr(stderr),
    ):
        status = query_corpus.main()
    return status, stdout.getvalue(), stderr.getvalue()


def build_indexed_store():
    """Return `(data_root, store)` with two chunks written and embedded."""
    from kaki_rag.retrieve.chunks import load_chunks
    from kaki_rag.retrieve.vector_store import ChromaVectorStore
    data_root = write_corpus([
        chunk_record("chunk-a", "cdc-vouchers-residents",
                     "CDC Vouchers can be claimed through the SMS link by households."),
        chunk_record("chunk-b", "chas-about",
                     "CHAS subsidises visits to participating clinics."),
    ])
    store = ChromaVectorStore.ephemeral(collection_name="kaki_corpus_query_test")
    chunks = load_chunks(data_root / "corpus/processed/chunks.jsonl")
    store.replace_corpus(
        chunks, FakeEmbedder().embed_passages([chunk.text for chunk in chunks])
    )
    return data_root, store


class QueryCorpusCliTests(CannedEnvironment, unittest.TestCase):  #v1.1
    """The CLI validates configuration and prints provenanced evidence."""

    def test_help_is_available(self):
        with (
            patch.object(query_corpus.sys, "argv", ["query_corpus.py", "--help"]),
            redirect_stdout(io.StringIO()) as stdout,
        ):
            with self.assertRaises(SystemExit) as leave:
                query_corpus.main()
        self.assertEqual(leave.exception.code, 0)
        self.assertIn("--normalised", stdout.getvalue())

    def test_missing_data_root_is_a_usage_error(self):
        with patch.dict(query_corpus.os.environ, {"KAKI_DATA_ROOT": ""}):
            status, _, stderr = run_main(["--query", "CDC vouchers"])
        self.assertEqual(status, 2)
        self.assertIn("KAKI_DATA_ROOT", stderr)

    def test_top_k_below_one_is_a_usage_error(self):
        status, _, stderr = run_main(["--query", "CDC", "--top-k", "0"])
        self.assertEqual(status, 2)
        self.assertIn("--top-k", stderr)

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
    def test_query_prints_provenanced_results(self):
        data_root, store = build_indexed_store()
        status, stdout, _ = run_main(
            ["--data-root", str(data_root), "--query", "claim CDC Vouchers SMS"],
            store=store,
        )
        self.assertEqual(status, 0)
        output = json.loads(stdout)
        self.assertEqual(output["results"][0]["source_id"], "cdc-vouchers-residents")
        self.assertIn("source_url", output["results"][0]["provenance"])
        self.assertNotIn("path_ranks", output["results"][0])

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
    def test_show_paths_includes_per_path_ranks(self):
        data_root, store = build_indexed_store()
        status, stdout, _ = run_main(
            ["--data-root", str(data_root), "--query", "macam mana claim CDC ah",
             "--normalised", "claim CDC Vouchers SMS", "--show-paths"],
            store=store,
        )
        self.assertEqual(status, 0)
        top = json.loads(stdout)["results"][0]
        self.assertIn("path_ranks", top)
        self.assertTrue(
            any(path.endswith("normalised") for path in top["path_ranks"])
        )

    @unittest.skipUnless(CHROMADB_AVAILABLE, "chromadb (kaki-rag[retrieve]) is not installed")
    def test_empty_collection_is_a_usage_error(self):
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
        data_root = write_corpus([
            chunk_record("chunk-a", "chas-about", "CHAS subsidises clinic visits."),
        ])
        store = ChromaVectorStore.ephemeral(collection_name="kaki_corpus_query_test2")
        status, _, stderr = run_main(
            ["--data-root", str(data_root), "--query", "CHAS"], store=store,
        )
        self.assertEqual(status, 2)
        self.assertIn("index_corpus", stderr)


if __name__ == "__main__":
    unittest.main()
