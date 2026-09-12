# v1.1 | 12-Sep-2026 | Load HF_TOKEN from the project-root .env before embedding.
# v1.0 | 10-Sep-2026 | Provide the owner CLI for the WP3.2 vector index build.
"""Embed the processed corpus into the persistent Chroma collection.

Run this on the Mac as `websvc` after ingestion whenever the corpus has
changed (runbook 8.1/8.2 WP3.2). It reads
`<data root>/corpus/processed/chunks.jsonl`, embeds every chunk with the
approved multilingual model (`Qwen/Qwen3-Embedding-0.6B` by default) and
upserts into the `kaki_corpus` collection under `<data root>/chroma`, keyed
by the stable chunk identifiers; identifiers no longer in the corpus are
deleted as stale. Re-running over an unchanged corpus is idempotent.

Side effects: writes under `<data root>/chroma` only; the first run
downloads the embedding model into the Hugging Face cache (network needed
once). Exit status: 0 on a successful build, 1 when the collection does not
match the corpus afterwards, 2 for usage or configuration errors.

Example:
    python scripts/index_corpus.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv  #v1.1

from kaki_rag.retrieve.chunks import PROCESSED_RELATIVE_PATH, CorpusError
from kaki_rag.retrieve.embedding import QWEN3_EMBEDDING_MODEL, SentenceTransformerEmbedder
from kaki_rag.retrieve.index import build_index
from kaki_rag.retrieve.vector_store import COLLECTION_NAME, ChromaVectorStore

# `HF_TOKEN` lives in the untracked project-root .env; a real export wins and
# a missing .env is a silent no-op.
load_dotenv()  #v1.1


def build_parser() -> argparse.ArgumentParser:
    """Describe the index-build arguments and their defaults."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-root", type=Path, default=None,
        help="Runtime data root; defaults to the KAKI_DATA_ROOT environment variable",
    )
    parser.add_argument(
        "--model", default=QWEN3_EMBEDDING_MODEL,
        help=f"Embedding model identifier (default {QWEN3_EMBEDDING_MODEL})",
    )
    parser.add_argument(
        "--collection", default=COLLECTION_NAME,
        help=f"Chroma collection name (default {COLLECTION_NAME})",
    )
    return parser


def resolve_data_root(argument: Path | None) -> Path:
    """Return the absolute data root from the argument or environment, or fail."""
    root = argument if argument is not None else Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if str(root) == "" or not root.is_absolute():
        raise ValueError(
            "Provide --data-root or export an absolute KAKI_DATA_ROOT (runbook 8.1)."
        )
    return root


def main() -> int:
    """Run one index build and print the JSON summary."""
    args = build_parser().parse_args()
    try:
        data_root = resolve_data_root(args.data_root)
        embedder = SentenceTransformerEmbedder(args.model)
        store = ChromaVectorStore.persistent(data_root, args.collection)
        report = build_index(data_root / PROCESSED_RELATIVE_PATH, embedder, store)
    except (CorpusError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"FAIL: cannot use the data root: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    if report.succeeded:
        print("PASS: the collection holds the current corpus.", file=sys.stderr)
        return 0
    print(
        f"FAIL: collection count {report.collection_count} does not match "
        f"{report.chunks_read} corpus chunks.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
