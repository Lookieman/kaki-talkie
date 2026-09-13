# v1.0 | 13-Sep-2026 | Verify WP4.5 whole-session deletion against a disposable database.
"""Deterministic tests for `scripts/delete_session.py` (ADR-0008 decision 3).

Each test builds a disposable data root with two sessions. The target session
holds an answer, a repeat that points at it through `previous_turn_id`, and a
source row; the other session must survive every run. Backup sets are faked
with a manifest only, because the script reads nothing else from them.
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from kaki_test_env import canned_environment

from kaki_backend.persistence.database import Database

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/delete_session.py"
TURN_TIME = "2026-09-13T05:00:00.000+00:00"
BEFORE_TURNS = "2026-09-13T04:00:00Z"
AFTER_TURNS = "2026-09-13T06:00:00Z"
TARGET = "session-third-party"
OTHER = "session-owner"


def insert_turn(connection: sqlite3.Connection, turn_id: str, session_id: str, state: str,
                previous_turn_id: str | None = None) -> None:
    """Insert one minimal turn with a ten-byte reply-audio BLOB."""
    connection.execute(
        "INSERT INTO turns (turn_id, session_id, device_id, state, transcript, language, "
        "reply_text, display_text, slip_text, reply_audio, timings_json, "
        "retrieval_evidence_json, completed_at, previous_turn_id) VALUES (?, ?, 'device-1', ?, "
        "'hello', 'en', 'reply', 'reply', 'slip', ?, '{}', '[]', ?, ?)",
        (turn_id, session_id, state, b"0123456789", TURN_TIME, previous_turn_id),
    )


def build_data_root(root: Path) -> Path:
    """Create a migrated database with the target and the other session; return its path."""
    path = root / "sqlite/kaki.db"
    Database.open(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO devices VALUES ('device-1', ?, ?)", (TURN_TIME, TURN_TIME))
        for session_id in (TARGET, OTHER):
            connection.execute(
                "INSERT INTO sessions (session_id, device_id, started_at) VALUES (?, "
                "'device-1', ?)", (session_id, TURN_TIME),
            )
        insert_turn(connection, "target-answer", TARGET, "answered")
        insert_turn(connection, "target-repeat", TARGET, "acted", "target-answer")
        insert_turn(connection, "other-answer", OTHER, "answered")
        connection.execute(
            "INSERT INTO turn_sources (turn_id, position, source_id, source_url, page_title, "
            "captured_at, chunk_id, retrieval_rank, cited) VALUES ('target-answer', 0, 'cdc', "
            "'https://vouchers.cdc.gov.sg/', 'CDC', '2026-09-10', 'cdc-0', 1, 1)"
        )
        connection.commit()
    return path


def fake_backup_set(root: Path, name: str, created_utc: str) -> None:
    """Write a backup set directory holding only a manifest."""
    directory = root / "backups" / name
    directory.mkdir(parents=True)
    (directory / "manifest.txt").write_text(
        f"format=kaki-backup-manifest/1\ncreated_utc={created_utc}\n", encoding="utf-8",
    )


def run_delete(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    """Run the script with a canned environment and only this data root."""
    environment = {**os.environ, **canned_environment(), "KAKI_DATA_ROOT": str(root)}
    environment.pop("KAKI_SQLITE_PATH", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True,
        env=environment,
    )


def scalar(database: Path, statement: str) -> object:
    """Return the first column of the first row of one query."""
    with closing(sqlite3.connect(database)) as connection:
        return connection.execute(statement).fetchone()[0]


class DeleteSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory(prefix="kaki-delete-test-")
        self.root = Path(self.scratch.name)
        self.database = build_data_root(self.root)

    def tearDown(self) -> None:
        self.scratch.cleanup()

    def turn_count(self, session_id: str) -> object:
        return scalar(self.database, f"SELECT COUNT(*) FROM turns WHERE session_id = '{session_id}'")

    def test_dry_run_reports_counts_and_bytes_and_deletes_nothing(self) -> None:
        result = run_delete(self.root, "--session-id", TARGET)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("turns: 2 (action turns: 1)", result.stdout)
        self.assertIn("turn_sources rows: 1", result.stdout)
        self.assertIn("reply_audio bytes: 20", result.stdout)
        self.assertIn("transcript bytes: 10", result.stdout)
        self.assertIn("Dry run: nothing deleted.", result.stdout)
        self.assertIn("--apply will refuse", result.stderr)
        self.assertEqual(self.turn_count(TARGET), 2)

    def test_apply_refuses_without_a_backup_set(self) -> None:
        result = run_delete(self.root, "--session-id", TARGET, "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("backup_sqlite.sh", result.stderr)
        self.assertEqual(self.turn_count(TARGET), 2)

    def test_apply_refuses_when_every_backup_predates_the_last_turn(self) -> None:
        fake_backup_set(self.root, "20260913T040000Z", BEFORE_TURNS)
        fake_backup_set(self.root, "20260913T070000Z.partial", AFTER_TURNS)
        result = run_delete(self.root, "--session-id", TARGET, "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.turn_count(TARGET), 2)

    def test_apply_deletes_the_whole_session_and_nothing_else(self) -> None:
        fake_backup_set(self.root, "20260913T060000Z", AFTER_TURNS)
        result = run_delete(self.root, "--session-id", TARGET, "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deleted action turns: 1", result.stdout)
        self.assertIn("deleted turns: 1", result.stdout)
        self.assertIn("holds this session", result.stdout)
        self.assertEqual(self.turn_count(TARGET), 0)
        self.assertEqual(scalar(self.database, "SELECT COUNT(*) FROM turn_sources"), 0)
        self.assertEqual(
            scalar(self.database, f"SELECT COUNT(*) FROM sessions WHERE session_id = '{TARGET}'"),
            0,
        )
        self.assertEqual(self.turn_count(OTHER), 1)
        self.assertEqual(scalar(self.database, "SELECT COUNT(*) FROM devices"), 1)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertTrue((self.root / "backups/20260913T060000Z/manifest.txt").exists())

    def test_refuses_when_a_turn_outside_the_session_points_into_it(self) -> None:
        fake_backup_set(self.root, "20260913T060000Z", AFTER_TURNS)
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            insert_turn(connection, "other-repeat", OTHER, "acted", "target-answer")
            connection.commit()
        result = run_delete(self.root, "--session-id", TARGET, "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("other-repeat", result.stderr)
        self.assertEqual(self.turn_count(TARGET), 2)

    def test_unknown_session_is_a_usage_error(self) -> None:
        result = run_delete(self.root, "--session-id", "session-missing")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no session", result.stderr)

    def test_help_documents_the_dry_run_default(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--apply", result.stdout)
        self.assertIn("Dry run by default", result.stdout)


if __name__ == "__main__":
    unittest.main()
