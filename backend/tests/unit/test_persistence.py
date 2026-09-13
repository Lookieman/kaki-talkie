# v1.0 | 13-Sep-2026 | Cover WP4.1 storage settings, migrations, pragmas and the turn store.
"""SQLite persistence with disposable databases and fake ports; no models or network.

Covers the WP4.1 storage mechanics: the data-root requirement, private file
creation, ordered and idempotent migrations, per-connection pragmas, the
durable turn record with its `turn_sources` rows and BLOB audio, replay
counting, and refusal to open a database newer than this build.
"""

import io
import os
import sqlite3
import stat
import tempfile
import unittest
import wave
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from kaki_backend.config import StorageSettings
from kaki_backend.contracts.ports import EvidenceChunk, GroundedReply, Transcription
from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.persistence.database import Database, DatabaseError
from kaki_backend.persistence.migrations import Migration, load_migrations
from kaki_backend.persistence.repositories import TurnRepository, audio_to_bytes

CDC_SOURCE = SourceRecord(
    source_url="https://vouchers.cdc.gov.sg/residents/faq",
    page_title="CDC Vouchers FAQ",
    captured_at=datetime(2026, 9, 10, 11, 6, 44, tzinfo=timezone.utc),
    content_hash="sha256:cdc",
)
CHAS_SOURCE = SourceRecord(
    source_url="https://www.chas.sg/about",
    page_title="About CHAS",
    captured_at=datetime(2026, 9, 10, 11, 8, 0, tzinfo=timezone.utc),
)
# Rank 1 is CHAS, but the model cites block 2 (CDC); the store must record the
# cited CDC chunk at position 0 with its true retrieval rank.
EVIDENCE = (
    EvidenceChunk(chunk_id="chas-1", source_id="chas-about", text="CHAS subsidises visits.",
                  source=CHAS_SOURCE, fused_score=0.05, dense_score=0.61),
    EvidenceChunk(chunk_id="cdc-1", source_id="cdc-vouchers-residents",
                  text="Claim CDC Vouchers through the SMS link.",
                  source=CDC_SOURCE, fused_score=0.04, dense_score=0.82),
    EvidenceChunk(chunk_id="cdc-2", source_id="cdc-vouchers-residents",
                  text="Spend vouchers at participating merchants.",
                  source=CDC_SOURCE, fused_score=0.03, dense_score=0.7),
)


def synthetic_audio() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x01\x00" * 160)
    return buffer.getvalue()


REPLY_WAV = synthetic_audio()


class FakeStt:
    def __init__(self, text: str) -> None:
        self._text = text

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        return Transcription(text=self._text)


class FakeLlm:
    def ready(self) -> bool:
        return True

    def generate(self, transcript: str) -> str:
        return "An ungrounded reply."

    def generate_grounded(self, transcript: str, *, evidence: str) -> GroundedReply:
        return GroundedReply(text="1. Open the SMS link. 2. Show the code.", cited_index=2)

    def rewrite_query(self, transcript: str) -> str:
        return transcript


class FakeTts:
    def ready(self) -> bool:
        return True

    def synthesize(self, reply_text: str) -> str:
        return "data:audio/wav;base64," + b64encode(REPLY_WAV).decode("ascii")


class FakeRetriever:
    def __init__(self, evidence=EVIDENCE) -> None:
        self._evidence = evidence

    def ready(self) -> bool:
        return True

    def retrieve(self, original_query, normalized_query):
        return self._evidence


def execute(pipeline: TurnPipeline, turn_id: str, *, audio: bytes | None = None,
            session_id: str = "session-1"):
    return pipeline.execute(
        device_id="device-1", session_id=session_id, turn_id=turn_id,
        audio=synthetic_audio() if audio is None else audio,
        audio_preparation_ms=0.0, request_started_at=perf_counter(),
    )


def grounded_pipeline() -> TurnPipeline:
    return TurnPipeline(stt=FakeStt("How do I use my CDC vouchers?"), llm=FakeLlm(),
                        tts=FakeTts(), retriever=FakeRetriever(), retrieval_active=True,
                        query_normalise=False)


class TemporaryDatabaseMixin:
    def setUp(self) -> None:
        super().setUp()
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "sqlite" / "kaki.db"


class StorageSettingsTests(unittest.TestCase):
    def test_unset_data_root_names_the_variable_and_expected_path(self) -> None:
        for environment in ({}, {"KAKI_DATA_ROOT": ""}, {"KAKI_DATA_ROOT": "relative"}):
            with self.subTest(environment=environment):
                with self.assertRaises(ValueError) as raised:
                    StorageSettings.from_environment(environment)
                self.assertIn("KAKI_DATA_ROOT", str(raised.exception))
                self.assertIn("$KAKI_DATA_ROOT/sqlite/kaki.db", str(raised.exception))

    def test_data_root_is_required_even_with_an_override(self) -> None:
        with self.assertRaises(ValueError):
            StorageSettings.from_environment({"KAKI_SQLITE_PATH": "/tmp/kaki.db"})

    def test_default_path_derives_from_the_data_root(self) -> None:
        settings = StorageSettings.from_environment({"KAKI_DATA_ROOT": "/data"})
        self.assertEqual(settings.path, "/data/sqlite/kaki.db")

    def test_absolute_override_wins_and_relative_override_is_rejected(self) -> None:
        settings = StorageSettings.from_environment(
            {"KAKI_DATA_ROOT": "/data", "KAKI_SQLITE_PATH": "/elsewhere/test.db"}
        )
        self.assertEqual(settings.path, "/elsewhere/test.db")
        with self.assertRaises(ValueError) as raised:
            StorageSettings.from_environment(
                {"KAKI_DATA_ROOT": "/data", "KAKI_SQLITE_PATH": "test.db"}
            )
        self.assertIn("KAKI_SQLITE_PATH", str(raised.exception))


class DatabaseTests(TemporaryDatabaseMixin, unittest.TestCase):
    def test_open_creates_a_private_file_with_the_four_tables(self) -> None:
        database = Database.open(self.path)
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        with database.connect() as connection:
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertEqual(tables, {"devices", "sessions", "turns", "turn_sources"})
        self.assertEqual(database.schema_version(), 1)
        self.assertTrue(database.ready())

    def test_packaged_migrations_are_numbered_from_one(self) -> None:
        migrations = load_migrations()
        self.assertEqual(migrations[0].version, 1)
        self.assertEqual(migrations[0].name, "0001_initial.sql")

    def test_reopening_is_idempotent(self) -> None:
        Database.open(self.path)
        database = Database.open(self.path)
        self.assertEqual(database.schema_version(), 1)

    def test_every_connection_carries_the_pragmas(self) -> None:
        database = Database.open(self.path)
        for _ in range(2):
            with database.connect() as connection:
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)

    def test_newer_database_is_refused(self) -> None:
        database = Database.open(self.path)
        with database.connect() as connection:
            connection.execute("PRAGMA user_version = 99")
        with self.assertRaises(DatabaseError) as raised:
            Database.open(self.path)
        self.assertIn("newer than this build", str(raised.exception))
        self.assertFalse(database.ready())

    def test_failed_migration_rolls_back_to_the_previous_version(self) -> None:
        migrations = (
            Migration(1, "0001_a.sql", "CREATE TABLE first (id INTEGER);"),
            Migration(2, "0002_b.sql", "CREATE TABLE second (id INTEGER); NOT SQL;"),
        )
        database = Database(self.path, migrations)
        database.create_file()
        with self.assertRaises(sqlite3.Error):
            database.migrate()
        self.assertEqual(database.schema_version(), 1)
        with database.connect() as connection:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        self.assertIn("first", names)
        self.assertNotIn("second", names)

    def test_gapped_migration_numbering_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Database(self.path, (Migration(1, "0001_a.sql", ""), Migration(3, "0003_c.sql", "")))


class TurnRepositoryTests(TemporaryDatabaseMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.database = Database.open(self.path)
        self.turns = TurnRepository(self.database)

    def test_grounded_turn_round_trips_identically(self) -> None:
        execution = execute(grounded_pipeline(), "grounded")
        self.turns.record(execution)
        stored = TurnRepository(Database.open(self.path)).find("grounded")
        self.assertEqual(stored.response.model_dump(mode="json"),
                         execution.response.model_dump(mode="json"))
        self.assertEqual(stored.log.model_dump(mode="json"), execution.log.model_dump(mode="json"))
        self.assertEqual(stored.replay_count, 0)

    def test_reply_audio_is_stored_as_raw_wav_bytes(self) -> None:
        self.turns.record(execute(grounded_pipeline(), "audio"))
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT typeof(reply_audio) AS kind, reply_audio FROM turns WHERE turn_id = ?",
                ("audio",),
            ).fetchone()
        self.assertEqual(row["kind"], "blob")
        self.assertEqual(row["reply_audio"], REPLY_WAV)

    def test_one_source_row_per_response_source_cited_first(self) -> None:
        execution = execute(grounded_pipeline(), "sources")
        self.turns.record(execution)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM turn_sources WHERE turn_id = ? ORDER BY position", ("sources",)
            ).fetchall()
        self.assertEqual(len(rows), len(execution.response.sources))
        self.assertEqual(len(rows), 2)
        first, second = rows
        self.assertEqual((first["source_url"], first["chunk_id"], first["retrieval_rank"],
                          first["cited"]), (CDC_SOURCE.source_url, "cdc-1", 2, 1))
        self.assertEqual((second["source_url"], second["chunk_id"], second["retrieval_rank"],
                          second["cited"]), (CHAS_SOURCE.source_url, "chas-1", 1, 0))
        self.assertEqual(first["content_hash"], "sha256:cdc")

    def test_refused_and_failed_turns_store_no_sources(self) -> None:
        refused = TurnPipeline(stt=FakeStt("What is the weather?"), llm=FakeLlm(), tts=FakeTts(),
                               retriever=FakeRetriever(evidence=()), retrieval_active=True,
                               query_normalise=False)
        cases = (("refused", execute(refused, "refused")),
                 ("failed", execute(grounded_pipeline(), "failed", audio=b"")))
        for state, execution in cases:
            with self.subTest(state=state):
                self.assertEqual(execution.response.state.value, state)
                self.turns.record(execution)
                stored = self.turns.find(state)
                self.assertEqual(stored.response, execution.response)
                self.assertEqual(stored.log.source_links, [])

    def test_replay_counts_and_unknown_turn_returns_none(self) -> None:
        execution = execute(grounded_pipeline(), "replayed")
        self.turns.record(execution)
        self.assertIsNone(self.turns.replay("unknown"))
        self.assertEqual(self.turns.replay("replayed"), execution.response)
        self.assertEqual(self.turns.replay("replayed"), execution.response)
        self.assertEqual(self.turns.find("replayed").replay_count, 2)

    def test_duplicate_turn_id_is_rejected_and_leaves_one_row(self) -> None:
        execution = execute(grounded_pipeline(), "duplicate")
        self.turns.record(execution)
        with self.assertRaises(sqlite3.IntegrityError):
            self.turns.record(execution)
        with self.database.connect() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM turns").fetchone()[0], 1)
            self.assertEqual(
                connection.execute("SELECT count(*) FROM turn_sources").fetchone()[0], 2
            )

    def test_devices_and_sessions_track_the_newest_turn(self) -> None:
        pipeline = grounded_pipeline()
        self.turns.record(execute(pipeline, "first"))
        self.turns.record(execute(pipeline, "second"))
        with self.database.connect() as connection:
            devices = connection.execute("SELECT device_id FROM devices").fetchall()
            session = connection.execute("SELECT * FROM sessions").fetchone()
        self.assertEqual([row["device_id"] for row in devices], ["device-1"])
        self.assertEqual(session["last_turn_id"], "second")
        self.assertEqual(self.turns.newest().response.turn_id, "second")

    def test_foreign_keys_are_enforced_on_repository_connections(self) -> None:
        with self.database.connect() as connection, self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO turn_sources (turn_id, position, source_id, source_url, page_title, "
                "captured_at, chunk_id, retrieval_rank, cited) "
                "VALUES ('missing', 0, 's', 'u', 't', 'c', 'k', 1, 0)"
            )

    def test_clear_empties_every_table(self) -> None:
        self.turns.record(execute(grounded_pipeline(), "cleared"))
        self.turns.clear()
        self.assertIsNone(self.turns.newest())

    def test_non_wav_audio_reference_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            audio_to_bytes("https://example.com/reply.mp3")


if __name__ == "__main__":
    unittest.main()
