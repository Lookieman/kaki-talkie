#!/usr/bin/env python3
# v1.0 | 18-Sep-2026 | Re-seed the WP6.6 canned push wording without a migration.
"""Write the canned push message's wording and audio fixture names.

The seeded wording is provisional (owner decision, 18-Sep-2026): the Singlish
and Auntie phrasing is still open, so the words live here, re-runnable, and
changing them never needs a schema migration. Migration 0004 creates the row;
this script updates it in place and keeps its delivery state untouched, so a
re-seed between rehearsals does not re-arm or reset anything.

Usage:

    source scripts/kaki_env.sh env
    python scripts/seed_push_message.py            # show what would change
    python scripts/seed_push_message.py --apply    # write it

Side effects with `--apply`: one UPDATE to `pending_messages` in the
database at `$KAKI_DATA_ROOT/sqlite/kaki.db` (or `$KAKI_SQLITE_PATH`).
Restart nothing: the pending endpoint reads the row per poll. Without
`--apply` the script only reports. Exit status: 0 on success or no change
needed, 2 on a usage or database error.
"""

import argparse
import sqlite3
import sys
from contextlib import closing

from kaki_backend.config import StorageSettings

MESSAGE_KEY = "cdc-vouchers-available"

# The provisional wording. Edit here, re-run with --apply, rehearse again.
BODY_EN = (
    "Good news: new CDC vouchers are available. "
    "Press the button to ask me about them."
)
BODY_MS = (
    "Berita baik: baucar CDC baharu sudah tersedia. "
    "Tekan butang untuk bertanya kepada saya."
)
AUDIO_FIXTURE_EN = "push_cdc_en.wav"
AUDIO_FIXTURE_MS = "push_cdc_ms.wav"


def build_parser() -> argparse.ArgumentParser:
    """Describe the one option; the default run is a dry report."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Write the wording; without this flag the script only reports",
    )
    return parser


def main() -> int:
    """Compare the stored row with this file's wording; update it on --apply."""
    arguments = build_parser().parse_args()
    try:
        path = StorageSettings.from_environment().path
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    desired = (BODY_EN, BODY_MS, AUDIO_FIXTURE_EN, AUDIO_FIXTURE_MS)
    try:
        with closing(sqlite3.connect(path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT body_en, body_ms, audio_fixture_en, audio_fixture_ms "
                "FROM pending_messages WHERE message_key = ?", (MESSAGE_KEY,),
            ).fetchone()
            if row is None:
                print(
                    f"FAIL: {path} has no {MESSAGE_KEY!r} row. Start the backend once "
                    "so migration 0004 seeds it, then re-run.", file=sys.stderr,
                )
                return 2
            if tuple(row) == desired:
                print(f"No change: {MESSAGE_KEY} already carries this wording.")
                return 0
            for name, stored, wanted in zip(row.keys(), tuple(row), desired):
                marker = " " if stored == wanted else "*"
                print(f"{marker} {name}: {stored!r}")
                if stored != wanted:
                    print(f"    -> {wanted!r}")
            if not arguments.apply:
                print("Dry run: re-run with --apply to write this.")
                return 0
            connection.execute(
                "UPDATE pending_messages SET body_en = ?, body_ms = ?, "
                "audio_fixture_en = ?, audio_fixture_ms = ? WHERE message_key = ?",
                (*desired, MESSAGE_KEY),
            )
            connection.commit()
    except sqlite3.Error as error:
        print(f"FAIL: cannot update {path}: {error}", file=sys.stderr)
        return 2
    print(f"Seeded: {MESSAGE_KEY} in {path}. Delivery state untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
