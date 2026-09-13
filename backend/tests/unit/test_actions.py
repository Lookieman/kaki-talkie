# v1.1 | 13-Sep-2026 | Cover a repeat replay from its own stored rows.
# v1.0 | 13-Sep-2026 | Cover WP4.2 actions in the pipeline, the store lookup and migration 0002.
"""WP4.2 actions with fake ports and disposable databases; no models or network.

WP4-AT-04 a repeat calls no LLM, retrieval or TTS and keeps the stored text.
WP4-AT-05 a print returns the stored slip unchanged.
Also: "nothing to act on", previous-turn resolution rules, migration 0002 at
its exact version, and the documented rollback SQL.
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from time import perf_counter

from kaki_backend.contracts.ports import Transcription
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.persistence.database import Database
from kaki_backend.persistence.migrations import load_migrations
from kaki_backend.persistence.repositories import TurnRepository

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_persistence import FakeLlm, FakeRetriever, FakeTts, synthetic_audio  # noqa: E402

CDC_QUESTION = "How do I use my CDC vouchers?"
CREDENTIAL_ACTION = "Log in to my Singpass for me."
NOTHING_TO_ACT_ON = "I have not answered a question yet. Please ask me first."
WP42_SCHEMA_VERSION = 2

ROLLBACK_0002 = (
    "ALTER TABLE turns DROP COLUMN action_outcome;"
    "ALTER TABLE turns DROP COLUMN previous_turn_id;"
    "PRAGMA user_version = 1;"
)


class ScriptedStt:
    """Return whichever transcript the test set for the next turn."""

    def __init__(self) -> None:
        self.text = CDC_QUESTION

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        return Transcription(text=self.text)


class CountingPort:
    """Wrap a fake port and count calls by method name."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.calls: list[str] = []

    def __getattr__(self, name: str):
        attribute = getattr(self._inner, name)
        if name == "ready":
            return attribute

        def counted(*args, **kwargs):
            self.calls.append(name)
            return attribute(*args, **kwargs)
        return counted


class ActionPipelineMixin:
    def setUp(self) -> None:
        super().setUp()
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.database = Database.open(Path(scratch.name) / "sqlite" / "kaki.db")
        self.store = TurnRepository(self.database)
        self.stt = ScriptedStt()
        self.llm = CountingPort(FakeLlm())
        self.tts = CountingPort(FakeTts())
        self.retriever = CountingPort(FakeRetriever())
        self.pipeline = TurnPipeline(
            stt=self.stt, llm=self.llm, tts=self.tts, retriever=self.retriever,
            retrieval_active=True, query_normalise=False, history=self.store,
        )

    def turn(self, turn_id: str, transcript: str, session_id: str = "session-1"):
        self.stt.text = transcript
        execution = self.pipeline.execute(
            device_id="device-1", session_id=session_id, turn_id=turn_id,
            audio=synthetic_audio(), audio_preparation_ms=0.0,
            request_started_at=perf_counter(),
        )
        self.store.record(execution)
        return execution

    def reset_calls(self) -> None:
        for port in (self.llm, self.tts, self.retriever):
            port.calls.clear()


class RepeatPreviousTests(ActionPipelineMixin, unittest.TestCase):
    def test_repeat_replays_stored_answer_without_llm_retrieval_or_tts(self):  # WP4-AT-04
        answer = self.turn("answer", CDC_QUESTION)
        self.reset_calls()
        repeat = self.turn("repeat", "Can you repeat that?")
        self.assertEqual((self.llm.calls, self.retriever.calls, self.tts.calls), ([], [], []))
        first, again = answer.response, repeat.response
        self.assertEqual(again.state.value, "acted")
        self.assertEqual((again.reply_text, again.display_text, again.reply_audio,
                          again.language, again.sources),
                         (first.reply_text, first.display_text, first.reply_audio,
                          first.language, first.sources))
        self.assertEqual(again.slip_text, "")
        self.assertIsNone(again.case_id)
        log = repeat.log
        self.assertEqual((log.intent, log.previous_turn_id, log.action_outcome),
                         ("repeat_previous", "answer", "resolved"))
        self.assertIsNone(log.timings.retrieval_ms)
        self.assertIsNone(log.timings.llm_ms)
        self.assertIsNone(log.timings.tts_ms)
        self.assertIsNotNone(log.timings.stt_ms)
        self.assertIsNone(log.best_dense_score)
        self.assertIsNone(log.evidence_min_dense)

    def test_repeat_of_a_refusal_replays_the_refusal(self):
        refused = self.turn("refused", CREDENTIAL_ACTION)
        self.assertEqual(refused.response.state.value, "refused")
        repeat = self.turn("repeat", "Say again lah")
        self.assertEqual(repeat.response.reply_text, refused.response.reply_text)
        self.assertEqual(repeat.log.previous_turn_id, "refused")

    def test_second_repeat_and_repeat_after_print_resolve_to_the_original(self):
        self.turn("answer", CDC_QUESTION)
        self.turn("repeat-1", "Can you repeat that?")
        self.turn("print", "Please print that for me.")
        second = self.turn("repeat-2", "Boleh ulang sekali lagi?")
        self.assertEqual(second.log.previous_turn_id, "answer")

    def test_failed_turn_is_skipped(self):
        self.turn("answer", CDC_QUESTION)
        failed = self.pipeline.execute(
            device_id="device-1", session_id="session-1", turn_id="failed", audio=b"",
            audio_preparation_ms=0.0, request_started_at=perf_counter(),
        )
        self.store.record(failed)
        self.assertEqual(failed.response.state.value, "failed")
        repeat = self.turn("repeat", "Can you repeat that?")
        self.assertEqual(repeat.log.previous_turn_id, "answer")

    def test_repeat_reproduces_missing_audio_without_synthesising(self):
        answer = self.turn("answer", CDC_QUESTION)
        stored = answer.response.model_copy(update={"reply_audio": None})
        with self.database.connect() as connection:
            connection.execute("UPDATE turns SET reply_audio = NULL WHERE turn_id = 'answer'")
        self.reset_calls()
        repeat = self.turn("repeat", "Can you repeat that?")
        self.assertIsNone(repeat.response.reply_audio)
        self.assertEqual(repeat.response.reply_text, stored.reply_text)
        self.assertEqual(self.tts.calls, [])


class PrintPreviousTests(ActionPipelineMixin, unittest.TestCase):
    def test_print_returns_the_stored_slip_unchanged_without_llm(self):  # WP4-AT-05
        answer = self.turn("answer", CDC_QUESTION)
        self.reset_calls()
        printed = self.turn("print", "Tolong cetak slip itu.")
        self.assertEqual((self.llm.calls, self.retriever.calls), ([], []))
        self.assertEqual(self.tts.calls, ["synthesize"])
        response = printed.response
        self.assertEqual(response.state.value, "acted")
        self.assertEqual(response.slip_text, answer.response.slip_text)
        self.assertTrue(response.slip_text)
        self.assertEqual(response.reply_text, "Here is your slip.")
        self.assertEqual(response.sources, answer.response.sources)
        self.assertEqual((printed.log.previous_turn_id, printed.log.action_outcome),
                         ("answer", "resolved"))
        self.assertIsNone(printed.log.timings.llm_ms)
        self.assertIsNotNone(printed.log.timings.tts_ms)

    def test_action_turn_copies_source_rows_and_replays_identically(self):
        answer = self.turn("answer", CDC_QUESTION)
        printed = self.turn("print", "Please print that for me.")
        with self.database.connect() as connection:
            rows = [
                [tuple(row) for row in connection.execute(
                    "SELECT position, source_id, source_url, chunk_id, cited "
                    "FROM turn_sources WHERE turn_id = ? ORDER BY position", (turn_id,)
                )]
                for turn_id in ("answer", "print")
            ]
        self.assertEqual(rows[0], rows[1])
        self.assertTrue(rows[0])
        self.assertEqual(self.store.replay("print"), printed.response)
        self.assertNotEqual(printed.response, answer.response)

    def test_repeat_turn_replays_identically_from_its_own_rows(self):
        self.turn("answer", CDC_QUESTION)
        repeat = self.turn("repeat", "Can you repeat that?")
        self.turn("print", "Please print that for me.")
        self.assertEqual(self.store.replay("repeat"), repeat.response)
        stored = self.store.find("repeat")
        self.assertEqual(stored.replay_count, 1)
        self.assertEqual((stored.log.previous_turn_id, stored.log.action_outcome),
                         ("answer", "resolved"))
        self.assertEqual(self.store.newest().log.turn_id, "print")


class NothingToActOnTests(ActionPipelineMixin, unittest.TestCase):
    def test_action_with_no_previous_turn_is_acted_no_op(self):
        for turn_id, transcript in (("repeat", "Can you repeat that?"),
                                    ("print", "Can I have the receipt?")):
            with self.subTest(transcript=transcript):
                execution = self.turn(turn_id, transcript, session_id=f"empty-{turn_id}")
                response = execution.response
                self.assertEqual(response.state.value, "acted")
                self.assertEqual(response.reply_text, NOTHING_TO_ACT_ON)
                self.assertEqual((response.slip_text, response.sources), ("", []))
                self.assertEqual((execution.log.previous_turn_id, execution.log.action_outcome),
                                 (None, "nothing_to_act_on"))

    def test_another_sessions_answer_is_never_used(self):
        self.turn("answer", CDC_QUESTION, session_id="session-a")
        repeat = self.turn("repeat", "Can you repeat that?", session_id="session-b")
        self.assertEqual(repeat.log.action_outcome, "nothing_to_act_on")
        self.assertEqual(self.llm.calls, ["generate_grounded"])

    def test_pipeline_without_a_store_has_nothing_to_act_on(self):
        pipeline = TurnPipeline(stt=ScriptedStt(), tts=FakeTts())
        pipeline._stt.text = "Can you repeat that?"
        execution = pipeline.execute(
            device_id="d", session_id="s", turn_id="t", audio=synthetic_audio(),
            audio_preparation_ms=0.0, request_started_at=perf_counter(),
        )
        self.assertEqual(execution.log.action_outcome, "nothing_to_act_on")


class Migration0002Tests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "kaki.db"

    def columns(self, database: Database) -> dict[str, sqlite3.Row]:
        with database.connect() as connection:
            return {row["name"]: row for row in connection.execute("PRAGMA table_info(turns)")}

    def test_packaged_schema_is_exactly_version_2_with_nullable_columns(self):
        database = Database.open(self.path)
        self.assertEqual(database.schema_version(), WP42_SCHEMA_VERSION)
        self.assertEqual(database.latest_version, WP42_SCHEMA_VERSION)
        columns = self.columns(database)
        for name in ("previous_turn_id", "action_outcome"):
            self.assertIn(name, columns)
            self.assertEqual(columns[name]["notnull"], 0)

    def test_version_1_database_upgrades_and_keeps_its_rows(self):
        first = Database(self.path, load_migrations()[:1])
        first.create_file()
        first.migrate()
        with first.connect() as connection:
            connection.executescript(
                "INSERT INTO devices VALUES ('d', 'now', 'now');"
                "INSERT INTO sessions VALUES ('s', 'd', 'now', 'old', 'now');"
                "INSERT INTO turns (turn_id, session_id, device_id, state, language, reply_text,"
                " display_text, slip_text, timings_json, retrieval_evidence_json, completed_at)"
                " VALUES ('old', 's', 'd', 'answered', 'en', 'r', 'd', 's', '{}', '[]', 'now');"
            )
        upgraded = Database.open(self.path)
        self.assertEqual(upgraded.schema_version(), WP42_SCHEMA_VERSION)
        with upgraded.connect() as connection:
            row = connection.execute(
                "SELECT turn_id, previous_turn_id, action_outcome FROM turns"
            ).fetchone()
        self.assertEqual(tuple(row), ("old", None, None))

    def test_outcome_values_are_constrained(self):
        database = Database.open(self.path)
        with database.connect() as connection, self.assertRaises(sqlite3.IntegrityError):
            connection.executescript(
                "INSERT INTO devices VALUES ('d', 'now', 'now');"
                "INSERT INTO sessions VALUES ('s', 'd', 'now', NULL, NULL);"
                "INSERT INTO turns (turn_id, session_id, device_id, state, language, reply_text,"
                " display_text, slip_text, timings_json, retrieval_evidence_json, completed_at,"
                " action_outcome) VALUES ('t', 's', 'd', 'acted', 'en', 'r', 'd', '', '{}',"
                " '[]', 'now', 'maybe');"
            )

    def test_documented_rollback_returns_to_version_1(self):
        database = Database.open(self.path)
        with database.connect() as connection:
            connection.executescript(ROLLBACK_0002)
        self.assertEqual(database.schema_version(), 1)
        self.assertNotIn("previous_turn_id", self.columns(database))
        self.assertNotIn("action_outcome", self.columns(database))
        # Reopening with the WP4.2 build re-applies 0002.
        self.assertEqual(Database.open(self.path).schema_version(), WP42_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
