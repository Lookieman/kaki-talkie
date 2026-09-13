-- v1.0 | 13-Sep-2026 | WP4.1 devices, sessions, turns and turn_sources.
--
-- Timestamps are ISO 8601 UTC text. The cases table is deliberately absent:
-- WP4.3 creates it in migration 0002 with cases.opened_by_turn_id referencing
-- turns, so no existing table needs a rebuild (ADR-0007).

CREATE TABLE devices (
    device_id      TEXT PRIMARY KEY,
    first_seen_at  TEXT NOT NULL,
    last_seen_at   TEXT NOT NULL
);

CREATE TABLE sessions (
    session_id         TEXT PRIMARY KEY,
    device_id          TEXT NOT NULL REFERENCES devices (device_id),
    started_at         TEXT NOT NULL,
    last_turn_id       TEXT,
    last_completed_at  TEXT
);

-- One row per completed turn: the nine public response fields plus the
-- internal turn log, so a replay and the debug view rebuild from the row.
CREATE TABLE turns (
    turn_id                  TEXT PRIMARY KEY,
    session_id               TEXT NOT NULL REFERENCES sessions (session_id),
    device_id                TEXT NOT NULL REFERENCES devices (device_id),
    state                    TEXT NOT NULL CHECK (
        state IN ('answered', 'refused', 'handed_off', 'acted', 'failed')
    ),
    intent                   TEXT,
    refusal_reason           TEXT,
    transcript               TEXT,
    stt_language_json        TEXT,
    language                 TEXT NOT NULL,
    reply_text               TEXT NOT NULL,
    display_text             TEXT NOT NULL,
    slip_text                TEXT NOT NULL,
    reply_audio              BLOB,
    case_id                  TEXT,
    stt_error                TEXT,
    llm_error                TEXT,
    tts_error                TEXT,
    retrieval_error          TEXT,
    normalised_query         TEXT,
    best_dense_score         REAL,
    evidence_min_dense       REAL,
    cited_source_id          TEXT,
    llm_cited_index          INTEGER,
    timings_json             TEXT NOT NULL,
    retrieval_evidence_json  TEXT NOT NULL,
    replay_count             INTEGER NOT NULL DEFAULT 0,
    completed_at             TEXT NOT NULL
);

CREATE INDEX turns_by_session ON turns (session_id);

-- One row per response source, in response order; position 0 is the cited
-- source on a grounded answer.
CREATE TABLE turn_sources (
    turn_id            TEXT NOT NULL REFERENCES turns (turn_id) ON DELETE CASCADE,
    position           INTEGER NOT NULL CHECK (position >= 0),
    source_id          TEXT NOT NULL,
    source_url         TEXT NOT NULL,
    page_title         TEXT NOT NULL,
    captured_at        TEXT NOT NULL,
    source_updated_at  TEXT,
    content_hash       TEXT,
    chunk_id           TEXT NOT NULL,
    retrieval_rank     INTEGER NOT NULL CHECK (retrieval_rank >= 1),
    dense_score        REAL,
    cited              INTEGER NOT NULL CHECK (cited IN (0, 1)),
    PRIMARY KEY (turn_id, position)
);
