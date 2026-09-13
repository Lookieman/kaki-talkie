# v1.1 | 13-Sep-2026 | Credential requests refuse before actions; print my CDC voucher slip is a print.
# v1.0 | 13-Sep-2026 | Cover WP4.2 repeat and print routing, the procedural guard and near misses.
"""Verify WP4.2 action routing: rule-based, before retrieval, no model call.

Repeat and print requests route in English, Singlish and Malay. A procedural
question about printing ("How do I print my CDC vouchers?") still answers,
and topic words that merely contain an action verb do not trigger one. The
WP3.4 credential rules keep precedence.
"""

import unittest

from kaki_backend.orchestration.intent_router import (
    ACTION_INTENTS,
    ActionMessageKind,
    Intent,
    RefusalReason,
    action_message,
    route,
)

REPEAT_UTTERANCES = {
    "en": ["Can you repeat that?", "Please repeat that.", "Sorry, can you say that again?",
           "What did you say?", "Pardon?", "Tell me again please."],
    "singlish": ["Say again lah, I didn't catch that.", "Eh repeat leh",
                 "Can say one more time or not?"],
    "ms": ["Boleh ulang sekali lagi?", "Tolong ulangi.", "Cakap sekali lagi."],
}

PRINT_UTTERANCES = {
    "en": ["Please print that for me.", "Print it again please.", "Can I have the receipt?",
           "Could you print this?", "print my CDC voucher slip"],
    "singlish": ["Can print the slip for me ah?", "Print that one lah"],
    "ms": ["Tolong cetak slip itu.", "Cetak lagi.", "Boleh cetakkan untuk saya?"],
}


class ActionRoutingTests(unittest.TestCase):
    """Repeat and print requests route to their action intents in three varieties."""

    def test_repeat_requests_route_to_repeat_previous(self):
        for variety, utterances in REPEAT_UTTERANCES.items():
            for utterance in utterances:
                with self.subTest(variety=variety, utterance=utterance):
                    routing = route(utterance)
                    self.assertEqual(routing.intent, Intent.REPEAT_PREVIOUS)
                    self.assertIsNone(routing.refusal_reason)

    def test_print_requests_route_to_print_previous(self):
        for variety, utterances in PRINT_UTTERANCES.items():
            for utterance in utterances:
                with self.subTest(variety=variety, utterance=utterance):
                    routing = route(utterance)
                    self.assertEqual(routing.intent, Intent.PRINT_PREVIOUS)
                    self.assertIsNone(routing.refusal_reason)

    def test_action_intents_are_exactly_repeat_and_print(self):
        self.assertEqual(ACTION_INTENTS, {Intent.REPEAT_PREVIOUS, Intent.PRINT_PREVIOUS})


class ProceduralGuardTests(unittest.TestCase):
    """Questions about printing or repeating a scheme step are information requests."""

    def test_how_do_i_print_my_cdc_vouchers_still_answers(self):
        self.assertEqual(route("How do I print my CDC vouchers?").intent, Intent.ANSWER)

    def test_malay_procedural_print_question_answers(self):
        self.assertEqual(route("Macam mana nak cetak baucar CDC?").intent, Intent.ANSWER)

    def test_near_misses_do_not_trigger_an_action(self):
        for utterance in (
            "Can I use CHAS for repeat visits?",
            "Hari ulang tahun saya esok.",
            "I lost my CDC voucher slip",
            "How do I use my CDC vouchers?",
        ):
            with self.subTest(utterance=utterance):
                self.assertEqual(route(utterance).intent, Intent.ANSWER)


class PrecedenceTests(unittest.TestCase):
    """The WP3.4 credential rules run before the action rules."""

    def test_print_of_a_credential_refuses_rather_than_printing(self):
        routing = route("Print my Singpass password")
        self.assertEqual(routing.intent, Intent.REFUSE)
        self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)

    def test_credential_action_still_refuses_first(self):
        routing = route("Log in to my Singpass and print that for me.")
        self.assertEqual(routing.intent, Intent.REFUSE)
        self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)

    def test_procedural_singpass_question_is_neither_refused_nor_an_action(self):
        self.assertEqual(route("How do I reset my Singpass password?").intent, Intent.ANSWER)


class ActionWordingTests(unittest.TestCase):
    """Action wording is fixed application text with an English fallback."""

    def test_fixed_strings(self):
        self.assertEqual(action_message(ActionMessageKind.PRINT_CONFIRMATION).reply_text,
                         "Here is your slip.")
        self.assertEqual(
            action_message(ActionMessageKind.NOTHING_TO_ACT_ON).reply_text,
            "I have not answered a question yet. Please ask me first.",
        )

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(action_message(ActionMessageKind.PRINT_CONFIRMATION, "ms"),
                         action_message(ActionMessageKind.PRINT_CONFIRMATION))


if __name__ == "__main__":
    unittest.main()
