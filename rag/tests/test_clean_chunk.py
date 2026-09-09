# v1.0 | 10-Sep-2026 | Verify HTML cleaning and heading-aware bounded chunking.
"""Exercise cleaning and chunking deterministically from committed fixtures."""

import unittest
from pathlib import Path

from kaki_rag.ingest.chunk import chunk_blocks
from kaki_rag.ingest.clean import CleanBlock, blocks_to_markdown, clean_html

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def paragraph(text: str) -> CleanBlock:
    return CleanBlock(kind="paragraph", text=text)


def heading(text: str, level: int) -> CleanBlock:
    return CleanBlock(kind="heading", text=text, level=level)


class CleanHtmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.blocks = clean_html(
            (FIXTURES / "cdc-vouchers.html").read_text(encoding="utf-8")
        )
        self.joined = " ".join(block.text for block in self.blocks)

    def test_main_region_content_is_kept_in_order(self) -> None:
        headings = [block.text for block in self.blocks if block.kind == "heading"]
        self.assertEqual(
            headings, ["About CDC Vouchers", "How to claim", "Where to spend"]
        )
        self.assertIn("participating hawkers", self.joined)
        self.assertIn("Log in with Singpass.", self.joined)

    def test_page_furniture_and_scripts_are_discarded(self) -> None:
        for stripped in ("tracking script", "Site header furniture", "Footer links",
                         "Promotional sidebar", ".banner"):
            self.assertNotIn(stripped, self.joined)

    def test_whitespace_is_normalised(self) -> None:
        self.assertIn(
            "Claim your household's vouchers digitally using your Singpass.",
            self.joined,
        )

    def test_page_without_main_region_falls_back_to_body(self) -> None:
        blocks = clean_html(
            (FIXTURES / "singpass-support.html").read_text(encoding="utf-8")
        )
        self.assertIn("Singpass support", [block.text for block in blocks])
        self.assertIn("reset your Singpass password", " ".join(b.text for b in blocks))

    def test_markdown_rendering_marks_heading_levels(self) -> None:
        markdown = blocks_to_markdown(self.blocks)
        self.assertIn("# About CDC Vouchers", markdown)
        self.assertIn("## How to claim", markdown)


class ChunkingTests(unittest.TestCase):
    def test_fixture_chunks_carry_heading_paths(self) -> None:
        blocks = clean_html(
            (FIXTURES / "cdc-vouchers.html").read_text(encoding="utf-8")
        )
        chunks = chunk_blocks(blocks)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(chunks[0].heading_path, ("About CDC Vouchers",))
        self.assertEqual([chunk.index for chunk in chunks], list(range(len(chunks))))

    def test_sections_split_on_headings_when_large_enough(self) -> None:
        blocks = [
            heading("First", 1), paragraph("alpha " * 100),
            heading("Second", 2), paragraph("beta " * 100),
        ]
        chunks = chunk_blocks(blocks)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].heading_path, ("First",))
        self.assertEqual(chunks[1].heading_path, ("First", "Second"))

    def test_small_sections_merge_forward(self) -> None:
        blocks = [
            heading("Tiny", 1), paragraph("short text"),
            heading("Next", 1), paragraph("gamma " * 100),
        ]
        chunks = chunk_blocks(blocks)
        self.assertEqual(len(chunks), 1)
        self.assertIn("short text", chunks[0].text)

    def test_chunks_respect_the_maximum_word_bound(self) -> None:
        blocks = [heading("Long", 1)] + [paragraph("word " * 120) for _ in range(6)]
        chunks = chunk_blocks(blocks)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(chunk.word_count, 380)
            self.assertEqual(chunk.word_count, len(chunk.text.split()))

    def test_single_oversized_paragraph_is_split(self) -> None:
        chunks = chunk_blocks([paragraph("token " * 1000)])
        self.assertGreater(len(chunks), 1)
        self.assertEqual(sum(chunk.word_count for chunk in chunks), 1000)

    def test_identical_input_chunks_identically(self) -> None:
        blocks = clean_html(
            (FIXTURES / "cdc-vouchers.html").read_text(encoding="utf-8")
        )
        self.assertEqual(chunk_blocks(blocks), chunk_blocks(blocks))

    def test_rejects_inconsistent_size_bounds(self) -> None:
        with self.assertRaises(ValueError):
            chunk_blocks([], target_words=100, maximum_words=50)


if __name__ == "__main__":
    unittest.main()
