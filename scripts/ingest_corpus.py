# v1.0 | 10-Sep-2026 | Provide the owner CLI for WP3.1 corpus ingestion.
"""Ingest the allowlisted official corpus into the runtime data root.

Run this on the Mac as `websvc` whenever the corpus should be captured or
refreshed (runbook 8.1/8.2 WP3.1). For every source in the allowlist it
fetches the official page over HTTPS, keeps or reuses a dated snapshot under
`<data root>/corpus/snapshots/YYYY-MM-DD/`, cleans and chunks the content,
and atomically rewrites `<data root>/corpus/processed/` with fully
provenanced chunk records. Unchanged sources are reported as `unchanged` and
write nothing new.

Side effects: network requests to the allowlisted domains and writes under
the data root only; nothing in the repository is modified and nothing is
deleted. Exit status: 0 when every source ingested cleanly, 1 when any
source failed (the summary names it), 2 for usage or configuration errors.

Example:
    python scripts/ingest_corpus.py --allowlist rag/corpus/allowlist.yaml
"""

import argparse
import json
import os
import sys
from pathlib import Path

from kaki_rag.ingest.fetch import AllowlistError, SourceFetcher
from kaki_rag.ingest.pipeline import run_ingestion


def build_parser() -> argparse.ArgumentParser:
    """Describe the ingestion arguments and their defaults."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--allowlist", required=True, type=Path,
        help="Path to the source allowlist, normally rag/corpus/allowlist.yaml",
    )
    parser.add_argument(
        "--data-root", type=Path, default=None,
        help="Runtime data root; defaults to the KAKI_DATA_ROOT environment variable",
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=30.0,
        help="Per-request network timeout between 0.1 and 120 seconds (default 30)",
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
    """Run one ingestion and print the JSON summary."""
    args = build_parser().parse_args()
    try:
        data_root = resolve_data_root(args.data_root)
        fetcher = SourceFetcher(timeout_seconds=args.timeout_seconds)
        report = run_ingestion(args.allowlist, data_root, fetcher=fetcher)
    except (AllowlistError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"FAIL: cannot write under the data root: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    if report.succeeded:
        print("PASS: every allowlisted source ingested cleanly.", file=sys.stderr)
        return 0
    failed = ", ".join(
        result.source_id for result in report.results if result.status == "failed"
    )
    print(f"FAIL: sources not ingested cleanly: {failed or 'duplicate chunk identity'}.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
