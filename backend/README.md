# Backend foundation

This implements the canned backend through WP1.4. The complete WP1 gate still
requires hosted CI and the owner deployment/phone/laptop checks.
The authoritative contract is in `../docs/04-prototype/design.md`.

Use Python 3.11 or newer. From the repository root:

```text
python -m venv .venv
```

Activate `.venv` with the command appropriate for your shell, then run:

```text
python -m pip install -e "backend[test,dev]"
python -m kaki_backend.main
```

Run contract tests from the repository root:

```text
python -m unittest discover -s backend/tests/contract -v
python -m ruff check --config backend/pyproject.toml backend scripts
python -m unittest discover -s scripts/tests -v
python scripts/check_code_history.py
```

`GET /api/health` returns `{"status":"ok","version":"0.1.0"}`. The version comes
from the FastAPI application. Health does not check future model services.

`POST /api/device/turn` accepts multipart form fields `audio`, `device_id`,
`session_id` and `turn_id`. Identifiers are opaque nonblank strings. Non-empty
uploads return a clearly labelled English test reply, display text and sample
slip. An empty upload returns a `failed` turn; missing or invalid required fields
return HTTP 422. Audio contents and duration are not decoded or validated yet.
WP1 validates zero-byte uploads only. Non-empty silent recordings receive the canned
answer; acoustic silence/usefulness detection is deferred to WP2.
Use synthetic audio when exercising this foundation.

`GET /api/device/pending` returns an empty list in WP1. Meaningful pending items,
delivery acknowledgement and case state remain deferred to WP4.

Every successful HTTP turn response includes all nine design fields. `reply_audio`
contains a prerecorded PCM WAV data URI for the canned answer or zero-byte failure.
No runtime synthesis occurs. See [fixture provenance](src/kaki_backend/fixtures/README.md).
`case_id` is null and `sources` is empty because no case or retrieved evidence exists.
Receipt source/date text is explicitly labelled as a canned fixture, with no claim
of official provenance or retrieval.

The endpoint reads only enough to distinguish an empty upload, closes the upload,
and does not retain audio or log its contents. Multipart parsing may temporarily
spool large uploads; FastAPI manages these request-scoped temporary files.

API routes handle transport, contracts define the input/output types, and
`orchestration/turn_pipeline.py` supplies canned behaviour. No model, retrieval,
database or external service is invoked; the existing canned ports supply fixtures.

Completed responses are cached in process memory by `turn_id`. Reusing a turn ID
returns the stored first response without executing the canned pipeline again,
even if retry content differs. The cache is intentionally lost on restart;
durable SQLite idempotency and side-effect handling remain deferred to WP4.

Each first execution records an in-memory log with audio-preparation, STT,
routing, retrieval, live-lookup, LLM, TTS, overall and future first-audio timing
fields. Stages not invoked in WP1 remain null.

The supported launcher explicitly binds to `127.0.0.1:8000`. Follow the
[Mac deployment and WP1 owner gate](../infra/macos/README.md) and
[Cloudflare Tunnel/Access instructions](../infra/cloudflare/README.md).
Authentication is enforced by the configured edge, not by this local application.
No Cloudflare account configuration or deployment success is implied by these files.
