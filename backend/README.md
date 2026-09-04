# Backend foundation

This implements only the canned backend foundation, not the complete WP1 gate.
The authoritative contract is in `../docs/04-prototype/design.md`.

Use Python 3.11 or newer. From the repository root:

```text
python -m venv .venv
```

Activate `.venv` with the command appropriate for your shell, then run:

```text
python -m pip install -e "backend[test]"
python -m uvicorn kaki_backend.main:app --host 127.0.0.1 --port 8000
```

Run contract tests from the repository root:

```text
python -m unittest discover -s backend/tests/contract -v
```

`GET /api/health` returns `{"status":"ok"}` for this canned application. It does
not check future model services.

`POST /api/device/turn` accepts multipart form fields `audio`, `device_id`,
`session_id` and `turn_id`. Identifiers are opaque nonblank strings. Non-empty
uploads return a clearly labelled English test reply, display text and sample
slip. An empty upload returns a `failed` turn; missing or invalid required fields
return HTTP 422. Audio contents and duration are not decoded or validated yet.
Use synthetic audio when exercising this foundation.

Every successful HTTP turn response includes all nine design fields. `reply_audio`
is null because no recorded reply or TTS exists in this foundation. `case_id` is
null and `sources` is empty because no case or retrieved evidence exists.

The endpoint reads only enough to distinguish an empty upload, closes the upload,
and does not retain audio or log its contents. Multipart parsing may temporarily
spool large uploads; FastAPI manages these request-scoped temporary files.

API routes handle transport, contracts define the input/output types, and
`orchestration/turn_pipeline.py` supplies canned behaviour. No model, retrieval,
database, external service or adapter is invoked.

Retries of the same valid request yield identical canned JSON. This is not an
idempotency store: reusing a turn ID with different input does not retrieve an
earlier result. Persistent idempotency and side-effect handling are deferred.

This is a local development foundation. Authentication and public deployment are
not implemented; use the documented localhost binding.
