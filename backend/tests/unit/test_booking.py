# v1.0 | 21-Sep-2026 | WP6.7 booking: routing, canned reply, receipt fields, no LLM.
"""Prove the booking path is deterministic and cannot shadow a refusal.

Three properties matter here (WP6-AT-19, WP6-AT-20):

- a direct booking request reaches the canned reply and no model is called;
- a booking regex placed after the credential and procedural rules cannot
  capture a credential request or a procedural question;
- the receipt body stays inside the slip contract's 40-word budget and the
  case reference reaches the response's existing `case_id` field.
"""

import unittest
from datetime import datetime, timezone

from kaki_backend.actions.book_action import (
    BOOKING_REPLIES,
    BOOKING_SLIPS,
    book_appointment,
    booking_case_id,
)
from kaki_backend.orchestration.intent_router import ACTION_INTENTS, Intent, route
from kaki_backend.orchestration.slip import MAX_SLIP_WORDS


BOOKING_UTTERANCES = (
    "book voucher collection",
    "Book my voucher collection please.",
    "I want to make an appointment.",
    "Can you arrange a collection for me?",
    "schedule a collection",
    "saya nak tempah temujanji",
)

# Requests that must never reach booking, with the intent that must win.
NOT_BOOKING = {
    # The credential rules return before booking is ever tested.
    "Log in to my Singpass for me.": Intent.REFUSE,
    "Book my Singpass password for me.": Intent.REFUSE,
    # The procedural guard answers questions about booking from the corpus.
    "How do I book my CDC vouchers?": Intent.ANSWER,
    "Where do I book a collection?": Intent.ANSWER,
    # Unrelated requests keep their own intents.
    "Can you repeat that?": Intent.REPEAT_PREVIOUS,
    "Please print that for me.": Intent.PRINT_PREVIOUS,
    "How do I use my CDC vouchers?": Intent.ANSWER,
}


class BookingRoutingTests(unittest.TestCase):
    def test_direct_booking_requests_route_to_the_booking_action(self):
        for utterance in BOOKING_UTTERANCES:
            with self.subTest(utterance=utterance):
                routing = route(utterance)
                self.assertEqual(routing.intent, Intent.BOOK_APPOINTMENT)
                self.assertIsNone(routing.refusal_reason)

    def test_booking_never_captures_a_refusal_or_a_procedural_question(self):
        for utterance, expected in NOT_BOOKING.items():
            with self.subTest(utterance=utterance):
                self.assertEqual(route(utterance).intent, expected)

    def test_booking_is_an_action_intent(self):
        self.assertIn(Intent.BOOK_APPOINTMENT, ACTION_INTENTS)


class ActionRefusalExclusivityTests(unittest.TestCase):
    """The pipeline checks `action` before `refusal_reason`, so they must never coexist.

    `turn_pipeline` shapes an action response before it shapes a refusal.
    That is only safe because the router returns early on a credential
    match, so a routing can carry an action intent or a refusal reason but
    never both. This test pins that invariant: if a later rule is ever added
    above the credential checks, an action would silently shadow a refusal
    and this fails first.
    """

    def test_no_routing_carries_both_an_action_intent_and_a_refusal(self):
        utterances = (
            *BOOKING_UTTERANCES,
            *NOT_BOOKING,
            "print my one-time password",
            "repeat my PIN",
            "book an appointment to reset my password",
            "unlock my account and book a slot",
            "What is the weather tomorrow?",
        )
        for utterance in utterances:
            with self.subTest(utterance=utterance):
                routing = route(utterance)
                acted = routing.intent in ACTION_INTENTS
                refused = routing.refusal_reason is not None
                self.assertFalse(acted and refused)
                if refused:
                    self.assertEqual(routing.intent, Intent.REFUSE)


class BookingOutcomeTests(unittest.TestCase):
    def test_the_reply_is_canned_and_names_the_office(self):
        outcome = book_appointment()
        self.assertEqual(outcome.reply_text, BOOKING_REPLIES["en"])
        self.assertEqual(outcome.display_text, BOOKING_REPLIES["en"])
        self.assertIn("level 1", outcome.reply_text)
        self.assertEqual(outcome.sources, ())
        self.assertTrue(outcome.speak)

    def test_malay_uses_the_malay_wording_and_slip(self):
        outcome = book_appointment("ms")
        self.assertEqual(outcome.reply_text, BOOKING_REPLIES["ms"])
        self.assertEqual(outcome.slip_text, BOOKING_SLIPS["ms"])
        self.assertEqual(outcome.language, "ms")

    def test_an_unknown_language_falls_back_to_english(self):
        outcome = book_appointment("ta")
        self.assertEqual(outcome.reply_text, BOOKING_REPLIES["en"])
        self.assertEqual(outcome.language, "en")

    def test_every_booking_slip_stays_within_the_word_budget(self):
        # WP6-AT-20 / WP1-AT-10: the receipt shares the slip contract.
        for language, slip in BOOKING_SLIPS.items():
            with self.subTest(language=language):
                self.assertLessEqual(len(slip.split()), MAX_SLIP_WORDS)

    def test_every_booking_slip_is_latin_1(self):
        # design.md 9.3: every slip leaves the backend as Latin-1 text.
        for language, slip in BOOKING_SLIPS.items():
            with self.subTest(language=language):
                slip.encode("latin-1")  # raises if a character cannot print

    def test_the_case_reference_is_shaped_like_the_prototype(self):
        moment = datetime(2026, 9, 20, 13, 56, tzinfo=timezone.utc)
        self.assertEqual(booking_case_id(moment), "EC-0920-1356")
        self.assertEqual(book_appointment(now=moment).case_id, "EC-0920-1356")


if __name__ == "__main__":
    unittest.main()
