# v1.0 | 13-Sep-2026 | Verify WP4-AT-01/02/03 over HTTP, including a real process restart.
"""WP4.1 durable turns over the device HTTP contract; canned or fake ports only.

WP4-AT-01 a completed turn is durably stored.
WP4-AT-02 a grounded turn stores one `turn_sources` row per response source.
WP4-AT-03 after a restart the same turn_id returns the stored response
          without re-execution.

AT-03 is proven twice: in-process, with a fresh service and database handle
whose ports would fail the test if called, and across two separate Python
processes that share only a disposable `KAKI_DATA_ROOT`.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import wave

from fastapi.testclient import TestClient

from kaki_backend.orchestration.idempotency import TurnService
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.persistence.database import Database
from kaki_backend.persistence.repositories import TurnRepository
from kaki_test_env import canned_backend

# The application is built at import time from the environment, so it must be
# imported through the canned sanitiser rather than directly.
app = canned_backend().app

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "unit"))
from test_persistence import grounded_pipeline  # noqa: E402

# Run in a child process: build the application from its environment, report
# the debug view before any request, submit one turn and report the result.
RESTART_CHILD = """
import json, sys
from fastapi.testclient import TestClient
from kaki_backend.main import app
client = TestClient(app)
debug = client.get("/api/device/debug/last-turn")
response = client.post(
    "/api/device/turn",
    data={"device_id": "wp41", "session_id": "wp41", "turn_id": "restart-turn"},
    files={"audio": ("upload.wav", open(sys.argv[1], "rb").read(), "audio/wav")},
)
print(json.dumps({
    "debug_status": debug.status_code,
    "debug": debug.json() if debug.status_code == 200 else None,
    "status": response.status_code,
    "response": response.json(),
    "execution_count": app.state.turn_service.execution_count,
}))
"""


def synthetic_audio() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


class ExplodingPort:
    """Fail loudly if a replay reaches any model port."""

    def ready(self) -> bool:
        return True

    def __getattr__(self, name: str):
        raise AssertionError(f"replay must not call {name}")


class Wp41ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app.state.turn_service.reset()
        original = app.state.turn_service
        self.addCleanup(setattr, app.state, "turn_service", original)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def post_turn(self, turn_id: str, audio: bytes) -> dict:
        response = self.client.post(
            "/api/device/turn",
            data={"device_id": "wp41-device", "session_id": "wp41-session", "turn_id": turn_id},
            files={"audio": ("upload.wav", audio, "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_completed_turn_is_durably_stored(self) -> None:  # WP4-AT-01
        response = self.post_turn("stored", synthetic_audio())
        stored = TurnRepository(Database.open(app.state.database.path)).find("stored")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.response.model_dump(mode="json"), response)
        self.assertEqual((stored.log.device_id, stored.log.session_id),
                         ("wp41-device", "wp41-session"))

    def test_grounded_turn_stores_one_row_per_source(self) -> None:  # WP4-AT-02
        app.state.turn_service = TurnService(
            grounded_pipeline(), TurnRepository(app.state.database)
        )
        response = self.post_turn("grounded", synthetic_audio())
        self.assertEqual(response["state"], "answered")
        with app.state.database.connect() as connection:
            rows = connection.execute(
                "SELECT source_url, cited FROM turn_sources WHERE turn_id = 'grounded' "
                "ORDER BY position"
            ).fetchall()
        self.assertEqual([row["source_url"] for row in rows],
                         [source["source_url"] for source in response["sources"]])
        self.assertEqual([row["cited"] for row in rows], [1, 0])

    def test_fresh_service_replays_without_calling_ports(self) -> None:  # WP4-AT-03
        first = self.post_turn("replayed", synthetic_audio())
        exploding = ExplodingPort()
        restarted = TurnPipeline(stt=exploding, llm=exploding, tts=exploding,
                                 retriever=exploding)
        app.state.turn_service = TurnService(
            restarted, TurnRepository(Database.open(app.state.database.path))
        )
        replay = self.post_turn("replayed", b"")
        self.assertEqual(replay, first)
        self.assertEqual(restarted.execution_count, 0)
        debug = self.client.get("/api/device/debug/last-turn").json()
        self.assertEqual((debug["turn_id"], debug["replay_count"], debug["schema_version"]),
                         ("replayed", 1, 1))

    def test_health_reports_storage_ready(self) -> None:
        self.assertIs(self.client.get("/api/health").json()["storage_ready"], True)

    def test_restart_in_a_new_process_returns_the_stored_response(self) -> None:  # WP4-AT-03
        with tempfile.TemporaryDirectory() as scratch:
            valid = os.path.join(scratch, "valid.wav")
            empty = os.path.join(scratch, "empty.wav")
            with open(valid, "wb") as handle:
                handle.write(synthetic_audio())
            open(empty, "wb").close()
            environment = {**os.environ, "KAKI_DATA_ROOT": os.path.join(scratch, "data")}

            def run_child(audio_path: str) -> dict:
                completed = subprocess.run(
                    [sys.executable, "-c", RESTART_CHILD, audio_path], cwd=scratch,
                    env=environment, capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return json.loads(completed.stdout.strip().splitlines()[-1])

            first = run_child(valid)
            # Different audio: re-execution would return a failed turn instead.
            second = run_child(empty)

        self.assertEqual(first["debug_status"], 404)
        self.assertEqual((first["status"], first["execution_count"]), (200, 1))
        self.assertEqual(first["response"]["state"], "answered")
        self.assertEqual(second["debug_status"], 200)
        self.assertEqual(second["debug"]["turn_id"], "restart-turn")
        self.assertEqual((second["status"], second["execution_count"]), (200, 0))
        self.assertEqual(second["response"], first["response"])


if __name__ == "__main__":
    unittest.main()
