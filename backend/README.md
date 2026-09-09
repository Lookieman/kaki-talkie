# Backend

This is the KaKi-Talkie application API. Through WP2.4 it runs a real local
English voice loop: whisper.cpp STT, MLX-LM/Qwen generation and macOS `say`
TTS behind port adapters, with the WP1 contract unchanged. Replies remain
deliberately ungrounded until WP3 retrieval.

The authoritative contract is `../docs/04-prototype/design.md`.
Mac installation is governed by `../infra/macos/setup.md`. Service start
order, validation and evidence are governed by
`../docs/04-prototype/wp-validation-runbook.md`.

## Install

Use Python 3.11 or newer. From the repository root:

```text
python -m venv .venv
```

Activate `.venv` with the command appropriate for your shell, then run:

```text
python -m pip install --only-binary=av -e "backend[test,dev]"
```

The inference adapters are separate packages. Install the ones the current
work package needs into the same environment:

```text
python -m pip install -e services/stt/whisper_cpp
python -m pip install -e services/llm/qwen_local
python -m pip install -e services/tts/english
```

## Run

```text
python -m kaki_backend.main
```

The launcher binds to `127.0.0.1:8000` only. Adapters are opt-in through
environment variables; each defaults to `canned`, so the backend runs with
no model services present:

```text
KAKI_STT_MODE   canned | whisper   (with KAKI_WHISPER_URL)
KAKI_LLM_MODE   canned | qwen      (with KAKI_LLM_URL)
KAKI_TTS_MODE   canned | say
```

The application does not auto-load `.env`; export settings explicitly. The
exact exports, timeouts and start order are in runbook sections 7.2.1,
7.3.1 and 7.4.1.

## Tests

From the repository root:

```text
python -m unittest discover -s backend/tests/unit -v
python -m unittest discover -s backend/tests/contract -v
python -m ruff check --config backend/pyproject.toml backend scripts
python -m unittest discover -s scripts/tests -v
```

These run against fakes; no model service is required. Tier B validation
against real models runs on the Mac Mini from the runbook.

## Endpoints

`GET /api/health` returns `status`, the application version and, from
WP2.4, live `stt_ready`, `llm_ready` and `tts_ready` fields. A readiness
field goes false when its service is down; `status` stays `ok`. Probes use
bounded two-second timeouts.

`POST /api/device/turn` accepts multipart form fields `audio`, `device_id`,
`session_id` and `turn_id`. Identifiers are opaque nonblank strings;
missing or invalid fields return HTTP 422. Uploads are normalised to
16 kHz mono PCM (at most 8 MiB and 16 seconds decoded); oversized or
malformed input returns a calm `failed` turn. Every successful response
carries all nine design fields. A TTS failure degrades an answered turn to
text only (`reply_audio` null); it does not fail the turn.

Raw audio is deleted after transcription by default, in success and
failure paths. The explicit consent-cleared retention mode exists only for
the STT bake-off (runbook 7.2.2 Test 2).

`GET /api/device/pending` returns an empty list until WP4.

`GET /api/device/debug/last-turn` is the protected debug view: transcript,
language evidence, state and stage timings for the most recent turn. It is
served by the loopback-only application and reached remotely only through
the protected `/api/device/*` path.

Completed responses are cached in process memory by `turn_id`. Reusing a
turn ID returns the stored first response without re-executing the
pipeline. The cache is lost on restart; durable SQLite idempotency arrives
in WP4.
