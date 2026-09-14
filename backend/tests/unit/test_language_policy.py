# v1.0 | 13-Sep-2026 | WP5.1 reply-language policy over the curated cases (WP5-AT-02).
"""Verify the reply-language policy: transcript first, short utterances, STT, preference.

WP5-AT-02 runs every case in `agent/data/language_cases.jsonl`. The rule
tests pin the properties design.md 6.4 and the owner decisions of
13-Sep-2026 depend on: STT never decides alone, the preference outranks
Whisper's label on short utterances, and particles count for neither language.
"""

import json
import unittest
from pathlib import Path

from kaki_backend.contracts.ports import LanguageEvidence
from kaki_backend.orchestration.language_policy import (
    SHORT_UTTERANCE_TOKENS,
    DecisionRule,
    decide_reply_language,
)

CASES_PATH = Path(__file__).resolve().parents[3] / "agent/data/language_cases.jsonl"
CASE_FIELDS = {"id", "transcript", "stt_language", "preference", "expected_language", "note"}


def load_cases() -> list[dict]:
    """Read the curated cases; every line must carry exactly the documented fields."""
    return [json.loads(line) for line in CASES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def evidence(label: str | None) -> LanguageEvidence | None:
    return LanguageEvidence(language=label) if label else None


class CuratedCaseTests(unittest.TestCase):
    """WP5-AT-02: each curated case returns its expected reply language."""

    def test_case_file_is_well_formed(self):
        cases = load_cases()
        self.assertGreaterEqual(len(cases), 12)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case.get("id")):
                self.assertEqual(set(case), CASE_FIELDS)
                self.assertIn(case["expected_language"], ("en", "ms"))
                self.assertIn(case["preference"], ("en", "ms"))

    def test_every_case_returns_its_expected_language(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                decision = decide_reply_language(
                    case["transcript"], evidence(case["stt_language"]), case["preference"]
                )
                self.assertEqual(decision.language, case["expected_language"], case["note"])

    def test_no_case_decides_on_stt_evidence_without_transcript_support(self):
        for case in load_cases():
            decision = decide_reply_language(
                case["transcript"], evidence(case["stt_language"]), case["preference"]
            )
            if decision.rule is DecisionRule.STT_EVIDENCE:
                with self.subTest(case=case["id"]):
                    supporting = (decision.malay_tokens if decision.language == "ms"
                                  else decision.english_tokens)
                    self.assertGreater(supporting, 0)


class RuleTests(unittest.TestCase):
    """The rule order and its boundaries."""

    def test_transcript_overrides_a_contrary_stt_label(self):
        decision = decide_reply_language(
            "Macam mana nak reset kata laluan Singpass saya?", evidence("en"), "en"
        )
        self.assertEqual((decision.language, decision.rule), ("ms", DecisionRule.TRANSCRIPT))

    def test_short_utterance_preference_outranks_whisper(self):
        for preference in ("en", "ms"):
            with self.subTest(preference=preference):
                label = "ms" if preference == "en" else "en"
                decision = decide_reply_language("Baucar CDC tu?", evidence(label), preference)
                self.assertEqual(decision.language, preference)
                self.assertEqual(decision.rule, DecisionRule.SHORT_UTTERANCE)

    def test_short_utterance_threshold_is_inclusive(self):
        at_limit = " ".join(["Singpass"] * SHORT_UTTERANCE_TOKENS)
        above = " ".join(["Singpass"] * (SHORT_UTTERANCE_TOKENS + 1))
        self.assertEqual(
            decide_reply_language(at_limit, evidence("ms"), "en").rule,
            DecisionRule.SHORT_UTTERANCE,
        )
        self.assertEqual(
            decide_reply_language(above, evidence("ms"), "en").rule, DecisionRule.PREFERENCE,
        )

    def test_stt_breaks_a_long_tie_only_with_transcript_support(self):
        tie = "Tolong print slip itu untuk my mother, dia nak tengok the steps"
        self.assertEqual(decide_reply_language(tie, evidence("id"), "en").language, "ms")
        self.assertEqual(decide_reply_language(tie, evidence("en"), "ms").language, "en")
        self.assertEqual(decide_reply_language(tie, None, "ms").rule, DecisionRule.PREFERENCE)

    def test_particles_and_scheme_names_count_for_neither_language(self):
        decision = decide_reply_language("Singpass CHAS lah leh lor", evidence("en"), "ms")
        self.assertEqual((decision.malay_tokens, decision.english_tokens), (0, 0))

    def test_unsupported_preference_is_rejected(self):
        with self.assertRaises(ValueError):
            decide_reply_language("How do I use my CDC vouchers?", None, "zh")


if __name__ == "__main__":
    unittest.main()
