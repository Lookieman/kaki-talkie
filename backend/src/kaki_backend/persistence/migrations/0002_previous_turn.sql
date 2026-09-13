-- v1.0 | 13-Sep-2026 | WP4.2 previous_turn_id and action_outcome on turns.
--
-- An action turn (repeat_previous, print_previous) records which stored turn
-- it resolved to, and whether it resolved at all. Both columns are null on
-- answer and refuse turns; rows written before this migration read null.
--
-- Rollback (ADR-0007): with the backend stopped and a backup taken, drop
-- action_outcome, then previous_turn_id, then set PRAGMA user_version = 1.

ALTER TABLE turns ADD COLUMN previous_turn_id TEXT REFERENCES turns (turn_id);

ALTER TABLE turns ADD COLUMN action_outcome TEXT CHECK (
    action_outcome IN ('resolved', 'nothing_to_act_on')
);
