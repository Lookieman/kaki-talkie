# v1.0 | 13-Sep-2026 | Verify the WP4.5 backup set against a disposable database.
"""Deterministic tests for `scripts/backup_sqlite.sh` (runbook 9.2 WP4.5 Test 1).

Every test builds a disposable data root under the system temporary directory:
a migrated database with an answer and a repeat that points at it, a small
corpus and index, and decoy files that must never be copied. No service, model
or network is used, and the owner's data root is never read.
"""

import hashlib
import os
import sqlite3
import stat
import subprocess
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from kaki_test_env import canned_environment

from kaki_backend.persistence.database import Database

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/backup_sqlite.sh"
EXPECTED_SCHEMA_VERSION = 2
NOW = "2026-09-13T05:00:00.000+00:00"
TIMINGS = '{"overall_ms": 1.0}'


def seed_database(path: Path) -> None:
    """Create a migrated database holding one answer, one repeat and one source row."""
    Database.open(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO devices VALUES ('device-1', ?, ?)", (NOW, NOW))
        connection.execute(
            "INSERT INTO sessions (session_id, device_id, started_at) VALUES ('session-1', "
            "'device-1', ?)", (NOW,),
        )
        insert_turn(connection, "turn-answer", "answered", None)
        insert_turn(connection, "turn-repeat", "acted", "turn-answer")
        connection.execute(
            "INSERT INTO turn_sources (turn_id, position, source_id, source_url, page_title, "
            "captured_at, chunk_id, retrieval_rank, cited) VALUES ('turn-answer', 0, "
            "'cdc', 'https://vouchers.cdc.gov.sg/', 'CDC', '2026-09-10', 'cdc-0', 1, 1)"
        )
        connection.commit()


def insert_turn(connection: sqlite3.Connection, turn_id: str, state: str,
                previous_turn_id: str | None) -> None:
    """Insert one minimal turn row with a small reply-audio BLOB."""
    connection.execute(
        "INSERT INTO turns (turn_id, session_id, device_id, state, language, reply_text, "
        "display_text, slip_text, reply_audio, timings_json, retrieval_evidence_json, "
        "completed_at, previous_turn_id) VALUES (?, 'session-1', 'device-1', ?, 'en', "
        "'reply', 'reply', '', ?, ?, '[]', ?, ?)",
        (turn_id, state, b"RIFF-audio", TIMINGS, NOW, previous_turn_id),
    )


def build_data_root(root: Path) -> None:
    """Lay out a data root with a database, corpus, index and excluded decoys."""
    seed_database(root / "sqlite/kaki.db")
    (root / "corpus/snapshots/2026-09-10").mkdir(parents=True)
    (root / "corpus/snapshots/2026-09-10/cdc.md").write_text("CDC vouchers\n", encoding="utf-8")
    (root / "corpus/processed").mkdir(parents=True)
    (root / "corpus/processed/chunks.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "chroma").mkdir()
    (root / "chroma/chroma.sqlite3").write_bytes(b"index")
    for decoy in ("wp4.5/evidence.abc/transcript.txt", "logs/backend.log", "models/m.bin"):
        (root / decoy).parent.mkdir(parents=True, exist_ok=True)
        (root / decoy).write_text("never copied\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=never-copied\n", encoding="utf-8")


def run_backup(root: Path, *arguments: str) -> subprocess.CompletedProcess:
    """Run the script with a canned environment and only this data root."""
    environment = {**os.environ, **canned_environment(), "KAKI_DATA_ROOT": str(root)}
    environment.pop("KAKI_SQLITE_PATH", None)
    return subprocess.run(
        ["bash", str(SCRIPT), *arguments], capture_output=True, text=True, env=environment,
    )


def set_directories(root: Path) -> list[Path]:
    """Return completed backup set directories, oldest first."""
    return sorted(path for path in (root / "backups").iterdir() if path.is_dir())


def read_manifest(set_directory: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Split a manifest into its fields and its per-file SHA-256 values."""
    fields: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for line in (set_directory / "manifest.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("sha256:"):
            relative, digest = line[len("sha256:"):].rsplit("=", 1)
            hashes[relative] = digest
        else:
            name, value = line.split("=", 1)
            fields[name] = value
    return fields, hashes


def files_in(set_directory: Path) -> list[str]:
    """Return every file path in a set, relative and sorted."""
    return sorted(
        str(path.relative_to(set_directory)) for path in set_directory.rglob("*") if path.is_file()
    )


def sha256(path: Path) -> str:
    """Return the hex SHA-256 of one file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def query_backup(database: Path, statement: str) -> list[tuple]:
    """Read a backup database through an immutable URI, leaving no sidecar files."""
    with closing(sqlite3.connect(f"file:{database}?immutable=1", uri=True)) as connection:
        return connection.execute(statement).fetchall()


class BackupSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory(prefix="kaki-backup-test-")
        self.root = Path(self.scratch.name)
        build_data_root(self.root)
        self.result = run_backup(self.root)

    def tearDown(self) -> None:
        self.scratch.cleanup()

    def test_run_succeeds_and_writes_one_complete_set(self) -> None:
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        sets = set_directories(self.root)
        self.assertEqual(len(sets), 1)
        self.assertRegex(sets[0].name, r"^\d{8}T\d{6}Z$")
        self.assertIn("PASS", self.result.stdout)

    def test_modes_are_owner_only(self) -> None:
        set_directory = set_directories(self.root)[0]
        self.assertEqual(stat.S_IMODE(set_directory.stat().st_mode), 0o700)
        for path in set_directory.rglob("*"):
            expected = 0o700 if path.is_dir() else 0o600
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), expected, str(path))

    def test_backup_database_is_consistent(self) -> None:
        database = set_directories(self.root)[0] / "kaki.db"
        self.assertEqual(query_backup(database, "PRAGMA integrity_check"), [("ok",)])
        self.assertEqual(query_backup(database, "PRAGMA foreign_key_check"), [])
        self.assertEqual(query_backup(database, "PRAGMA user_version"),
                         [(EXPECTED_SCHEMA_VERSION,)])
        self.assertEqual(query_backup(database, "SELECT COUNT(*) FROM turns"), [(2,)])
        self.assertEqual(
            query_backup(database, "SELECT reply_audio FROM turns WHERE turn_id = 'turn-repeat'"),
            [(b"RIFF-audio",)],
        )

    def test_manifest_records_fields_and_matching_hashes(self) -> None:
        set_directory = set_directories(self.root)[0]
        fields, hashes = read_manifest(set_directory)
        self.assertEqual(fields["user_version"], str(EXPECTED_SCHEMA_VERSION))
        self.assertEqual(fields["turns"], "2")
        self.assertEqual(fields["integrity_check"], "ok")
        self.assertIn(fields["ingest_running"], {"true", "false", "unknown"})
        self.assertRegex(fields["git_commit"], r"^([0-9a-f]{40}|unknown)$")
        self.assertRegex(fields["created_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        listed = sorted(hashes)
        self.assertEqual(listed, [name for name in files_in(set_directory)
                                  if name != "manifest.txt"])
        for relative, digest in hashes.items():
            self.assertEqual(sha256(set_directory / relative), digest, relative)

    def test_set_holds_database_corpus_and_index_only(self) -> None:
        names = files_in(set_directories(self.root)[0])
        self.assertEqual(names, [
            "chroma/chroma.sqlite3", "corpus/processed/chunks.jsonl",
            "corpus/snapshots/2026-09-10/cdc.md", "kaki.db", "manifest.txt",
        ])

    def test_reading_the_set_leaves_no_sidecar_files(self) -> None:
        set_directory = set_directories(self.root)[0]
        query_backup(set_directory / "kaki.db", "SELECT COUNT(*) FROM turns")
        self.assertFalse(any(name.endswith(("-wal", "-shm")) for name in files_in(set_directory)))
        self.assertFalse(list((self.root / "backups").glob("*.partial")))

    def test_second_run_writes_a_new_set_and_leaves_the_first_untouched(self) -> None:
        first = set_directories(self.root)[0]
        before = {name: (sha256(first / name), (first / name).stat().st_mtime_ns)
                  for name in files_in(first)}
        time.sleep(1.1)  # set names have one-second resolution
        second_result = run_backup(self.root)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        sets = set_directories(self.root)
        self.assertEqual(len(sets), 2)
        self.assertEqual(sets[0], first)
        after = {name: (sha256(first / name), (first / name).stat().st_mtime_ns)
                 for name in files_in(first)}
        self.assertEqual(after, before)


class BackupCliTests(unittest.TestCase):
    def test_help_prints_usage_and_exits_zero(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertIn("manifest.txt", result.stdout)

    def test_unknown_argument_is_a_usage_error(self) -> None:
        result = subprocess.run(["bash", str(SCRIPT), "--force"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_relative_data_root_is_a_configuration_error(self) -> None:
        result = run_backup(Path("relative/root"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("KAKI_DATA_ROOT", result.stderr)

    def test_missing_database_is_a_configuration_error_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kaki-backup-test-") as scratch:
            root = Path(scratch)
            (root / "corpus").mkdir()
            (root / "chroma").mkdir()
            result = run_backup(root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("database", result.stderr)
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
