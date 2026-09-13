# v1.0 | 13-Sep-2026 | WP4.2 repeat_previous from the stored turn.
"""Replay the previous spoken answer without generating or synthesising again.

WP4-AT-04: a repeat calls no LLM and the stored text is unchanged. The stored
reply audio is replayed as-is, so no TTS call happens either; if the stored
turn had no audio, the repeat has none. The slip is empty so that a client
with the `auto` print policy does not reprint (design.md 9.3).
"""

from kaki_backend.actions import ActionOutcome, ActionOutcomeKind
from kaki_backend.actions.print_action import nothing_to_act_on
from kaki_backend.contracts.turn_log import TurnExecution


def repeat_previous(previous: TurnExecution | None) -> ActionOutcome:
    """Return the previous turn's reply, display text, audio and sources unchanged."""
    if previous is None:
        return nothing_to_act_on()
    response = previous.response
    return ActionOutcome(
        kind=ActionOutcomeKind.RESOLVED,
        reply_text=response.reply_text,
        display_text=response.display_text,
        slip_text="",
        language=response.language,
        sources=tuple(response.sources),
        source_links=tuple(previous.log.source_links),
        speak=False,
        reply_audio=response.reply_audio,
        previous_turn_id=response.turn_id,
    )
