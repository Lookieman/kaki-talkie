# v1.0 | 13-Sep-2026 | WP4.2 print_previous from the stored turn.
"""Return the previous slip unchanged, with a short spoken confirmation.

WP4-AT-05: the slip is the stored `slip_text`, never regenerated. The turn
speaks a fixed confirmation rather than the answer. The backend prints
nothing itself; the client applies its print policy (design.md 9.3), and an
`acted` turn with a non-empty slip is the print request.

Also owns the "nothing to act on" outcome shared with `repeat_previous`: a
calm fixed reply, no slip and no sources, marked distinctly in the debug view.
"""

from kaki_backend.actions import ActionOutcome, ActionOutcomeKind
from kaki_backend.contracts.turn_log import TurnExecution
from kaki_backend.orchestration.intent_router import (
    DEFAULT_LANGUAGE,
    ActionMessageKind,
    action_message,
)


def nothing_to_act_on() -> ActionOutcome:
    """Return the fixed reply for an action with no stored turn in its session."""
    message = action_message(ActionMessageKind.NOTHING_TO_ACT_ON)
    return ActionOutcome(
        kind=ActionOutcomeKind.NOTHING_TO_ACT_ON,
        reply_text=message.reply_text,
        display_text=message.display_text,
        slip_text="",
        language=DEFAULT_LANGUAGE,
        sources=(),
        source_links=(),
        speak=True,
    )


def print_previous(previous: TurnExecution | None) -> ActionOutcome:
    """Return the previous slip and sources unchanged with the fixed confirmation."""
    if previous is None:
        return nothing_to_act_on()
    message = action_message(ActionMessageKind.PRINT_CONFIRMATION)
    return ActionOutcome(
        kind=ActionOutcomeKind.RESOLVED,
        reply_text=message.reply_text,
        display_text=message.display_text,
        slip_text=previous.response.slip_text,
        language=DEFAULT_LANGUAGE,
        sources=tuple(previous.response.sources),
        source_links=tuple(previous.log.source_links),
        speak=True,
        previous_turn_id=previous.response.turn_id,
    )
