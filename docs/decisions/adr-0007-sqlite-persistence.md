# ADR 0007: SQLite persistence with standard-library migrations

Date: 13-Sep-2026

Status: accepted for WP4.1 by owner decision, 13-Sep-2026. Amended for WP4.2
(migration 0002), 13-Sep-2026. Implements the
SQLite state decision in design.md sections 2 and 14.

## Decision

The backend stores devices, sessions, completed turns and their provenance in
one SQLite file. The store is the only turn idempotency record; the WP1.2
process-memory cache is gone.

The following choices apply:

- **Mechanism.** Standard-library `sqlite3`. No ORM and no migration
  framework. The module lives at `backend/src/kaki_backend/persistence/`, the
  name design.md 18 fixes.
- **Location.** `$KAKI_DATA_ROOT/sqlite/kaki.db`. `KAKI_SQLITE_PATH` is an
  optional absolute override. `KAKI_DATA_ROOT` is required in every mode,
  canned included. Startup fails with a message naming the variable and the
  expected path. There is no in-memory fallback.
- **Migrations.** Numbered SQL files `NNNN_description.sql` in
  `persistence/migrations/`. Migrations run at backend start, each in its own
  transaction that also sets `PRAGMA user_version`. A database newer than the
  build refuses to open. A shipped migration is never edited.
- **Idempotency key.** `turn_id` alone, as in WP1. The public response and
  the WP1 schema snapshot are unchanged.

## Connection pragmas

Every connection applies these pragmas when it opens:

```text
+----------------------------+--------------------------------------------------+
| Pragma                     | Why                                              |
+----------------------------+--------------------------------------------------+
| journal_mode = WAL         | Readers (health, debug, sqlite3 CLI) do not      |
|                            | block the writer. Persistent once set.           |
| foreign_keys = ON          | SQLite defaults it off, per connection.          |
| busy_timeout = 5000        | Wait 5 s on a lock instead of failing at once.   |
| synchronous = NORMAL       | Durable across application crashes in WAL mode;  |
|                            | a power loss may lose the last commits, never    |
|                            | corrupt the file.                                |
+----------------------------+--------------------------------------------------+
```

`foreign_keys`, `busy_timeout` and `synchronous` are connection state, so they
cannot be set once at startup. The backend opens a short-lived connection per
operation, and each one applies all four.

## Deviation from design.md 14: reply audio on the turn row

design.md 14 lists no audio column on `turns`. WP4.1 adds `reply_audio BLOB`
holding the raw WAV bytes of the spoken reply. The device response carries
that audio as a base64 data URL. The repository converts between the two at
the storage edge, so no base64 text reaches the database.

This is needed for WP4-AT-03: a replay after restart must return the
identical response and make no TTS call. Re-synthesis would call the TTS port
and could return different bytes.

Cost: WP4.1 estimated 70-180 KB per turn from the canned fixtures. Real `say`
replies measure about 0.9 MB, and reply audio is about 95% of the database.
ADR-0008 holds the measurement, the growth rate and the retention rules.

design.md section 14 lists the reply-audio column since 13-Sep-2026.

## Direction if the cases table is revived

Migration 0001 creates `devices`, `sessions`, `turns` and `turn_sources` only.
Handoff and follow-up, which `cases` served, are deferred beyond the MVP
(design.md v1.4), so no MVP migration creates it. Migration 0002 belongs to
WP4.2 (below); a revived `cases` takes the next free number.

SQLite cannot add a foreign key to an existing table without rebuilding it.
The reference therefore points from the new table to the old one:
`cases.opened_by_turn_id` references `turns (turn_id)`, and no change to
`turns` is needed.

`turns.case_id` already exists as plain text with no foreign key, because it
belongs to the public response. It records the case a turn reports. It does
not own the relationship.

## Migration 0002 (WP4.2): action resolution

`0002_previous_turn.sql` adds two nullable columns to `turns`:

```text
+-------------------+----------------------------------------------------------+
| Column            | Meaning                                                  |
+-------------------+----------------------------------------------------------+
| previous_turn_id  | TEXT REFERENCES turns (turn_id). The stored turn a       |
|                   | repeat_previous or print_previous resolved to.           |
| action_outcome    | TEXT, 'resolved' or 'nothing_to_act_on' (CHECK). Null on |
|                   | answer and refuse turns.                                 |
+-------------------+----------------------------------------------------------+
```

Both are additive; rows written at version 1 read null. `ADD COLUMN` needs no
table rebuild, and the existing `turns_by_session` index serves the lookup.

An action turn copies the resolved turn's `turn_sources` rows and, for a
repeat, its reply audio, so the action's own replay rebuilds from its own
rows. Each repeat therefore adds another copy of the reply audio. ADR-0008
records the size and why the copy stays.

**Rollback.** A WP4.1 build refuses a version 2 database, so rolling back the
code needs a schema downgrade:

1. Stop the backend: `python scripts/dev_stack.py down --only backend`.
2. Back up: `sqlite3 "$KAKI_DB" ".backup '$KAKI_DB.pre-rollback'"`.
3. Downgrade:
   `sqlite3 "$KAKI_DB" "ALTER TABLE turns DROP COLUMN action_outcome; ALTER TABLE turns DROP COLUMN previous_turn_id; PRAGMA user_version = 1;"`
4. Check out the WP4.1 commit and start the backend.

`DROP COLUMN` needs SQLite 3.35 or later; the `.venv` library is 3.53.4 and
the macOS CLI 3.51.0. Rows that were action turns stay, with state `acted`
and their copied sources; WP4.1 replays them unchanged. The downgrade SQL is
tested in `backend/tests/unit/test_actions.py`. Starting a WP4.2 build again
re-applies 0002.

## Consequences

- One writer process per database file. Two backends on one file would be
  safe for SQLite but would break in-flight turn de-duplication, which relies
  on a process lock.
- WAL creates `kaki.db-wal` and `kaki.db-shm` beside the database. A plain
  file copy taken during a write can be inconsistent. Back up with
  `sqlite3 kaki.db ".backup 'target'"` or `VACUUM INTO 'target'`.
- A storage failure after execution returns HTTP 500, and the client's retry
  re-executes. No MVP unit adds an external side effect. A revived handoff or
  calendar capability must record idempotency before its side effect.
