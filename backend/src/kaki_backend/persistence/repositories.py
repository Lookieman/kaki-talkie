# v1.3 | 18-Sep-2026 | WP6.6: store language_override (migration 0004).
# v1.2 | 13-Sep-2026 | WP5.1: store reply_language, reply_mode and render_outcome (migration 0003).
# v1.1 | 13-Sep-2026 | Resolve an action's previous turn; store previous_turn_id and outcome.
# v1.0 | 13-Sep-2026 | Store completed turns durably and replay them by turn_id.
"""Read and write completed turns as the durable idempotency record.

A completed turn is written in one transaction: device and session upserts,
the `turns` row, and one `turn_sources` row per response source. Replaying a
`turn_id` rebuilds the response from those rows and calls no port.

Reply audio is stored as the raw WAV bytes in a BLOB. The device response
carries it as a base64 data URL, so this module converts at the storage edge
in both directions and nothing base64-encoded reaches the database.

WP4.2 actions read this store too: `previous_content_turn` returns the turn
a repeat or print resolves to, and an action turn copies that turn's source
rows so its own replay rebuilds from its own rows.
"""

import json
import sqlite3
from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime, timezone

from kaki_backend.contracts.ports import LanguageEvidence
from kaki_backend.contracts.responses import SourceRecord, TurnResponse
from kaki_backend.contracts.turn_log import (
    EvidenceScore,
    SourceLink,
    TurnExecution,
    TurnLog,
    TurnTimings,
)
from kaki_backend.persistence.database import Database

AUDIO_DATA_URL_PREFIX = "data:audio/wav;base64,"


@dataclass(frozen=True)
class StoredTurn:
    """A completed turn as stored: its response, diagnostics and replay history."""

    response: TurnResponse
    log: TurnLog
    replay_count: int
    completed_at: str


def audio_to_bytes(reply_audio: str | None) -> bytes | None:
    """Decode a WAV data URL to raw bytes for storage.

    Raises ValueError for any other reference form: storing it would break
    byte-identical replay, so a new audio format needs its own migration.
    """
    if reply_audio is None:
        return None
    if not reply_audio.startswith(AUDIO_DATA_URL_PREFIX):
        raise ValueError("Only WAV data URLs can be stored as reply audio.")
    return b64decode(reply_audio[len(AUDIO_DATA_URL_PREFIX):], validate=True)


def audio_to_data_url(audio: bytes | None) -> str | None:
    """Encode stored WAV bytes as the data URL the device contract carries."""
    if audio is None:
        return None
    return AUDIO_DATA_URL_PREFIX + b64encode(audio).decode("ascii")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class TurnRepository:
    """Persist completed turns and serve them back by turn_id."""

    def __init__(self, database: Database) -> None:
        """Use the given migrated database for every read and write."""
        self.database = database

    def record(self, execution: TurnExecution) -> str:
        """Store one completed turn atomically and return its completion timestamp.

        Raises ValueError when the log's source links do not align with the
        response sources, or when the reply audio is not a WAV data URL.
        Raises `sqlite3.IntegrityError` when the turn_id is already stored.
        """
        response, log = execution.response, execution.log
        if len(log.source_links) != len(response.sources):
            raise ValueError("Every response source needs exactly one source link.")
        audio = audio_to_bytes(response.reply_audio)
        completed_at = _utc_now()
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "INSERT INTO devices (device_id, first_seen_at, last_seen_at) "
                    "VALUES (?, ?, ?) ON CONFLICT (device_id) "
                    "DO UPDATE SET last_seen_at = excluded.last_seen_at",
                    (log.device_id, completed_at, completed_at),
                )
                connection.execute(
                    "INSERT INTO sessions (session_id, device_id, started_at, last_turn_id, "
                    "last_completed_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT (session_id) "
                    "DO UPDATE SET last_turn_id = excluded.last_turn_id, "
                    "last_completed_at = excluded.last_completed_at",
                    (log.session_id, log.device_id, completed_at, response.turn_id,
                     completed_at),
                )
                connection.execute(_INSERT_TURN, _turn_values(execution, audio, completed_at))
                for position, (source, link) in enumerate(
                    zip(response.sources, log.source_links)
                ):
                    stored = source.model_dump(mode="json")
                    connection.execute(
                        "INSERT INTO turn_sources (turn_id, position, source_id, source_url, "
                        "page_title, captured_at, source_updated_at, content_hash, chunk_id, "
                        "retrieval_rank, dense_score, cited) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (response.turn_id, position, link.source_id, stored["source_url"],
                         stored["page_title"], stored["captured_at"],
                         stored["source_updated_at"], stored["content_hash"], link.chunk_id,
                         link.retrieval_rank, link.dense_score, int(link.cited)),
                    )
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        return completed_at

    def replay(self, turn_id: str) -> TurnResponse | None:
        """Return the stored response and count the replay, or None when unknown."""
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                updated = connection.execute(
                    "UPDATE turns SET replay_count = replay_count + 1 WHERE turn_id = ?",
                    (turn_id,),
                ).rowcount
                stored = self._load(connection, turn_id) if updated else None
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        return stored.response if stored is not None else None

    def previous_content_turn(self, session_id: str) -> TurnExecution | None:  #v1.1
        """Return the newest `answered` or `refused` turn in the session, or None.

        `acted` and `failed` turns are skipped (runbook 9.1 WP4.2), so a
        second repeat, or a print after a repeat, resolves to the original
        answer. Reads the store, so it works after a restart.
        """
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT turn_id FROM turns WHERE session_id = ? "
                "AND state IN ('answered', 'refused') ORDER BY rowid DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            stored = self._load(connection, row["turn_id"]) if row is not None else None
        if stored is None:
            return None
        return TurnExecution(response=stored.response, log=stored.log)

    def find(self, turn_id: str) -> StoredTurn | None:
        """Return one stored turn without counting a replay."""
        with self.database.connect() as connection:
            return self._load(connection, turn_id)

    def newest(self) -> StoredTurn | None:
        """Return the most recently executed turn, or None before any turn."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT turn_id FROM turns ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            return self._load(connection, row["turn_id"]) if row is not None else None

    def clear(self) -> None:
        """Delete every stored turn, session and device; for test isolation only."""
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for table in ("turn_sources", "turns", "sessions", "devices"):
                connection.execute(f"DELETE FROM {table}")
            connection.execute("COMMIT")

    @staticmethod
    def _load(connection: sqlite3.Connection, turn_id: str) -> StoredTurn | None:
        """Rebuild a stored turn from its `turns` row and ordered `turn_sources` rows."""
        row = connection.execute("SELECT * FROM turns WHERE turn_id = ?", (turn_id,)).fetchone()
        if row is None:
            return None
        source_rows = connection.execute(
            "SELECT * FROM turn_sources WHERE turn_id = ? ORDER BY position", (turn_id,)
        ).fetchall()
        response = TurnResponse(
            turn_id=row["turn_id"],
            reply_audio=audio_to_data_url(row["reply_audio"]),
            reply_text=row["reply_text"],
            display_text=row["display_text"],
            slip_text=row["slip_text"],
            language=row["language"],
            state=row["state"],
            case_id=row["case_id"],
            sources=[
                SourceRecord(
                    source_url=source["source_url"], page_title=source["page_title"],
                    captured_at=source["captured_at"],
                    source_updated_at=source["source_updated_at"],
                    content_hash=source["content_hash"],
                )
                for source in source_rows
            ],
        )
        log = TurnLog(
            turn_id=row["turn_id"],
            device_id=row["device_id"],
            session_id=row["session_id"],
            state=row["state"],
            timings=TurnTimings.model_validate_json(row["timings_json"]),
            transcript=row["transcript"],
            intent=row["intent"],
            refusal_reason=row["refusal_reason"],
            best_dense_score=row["best_dense_score"],
            evidence_min_dense=row["evidence_min_dense"],
            stt_language=(
                LanguageEvidence.model_validate_json(row["stt_language_json"])
                if row["stt_language_json"] is not None else None
            ),
            stt_error=row["stt_error"],
            llm_error=row["llm_error"],
            tts_error=row["tts_error"],
            retrieval_error=row["retrieval_error"],
            normalised_query=row["normalised_query"],
            retrieval_evidence=[
                EvidenceScore.model_validate(entry)
                for entry in json.loads(row["retrieval_evidence_json"])
            ],
            cited_source_id=row["cited_source_id"],
            llm_cited_index=row["llm_cited_index"],
            source_links=[
                SourceLink(
                    source_id=source["source_id"], chunk_id=source["chunk_id"],
                    retrieval_rank=source["retrieval_rank"],
                    dense_score=source["dense_score"], cited=bool(source["cited"]),
                )
                for source in source_rows
            ],
            previous_turn_id=row["previous_turn_id"],  #v1.1
            action_outcome=row["action_outcome"],  #v1.1
            reply_language=row["reply_language"],  #v1.2
            reply_mode=row["reply_mode"],  #v1.2
            render_outcome=row["render_outcome"],  #v1.2
            language_override=row["language_override"],  #v1.3
        )
        return StoredTurn(
            response=response, log=log,
            replay_count=row["replay_count"], completed_at=row["completed_at"],
        )


_INSERT_TURN = (
    "INSERT INTO turns (turn_id, session_id, device_id, state, intent, refusal_reason, "
    "transcript, stt_language_json, language, reply_text, display_text, slip_text, "
    "reply_audio, case_id, stt_error, llm_error, tts_error, retrieval_error, "
    "normalised_query, best_dense_score, evidence_min_dense, cited_source_id, "
    "llm_cited_index, timings_json, retrieval_evidence_json, completed_at, "
    "previous_turn_id, action_outcome, reply_language, reply_mode, render_outcome, "  #v1.2
    "language_override) "  #v1.3
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
    "?, ?, ?, ?)"
)


def _turn_values(execution: TurnExecution, audio: bytes | None, completed_at: str) -> tuple:
    """Order one execution's fields to match `_INSERT_TURN`."""
    response, log = execution.response, execution.log
    return (
        response.turn_id, log.session_id, log.device_id, response.state.value, log.intent,
        log.refusal_reason, log.transcript,
        log.stt_language.model_dump_json() if log.stt_language is not None else None,
        response.language, response.reply_text, response.display_text, response.slip_text,
        audio, response.case_id, log.stt_error, log.llm_error, log.tts_error,
        log.retrieval_error, log.normalised_query, log.best_dense_score,
        log.evidence_min_dense, log.cited_source_id, log.llm_cited_index,
        log.timings.model_dump_json(),
        json.dumps([entry.model_dump(mode="json") for entry in log.retrieval_evidence]),
        completed_at, log.previous_turn_id, log.action_outcome,  #v1.1
        log.reply_language, log.reply_mode, log.render_outcome,  #v1.2
        log.language_override,  #v1.3
    )
