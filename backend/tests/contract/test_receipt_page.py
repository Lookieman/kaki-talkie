# v1.0 | 24-Sep-2026 | Pitch receipt page: the latest-booking endpoint over HTTP.
"""Prove the receipt page's endpoint returns the newest booking, or nothing yet.

Bookings are driven through the real turn route with a scripted transcript,
from two device IDs, so the endpoint is shown to follow whichever client
booked last. The empty case uses a fresh database, because the contract
suites share one application and another suite may already have booked.
"""

import io
import tempfile
import unittest
import wave
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from kaki_backend.actions.book_action import BOOKING_SLIPS
from kaki_backend.contracts.ports import Transcription
from kaki_backend.persistence.admin_store import AdminStore
from kaki_backend.persistence.database import Database
from kaki_test_env import CANNED_ADMIN_TOKEN, DEVICE_AUTH, canned_backend

main = canned_backend()
app = main.app

ADMIN_AUTH = {"Authorization": f"Bearer {CANNED_ADMIN_TOKEN}"}
LATEST_PATH = "/api/admin/booking/latest"


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

    def transcribe(self, audio: bytes) -> Transcription:
        return Transcription(text=self.transcript)


class LatestBookingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app, headers=DEVICE_AUTH)
        pipeline = app.state.turn_service._pipeline
        self.addCleanup(setattr, pipeline, "_stt", pipeline._stt)
        pipeline._stt = ScriptedStt("book voucher collection")

    def book(self, device_id: str) -> dict:
        response = self.client.post(
            "/api/device/turn",
            data={"device_id": device_id, "session_id": f"rcpt-{uuid4().hex[:8]}",
                  "turn_id": f"rcpt-{uuid4().hex[:8]}"},
            files={"audio": ("upload.wav", synthetic_audio(), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def latest(self) -> dict:
        response = self.client.get(LATEST_PATH, headers=ADMIN_AUTH)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_returns_the_most_recent_booking_from_any_device(self):
        self.book("kaki-pi-01")
        second = self.book("web-simulator")
        booking = self.latest()["booking"]
        self.assertEqual(booking["device_id"], "web-simulator")
        self.assertEqual(booking["case_id"], second["case_id"])
        self.assertEqual(booking["slip_text"], BOOKING_SLIPS["en"])
        self.assertTrue(booking["completed_at"])

    def test_returns_empty_before_any_booking(self):
        directory = Path(tempfile.mkdtemp(prefix="kaki-receipt-"))
        fresh = AdminStore(Database.open(directory / "kaki.db"))
        original = app.state.admin_store
        app.state.admin_store = fresh
        self.addCleanup(setattr, app.state, "admin_store", original)
        self.assertEqual(self.latest(), {"booking": None})

    def test_requires_the_admin_token(self):
        for headers in ({}, DEVICE_AUTH, {"Authorization": "Bearer wrong"}):
            with self.subTest(headers=headers):
                response = self.client.get(LATEST_PATH, headers=headers or {"Authorization": ""})
                self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
