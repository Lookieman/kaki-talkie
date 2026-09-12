# v1.2 | 12-Sep-2026 | Load HF_TOKEN from the project-root .env before embedding.
# v1.1 | 11-Sep-2026 | Show raw per-path scores alongside ranks with --show-paths.
# v1.0 | 10-Sep-2026 | Provide the owner CLI for WP3.2 hybrid retrieval smoke tests.
"""Query the corpus with hybrid retrieval and print the ranked evidence.

Run this on the Mac as `websvc` to inspect what retrieval returns for one
question (runbook 8.2 WP3.2). It loads the processed chunks, opens the
persistent Chroma collection and runs the hybrid retriever over the
original query and, when given, the normalised English form. Every result
prints its provenance taken from chunk metadata - the source URLs and dates
are application-derived, never generated. `--show-paths` includes each
result's per-path ranks (dense/lexical, original/normalised), the
observable evidence for WP3-AT-04 and WP3-AT-10.

Side effects: read-only apart from the embedding model cache on first use.
Exit status: 0 when evidence was found, 1 when retrieval returned nothing,
2 for usage or configuration errors.

Example:
    python scripts/query_corpus.py --query "How do I use my CDC vouchers?" --top-k 3
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv  #v1.2

from kaki_rag.retrieve.chunks import PROCESSED_RELATIVE_PATH, CorpusError, load_chunks
from kaki_rag.retrieve.embedding import QWEN3_EMBEDDING_MODEL, SentenceTransformerEmbedder
from kaki_rag.retrieve.hybrid import DEFAULT_TOP_K, HybridRetriever, RetrievalQuery
from kaki_rag.retrieve.vector_store import COLLECTION_NAME, ChromaVectorStore

# `HF_TOKEN` lives in the untracked project-root .env; a real export wins and
# a missing .env is a silent no-op.
load_dotenv()  #v1.2


def build_parser() -> argparse.ArgumentParser:
    """Describe the query arguments and their defaults."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--query", required=True, help="The original question text")
    parser.add_argument(
        "--normalised", default=None,
        help="Optional normalised English search query retrieved alongside the original",
    )
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"Number of evidence chunks to return (default {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--show-paths", action="store_true",
        help="Include each result's per-path ranks in the output",
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
    """Run one hybrid retrieval and print the ranked JSON evidence."""
    args = build_parser().parse_args()
    if args.top_k < 1:
        print("FAIL: --top-k must be at least 1.", file=sys.stderr)
        return 2
    try:
        data_root = resolve_data_root(args.data_root)
        chunks = load_chunks(data_root / PROCESSED_RELATIVE_PATH)
        store = ChromaVectorStore.persistent(data_root, args.collection)
        if store.count() == 0:
            raise ValueError(
                "the vector collection is empty; run scripts/index_corpus.py first."
            )
        retriever = HybridRetriever(chunks, SentenceTransformerEmbedder(args.model), store)
        results = retriever.retrieve(
            RetrievalQuery(original=args.query, normalised=args.normalised),
            top_k=args.top_k,
        )
    except (CorpusError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"FAIL: cannot use the data root: {error}", file=sys.stderr)
        return 2
    printable = []
    for result in results:
        record = result.as_dict()
        if not args.show_paths:
            del record["path_ranks"]  #v1.1
            del record["path_scores"]  #v1.1
        printable.append(record)
    print(json.dumps(
        {"query": args.query, "normalised": args.normalised, "results": printable},
        indent=2, ensure_ascii=False,
    ))
    if results:
        print(f"PASS: {len(results)} evidence chunk(s) returned.", file=sys.stderr)
        return 0
    print("FAIL: retrieval returned no evidence.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
