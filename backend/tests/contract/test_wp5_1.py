# v1.0 | 13-Sep-2026 | Verify the WP5.1 debug-view fields and the unchanged nine-field response.
"""WP5.1 over the device HTTP contract with canned ports.

The response keeps its nine fields (X-AT-01; the schema snapshot test owns the
exact shape). The debug view gains the reply-language diagnostics and the
rewrite audit, read back from SQLite (migration 0003).
"""

import io
import unittest
import wave
from uuid import uuid4

from fastapi.testclient import TestClient

from kaki_test_env import DEVICE_AUTH, canned_backend

app = canned_backend().app

RESPONSE_FIELDS = {
    "turn_id", "reply_audio", "reply_text", "display_text", "slip_text",
    "language", "state", "case_id", "sources",
}
WP51_DEBUG_FIELDS = {
    "rewrite_present", "rewrite_ms", "reply_language", "reply_mode", "render_outcome",
}


def synthetic_audio() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


class Wp51DebugContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app, headers=DEVICE_AUTH)  # WP6.4

    def test_response_keeps_nine_fields_and_debug_reports_language_diagnostics(self):
        response = self.client.post(
            "/api/device/turn",
            data={"device_id": "wp51", "session_id": "wp51", "turn_id": f"wp51-{uuid4()}"},
            files={"audio": ("upload.wav", synthetic_audio(), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), RESPONSE_FIELDS)
        debug = self.client.get("/api/device/debug/last-turn").json()
        self.assertTrue(WP51_DEBUG_FIELDS <= set(debug))
        # Canned configuration: English transcript, no retrieval, no rewrite, no render.
        self.assertEqual(debug["reply_language"], "en")
        self.assertEqual(debug["reply_mode"], "full")
        self.assertIsNone(debug["render_outcome"])
        self.assertIs(debug["rewrite_present"], False)
        self.assertIsNone(debug["rewrite_ms"])


if __name__ == "__main__":
    unittest.main()
