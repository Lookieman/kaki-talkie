# v1.0 | 10-Sep-2026 | Provide the BM25 lexical index protecting exact Singapore terms.
"""Lexical BM25 ranking over the processed chunks (WP3-AT-04).

The lexical path exists so that exact scheme terms - `CHAS`, `CDC`,
`Singpass` - match literally regardless of embedding behaviour. It is a
plain BM25 implementation over lowercased ASCII word tokens with no
third-party dependency; non-Latin text (for example a fully Chinese
utterance) simply yields no lexical candidates and is served by the dense
multilingual path instead. Ranking is deterministic: ties break on the
chunk identifier.
"""

import math
import re
from collections import Counter

from kaki_rag.retrieve.chunks import CorpusChunk

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    """Return the lowercased ASCII word tokens of one text."""
    return TOKEN_PATTERN.findall(text.lower())


class BM25Index:
    """An in-memory BM25 index over the corpus chunks' text and headings.

    Heading paths are indexed with the body text so a chunk whose section
    title names the scheme ranks for that exact term.
    """

    def __init__(self, chunks: list[CorpusChunk], *, k1: float = K1, b: float = B) -> None:
        self._k1 = k1
        self._b = b
        self._chunk_ids: list[str] = []
        self._term_frequencies: list[Counter[str]] = []
        self._lengths: list[int] = []
        document_frequency: Counter[str] = Counter()
        for chunk in chunks:
            tokens = tokenize(" ".join((*chunk.heading_path, chunk.text)))
            self._chunk_ids.append(chunk.chunk_id)
            self._term_frequencies.append(Counter(tokens))
            self._lengths.append(len(tokens))
            document_frequency.update(set(tokens))
        total = len(chunks)
        self._average_length = (sum(self._lengths) / total) if total else 0.0
        self._idf = {
            term: math.log(1.0 + (total - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def query(self, text: str, top_k: int) -> list[tuple[str, float]]:
        """Return up to `top_k` `(chunk_id, score)` pairs with positive BM25 scores.

        An empty or fully non-ASCII query returns an empty list rather than
        failing; the dense path covers it.
        """
        query_terms = tokenize(text)
        if not query_terms or not self._chunk_ids:
            return []
        scored: list[tuple[str, float]] = []
        for chunk_id, frequencies, length in zip(
            self._chunk_ids, self._term_frequencies, self._lengths
        ):
            score = 0.0
            for term in query_terms:
                idf = self._idf.get(term)
                frequency = frequencies.get(term, 0)
                if idf is None or frequency == 0:
                    continue
                normalised = frequency * (self._k1 + 1) / (
                    frequency
                    + self._k1 * (1 - self._b + self._b * length / self._average_length)
                )
                score += idf * normalised
            if score > 0.0:
                scored.append((chunk_id, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored[:top_k]
