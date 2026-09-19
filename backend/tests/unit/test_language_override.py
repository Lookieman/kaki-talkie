# v1.0 | 18-Sep-2026 | WP6.6: the per-device admin override of the reply language.
"""Prove the override rules in the pipeline with fake ports (WP6-AT-15).

The properties: `en`/`ms` beats the section 6.4 policy whatever the
transcript and STT say; `auto` is byte-identical to the shipped policy; the
STT evidence is never rewritten; and the stored turn records that the admin,
not the policy, chose the language. A pipeline built without the callable
behaves exactly as before WP6.6.
"""

import sys
import unittest
from pathlib import Path
from time import perf_counter

from kaki_backend.orchestration.turn_pipeline import TurnPipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_malay_reply import (  # noqa: E402
    ENGLISH_QUESTION,
    ENGLISH_REPLY,
    MALAY_QUESTION,
    MALAY_RENDER,
    FakeLlm,
    FakeRetriever,
    FakeStt,
    RecordingTts,
    upload,
)


def run_with_override(transcript: str, label: str, override):
    """Execute one grounded turn; `override` is the per-device callable or None."""
    llm, tts = FakeLlm(), RecordingTts()
    pipeline = TurnPipeline(
        stt=FakeStt(transcript, label), llm=llm, tts=tts, retriever=FakeRetriever(),
        retrieval_active=True, language_preference="en", malay_reply_mode="full",
        reply_language_for=override,
    )
    execution = pipeline.execute(
        device_id="override-test", session_id="override-test", turn_id="override-turn",
        audio=upload(), audio_preparation_ms=0.0, request_started_at=perf_counter(),
    )
    return execution, llm, tts


class OverrideTests(unittest.TestCase):
    def test_ms_override_beats_an_english_transcript_and_stt(self):
        execution, llm, tts = run_with_override(ENGLISH_QUESTION, "en", lambda device: "ms")
        response, log = execution.response, execution.log
        self.assertEqual(response.language, "ms")
        self.assertEqual(response.reply_text, MALAY_RENDER)
        self.assertEqual(log.reply_language, "ms")
        self.assertEqual(log.language_override, "ms")
        self.assertEqual(len(llm.render_calls), 1)
        self.assertEqual(tts.calls[0][1], "ms")
        # Evidence is never rewritten: Whisper's label survives untouched.
        self.assertEqual(log.stt_language.language, "en")

    def test_en_override_beats_a_malay_transcript_without_rendering(self):
        execution, llm, _ = run_with_override(MALAY_QUESTION, "ms", lambda device: "en")
        self.assertEqual(execution.response.language, "en")
        self.assertEqual(execution.response.reply_text, ENGLISH_REPLY)
        self.assertEqual(execution.log.language_override, "en")
        self.assertEqual(llm.render_calls, [])
        self.assertEqual(execution.log.stt_language.language, "ms")

    def test_auto_is_identical_to_the_shipped_policy(self):
        for transcript, label in ((MALAY_QUESTION, "ms"), (ENGLISH_QUESTION, "en")):
            with self.subTest(transcript=transcript[:20]):
                baseline, _, _ = run_with_override(transcript, label, None)
                configured, _, _ = run_with_override(transcript, label, lambda device: "auto")
                self.assertEqual(configured.response.model_dump(),
                                 baseline.response.model_dump())
                self.assertIsNone(configured.log.language_override)

    def test_the_override_is_read_per_turn_with_the_device_id(self):
        seen: list[str] = []

        def override(device_id: str) -> str:
            seen.append(device_id)
            return "ms"

        run_with_override(ENGLISH_QUESTION, "en", override)
        self.assertEqual(seen, ["override-test"])

    def test_an_unexpected_store_value_falls_back_to_the_policy(self):
        execution, _, _ = run_with_override(ENGLISH_QUESTION, "en", lambda device: "zh")
        self.assertEqual(execution.response.language, "en")
        self.assertIsNone(execution.log.language_override)


if __name__ == "__main__":
    unittest.main()
