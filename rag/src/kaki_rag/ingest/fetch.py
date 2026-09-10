# v1.1 | 10-Sep-2026 | Add capture: manual sources and markdown-aware snapshot records.
# v1.0 | 10-Sep-2026 | Load the source allowlist, fetch official pages and keep dated snapshots.
"""Allowlist loading, bounded fetching and dated snapshot storage.

Only sources declared in `rag/corpus/allowlist.yaml` may be fetched, and only
over HTTPS from the explicitly allowed official domains. The allowlist file
uses a deliberately strict YAML subset (top-level scalars, lists of scalars
and lists of flat mappings; two-space indents; no tabs, anchors, flow syntax
or multiline scalars) parsed here without a third-party dependency; anything
outside the subset is rejected loudly rather than guessed at.

Snapshots are the durable capture record: raw page bytes plus a metadata file
under `KAKI_DATA_ROOT/corpus/snapshots/YYYY-MM-DD/`, never hand-edited.
Provenance `captured_at` derives from the snapshot metadata, not from the
clock at processing time. Sources marked `capture: manual` are never fetched
here: their snapshots are owner-reviewed markdown seeded with
`scripts/seed_snapshot.py` (design.md 7.2), and the store reads `.md` and
`.html` snapshots alike.
"""  #v1.1

import ipaddress
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from kaki_rag.ingest.metadata import FRESHNESS_CLASSES

MAX_FETCH_BYTES = 8 * 1024 * 1024
ACCEPTED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
DATE_DIRECTORY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
USER_AGENT = "kaki-talkie-ingest/0.1 (allowlisted official-source snapshot)"

REQUIRED_SOURCE_KEYS = ("source_id", "url", "page_title", "scheme", "freshness_class")
OPTIONAL_SOURCE_KEYS = ("valid_until", "capture")  #v1.1
CAPTURE_MODES = ("auto", "manual")  #v1.1
MARKDOWN_CONTENT_TYPE = "text/markdown"  #v1.1
DEFAULT_SNAPSHOT_CONTENT_TYPE = "text/html"  #v1.1


class AllowlistError(ValueError):
    """The allowlist file is malformed or violates the source rules."""


class FetchError(RuntimeError):
    """One source could not be fetched; the reason never includes response bodies."""

    def __init__(self, source_id: str, reason: str) -> None:
        super().__init__(f"{source_id}: {reason}")
        self.source_id = source_id
        self.reason = reason


@dataclass(frozen=True)
class AllowlistedSource:
    """One approved official page with its retrieval-facing metadata.

    `capture` is `auto` (fetched over HTTPS) or `manual` (owner-seeded
    snapshots only; never fetched live).
    """  #v1.1

    source_id: str
    url: str
    page_title: str
    scheme: str
    freshness_class: str
    valid_until: str | None = None
    capture: str = "auto"  #v1.1


@dataclass(frozen=True)
class Allowlist:
    """The validated allowlist: approved domains and the sources drawn from them."""

    allowed_domains: tuple[str, ...]
    sources: tuple[AllowlistedSource, ...]


def _parse_strict_yaml(text: str, path: str) -> dict[str, object]:
    """Parse the restricted allowlist YAML subset into scalars, lists and flat maps.

    Raises AllowlistError on tabs, flow/anchor/multiline syntax, unexpected
    indentation or empty values, naming the offending line number.
    """
    result: dict[str, object] = {}
    current_list: list[object] | None = None
    current_item: dict[str, str] | None = None

    def fail(line_number: int, reason: str) -> None:
        raise AllowlistError(f"{path}:{line_number}: {reason}")

    def scalar(raw: str, line_number: int) -> str:
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1].strip()
        if not value:
            fail(line_number, "empty value")
        if value[0] in "{[&*|>":
            fail(line_number, "flow, anchor and multiline YAML syntax is not supported")
        return value

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if "\t" in raw_line:
            fail(line_number, "tabs are not allowed")
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 0:
            current_item = None
            key, separator, value = stripped.partition(":")
            if not separator or not key.strip():
                fail(line_number, "expected 'key:' or 'key: value'")
            key = key.strip()
            if key in result:
                fail(line_number, f"duplicate key {key}")
            if value.strip():
                result[key] = scalar(value, line_number)
                current_list = None
            else:
                current_list = []
                result[key] = current_list
        elif stripped.startswith("- "):
            if current_list is None:
                fail(line_number, "list item outside a list")
            item_text = stripped[2:]
            key, separator, value = item_text.partition(":")
            if separator and key.strip() and " " not in key.strip():
                current_item = {key.strip(): scalar(value, line_number)}
                current_list.append(current_item)
            else:
                current_item = None
                current_list.append(scalar(item_text, line_number))
        elif indent >= 4 and current_item is not None:
            key, separator, value = stripped.partition(":")
            if not separator or not key.strip():
                fail(line_number, "expected 'key: value' inside a list mapping")
            key = key.strip()
            if key in current_item:
                fail(line_number, f"duplicate key {key}")
            current_item[key] = scalar(value, line_number)
        else:
            fail(line_number, "unexpected indentation")
    return result


def _validate_source_url(url: str, allowed_domains: tuple[str, ...], source_id: str) -> None:
    """Require an HTTPS URL on an approved domain without credentials or fragments."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise AllowlistError(f"{source_id}: url must use https.")
    if parsed.username is not None or parsed.password is not None:
        raise AllowlistError(f"{source_id}: url must not embed credentials.")
    if parsed.fragment:
        raise AllowlistError(f"{source_id}: url must not carry a fragment.")
    hostname = (parsed.hostname or "").lower()
    if hostname not in allowed_domains:
        raise AllowlistError(
            f"{source_id}: host {hostname or '(none)'} is not in allowed_domains."
        )
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return
    raise AllowlistError(f"{source_id}: allowed domains must be names, not IP addresses.")


def load_allowlist(path: Path | str) -> Allowlist:
    """Read and validate the allowlist file, or raise AllowlistError.

    Enforces: version 1; a non-empty lowercase domain list; and per source a
    unique slug `source_id`, an HTTPS URL on an allowed domain, a page title,
    a scheme label and a known freshness class. The five-to-ten-page scope
    guidance lives in setup.md 13.3 and is deliberately not enforced here.
    """
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as error:
        raise AllowlistError(f"cannot read {file_path}: {error.strerror}") from None
    parsed = _parse_strict_yaml(text, str(file_path))

    if parsed.get("version") != "1":
        raise AllowlistError("allowlist version must be 1.")
    raw_domains = parsed.get("allowed_domains")
    if not isinstance(raw_domains, list) or not raw_domains:
        raise AllowlistError("allowed_domains must be a non-empty list.")
    domains: list[str] = []
    for entry in raw_domains:
        if not isinstance(entry, str) or entry.lower() != entry:
            raise AllowlistError(f"allowed domain {entry!r} must be a lowercase hostname.")
        domains.append(entry)

    raw_sources = parsed.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise AllowlistError("sources must be a non-empty list.")
    sources: list[AllowlistedSource] = []
    seen_ids: set[str] = set()
    for entry in raw_sources:
        if not isinstance(entry, dict):
            raise AllowlistError("each source must be a mapping of source fields.")
        unknown = set(entry) - set(REQUIRED_SOURCE_KEYS) - set(OPTIONAL_SOURCE_KEYS)
        if unknown:
            raise AllowlistError(f"unknown source keys: {', '.join(sorted(unknown))}.")
        missing = [key for key in REQUIRED_SOURCE_KEYS if not entry.get(key)]
        if missing:
            raise AllowlistError(f"source missing keys: {', '.join(missing)}.")
        source_id = entry["source_id"]
        if not SOURCE_ID_PATTERN.match(source_id):
            raise AllowlistError(f"source_id {source_id!r} must be a lowercase slug.")
        if source_id in seen_ids:
            raise AllowlistError(f"duplicate source_id {source_id}.")
        seen_ids.add(source_id)
        if entry["freshness_class"] not in FRESHNESS_CLASSES:
            raise AllowlistError(
                f"{source_id}: freshness_class must be one of "
                f"{', '.join(FRESHNESS_CLASSES)}."
            )
        capture = entry.get("capture", "auto")  #v1.1
        if capture not in CAPTURE_MODES:  #v1.1
            raise AllowlistError(  #v1.1
                f"{source_id}: capture must be one of {', '.join(CAPTURE_MODES)}."  #v1.1
            )  #v1.1
        _validate_source_url(entry["url"], tuple(domains), source_id)
        sources.append(
            AllowlistedSource(
                source_id=source_id,
                url=entry["url"],
                page_title=entry["page_title"],
                scheme=entry["scheme"],
                freshness_class=entry["freshness_class"],
                valid_until=entry.get("valid_until"),
                capture=capture,  #v1.1
            )
        )
    return Allowlist(allowed_domains=tuple(domains), sources=tuple(sources))


@dataclass(frozen=True)
class FetchResult:
    """One successful capture: raw bytes plus the metadata provenance needs."""

    content: bytes
    final_url: str
    fetched_at: str
    status_code: int
    content_type: str
    source_updated_at: str | None


def _normalise_last_modified(header_value: str | None) -> str | None:
    """Convert an HTTP Last-Modified header to ISO 8601 UTC, or None."""
    if not header_value:
        return None
    try:
        parsed = parsedate_to_datetime(header_value)
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


class SourceFetcher:
    """Fetch allowlisted pages over HTTPS with bounded time, size and redirects.

    Environment proxy settings are honoured because official sources are
    external; redirects are followed but the final URL must stay on an
    allowed domain. Response bodies are never logged.
    """

    def __init__(
        self, *, timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Validate the bounded timeout; transport injection supports offline tests."""
        if not math.isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 120:
            raise ValueError("Fetch timeout must be between 0.1 and 120 seconds.")
        self._timeout = timeout_seconds
        self._transport = transport

    def fetch(self, source: AllowlistedSource, allowed_domains: tuple[str, ...]) -> FetchResult:
        """Return the page capture for one source, or raise a sanitised FetchError."""
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            with httpx.Client(
                timeout=self._timeout, follow_redirects=True, max_redirects=5,
                headers={"User-Agent": USER_AGENT}, transport=self._transport,
            ) as client:
                response = client.get(source.url)
        except httpx.HTTPError as error:
            raise FetchError(source.source_id, type(error).__name__) from None
        if response.status_code != 200:
            raise FetchError(source.source_id, f"HTTP {response.status_code}")
        final_host = (urlsplit(str(response.url)).hostname or "").lower()
        if final_host not in allowed_domains:
            raise FetchError(source.source_id, f"redirected off-allowlist to {final_host}")
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in ACCEPTED_CONTENT_TYPES:
            raise FetchError(source.source_id, f"unsupported content type {content_type!r}")
        if len(response.content) > MAX_FETCH_BYTES:
            raise FetchError(source.source_id, "response exceeds the size bound")
        if not response.content.strip():
            raise FetchError(source.source_id, "empty response body")
        return FetchResult(
            content=response.content,
            final_url=str(response.url),
            fetched_at=fetched_at,
            status_code=response.status_code,
            content_type=content_type,
            source_updated_at=_normalise_last_modified(response.headers.get("last-modified")),
        )


@dataclass(frozen=True)
class SnapshotRecord:
    """One stored capture of one source, as later stages consume it.

    `content_type` comes from the metadata sidecar (default text/html) and
    routes cleaning: text/markdown snapshots use the markdown cleaner.
    """  #v1.1

    source_id: str
    snapshot_path: Path
    meta_path: Path
    captured_at: str
    content_hash: str
    source_updated_at: str | None
    content_type: str = DEFAULT_SNAPSHOT_CONTENT_TYPE  #v1.1


class SnapshotStore:
    """Read and write dated, never-hand-edited source snapshots under the data root."""

    def __init__(self, data_root: Path) -> None:
        """Anchor the store at `<data_root>/corpus/snapshots`; require an absolute root."""
        if not data_root.is_absolute():
            raise ValueError("KAKI_DATA_ROOT must be an absolute path.")
        self._snapshots_directory = data_root / "corpus" / "snapshots"

    def latest(self, source_id: str) -> SnapshotRecord | None:
        """Return the newest existing snapshot of one source, or None.

        Snapshots with unreadable metadata or a missing content file are
        skipped rather than trusted.
        """
        if not self._snapshots_directory.is_dir():
            return None
        dated = sorted(
            (
                entry for entry in self._snapshots_directory.iterdir()
                if entry.is_dir() and DATE_DIRECTORY_PATTERN.match(entry.name)
            ),
            key=lambda entry: entry.name,
            reverse=True,
        )
        for directory in dated:
            record = self._read_record(directory, source_id)
            if record is not None:
                return record
        return None

    def write(
        self, source_id: str, result: FetchResult, content_hash: str, capture_date: str,
    ) -> SnapshotRecord:
        """Store the capture bytes and metadata under the dated directory."""
        directory = self._snapshots_directory / capture_date
        directory.mkdir(parents=True, exist_ok=True)
        snapshot_path = directory / f"{source_id}.html"
        meta_path = directory / f"{source_id}.meta.json"
        snapshot_path.write_bytes(result.content)
        meta_path.write_text(
            json.dumps(
                {
                    "source_id": source_id,
                    "final_url": result.final_url,
                    "captured_at": result.fetched_at,
                    "http_status": result.status_code,
                    "content_type": result.content_type,
                    "content_hash": content_hash,
                    "content_length": len(result.content),
                    "source_updated_at": result.source_updated_at,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        return SnapshotRecord(
            source_id=source_id,
            snapshot_path=snapshot_path,
            meta_path=meta_path,
            captured_at=result.fetched_at,
            content_hash=content_hash,
            source_updated_at=result.source_updated_at,
            content_type=result.content_type,  #v1.1
        )

    def read_content(self, record: SnapshotRecord) -> bytes:
        """Return the raw stored bytes of one snapshot."""
        return record.snapshot_path.read_bytes()

    def _read_record(self, directory: Path, source_id: str) -> SnapshotRecord | None:
        """Build a record from one dated directory when its files are usable.

        A snapshot may be `<source_id>.md` (owner-seeded markdown) or
        `<source_id>.html`. When both exist, the extension the metadata
        `content_type` names wins; otherwise whichever file exists is used.
        """  #v1.1
        meta_path = directory / f"{source_id}.meta.json"
        if not meta_path.is_file():  #v1.1
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        content_type = meta.get("content_type")  #v1.1
        if not isinstance(content_type, str) or not content_type:  #v1.1
            content_type = DEFAULT_SNAPSHOT_CONTENT_TYPE  #v1.1
        preferred = ".md" if content_type == MARKDOWN_CONTENT_TYPE else ".html"  #v1.1
        other = ".html" if preferred == ".md" else ".md"  #v1.1
        snapshot_path = directory / f"{source_id}{preferred}"  #v1.1
        if not snapshot_path.is_file():  #v1.1
            snapshot_path = directory / f"{source_id}{other}"  #v1.1
        if not snapshot_path.is_file():  #v1.1
            return None
        captured_at = meta.get("captured_at")
        content_hash = meta.get("content_hash")
        if not isinstance(captured_at, str) or not isinstance(content_hash, str):
            return None
        source_updated_at = meta.get("source_updated_at")
        if source_updated_at is not None and not isinstance(source_updated_at, str):
            source_updated_at = None
        return SnapshotRecord(
            source_id=source_id,
            snapshot_path=snapshot_path,
            meta_path=meta_path,
            captured_at=captured_at,
            content_hash=content_hash,
            source_updated_at=source_updated_at,
            content_type=content_type,  #v1.1
        )
