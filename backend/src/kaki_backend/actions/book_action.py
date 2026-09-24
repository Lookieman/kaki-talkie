# v1.1 | 24-Sep-2026 | WP6.8 voice revision: new English booking reply; Malay unchanged.
# v1.0 | 21-Sep-2026 | WP6.7 canned booking reply and its on-screen receipt.
"""Answer a booking request from fixed wording, never from the model (WP6-AT-19).

A booking request routes here through the same mechanism as the WP3.4
credential refusal: the router decides, the pipeline dispatches, and
retrieval, the evidence gate and the LLM are all skipped. The model is never
asked to say the right thing about a booking, so it cannot say a wrong one -
no invented phone number, opening hour or counter name can reach the user.

The wording is authored, not generated, so it is written here in the WP6.8
`a1_warm` register by hand: the booking path bypasses the persona prompt
entirely, and a canned line in the plain register beside persona-voiced
answers would sound like a different kiosk. It still flows through the
ordinary reply/display/slip fields. When a recorded clip of the exact reply
exists (`orchestration/canned_clips.py`), that clip is played; otherwise
WP6.8's spoken-form normaliser applies to it in the TTS adapter exactly as it
does to a generated answer.

The receipt the simulator draws is built from the existing contract fields:
`slip_text` carries the body, `case_id` the reference. The QR code and the
follow-up line on the drawn slip are printed illustration (execution-plan.md
7): this module creates no case record, stores no follow-up state and starts
no live-pipeline branch, so the reference is a demo identifier rather than a
key into anything.

The wording is provisional and editable, like the push message's
(scripts/seed_push_message.py): edit the constants and rehearse again.
"""

from datetime import datetime, timezone

from kaki_backend.actions import ActionOutcome, ActionOutcomeKind
from kaki_backend.orchestration.intent_router import DEFAULT_LANGUAGE

# Where the kiosk sends someone who wants to arrange a collection in person.
# The owner confirmed the destination on 19-Sep-2026 (execution-plan.md 7).
OFFICE_LOCATION = "the main office on level 1"

# The spoken and displayed wording, per language, in the a1_warm register.
# Kept within the same plain-sentence shape the grounded answers use, so the
# two sound like one kiosk.
BOOKING_REPLIES = {
    "en": (
        "Okay Auntie, done already! I book for you. "
        "Go to the main office on level 1 to collect your vouchers, can? "
        "Your receipt is on the screen."
    ),
    "ms": (
        "Baik, jangan risau. Pergi ke pejabat utama di tingkat 1. "
        "Staf di sana akan tempahkan untuk anda. Tunjukkan slip ini."
    ),
}

# The receipt body. Kept well inside the WP1-AT-10 40-word budget that every
# slip shares, and in Latin-1 like every other slip (design.md 9.3).
BOOKING_SLIPS = {
    "en": (
        "KAKI-TALKIE BOOKING\n"
        "Go to the main office, level 1.\n"
        "The staff will book your collection.\n"
        "Bring your NRIC.\n"
        "Show this slip at the counter."
    ),
    "ms": (
        "KAKI-TALKIE TEMPAHAN\n"
        "Pergi ke pejabat utama, tingkat 1.\n"
        "Staf akan tempahkan untuk anda.\n"
        "Bawa kad pengenalan anda.\n"
        "Tunjukkan slip ini di kaunter."
    ),
}

CASE_PREFIX = "EC"


def booking_case_id(now: datetime | None = None) -> str:
    """Return the demo case reference shown on the receipt.

    Shaped like the prototype's `EC-0920-1356`: a month-day and a
    hour-minute, which is short enough to read aloud at a counter. It keys
    nothing: no case is created, and two bookings in the same minute share a
    reference by design rather than by accident.
    """
    moment = now or datetime.now(timezone.utc)
    return f"{CASE_PREFIX}-{moment:%m%d}-{moment:%H%M}"


def book_appointment(
    language: str = DEFAULT_LANGUAGE, now: datetime | None = None,
) -> ActionOutcome:
    """Return the canned booking reply, its receipt body and a case reference.

    Takes no previous turn: a booking request stands on its own, unlike
    repeat and print, so there is nothing to resolve and nothing to fail.
    An unknown language falls back to English rather than failing, matching
    the refusal and action catalogues.
    """
    reply = BOOKING_REPLIES.get(language) or BOOKING_REPLIES[DEFAULT_LANGUAGE]
    slip = BOOKING_SLIPS.get(language) or BOOKING_SLIPS[DEFAULT_LANGUAGE]
    spoken_language = language if language in BOOKING_REPLIES else DEFAULT_LANGUAGE
    return ActionOutcome(
        kind=ActionOutcomeKind.RESOLVED,
        reply_text=reply,
        display_text=reply,
        slip_text=slip,
        language=spoken_language,
        sources=(),
        source_links=(),
        speak=True,
        case_id=booking_case_id(now),
    )
