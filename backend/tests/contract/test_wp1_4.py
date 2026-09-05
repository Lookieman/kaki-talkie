# v1.0 | 05-Sep-2026 | Verify WP1 deployment defaults and packaged spoken fixtures.

import base64  #v1.0
import io  #v1.0
import json  #v1.0
import unittest  #v1.0
import wave  #v1.0
from importlib.resources import files  #v1.0
from pathlib import Path  #v1.0
from unittest.mock import patch  #v1.0

from fastapi.testclient import TestClient  #v1.0

from kaki_backend.main import app, run  #v1.0
from kaki_backend.orchestration.canned_ports import CannedTtsPort, canned_audio  #v1.0


class Wp14ContractTests(unittest.TestCase):  #v1.0
    def setUp(self) -> None:  #v1.0
        app.state.turn_service.reset()  #v1.0
        self.client = TestClient(app)  #v1.0
        self.addCleanup(self.client.close)  #v1.0

    def post_turn(self, turn_id: str, audio: bytes) -> dict:  #v1.0
        response = self.client.post(  #v1.0
            "/api/device/turn",  #v1.0
            data={"device_id": "wp14", "session_id": "wp14", "turn_id": turn_id},  #v1.0
            files={"audio": ("synthetic.wav", audio, "audio/wav")},  #v1.0
        )  #v1.0
        self.assertEqual(response.status_code, 200)  #v1.0
        return response.json()  #v1.0

    def test_launcher_uses_loopback_even_with_uvicorn_environment(self) -> None:  #v1.0
        with patch.dict("os.environ", {"UVICORN_HOST": "0.0.0.0", "UVICORN_PORT": "9000"}):  #v1.0
            with patch("uvicorn.run") as server:  #v1.0
                run()  #v1.0
        server.assert_called_once_with(app, host="127.0.0.1", port=8000)  #v1.0

    def test_web_start_and_dev_bind_to_loopback(self) -> None:  #v1.0
        root = Path(__file__).resolve().parents[3]  #v1.0
        package = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8"))  #v1.0
        for name, command in (("start", "next start"), ("dev", "next dev")):  #v1.0
            self.assertEqual(  #v1.0
                package["scripts"][name], command + " --hostname 127.0.0.1 --port 3000"  #v1.0
            )  #v1.0

    def test_health_reads_application_version(self) -> None:  #v1.0
        with patch.object(app, "version", "test-version"):  #v1.0
            response = self.client.get("/api/health")  #v1.0
        self.assertEqual(response.json(), {"status": "ok", "version": "test-version"})  #v1.0

    def test_both_paths_return_their_packaged_pcm_speech(self) -> None:  #v1.0
        cases = (("answered", b"synthetic", "canned_reply.wav"), ("failed", b"", "empty_audio.wav"))  #v1.0
        payloads = []  #v1.0
        for state, upload, filename in cases:  #v1.0
            with self.subTest(state=state):  #v1.0
                response = self.post_turn(state, upload)  #v1.0
                self.assertEqual(response["state"], state)  #v1.0
                prefix, encoded = response["reply_audio"].split(",", 1)  #v1.0
                self.assertEqual(prefix, "data:audio/wav;base64")  #v1.0
                payload = base64.b64decode(encoded, validate=True)  #v1.0
                resource = files("kaki_backend").joinpath("fixtures").joinpath(filename)  #v1.0
                self.assertEqual(payload, resource.read_bytes())  #v1.0
                with wave.open(io.BytesIO(payload), "rb") as recording:  #v1.0
                    self.assertEqual(recording.getcomptype(), "NONE")  #v1.0
                    self.assertEqual(recording.getnchannels(), 1)  #v1.0
                    self.assertEqual(recording.getsampwidth(), 2)  #v1.0
                    self.assertEqual(recording.getframerate(), 16000)  #v1.0
                    self.assertGreater(recording.getnframes(), 16000)  #v1.0
                    frames = recording.readframes(recording.getnframes())  #v1.0
                    self.assertTrue(any(frames), "Fixture must not be silent PCM")  #v1.0
                    self.assertEqual(len(frames), recording.getnframes() * 2)  #v1.0
                payloads.append(payload)  #v1.0
        self.assertNotEqual(payloads[0], payloads[1])  #v1.0

    def test_fixture_audio_does_not_claim_to_synthesize_arbitrary_text(self) -> None:  #v1.0
        with self.assertRaises(ValueError):  #v1.0
            CannedTtsPort().synthesize("An unrelated answer")  #v1.0
        with self.assertRaises(ValueError):  #v1.0
            canned_audio("../main.py")  #v1.0

    def test_receipt_labels_fixture_source_and_date_without_retrieval(self) -> None:  #v1.0
        response = self.post_turn("receipt", b"synthetic")  #v1.0
        self.assertIn("Source: canned test fixture", response["slip_text"])  #v1.0
        self.assertIn("Source checked: 05-Sep-2026 (fixture date)", response["slip_text"])  #v1.0
        self.assertIn("No retrieval occurred.", response["slip_text"])  #v1.0
        self.assertLessEqual(len(response["slip_text"].split()), 40)  #v1.0
        self.assertEqual(response["sources"], [])  #v1.0


if __name__ == "__main__":  #v1.0
    unittest.main()  #v1.0
