# v1.0 | 21-Sep-2026 | WP6.8 deterministic spoken-form normaliser for macOS say.
"""Turn a written reply into the form macOS `say` should speak (WP6-AT-22).

`display_text` keeps the written form the kiosk shows. This module produces
the spoken form, and nothing else in the system sees its output: it runs
inside the TTS adapter, immediately before synthesis, so the contract's
`reply_text` and the printed slip are unaffected.

Five deterministic rules, in this order (execution-plan.md 7, WP6.8):

1. numbered-list markers are dropped - "1. Tap the link." reads as a
   sentence, because `say` pronounces "1." as "one full stop";
2. known URLs are replaced by their spoken wording from a lookup table,
   because a read-aloud URL is unusable to a listener;
3. acronyms are wrapped in `[[char LTRL]]` ... `[[char NORM]]`, so CDC is
   spelled out rather than pronounced as a word;
4. round brackets are removed, keeping their contents as ordinary speech;
5. `[[slnc 400]]` is inserted between sentences, giving an elderly listener
   a beat to follow the step boundary.

The control sequences are macOS `say` embedded speech commands. They are
engine-specific by design: a different speech engine needs this module
rewritten, not merely reconfigured. Nothing here calls a model, and the
transform is pure - the same input always yields the same output.

The URL table is deliberately a lookup rather than a pattern. A generic URL
reader would have to guess at pronunciation for any address, and a wrong
guess is worse than the written form; an unknown URL is therefore left
exactly as written, and the table grows as the corpus does.
"""

import re

# Between sentences: long enough to hear as a pause, short enough not to
# sound like the kiosk has stopped working.
SENTENCE_SILENCE_MS = 400
LITERAL_ON = "[[char LTRL]]"
LITERAL_OFF = "[[char NORM]]"

# Spoken wording for the corpus's official addresses. Keys are matched
# case-insensitively, longest first, so a longer path wins over its origin.
URL_SPOKEN_FORMS = {
    "vouchers.cdc.gov.sg": "the C D C vouchers website",
    "www.cdc.gov.sg": "the C D C website",
    "cdc.gov.sg": "the C D C website",
    "www.chas.sg": "the CHAS website",
    "chas.sg": "the CHAS website",
    "www.singpass.gov.sg": "the Singpass website",
    "singpass.gov.sg": "the Singpass website",
    "www.careshieldlife.gov.sg": "the CareShield Life website",
    "careshieldlife.gov.sg": "the CareShield Life website",
    "www.gov.sg": "the government website",
    "supportgowhere.life.gov.sg": "the Support Go Where website",
}

# Acronyms the kiosk must spell out. Scheme names that read as words
# (Singpass, CareShield) are deliberately absent: spelling them would be
# worse than saying them.
SPELLED_ACRONYMS = ("CDC", "CHAS", "NRIC", "PIN", "OTP", "SMS", "ATM", "MRT")

# A numbered-list marker at the start of the text or after whitespace, in
# the exact form the grounded prompt asks for ("1. Do this. 2. Do that.").
# The same shape the slip builder parses, kept separate so the two can
# diverge without surprising each other.
_NUMBERED_MARKER = re.compile(r"(?:(?<=^)|(?<=\s))\d+[.)]\s+")
# A sentence boundary: terminal punctuation followed by whitespace.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_URL_PATTERN = re.compile(r"\b(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s,;)]*)?", re.I)
_ACRONYM_PATTERN = re.compile(r"\b(?:" + "|".join(SPELLED_ACRONYMS) + r")\b")
_BRACKETS = re.compile(r"[()]")
_WHITESPACE = re.compile(r"[ \t]+")


# Punctuation that ends the sentence an address sits in, rather than the
# address itself. It is handed back unchanged, or a URL at the end of a
# sentence would swallow the full stop the silence rule looks for.
_TRAILING_PUNCTUATION = ".,;:!?"


def _spoken_url(match: re.Match[str]) -> str:
    """Return the table's wording for a known address, or the text unchanged."""
    written = match.group(0)
    trailing = ""
    while written and written[-1] in _TRAILING_PUNCTUATION:
        trailing = written[-1] + trailing
        written = written[:-1]
    host = written.split("://", 1)[-1].split("/", 1)[0].lower()
    return URL_SPOKEN_FORMS.get(host, written) + trailing


def strip_list_markers(text: str) -> str:
    """Drop numbered-list markers so steps read as plain sentences."""
    return _NUMBERED_MARKER.sub("", text)


def spell_urls(text: str) -> str:
    """Replace known addresses with their spoken wording; leave others alone."""
    return _URL_PATTERN.sub(_spoken_url, text)


def spell_acronyms(text: str) -> str:
    """Wrap known acronyms so `say` spells them letter by letter."""
    return _ACRONYM_PATTERN.sub(lambda m: f"{LITERAL_ON}{m.group(0)}{LITERAL_OFF}", text)


def remove_brackets(text: str) -> str:
    """Remove round brackets, keeping what they contain as ordinary speech."""
    return _BRACKETS.sub("", text)


def add_sentence_silences(text: str) -> str:
    """Insert an explicit pause between sentences."""
    return _SENTENCE_BOUNDARY.sub(f" [[slnc {SENTENCE_SILENCE_MS}]] ", text)


def to_spoken_form(reply_text: str) -> str:
    """Return the spoken form of a written reply.

    Pure: no I/O, no model call, no randomness. Applied in the documented
    order, because each rule assumes the previous one has run - silences are
    inserted last so an inserted command can never be mistaken for a
    sentence boundary, and URLs are spelled before acronyms so an address
    is not part-spelled by the acronym rule.
    """
    text = strip_list_markers(reply_text)
    text = spell_urls(text)
    text = spell_acronyms(text)
    text = remove_brackets(text)
    text = add_sentence_silences(text)
    return _WHITESPACE.sub(" ", text).strip()
