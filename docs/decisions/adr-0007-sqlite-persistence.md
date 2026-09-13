# ADR 0007: SQLite persistence with standard-library migrations

Date: 13-Sep-2026

Status: accepted for WP4.1 by owner decision, 13-Sep-2026. Implements the
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

Cost: a spoken reply is about 70-180 KB, so each stored turn adds roughly that
much. WP4.1 does no pruning. Size review belongs with the WP4.5 backup work.

design.md is not edited in WP4.1. Reconcile section 14 at the next baseline
update.

## Direction for WP4.3: the cases table

Migration 0001 creates `devices`, `sessions`, `turns` and `turn_sources` only.

SQLite cannot add a foreign key to an existing table without rebuilding it.
The reference therefore points from the new table to the old one:
`cases.opened_by_turn_id` references `turns (turn_id)`. Migration 0002 creates
`cases` with that column and needs no change to `turns`.

`turns.case_id` already exists as plain text with no foreign key, because it
belongs to the public response. It records the case a turn reports. It does
not own the relationship.

## Consequences

- One writer process per database file. Two backends on one file would be
  safe for SQLite but would break in-flight turn de-duplication, which relies
  on a process lock.
- WAL creates `kaki.db-wal` and `kaki.db-shm` beside the database. A plain
  file copy taken during a write can be inconsistent. Back up with
  `sqlite3 kaki.db ".backup 'target'"` or `VACUUM INTO 'target'`.
- A storage failure after execution returns HTTP 500, and the client's retry
  re-executes. WP4.1 has no side effect beyond speech synthesis. WP4.3 and
  WP4.4 must record action idempotency before performing a side effect.
