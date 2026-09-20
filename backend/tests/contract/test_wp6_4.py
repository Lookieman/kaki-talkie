# v1.0 | 20-Sep-2026 | WP6.4 device service auth and same-turn_id single-answer guarantees.
"""Prove the device path's authentication and idempotency contracts (WP6-AT-04/05).

Authentication: every `/api/device/*` route requires the device bearer token,
fails closed without a configured one, rejects before any state change, and
never accepts the admin token (nor the other way round). The failure body is
identical for a missing and a wrong token.

Idempotency under retry: the turn service holds its lock across execution, so
a duplicate `turn_id` arriving while the first execution is still in flight
waits and is served the single stored answer - never a second execution, and
never zero answers while the server is still committing one. That is the
server half of WP6-AT-04; the device client's retry reuses the same turn_id.
"""

import asyncio
import io
import time
import unittest
import wave
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kaki_test_env import CANNED_ADMIN_TOKEN, CANNED_DEVICE_TOKEN, DEVICE_AUTH, canned_backend

main = canned_backend()
app = main.app

DEVICE_ROUTES = (
    ("POST", "/api/device/turn"),
    ("GET", "/api/device/pending"),
    ("GET", "/api/device/debug/last-turn"),
)


def synthetic_audio() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


class DeviceAuthTests(unittest.TestCase):
    """WP6-AT-05: unauthenticated device requests are denied before turn processing."""

    def setUp(self) -> None:
        app.state.turn_service.reset()
        self.client = TestClient(app)  # deliberately no default auth header

    def turn_fields(self) -> dict:
        return {
            "data": {"device_id": "wp64", "session_id": "wp64",
                     "turn_id": f"wp64-{uuid4().hex[:8]}"},
            "files": {"audio": ("upload.wav", synthetic_audio(), "audio/wav")},
        }

    def test_missing_wrong_and_admin_tokens_are_rejected_identically(self):
        for headers in ({}, {"Authorization": "Bearer wrong-token"},
                        {"Authorization": f"Bearer {CANNED_ADMIN_TOKEN}"},
                        {"Authorization": f"Token {CANNED_DEVICE_TOKEN}"}):
            for method, path in DEVICE_ROUTES:
                with self.subTest(path=path, headers=headers.get("Authorization", "none")):
                    kwargs = self.turn_fields() if method == "POST" else {}
                    response = self.client.request(method, path, headers=headers, **kwargs)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json()["detail"],
                                     "Device bearer token required.")

    def test_rejection_happens_before_any_state_change(self):
        rejected = self.client.post("/api/device/turn", **self.turn_fields())
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(app.state.turn_service.execution_count, 0)
        debug = self.client.get("/api/device/debug/last-turn", headers=DEVICE_AUTH)
        self.assertEqual(debug.status_code, 404)  # nothing was stored

    def test_the_device_token_is_never_accepted_on_the_admin_routes(self):
        response = self.client.get("/api/admin/state", headers=DEVICE_AUTH)
        self.assertEqual(response.status_code, 401)

    def test_health_stays_open_without_a_token(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_an_unset_token_fails_closed_with_403(self):
        from kaki_backend.api.turn import router
        from kaki_backend.config import DeviceAuthSettings

        closed = FastAPI()
        closed.include_router(router)
        closed.state.device_settings = DeviceAuthSettings(token="")
        response = TestClient(closed).post("/api/device/turn", headers=DEVICE_AUTH,
                                           **self.turn_fields())
        self.assertEqual(response.status_code, 403)
        self.assertIn("KAKI_DEVICE_TOKEN", response.json()["detail"])

    def test_an_authenticated_turn_still_answers(self):
        response = self.client.post("/api/device/turn", headers=DEVICE_AUTH,
                                    **self.turn_fields())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "answered")


class SlowPipeline:
    """Wrap the application's pipeline, delaying execution to keep it in flight."""

    def __init__(self, inner, delay_seconds: float) -> None:
        self._inner = inner
        self._delay = delay_seconds
        self.executions = 0
        self.execution_count = 0

    def execute(self, **kwargs):
        self.executions += 1
        time.sleep(self._delay)
        return self._inner.execute(**kwargs)


class InFlightRetryTests(unittest.TestCase):
    """WP6-AT-04, server half: one execution and one answer for a retried turn_id."""

    def test_a_duplicate_arriving_mid_execution_waits_for_the_single_answer(self):
        import tempfile

        from kaki_backend.orchestration.idempotency import TurnService
        from kaki_backend.persistence.database import Database
        from kaki_backend.persistence.repositories import TurnRepository

        service = app.state.turn_service
        slow = SlowPipeline(service._pipeline, delay_seconds=0.2)
        with tempfile.TemporaryDirectory() as scratch:
            retried = TurnService(slow, TurnRepository(Database.open(f"{scratch}/kaki.db")))

            async def submit():
                return await retried.process(
                    device_id="wp64", session_id="wp64", turn_id="in-flight",
                    audio=synthetic_audio(), audio_preparation_ms=0.0,
                    request_started_at=0.0,
                )

            async def race():
                first = asyncio.create_task(submit())
                await asyncio.sleep(0.05)  # the retry arrives mid-execution
                second = asyncio.create_task(submit())
                return await asyncio.gather(first, second)

            first, second = asyncio.run(race())
            self.assertEqual(slow.executions, 1)
            self.assertEqual(first.model_dump(), second.model_dump())
            # A later retry of the committed turn replays from the store too.
            late = asyncio.run(submit())
            self.assertEqual(slow.executions, 1)
            self.assertEqual(late.model_dump(), first.model_dump())


if __name__ == "__main__":
    unittest.main()
