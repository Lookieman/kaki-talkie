# v1.0 | 18-Sep-2026 | WP6.6 admin surface over HTTP: auth, config, push, pending, WP1-AT-05.
"""Drive the admin surface end to end with canned ports (WP6-AT-15, 16, 17).

The application is built through the canned sanitiser, whose environment
carries the fixed test admin token, so authentication is deterministic and
needs no tunnel. Auth failures are proven to change nothing by reading the
state before and after. The nine-field turn response and the pending path's
empty default (WP1-AT-05) are asserted unchanged.
"""

import io
import unittest
import wave
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kaki_test_env import CANNED_ADMIN_TOKEN, DEVICE_AUTH, canned_backend

main = canned_backend()
app = main.app

AUTH = {"Authorization": f"Bearer {CANNED_ADMIN_TOKEN}"}
SEEDED_KEY = "cdc-vouchers-available"


def synthetic_audio() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


class Wp66Base(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app, headers=DEVICE_AUTH)  # WP6.4
        self.device_id = f"wp66-{uuid4().hex[:8]}"

    def tearDown(self) -> None:
        # Leave shared state calm for the next test: policy decides, queue idle.
        app.state.admin_store.set_reply_language(self.device_id, "auto")
        app.state.admin_store.take_due(self.device_id)

    def post_turn(self, device_id: str) -> dict:
        response = self.client.post(
            "/api/device/turn",
            data={"device_id": device_id, "session_id": device_id,
                  "turn_id": f"turn-{uuid4().hex[:8]}"},
            files={"audio": ("upload.wav", synthetic_audio(), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def state(self) -> dict:
        response = self.client.get("/api/admin/state", headers=AUTH)
        self.assertEqual(response.status_code, 200)
        return response.json()


class AuthTests(Wp66Base):
    """WP6-AT-17: rejected before any state change; fail closed without a token."""

    def test_missing_and_wrong_tokens_are_rejected_and_change_nothing(self):
        before = self.state()
        for headers in ({}, {"Authorization": "Bearer wrong-token"},
                        {"Authorization": f"Token {CANNED_ADMIN_TOKEN}"}):
            for method, path, body in (
                ("POST", "/api/admin/config",
                 {"device_id": self.device_id, "reply_language": "ms"}),
                ("POST", "/api/admin/push", {"device_id": self.device_id}),
                ("GET", "/api/admin/state", None),
            ):
                with self.subTest(path=path, headers=bool(headers)):
                    response = self.client.request(method, path, json=body, headers=headers)
                    self.assertEqual(response.status_code, 401)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.client.get(f"/api/device/pending?device_id={self.device_id}").json(), [])

    def test_an_unset_token_fails_closed_with_403(self):
        # A separate app instance carrying no token: the routes refuse everyone.
        from kaki_backend.api.admin import router
        from kaki_backend.config import AdminSettings

        closed = FastAPI()
        closed.include_router(router)
        closed.state.admin_settings = AdminSettings(token="")
        closed.state.admin_store = app.state.admin_store
        client = TestClient(closed)
        response = client.get("/api/admin/state", headers=AUTH)
        self.assertEqual(response.status_code, 403)
        self.assertIn("KAKI_ADMIN_TOKEN", response.json()["detail"])


class ConfigTests(Wp66Base):
    """WP6-AT-15: a config change alters the next turn, no restart."""

    def test_the_next_turn_follows_the_override_and_records_it(self):
        response = self.client.post(
            "/api/admin/config", headers=AUTH,
            json={"device_id": self.device_id, "reply_language": "ms"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn({"device_id": self.device_id, "reply_language": "ms"},
                      [{k: row[k] for k in ("device_id", "reply_language")}
                       for row in self.state()["config"]])

        body = self.post_turn(self.device_id)
        self.assertEqual(body["language"], "ms")
        debug = self.client.get("/api/device/debug/last-turn").json()
        self.assertEqual(debug["language_override"], "ms")
        self.assertEqual(debug["reply_language"], "ms")

        # Back to auto: the very next turn returns to the policy, still no restart.
        self.client.post("/api/admin/config", headers=AUTH,
                         json={"device_id": self.device_id, "reply_language": "auto"})
        self.assertEqual(self.post_turn(self.device_id)["language"], "en")
        self.assertIsNone(self.client.get("/api/device/debug/last-turn").json()["language_override"])

    def test_the_override_is_per_device(self):
        self.client.post("/api/admin/config", headers=AUTH,
                         json={"device_id": self.device_id, "reply_language": "ms"})
        other = f"wp66-other-{uuid4().hex[:8]}"
        self.assertEqual(self.post_turn(other)["language"], "en")

    def test_invalid_language_and_blank_device_are_422(self):
        for body in ({"device_id": self.device_id, "reply_language": "zh"},
                     {"device_id": " ", "reply_language": "ms"},
                     {"reply_language": "ms"}):
            with self.subTest(body=body):
                response = self.client.post("/api/admin/config", headers=AUTH, json=body)
                self.assertEqual(response.status_code, 422)


class PushTests(Wp66Base):
    """WP6-AT-16 backend half, and WP1-AT-05 unchanged."""

    def push(self) -> dict:
        response = self.client.post("/api/admin/push", headers=AUTH,
                                    json={"device_id": self.device_id})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def pending(self, device_id: str | None):
        path = "/api/device/pending"
        if device_id is not None:
            path += f"?device_id={device_id}"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_pending_returns_empty_without_a_push_or_a_device_id(self):
        # WP1-AT-05: the path and its empty default are unchanged.
        self.assertEqual(self.pending(None), [])
        self.assertEqual(self.pending(self.device_id), [])
        self.push()
        self.assertEqual(self.pending(None), [])          # still [] with no identity

    def test_a_push_is_delivered_exactly_once_to_its_named_device(self):
        pushed = self.push()
        self.assertEqual((pushed["state"], pushed["target_device_id"]),
                         ("queued", self.device_id))
        self.assertEqual(self.pending("some-other-device"), [])
        items = self.pending(self.device_id)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["id"], SEEDED_KEY)
        self.assertEqual(item["kind"], "nudge")
        self.assertEqual(item["language"], "en")
        self.assertIn("CDC vouchers", item["text"])
        self.assertIsNotNone(item["pushed_at"])
        for _ in range(20):
            self.assertEqual(self.pending(self.device_id), [])
        message = self.state()["messages"][0]
        self.assertEqual((message["state"], message["delivered_count"]), ("delivered", 1))

    def test_only_a_new_push_re_arms_and_ms_config_delivers_malay(self):
        self.push()
        self.pending(self.device_id)
        self.assertEqual(self.pending(self.device_id), [])
        self.client.post("/api/admin/config", headers=AUTH,
                         json={"device_id": self.device_id, "reply_language": "ms"})
        self.push()
        item = self.pending(self.device_id)[0]
        self.assertEqual(item["language"], "ms")
        self.assertIn("baucar CDC", item["text"])

    def test_a_push_without_a_device_id_or_with_an_unknown_key_is_refused(self):
        before = self.state()["messages"]
        self.assertEqual(
            self.client.post("/api/admin/push", headers=AUTH, json={}).status_code, 422
        )
        response = self.client.post(
            "/api/admin/push", headers=AUTH,
            json={"device_id": self.device_id, "message_key": "no-such-message"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.state()["messages"], before)

    def test_state_names_the_default_device_for_the_admin_page(self):
        state = self.state()
        self.assertEqual(state["default_device"], "kaki-pi-01")
        self.assertEqual(state["reply_languages"], ["en", "ms", "auto"])


if __name__ == "__main__":
    unittest.main()
