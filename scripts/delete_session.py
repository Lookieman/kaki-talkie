# v1.0 | 13-Sep-2026 | WP4.5 delete one whole stored session on request (ADR-0008 decision 3).
"""Delete one whole session from the KaKi-Talkie database on request.

Makes the third-party retention rule executable (runbook 9.1 WP4.5 "Storage
and retention", ADR-0008). A session recorded with a person other than the
owner is deleted whole: its `turn_sources` rows, its turns (action turns
included) and its `sessions` row. The `devices` row stays; it holds no speech.

Dry run by default: the script prints what it would delete, with row counts
and byte totals, and changes nothing. `--apply` performs the delete in one
transaction.

Safety rules:
- `--apply` refuses unless a backup set under `$KAKI_DATA_ROOT/backups/`
  was created after the session's last turn, so the delete can be undone.
  The dry run reports the same check without refusing.
- It refuses when a turn outside the session points into it through
  `previous_turn_id`. Action resolution stays inside one session, so this
  signals a damaged database.
- Deletes run in dependency order: `turn_sources`, then action turns, then
  the turns they point at, then the session row. No action turn outlives the
  answer it references, so `foreign_keys=ON` is never violated.

The script never touches backup sets or evidence files. Every backup set
created after the session's first turn still holds it; the script lists them.
Remove those sets and evidence files that name the session by hand, then take
a fresh backup set with `scripts/backup_sqlite.sh`.

Reads `KAKI_DATA_ROOT` (required, absolute) and `KAKI_SQLITE_PATH` (optional,
absolute), like the backend. It may run while the backend runs; SQLite waits
up to 5 s for a lock.

Exit status: 0 when the dry run or delete succeeds; 1 when a safety rule
refuses or the delete fails; 2 on a usage or configuration error, including an
unknown session.
"""

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kaki_backend.config import StorageSettings

BUSY_TIMEOUT_SECONDS = 5.0
MANIFEST_NAME = "manifest.txt"

# Byte totals over the columns that carry speech, text or audio.
SESSION_SUMMARY_SQL = """
SELECT
    COUNT(*) AS turns,
    COALESCE(SUM(previous_turn_id IS NOT NULL), 0) AS action_turns,
    COALESCE(SUM(LENGTH(reply_audio)), 0) AS reply_audio_bytes,
    COALESCE(SUM(LENGTH(CAST(transcript AS BLOB))), 0) AS transcript_bytes,
    COALESCE(SUM(LENGTH(CAST(reply_text AS BLOB)) + LENGTH(CAST(display_text AS BLOB))
                 + LENGTH(CAST(slip_text AS BLOB))), 0) AS reply_text_bytes,
    MIN(completed_at) AS first_completed_at,
    MAX(completed_at) AS last_completed_at
FROM turns WHERE session_id = ?
"""
SOURCE_COUNT_SQL = (
    "SELECT COUNT(*) FROM turn_sources WHERE turn_id IN "
    "(SELECT turn_id FROM turns WHERE session_id = ?)"
)
OUTSIDE_REFERENCES_SQL = (
    "SELECT turn_id FROM turns WHERE session_id != ? AND previous_turn_id IN "
    "(SELECT turn_id FROM turns WHERE session_id = ?)"
)
DELETE_STATEMENTS = (
    ("turn_sources", "DELETE FROM turn_sources WHERE turn_id IN "
                     "(SELECT turn_id FROM turns WHERE session_id = ?)"),
    ("action turns", "DELETE FROM turns WHERE session_id = ? AND previous_turn_id IS NOT NULL"),
    ("turns", "DELETE FROM turns WHERE session_id = ?"),
    ("sessions", "DELETE FROM sessions WHERE session_id = ?"),
)


@dataclass(frozen=True)
class BackupSet:
    """One backup set directory and the creation time its manifest records."""

    path: Path
    created_utc: datetime


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp with an offset or a trailing Z."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_backup_sets(backups_directory: Path) -> list[BackupSet]:
    """Return every completed backup set with a readable `created_utc`, oldest first.

    Directories without a manifest, including `.partial` leftovers, are skipped.
    """
    if not backups_directory.is_dir():
        return []
    found = []
    for directory in sorted(backups_directory.iterdir()):
        manifest = directory / MANIFEST_NAME
        if directory.name.endswith(".partial") or not manifest.is_file():
            continue
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.startswith("created_utc="):
                try:
                    created = parse_timestamp(line.split("=", 1)[1])
                except ValueError:
                    break
                found.append(BackupSet(directory, created))
                break
    return sorted(found, key=backup_created)


def backup_created(backup: BackupSet) -> datetime:
    """Sort key: a backup set's creation time."""
    return backup.created_utc


def connect(database: Path) -> sqlite3.Connection:
    """Open the live database with the backend's foreign-key and lock settings."""
    connection = sqlite3.connect(database, isolation_level=None, timeout=BUSY_TIMEOUT_SECONDS)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def build_parser() -> argparse.ArgumentParser:
    """Describe the session selection and the apply switch."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--session-id", required=True, help="session_id to delete whole")
    parser.add_argument(
        "--apply", action="store_true",
        help="Perform the delete. Without it the script only reports (dry run).",
    )
    return parser


def print_plan(session_id: str, summary: sqlite3.Row, source_rows: int) -> None:
    """Print the rows and bytes the delete would remove."""
    print(f"Session: {session_id}")
    print(f"  turns: {summary['turns']} (action turns: {summary['action_turns']})")
    print(f"  turn_sources rows: {source_rows}")
    print("  sessions rows: 1")
    print(f"  reply_audio bytes: {summary['reply_audio_bytes']}")
    print(f"  transcript bytes: {summary['transcript_bytes']}")
    print(f"  reply, display and slip text bytes: {summary['reply_text_bytes']}")
    print(f"  first turn completed_at: {summary['first_completed_at']}")
    print(f"  last turn completed_at: {summary['last_completed_at']}")


def delete_session(connection: sqlite3.Connection, session_id: str) -> dict[str, int]:
    """Delete one session in dependency order inside one transaction; return rows per step.

    Rolls back and re-raises `sqlite3.Error` if any statement fails.
    """
    deleted: dict[str, int] = {}
    connection.execute("BEGIN IMMEDIATE")
    try:
        for label, statement in DELETE_STATEMENTS:
            deleted[label] = connection.execute(statement, (session_id,)).rowcount
        connection.execute("COMMIT")
    except sqlite3.Error:
        connection.execute("ROLLBACK")
        raise
    return deleted


def run(args: argparse.Namespace) -> int:
    """Report, check and optionally delete one session; return the exit status."""
    try:
        storage = StorageSettings.from_environment()
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    database = Path(storage.path)
    if not database.is_file():
        print(f"FAIL: the database does not exist: {database}", file=sys.stderr)
        return 2
    # StorageSettings has already required an absolute KAKI_DATA_ROOT.
    backups_directory = Path(os.environ["KAKI_DATA_ROOT"]) / "backups"

    with closing(connect(database)) as connection:
        session = connection.execute(
            "SELECT session_id FROM sessions WHERE session_id = ?", (args.session_id,)
        ).fetchone()
        if session is None:
            print(f"FAIL: no session {args.session_id} in {database}", file=sys.stderr)
            return 2
        summary = connection.execute(SESSION_SUMMARY_SQL, (args.session_id,)).fetchone()
        source_rows = connection.execute(SOURCE_COUNT_SQL, (args.session_id,)).fetchone()[0]
        print(f"Database: {database}")
        print_plan(args.session_id, summary, source_rows)

        outside = connection.execute(
            OUTSIDE_REFERENCES_SQL, (args.session_id, args.session_id)
        ).fetchall()
        if outside:
            names = ", ".join(row["turn_id"] for row in outside)
            print(f"FAIL: turns outside the session point into it: {names}", file=sys.stderr)
            return 1

        backups = read_backup_sets(backups_directory)
        last_turn = summary["last_completed_at"]
        first_turn = summary["first_completed_at"]
        newer = backups
        holding = backups
        if last_turn is not None:
            newer = [backup for backup in backups
                     if backup.created_utc > parse_timestamp(last_turn)]
            holding = [backup for backup in backups
                       if backup.created_utc > parse_timestamp(first_turn)]
        print(f"Backup sets newer than the last turn: {len(newer)}")
        for backup in holding:
            print(f"  holds this session: {backup.path}")

        if not args.apply:
            if not newer:
                print("WARN: no backup set is newer than the last turn; --apply will refuse "
                      "until scripts/backup_sqlite.sh has run.", file=sys.stderr)
            print("Dry run: nothing deleted. Rerun with --apply to delete.")
            return 0
        if not newer:
            print("FAIL: no backup set is newer than the session's last turn. "
                  "Run scripts/backup_sqlite.sh first.", file=sys.stderr)
            return 1
        try:
            deleted = delete_session(connection, args.session_id)
        except sqlite3.Error as error:
            print(f"FAIL: the delete was rolled back: {error}", file=sys.stderr)
            return 1

    for label, _ in DELETE_STATEMENTS:
        print(f"deleted {label}: {deleted[label]}")
    print("PASS: session deleted.")
    print("Next: remove the backup sets listed above and evidence files that name the "
          "session, then run scripts/backup_sqlite.sh.")
    return 0


def main() -> int:
    """Parse arguments and run the session deletion."""
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
