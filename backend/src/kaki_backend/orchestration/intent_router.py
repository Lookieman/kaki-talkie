# v1.1 | 12-Sep-2026 | Drop the secret_volunteered input; refuse on the request alone.
# v1.0 | 12-Sep-2026 | Route answer/refuse and own the fixed refusal wording.
"""Decide whether a turn may be answered, and own every refusal string.

Two responsibilities, both deliberately free of model calls so that a
refusal is reproducible and testable offline:

1. Request rules that run *before* retrieval and generation. A request for
   the kiosk to authenticate on the user's behalf, or to disclose a
   credential, is refused outright (WP3-AT-08).
   design.md 8 draws the line precisely: the *procedure* for resetting a
   Singpass password is ordinary grounded information, and only acting on
   the account or handling the secret itself is out of scope. GP2 is the
   most likely question at the pitch, so `how do I reset my Singpass
   password?` must answer while `what is my Singpass password?` must not.
2. The refusal wording. Refusal text is never model output: a no-coverage
   turn must not speak the model's apology (see `TurnPipeline`), because the
   demo, the spoken output and the devset all need stable strings.

The intent vocabulary here is internal (design.md 10 lists the full MVP set).
WP3.4 needs only `answer` and `refuse`; `print_previous`, `repeat_previous`,
`kaki_handoff` and `calendar_create` arrive with their own units, and
`live_lookup` with WP5.6. The public contract is untouched: `refused` has
been a `TurnState` member since WP1.1.
"""

import re
from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    """The internal routing decision for one turn."""

    ANSWER = "answer"
    REFUSE = "refuse"


class RefusalReason(str, Enum):
    """Why a turn was refused; recorded for evidence and the devset."""

    CREDENTIAL_ACTION = "credential_action"
    NO_COVERAGE = "no_coverage"


@dataclass(frozen=True)
class RefusalMessage:
    """The spoken and displayed wording for one refusal reason."""

    reply_text: str
    display_text: str


# One catalogue, keyed by language then reason, so WP5.1 adds a language by
# adding a key here rather than by touching the pipeline. English is the MVP
# reply language and the permanent fallback.
REFUSAL_MESSAGES: dict[str, dict[RefusalReason, RefusalMessage]] = {
    "en": {
        RefusalReason.NO_COVERAGE: RefusalMessage(
            reply_text=(
                "Sorry, I do not have official information about that. I can help with "
                "Singpass, CDC Vouchers, CHAS and CareShield Life. For anything else, "
                "please ask a staff member at your community centre."
            ),
            display_text="No official information on that. Please ask a community centre staff member.",
        ),
        RefusalReason.CREDENTIAL_ACTION: RefusalMessage(
            reply_text=(
                "Sorry, I cannot log in for you or handle your password. Never share your "
                "password or one-time password with anyone, including me. I can explain the "
                "official steps so you can do it yourself."
            ),
            display_text="I cannot handle passwords. Never share them with anyone.",
        ),
    },
}

DEFAULT_LANGUAGE = "en"


def refusal_message(reason: RefusalReason, language: str = DEFAULT_LANGUAGE) -> RefusalMessage:
    """Return the fixed wording for a refusal, falling back to English.

    An unknown language falls back rather than failing: a missing
    translation must never turn a refusal into an error.
    """
    catalogue = REFUSAL_MESSAGES.get(language) or REFUSAL_MESSAGES[DEFAULT_LANGUAGE]
    return catalogue[reason]


@dataclass(frozen=True)
class Routing:
    """The routing outcome: an intent and, when refusing, the reason."""

    intent: Intent
    refusal_reason: RefusalReason | None = None


# A question about a procedure. Its presence is what separates "how do I log
# in?" (answerable guidance) from "log in for me" (an action request).
_PROCEDURAL = re.compile(
    r"\b(?:how\s+(?:do|can|to|does|would)|where\s+(?:do|can|is|are)|"
    r"what\s+(?:do|should)\s+i|steps\s+to|guide\s+to|process\s+for)\b",
    re.IGNORECASE,
)

# Authentication acts only. Broader verbs such as "apply" are deliberately
# excluded: "apply for CHAS for me" is better served by the CHAS page than by
# a refusal about passwords.
_AUTHENTICATION_ACT = re.compile(
    r"\b(?:log\s?in|login|log\s?on|sign\s?in|sign\s?on|unlock|authenticate)\b",
    re.IGNORECASE,
)

# Asking the kiosk to reveal a secret it must never hold.
_CREDENTIAL_NOUN = (
    r"(?:password|passcode|pin|otp|one[- ]time\s+password|verification\s+code|kata\s+laluan)"
)
_DISCLOSURE_REQUEST = re.compile(
    r"\b(?:what(?:'s|s)?|what\s+is|tell\s+me|show\s+me|give\s+me|read\s+out|say)\b"
    r"[^.?!]{0,40}?\b" + _CREDENTIAL_NOUN + r"\b",
    re.IGNORECASE,
)


def route(transcript: str) -> Routing:
    """Return the intent for one transcript, refusing before retrieval.

    Rules are evaluated most-specific first. A procedural question is never
    refused here, which is what keeps the official Singpass reset procedure
    answerable (design.md 8).

    A transcript that merely contains a volunteered credential is not
    refused on that basis: the system does not inspect transcripts for
    secrets, because design.md 8 declines to promise a protection it cannot
    deliver once the audio has reached the STT service. What is refused is
    the *request* - an account action, or asking the kiosk to disclose a
    credential.
    """  #v1.1
    procedural = _PROCEDURAL.search(transcript) is not None
    if not procedural and _AUTHENTICATION_ACT.search(transcript):
        # "Log in to my Singpass (for me)" - an action, not a question.
        return Routing(Intent.REFUSE, RefusalReason.CREDENTIAL_ACTION)
    if not procedural and _DISCLOSURE_REQUEST.search(transcript):
        return Routing(Intent.REFUSE, RefusalReason.CREDENTIAL_ACTION)
    return Routing(Intent.ANSWER)
