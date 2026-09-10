# v1.0 | 10-Sep-2026 | Seed snapshot store from browser-saved HTML for manual corpus capture.
"""Create a dated snapshot and metadata sidecar from a browser-saved HTML file.

Run from the kaki-talkie repository root after saving an allowlisted page in
Chrome. The script validates the source-id against the allowlist, computes
the content hash using the same function as the ingestion pipeline, copies
the HTML file into the snapshot directory, and writes the .meta.json sidecar.

Side effects:
  - creates KAKI_DATA_ROOT/corpus/snapshots/<date>/ if absent;
  - writes <source-id>.html and <source-id>.meta.json in that directory.

Does not commit, merge or push. Does not overwrite existing files unless
--force is given.

Examples:

    python scripts/seed_snapshot.py --source-id singpass-reset \\
        --html ~/Downloads/Rest_Singpass_howto.html

    python scripts/seed_snapshot.py --source-id singpass-reset \\
        --html ~/Downloads/Rest_Singpass_howto.html \\
        --data-root /Users/websvc/kaki-talkie-data \\
        --date 2026-09-10

    python scripts/seed_snapshot.py --list
"""  #v1.0

from __future__ import annotations  #v1.0

import argparse  #v1.0
import hashlib  #v1.0
import json  #v1.0
import os  #v1.0
import re  #v1.0
import shutil  #v1.0
import sys  #v1.0
from datetime import datetime, timezone  #v1.0
from pathlib import Path  #v1.0


SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")  #v1.0
DEFAULT_ALLOWLIST = "rag/corpus/allowlist.yaml"  #v1.0


def find_repo_root(start: Path) -> Path:  #v1.0
    """Walk up from start to find the directory that contains .git."""  #v1.0
    current = start.resolve()  #v1.0
    while current != current.parent:  #v1.0
        if (current / ".git").exists():  #v1.0
            return current  #v1.0
        current = current.parent  #v1.0
    raise RuntimeError(  #v1.0
        "Cannot find .git directory. Run this script from within the repository."  #v1.0
    )  #v1.0


def content_sha256(content: bytes) -> str:  #v1.0
    """Return the prefixed SHA-256 hash, matching metadata.content_sha256."""  #v1.0
    return "sha256:" + hashlib.sha256(content).hexdigest()  #v1.0


def extract_sources_from_allowlist(  #v1.0
    allowlist_path: Path,  #v1.0
) -> dict[str, dict[str, str]]:  #v1.0
    """Extract source_id -> {url, page_title} from the allowlist.

    Uses minimal line parsing rather than importing the kaki_rag YAML
    parser. This is intentionally simple: fetch.py does the full
    validation during ingestion.
    """  #v1.0
    if not allowlist_path.is_file():  #v1.0
        raise RuntimeError(f"Allowlist not found: {allowlist_path}")  #v1.0

    text = allowlist_path.read_text(encoding="utf-8")  #v1.0
    entries: dict[str, dict[str, str]] = {}  #v1.0
    current_entry: dict[str, str] = {}  #v1.0

    for line in text.splitlines():  #v1.0
        stripped = line.strip()  #v1.0
        if stripped.startswith("- source_id:"):  #v1.0
            if "source_id" in current_entry:  #v1.0
                entries[current_entry["source_id"]] = current_entry  #v1.0
            value = stripped.split(":", 1)[1].strip().strip("'\"")  #v1.0
            current_entry = {"source_id": value}  #v1.0
        elif ":" in stripped and current_entry:  #v1.0
            key, _, value = stripped.partition(":")  #v1.0
            key = key.strip().strip("- ")  #v1.0
            value = value.strip().strip("'\"")  #v1.0
            if key in ("url", "page_title", "scheme", "freshness_class"):  #v1.0
                current_entry[key] = value  #v1.0

    if "source_id" in current_entry:  #v1.0
        entries[current_entry["source_id"]] = current_entry  #v1.0

    return entries  #v1.0


def resolve_data_root(argument: str | None) -> Path:  #v1.0
    """Return the data root from --data-root, then KAKI_DATA_ROOT, or fail."""  #v1.0
    raw = argument or os.environ.get("KAKI_DATA_ROOT")  #v1.0
    if not raw:  #v1.0
        raise RuntimeError(  #v1.0
            "Set KAKI_DATA_ROOT or pass --data-root. "  #v1.0
            "Example: /Users/websvc/kaki-talkie-data"  #v1.0
        )  #v1.0
    root = Path(raw)  #v1.0
    if not root.is_absolute():  #v1.0
        raise RuntimeError(f"Data root must be an absolute path: {root}")  #v1.0
    return root  #v1.0


def list_sources(allowlist_path: Path) -> None:  #v1.0
    """Print the available source-ids from the allowlist."""  #v1.0
    entries = extract_sources_from_allowlist(allowlist_path)  #v1.0
    if not entries:  #v1.0
        print("No sources found in the allowlist.")  #v1.0
        return  #v1.0
    print(f"{'source-id':<30} {'url'}")  #v1.0
    print("-" * 78)  #v1.0
    for source_id, fields in entries.items():  #v1.0
        url = fields.get("url", "(missing)")  #v1.0
        print(f"{source_id:<30} {url}")  #v1.0


def seed_snapshot(  #v1.0
    source_id: str,  #v1.0
    html_path: Path,  #v1.0
    data_root: Path,  #v1.0
    capture_date: str,  #v1.0
    source_entry: dict[str, str],  #v1.0
    force: bool,  #v1.0
) -> None:  #v1.0
    """Copy the HTML file and write the .meta.json sidecar."""  #v1.0
    snapshot_dir = data_root / "corpus" / "snapshots" / capture_date  #v1.0
    target_html = snapshot_dir / f"{source_id}.html"  #v1.0
    target_meta = snapshot_dir / f"{source_id}.meta.json"  #v1.0

    if not force:  #v1.0
        existing = []  #v1.0
        if target_html.exists():  #v1.0
            existing.append(str(target_html))  #v1.0
        if target_meta.exists():  #v1.0
            existing.append(str(target_meta))  #v1.0
        if existing:  #v1.0
            raise RuntimeError(  #v1.0
                f"Files already exist (use --force to overwrite):\n"  #v1.0
                + "\n".join(f"  {path}" for path in existing)  #v1.0
            )  #v1.0

    content = html_path.read_bytes()  #v1.0
    if not content.strip():  #v1.0
        raise RuntimeError(f"HTML file is empty: {html_path}")  #v1.0

    hash_value = content_sha256(content)  #v1.0
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")  #v1.0

    meta = {  #v1.0
        "source_id": source_id,  #v1.0
        "final_url": source_entry.get("url", ""),  #v1.0
        "captured_at": captured_at,  #v1.0
        "http_status": 200,  #v1.0
        "content_type": "text/html",  #v1.0
        "content_hash": hash_value,  #v1.0
        "content_length": len(content),  #v1.0
        "source_updated_at": None,  #v1.0
        "capture_method": "browser-save",  #v1.0
    }  #v1.0

    snapshot_dir.mkdir(parents=True, exist_ok=True)  #v1.0
    shutil.copy2(html_path, target_html)  #v1.0
    target_meta.write_text(  #v1.0
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",  #v1.0
        encoding="utf-8",  #v1.0
    )  #v1.0

    print(f"Source:    {source_id}")  #v1.0
    print(f"Title:     {source_entry.get('page_title', '(unknown)')}")  #v1.0
    print(f"URL:       {source_entry.get('url', '(unknown)')}")  #v1.0
    print(f"Hash:      {hash_value}")  #v1.0
    print(f"Size:      {len(content):,} bytes")  #v1.0
    print(f"Snapshot:  {target_html}")  #v1.0
    print(f"Metadata:  {target_meta}")  #v1.0
    print(f"Date:      {capture_date}")  #v1.0


def parse_arguments() -> argparse.Namespace:  #v1.0
    """Parse and return command-line arguments."""  #v1.0
    parser = argparse.ArgumentParser(  #v1.0
        description=(  #v1.0
            "Seed the snapshot store from a browser-saved HTML file. "  #v1.0
            "Creates the dated snapshot directory, copies the HTML, "  #v1.0
            "computes the content hash, and writes the .meta.json sidecar."  #v1.0
        ),  #v1.0
        epilog=(  #v1.0
            "Run --list to see available source-ids from the allowlist. "  #v1.0
            "Does not commit, merge or push."  #v1.0
        ),  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--source-id",  #v1.0
        help="Source identifier from rag/corpus/allowlist.yaml.",  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--html",  #v1.0
        help="Path to the browser-saved HTML file.",  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--data-root",  #v1.0
        help=(  #v1.0
            "Absolute path to KAKI_DATA_ROOT. "  #v1.0
            "Falls back to the KAKI_DATA_ROOT environment variable."  #v1.0
        ),  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--date",  #v1.0
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),  #v1.0
        help="Capture date in YYYY-MM-DD format (default: today UTC).",  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--force",  #v1.0
        action="store_true",  #v1.0
        help="Overwrite existing snapshot files.",  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--list",  #v1.0
        action="store_true",  #v1.0
        help="List available source-ids from the allowlist and exit.",  #v1.0
    )  #v1.0
    parser.add_argument(  #v1.0
        "--allowlist",  #v1.0
        help=(  #v1.0
            f"Path to the allowlist file "  #v1.0
            f"(default: <repo-root>/{DEFAULT_ALLOWLIST})."  #v1.0
        ),  #v1.0
    )  #v1.0
    return parser.parse_args()  #v1.0


def main() -> int:  #v1.0
    """Validate inputs, then seed one snapshot. Return 0 on success, 1 on error."""  #v1.0
    args = parse_arguments()  #v1.0

    try:  #v1.0
        repo_root = find_repo_root(Path.cwd())  #v1.0
    except RuntimeError as error:  #v1.0
        print(f"Error: {error}", file=sys.stderr)  #v1.0
        return 1  #v1.0

    allowlist_path = (  #v1.0
        Path(args.allowlist) if args.allowlist  #v1.0
        else repo_root / DEFAULT_ALLOWLIST  #v1.0
    )  #v1.0

    if args.list:  #v1.0
        try:  #v1.0
            list_sources(allowlist_path)  #v1.0
        except RuntimeError as error:  #v1.0
            print(f"Error: {error}", file=sys.stderr)  #v1.0
            return 1  #v1.0
        return 0  #v1.0

    if not args.source_id or not args.html:  #v1.0
        print(  #v1.0
            "Error: --source-id and --html are required "  #v1.0
            "(or use --list to see available sources).",  #v1.0
            file=sys.stderr,  #v1.0
        )  #v1.0
        return 1  #v1.0

    html_path = Path(args.html).expanduser().resolve()  #v1.0
    if not html_path.is_file():  #v1.0
        print(f"Error: HTML file not found: {html_path}", file=sys.stderr)  #v1.0
        return 1  #v1.0

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):  #v1.0
        print(  #v1.0
            f"Error: --date must be YYYY-MM-DD, got: {args.date}",  #v1.0
            file=sys.stderr,  #v1.0
        )  #v1.0
        return 1  #v1.0

    try:  #v1.0
        entries = extract_sources_from_allowlist(allowlist_path)  #v1.0
    except RuntimeError as error:  #v1.0
        print(f"Error: {error}", file=sys.stderr)  #v1.0
        return 1  #v1.0

    source_id = args.source_id  #v1.0
    if source_id not in entries:  #v1.0
        print(  #v1.0
            f"Error: source-id '{source_id}' not found in allowlist.\n"  #v1.0
            f"Available: {', '.join(sorted(entries))}",  #v1.0
            file=sys.stderr,  #v1.0
        )  #v1.0
        return 1  #v1.0

    try:  #v1.0
        data_root = resolve_data_root(args.data_root)  #v1.0
        seed_snapshot(  #v1.0
            source_id=source_id,  #v1.0
            html_path=html_path,  #v1.0
            data_root=data_root,  #v1.0
            capture_date=args.date,  #v1.0
            source_entry=entries[source_id],  #v1.0
            force=args.force,  #v1.0
        )  #v1.0
    except RuntimeError as error:  #v1.0
        print(f"Error: {error}", file=sys.stderr)  #v1.0
        return 1  #v1.0

    return 0  #v1.0


if __name__ == "__main__":  #v1.0
    raise SystemExit(main())  #v1.0
