# v1.1 | 24-Sep-2026 | Pitch receipt page: read the most recent booking turn.
# v1.0 | 18-Sep-2026 | WP6.6 admin state: per-device reply language and the push queue.
"""Read and write the demo admin surface's state (design.md 5.5).

Two responsibilities, both plain SQLite and nothing else:

- `device_config`: the per-device reply-language override. `reply_language_for`
  is the read the turn pipeline makes once per transcribed turn; an absent row
  reads `auto`, which returns the decision to the section 6.4 policy.
- `pending_messages`: the seeded canned nudges. `push` marks one queued for
  one named device; `take_due` is the pending endpoint's atomic
  fetch-and-mark, so a 3-second poll delivers a push exactly once (the
  design.md 5.4 delivery-state rule, at-most-once). Only the next push
  re-arms a delivered message; nothing resets on a timer.

A third, read-only responsibility serves the pitch's receipt page:
`latest_booking` reads the newest booking turn from the `turns` table the
turn repository writes, whichever device made it. It never writes there.

No route through this module touches the turn pipeline, calls a model or
synthesises audio: push audio is pre-synthesised fixture WAV, read from the
packaged fixtures directory and handed over as the same data-URL form reply
audio uses.
"""

from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files

from kaki_backend.persistence.database import Database

REPLY_LANGUAGES = ("en", "ms", "auto")
AUDIO_DATA_URL_PREFIX = "data:audio/wav;base64,"


class UnknownMessage(ValueError):
    """Signal a push for a message_key that was never seeded."""


@dataclass(frozen=True)
class MessageState:
    """One canned message's row, as the admin state view reports it."""

    message_key: str
    state: str
    target_device_id: str | None
    pushed_at: str | None
    delivered_at: str | None
    delivered_count: int


@dataclass(frozen=True)
class DueMessage:
    """One delivered nudge, in the language the target device is configured for."""

    message_id: str
    text: str
    language: str
    audio: str | None
    pushed_at: str | None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _fixture_data_url(fixture_name: str) -> str | None:
    """Return the packaged fixture as a WAV data URL, or None when not captured yet.

    The two push fixtures are owner-captured (`wp6_6_evidence.sh
    --capture-fixtures`). Until they exist, a push still delivers its text;
    the tier B check is what insists on the audio.
    """
    try:
        audio = files("kaki_backend").joinpath("fixtures", fixture_name).read_bytes()
    except (FileNotFoundError, OSError):
        return None
    if not audio:
        return None
    return AUDIO_DATA_URL_PREFIX + b64encode(audio).decode("ascii")


@dataclass(frozen=True)
class LatestBooking:  #v1.1
    """The newest booking turn: its reference, completion time, slip body and device."""

    case_id: str
    completed_at: str
    slip_text: str
    device_id: str


class AdminStore:
    """Own the admin tables; every method is one short transaction."""

    def __init__(self, database: Database) -> None:
        """Bind to the application's database; no I/O here."""
        self._database = database

    # -- per-device reply language ---------------------------------------

    def set_reply_language(self, device_id: str, reply_language: str) -> None:
        """Upsert one device's override; `auto` is stored, meaning policy decides.

        Raises ValueError for an unknown language or a blank device_id, before
        any write, so a bad request changes nothing (WP6-AT-17's spirit).
        """
        if reply_language not in REPLY_LANGUAGES:
            raise ValueError(f"reply_language must be one of {REPLY_LANGUAGES}.")
        if not device_id.strip():
            raise ValueError("device_id must not be blank.")
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO device_config (device_id, reply_language, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT (device_id) DO UPDATE SET "
                "reply_language = excluded.reply_language, updated_at = excluded.updated_at",
                (device_id.strip(), reply_language, _utc_now()),
            )
            connection.execute("COMMIT")

    def reply_language_for(self, device_id: str) -> str:
        """Return `en`, `ms` or `auto` for one device; the pipeline's per-turn read."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT reply_language FROM device_config WHERE device_id = ?", (device_id,)
            ).fetchone()
        return row["reply_language"] if row is not None else "auto"

    def config_rows(self) -> list[dict[str, str]]:
        """Return every configured device, for the admin state view."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT device_id, reply_language, updated_at FROM device_config "
                "ORDER BY device_id"
            ).fetchall()
        return [dict(row) for row in rows]

    # -- the push queue ---------------------------------------------------

    def push(self, message_key: str, device_id: str) -> MessageState:
        """Mark one seeded message queued for one named device.

        Re-pushing re-arms a delivered message; that is the only reset
        (runbook 11.1 WP6.6). Raises UnknownMessage for an unseeded key and
        ValueError for a blank device_id, before any write.
        """
        if not device_id.strip():
            raise ValueError("device_id must not be blank; every admin write names its target.")
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE pending_messages SET state = 'queued', target_device_id = ?, "
                "pushed_at = ?, delivered_at = NULL WHERE message_key = ?",
                (device_id.strip(), _utc_now(), message_key),
            ).rowcount
            connection.execute("COMMIT")
        if not updated:
            raise UnknownMessage(f"no seeded message is named {message_key!r}.")
        return self.message_states()[0]

    def take_due(self, device_id: str) -> list[DueMessage]:
        """Atomically hand over and mark delivered every message queued for `device_id`.

        One transaction selects and marks, so concurrent 3-second polls cannot
        both receive the same push. The language follows the device's
        configuration: `ms` delivers the Malay body and audio, `en` and `auto`
        the English (owner decision, 18-Sep-2026).
        """
        if not device_id.strip():
            return []
        delivered: list[DueMessage] = []
        with self._database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT message_key, body_en, body_ms, audio_fixture_en, audio_fixture_ms, "
                "pushed_at FROM pending_messages WHERE state = 'queued' "
                "AND target_device_id = ?",
                (device_id,),
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE pending_messages SET state = 'delivered', delivered_at = ?, "
                    "delivered_count = delivered_count + 1 WHERE message_key = ?",
                    (_utc_now(), row["message_key"]),
                )
            connection.execute("COMMIT")
        language_row = self.reply_language_for(device_id)
        language = "ms" if language_row == "ms" else "en"
        for row in rows:
            body = row["body_ms"] if language == "ms" else row["body_en"]
            fixture = row["audio_fixture_ms"] if language == "ms" else row["audio_fixture_en"]
            delivered.append(DueMessage(
                message_id=row["message_key"], text=body, language=language,
                audio=_fixture_data_url(fixture), pushed_at=row["pushed_at"],
            ))
        return delivered

    def message_states(self) -> list[MessageState]:
        """Return every seeded message's delivery state, for the admin state view."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT message_key, state, target_device_id, pushed_at, delivered_at, "
                "delivered_count FROM pending_messages ORDER BY message_key"
            ).fetchall()
        return [MessageState(**dict(row)) for row in rows]

    # -- the receipt page ------------------------------------------------

    def latest_booking(self) -> LatestBooking | None:  #v1.1
        """Return the most recent turn that carried a booking reference, or None.

        Only a WP6.7 booking sets `case_id`, so the newest row with one is the
        latest booking from any device - the Pi or the simulator. Read-only.
        """
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT case_id, completed_at, slip_text, device_id FROM turns "
                "WHERE case_id IS NOT NULL ORDER BY completed_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        return LatestBooking(**dict(row)) if row is not None else None
