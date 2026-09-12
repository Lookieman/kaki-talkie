# v1.1 | 12-Sep-2026 | Drop the volunteered-secret case with transcript redaction.
# v1.0 | 12-Sep-2026 | Cover the credential-action rules and the fixed refusal wording.
"""Verify WP3-AT-08 routing: refuse credential actions, answer procedures.

The boundary this module defends is the one design.md 8 draws. Explaining how
to reset a Singpass password is ordinary grounded information; acting on the
account or asking the kiosk to disclose a secret is not. The Singpass cases are
covered adversarially because GP2 is the most likely question at the pitch, so
a false refusal there would be a gate failure rather than a nuisance.

Merely volunteering a credential is not itself a refusal trigger: the system
does not inspect transcripts for secrets (design.md 8, owner decision
12-Sep-2026), so there is no such case here.
"""

import unittest

from kaki_backend.orchestration.intent_router import (
    Intent,
    RefusalReason,
    refusal_message,
    route,
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
        for transcript in (
            "How do I reset my Singpass password?",
            "How do I log in to Singpass?",
            "How can I unlock my Singpass account?",
            "Where do I reset my password?",
            "What do I do if I forgot my Singpass password?",
            "How do I use my CDC vouchers?",
            "Can I use CHAS at the clinic near my house?",
            "Macam mana nak reset kata laluan Singpass saya?",
        ):
            self.assertEqual(route(transcript).intent, Intent.ANSWER, msg=transcript)

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
