# v1.0 | 12-Sep-2026 | Choose the evidence chunk an answer actually relied on.
"""Decide which retrieved chunk a grounded answer is attributed to.

The top-ranked chunk is not reliably the one the answer came from: a corpus
page may rank first for a question it only mentions in passing, while the
answer is drawn from a lower-ranked page. Attributing the printed slip to
rank one therefore prints the wrong official source, which is exactly the
claim the product must never get wrong.

Selection prefers the block the model itself cited. When that citation is
missing or unusable, a deterministic word-overlap score against the reply
picks the closest chunk, so attribution stays reproducible and testable
offline. Rank one remains the last resort.
"""

import re

from kaki_backend.contracts.ports import EvidenceChunk

_WORD = re.compile(r"[a-z0-9]+")
# Frequent English words carry no attribution signal and would otherwise let
# a long chunk win purely on length.
_IGNORED_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from",
    "have", "how", "i", "if", "in", "is", "it", "may", "not", "of", "on", "or",
    "that", "the", "this", "to", "up", "use", "want", "what", "when", "which",
    "will", "with", "you", "your",
})


def _content_words(text: str) -> set[str]:
    """Return the lowercased content words of one text."""
    return {word for word in _WORD.findall(text.lower()) if word not in _IGNORED_WORDS}


def _overlap_score(reply_words: set[str], chunk: EvidenceChunk) -> float:
    """Return the share of the chunk's content words that the reply reuses.

    Normalising by chunk length keeps a short, precisely reused chunk ahead
    of a long chunk that merely happens to share vocabulary.
    """
    chunk_words = _content_words(" ".join((*chunk.heading_path, chunk.text)))
    if not chunk_words:
        return 0.0
    return len(reply_words & chunk_words) / len(chunk_words)


def select_cited_evidence(
    evidence: tuple[EvidenceChunk, ...], reply_text: str, cited_index: int | None,
) -> EvidenceChunk | None:
    """Return the chunk to attribute the answer to, or None without evidence.

    `cited_index` is the model's 1-based citation; it is honoured only when
    it addresses a chunk that was actually supplied. Otherwise the best
    word-overlap chunk wins, falling back to the top-ranked chunk when the
    reply shares no content words with any of them.
    """
    if not evidence:
        return None
    if cited_index is not None and 1 <= cited_index <= len(evidence):
        return evidence[cited_index - 1]
    reply_words = _content_words(reply_text)
    best = max(evidence, key=lambda chunk: _overlap_score(reply_words, chunk))
    return best if _overlap_score(reply_words, best) > 0 else evidence[0]
