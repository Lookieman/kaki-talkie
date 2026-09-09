# v1.0 | 10-Sep-2026 | Chunk cleaned blocks along headings within the 300-500-token guidance.
"""Split cleaned page blocks into retrieval chunks along heading boundaries.

Chunks follow headings and semantic boundaries rather than arbitrary
character counts (design.md 7.2), targeting roughly 300-500 tokens. Sizes
are measured in words with tokens approximated at about 1.3 tokens per word,
so the defaults of 280 target words and 380 maximum words sit inside that
guidance; the exact numbers are tuning knobs for later real retrieval tests,
not acceptance thresholds.

Chunking is deterministic: identical input blocks always produce identical
chunks, which the stable chunk identity in `metadata` relies on.
"""

from dataclasses import dataclass

from kaki_rag.ingest.clean import CleanBlock

TARGET_WORDS = 280
MAXIMUM_WORDS = 380
MINIMUM_WORDS = 60


@dataclass(frozen=True)
class Chunk:
    """One retrieval unit: text under its heading path, in document order."""

    index: int
    heading_path: tuple[str, ...]
    text: str
    word_count: int


def _word_count(text: str) -> int:
    return len(text.split())


def _split_long_paragraph(text: str, maximum_words: int) -> list[str]:
    """Split one oversized paragraph on word boundaries into bounded pieces."""
    words = text.split()
    return [
        " ".join(words[start:start + maximum_words])
        for start in range(0, len(words), maximum_words)
    ]


class _ChunkBuilder:
    """Accumulate paragraphs into bounded chunks, flushing on size and headings."""

    def __init__(self, target_words: int, maximum_words: int, minimum_words: int) -> None:
        self._target = target_words
        self._maximum = maximum_words
        self._minimum = minimum_words
        self._heading_path: list[str] = []
        self._chunk_heading_path: tuple[str, ...] = ()
        self._parts: list[str] = []
        self._words = 0
        self.chunks: list[Chunk] = []

    def enter_heading(self, block: CleanBlock) -> None:
        """Update the heading path; close the open chunk when it is big enough.

        A chunk still below the minimum size stays open so that very small
        sections merge with the following section instead of producing
        fragment chunks.
        """
        if self._words >= self._minimum:
            self._flush()
        del self._heading_path[block.level - 1:]
        while len(self._heading_path) < block.level - 1:
            self._heading_path.append("")
        self._heading_path.append(block.text)

    def add_paragraph(self, block: CleanBlock) -> None:
        """Append one paragraph, flushing beforehand when it would overflow."""
        for piece in _split_long_paragraph(block.text, self._maximum):
            words = _word_count(piece)
            if self._words and self._words + words > self._maximum:
                self._flush()
            if not self._parts:
                self._chunk_heading_path = tuple(part for part in self._heading_path if part)
            self._parts.append(piece)
            self._words += words
            if self._words >= self._target:
                self._flush()

    def finish(self) -> list[Chunk]:
        """Close any open chunk and return all chunks in order."""
        self._flush()
        return self.chunks

    def _flush(self) -> None:
        if not self._parts:
            return
        text = "\n".join(self._parts)
        self.chunks.append(
            Chunk(
                index=len(self.chunks),
                heading_path=self._chunk_heading_path,
                text=text,
                word_count=self._words,
            )
        )
        self._parts = []
        self._words = 0


def chunk_blocks(
    blocks: list[CleanBlock], *,
    target_words: int = TARGET_WORDS,
    maximum_words: int = MAXIMUM_WORDS,
    minimum_words: int = MINIMUM_WORDS,
) -> list[Chunk]:
    """Return bounded, heading-aware chunks for one page's cleaned blocks.

    Headings set the context path recorded on each chunk; paragraphs
    accumulate until the target size, never exceeding the maximum. Sections
    smaller than the minimum merge forward across the next heading.
    """
    if not 0 < minimum_words <= target_words <= maximum_words:
        raise ValueError("Chunk sizes must satisfy 0 < minimum <= target <= maximum.")
    builder = _ChunkBuilder(target_words, maximum_words, minimum_words)
    for block in blocks:
        if block.kind == "heading":
            builder.enter_heading(block)
        else:
            builder.add_paragraph(block)
    return builder.finish()
