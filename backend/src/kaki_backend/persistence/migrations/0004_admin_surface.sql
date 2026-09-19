-- v1.0 | 18-Sep-2026 | WP6.6 admin surface: device_config, pending_messages, language override.
--
-- The demo admin surface (design.md 5.5) writes state that the turn pipeline
-- and the pending endpoint read:
--   device_config     one row per configured device; absent row means auto,
--                     so the section 6.4 policy decides. No FK to devices:
--                     an operator may configure a kiosk before its first turn.
--   pending_messages  seeded canned nudges. push marks one queued for one
--                     device; the pending endpoint marks it delivered as it
--                     hands it over (the 5.4 delivery-state rule).
--   turns.language_override
--                     'en' or 'ms' when the admin override, not the policy,
--                     chose the reply language; null otherwise. Evidence
--                     stays interpretable: stt_language_json keeps what
--                     Whisper heard, reply_language what actually ran.
--
-- The seed row carries provisional wording. scripts/seed_push_message.py
-- re-seeds it, so changing a word never needs a migration.
--
-- Rollback (ADR-0007): with the backend stopped and a backup taken, drop
-- turns.language_override, then pending_messages, then device_config, then
-- set PRAGMA user_version = 3.

CREATE TABLE device_config (
    device_id       TEXT PRIMARY KEY,
    reply_language  TEXT NOT NULL CHECK (reply_language IN ('en', 'ms', 'auto')),
    updated_at      TEXT NOT NULL
);

CREATE TABLE pending_messages (
    message_key       TEXT PRIMARY KEY,
    body_en           TEXT NOT NULL,
    body_ms           TEXT NOT NULL,
    audio_fixture_en  TEXT NOT NULL,
    audio_fixture_ms  TEXT NOT NULL,
    state             TEXT NOT NULL DEFAULT 'idle' CHECK (
        state IN ('idle', 'queued', 'delivered')
    ),
    target_device_id  TEXT,
    pushed_at         TEXT,
    delivered_at      TEXT,
    delivered_count   INTEGER NOT NULL DEFAULT 0
);

ALTER TABLE turns ADD COLUMN language_override TEXT CHECK (
    language_override IN ('en', 'ms')
);

INSERT INTO pending_messages (
    message_key, body_en, body_ms, audio_fixture_en, audio_fixture_ms
) VALUES (
    'cdc-vouchers-available',
    'Good news: new CDC vouchers are available. Press the button to ask me about them.',
    'Berita baik: baucar CDC baharu sudah tersedia. Tekan butang untuk bertanya kepada saya.',
    'push_cdc_en.wav',
    'push_cdc_ms.wav'
);
