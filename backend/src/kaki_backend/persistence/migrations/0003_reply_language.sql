-- v1.1 | 14-Sep-2026 | Allow render_outcome fallback_numbers (edited before release; no database had applied 0003).
-- v1.0 | 13-Sep-2026 | WP5.1 reply language, Malay reply mode and render outcome on turns.
--
-- The debug view reads SQLite, so the WP5.1 language diagnostics are stored
-- with the turn (runbook 10.1 WP5.1, "Debug view additions"):
--   reply_language  the language policy's decision, en or ms;
--   reply_mode      KAKI_MALAY_REPLY_MODE when the turn ran;
--   render_outcome  what a full-mode render did, null when none was attempted.
-- All three are null on failed turns and on rows written before this migration.
-- The public response is unchanged; `language` stays its own column.
--
-- Rollback (ADR-0007): with the backend stopped and a backup taken, drop
-- render_outcome, then reply_mode, then reply_language, then set
-- PRAGMA user_version = 2.

ALTER TABLE turns ADD COLUMN reply_language TEXT CHECK (reply_language IN ('en', 'ms'));

ALTER TABLE turns ADD COLUMN reply_mode TEXT CHECK (reply_mode IN ('full', 'bridge', 'english'));

ALTER TABLE turns ADD COLUMN render_outcome TEXT CHECK (
    render_outcome IN (
        'rendered', 'fallback_empty', 'fallback_numbers', 'fallback_length', 'fallback_error'
    )
);
