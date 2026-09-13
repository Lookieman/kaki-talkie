# v1.3 | 13-Sep-2026 | Refuse any credential mention without a procedural marker (WP3.4 defect).
# v1.2 | 13-Sep-2026 | Route repeat_previous and print_previous; own their fixed wording.
# v1.1 | 12-Sep-2026 | Drop the secret_volunteered input; refuse on the request alone.
# v1.0 | 12-Sep-2026 | Route answer/refuse and own the fixed refusal wording.
"""Decide whether a turn may be answered, and own every refusal string.

Three responsibilities, all deliberately free of model calls so that a
routing decision is reproducible and testable offline:

1. Credential rules that run *before* retrieval, generation and action
   routing (WP3-AT-08). Without a procedural marker, a transcript is refused
   when it names an authentication act or mentions a credential at all.
   design.md 8 draws the line: the *procedure* for resetting a Singpass
   password is ordinary grounded information, and only acting on the account
   or handling the secret itself is out of scope. GP2 is the most likely
   question at the pitch, so `how do I reset my Singpass password?` must
   answer while `what is my Singpass password?` must not.
   The credential rule is inverted rather than a verb list: a list missed
   "print my Singpass password", which then passed the evidence gate against
   the Singpass corpus and got a helpful reply. Any verb now refuses; only a
   procedural question is exempt.
2. Action rules (WP4.2), also before retrieval. "Can you repeat that?" and
   "Please print that for me." resolve from stored state, so they must never
   reach the evidence gate, which would refuse them: the 13-Sep-2026 probe
   scored such utterances at best dense 0.26-0.34, below the 0.50 gate. A
   procedural question is never an action, so "How do I print my CDC
   vouchers?" still answers.
3. The fixed wording. Refusal and action text is never model output: a
   no-coverage turn must not speak the model's apology (see `TurnPipeline`),
   because the demo, the spoken output and the devset all need stable strings.

The intent vocabulary here is internal (design.md 10 lists the MVP set).
`live_lookup` arrives with WP5.6. `kaki_handoff` and `calendar_create` are
deferred beyond the MVP (design.md v1.4) and are not built. Routing stays
rule-based until the WP5.5 DSPy migration. The public contract is untouched:
`refused` and `acted` have been `TurnState` members since WP1.1.
"""

import re
from dataclasses import dataclass
from enum import Enum


class Intent(str, Enum):
    """The internal routing decision for one turn."""

    ANSWER = "answer"
    REFUSE = "refuse"
    REPEAT_PREVIOUS = "repeat_previous"  #v1.2
    PRINT_PREVIOUS = "print_previous"  #v1.2


ACTION_INTENTS = frozenset({Intent.REPEAT_PREVIOUS, Intent.PRINT_PREVIOUS})  #v1.2


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


class ActionMessageKind(str, Enum):  #v1.2
    """Which fixed action wording a turn speaks."""

    PRINT_CONFIRMATION = "print_confirmation"
    NOTHING_TO_ACT_ON = "nothing_to_act_on"


# Action wording, keyed like the refusal catalogue. A resolved repeat speaks
# the stored answer itself and needs no entry here.
ACTION_MESSAGES: dict[str, dict[ActionMessageKind, RefusalMessage]] = {  #v1.2
    "en": {
        ActionMessageKind.PRINT_CONFIRMATION: RefusalMessage(
            reply_text="Here is your slip.",
            display_text="Here is your slip.",
        ),
        ActionMessageKind.NOTHING_TO_ACT_ON: RefusalMessage(
            reply_text="I have not answered a question yet. Please ask me first.",
            display_text="I have not answered a question yet. Please ask me first.",
        ),
    },
}


def refusal_message(reason: RefusalReason, language: str = DEFAULT_LANGUAGE) -> RefusalMessage:
    """Return the fixed wording for a refusal, falling back to English.

    An unknown language falls back rather than failing: a missing
    translation must never turn a refusal into an error.
    """
    catalogue = REFUSAL_MESSAGES.get(language) or REFUSAL_MESSAGES[DEFAULT_LANGUAGE]
    return catalogue[reason]


def action_message(kind: ActionMessageKind, language: str = DEFAULT_LANGUAGE) -> RefusalMessage:  #v1.2
    """Return the fixed wording for an action outcome, falling back to English."""
    catalogue = ACTION_MESSAGES.get(language) or ACTION_MESSAGES[DEFAULT_LANGUAGE]
    return catalogue[kind]


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

# A credential the kiosk must never hold. Any mention refuses unless the
# transcript asks about a procedure (v1.3): the verb does not matter, so "print",
# "send", "spell out" and "write down" are all covered without a list.
_CREDENTIAL_NOUN = (
    r"(?:password|passcode|pin|otp|one[- ]time\s+password|verification\s+code|kata\s+laluan)"
)
_CREDENTIAL_MENTION = re.compile(r"\b" + _CREDENTIAL_NOUN + r"\b", re.IGNORECASE)  #v1.3

# Malay procedural markers, exempting both the credential and the action rules:
# "macam mana" and "bagaimana" (how), "di mana" (where), "cara ... nak" (way
# to), and "apa" only in its procedural forms ("apa yang perlu saya buat",
# "apa langkah"). Bare "apa" is excluded because "Apa kata laluan Singpass
# saya?" asks for the password itself, which English refuses.
_MALAY_PROCEDURAL = re.compile(  #v1.3
    r"\b(?:macam\s+mana|bagaimana|di\s+mana|cara(?:nya)?\s+(?:nak|untuk|mahu)|"
    r"apa\s+(?:yang\s+)?(?:perlu|patut|harus|kena|boleh)|apa\s+(?:langkah|cara))\b",
    re.IGNORECASE,
)

# What may follow an action verb for it to aim at the previous reply rather
# than at a topic: "print that", "repeat again lah", "print it for me", or the
# end of the utterance. "Print my Singpass password" and "CHAS for repeat
# visits" therefore do not match.
_ANAPHORA = (  #v1.2
    r"(?=\s*(?:that|it|this|again|please|for\s+me|one\s+more\s+time|once\s+more|"
    r"yourself|what\s+you\s+said|the\s+(?:slip|receipt|answer)|a\s+(?:slip|copy|receipt)|"
    r"one|out\s+(?:that|it|this|the\s+slip|for\s+me)|can|lah|la|leh|lor|ah|"
    r"[.?!,]|$))"
)

_PRINT_REQUEST = re.compile(  #v1.2
    r"\bprint" + _ANAPHORA
    # "print my CDC voucher slip": print aimed at a slip or receipt (v1.3).
    + r"|\bprint\b[^.?!]{0,30}?\b(?:slip|receipt|printout)\b"
    + r"|\b(?:the|a|that|this)\s+(?:slip|receipt|printout)\b"
    + r"|\bcetak(?:kan)?(?=\s*(?:slip|resit|itu|tu|ini|lagi|semula|balik|untuk\s+saya|"
    r"lah|[.?!,]|$))",
    re.IGNORECASE,
)

_REPEAT_REQUEST = re.compile(  #v1.2
    r"\brepeat" + _ANAPHORA
    + r"|\b(?:can|could|would|please)\s+(?:you\s+)?repeat\b"
    + r"|\bsay\s+(?:that|it|again|one\s+more\s+time)\b"
    + r"|\btell\s+me\s+again\b|\bcome\s+again\b|\bpardon\b"
    + r"|\bwhat\s+did\s+you\s+(?:just\s+)?say\b"
    + r"|\b(?:didn'?t|did\s+not|never|cannot|can'?t)\s+(?:catch|hear)\b"
    + r"|\bulang(?:i|kan)?\b(?!\s*-?\s*(?:tahun|alik))"
    + r"|\b(?:cakap|sebut)\s+(?:sekali\s+)?lagi\b",
    re.IGNORECASE,
)


def route(transcript: str) -> Routing:
    """Return the intent for one transcript, refusing or acting before retrieval.

    Rules run in a fixed order: credential rules first (safety), then the
    procedural guard, then print and repeat requests, otherwise `answer`.
    Because credentials are checked first, `print_previous` and
    `repeat_previous` can never capture a credential request.
    A procedural question is never refused or treated as an action, which
    keeps the Singpass reset procedure and "How do I print my CDC vouchers?"
    answerable (design.md 8, runbook 9.1 WP4.2). Print is checked before
    repeat because "print it again" names the more specific act.

    The credential rule matches on the word, not on a secret value: the
    system still does not inspect transcripts for secrets (design.md 8). A
    transcript that mentions a credential without asking how to do something
    is treated as a credential request and refused, whatever its verb. A
    procedural question that also volunteers a credential still answers.
    """  #v1.3
    procedural = (
        _PROCEDURAL.search(transcript) is not None
        or _MALAY_PROCEDURAL.search(transcript) is not None
    )  #v1.3
    if not procedural and _AUTHENTICATION_ACT.search(transcript):
        # "Log in to my Singpass (for me)" - an action, not a question.
        return Routing(Intent.REFUSE, RefusalReason.CREDENTIAL_ACTION)
    if not procedural and _CREDENTIAL_MENTION.search(transcript):  #v1.3
        # "Print my Singpass password", "spell out my PIN" - any verb.
        return Routing(Intent.REFUSE, RefusalReason.CREDENTIAL_ACTION)
    if procedural:  #v1.3
        return Routing(Intent.ANSWER)
    if _PRINT_REQUEST.search(transcript):  #v1.2
        return Routing(Intent.PRINT_PREVIOUS)
    if _REPEAT_REQUEST.search(transcript):  #v1.2
        return Routing(Intent.REPEAT_PREVIOUS)
    return Routing(Intent.ANSWER)
