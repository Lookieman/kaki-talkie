# ADR 0006: Simulator and Pi share one device contract

Date: 05-Sep-2026

Status: records the locked decision in design.md sections 3, 5 and 13.

The browser simulator and future Raspberry Pi are thin clients of the same FastAPI
backend. Both submit multipart `POST /api/device/turn` with `audio`, `device_id`,
`session_id` and mandatory `turn_id`; both consume the same nine-field turn response
and `GET /api/device/pending` contract. Client implementation does not redefine
orchestration, retrieval, case behavior, or model interfaces.

WP1 uses deterministic canned behavior. Prerecorded WAV payloads travel through
the existing `reply_audio` field. Test-labelled receipts do not imply retrieval.
In-memory idempotency and an empty pending list remain unchanged. The schema snapshot
is the regression gate for later implementations.

The browser uses a human Cloudflare Access session and its simulator identity.
Physical-device service authentication remains later work; no service credential is
embedded in browser JavaScript. Both origins bind to localhost; Cloudflare Tunnel
routes the public hostname to them.

The simulator proves the software contract and browser interaction. It does not
prove microphone acoustics, GPIO, printer hardware, LED wiring, or Pi recovery.
Later model/service replacements must preserve this shared client contract.
