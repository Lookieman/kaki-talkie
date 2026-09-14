# v1.3 | 14-Sep-2026 | The served schema equals the packaged migration count.
# v1.2 | 13-Sep-2026 | WP5.1 migration 0003: the served schema is at least version 2.
# v1.1 | 13-Sep-2026 | Cover repeat replay and replays of older turns against the debug contract.
# v1.0 | 13-Sep-2026 | Verify WP4-AT-04/05 over the device HTTP contract with fake ports.
"""WP4.2 repeat and print over the device HTTP contract; fake ports only.

WP4-AT-04 repeat_previous calls no LLM and returns the stored text unchanged.
WP4-AT-05 print_previous returns the stored slip unchanged.

Also proves, over HTTP: the nine-field response and `acted` state, the debug
fields, an action turn_id replaying from the store, resolution after a
restart (fresh service and database handle), session isolation, and the
exact WP4.2 schema version. WP4-AT-06 (print policy) is a client rule
(design.md 9.3) covered by `apps/web/src/test/printPolicy.test.ts`.
"""

import os
import sys
import unittest

from fastapi.testclient import TestClient

from kaki_backend.orchestration.idempotency import TurnService
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.persistence.database import Database
from kaki_backend.persistence.repositories import TurnRepository
from kaki_test_env import canned_backend

app = canned_backend().app

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "unit"))
from test_actions import CountingPort, ScriptedStt, packaged_schema_version  # noqa: E402
from test_persistence import FakeLlm, FakeRetriever, FakeTts, synthetic_audio  # noqa: E402

RESPONSE_FIELDS = {"turn_id", "reply_audio", "reply_text", "display_text", "slip_text",
                   "language", "state", "case_id", "sources"}


class Wp42ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app.state.turn_service.reset()
        original = app.state.turn_service
        self.addCleanup(setattr, app.state, "turn_service", original)
        self.build_service(Database.open(app.state.database.path))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def build_service(self, database: Database) -> None:
        self.stt = ScriptedStt()
        self.llm = CountingPort(FakeLlm())
        self.tts = CountingPort(FakeTts())
        store = TurnRepository(database)
        self.pipeline = TurnPipeline(stt=self.stt, llm=self.llm, tts=self.tts,
                                     retriever=FakeRetriever(), retrieval_active=True,
                                     query_normalise=False, history=store)
        app.state.turn_service = TurnService(self.pipeline, store)

    def post(self, turn_id: str, transcript: str, session_id: str = "wp42-session") -> dict:
        self.stt.text = transcript
        response = self.client.post(
            "/api/device/turn",
            data={"device_id": "wp42-device", "session_id": session_id, "turn_id": turn_id},
            files={"audio": ("upload.wav", synthetic_audio(), "audio/wav")},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), RESPONSE_FIELDS)
        return body

    def debug(self) -> dict:
        return self.client.get("/api/device/debug/last-turn").json()

    def test_repeat_returns_stored_answer_without_llm(self) -> None:  # WP4-AT-04
        answer = self.post("answer", "How do I use my CDC vouchers?")
        self.llm.calls.clear()
        self.tts.calls.clear()
        repeat = self.post("repeat", "Can you repeat that?")
        self.assertEqual((self.llm.calls, self.tts.calls), ([], []))
        self.assertEqual(repeat["state"], "acted")
        for field in ("reply_text", "display_text", "reply_audio", "language", "sources"):
            self.assertEqual(repeat[field], answer[field], field)
        self.assertEqual((repeat["slip_text"], repeat["case_id"]), ("", None))
        debug = self.debug()
        self.assertEqual(
            (debug["intent"], debug["previous_turn_id"], debug["action_outcome"]),
            ("repeat_previous", "answer", "resolved"),
        )
        self.assertIsNone(debug["timings_ms"]["llm_ms"])
        self.assertIsNone(debug["timings_ms"]["retrieval_ms"])
        self.assertIsNone(debug["timings_ms"]["tts_ms"])

    def test_print_returns_stored_slip_unchanged(self) -> None:  # WP4-AT-05
        answer = self.post("answer", "How do I use my CDC vouchers?")
        self.post("repeat", "Say again lah")
        self.llm.calls.clear()
        printed = self.post("print", "Please print that for me.")
        self.assertEqual(self.llm.calls, [])
        self.assertEqual(printed["state"], "acted")
        self.assertEqual(printed["slip_text"], answer["slip_text"])
        self.assertEqual(printed["reply_text"], "Here is your slip.")
        self.assertEqual(self.debug()["previous_turn_id"], "answer")

    def test_action_turn_id_replays_from_the_store(self) -> None:
        self.post("answer", "How do I use my CDC vouchers?")
        printed = self.post("print", "Please print that for me.")
        executions = self.pipeline.execution_count
        replay = self.post("print", "How do I use my CDC vouchers?")
        self.assertEqual(replay, printed)
        self.assertEqual(self.pipeline.execution_count, executions)
        self.assertEqual(self.debug()["replay_count"], 1)

    def test_repeat_turn_id_replays_from_the_store(self) -> None:
        self.post("answer", "How do I use my CDC vouchers?")
        repeat = self.post("repeat", "Can you repeat that?")
        executions = self.pipeline.execution_count
        self.tts.calls.clear()
        # Print audio under the repeat's turn_id: re-execution would print.
        replay = self.post("repeat", "Please print that for me.")
        self.assertEqual(replay, repeat)
        self.assertEqual(self.pipeline.execution_count, executions)
        self.assertEqual(self.tts.calls, [])
        self.assertEqual(self.debug()["replay_count"], 1)

    def test_replaying_older_actions_counts_in_store_not_in_debug_view(self) -> None:
        # The wp_check sequence: the debug view shows the newest executed turn,
        # and a replay writes no row, so replaying older turns does not move it.
        self.post("answer", "How do I use my CDC vouchers?")
        repeat = self.post("repeat", "Can you repeat that?")
        printed = self.post("print", "Please print that for me.")
        self.post("repeat-2", "Can you repeat that?")
        self.assertEqual(self.post("print", "Can you repeat that?"), printed)
        self.assertEqual(self.post("repeat", "Please print that for me."), repeat)
        debug = self.debug()
        self.assertEqual((debug["turn_id"], debug["replay_count"]), ("repeat-2", 0))
        store = TurnRepository(app.state.database)
        self.assertEqual(store.find("print").replay_count, 1)
        self.assertEqual(store.find("repeat").replay_count, 1)
        self.assertEqual(store.find("repeat-2").replay_count, 0)

    def test_repeat_resolves_from_sqlite_after_a_restart(self) -> None:
        answer = self.post("answer", "How do I use my CDC vouchers?")
        self.build_service(Database.open(app.state.database.path))
        repeat = self.post("repeat-after-restart", "Boleh ulang sekali lagi?")
        self.assertEqual(repeat["reply_text"], answer["reply_text"])
        self.assertEqual(self.debug()["previous_turn_id"], "answer")

    def test_nothing_to_act_on_is_distinguished_in_debug(self) -> None:
        self.post("answer", "How do I use my CDC vouchers?", session_id="other-session")
        response = self.post("lonely-repeat", "Can you repeat that?", session_id="new-session")
        self.assertEqual(response["state"], "acted")
        self.assertEqual((response["slip_text"], response["sources"]), ("", []))
        debug = self.debug()
        self.assertEqual((debug["previous_turn_id"], debug["action_outcome"]),
                         (None, "nothing_to_act_on"))

    def test_answer_turns_carry_null_action_fields(self) -> None:
        self.post("answer", "How do I print my CDC vouchers?")
        debug = self.debug()
        self.assertEqual((debug["intent"], debug["previous_turn_id"], debug["action_outcome"]),
                         ("answer", None, None))

    def test_schema_is_the_packaged_version_and_pending_stays_empty(self) -> None:  #v1.3
        self.post("answer", "How do I use my CDC vouchers?")
        self.assertEqual(self.debug()["schema_version"], packaged_schema_version())
        self.assertIs(self.client.get("/api/health").json()["storage_ready"], True)
        self.assertEqual(self.client.get("/api/device/pending").json(), [])


if __name__ == "__main__":
    unittest.main()
