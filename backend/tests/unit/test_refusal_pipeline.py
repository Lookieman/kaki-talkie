# v1.1 | 12-Sep-2026 | Drop the redaction test; three refusal layers remain.
# v1.0 | 12-Sep-2026 | Cover the WP3.4 refusal layers end to end with fake ports.
"""Pipeline-level refusal behaviour with fake ports; no models or network.

Covers the three WP3.4 layers in the order the pipeline applies them, plus the
properties the owner gate depends on: a refused turn carries no sources and no
provenance on its slip, generation is not called once the evidence gate has
refused, and the canned configuration keeps its WP1/WP2 behaviour.
"""

import io
import unittest
import wave
from datetime import datetime, timezone
from time import perf_counter

from kaki_backend.contracts.ports import (
    EvidenceChunk,
    GroundedReply,
    LanguageEvidence,
    Transcription,
)
from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.orchestration.intent_router import RefusalReason, refusal_message
from kaki_backend.orchestration.turn_pipeline import TurnPipeline

CDC_SOURCE = SourceRecord(
    source_url="https://vouchers.cdc.gov.sg/residents/",
    page_title="CDC Vouchers for residents",
    captured_at=datetime(2026, 9, 10, 11, 6, 44, tzinfo=timezone.utc),
)


def evidence_scoring(dense: float | None, lexical: float | None = 4.0):
    """Build one evidence chunk whose dense score the gate will judge."""
    return (
        EvidenceChunk(
            chunk_id="chunk-1", source_id="cdc-vouchers-residents",
            heading_path=("Claiming vouchers",),
            text="Households claim CDC Vouchers through the SMS link.",
            source=CDC_SOURCE, fused_score=0.0325,
            dense_score=dense, lexical_score=lexical,
        ),
    )


def synthetic_audio() -> bytes:
    """Build a short valid PCM upload so normalisation succeeds."""
    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return audio_buffer.getvalue()


class FakeStt:
    """Return a fixed transcript with English language evidence."""

    def __init__(self, text: str) -> None:
        self._result = Transcription(
            text=text, evidence=LanguageEvidence(language="en")
        )

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        return self._result


class RecordingLlm:
    """Record every call so a test can prove generation did not happen."""

    def __init__(self, no_coverage: bool = False, reply: str | None = None) -> None:
        self.grounded_calls: list[str] = []
        self.plain_calls: list[str] = []
        self.rewrite_calls: list[str] = []
        self._no_coverage = no_coverage
        self._reply = reply or "1. Open the SMS link. 2. Show the code."

    def ready(self) -> bool:
        return True

    def generate(self, transcript: str) -> str:
        self.plain_calls.append(transcript)
        return self._reply

    def generate_grounded(self, transcript: str, *, evidence: str) -> GroundedReply:
        self.grounded_calls.append(transcript)
        if self._no_coverage:
            return GroundedReply(text="", cited_index=None, no_coverage=True)
        return GroundedReply(text=self._reply, cited_index=1)

    def rewrite_query(self, transcript: str) -> str:
        self.rewrite_calls.append(transcript)
        return "normalised query"


class FakeRetriever:
    """Return fixed evidence and record what retrieval was asked for."""

    def __init__(self, evidence) -> None:
        self._evidence = evidence
        self.queries: list[tuple[str, str | None]] = []

    def ready(self) -> bool:
        return True

    def retrieve(self, original_query, normalized_query):
        self.queries.append((original_query, normalized_query))
        return self._evidence


class SilentTts:
    """Accept any text; speech content is not what these tests assert."""

    def ready(self) -> bool:
        return True

    def synthesize(self, reply_text: str) -> str | None:
        return "data:audio/wav;base64,AAAA"


def run(transcript: str, *, evidence=None, llm=None, retrieval_active=True,
        evidence_min_dense=0.50):
    """Execute one turn and return its execution record plus the fake ports."""
    llm = llm or RecordingLlm()
    retriever = FakeRetriever(evidence if evidence is not None else evidence_scoring(0.80))
    pipeline = TurnPipeline(
        stt=FakeStt(transcript), llm=llm, tts=SilentTts(), retriever=retriever,
        retrieval_active=retrieval_active, evidence_min_dense=evidence_min_dense,
    )
    execution = pipeline.execute(
        device_id="refusal-test", session_id="refusal-test", turn_id="refusal-test-turn",
        audio=synthetic_audio(), audio_preparation_ms=0.0,
        request_started_at=perf_counter(),
    )
    return execution, llm, retriever


class CredentialActionTests(unittest.TestCase):
    """Layer 1 refuses before retrieval or generation run at all."""

    def test_credential_action_refuses_without_retrieval_or_generation(self):
        execution, llm, retriever = run("Log in to my Singpass for me")
        self.assertEqual(execution.response.state.value, "refused")
        self.assertEqual(execution.log.refusal_reason, "credential_action")
        self.assertEqual(execution.log.intent, "refuse")
        self.assertEqual(retriever.queries, [])
        self.assertEqual(llm.grounded_calls, [])
        self.assertEqual(llm.plain_calls, [])
        self.assertIsNone(execution.log.timings.retrieval_ms)
        self.assertIsNone(execution.log.timings.llm_ms)

    def test_credential_rules_apply_without_retrieval_configured(self):
        # Layer 1 is a safety rule, not a retrieval feature (WP2 config).
        execution, _, _ = run("Log in to my Singpass for me", retrieval_active=False)
        self.assertEqual(execution.response.state.value, "refused")
        self.assertEqual(execution.log.refusal_reason, "credential_action")


class EvidenceGateTests(unittest.TestCase):
    """Layer 2 refuses on weak evidence, and only on weak evidence."""

    def test_score_above_the_gate_answers_and_generates(self):
        execution, llm, _ = run("How do I use my CDC vouchers?",
                                evidence=evidence_scoring(0.76))
        self.assertEqual(execution.response.state.value, "answered")
        self.assertEqual(len(llm.grounded_calls), 1)
        self.assertEqual(execution.log.best_dense_score, 0.76)

    def test_score_below_the_gate_refuses_without_generating(self):
        execution, llm, _ = run("What is the weather forecast for tomorrow?",
                                evidence=evidence_scoring(0.24))
        self.assertEqual(execution.response.state.value, "refused")
        self.assertEqual(execution.log.refusal_reason, "no_coverage")
        self.assertEqual(llm.grounded_calls, [])
        self.assertEqual(execution.log.best_dense_score, 0.24)
        self.assertGreater(execution.log.timings.retrieval_ms, 0)

    def test_the_boundary_value_itself_answers(self):
        # The gate refuses strictly below the threshold, so an exact match
        # is coverage; a re-tune therefore has no ambiguous midpoint.
        above, _, _ = run("q", evidence=evidence_scoring(0.50))
        self.assertEqual(above.response.state.value, "answered")

    def test_empty_evidence_and_missing_dense_scores_refuse(self):
        for evidence in ((), evidence_scoring(None)):
            execution, llm, _ = run("q", evidence=evidence)
            self.assertEqual(execution.response.state.value, "refused")
            self.assertEqual(execution.log.refusal_reason, "no_coverage")
            self.assertIsNone(execution.log.best_dense_score)
            self.assertEqual(llm.grounded_calls, [])

    def test_threshold_is_recorded_beside_the_score_it_judged(self):
        execution, _, _ = run("q", evidence=evidence_scoring(0.31),
                              evidence_min_dense=0.30)
        self.assertEqual(execution.response.state.value, "answered")
        self.assertEqual(execution.log.evidence_min_dense, 0.30)
        self.assertEqual(execution.log.best_dense_score, 0.31)

    def test_canned_retrieval_never_refuses_for_coverage(self):
        # WP1/WP2 behaviour is preserved: no retrieval, no gate, no refusal.
        execution, llm, _ = run("What is the weather forecast for tomorrow?",
                                retrieval_active=False)
        self.assertEqual(execution.response.state.value, "answered")
        self.assertIsNone(execution.log.refusal_reason)
        self.assertIsNone(execution.log.best_dense_score)
        self.assertIsNone(execution.log.evidence_min_dense)
        self.assertEqual(len(llm.plain_calls), 1)


class ModelNoCoverageTests(unittest.TestCase):
    """Layer 3 refuses on the model's own signal and discards its text."""

    def test_source_zero_refuses_and_speaks_the_fixed_wording(self):
        execution, llm, _ = run(
            "How much Medisave can I use?", evidence=evidence_scoring(0.62),
            llm=RecordingLlm(no_coverage=True),
        )
        response = execution.response
        self.assertEqual(response.state.value, "refused")
        self.assertEqual(execution.log.refusal_reason, "no_coverage")
        self.assertEqual(len(llm.grounded_calls), 1)
        self.assertEqual(
            response.reply_text, refusal_message(RefusalReason.NO_COVERAGE).reply_text
        )


class RefusedTurnShapeTests(unittest.TestCase):
    """What a refused turn must and must not contain."""

    def test_refused_turn_has_fixed_wording_audio_and_no_sources(self):
        execution, _, _ = run("What is the weather forecast for tomorrow?",
                              evidence=evidence_scoring(0.24))
        response = execution.response
        expected = refusal_message(RefusalReason.NO_COVERAGE)
        self.assertEqual(response.reply_text, expected.reply_text)
        self.assertEqual(response.display_text, expected.display_text)
        self.assertEqual(response.sources, [])
        self.assertIsNone(response.case_id)
        self.assertEqual(response.language, "en")
        # Speech still happens: a refusal must be heard, not read.
        self.assertIsNotNone(response.reply_audio)

    def test_refusal_slip_claims_no_source_and_no_checked_date(self):
        execution, _, _ = run("What is the weather forecast for tomorrow?",
                              evidence=evidence_scoring(0.24))
        slip = execution.response.slip_text
        self.assertTrue(slip.strip())
        self.assertNotIn("Source:", slip)
        self.assertNotIn("Source checked", slip)
        self.assertNotIn("http", slip)
        self.assertLessEqual(len(slip.split()), 40)
        self.assertIn("staff member", slip)
        self.assertIn("weather forecast", slip)

    def test_a_very_long_question_is_omitted_rather_than_cut_short(self):
        question = " ".join(["voucher"] * 60) + "?"
        execution, _, _ = run(question, evidence=evidence_scoring(0.24))
        slip = execution.response.slip_text
        self.assertLessEqual(len(slip.split()), 40)
        self.assertNotIn("You asked:", slip)
        self.assertIn("staff member", slip)


if __name__ == "__main__":
    unittest.main()
