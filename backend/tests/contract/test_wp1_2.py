# v1.2 | 06-Sep-2026 | Use valid PCM input while preserving the earlier port assertions.
# v1.1 | 04-Sep-2026 | Prove the canned pipeline executes through injected ports.
# v1.0 | 04-Sep-2026 | Verify WP1.2 idempotency, timing and pending semantics.

"""Preserve WP1 acceptance assertions with valid audio inputs for WP2.1."""  #v1.2
import io
from time import perf_counter  #v1.1
import unittest
import wave

from fastapi.testclient import TestClient

from kaki_backend.main import app
from kaki_backend.orchestration.turn_pipeline import TurnPipeline  #v1.1


def synthetic_audio() -> bytes:
    """Build a short valid PCM upload without using personal recordings."""  #v1.2
    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return audio_buffer.getvalue()


class Wp12ContractTests(unittest.TestCase):
    """Provide deterministic Wp12ContractTests behaviour for contract tests."""  #v1.2
    def setUp(self) -> None:
        """Reset application state and create an isolated HTTP test client."""  #v1.2
        app.state.turn_service.reset()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.fields = {
            "device_id": "wp12-device",
            "session_id": "wp12-session",
            "turn_id": "wp12-turn",
        }

    def post_turn(self, audio: bytes):
        """Submit an audio fixture through the unchanged multipart contract."""  #v1.2
        return self.client.post(
            "/api/device/turn",
            data=self.fields,
            files={"audio": ("synthetic.wav", audio, "audio/wav")},
        )

    def test_same_turn_id_returns_first_result_and_executes_once(self) -> None:
        """Verify same turn id returns first result and executes once."""  #v1.2
        first = self.post_turn(synthetic_audio())
        retry_with_changed_content = self.post_turn(b"")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry_with_changed_content.status_code, 200)
        self.assertEqual(retry_with_changed_content.json(), first.json())
        self.assertEqual(app.state.turn_service.execution_count, 1)
        self.assertEqual(len(app.state.turn_service.logs), 1)

    def test_empty_audio_is_a_calm_failed_turn(self) -> None:
        """Verify empty audio is a calm failed turn."""  #v1.2
        response = self.post_turn(b"")

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["state"], "failed")
        self.assertTrue(result["reply_text"])
        self.assertIn("try recording again", result["reply_text"])

    def test_pending_returns_empty_well_formed_list(self) -> None:
        """Verify pending returns empty well formed list."""  #v1.2
        response = self.client.get("/api/device/pending")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_answered_turn_log_has_complete_timing_shape(self) -> None:
        """Verify answered turn log has complete timing shape."""  #v1.2
        response = self.post_turn(synthetic_audio())

        self.assertEqual(response.status_code, 200)
        timing = app.state.turn_service.logs[0].timings.model_dump()
        self.assertEqual(
            set(timing),
            {
                "audio_preparation_ms",
                "stt_ms",
                "routing_ms",
                "retrieval_ms",
                "live_lookup_ms",
                "llm_ms",
                "tts_ms",
                "overall_ms",
                "time_to_first_audio_ms",
            },
        )
        for stage in (
            "audio_preparation_ms",
            "stt_ms",
            "routing_ms",
            "llm_ms",
            "tts_ms",
            "overall_ms",
        ):
            self.assertIsInstance(timing[stage], float)
            self.assertGreaterEqual(timing[stage], 0)
        for stage in ("retrieval_ms", "live_lookup_ms", "time_to_first_audio_ms"):
            self.assertIsNone(timing[stage])

    def test_failed_turn_leaves_uninvoked_stage_timings_null(self) -> None:
        """Verify failed turn leaves uninvoked stage timings null."""  #v1.2
        response = self.post_turn(b"")

        self.assertEqual(response.status_code, 200)
        timing = app.state.turn_service.logs[0].timings.model_dump()
        self.assertIsInstance(timing["audio_preparation_ms"], float)
        self.assertIsInstance(timing["overall_ms"], float)
        for stage in (
            "stt_ms",
            "routing_ms",
            "retrieval_ms",
            "live_lookup_ms",
            "llm_ms",
            "tts_ms",
            "time_to_first_audio_ms",
        ):
            self.assertIsNone(timing[stage])

    def test_answered_pipeline_uses_ports_without_retrieval(self) -> None:  #v1.1
        """Verify answered pipeline uses ports without retrieval."""  #v1.2
        calls = {"stt": 0, "llm": 0, "tts": 0, "retriever": 0}  #v1.1

        class SttSpy:  #v1.1
            """Provide deterministic SttSpy behaviour for contract tests."""  #v1.2
            def transcribe(self, audio: bytes) -> str:  #v1.1
                """Record invocation and return a deterministic test transcript."""  #v1.2
                calls["stt"] += 1  #v1.1
                return "canned transcript"  #v1.1

        class LlmSpy:  #v1.1
            """Provide deterministic LlmSpy behaviour for contract tests."""  #v1.2
            def generate(self, transcript: str) -> str:  #v1.1
                """Record invocation and return deterministic reply text."""  #v1.2
                calls["llm"] += 1  #v1.1
                return "canned reply"  #v1.1

        class TtsSpy:  #v1.1
            """Provide deterministic TtsSpy behaviour for contract tests."""  #v1.2
            def synthesize(self, reply_text: str) -> str | None:  #v1.1
                """Record invocation without generating real audio."""  #v1.2
                calls["tts"] += 1  #v1.1
                return None  #v1.1

        class RetrieverSpy:  #v1.1
            """Provide deterministic RetrieverSpy behaviour for contract tests."""  #v1.2
            def retrieve(self, original_query: str, normalized_query: str | None):  #v1.1
                """Record any unexpected retrieval invocation."""  #v1.2
                calls["retriever"] += 1  #v1.1
                return ()  #v1.1

        pipeline = TurnPipeline(  #v1.1
            stt=SttSpy(),  #v1.1
            llm=LlmSpy(),  #v1.1
            tts=TtsSpy(),  #v1.1
            retriever=RetrieverSpy(),  #v1.1
        )
        execution = pipeline.execute(  #v1.1
            device_id="port-device",  #v1.1
            session_id="port-session",  #v1.1
            turn_id="port-turn",  #v1.1
            audio=synthetic_audio(),  #v1.2
            audio_preparation_ms=0.0,  #v1.1
            request_started_at=perf_counter(),  #v1.1
        )

        self.assertEqual(execution.response.state, "answered")  #v1.1
        self.assertEqual(execution.response.reply_text, "canned reply")  #v1.1
        self.assertEqual(  #v1.1
            calls, {"stt": 1, "llm": 1, "tts": 1, "retriever": 0}  #v1.1
        )


if __name__ == "__main__":
    unittest.main()
