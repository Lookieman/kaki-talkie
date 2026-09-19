# v1.0 | 18-Sep-2026 | WP6.6 wording seed: dry run, apply, delivery state untouched.
"""Prove the re-runnable seed against a disposable database.

The rule under test: wording changes flow from the script, never a migration,
and a re-seed between rehearsals must not touch the message's delivery state.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kaki_test_env import canned_environment

from kaki_backend.persistence.admin_store import AdminStore
from kaki_backend.persistence.database import Database

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/seed_push_message.py"
MESSAGE_KEY = "cdc-vouchers-available"


class SeedScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.data_root = Path(scratch.name)
        self.database_path = self.data_root / "sqlite/kaki.db"
        Database.open(self.database_path)

    def run_seed(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = {**os.environ, **canned_environment(),
                       "KAKI_DATA_ROOT": str(self.data_root)}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments], capture_output=True,
            text=True, timeout=60, env=environment, cwd=ROOT,
        )

    def mangle_wording(self) -> None:
        with Database(self.database_path).connect() as connection:
            connection.execute(
                "UPDATE pending_messages SET body_en = 'old words' WHERE message_key = ?",
                (MESSAGE_KEY,),
            )

    def body_en(self) -> str:
        with Database(self.database_path).connect() as connection:
            return connection.execute(
                "SELECT body_en FROM pending_messages WHERE message_key = ?", (MESSAGE_KEY,),
            ).fetchone()["body_en"]

    def test_help_and_the_freshly_migrated_row_needs_no_change(self):
        self.assertEqual(self.run_seed("--help").returncode, 0)
        completed = self.run_seed()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("No change", completed.stdout)

    def test_dry_run_reports_without_writing(self):
        self.mangle_wording()
        completed = self.run_seed()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Dry run", completed.stdout)
        self.assertEqual(self.body_en(), "old words")

    def test_apply_rewrites_the_wording_but_not_the_delivery_state(self):
        store = AdminStore(Database(self.database_path))
        store.push(MESSAGE_KEY, "sim-1")
        self.mangle_wording()
        completed = self.run_seed("--apply")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Seeded", completed.stdout)
        self.assertIn("CDC vouchers", self.body_en())
        state = store.message_states()[0]
        self.assertEqual((state.state, state.target_device_id), ("queued", "sim-1"))

    def test_a_missing_row_fails_with_guidance(self):
        with Database(self.database_path).connect() as connection:
            connection.execute("DELETE FROM pending_messages")
        completed = self.run_seed("--apply")
        self.assertEqual(completed.returncode, 2)
        self.assertIn("migration 0004", completed.stderr)


if __name__ == "__main__":
    unittest.main()
