# v1.6 | 14-Sep-2026 | Drop the referral question when the Latin-1 cut removes more than a quarter of it.
# v1.5 | 13-Sep-2026 | WP5.1: keep every slip within Latin-1 for the thermal printer.
# v1.4 | 12-Sep-2026 | Drop the redaction precondition from the referral slip.
# v1.3 | 12-Sep-2026 | Add the refusal referral slip, which carries no source or date.
# v1.2 | 12-Sep-2026 | Identify the source by domain alone; drop page titles from the slip.
# v1.1 | 12-Sep-2026 | Pack whole steps within the budget; never print a fragment.
# v1.0 | 11-Sep-2026 | Build the deterministic English slip from answer steps and provenance.
"""Compose `slip_text` from structured answer content and application metadata.

The slip is a printed artefact (design.md 9.3): short heading, a few short
instruction lines, the primary source and its "Source checked" date, and an
ask-again line. The WP1 device contract counts the whole `slip_text` against
40 words (`backend/tests/contract/test_wp1_4.py`).

Nothing here is ever truncated mid-phrase. Steps are whole sentences, packed
greedily in order until the next one would breach the budget, so the limit
holds by construction rather than by trimming afterwards; a slip with no room
for any step still prints its heading and full provenance.

The source line names the official domain alone. Page titles are deliberately
excluded: corpus titles are sometimes whole questions ("I forgot my Singpass
password. How do I reset it?"), which read poorly as attribution and spend
budget that belongs to the instructions. The domain is what a reader can act
on and verify, and it is never the full URL.

The builder works from structured content (instruction steps plus a source
record), not from raw `reply_text`: WP5-AT-01 pairs a Malay spoken reply with
an English slip, so the spoken text and the slip content must be separable.
Nothing here calls a model; slip wording is deterministic until the DSPy unit
revisits it.

Every slip leaves here as Latin-1 text (WP5.1, owner decision 13-Sep-2026).
The referral slip prints the question as captured, so a Malay question prints
in its own words; Malay is plain Latin script. Typographic punctuation folds
to its ASCII form and anything else outside Latin-1, such as CJK, is dropped
before the text can reach the printer. WP6.3 confirms the code page on the
real printer.
"""

import re
import unicodedata  #v1.5
from urllib.parse import urlsplit

from kaki_backend.contracts.responses import SourceRecord

SLIP_HEADING = "KAKI-TALKIE HELP"
ASK_AGAIN_LINE = "Ask KaKi-Talkie again if needed."
MAX_SLIP_WORDS = 40
MAX_STEPS = 4  #v1.1

REFERRAL_HEADING = "KAKI-TALKIE REFERRAL"  #v1.3
REFERRAL_LINE = "Please ask a community centre staff member for help."  #v1.3
QUESTION_PREFIX = "You asked:"  #v1.3

# Typographic characters outside Latin-1 that have a faithful ASCII form.
_ASCII_FOLDS = str.maketrans({  #v1.5
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2022": "-",
    "\u2026": "...", "\u00a0": " ", "\u202f": " ",
})
_LATIN_1_LIMIT = 0xFF  #v1.5
# A referral question that loses more than this share of its visible
# characters to the Latin-1 cut is omitted: what survives would be fragments
# such as "CHAS." under "You asked:", not the question.
MAX_QUESTION_CHARACTERS_REMOVED = 0.25  #v1.6

_NUMBERED_ITEM = re.compile(r"(?:(?<=^)|(?<=\s))\d+[.)]\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_TERMINAL_PUNCTUATION = (".", "!", "?")


def _fold(text: str) -> str:  #v1.6
    """Compose accents and fold typographic punctuation to ASCII; drop nothing."""
    return unicodedata.normalize("NFC", text).translate(_ASCII_FOLDS)


def to_printable(text: str) -> str:  #v1.5
    """Return `text` reduced to Latin-1 with whitespace collapsed.

    Composes accents first (NFC), folds typographic punctuation to ASCII,
    then drops every remaining character above U+00FF.
    """
    kept = "".join(character for character in _fold(text) if ord(character) <= _LATIN_1_LIMIT)
    return " ".join(kept.split())


def removed_share(text: str) -> float:  #v1.6
    """Return the share of visible characters `to_printable` would drop from `text`.

    Measured after folding, over non-whitespace characters, so a folded
    quote or dash counts as kept. Empty or all-whitespace text returns 0.
    """
    visible = [character for character in _fold(text) if not character.isspace()]
    if not visible:
        return 0.0
    removed = sum(1 for character in visible if ord(character) > _LATIN_1_LIMIT)
    return removed / len(visible)


def extract_steps(reply_text: str) -> list[str]:
    """Derive whole instruction sentences from the answer text.

    Prefers the numbered steps the grounded prompt asks the model for, and
    falls back to sentences when the answer is prose. Steps are returned
    complete and unabridged: fitting them to the slip is `build_slip`'s job,
    because only it knows how much room the provenance leaves.
    """
    numbered = [part.strip() for part in _NUMBERED_ITEM.split(reply_text)[1:] if part.strip()]
    candidates = numbered or [
        part.strip() for part in _SENTENCE_END.split(reply_text) if part.strip()
    ]
    steps = []
    for candidate in candidates[:MAX_STEPS]:
        step = " ".join(candidate.split())
        if not step:
            continue
        if not step.endswith(_TERMINAL_PUNCTUATION):
            step += "."
        steps.append(step)
    return steps


def build_slip(steps: list[str], source: SourceRecord) -> str:
    """Return the complete printable slip within the 40-word contract.

    `steps` are whole English instruction sentences (see `extract_steps`);
    the source domain and checked date derive only from the application-owned
    record. Steps are added in order while they fit, and packing stops at the
    first that does not so the printed procedure keeps its original order.
    """  #v1.2
    domain = to_printable(urlsplit(source.source_url).hostname or "") or "official source"  #v1.5
    footer = [
        f"Source: {domain}",  #v1.2
        f"Source checked: {source.captured_at.strftime('%d-%b-%Y')}",
        ASK_AGAIN_LINE,
    ]
    used = len(" ".join([SLIP_HEADING, *footer]).split())

    kept: list[str] = []
    for step in steps[:MAX_STEPS]:
        step = to_printable(step)  #v1.5
        if not step:
            continue
        step_words = len(step.split())
        if used + step_words > MAX_SLIP_WORDS:
            break
        kept.append(step)
        used += step_words
    return "\n".join([SLIP_HEADING, *kept, *footer])


def build_refusal_slip(question: str) -> str:  #v1.3
    """Return the referral slip for a refused turn, within the 40-word contract.

    A refusal has no evidence, so this slip deliberately carries no source
    line and no "Source checked" date: printing either would assert a
    provenance the turn does not have. WP3-AT-07 governs answered slips.

    `question` is the transcript as recognised, in whatever language was
    spoken; the slip reproduces it so a staff member can see what was asked.
    It is reduced to Latin-1 first. When that cut would remove more than
    `MAX_QUESTION_CHARACTERS_REMOVED` of its visible characters, as for a
    Chinese question, the question and its `You asked:` line are omitted
    rather than printed hollow. Otherwise its sentences are packed whole, in
    order, while they fit; a question too long for the budget is omitted
    rather than cut short. The heading and referral line always print.
    """  #v1.6
    used = len(" ".join([REFERRAL_HEADING, REFERRAL_LINE, QUESTION_PREFIX]).split())
    kept: list[str] = []
    printable = removed_share(question) <= MAX_QUESTION_CHARACTERS_REMOVED  #v1.6
    for sentence in extract_steps(to_printable(question)) if printable else []:  #v1.6
        sentence_words = len(sentence.split())
        if used + sentence_words > MAX_SLIP_WORDS:
            break
        kept.append(sentence)
        used += sentence_words
    if not kept:
        return "\n".join([REFERRAL_HEADING, REFERRAL_LINE])
    return "\n".join([REFERRAL_HEADING, REFERRAL_LINE, QUESTION_PREFIX, *kept])
