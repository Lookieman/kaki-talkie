# v1.2 | 12-Sep-2026 | Expect the domain-only slip source line.
# v1.1 | 12-Sep-2026 | Cover cited-source attribution and the owner-reported mis-attribution.
# v1.0 | 11-Sep-2026 | Cover grounded retrieval wiring, rewrite guards and provenance.
"""Pipeline-level grounded behaviour with fake ports; no models or network.

Covers the WP3.3 mechanics: evidence flows into generation, sources and the
slip derive only from application metadata, the normalised-query rewrite is
guarded and degrades silently, retrieval timings are scoped by mode, and a
broken evidence store fails the turn instead of answering ungrounded.
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
    LlmError,
    Transcription,
)
from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.orchestration.turn_pipeline import TurnPipeline

CDC_SOURCE = SourceRecord(
    source_url="https://vouchers.cdc.gov.sg/residents/faq",
    page_title="CDC Vouchers FAQ",
    captured_at=datetime(2026, 9, 10, 11, 6, 44, tzinfo=timezone.utc),
)
EVIDENCE = (
    EvidenceChunk(
        chunk_id="chunk-1", source_id="cdc-vouchers-residents",
        heading_path=("Claiming vouchers",),
        text="Households claim CDC Vouchers through the SMS link.",
        source=CDC_SOURCE, fused_score=0.05, dense_score=0.8, lexical_score=5.2,
    ),
    EvidenceChunk(
        chunk_id="chunk-2", source_id="cdc-vouchers-residents",
        heading_path=("Spending",),
        text="Vouchers are spent at participating hawkers and merchants.",
        source=CDC_SOURCE, fused_score=0.04, dense_score=0.7, lexical_score=None,
    ),
)


def synthetic_audio() -> bytes:
    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return audio_buffer.getvalue()


class FakeStt:
    """Return a fixed transcript with configurable language evidence."""

    def __init__(self, text: str, language: str | None = "en") -> None:
        self._result = Transcription(
            text=text,
            evidence=LanguageEvidence(language=language) if language else None,
        )

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        return self._result


class FakeLlm:
    """Record grounded-generation and rewrite calls; reply with numbered steps."""

    def __init__(self, rewrite_fails: bool = False, reply: str | None = None,
                 cited_index: int | None = None) -> None:
        self.generate_calls: list[tuple[str, str | None]] = []
        self.rewrite_calls: list[str] = []
        self._rewrite_fails = rewrite_fails
        self._reply = reply or "1. Open the SMS link. 2. Choose the amount. 3. Show the code."
        self._cited_index = cited_index

    def ready(self) -> bool:
        return True

    def generate(self, transcript: str) -> str:
        self.generate_calls.append((transcript, None))
        return self._reply

    def generate_grounded(self, transcript: str, *, evidence: str) -> GroundedReply:
        self.generate_calls.append((transcript, evidence))
        return GroundedReply(text=self._reply, cited_index=self._cited_index)

    def rewrite_query(self, transcript: str) -> str:
        self.rewrite_calls.append(transcript)
        if self._rewrite_fails:
            raise LlmError("timeout")
        return "how to use CDC vouchers"


class FakeRetriever:
    """Return the fixed evidence and record the queries retrieval received."""

    def __init__(self, evidence=EVIDENCE) -> None:
        self._evidence = evidence
        self.queries: list[tuple[str, str | None]] = []

    def ready(self) -> bool:
        return True

    def retrieve(self, original_query, normalized_query):
        self.queries.append((original_query, normalized_query))
        return self._evidence


class BrokenRetriever:
    """Fail every retrieval like an unusable evidence store."""

    def ready(self) -> bool:
        return False

    def retrieve(self, original_query, normalized_query):
        raise RuntimeError("store unavailable")


def execute(pipeline: TurnPipeline):
    return pipeline.execute(
        device_id="grounded-test", session_id="grounded-test",
        turn_id="grounded-test-turn", audio=synthetic_audio(),
        audio_preparation_ms=0.0, request_started_at=perf_counter(),
    )


def grounded_pipeline(transcript: str, language: str | None = "en", **kwargs):
    llm = kwargs.pop("llm", FakeLlm())
    retriever = kwargs.pop("retriever", FakeRetriever())
    pipeline = TurnPipeline(
        stt=FakeStt(transcript, language), llm=llm, retriever=retriever,
        retrieval_active=True, **kwargs,
    )
    return pipeline, llm, retriever


class GroundedTurnTests(unittest.TestCase):
    """Evidence grounds generation; provenance reaches the response and slip."""

    def test_answer_carries_deduplicated_application_sources(self):
        pipeline, _, _ = grounded_pipeline("How do I use my CDC vouchers?")
        response = execute(pipeline).response
        self.assertEqual(response.state.value, "answered")
        self.assertEqual(len(response.sources), 1)
        self.assertEqual(response.sources[0].source_url, CDC_SOURCE.source_url)
        self.assertEqual(response.sources[0].captured_at, CDC_SOURCE.captured_at)

    def test_evidence_text_reaches_generation(self):
        pipeline, llm, _ = grounded_pipeline("How do I use my CDC vouchers?")
        execute(pipeline)
        transcript, evidence = llm.generate_calls[0]
        self.assertIn("SMS link", evidence)
        self.assertIn("[1] CDC Vouchers FAQ - Claiming vouchers", evidence)

    def test_slip_derives_from_answer_and_metadata(self):
        pipeline, _, _ = grounded_pipeline("How do I use my CDC vouchers?")
        response = execute(pipeline).response
        self.assertIn("Source checked: 10-Sep-2026", response.slip_text)
        self.assertIn("Source: vouchers.cdc.gov.sg", response.slip_text)  #v1.2
        self.assertNotIn("CDC Vouchers FAQ", response.slip_text)  #v1.2
        self.assertNotIn("http", response.slip_text)
        self.assertLessEqual(len(response.slip_text.split()), 40)

    def test_retrieval_and_evidence_are_logged_for_debug(self):
        pipeline, _, _ = grounded_pipeline("How do I use my CDC vouchers?")
        log = execute(pipeline).log
        self.assertGreater(log.timings.retrieval_ms, 0)
        self.assertEqual(len(log.retrieval_evidence), 2)
        self.assertEqual(log.retrieval_evidence[0].dense_score, 0.8)
        self.assertEqual(log.retrieval_evidence[0].lexical_score, 5.2)


SINGPASS_SOURCE = SourceRecord(
    source_url="https://ask.gov.sg/singpass/questions/reset",
    page_title="I forgot my Singpass password. How do I reset it?",
    captured_at=datetime(2026, 9, 10, 11, 6, 44, tzinfo=timezone.utc),
)
# The owner-reported case: the CDC FAQ ranks first for a Singpass question
# because it has its own "forgot my Singpass password" section, but the answer
# is drawn from the Singpass page at rank two.
MISRANKED_EVIDENCE = (
    EvidenceChunk(
        chunk_id="chunk-cdc", source_id="cdc-vouchers-residents",
        heading_path=("CDC Vouchers FAQ", "I have problems with my Singpass account"),
        text="If you have problems with Singpass, visit the Singpass website for help.",
        source=CDC_SOURCE, fused_score=0.0325, dense_score=0.70, lexical_score=4.0,
    ),
    EvidenceChunk(
        chunk_id="chunk-singpass", source_id="singpass-support",
        heading_path=("I have forgotten my Singpass password",),
        text="Visit the Singpass Portal. Select 'Services' on the top scroll bar. "
             "Select 'Reset password'. Enter your NRIC or FIN details.",
        source=SINGPASS_SOURCE, fused_score=0.0325, dense_score=0.69, lexical_score=4.1,
    ),
)
SINGPASS_ANSWER = ("1. Visit the Singpass Portal. 2. Select 'Services' on the top scroll "
                   "bar. 3. Select 'Reset password'.")


class CitedSourceAttributionTests(unittest.TestCase):
    """The answer's own source leads, not whatever retrieval ranked first."""

    def build(self, cited_index):
        llm = FakeLlm(reply=SINGPASS_ANSWER, cited_index=cited_index)
        pipeline = TurnPipeline(
            stt=FakeStt("How do I reset my Singpass password?"), llm=llm,
            retriever=FakeRetriever(MISRANKED_EVIDENCE), retrieval_active=True,
        )
        return execute(pipeline)

    def test_model_citation_selects_the_source_over_rank_one(self):
        response = self.build(cited_index=2).response
        self.assertEqual(response.sources[0].source_url, SINGPASS_SOURCE.source_url)
        self.assertIn("ask.gov.sg", response.slip_text)
        self.assertNotIn("vouchers.cdc.gov.sg", response.slip_text)

    def test_missing_citation_falls_back_to_word_overlap_not_rank_one(self):
        response = self.build(cited_index=None).response
        self.assertEqual(response.sources[0].source_url, SINGPASS_SOURCE.source_url)
        self.assertNotIn("vouchers.cdc.gov.sg", response.slip_text)

    def test_out_of_range_citation_is_ignored_and_falls_back(self):
        response = self.build(cited_index=99).response
        self.assertEqual(response.sources[0].source_url, SINGPASS_SOURCE.source_url)

    def test_all_retrieved_sources_are_retained_as_consulted_evidence(self):
        response = self.build(cited_index=2).response
        urls = [record.source_url for record in response.sources]
        self.assertEqual(len(urls), 2)
        self.assertIn(CDC_SOURCE.source_url, urls)

    def test_log_keeps_retrieval_rank_order_for_turn_sources(self):
        log = self.build(cited_index=2).log
        self.assertEqual(
            [(item.source_id, item.retrieval_rank) for item in log.retrieval_evidence],
            [("cdc-vouchers-residents", 1), ("singpass-support", 2)],
        )
        self.assertEqual([item.cited for item in log.retrieval_evidence], [False, True])
        self.assertEqual(log.cited_source_id, "singpass-support")
        self.assertEqual(log.llm_cited_index, 2)


class RewriteGuardTests(unittest.TestCase):
    """The rewrite runs only when useful and never fails the turn."""

    def test_short_english_transcript_skips_the_rewrite(self):
        pipeline, llm, retriever = grounded_pipeline("How do I use my CDC vouchers?")
        log = execute(pipeline).log
        self.assertEqual(llm.rewrite_calls, [])
        self.assertIsNone(log.timings.query_rewrite_ms)
        self.assertEqual(retriever.queries[0][1], None)

    def test_non_english_evidence_triggers_the_rewrite(self):
        pipeline, llm, retriever = grounded_pipeline(
            "Macam mana nak guna baucar CDC saya?", language="ms"
        )
        log = execute(pipeline).log
        self.assertEqual(len(llm.rewrite_calls), 1)
        self.assertEqual(retriever.queries[0][1], "how to use CDC vouchers")
        self.assertEqual(log.normalised_query, "how to use CDC vouchers")
        self.assertGreater(log.timings.query_rewrite_ms, 0)

    def test_long_english_transcript_triggers_the_rewrite(self):
        long_question = " ".join(["word"] * 20)
        pipeline, llm, _ = grounded_pipeline(long_question)
        execute(pipeline)
        self.assertEqual(len(llm.rewrite_calls), 1)

    def test_rewrite_failure_degrades_to_original_only(self):
        pipeline, llm, retriever = grounded_pipeline(
            "Macam mana nak guna baucar CDC saya?", language="ms",
            llm=FakeLlm(rewrite_fails=True),
        )
        response = execute(pipeline).response
        self.assertEqual(response.state.value, "answered")
        self.assertEqual(retriever.queries[0][1], None)

    def test_normalise_off_never_rewrites(self):
        llm = FakeLlm()
        pipeline = TurnPipeline(
            stt=FakeStt("Macam mana nak guna baucar CDC?", "ms"), llm=llm,
            retriever=FakeRetriever(), retrieval_active=True, query_normalise=False,
        )
        execute(pipeline)
        self.assertEqual(llm.rewrite_calls, [])


class RetrievalScopingTests(unittest.TestCase):
    """Inactive retrieval keeps WP1/WP2 behaviour; a broken store fails safely."""

    def test_inactive_retrieval_keeps_timings_null_and_sample_slip(self):
        llm, retriever = FakeLlm(), FakeRetriever()
        pipeline = TurnPipeline(
            stt=FakeStt("How do I use my CDC vouchers?"), llm=llm, retriever=retriever,
        )
        execution = execute(pipeline)
        self.assertIsNone(execution.log.timings.retrieval_ms)
        self.assertIsNone(execution.log.timings.query_rewrite_ms)
        self.assertEqual(retriever.queries, [])
        self.assertEqual(execution.response.sources, [])
        self.assertIn("KAKI-TALKIE TEST", execution.response.slip_text)
        self.assertEqual(llm.generate_calls[0][1], None)

    def test_broken_store_fails_the_turn_instead_of_answering_ungrounded(self):
        llm = FakeLlm()
        pipeline = TurnPipeline(
            stt=FakeStt("How do I use my CDC vouchers?"), llm=llm,
            retriever=BrokenRetriever(), retrieval_active=True,
        )
        execution = execute(pipeline)
        self.assertEqual(execution.response.state.value, "failed")
        self.assertEqual(execution.log.retrieval_error, "unavailable")
        self.assertEqual(llm.generate_calls, [])


if __name__ == "__main__":
    unittest.main()
