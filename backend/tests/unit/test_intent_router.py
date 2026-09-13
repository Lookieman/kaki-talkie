# v1.2 | 13-Sep-2026 | Inverted credential rule: any verb refuses; Malay markers; rule order.
# v1.1 | 12-Sep-2026 | Drop the volunteered-secret case with transcript redaction.
# v1.0 | 12-Sep-2026 | Cover the credential-action rules and the fixed refusal wording.
"""Verify WP3-AT-08 routing: refuse credential actions, answer procedures.

The boundary this module defends is the one design.md 8 draws. Explaining how
to reset a Singpass password is ordinary grounded information; acting on the
account or asking the kiosk to disclose a secret is not. The Singpass cases are
covered adversarially because GP2 is the most likely question at the pitch, so
a false refusal there would be a gate failure rather than a nuisance.

The credential rule is inverted (router v1.3): a credential mentioned without
a procedural marker refuses whatever the verb, because a fixed verb list
missed "print my Singpass password". The rule matches the word, not a secret
value; the system still does not inspect transcripts for secrets (design.md 8).
"""

import unittest

from kaki_backend.orchestration import intent_router
from kaki_backend.orchestration.intent_router import (
    Intent,
    RefusalReason,
    refusal_message,
    route,
)

PROCEDURAL_PHRASES = (
    "How do I reset my Singpass password?",
    "How do I log in to Singpass?",
    "How can I unlock my Singpass account?",
    "Where do I reset my password?",
    "What do I do if I forgot my Singpass password?",
    "How do I use my CDC vouchers?",
    "Can I use CHAS at the clinic near my house?",
    "Macam mana nak reset kata laluan Singpass saya?",
)


class SingpassBoundaryTests(unittest.TestCase):
    """The three named adversarial cases around the Singpass procedure."""

    def test_procedural_reset_question_is_answered(self):
        routing = route("How do I reset my Singpass password?")
        self.assertEqual(routing.intent, Intent.ANSWER)
        self.assertIsNone(routing.refusal_reason)

    def test_asking_for_the_password_value_is_refused(self):
        routing = route("What is my Singpass password?")
        self.assertEqual(routing.intent, Intent.REFUSE)
        self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)

    def test_asking_the_kiosk_to_log_in_is_refused(self):
        routing = route("Log in to Singpass for me")
        self.assertEqual(routing.intent, Intent.REFUSE)
        self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)


class ProceduralQuestionTests(unittest.TestCase):
    """Guidance questions stay answerable even when they name an auth action."""

    def test_procedural_phrasings_are_never_refused(self):
        self.assertEqual(len(PROCEDURAL_PHRASES), 8)
        for transcript in PROCEDURAL_PHRASES:
            with self.subTest(transcript=transcript):
                routing = route(transcript)
                self.assertEqual(routing.intent, Intent.ANSWER)
                self.assertIsNone(routing.refusal_reason)

    def test_malay_procedural_markers_exempt_a_credential_question(self):
        for transcript in (
            "Macam mana nak reset kata laluan Singpass saya?",
            "Bagaimana saya boleh tukar kata laluan Singpass?",
            "Di mana saya boleh reset kata laluan saya?",
            "Apa yang perlu saya buat kalau lupa kata laluan Singpass?",
            "Macam mana nak log in Singpass?",
        ):
            with self.subTest(transcript=transcript):
                self.assertEqual(route(transcript).intent, Intent.ANSWER)

    def test_unsupported_topics_are_left_to_the_evidence_gate(self):
        # Routing only owns credential rules; coverage is decided downstream.
        for transcript in (
            "What is the weather forecast for tomorrow?",
            "How do I apply for a HDB flat?",
            "Good morning, how are you today?",
        ):
            self.assertEqual(route(transcript).intent, Intent.ANSWER, msg=transcript)


class ActionRequestTests(unittest.TestCase):
    """Imperative authentication requests are refused without a procedural cue."""

    def test_authentication_actions_are_refused(self):
        for transcript in (
            "Log in to my Singpass",
            "Sign in for me please",
            "Login to Singpass and check my vouchers",
            "Unlock my account for me",
            "Tell me my OTP",
            "Give me the verification code",
        ):
            routing = route(transcript)
            self.assertEqual(routing.intent, Intent.REFUSE, msg=transcript)
            self.assertEqual(
                routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION, msg=transcript
            )


class CredentialMentionTests(unittest.TestCase):
    """Any verb with a credential refuses; the rule does not rely on a verb list."""

    def test_credential_with_any_verb_is_refused(self):
        for transcript in (
            "Print my Singpass password",
            "send me my password",
            "spell out my PIN",
            "write down my OTP",
        ):
            with self.subTest(transcript=transcript):
                routing = route(transcript)
                self.assertEqual(routing.intent, Intent.REFUSE)
                self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)

    def test_bare_malay_apa_does_not_exempt_asking_for_the_password(self):
        # "What is my Singpass password?" in Malay refuses, as the English does.
        routing = route("Apa kata laluan Singpass saya?")
        self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)

    def test_disclosure_verb_list_is_gone(self):
        self.assertFalse(hasattr(intent_router, "_DISCLOSURE_REQUEST"))


class RuleOrderTests(unittest.TestCase):
    """Credential rules run before action routing, so an action cannot capture one."""

    def test_credential_requests_shaped_as_actions_refuse(self):
        for transcript, action_rule in (
            ("Please print that password for me", intent_router._PRINT_REQUEST),
            ("Print the OTP slip for me", intent_router._PRINT_REQUEST),
            ("Say again my OTP", intent_router._REPEAT_REQUEST),
            ("Cetak lagi kata laluan saya", intent_router._PRINT_REQUEST),
        ):
            with self.subTest(transcript=transcript):
                # Precondition: on its own, the action rule would claim this turn.
                self.assertIsNotNone(action_rule.search(transcript))
                routing = route(transcript)
                self.assertEqual(routing.intent, Intent.REFUSE)
                self.assertEqual(routing.refusal_reason, RefusalReason.CREDENTIAL_ACTION)

    def test_print_of_a_slip_without_a_credential_is_still_an_action(self):
        self.assertEqual(route("print my CDC voucher slip").intent, Intent.PRINT_PREVIOUS)


class RefusalWordingTests(unittest.TestCase):
    """Refusal text is fixed, English, and never model output."""

    def test_both_reasons_have_calm_bounded_wording(self):
        for reason in RefusalReason:
            message = refusal_message(reason)
            self.assertTrue(message.reply_text.strip(), msg=reason)
            self.assertTrue(message.display_text.strip(), msg=reason)
            # design.md 9.1 keeps spoken replies to roughly 60 words.
            self.assertLessEqual(len(message.reply_text.split()), 60, msg=reason)

    def test_credential_refusal_warns_against_sharing_secrets(self):
        message = refusal_message(RefusalReason.CREDENTIAL_ACTION)
        self.assertIn("never share", message.reply_text.lower())

    def test_no_coverage_refusal_names_the_supported_topics(self):
        message = refusal_message(RefusalReason.NO_COVERAGE)
        for scheme in ("Singpass", "CDC Vouchers", "CHAS", "CareShield Life"):
            self.assertIn(scheme, message.reply_text)

    def test_unknown_language_falls_back_to_english(self):
        # WP5.1 adds languages to the catalogue; a gap must not raise.
        self.assertEqual(
            refusal_message(RefusalReason.NO_COVERAGE, "ms"),
            refusal_message(RefusalReason.NO_COVERAGE, "en"),
        )


if __name__ == "__main__":
    unittest.main()
