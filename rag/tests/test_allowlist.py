# v1.1 | 10-Sep-2026 | Cover the capture field and the four-source manual allowlist.
# v1.0 | 10-Sep-2026 | Verify allowlist parsing, validation and rejection behaviour.
"""Exercise the strict allowlist loader against valid and hostile inputs."""

import tempfile
import unittest
from pathlib import Path

from kaki_rag.ingest.fetch import AllowlistError, load_allowlist

RAG_ROOT = Path(__file__).resolve().parents[1]

VALID_ALLOWLIST = """\
# comment line
version: 1
allowed_domains:
  - www.example.gov.sg
sources:
  - source_id: example-page
    url: https://www.example.gov.sg/guidance
    page_title: Example guidance
    scheme: example
    freshness_class: stable
"""


def load_text(text: str):
    """Write the text to a temporary file and load it as an allowlist."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "allowlist.yaml"
        path.write_text(text, encoding="utf-8")
        return load_allowlist(path)


class AllowlistParsingTests(unittest.TestCase):
    def test_valid_allowlist_parses(self) -> None:
        allowlist = load_text(VALID_ALLOWLIST)
        self.assertEqual(allowlist.allowed_domains, ("www.example.gov.sg",))
        self.assertEqual(len(allowlist.sources), 1)
        source = allowlist.sources[0]
        self.assertEqual(source.source_id, "example-page")
        self.assertEqual(source.freshness_class, "stable")
        self.assertIsNone(source.valid_until)

    def test_committed_repository_allowlist_is_valid(self) -> None:
        allowlist = load_allowlist(RAG_ROOT / "corpus/allowlist.yaml")
        self.assertGreaterEqual(len(allowlist.sources), 4)  #v1.1

    def test_committed_sources_are_all_manual(self) -> None:  #v1.1
        allowlist = load_allowlist(RAG_ROOT / "corpus/allowlist.yaml")  #v1.1
        self.assertTrue(all(  #v1.1
            source.capture == "manual" for source in allowlist.sources  #v1.1
        ))  #v1.1

    def test_capture_field_defaults_to_auto(self) -> None:  #v1.1
        allowlist = load_text(VALID_ALLOWLIST)  #v1.1
        self.assertEqual(allowlist.sources[0].capture, "auto")  #v1.1

    def test_capture_manual_is_accepted(self) -> None:  #v1.1
        allowlist = load_text(VALID_ALLOWLIST + "    capture: manual\n")  #v1.1
        self.assertEqual(allowlist.sources[0].capture, "manual")  #v1.1

    def test_rejects_unknown_capture_value(self) -> None:  #v1.1
        with self.assertRaises(AllowlistError):  #v1.1
            load_text(VALID_ALLOWLIST + "    capture: scheduled\n")  #v1.1

    def test_rejects_non_https_url(self) -> None:
        with self.assertRaises(AllowlistError):
            load_text(VALID_ALLOWLIST.replace("https://", "http://"))

    def test_rejects_host_outside_allowed_domains(self) -> None:
        hostile = VALID_ALLOWLIST.replace(
            "https://www.example.gov.sg/guidance", "https://evil.example.com/guidance"
        )
        with self.assertRaises(AllowlistError):
            load_text(hostile)

    def test_rejects_embedded_credentials(self) -> None:
        hostile = VALID_ALLOWLIST.replace(
            "https://www.example.gov.sg", "https://user:pass@www.example.gov.sg"
        )
        with self.assertRaises(AllowlistError):
            load_text(hostile)

    def test_rejects_duplicate_source_id(self) -> None:
        duplicated = VALID_ALLOWLIST + """\
  - source_id: example-page
    url: https://www.example.gov.sg/other
    page_title: Other page
    scheme: example
    freshness_class: stable
"""
        with self.assertRaises(AllowlistError):
            load_text(duplicated)

    def test_rejects_unknown_freshness_class(self) -> None:
        with self.assertRaises(AllowlistError):
            load_text(VALID_ALLOWLIST.replace("stable", "eternal"))

    def test_rejects_missing_required_key(self) -> None:
        with self.assertRaises(AllowlistError):
            load_text(VALID_ALLOWLIST.replace("    scheme: example\n", ""))

    def test_rejects_unknown_source_key(self) -> None:
        with self.assertRaises(AllowlistError):
            load_text(VALID_ALLOWLIST + "    surprise: value\n")

    def test_rejects_wrong_version(self) -> None:
        with self.assertRaises(AllowlistError):
            load_text(VALID_ALLOWLIST.replace("version: 1", "version: 2"))

    def test_rejects_tabs_and_flow_syntax(self) -> None:
        with self.assertRaises(AllowlistError):
            load_text("version: 1\nallowed_domains:\n\t- a.gov.sg\n")
        with self.assertRaises(AllowlistError):
            load_text("version: 1\nallowed_domains: [a.gov.sg]\n")

    def test_rejects_missing_file(self) -> None:
        with self.assertRaises(AllowlistError):
            load_allowlist(Path(tempfile.gettempdir()) / "kaki-absent-allowlist.yaml")


if __name__ == "__main__":
    unittest.main()
