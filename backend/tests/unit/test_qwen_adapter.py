# v1.3 | 12-Sep-2026 | Cover the SOURCE: 0 no-coverage signal and the zero/one boundary.
# v1.1 | 11-Sep-2026 | Cover grounded generation and the bounded query rewrite.
# v1.0 | 09-Sep-2026 | Verify Qwen adapter parsing, bounded failures and pipeline degradation.
"""Exercise the MLX/Qwen adapter deterministically without a model service.

Every network interaction uses an injected httpx.MockTransport, so these tests
run on any machine, including the Windows Tier A environment.
"""

import json
import unittest
from time import perf_counter

import httpx

from kaki_backend.config import APPROVED_QWEN_MODEL, LlmSettings
from kaki_backend.contracts.ports import LlmError, Transcription
from kaki_backend.orchestration.audio_lifecycle import TurnAudio
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_qwen_local.adapter import MAX_RESPONSE_BYTES, QwenLlm

URL = "http://127.0.0.1:8082"


def adapter_for(handler) -> QwenLlm:
    """Build an adapter whose HTTP layer is served by the given handler."""
    return QwenLlm(
        URL, model=APPROVED_QWEN_MODEL, timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )


def chat_response(content: str) -> httpx.Response:
    """Encode a minimal OpenAI-style chat completion payload."""
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


class QwenConstructionTest(unittest.TestCase):
    """Reject unsafe endpoints, models and timeouts before any request is made."""

    def test_rejects_non_loopback_and_malformed_urls(self):
        for url in (
            "http://192.168.1.10:8082", "https://127.0.0.1:8082", "http://localhost:8082",
            "http://127.0.0.1", "http://user:pw@127.0.0.1:8082", "http://127.0.0.1:8082/v1",
            "http://127.0.0.1:8082?x=1", "not a url",
        ):
            with self.assertRaises(ValueError, msg=url):
                QwenLlm(url, model=APPROVED_QWEN_MODEL)

    def test_rejects_blank_model_and_unbounded_timeouts(self):
        with self.assertRaises(ValueError):
            QwenLlm(URL, model="  ")
        for timeout in (0, 301, float("inf"), float("nan")):
            with self.assertRaises(ValueError, msg=timeout):
                QwenLlm(URL, model=APPROVED_QWEN_MODEL, timeout_seconds=timeout)


class QwenReadinessTest(unittest.TestCase):
    """Readiness means the approved model is resident, not merely a socket."""

    def test_ready_only_when_approved_model_listed(self):
        payloads = {
            True: {"data": [{"id": APPROVED_QWEN_MODEL}, {"id": "other"}]},
            False: {"data": [{"id": "other"}]},
        }
        for expected, payload in payloads.items():
            adapter = adapter_for(lambda request, p=payload: httpx.Response(200, json=p))
            self.assertIs(adapter.ready(), expected)

    def test_unavailable_or_malformed_server_reports_not_ready(self):
        def refuse(request):
            raise httpx.ConnectError("down")

        self.assertFalse(adapter_for(refuse).ready())
        self.assertFalse(adapter_for(lambda r: httpx.Response(500)).ready())
        self.assertFalse(adapter_for(lambda r: httpx.Response(200, json={"data": "x"})).ready())


class QwenGenerationTest(unittest.TestCase):
    """Parse successful replies and map every failure to a safe code."""

    def test_returns_trimmed_reply_and_sends_transcript_with_bounds(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return chat_response("  The centre opens at nine.  ")

        reply = adapter_for(handler).generate("What time does the centre open?")
        self.assertEqual(reply, "The centre opens at nine.")
        self.assertEqual(seen["model"], APPROVED_QWEN_MODEL)
        self.assertEqual(seen["messages"][1]["content"], "What time does the centre open?")
        self.assertIn("60 words", seen["messages"][0]["content"])
        self.assertLessEqual(seen["max_tokens"], 512)

    def test_strips_closed_think_block_and_rejects_unclosed_or_leftover(self):
        adapter = adapter_for(lambda r: chat_response("<think>silent plan</think>Reply text."))
        self.assertEqual(adapter.generate("hello"), "Reply text.")
        for bad in ("<think>never closed", "orphan</think> tail", "<think></think>  "):
            adapter = adapter_for(lambda r, b=bad: chat_response(b))
            with self.assertRaises(LlmError, msg=bad):
                adapter.generate("hello")

    def test_rejects_empty_or_oversized_transcripts_without_a_request(self):
        def handler(request):
            self.fail("No request should be sent for invalid transcripts")

        adapter = adapter_for(handler)
        for transcript in ("", "   ", "x" * 20000):
            with self.assertRaises(LlmError):
                adapter.generate(transcript)

    def test_maps_transport_failures_to_safe_codes(self):
        def refuse(request):
            raise httpx.ConnectError("down")

        def slow(request):
            raise httpx.ReadTimeout("slow")

        cases = {
            "unavailable": adapter_for(refuse),
            "timeout": adapter_for(slow),
            "invalid_response": adapter_for(lambda r: httpx.Response(200, text="not json")),
            "empty_reply": adapter_for(lambda r: chat_response("   ")),
        }
        for code, adapter in cases.items():
            with self.assertRaises(LlmError, msg=code) as raised:
                adapter.generate("hello")
            self.assertEqual(raised.exception.code, code)

    def test_rejects_error_payloads_status_failures_and_oversized_bodies(self):
        cases = [
            httpx.Response(200, json={"error": {"message": "boom"}}),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(200, json={"choices": [{"message": {"content": 5}}]}),
            httpx.Response(404),
            httpx.Response(200, content=b'"' + b"x" * MAX_RESPONSE_BYTES + b'"'),
        ]
        for response in cases:
            adapter = adapter_for(lambda r, rs=response: rs)
            with self.assertRaises(LlmError):
                adapter.generate("hello")


class QwenGroundedGenerationTest(unittest.TestCase):  #v1.1
    """Grounded generation restricts the prompt and reports the cited block."""

    def test_grounded_call_uses_the_grounded_prompt_and_bounded_reply(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return chat_response("1. Open the SMS link. 2. Spend at hawkers.\nSOURCE: 1")

        adapter_for(handler).generate_grounded(  #v1.2
            "How do I use my CDC vouchers?", evidence="[1] CDC FAQ\nClaim via SMS link.",
        )
        self.assertIn("only the official information", seen["messages"][0]["content"])
        self.assertIn("numbered steps", seen["messages"][0]["content"])
        self.assertIn("no more than 50 spoken words", seen["messages"][0]["content"])  #v1.2
        self.assertIn("SOURCE: n", seen["messages"][0]["content"])  #v1.2
        self.assertIn("Official information:\n[1] CDC FAQ", seen["messages"][1]["content"])
        self.assertIn("Question: How do I use my CDC vouchers?",
                      seen["messages"][1]["content"])

    def test_citation_is_reported_and_stripped_from_the_reply(self):  #v1.2
        adapter = adapter_for(
            lambda r: chat_response("Open the SMS link to claim.\nSOURCE: 2")
        )
        reply = adapter.generate_grounded("How do I claim?", evidence="[1] a\n\n[2] b")
        self.assertEqual(reply.text, "Open the SMS link to claim.")
        self.assertEqual(reply.cited_index, 2)

    def test_marker_variants_never_survive_into_the_spoken_text(self):  #v1.2
        # `SOURCE: 0` moved to its own test at WP3.4: it now means no coverage
        # rather than an unusable citation, so it no longer keeps its text.
        variants = {
            "Answer here.\nSOURCE: 3": 3,
            "Answer here.\nsource: 3": 3,
            "Answer here. SOURCE:3": 3,
            "Answer here.\n[SOURCE: 3]": 3,
            "Answer here.\nSOURCE - 3": 3,
            "Answer here.": None,
        }
        for raw, expected_index in variants.items():
            adapter = adapter_for(lambda r, body=raw: chat_response(body))
            reply = adapter.generate_grounded("q", evidence="[1] a")
            self.assertEqual(reply.text, "Answer here.", msg=raw)
            self.assertNotIn("SOURCE", reply.text.upper(), msg=raw)
            self.assertEqual(reply.cited_index, expected_index, msg=raw)
            self.assertFalse(reply.no_coverage, msg=raw)  #v1.3

    def test_source_zero_reports_no_coverage_and_discards_the_text(self):  #v1.3
        """Decision: a no-coverage verdict must never carry a partial answer."""
        for raw in ("SOURCE: 0", "Some half answer.\nSOURCE: 0", "[source:0]"):
            adapter = adapter_for(lambda r, body=raw: chat_response(body))
            reply = adapter.generate_grounded("q", evidence="[1] a")
            self.assertTrue(reply.no_coverage, msg=raw)
            self.assertEqual(reply.text, "", msg=raw)
            self.assertIsNone(reply.cited_index, msg=raw)

    def test_block_numbering_starts_at_one_so_zero_stays_unambiguous(self):  #v1.3
        """The off-by-one boundary: 1 is the first block, 0 is no coverage."""
        first = adapter_for(lambda r: chat_response("Answer here.\nSOURCE: 1"))
        reply = first.generate_grounded("q", evidence="[1] a")
        self.assertEqual((reply.cited_index, reply.no_coverage), (1, False))
        none = adapter_for(lambda r: chat_response("Answer here.\nSOURCE: 0"))
        self.assertTrue(none.generate_grounded("q", evidence="[1] a").no_coverage)

    def test_marker_only_reply_is_an_empty_reply_failure(self):  #v1.2
        adapter = adapter_for(lambda r: chat_response("SOURCE: 1"))
        with self.assertRaises(LlmError) as raised:
            adapter.generate_grounded("q", evidence="[1] a")
        self.assertEqual(raised.exception.code, "empty_reply")

    def test_ungrounded_generate_keeps_the_conversational_prompt(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return chat_response("The centre opens at nine.")

        adapter_for(handler).generate("What time does the centre open?")
        self.assertNotIn("official information", seen["messages"][0]["content"])

    def test_blank_or_oversized_evidence_is_rejected_without_a_request(self):
        def handler(request):
            self.fail("No request should be sent for invalid evidence")

        adapter = adapter_for(handler)
        for evidence in ("   ", "x" * 20000):
            with self.assertRaises(LlmError):
                adapter.generate_grounded("hello", evidence=evidence)  #v1.2


class QwenRewriteQueryTest(unittest.TestCase):  #v1.1
    """The rewrite is tightly bounded so callers can degrade instead of stall."""

    def test_rewrite_uses_small_completion_and_rewrite_prompt(self):
        seen = {}

        def handler(request):
            seen.update(json.loads(request.content))
            return chat_response("how to use CDC vouchers")

        query = adapter_for(handler).rewrite_query("Macam mana nak guna baucar CDC?")
        self.assertEqual(query, "how to use CDC vouchers")
        self.assertEqual(seen["max_tokens"], 32)
        self.assertIn("search query", seen["messages"][0]["content"])

    def test_rewrite_failures_map_to_safe_codes(self):
        def slow(request):
            raise httpx.ReadTimeout("slow")

        with self.assertRaises(LlmError) as raised:
            adapter_for(slow).rewrite_query("hello")
        self.assertEqual(raised.exception.code, "timeout")


class LlmSettingsTest(unittest.TestCase):
    """Environment selection keeps canned as the safe default."""

    def test_defaults_remain_canned_and_local(self):
        settings = LlmSettings.from_environment({})
        self.assertEqual(
            (settings.mode, settings.url), ("canned", "http://127.0.0.1:8082")
        )
        self.assertTrue(settings.create_port().ready())

    def test_qwen_mode_builds_the_adapter_and_invalid_values_fail(self):
        settings = LlmSettings.from_environment({"KAKI_LLM_MODE": "qwen"})
        self.assertIsInstance(settings.create_port(), QwenLlm)
        for env in (
            {"KAKI_LLM_MODE": "gpt"},
            {"KAKI_LLM_TIMEOUT_SECONDS": "0"},
            {"KAKI_LLM_TIMEOUT_SECONDS": "abc"},
        ):
            with self.assertRaises(ValueError, msg=env):
                LlmSettings.from_environment(env)


class FailingLlm:
    """Raise a controlled generation failure for pipeline tests."""

    def ready(self) -> bool:
        return True

    def generate(self, transcript: str) -> str:  #v1.2
        raise LlmError("unavailable")

    def generate_grounded(self, transcript: str, *, evidence: str):  #v1.2
        raise LlmError("unavailable")

    def rewrite_query(self, transcript: str) -> str:  #v1.1
        raise LlmError("unavailable")


class FixedStt:
    """Return a fixed transcript so pipeline tests avoid audio decoding."""

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        return Transcription(text="fixed transcript")


class RejectingTts:
    """Mimic the canned TTS refusing text it has no recording for."""

    def synthesize(self, reply_text: str) -> str | None:
        raise ValueError("no recording")


class PipelineDegradationTest(unittest.TestCase):
    """The turn stays calm when generation fails and text-only when speech does."""

    def run_turn(self, pipeline: TurnPipeline):
        """Execute one normalised-fixture turn through the real pipeline."""
        from kaki_backend.orchestration.canned_ports import canned_audio
        import base64

        audio = base64.b64decode(canned_audio("canned_reply.wav").split(",", 1)[1])
        return pipeline.execute(
            device_id="t", session_id="t", turn_id="t-1", audio=TurnAudio(audio),
            audio_preparation_ms=0.0, request_started_at=perf_counter(),
        )

    def test_llm_failure_returns_calm_failed_turn_with_safe_code(self):
        execution = self.run_turn(TurnPipeline(stt=FixedStt(), llm=FailingLlm()))
        self.assertEqual(execution.response.state.value, "failed")
        self.assertTrue(execution.response.reply_text)
        self.assertIsNone(execution.response.reply_audio)
        self.assertEqual(execution.log.llm_error, "unavailable")
        self.assertIsNotNone(execution.log.timings.llm_ms)

    def test_tts_failure_degrades_to_text_only_answer(self):
        execution = self.run_turn(TurnPipeline(stt=FixedStt(), tts=RejectingTts()))
        self.assertEqual(execution.response.state.value, "answered")
        self.assertTrue(execution.response.reply_text)
        self.assertIsNone(execution.response.reply_audio)
        self.assertIsNone(execution.log.llm_error)

    def test_canned_turn_behaviour_is_unchanged(self):
        execution = self.run_turn(TurnPipeline())
        self.assertEqual(execution.response.state.value, "answered")
        self.assertTrue(execution.response.reply_audio)


if __name__ == "__main__":
    unittest.main()
