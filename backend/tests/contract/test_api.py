# v1.2 | 05-Sep-2026 | Require versioned health and playable WP1 canned audio.
# v1.1 | 04-Sep-2026 | Isolate WP1.1 assertions from the WP1.2 memory store.
# v1.0 | 02-Sep-2026 | Verify canned HTTP behaviour and the shared turn schema.

import base64  #v1.2
import io
import unittest
import wave

from fastapi.testclient import TestClient
from pydantic import ValidationError

from kaki_backend.contracts.responses import TurnResponse
from kaki_backend.main import app


def synthetic_audio() -> bytes:
    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return audio_buffer.getvalue()


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app.state.turn_service.reset()  #v1.1
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.fields = {
            "device_id": "test-device",
            "session_id": "test-session",
            "turn_id": "test-turn",
        }
        self.audio = synthetic_audio()

    def post_turn(self, fields: dict[str, str], audio: bytes):
        return self.client.post(
            "/api/device/turn",
            data=fields,
            files={"audio": ("synthetic.wav", audio, "audio/wav")},
        )

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "version": app.version})  #v1.2
        self.assertTrue(response.json()["version"])  #v1.2

    def test_canned_turn_contract(self) -> None:
        response = self.post_turn(self.fields, self.audio)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(
            set(result),
            {
                "turn_id",
                "reply_audio",
                "reply_text",
                "display_text",
                "slip_text",
                "language",
                "state",
                "case_id",
                "sources",
            },
        )
        TurnResponse.model_validate(result)
        self.assertEqual(result["turn_id"], "test-turn")
        self.assertEqual(result["state"], "answered")
        self.assertEqual(result["language"], "en")
        self.assertIn("test reply", result["reply_text"])
        self.assertTrue(result["display_text"])
        self.assertIn("sample English slip", result["slip_text"])
        self.assertTrue(result["reply_audio"].startswith("data:audio/wav;base64,"))  #v1.2
        audio = base64.b64decode(result["reply_audio"].split(",", 1)[1], validate=True)  #v1.2
        with wave.open(io.BytesIO(audio), "rb") as recording:  #v1.2
            self.assertEqual(recording.getcomptype(), "NONE")  #v1.2
            self.assertGreater(recording.getnframes(), recording.getframerate())  #v1.2
        self.assertIsNone(result["case_id"])
        self.assertEqual(result["sources"], [])

    def test_retry_is_deterministic(self) -> None:
        first = self.post_turn(self.fields, self.audio)
        retry = self.post_turn(self.fields, self.audio)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(first.json(), retry.json())

    def test_each_turn_echoes_its_own_identifier(self) -> None:
        for turn_id in ("first-test-turn", "second-test-turn"):
            with self.subTest(turn_id=turn_id):
                fields = {**self.fields, "turn_id": turn_id}
                response = self.post_turn(fields, self.audio)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["turn_id"], turn_id)

    def test_missing_identifiers_are_rejected(self) -> None:
        for field in self.fields:
            with self.subTest(field=field):
                fields = self.fields.copy()
                del fields[field]
                response = self.post_turn(fields, self.audio)
                self.assertEqual(response.status_code, 422)
                locations = [error["loc"] for error in response.json()["detail"]]
                self.assertIn(["body", field], locations)

    def test_blank_identifiers_are_rejected(self) -> None:
        for field in self.fields:
            for value in ("", "   "):
                with self.subTest(field=field, value=value):
                    fields = {**self.fields, field: value}
                    response = self.post_turn(fields, self.audio)
                    self.assertEqual(response.status_code, 422)

    def test_missing_audio_is_rejected(self) -> None:
        response = self.client.post("/api/device/turn", data=self.fields)
        self.assertEqual(response.status_code, 422)
        locations = [error["loc"] for error in response.json()["detail"]]
        self.assertIn(["body", "audio"], locations)

    def test_empty_audio_returns_failed_turn(self) -> None:
        response = self.post_turn(self.fields, b"")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        TurnResponse.model_validate(result)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["turn_id"], "test-turn")
        self.assertIn("try recording again", result["reply_text"])
        self.assertEqual(result["slip_text"], "")
        self.assertEqual(result["sources"], [])

    def test_json_is_not_accepted_as_an_audio_upload(self) -> None:
        response = self.client.post(
            "/api/device/turn", json={**self.fields, "audio": "not-an-upload"}
        )
        self.assertEqual(response.status_code, 422)

    def test_openapi_requires_the_multipart_contract(self) -> None:
        schema = self.client.get("/openapi.json").json()
        operation = schema["paths"]["/api/device/turn"]["post"]
        request_body = operation["requestBody"]
        self.assertTrue(request_body["required"])
        self.assertEqual(set(request_body["content"]), {"multipart/form-data"})
        reference = request_body["content"]["multipart/form-data"]["schema"]["$ref"]
        request_schema = schema["components"]["schemas"][reference.rsplit("/", 1)[1]]
        self.assertEqual(
            set(request_schema["required"]),
            {"audio", "device_id", "session_id", "turn_id"},
        )
        audio_schema = request_schema["properties"]["audio"]
        self.assertEqual(audio_schema["type"], "string")
        self.assertTrue(
            audio_schema.get("format") == "binary"
            or audio_schema.get("contentMediaType") == "application/octet-stream"
        )
        self.assertEqual(
            set(schema["components"]["schemas"]["TurnState"]["enum"]),
            {"answered", "refused", "handed_off", "acted", "failed"},
        )

    def test_response_rejects_undocumented_state(self) -> None:
        result = self.post_turn(self.fields, self.audio).json()
        result["state"] = "invented-state"
        with self.assertRaises(ValidationError):
            TurnResponse.model_validate(result)


if __name__ == "__main__":
    unittest.main()
