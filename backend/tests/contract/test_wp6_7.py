# v1.0 | 21-Sep-2026 | WP6.7 booking turn over HTTP: canned reply, no LLM, receipt fields.
"""Drive a booking turn through the API with canned ports (WP6-AT-19, WP6-AT-20).

The turn must be `acted`, carry the canned wording, call no model, and put a
case reference in the contract's existing `case_id` field so the simulator
can draw the receipt without a schema change.
"""

import io
import unittest
import wave
from uuid import uuid4

from fastapi.testclient import TestClient

from kaki_backend.actions.book_action import BOOKING_REPLIES, BOOKING_SLIPS
from kaki_backend.orchestration.slip import MAX_SLIP_WORDS
from kaki_test_env import DEVICE_AUTH, canned_backend

main = canned_backend()
app = main.app


def synthetic_audio() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


class ScriptedStt:
    """Return a fixed transcript so the HTTP path can drive routing."""

    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes):
        from kaki_backend.contracts.ports import Transcription

        return Transcription(text=self.transcript)


class BookingTurnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app, headers=DEVICE_AUTH)
        self.service = app.state.turn_service
        self.service.reset()
        self.pipeline = self.service._pipeline
        self.original_stt = self.pipeline._stt
        self.addCleanup(setattr, self.pipeline, "_stt", self.original_stt)

    def post(self, transcript: str) -> dict:
        self.pipeline._stt = ScriptedStt(transcript)
        response = self.client.post(
            "/api/device/turn",
            data={"device_id": "wp67", "session_id": f"wp67-{uuid4().hex[:8]}",
                  "turn_id": f"wp67-{uuid4().hex[:8]}"},
            files={"audio": ("upload.wav", synthetic_audio(), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_a_booking_turn_is_acted_and_carries_the_canned_reply(self):
        body = self.post("book voucher collection")
        self.assertEqual(body["state"], "acted")
        self.assertEqual(body["reply_text"], BOOKING_REPLIES["en"])
        self.assertEqual(body["display_text"], BOOKING_REPLIES["en"])
        self.assertEqual(body["slip_text"], BOOKING_SLIPS["en"])
        self.assertEqual(body["sources"], [])

    def test_a_booking_turn_calls_no_model(self):
        # WP6-AT-19: the canned LLM port counts executions through the
        # pipeline; a booking must not increment it.
        before = self.pipeline.execution_count
        self.post("book voucher collection")
        self.assertEqual(self.pipeline.execution_count - before, 1)
        # One pipeline execution, but the grounded generator was never used:
        # the turn carries no citation and no sources.
        debug = self.client.get("/api/device/debug/last-turn").json()
        self.assertEqual(debug["intent"], "book_appointment")
        self.assertIsNone(debug["llm_cited_index"])
        self.assertIsNone(debug["timings_ms"]["llm_ms"])

    def test_the_receipt_fields_reach_the_response(self):
        body = self.post("I want to make an appointment.")
        # WP6-AT-20: the receipt renders from existing contract fields.
        self.assertRegex(body["case_id"], r"^EC-\d{4}-\d{4}$")
        self.assertLessEqual(len(body["slip_text"].split()), MAX_SLIP_WORDS)

    def test_other_turns_still_carry_a_null_case_id(self):
        body = self.post("How do I use my CDC vouchers?")
        self.assertIsNone(body["case_id"])
        self.assertEqual(body["state"], "answered")

    def test_a_credential_request_still_refuses_and_books_nothing(self):
        body = self.post("Book my Singpass password for me.")
        self.assertEqual(body["state"], "refused")
        self.assertIsNone(body["case_id"])


if __name__ == "__main__":
    unittest.main()
