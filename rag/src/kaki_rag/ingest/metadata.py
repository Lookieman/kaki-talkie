# v1.0 | 10-Sep-2026 | Define per-chunk provenance, content hashing and stable chunk identity.
"""Provenance metadata and identity for ingested corpus content.

Every stored chunk must carry the eight provenance fields from design.md 7.3
(`setup.md` 13.2). Source URLs and dates presented to users are derived from
this application metadata, never from an LLM. Chunk identifiers are pure
functions of the source identity, snapshot content hash and chunk position,
so an unchanged re-ingestion reproduces identical identifiers (WP3-AT-02).
"""

import hashlib
from dataclasses import dataclass

PROVENANCE_FIELDS = (
    "source_url",
    "page_title",
    "scheme",
    "captured_at",
    "source_updated_at",
    "content_hash",
    "freshness_class",
    "valid_until",
)

REQUIRED_PROVENANCE_FIELDS = (
    "source_url",
    "page_title",
    "scheme",
    "captured_at",
    "content_hash",
    "freshness_class",
)

FRESHNESS_CLASSES = ("stable", "periodic", "volatile")


@dataclass(frozen=True)
class Provenance:
    """The eight provenance fields attached to every chunk of one source.

    `source_updated_at` and `valid_until` are None when the source offers no
    value; the other six fields must be non-empty.
    """

    source_url: str
    page_title: str
    scheme: str
    captured_at: str
    content_hash: str
    freshness_class: str
    source_updated_at: str | None = None
    valid_until: str | None = None

    def __post_init__(self) -> None:
        """Reject empty required fields and unknown freshness classes."""
        for name in REQUIRED_PROVENANCE_FIELDS:
            if not getattr(self, name):
                raise ValueError(f"Provenance field {name} must be non-empty.")
        if self.freshness_class not in FRESHNESS_CLASSES:
            raise ValueError(
                f"freshness_class must be one of {', '.join(FRESHNESS_CLASSES)}."
            )

    def as_dict(self) -> dict[str, str | None]:
        """Return the eight fields in the documented order, with explicit nulls."""
        return {name: getattr(self, name) for name in PROVENANCE_FIELDS}


def content_sha256(content: bytes) -> str:
    """Return the prefixed SHA-256 of raw snapshot content, e.g. `sha256:ab12...`."""
    return "sha256:" + hashlib.sha256(content).hexdigest()


def chunk_identifier(source_id: str, content_hash: str, index: int) -> str:
    """Return a stable chunk identifier for one chunk position of one snapshot.

    Identical source content always yields identical identifiers; changed
    content changes every identifier of that source, which is what a later
    vector-store upsert (WP3.2) needs to replace stale chunks cleanly.
    """
    seed = f"{source_id}|{content_hash}|{index}".encode()
    return hashlib.sha256(seed).hexdigest()[:24]
