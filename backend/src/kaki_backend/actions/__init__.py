# v1.0 | 13-Sep-2026 | WP4.2 action outcome and the stored-turn history the actions read.
"""Deterministic actions that answer from stored turns rather than from models.

`repeat_previous` and `print_previous` (runbook 9.1 WP4.2) resolve their
target from SQLite through `TurnHistory`, so they work after a backend
restart and never call retrieval or the LLM. Each action returns an
`ActionOutcome`; the turn pipeline turns it into an `acted` response.

The print policy is not decided here. design.md 9.3 places it on the client:
the backend always produces the same response, and only a `print_previous`
outcome carries a non-empty slip on an `acted` turn.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.contracts.turn_log import SourceLink, TurnExecution


class ActionOutcomeKind(str, Enum):
    """Whether an action found a stored turn to act on."""

    RESOLVED = "resolved"
    NOTHING_TO_ACT_ON = "nothing_to_act_on"


class TurnHistory(Protocol):
    """Read the stored turn an action resolves to."""

    def previous_content_turn(self, session_id: str) -> TurnExecution | None:
        """Return the newest stored `answered` or `refused` turn in the session.

        `acted` and `failed` turns are skipped, so a repeat after a print
        resolves to the same original answer. None when no turn qualifies.
        """


class NoTurnHistory:
    """Report no stored turns; the default for pipelines built without a store."""

    def previous_content_turn(self, session_id: str) -> TurnExecution | None:
        """Return None: nothing has been stored."""
        return None


@dataclass(frozen=True)
class ActionOutcome:
    """The content an action turn returns, before speech is decided.

    `reply_audio` is used as-is when `speak` is false (a resolved repeat
    replays the stored bytes); otherwise the pipeline synthesises
    `reply_text`. `source_links` align with `sources` so the store can copy
    the previous turn's `turn_sources` rows.

    `case_id` fills the contract's existing `case_id` field, which every
    other path leaves null. WP6.7's booking receipt is the first thing that
    needs a reference the user can quote at the counter, and it travels in
    the field WP1 already defined rather than a new one (owner decision,
    21-Sep-2026).
    """

    kind: ActionOutcomeKind
    reply_text: str
    display_text: str
    slip_text: str
    language: str
    sources: tuple[SourceRecord, ...]
    source_links: tuple[SourceLink, ...]
    speak: bool
    reply_audio: str | None = None
    previous_turn_id: str | None = None
    case_id: str | None = None  #v1.2
