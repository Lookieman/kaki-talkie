# v1.1 | 14-Sep-2026 | Reject a render whose digit sequences differ from the English reply.
# v1.0 | 13-Sep-2026 | WP5.1 Malay reply modes, the render check and WAV joining.
"""Turn the English grounded answer into the reply a Malay turn speaks.

The English answer always comes first (runbook 10.1 WP5.1, "Reply modes"):
its citation, `SOURCE: 0` signal, evidence gate and slip are settled before
anything here runs. `KAKI_MALAY_REPLY_MODE` then selects the spoken and
displayed reply for a turn the language policy decided is Malay:

- `full`: one render call rewrites the English reply into Malay. The call
  sees the English reply text alone, never the evidence, so it rewrites and
  cannot answer. An error, an empty result, a changed set of digit
  sequences, or a length more than `RENDER_LENGTH_TOLERANCE` away from the
  English reply falls back to the English reply, and the outcome is
  recorded for the debug view.
- `bridge`: fixed Malay greeting and closing around the English reply. Demo
  insurance; WP5-AT-01 passes in `full` mode only.
- `english`: the English reply, and English fixed wording everywhere.

Refusal and action wording is fixed text in `intent_router`, so no mode
renders it.
"""

import io
import re  #v1.1
from base64 import b64decode, b64encode
from collections import Counter  #v1.1
from dataclasses import dataclass
from enum import Enum
from wave import Error as WaveError
from wave import open as wave_open

from kaki_backend.contracts.ports import LlmError, LlmPort, TtsError
from kaki_backend.orchestration.language_policy import ENGLISH, MALAY

# A rendered reply whose length differs from the English reply by more than
# this share of the English length is treated as a failed rewrite: it has
# likely dropped steps or started answering on its own.
RENDER_LENGTH_TOLERANCE = 0.5

# ASCII digit runs: step numbers, amounts, dates, phone numbers. A render must
# carry exactly the same multiset, so a changed figure or a dropped date is
# caught without a model.
_DIGIT_RUN = re.compile(r"[0-9]+")  #v1.1

BRIDGE_GREETING = "Baiklah, saya jawab dalam bahasa Inggeris ya."
BRIDGE_CLOSING = "Kalau ada soalan lagi, tanya saya ya."

WAV_DATA_URL_PREFIX = "data:audio/wav;base64,"


class ReplyMode(str, Enum):
    """How a Malay answered turn builds its spoken and displayed reply."""

    FULL = "full"
    BRIDGE = "bridge"
    ENGLISH = "english"


class RenderOutcome(str, Enum):
    """What happened to a full-mode render; stored for the debug view."""

    RENDERED = "rendered"
    FALLBACK_EMPTY = "fallback_empty"
    FALLBACK_NUMBERS = "fallback_numbers"  #v1.1
    FALLBACK_LENGTH = "fallback_length"
    FALLBACK_ERROR = "fallback_error"


@dataclass(frozen=True)
class ComposedReply:
    """The reply text, its response language and the speech segments to synthesise.

    `segments` are `(text, language)` pairs spoken in order and joined into
    one WAV. `render_outcome` is None unless a render was attempted.
    """

    text: str
    language: str
    segments: tuple[tuple[str, str], ...]
    render_outcome: RenderOutcome | None = None


def fixed_wording_language(decided: str, mode: ReplyMode) -> str:
    """Return the language of fixed refusal and action wording for a turn."""
    return ENGLISH if mode is ReplyMode.ENGLISH else decided


def digit_sequences(text: str) -> Counter[str]:  #v1.1
    """Return the multiset of ASCII digit runs in `text`, for example {"1": 1, "2026": 1}."""
    return Counter(_DIGIT_RUN.findall(text))


def check_render(english: str, rendered: str) -> RenderOutcome:
    """Judge a render against the English reply without a model.

    In order: empty text; a different multiset of digit sequences (a changed,
    added or dropped number or date); a length more than
    `RENDER_LENGTH_TOLERANCE` of the English length away. The first failure
    decides the recorded outcome.
    """  #v1.1
    if not rendered.strip():
        return RenderOutcome.FALLBACK_EMPTY
    if digit_sequences(rendered) != digit_sequences(english):  #v1.1
        return RenderOutcome.FALLBACK_NUMBERS
    english_length = len(english.strip())
    if abs(len(rendered.strip()) - english_length) > RENDER_LENGTH_TOLERANCE * english_length:
        return RenderOutcome.FALLBACK_LENGTH
    return RenderOutcome.RENDERED


def _english(text: str, outcome: RenderOutcome | None = None) -> ComposedReply:
    return ComposedReply(text, ENGLISH, ((text, ENGLISH),), outcome)


def compose_answer(
    english_reply: str, decided: str, mode: ReplyMode, llm: LlmPort,
) -> ComposedReply:
    """Build the answered reply for the decided language and mode.

    Calls `llm.render_reply` only for a Malay turn in `full` mode, passing the
    English reply text and nothing else. Never raises for a render failure:
    `LlmError` becomes `fallback_error` with the English reply.
    """
    if decided != MALAY or mode is ReplyMode.ENGLISH:
        return _english(english_reply)
    if mode is ReplyMode.BRIDGE:
        return ComposedReply(
            f"{BRIDGE_GREETING} {english_reply} {BRIDGE_CLOSING}", MALAY,
            ((BRIDGE_GREETING, MALAY), (english_reply, ENGLISH), (BRIDGE_CLOSING, MALAY)),
        )
    try:
        rendered = llm.render_reply(english_reply, MALAY)
    except LlmError:
        return _english(english_reply, RenderOutcome.FALLBACK_ERROR)
    outcome = check_render(english_reply, rendered)
    if outcome is not RenderOutcome.RENDERED:
        return _english(english_reply, outcome)
    text = rendered.strip()
    return ComposedReply(text, MALAY, ((text, MALAY),), RenderOutcome.RENDERED)


def join_wav_data_urls(urls: list[str]) -> str:
    """Concatenate WAV data URLs of identical format into one WAV data URL.

    `say` writes every segment in the same PCM format, so frames join
    without resampling. Raises TtsError("invalid_output") for a malformed
    segment or mismatched formats.
    """
    parameters = None
    frames = bytearray()
    for url in urls:
        if not url.startswith(WAV_DATA_URL_PREFIX):
            raise TtsError("invalid_output")
        try:
            with wave_open(io.BytesIO(b64decode(url[len(WAV_DATA_URL_PREFIX):])), "rb") as segment:
                current = (segment.getnchannels(), segment.getsampwidth(), segment.getframerate())
                frames.extend(segment.readframes(segment.getnframes()))
        except (WaveError, EOFError, ValueError):
            raise TtsError("invalid_output") from None
        if parameters is not None and current != parameters:
            raise TtsError("invalid_output")
        parameters = current
    if parameters is None:
        raise TtsError("invalid_output")
    buffer = io.BytesIO()
    with wave_open(buffer, "wb") as joined:
        joined.setnchannels(parameters[0])
        joined.setsampwidth(parameters[1])
        joined.setframerate(parameters[2])
        joined.writeframes(bytes(frames))
    return WAV_DATA_URL_PREFIX + b64encode(buffer.getvalue()).decode("ascii")
