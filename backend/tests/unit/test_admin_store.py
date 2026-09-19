# v1.1 | 19-Sep-2026 | The null-audio test names a fixture that cannot exist, instead of
#                      relying on the owner-captured fixtures being absent from the tree.
# v1.0 | 18-Sep-2026 | WP6.6 admin store: config, push, at-most-once delivery, seeding.
"""Prove the admin state rules on disposable databases; no routes, no network.

The delivery rule matters most: `take_due` marks in the transaction that
hands over, so two polls can never both receive one push (WP6-AT-16's
backend half), and only a new push re-arms a delivered message.
"""

import tempfile
import unittest
from pathlib import Path

from kaki_backend.persistence.admin_store import (
    AUDIO_DATA_URL_PREFIX,
    AdminStore,
    UnknownMessage,
)
from kaki_backend.persistence.database import Database

SEEDED_KEY = "cdc-vouchers-available"


class AdminStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "kaki.db"
        self.store = AdminStore(Database.open(self.path))

    # -- reply language ----------------------------------------------------

    def test_absent_row_reads_auto_and_set_get_round_trips(self):
        self.assertEqual(self.store.reply_language_for("never-seen"), "auto")
        for language in ("ms", "en", "auto"):
            self.store.set_reply_language("kaki-pi-01", language)
            self.assertEqual(self.store.reply_language_for("kaki-pi-01"), language)
        self.assertEqual(len(self.store.config_rows()), 1)

    def test_config_survives_a_reopened_database(self):
        self.store.set_reply_language("kaki-pi-01", "ms")
        reopened = AdminStore(Database.open(self.path))
        self.assertEqual(reopened.reply_language_for("kaki-pi-01"), "ms")

    def test_invalid_language_and_blank_device_change_nothing(self):
        with self.assertRaises(ValueError):
            self.store.set_reply_language("kaki-pi-01", "zh")
        with self.assertRaises(ValueError):
            self.store.set_reply_language("   ", "ms")
        self.assertEqual(self.store.config_rows(), [])

    # -- the push queue ------------------------------------------------------

    def test_migration_seeds_exactly_one_idle_message(self):
        states = self.store.message_states()
        self.assertEqual([state.message_key for state in states], [SEEDED_KEY])
        self.assertEqual(states[0].state, "idle")
        self.assertEqual(states[0].delivered_count, 0)

    def test_push_targets_one_device_and_take_due_delivers_exactly_once(self):
        self.store.push(SEEDED_KEY, "sim-1")
        self.assertEqual(self.store.take_due("pi-1"), [])          # wrong device
        first = self.store.take_due("sim-1")
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].message_id, SEEDED_KEY)
        self.assertIn("CDC vouchers", first[0].text)
        self.assertEqual(first[0].language, "en")
        for _ in range(20):                                        # the 3-second poll
            self.assertEqual(self.store.take_due("sim-1"), [])
        state = self.store.message_states()[0]
        self.assertEqual((state.state, state.delivered_count), ("delivered", 1))
        self.assertIsNotNone(state.delivered_at)

    def test_only_a_new_push_re_arms_and_the_count_accumulates(self):
        self.store.push(SEEDED_KEY, "sim-1")
        self.store.take_due("sim-1")
        self.assertEqual(self.store.take_due("sim-1"), [])
        self.store.push(SEEDED_KEY, "sim-1")
        self.assertEqual(self.store.message_states()[0].state, "queued")
        self.assertEqual(len(self.store.take_due("sim-1")), 1)
        self.assertEqual(self.store.message_states()[0].delivered_count, 2)

    def test_delivery_language_follows_the_device_config(self):
        self.store.set_reply_language("sim-ms", "ms")
        self.store.push(SEEDED_KEY, "sim-ms")
        malay = self.store.take_due("sim-ms")[0]
        self.assertEqual(malay.language, "ms")
        self.assertIn("baucar CDC", malay.text)
        for language in ("en", "auto"):
            self.store.set_reply_language("sim-2", language)
            self.store.push(SEEDED_KEY, "sim-2")
            delivered = self.store.take_due("sim-2")[0]
            self.assertEqual(delivered.language, "en", language)

    def test_unknown_message_and_blank_device_are_rejected_before_writing(self):
        with self.assertRaises(UnknownMessage):
            self.store.push("no-such-message", "sim-1")
        with self.assertRaises(ValueError):
            self.store.push(SEEDED_KEY, "  ")
        self.assertEqual(self.store.message_states()[0].state, "idle")

    def test_missing_audio_fixture_delivers_text_with_null_audio(self):
        # A push must still deliver its text when its fixture is not on disk.
        # The seeded row names a captured fixture, so the test names one that
        # cannot exist rather than depending on the tree.
        with self.store._database.connect() as connection:
            connection.execute(
                "UPDATE pending_messages SET audio_fixture_en = 'no_such_fixture.wav' "
                "WHERE message_key = ?", (SEEDED_KEY,),
            )
        self.store.push(SEEDED_KEY, "sim-1")
        delivered = self.store.take_due("sim-1")[0]
        self.assertIsNone(delivered.audio)
        self.assertIn("CDC vouchers", delivered.text)

    def test_an_existing_fixture_becomes_a_wav_data_url(self):
        with self.store._database.connect() as connection:
            connection.execute(
                "UPDATE pending_messages SET audio_fixture_en = 'canned_reply.wav' "
                "WHERE message_key = ?", (SEEDED_KEY,),
            )
        self.store.push(SEEDED_KEY, "sim-1")
        audio = self.store.take_due("sim-1")[0].audio
        self.assertIsNotNone(audio)
        self.assertTrue(audio.startswith(AUDIO_DATA_URL_PREFIX))


if __name__ == "__main__":
    unittest.main()
