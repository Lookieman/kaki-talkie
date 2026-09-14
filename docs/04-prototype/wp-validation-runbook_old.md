# KaKi-Talkie WP validation runbook

Version 1.18 | 13-Sep-2026 | SGLN Group 10

> v1.18 rewrites section 10 for the reduced WP5 of `execution-plan.md`
> v1.10: WP5.1 is the only build unit, WP5.2 is a timeboxed viability
> check, and WP5.3 to WP5.6 are deferred beyond the MVP. The consented
> speech set is deferred with them. Cross-references to WP5.5 and WP5.6
> elsewhere in this document are corrected.
> v1.17 applies the within-package regression rule of `execution-plan.md`
> 1.1: Test 6 package mode reruns WP4.1 and WP4.2 only. WP2.3, WP2.4,
> WP3.3 and WP3.4 are dropped, because WP4.5 changes no code their checks
> exercise.
> v1.16 adds the "Closed block compression" rule to section 12 and applies
> it to the WP4.1 and WP4.2 setup blocks; their test blocks are unchanged.
> The WP4.5 setup and test blocks are rewritten, and the decision record
> moves to ADR-0008. Corrections: Test 1 bounds the backup row count
> between before and after counts; the restore test sends the grounded
> question before the repeat; `setup.md` 12 names `kaki.db`; design.md 14
> lists reply audio; the execution point reads WP4.5 and the gate checks
> it; the backup manifest records `ingest_running`; presenter controls
> use `localStorage`; in-place recovery is marked not rehearsed with a
> gate line; the action result is a count and a rate; third-party
> sessions are tagged and deleted on request. Section 9 marks WP4.3 and
> WP4.4 withdrawn. A stray code fence in section 12 is removed. WP4.5
> stays DRAFT.
> v1.15 also corrects the WP3.4 credential rule (runbook 8.1 WP3.4 layer
> 1): "Print my Singpass password" routed to `answer` because disclosure
> matched a fixed verb list. The rule is now inverted, with Malay
> procedural markers, and the layer 1 text states what the code does.
> v1.15 adds the WP4.2 setup and test blocks (Prepare and Implement
> WP4.2): `repeat_previous` and `print_previous` from stored turns,
> migration 0002 (`previous_turn_id`, `action_outcome`), the client
> print policy of design.md 9.3, ten devset action items and the owner
> evidence harness `scripts/wp4_2_evidence.sh`. The harness drops its
> `whisper.log` cross-checks (block-buffered, so the count lags) and keeps
> the `llm.log` check with a positive control; `dev_stack.py` runs MLX-LM
> with `PYTHONUNBUFFERED=1`. The WP4.2 tier B check
> and harness Test 4 replay both action types and read the debug view as
> the newest executed turn. Owner decisions 2-4
> approved 13-Sep-2026. Schema-version checks in earlier units now
> assert "at least"; only WP4.2 asserts the exact version. WP4.2 is
> marked VERIFIED / CLOSED as of 13-Sep-2026.
> v1.14 records the owner decision of 13-Sep-2026: the handoff and
> calendar capabilities, and their Telegram and Google Calendar
> integrations, are deferred beyond the MVP. Section 9 loses the handoff
> channel choice and the case-lifecycle objective. The former Test 3
> (case lifecycle and handoff) is withdrawn and backup/restore becomes
> Test 3. WP4-AT-07 to WP4-AT-12 are withdrawn. WP4.1 is marked
> VERIFIED / CLOSED as of 13-Sep-2026.
> v1.13 also marks WP3.4 VERIFIED / CLOSED and the WP3 package gate
> CLOSED as of 12-Sep-2026, and records the WP3.4 Test 3 devset result
> (14/14, intent accuracy 1.00, golden-path items 6/6).
> v1.13 adds the WP4.1 setup and test blocks (Prepare and Implement
> WP4.1): SQLite schema and migrations, repositories, durable turn
> idempotency across a backend restart. Section 9 gains a WP-level
> objectives heading so the scaffold tests are not confused with the
> numbered WP4.1 tests.
> v1.12 removes secret redaction from WP3.4 after an owner decision
> that redaction creates a false security promise the MVP cannot defend.
> The credential-action refusal stays. The credential-request fixture,
> layer 2 (redaction), Test 3 (secret handling), the benign-six-digit
> devset item, and the transcript_redacted debug field are removed.
> Tests renumber: old 4-8 become 3-7.
> v1.11 restructures the WP3.4 setup and test blocks into titled
> subsections (one topic each, specification before rationale, tables for
> structured fields). Adds a section-structure standard to section 12 and
> applies it to the WP4, WP5 and WP6 draft scaffolds.
> v1.10 updates sections 1, 3 and 4 to the Mac Mini development model and
> removes the retired Windows and named-agent references from the live
> sections. Closed WP2.x sections keep their original machine names as
> historical evidence of what was run at the time.
> v1.9 adds the WP3.4 setup and test blocks (Prepare WP3.4): refusal,
> no-coverage, devset regression and the WP3 gate.
> v1.7 revises the WP3.1 block only: the corpus is captured manually as
> owner-reviewed markdown (design.md 7.2, v1.2). Four `capture: manual`
> sources, `seed_snapshot.py` workflow, and revised Test 1-3
> expectations.

Repository location: `docs/04-prototype/wp-validation-runbook.md`

`setup.md` is the source of truth for Mac backend installation and configuration. This runbook is the source of truth for work-package validation: what to test, why, in what order, and what evidence to keep. Each WP setup section cross-references `setup.md` and adds only components that the final solution needs and `setup.md` does not cover.

`design.md` defines architecture. `execution-plan.md` defines scope and acceptance. This runbook explains exactly what the owner does at the keyboard.

---

## 1. Environment model

```text
+--------------------------+-----------------------------+-------------------------+
| Environment              | Primary purpose             | Coding agent            |
+--------------------------+-----------------------------+-------------------------+
| Mac Mini (websvc)        | Development, Tier A, Tier B | Runs here               |
|                          | and the runtime             |                         |
| Raspberry Pi             | Thin client/Tier C tests    | Does not run here       |
| Phone/laptop browser     | Interaction smoke/gates     | Not applicable          |
+--------------------------+-----------------------------+-------------------------+
```

Rules:

- Code is created in a worktree on the Mac Mini.
- Runtime and Pi preparation is performed manually by the owner.
- Runtime/model caches stay outside the Git repository.
- Generated application data uses `KAKI_DATA_ROOT` where applicable.
- Tier A tests run with the `KAKI_*` mode switches cleared, so a canned test
  never reaches a live service.
- Chrome is the primary simulator acceptance browser; Safari is optional/non-gating.

Closed WP2.x sections below name a Windows development machine. That machine is
retired. Read those sections as evidence of what was run at the time, and run any
repeated command on the Mac Mini.

---

## 2. Runbook states

```text
DRAFT      Structure exists, but exact commands may still change.
READY      Owner prerequisites and validation procedure are complete.
VERIFIED   Owner executed the procedure successfully.
BLOCKED    A real prerequisite/decision prevents implementation or validation.
```

An IU that depends on a Mac/Pi runtime must not move from `Prepare` to `Implement` while its section contains `BLOCKED - VERIFY BEFORE IMPLEMENTATION`.

---

## 3. Standard IU structure

Each active `WPn.m` section contains, as applicable:

1. purpose and owner level;
2. status;
3. machine and account;
4. working directories;
5. one-time prerequisites;
6. package/runtime/model installation;
7. installation verification;
8. environment/configuration;
9. service start order and readiness checks;
10. independent automated checks the owner may rerun;
11. owner smoke/gate steps;
12. expected observations;
13. evidence to retain;
14. shutdown/teardown;
15. known limitations/deferred validation;
16. troubleshooting.

Completion reports point here instead of duplicating these procedures.

---

## 4. Development worktree lifecycle

Machine: Mac Mini as `websvc`  
Repository: `~/projects/kaki-talkie`

### 4.1 Before creating a worktree

```sh
git switch main
git pull --ff-only
git status
```

`main` must be clean and current before setup.

### 4.2 Create an IU worktree

Use the repository helper after its pre-WP2 contract update:

```sh
python scripts/setup_wp_worktree.py --help
```

Example:

```sh
python scripts/setup_wp_worktree.py \
    --unit WP2.1 \
    --slug audio-normalisation \
    --run-baseline
```

The helper creates the sibling worktree, local feature branch and worktree-local development environment. It does not commit, merge or push.

Point the agent session only at the new worktree.

### 4.3 Manual acceptance boundary

The owner performs these steps manually after review/testing:

```text
commit feature branch
-> fast-forward merge into main
-> push main
```

Do not automate this approval boundary.

### 4.4 Cleanup

After the feature is committed, fast-forward merged, pushed, and both trees are clean:

```sh
cd ~/projects/kaki-talkie
python scripts/cleanup_wp_worktree.py --help
python scripts/cleanup_wp_worktree.py --unit WP2.1
```

The cleanup helper must refuse cleanup when main is not pushed, the worktree is dirty, or the branch is not merged.

---

## 5. Repository-maintenance checkpoint before WP2.1

Status: **READY**

Machine: Windows gaming desktop  
Branch: `main`

Before creating the WP2.1 worktree, update:

- `scripts/setup_wp_worktree.py`;
- `scripts/cleanup_wp_worktree.py`.

Both scripts must meet the `AGENTS.md` human-operated-script contract:

- module docstring;
- `-h`/`--help`;
- clear argument help;
- documented side effects;
- non-zero failure exit;
- safe/no-force behaviour;
- no commit, merge or push.

Verify:

```powershell
python scripts\setup_wp_worktree.py --help
python scripts\cleanup_wp_worktree.py --help
python -m py_compile scripts\setup_wp_worktree.py scripts\cleanup_wp_worktree.py
```

Run any script tests present in the repository.

Commit/push this maintenance change separately before WP2.1.

---

## 6. WP1 - contract + simulator regression reference

Status: **VERIFIED / CLOSED 05-Sep-2026**

WP1 remains a regression baseline. Do not rerun the full WP1 owner gate after every later IU unless a change affects the WP1 contract/browser/deployment boundary.

The normal earlier regression commands are the repository's current Tier A contract/web checks. The exact commands must remain discoverable through the repository scripts and CI configuration.

Key retained observations:

- FastAPI and web runtime on Mac are loopback-only.
- Protected HTTPS simulator works on desktop and iPhone.
- Phone microphone testing uses HTTPS, not plain LAN HTTP.
- WP1 schema/contract remains the cross-package baseline.

---

# 7. WP2 - real English voice loop

Goal: replace canned inference with real local English STT, LLM and TTS while preserving the WP1 contract.

## 7.1 WP2.1 - audio input and normalisation

Owner level: **S**  
Status: ****VERIFIED / CLOSED 06-Sep-2026****

Machine split:

```text
Windows gaming desktop:
- Codex implementation
- deterministic audio fixtures/tests

Mac Mini:
- target-runtime smoke only if the selected normaliser has a Mac dependency
```

Acceptance target: supported current browser/device recordings normalise to 16 kHz mono PCM WAV.

Primary browser target: Chrome. Safari compatibility is optional/non-gating for the MVP.

Selected mechanism: PyAV 18.1.0 decodes/resamples in memory; Python writes signed
16-bit PCM WAV. No separate FFmpeg executable, model, cache or normaliser service.
Binary wheels verified on PyPI for Windows AMD64 and macOS 14+ Apple Silicon,
Python 3.11+. Windows installation verified on Python 3.14.3. Mac execution is
owner-only and has not been claimed verified.

Accepted containers: WAV, WebM/Matroska, Ogg and MP4/MOV (codec support depends
on the bundled decoder). Chrome WebM/Opus and PCM WAV are acceptance-tested.
The normaliser accepts at most 8 MiB and 16 seconds of decoded samples; the
client's recording cap remains 15 seconds, with one second of container rounding
allowance. Oversized/malformed input uses the existing failed-turn response.
The multipart parser may spool uploads temporarily before the bounded read;
the request handler always closes that resource. No retained-audio mode is added.

Windows: existing development account, `C:\projects\kaki-talkie-wp2.1`.
Mac: `websvc`, existing application checkout. From that checkout root, activate
its `.venv` using `source .venv/bin/activate`. Check `pwd`,
`sw_vers -productVersion`, and `python --version`;
require macOS 14+ and Python 3.11+. No Pi prerequisites. No credentials needed.

Install from the checkout root (Windows uses `.venv\Scripts\python.exe`):

```sh
python -m pip install --only-binary=av -e 'backend[test,dev]'
python -c "import av; print(av.__version__); print(av.library_versions)"
```

Expected: version 18.1.0 and linked FFmpeg library versions. If no compatible
wheel is available, verify interpreter/OS/architecture; do not silently source-build.

### WP2.1 automated validation

From the Windows worktree root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/unit -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/contract -v
.\.venv\Scripts\python.exe -m unittest discover -s scripts/tests -v
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend scripts
npm --prefix apps/web test
npm --prefix apps/web run lint
npm --prefix apps/web run build
.\.venv\Scripts\python.exe scripts/check_wp1_integration.py --start-services
```

Coverage: current Chrome tone, alternate-rate stereo PCM, malformed/empty input,
duration and output bounds, normalised STT input, idempotency and WP1 schema.
Old arbitrary-byte success fixtures are replaced by valid audio without removing
their response assertions. Silence detection and STT lifecycle belong to later units.

### WP2.1 owner smoke and evidence

As `websvc` on Mac, from the application checkout with `.venv` active:

```sh
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
mkdir -p "$KAKI_DATA_ROOT/wp2.1"
python scripts/check_audio_normalisation.py --help
python scripts/check_audio_normalisation.py --input backend/tests/fixtures/audio/chrome-tone.webm --output "$KAKI_DATA_ROOT/wp2.1/chrome-normalised.wav"
afplay "$KAKI_DATA_ROOT/wp2.1/chrome-normalised.wav"
```

Expected: exit zero, 16000 Hz, one channel, 16-bit uncompressed PCM, non-zero
frames/duration, and an audible tone. Duration tolerance is 0.1 seconds against
the fixture provenance. CLI refuses existing output paths; choose a fresh name
on rerun. Invalid input returns non-zero without creating output. `--help`
documents side effects. This standalone smoke needs no running application.

Fixtures are deliberate non-sensitive test assets; see
`backend/tests/fixtures/audio/README.md` for Chrome provenance. Ordinary user audio
is not retained. Generated smoke files stay outside Git. Retain dependency versions,
CLI metadata and the owner's observation under `KAKI_DATA_ROOT/wp2.1`.

No service shutdown is needed: the CLI exits after conversion. Remove only the
specific generated smoke output when no longer needed; keep shared environments.
Decode failures require checking the actual container/codec, not the upload name.
Wrong rate/channels or a silent known-tone output fails the smoke. Safari failures
are non-gating. If Mac is unavailable, report smoke not run and leave VERIFIED pending.

Implementation validation on Windows (06-Sep-2026): seven audio tests, 24 backend
contract/schema tests, 19 script tests and nine web tests passed. Ruff, web lint,
production build and real localhost HTTP integration passed. CLI help, conversion,
invalid-input and no-overwrite behaviour passed. No Mac/Pi execution is claimed.

History enforcement was removed on 07-Sep-2026 by owner direction; history
metadata does not gate validation. Mark VERIFIED only after the owner completes
the Mac smoke.

```text
WP2.1 output: 16000 Hz / mono / signed 16-bit PCM WAV
Later gates: transcription, language evidence, retain mode, full speech loop
```

Do not introduce STT, LLM or TTS in WP2.1.

## 7.2 WP2.2 - whisper.cpp STT

Owner level: **S**  
Status: **VERIFIED / CLOSED 8 Sep**.
The owner's 07-Sep-2026 implementation instruction resolves the prior B1/B2
planning blockers with the configuration and CLI contract below. Verify commands
for new application code on Windows before reporting implementation complete.
Mac execution is owner-only.

Scope: WP2-AT-02/03/07/08 - useful English transcription, language evidence,
default audio deletion and explicit test retention. Baseline: Whisper
large-v3-turbo through `whisper.cpp`.

### 7.2.1 Setup and installation

Install and configure through `setup.md`. This table maps each component to its
`setup.md` section. All of these are complete on the Mac Mini.

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| Host preparation and accounts         | 2, 4 (Stage 0)      |
| Homebrew and base tooling             | 5 (Stage 1)         |
| Directory layout and repository clone | 6 (Stage 2)         |
| Backend Python environment            | 7.1                 |
| whisper.cpp clone and Metal build     | 8.1, 8.2            |
| large-v3-turbo model download         | 8.3                 |
| Known-good audio fixture              | 8.4                 |
| whisper-server on 127.0.0.1:8081      | 8.5, 3 (port map)   |
+---------------------------------------+---------------------+
```

Two components are crucial to the final solution and absent from `setup.md`.
Install them here.

#### Install the STT adapter

The adapter is the WP2.2 deliverable: it connects FastAPI to the Whisper
service. On the Mac, as `websvc`, from the application checkout root with its
`.venv` active:

```sh
python -m pip install -e services/stt/whisper_cpp
python -c "from kaki_whisper_cpp.adapter import WhisperStt; print('Whisper adapter import OK')"
```

On Windows, install it into the worktree `.venv` for the regression tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -e services/stt/whisper_cpp
```

The adapter declares HTTPX >=0.27,<1, already used by backend tests. Do not
install into a global Python.

#### Prepare the validation environment

Repeat these exports in every terminal of a validation session. Reuse the same
printed evidence directory within one session instead of creating another.

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp2.2"
export WP22_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp2.2/smoke.XXXXXX")"
export KAKI_STT_MODE=whisper
export KAKI_WHISPER_URL=http://127.0.0.1:8081
export KAKI_STT_TIMEOUT_SECONDS=30
printf '%s\n' "$KAKI_APP_ROOT" "$WP22_EVIDENCE"
```

`KAKI_STT_MODE` accepts `canned` (default) or `whisper`; invalid values fail
startup. The URL must be HTTP with a literal loopback address, port and no
credentials, path or query. Readiness uses a two-second network timeout;
transcription uses the configured 0.1-120-second network timeout (default 30
seconds). These bound network operations; they are not latency acceptance
targets. Redirects and proxies are disabled; response size is capped at
256 KiB. The application does not auto-load `.env`, so export settings
explicitly.

#### Record the runtime identity

`setup.md` clones `whisper.cpp` from `master` without recording the version.
Evidence needs provenance, so record it once:

```sh
cd ~/src/whisper.cpp
git describe --tags --always
git rev-parse HEAD
shasum -a 256 ~/models/whisper/ggml-large-v3-turbo.bin
```

Copy the three outputs into the current evidence directory. This step runs once per runtime, not once per session; later sessions may copy the existing record forward. If you later rebuild
`whisper.cpp`, record the new identity before the next validation session.

### 7.2.2 Testing and validation

Each test states its objective. If a test stops serving its objective, remove
it rather than maintaining it out of habit.

Run the tests in order. Tests 1-4 run on the Mac as `websvc` with the exports
from 7.2.1 active.

#### Test 1: STT service readiness

Objective: prove the STT runtime that the solution depends on starts cleanly,
binds only to localhost, and reports ready before FastAPI needs it.

Check that port 8081 is free, then start the server in a foreground terminal
(start command: `setup.md` 8.5, with `-l auto` for language evidence):

```sh
lsof -nP -iTCP:8081 -sTCP:LISTEN
cd ~/src/whisper.cpp
./build/bin/whisper-server --host 127.0.0.1 --port 8081 \
  -m ~/models/whisper/ggml-large-v3-turbo.bin -l auto
```

If the port is occupied, identify the process; do not kill an existing service
or change the documented port. In a second terminal:

```sh
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8081/health
lsof -nP -iTCP:8081 -sTCP:LISTEN
```

Expected: HTTP 200 with `{"status":"ok"}` and only `127.0.0.1:8081` listening.
Retry manually while the model loads. Record startup errors; a listening socket
alone is not readiness.

Start order for the full stack: Whisper, then the CLI readiness check, then
FastAPI, then the optional simulator. The CLI in Test 2 does not require
FastAPI.

#### Test 2: adapter transcription, deletion and retention

Objective: prove WP2-AT-02/03/07/08 through the production adapter - useful
English transcription with language evidence, default audio deletion, and
explicit consent-gated retention.

```sh
cd "$KAKI_APP_ROOT"
python scripts/check_stt.py --readiness
python scripts/check_stt.py --input backend/src/kaki_backend/fixtures/canned_reply.wav
python scripts/check_stt.py --input backend/src/kaki_backend/fixtures/canned_reply.wav --retain-test-audio --consent-to-retain
```

The fixture is synthetic; its provenance and exact text are in the adjacent
README. The CLI runs an original turn, a same-ID retry and an unselected
control turn, and reports JSON with the transcript, language evidence, timings,
audio release, retry and selection checks, and any retained path.

Expected: useful English text, language evidence with a finite probability
between zero and one, released input buffers, one execution for the
original/retry pair, and two total STT calls including the control. Inspect the
text against the fixture; no invented accuracy threshold applies. Default mode
writes no audio. Retain mode writes exactly one copy of the original input
under `KAKI_DATA_ROOT/wp2.2/retained`; the retry and the control must create no
copies. Both retention flags and an explicit `--input` are required; no public
API parameter or environment variable enables retention.

After examining the printed retained path, delete only that file, replacing the
placeholder with the exact generated basename:

```sh
rm -i "$KAKI_DATA_ROOT/wp2.2/retained/<printed-basename>"
```

Rerun the default CLI and confirm no new retained file appears. Do not delete
the data root.

#### Test 3: device HTTP contract with real transcription

Objective: prove the route the kiosk calls returns the locked nine-field
contract with real transcription behind it, and that a retried `turn_id`
returns the first response.

Start FastAPI in a separate foreground terminal with the 7.2.1 exports and
`.venv` active:

```sh
cd "$KAKI_APP_ROOT"
python -m kaki_backend.main
```

Confirm `127.0.0.1:8000` with `lsof -nP -iTCP:8000 -sTCP:LISTEN` and
`curl --fail http://127.0.0.1:8000/api/health`. Then submit a turn:

```sh
curl --fail --silent --show-error --max-time 120 http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp22-smoke -F session_id=wp22-smoke -F turn_id=wp22-smoke-1 \
  -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/canned_reply.wav"
```

Expected: `answered` with the unchanged nine-field response; only transcription
is real in WP2.2, so the reply and audio are clearly canned. Repeat the same
request and confirm the first response returns. Use a fresh `turn_id` for each
new test.

#### Test 4: failure and recovery

Objective: prove the solution fails safely when STT is down and recovers
without an application restart. Sabariah gets a calm answer, not a hang.

1. Stop Whisper with Ctrl+C in its terminal.
2. Run `python scripts/check_stt.py --readiness` and the fixture command from
   Test 2. Both must exit non-zero with safe diagnostics.
3. Submit the Test 3 request with a fresh `turn_id`. Expect HTTP 200, status
   `failed`, calm non-empty text and no invented speech audio.
4. Restart Whisper, wait for readiness, and repeat the readiness check, the
   fixture command and a fresh-ID HTTP request to prove recovery.

Reusing a completed failed `turn_id` deliberately returns its first failure.

#### Test 5: deterministic regression

Objective: prove the WP1 contract and all prior behaviour still hold with the
adapter installed, so later packages can build on WP2.2 without re-checking it.

On Windows, from the worktree root, with the adapter installed (7.2.1) and
`KAKI_STT_MODE=canned`:

```powershell
.\.venv\Scripts\python.exe -m ruff check --config backend/pyproject.toml backend scripts services
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/contract -v
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/unit -v
.\.venv\Scripts\python.exe -m unittest discover -s scripts/tests -v
npm --prefix apps/web test
npm --prefix apps/web run lint
npm --prefix apps/web run build
.\.venv\Scripts\python.exe scripts/check_wp1_integration.py --start-services
```

Expected: all pass without a model service. Adapter tests live in
`backend/tests/unit` and must cover response parsing, language evidence,
readiness, bounded failures, success and error cleanup, retention isolation and
idempotent retries. Preserve earlier behavioural assertions.

#### Teardown and evidence

Stop the stack in reverse order with Ctrl+C in each owned terminal: simulator,
FastAPI, then Whisper. Never use broad process kills. Keep the runtime build
and model cache for reruns.

Retain under `WP22_EVIDENCE`: application path and commit, OS and architecture,
Python version, Whisper identity from 7.2.1, model SHA-256, command results,
readiness and listener observations, transcript and language output, regression
results, and the deletion, retention, failure and recovery observations. Record
consent and disposal of deliberately retained test audio separately. Never
collect ordinary user audio as gate evidence. Memory release is not a promise
of forensic RAM erasure.

Troubleshooting: if Test 2 fails, isolate the layer by calling the Whisper
service directly with the `setup.md` 8.5 procedure
(`curl http://127.0.0.1:8081/inference -F file=@... -F response_format=json`).
If that also fails, the fault is in the runtime or model; if it passes, the
fault is in the adapter or configuration.

Mark VERIFIED only after the owner completes Tests 1-4 on the Mac.

## 7.3 WP2.3 - MLX/Qwen generation

Owner level: **S**  
Status: **VERIFIED / CLOSED 9 Sep**

Machine: Mac Mini. User: `websvc`. Locked runtime family: MLX-LM with a small
quantised Qwen-class instruct model. Do not introduce RAG, DSPy or SEA-LION.

Scope: WP2-AT-04 - the fixed request yields a reply of 60 words or fewer in
five consecutive runs. Baseline model (selected 07-Sep-2026):
`mlx-community/Qwen3-8B-4bit`. Record any change here with a date.

### 7.3.1 Setup and installation

Install and configure through `setup.md`. This table maps each component to
its `setup.md` section. All of these are complete on the Mac Mini.

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| LLM virtual environment (kaki-llm)    | 7.2                 |
| MLX-LM interactive verification       | 9.2                 |
| Model cache location (HF_HOME)        | 9.3                 |
| LLM service on 127.0.0.1:8082         | 9.4, 3 (port map)   |
+---------------------------------------+---------------------+
```

Components crucial to the solution and absent from `setup.md` are installed
here.

#### Install the LLM adapter

The adapter is the WP2.3 deliverable: it connects FastAPI to the MLX-LM
service. On the Mac, as `websvc`, from the application checkout root with its
`.venv` active:

```sh
python -m pip install -e services/llm/qwen_local
python -c "from kaki_qwen_local.adapter import QwenLlm; print('Qwen adapter import OK')"
```

On Windows, install it into the worktree `.venv` for the regression tests:

```powershell
.\.venv\Scripts\python.exe -m pip install -e services/llm/qwen_local
```

The adapter declares HTTPX >=0.27,<1, already used by backend tests. Do not
install into a global Python.

#### Start the LLM service with thinking disabled

Qwen3 emits `<think>` deliberation blocks by default, which would leave the
kiosk silent while the model thinks. The server must be started with thinking
disabled; the adapter additionally strips or rejects think content as defence
in depth. Check that port 8082 is free, then start the service in a foreground
terminal:

```sh
lsof -nP -iTCP:8082 -sTCP:LISTEN
export HF_HOME=/Users/websvc/models/huggingface
~/.venvs/kaki-llm/bin/python -m mlx_lm server \
  --model mlx-community/Qwen3-8B-4bit --host 127.0.0.1 --port 8082 \
  --chat-template-args '{"enable_thinking":false}'
```

If the port is occupied, identify the process; do not kill an existing service
or change the documented port. The model is already cached; no download should
occur. Stop the service with Ctrl+C in its terminal.

#### Prepare the validation environment

Repeat these exports in every terminal of a validation session. Reuse the same
printed evidence directory within one session instead of creating another.

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp2.3"
export WP23_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp2.3/smoke.XXXXXX")"
export KAKI_LLM_MODE=qwen
export KAKI_LLM_URL=http://127.0.0.1:8082
export KAKI_LLM_TIMEOUT_SECONDS=120
printf '%s\n' "$KAKI_APP_ROOT" "$WP23_EVIDENCE"
```

`KAKI_LLM_MODE` accepts `canned` (default) or `qwen`; invalid values fail
startup. The URL must be HTTP with a literal loopback address, port and no
credentials, path or query. Readiness uses a two-second network timeout;
generation uses the configured 0.1-300-second network timeout (default 120
seconds). These bound network operations; they are not latency acceptance
targets. Redirects and proxies are disabled; response size is capped at
256 KiB. The application does not auto-load `.env`, so export settings
explicitly. Leave `KAKI_STT_MODE` unset (canned) unless the Whisper service
from 7.2 is also running.

#### Record the runtime identity

Record the runtime once per session into the evidence directory:

```sh
~/.venvs/kaki-llm/bin/python -c "import mlx_lm; print('mlx-lm', mlx_lm.__version__)"
ls "$HF_HOME/hub/models--mlx-community--Qwen3-8B-4bit/snapshots"
```

Copy both outputs into the current evidence directory together with the
application commit (`git rev-parse HEAD`), OS and Python versions.

### 7.3.2 Testing and validation

Each test states its objective. Run the tests in order on the Mac as `websvc`
with the 7.3.1 exports active.

#### Test 1: LLM service readiness

Objective: prove the model loads once, stays resident across turns, and
serves only on `127.0.0.1:8082`.

Start the service as in 7.3.1, then in a second terminal:

```sh
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8082/health
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8082/v1/models
lsof -nP -iTCP:8082 -sTCP:LISTEN
```

Expected: HTTP 200 from both endpoints, `/v1/models` listing exactly
`mlx-community/Qwen3-8B-4bit`, and only `127.0.0.1:8082` listening. Retry
manually while the model loads. Record startup errors; a listening socket
alone is not readiness.

Start order for the full stack: MLX-LM service (and Whisper, if used), then
FastAPI, then the optional simulator. Test 2 does not require FastAPI.

#### Test 2: bounded generation

Objective: prove WP2-AT-04 through the production adapter - the fixed
transcript yields a concise reply, five runs, each 60 words or fewer, with no
leaked think content - because long replies break spoken delivery for elderly
users.

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP2.3 --tier B | tee "$WP23_EVIDENCE/wp_check_wp23_tierB.json"
```

The CLI reports JSON with the configured mode/URL/model, the five replies,
word counts, per-run latencies and named checks. Expected: every check true
and exit status zero. Inspect the replies for sensible concise English; no
invented quality threshold applies.

#### Test 3: failure and recovery

Objective: prove FastAPI returns a calm `failed` response while the LLM
service is down and recovers without an application restart.

Start FastAPI in a separate foreground terminal with the 7.3.1 exports and
`.venv` active (`python -m kaki_backend.main`), confirm
`curl --fail http://127.0.0.1:8000/api/health`, then:

1. Submit a turn with a fresh `turn_id` while the LLM service is up:

   ```sh
   curl --fail --silent --show-error --max-time 120 http://127.0.0.1:8000/api/device/turn \
     -F device_id=wp23-smoke -F session_id=wp23-smoke -F turn_id=wp23-smoke-1 \
     -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/canned_reply.wav"
   ```

   Expected: `answered` with generated `reply_text` and `reply_audio` null -
   real speech arrives in WP2.4; until then answered turns degrade to text
   only because the canned TTS has no recording for generated text.
2. Stop the LLM service with Ctrl+C in its terminal. Rerun the Test 2 command;
   it must exit non-zero with `service_ready` false. Submit the turn with a
   fresh `turn_id`; expect HTTP 200, status `failed`, calm non-empty text and
   no invented speech audio.
3. Restart the LLM service, wait for Test 1 readiness, and submit a fresh-ID
   turn to prove recovery without restarting FastAPI. Expected: `answered`.

Reusing a completed failed `turn_id` deliberately returns its first failure.

#### Test 4: deterministic regression

Objective: prove the WP1 contract and all prior behaviour still hold with the
LLM adapter installed. Run the 7.2.2 Test 5 command set with both adapters
installed and `KAKI_STT_MODE`/`KAKI_LLM_MODE` unset or `canned`. The LLM
adapter unit tests live in `backend/tests/unit/test_qwen_adapter.py` and run
without a model service.

Known limitation: `scripts/tests/test_check_code_history.py` fails on any
machine because it references the deliberately removed history checker; this
predates WP2.3 and is tracked separately by the owner.

#### Teardown and evidence

Stop the stack in reverse order with Ctrl+C in each owned terminal:
simulator, FastAPI, then the LLM service. Never use broad process kills. Keep
the model cache for reruns.

Retain under `WP23_EVIDENCE`: application path and commit, OS and
architecture, Python and mlx-lm versions, model snapshot revision, the Test 2
JSON report, readiness and listener observations, the answered/failed/
recovered turn responses, and the regression results.

Evidence of the 09-Sep-2026 automated execution:
`/Users/websvc/kaki-talkie-data/wp2.3/smoke.y5wWTd/` containing
`wp_check_wp23_tierB.json` (five runs, 26 words each, all checks true),
`runtime_identity.txt`, `http_turn_answered.json`, `wp_check_llm_down.json`,
`http_turn_llm_down.json` and `http_turn_recovered.json`.

Mark VERIFIED only after the owner completes Tests 1-3 on the Mac.

## 7.4 WP2.4 - macOS say + full WP2 gate

Owner level: **G**  
Status: **VERIFIED / CLOSED 09-Sep-2026**

Machine: Mac Mini plus a protected Chrome browser on a laptop or phone.
User: `websvc`. Baseline English TTS: macOS `say`. Do not introduce RAG,
retrieval or DSPy; WP2 replies remain deliberately ungrounded.

Scope: WP2-AT-05/06/09/10/11/12 - playable synthesised speech, a full real
speech-in/speech-out turn, positive invoked stage timings with retrieval
unused, health readiness reporting, a recorded p50/p95 latency baseline and
a green WP1 regression.

### 7.4.1 Setup and installation

Install and configure through `setup.md`. This table maps each component to
its `setup.md` section. All of these are complete on the Mac Mini.

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| macOS say TTS baseline                | 10.1                |
| FastAPI runtime and configuration     | 11                  |
| Next.js simulator                     | 14                  |
| Cloudflare access to the simulator    | 15                  |
| Latency measures to record            | 18.1                |
| End-to-end fixed questions and flow   | 23                  |
+---------------------------------------+---------------------+
```

Components crucial to the solution and absent from `setup.md` are installed
here: the TTS adapter, the latency script and the development stack helper
(all repository deliverables).

#### Install the TTS adapter

The adapter is the WP2.4 deliverable: it connects FastAPI to macOS speech.
On the Mac, as `websvc`, from the application checkout root with its `.venv`
active:

```sh
python -m pip install -e services/tts/english
python -c "from kaki_say_tts.adapter import SayTts; print('Say adapter import OK')"
```

On Windows, install it into the worktree `.venv` for the regression tests
(the unit tests inject a fake runner and do not invoke `say`):

```powershell
.\.venv\Scripts\python.exe -m pip install -e services/tts/english
```

The adapter invokes the local `say` binary directly and receives 22.05 kHz
mono signed 16-bit PCM WAV from it; no FFmpeg conversion step, extra
service, model download, cache or credential is required. The `setup.md`
10.1 ffmpeg conversion remains a manual verification aid only.

#### Prepare the validation environment

Repeat these exports in every terminal of a validation session. Reuse the
same printed evidence directory within one session instead of creating
another.

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp2.4"
export WP24_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp2.4/smoke.XXXXXX")"
export KAKI_STT_MODE=whisper
export KAKI_WHISPER_URL=http://127.0.0.1:8081
export KAKI_STT_TIMEOUT_SECONDS=30
export KAKI_LLM_MODE=qwen
export KAKI_LLM_URL=http://127.0.0.1:8082
export KAKI_LLM_TIMEOUT_SECONDS=120
export KAKI_TTS_MODE=say
export KAKI_TTS_TIMEOUT_SECONDS=30
export HF_HOME=/Users/websvc/models/huggingface
printf '%s\n' "$KAKI_APP_ROOT" "$WP24_EVIDENCE"
```

`KAKI_TTS_MODE` accepts `canned` (default) or `say`; invalid values fail
startup. Synthesis uses the configured 0.1-120-second subprocess timeout
(default 30 seconds); it bounds the `say` call and is not a latency
acceptance target. A TTS failure degrades an answered turn to text only; it
does not fail the turn. The application does not auto-load `.env`, so
export settings explicitly.

#### Start the full stack

Either start each service manually in its own foreground terminal, in this
order - Whisper (7.2.2 Test 1), MLX-LM with thinking disabled (7.3.1),
FastAPI (`python -m kaki_backend.main` with the exports above), then the
optional simulator (`setup.md` 14) - or use the development stack helper
from the checkout root:

```sh
python scripts/dev_stack.py --help
python scripts/dev_stack.py up
python scripts/dev_stack.py status
```

The helper starts whisper-server, the MLX-LM server (thinking disabled) and
FastAPI detached, writes logs under `$KAKI_DATA_ROOT/logs` and pidfiles
under `$KAKI_DATA_ROOT/run`, and waits for readiness. It manages only
processes it started: `up` refuses occupied ports and existing pidfiles,
and `down` stops only its own recorded processes, in reverse order. It
never uses broad process kills. The simulator is not managed by the helper;
start it per `setup.md` 14 when the browser test needs it.

#### Record the runtime identity

Copy the WP2.2 (Whisper) and WP2.3 (MLX-LM) runtime identity records
forward into the current evidence directory and add:

```sh
sw_vers -productVersion
git -C "$KAKI_APP_ROOT" rev-parse HEAD
python --version
```

The macOS version identifies the bundled `say` engine.

### 7.4.2 Testing and validation

Each test states its objective. Run the tests in order on the Mac as
`websvc` with the 7.4.1 exports active.

#### Test 1: full stack readiness

Objective: prove the documented start order brings every service healthy
and `/api/health` reflects STT, LLM and TTS readiness (WP2-AT-10).

With the stack started as in 7.4.1:

```sh
python scripts/dev_stack.py status
curl --fail --silent --show-error --max-time 15 http://127.0.0.1:8000/api/health
lsof -nP -iTCP:8000 -iTCP:8081 -iTCP:8082 -sTCP:LISTEN
```

Expected: status `ok` with the application version and `stt_ready`,
`llm_ready` and `tts_ready` all true; only `127.0.0.1` listeners on ports
8000, 8081 and 8082. Then prove the readiness fields are live: stop the
MLX-LM service (Ctrl+C in its terminal, or
`python scripts/dev_stack.py down --only llm`), re-run the health request
and expect `llm_ready` false while `status` stays `ok`; restart it
(`... up --only llm`), wait for 7.3.2 Test 1 readiness and confirm
`llm_ready` returns true without restarting FastAPI. Health probes use
bounded two-second readiness timeouts per service.

#### Test 2: automated full-loop check

Objective: prove WP2-AT-05/06/09 through the production adapters - playable
non-zero-duration synthesised speech, a full answered turn with reply,
display and speech audio, and positive invoked stage timings with retrieval
unused.

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP2.4 --tier B | tee "$WP24_EVIDENCE/wp_check_wp24_tierB.json"
```

The CLI synthesises a fixed sentence through the say adapter, then runs one
fixture turn through the real HTTP route and reads the debug report. It
prints JSON with the decoded speech format and duration, the turn response
summary, the stage timings and named checks. Expected: every check true and
exit status zero - WAV speech with non-zero duration, state `answered`,
non-empty reply and display text, non-null `reply_audio`, positive
`audio_preparation`/`stt`/`routing`/`llm`/`tts`/`overall` timings, and null
retrieval/live-lookup timings.

#### Test 3: browser voice loop

Objective: prove real English speech in produces speech out through the
simulator - the core demo path - with the transcript and timings
inspectable (`setup.md` 23 fixed questions and flow).

In Chrome, open the protected simulator, hold the talk control, ask a fixed
question such as "How do I reset my Singpass password?", and release. Then
on the Mac:

```sh
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8000/api/device/debug/last-turn
```

Expected: the simulator plays an audible spoken English reply, the display
shows the generated reply text, and the receipt mock renders an English
slip clearly labelled as generated without sources. The debug JSON shows
the recognised transcript, language evidence, state `answered` and positive
stt/llm/tts/overall timings with retrieval null. The debug route is the
design section 13 protected debug/test view: it carries only the most
recent turn's diagnostics, is served by loopback-only FastAPI, and is
reached remotely only through the protected `/api/device/*` path.

#### Test 4: degraded input

Objective: prove empty audio and silence produce calm, well-formed
responses rather than hangs or crashes.

```sh
curl --fail --silent --show-error --max-time 120 http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp24-smoke -F session_id=wp24-smoke -F turn_id=wp24-degraded-1 \
  -F "audio=@/dev/null"
```

Expected: HTTP 200, state `failed`, calm non-empty reply text. Then hold
the simulator talk control without speaking for a few seconds and release:
expect a calm well-formed response, not a hang or crash (Whisper may
transcribe faint room noise, so an `answered` reply to noise is
acceptable; a truly empty transcript fails calmly). Use a fresh `turn_id`
for each attempt. Do not use `fixtures/empty_audio.wav` here: it is the
spoken "no audio" recording and transcribes as real speech.

#### Test 5: latency baseline

Objective: record the WP2-AT-11 p50/p95 baseline over ten runs against the
`setup.md` 18.1 measures. The five-second target is a hypothesis; record
the numbers, do not invent a pass threshold.

```sh
cd "$KAKI_APP_ROOT"
python scripts/check_latency.py --help
python scripts/check_latency.py --runs 10 \
  --input backend/src/kaki_backend/fixtures/canned_reply.wav \
  | tee "$WP24_EVIDENCE/latency_p50_p95.json"
```

Expected: exit zero, JSON with ten answered runs (each a fresh `turn_id`),
per-run end-to-end milliseconds and the overall p50 and p95. The script
sends real turns through the running stack; it fails only when a turn does
not complete as `answered`, never on a latency value.

#### Test 6: deterministic regression and shutdown

Objective: prove WP2-AT-12 - the WP1 contract and all prior WP2 behaviour
still hold - and stop the stack cleanly.

With the MLX-LM service still up, rerun the WP2.3 regression:

```sh
python scripts/wp_check.py --unit WP2.3 --tier B | tee "$WP24_EVIDENCE/wp_check_wp23_tierB.json"
```

Then run the 7.2.2 Test 5 deterministic command set (on the Mac substitute
the active `.venv` `python` for `.venv\Scripts\python.exe`) with
`KAKI_STT_MODE`/`KAKI_LLM_MODE`/`KAKI_TTS_MODE` unset or `canned`; all
adapters installed. Expected: all pass without any model service running.

Shut down in reverse order: simulator, then `python scripts/dev_stack.py
down` (or Ctrl+C in each owned terminal: FastAPI, MLX-LM, Whisper). Never
use broad process kills. Keep the runtime builds and model caches for
reruns.

#### Teardown and evidence

Retain under `WP24_EVIDENCE`: application path and commit, macOS and Python
versions, the forwarded Whisper and MLX-LM identity records, the Test 2 and
Test 5 JSON reports, the health readiness observations including the
degraded/recovered `llm_ready` values, the Test 3 debug JSON and owner
observation, the Test 4 failed responses, the WP2.3 regression JSON and the
Tier A regression results. No user audio is collected; raw turn audio
deletion remains the WP2.2-proven default.

Package-gate outcome: real English speech-in to speech-out works; replies
are clearly labelled ungrounded in WP2; raw-audio deletion remains proven;
p50/p95 are recorded; WP1 regression is green.

Evidence of the 09-Sep-2026 automated execution:
`/Users/websvc/kaki-talkie-data/wp2.4/smoke.a2jbvE/` containing
`wp_check_wp24_tierB.json` (all fifteen checks true),
`latency_p50_p95.json` (ten answered runs, p50 3167.1 ms, p95 3289.8 ms),
`health_all_ready.json`, `health_llm_down.json`,
`health_llm_recovered.json`, `http_turn_empty.json`,
`wp_check_wp23_tierB.json` and `runtime_identity.txt`.

Mark VERIFIED only after the owner completes Tests 1-6, with Test 3
performed in Chrome through the protected simulator.

---

# 8. WP3 - grounded knowledge + refusal

Status: **WP3.1 VERIFIED / CLOSED 10-Sep-2026; WP3.2 VERIFIED / CLOSED
12-Sep-2026; WP3.3 VERIFIED / CLOSED 12-Sep-2026; WP3.4 VERIFIED / CLOSED
12-Sep-2026. WP3 package gate CLOSED 12-Sep-2026.**

The fixed 8.1/8.2/8.3 skeleton is retained. Each `Prepare WP3.x` adds its
IU-labelled blocks inside 8.1 and 8.2 without renumbering, so earlier
cross-references (for example `setup.md` 13.4 to section 8.2) stay valid.

### 8.1 Setup and installation

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| Chroma storage location               | 13                  |
| Corpus split, allowlist, provenance   | 13.1, 13.2          |
| Initial 5-10 page ingestion scope     | 13.3                |
| Runtime configuration file            | 11.4                |
+---------------------------------------+---------------------+
```

Components crucial to the solution and absent from `setup.md`:

- The embedding runtime and model. `setup.md` covers Chroma storage but not
  how chunks are embedded. This selection belongs to `Prepare WP3.2`
  (embeddings/Chroma/retrieval), not WP3.1, and is recorded in `setup.md`
  when made.
- The ingestion script (repository deliverable) and its example invocation:
  covered by the WP3.1 block below.

Generated corpus snapshots belong under `KAKI_DATA_ROOT`. Commit only
intentional, small, non-sensitive deterministic fixtures.

#### WP3.1 setup - allowlist, fetch/snapshot, clean/chunk, provenance

Owner level: **S**  
Status: **VERIFIED / CLOSED 10-Sep-2026.**
Owner pilot runs on 10-Sep-2026 found that most target pages render
their content with JavaScript or block automated fetching, so the
corpus is captured manually as owner-reviewed markdown (design.md
7.2, v1.2). The manual-capture pipeline revision is implemented and
owner-validated; this section remains the reference for re-seeding and
re-running validation when the corpus changes.

Scope: WP3-AT-01/02 - ingestion writes dated runtime snapshots under
`KAKI_DATA_ROOT`, and an unchanged re-ingestion keeps content hashes stable
without duplicating chunks. WP3.1 delivers the corpus pipeline only: the
allowlist definition, snapshot store, clean/chunk and per-chunk provenance
metadata (the eight `setup.md` 13.2 fields). No embeddings, Chroma,
retrieval or backend behaviour change; the turn contract and FastAPI stack
are untouched.

Machine and account: Mac Mini as `websvc`, application checkout
`~/projects/kaki-talkie`. Deterministic tests also run on the development
checkout without network or model services.

New repository areas: the first real `rag/` implementation -
`rag/pyproject.toml` (package `kaki-rag`), `rag/src/kaki_rag/ingest/`
(fetch, clean, chunk, metadata), `rag/corpus/allowlist.yaml`, `rag/tests/`
with small deterministic HTML fixtures, `rag/README.md`, and the
owner CLI `scripts/ingest_corpus.py` (Python, per the human-operated
script contract; supersedes the advisory `ingest_corpus.sh` name in the
design tree).

Allowlist content: `rag/corpus/allowlist.yaml` holds four official
pages, each with `source_id`, URL, `page_title`, `scheme`,
`freshness_class` and `capture: manual`:

```text
+--------------------------+--------------------------------------+
| source_id                | Official source                      |
+--------------------------+--------------------------------------+
| singpass-support         | ask.gov.sg (PA Singpass reset FAQ)   |
| cdc-vouchers-residents   | vouchers.cdc.gov.sg residents' FAQ   |
| chas-about               | chas.sg FAQ                          |
| careshield-life          | cpf.gov.sg CareShield Life page      |
+--------------------------+--------------------------------------+
```

Only official government domains are eligible. The URL records the
official source for provenance; the pipeline never fetches
`capture: manual` sources live.

Manual capture workflow, per source:

1. Save the official page from the browser (PDF print or HTML export)
   as the capture record.
2. Extract the useful content to clean structured markdown: one H1
   title, section headings, the official wording, no
   banner/navigation/footer noise.
3. Review the markdown against the source page.
4. Seed it as the dated snapshot:

```sh
python scripts/seed_snapshot.py --source-id <source_id> \
    --html <path-to-markdown-file>
```

The seeding tool computes the content hash and writes the
`.meta.json` sidecar with `content_type: text/markdown`; re-seed with
`--force` after re-capturing a changed source.

Install the corpus package into the existing application environment
(prerequisites: `setup.md` 6, 7.1, 13.1). From the checkout root with its
`.venv` active:

```sh
python -m pip install -e rag
python -c "import kaki_rag; print('kaki-rag import OK')"
```

The package deliberately depends on `httpx` alone (already installed for
the backend adapters): the allowlist parser accepts a strict YAML subset
and the HTML cleaner uses the standard-library parser, so ingestion adds
no new third-party dependency on the Mac. Pending documentation
maintenance: copy this installation into `setup.md` 13 per the section 12
rule (the implementation session could not edit `setup.md`).

Prepare the validation environment in every session terminal:

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp3.1"
export WP31_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp3.1/evidence.XXXXXX")"
printf '%s\n' "$KAKI_APP_ROOT" "$WP31_EVIDENCE"
```

No new backend environment variables are introduced; ingestion reads
`KAKI_DATA_ROOT` only. No service start order changes: the ingestion CLI
is a run-to-completion tool and needs no Whisper, MLX-LM or FastAPI
process. Outbound HTTPS to the allowlisted domains is required on the Mac
for the live ingestion tests only; all committed tests run offline.

#### WP3.2 setup - multilingual embeddings, Chroma, hybrid retrieval

Owner level: **S**  
Status: **VERIFIED / CLOSED 12-Sep-2026.**
The retrieval layer was exercised end to end during WP3.3 owner
validation, which serves the grounded stack from the index this section
builds. This section remains the reference for re-indexing and
re-running retrieval validation whenever the corpus or the embedding
model changes.

Scope: WP3-AT-03/04/10 - a CDC query returns CDC evidence in the top
three, an exact `CHAS` term proves the lexical path, and Malay/Singlish/
code-switch fixtures exercise original + normalised retrieval. WP3.2
delivers the retrieval layer only: multilingual embedding of the WP3.1
processed chunks, a persistent Chroma collection under
`KAKI_DATA_ROOT/chroma`, a lexical BM25 path over the same chunks, and
hybrid merge (reciprocal rank fusion, de-duplicated by chunk identifier)
behind a `Retriever` interface per design.md 7.4. No backend, contract or
web change; grounded answering, slips and refusal remain WP3.3/WP3.4.

Machine and account: Mac Mini as `websvc`, application checkout
`~/projects/kaki-talkie`. Deterministic tests also run on the development
checkout without network or model services.

Prerequisite corpus: WP3.1 is VERIFIED and its processed store exists
(`$KAKI_DATA_ROOT/corpus/processed/chunks.jsonl`). If it is absent,
re-run WP3.1 Test 1 first.

Embedding runtime and model (the selection deferred to this block by
8.1, owner-approved 10-Sep-2026): the `sentence-transformers` runtime
with model `Qwen/Qwen3-Embedding-0.6B` (multilingual, 1024-dimensional,
roughly 1.2 GB; the adapter applies the model's built-in `query`
instruction prompt to queries only, per its model card). The approved
fallback if its quality or Mac performance disappoints is `BAAI/bge-m3`
(pass `--model BAAI/bge-m3` to the CLIs; re-index before querying). The
model caches under the Hugging Face cache at `$HF_HOME`
(`~/models/huggingface`, the same cache `scripts/dev_stack.py` uses).
Chroma runs embedded via `PersistentClient`
(no server, setup.md 13) with collection `kaki_corpus`; vectors are
always supplied by the application adapter, and Chroma's built-in
English-only default embedder stays unused. Application code depends on
the `Retriever`/embedding interfaces, not Chroma or model APIs directly.

Install into the existing application environment (prerequisites:
`setup.md` 6, 7.1, 13.1). From the checkout root with its `.venv`
active:

```sh
export HF_HOME="$HOME/models/huggingface"
python -m pip install -e "rag[retrieve,embed]"
python -c "import chromadb; print('chromadb', chromadb.__version__)"
python -c "from sentence_transformers import SentenceTransformer; \
model = SentenceTransformer('Qwen/Qwen3-Embedding-0.6B'); \
print('embedding dim', model.get_embedding_dimension())"
```

Expected: `embedding dim 1024`. The first model command downloads the
checkpoint once and needs outbound HTTPS to `huggingface.co`; later runs
read the cache offline. The `retrieve` extra adds `chromadb` and is also
what CI needs for the offline retrieval tests; the `embed` extra adds
`sentence-transformers`/`transformers` (Mac runtime only - the offline
tests use a fake embedding port and never import them).

Prepare the validation environment in every session terminal:

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp3.2"
export WP32_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp3.2/evidence.XXXXXX")"
printf '%s\n' "$KAKI_APP_ROOT" "$WP32_EVIDENCE"
```

No new backend environment variables and no service start order change:
the index and query CLIs read `KAKI_DATA_ROOT` only, run to completion,
and need no Whisper, MLX-LM or FastAPI process. Chroma data persists at
`$KAKI_DATA_ROOT/chroma`.

New repository areas: `rag/src/kaki_rag/retrieve/` (embedding port +
sentence-transformers adapter, Chroma store adapter, lexical BM25,
hybrid `Retriever`), optional extras in `rag/pyproject.toml`,
`rag/tests/` additions including the committed multilingual query
fixtures, owner CLIs `scripts/index_corpus.py` and
`scripts/query_corpus.py` (human-operated script contract), and the
WP3.2 tier B block in `scripts/wp_check.py`.

Pending documentation maintenance: record this embedding selection and
installation in `setup.md` 13 per the section 12 rule (this prepare
session edits only the runbook).

#### WP3.3 setup - grounded answerer, application provenance, output/slip

Owner level: **S**  
Status: **VERIFIED / CLOSED 12-Sep-2026.**
Owner validation on 11-12-Sep-2026 found three defects, all fixed on
12-Sep-2026: the slip attributed the answer to the top-ranked chunk
rather than the chunk the answer used; `extract_steps` clipped steps at
seven words and re-punctuated them into fragments such as "contact
the."; and the source line carried page titles, which are sometimes
whole questions. Attribution now follows the evidence block the model
cites, with a deterministic word-overlap fallback; steps are whole
sentences packed to fit; and the source line is the official domain
alone. This section remains the reference for re-running validation
after any corpus or prompt change.

Scope: WP3-AT-06/07 - answered turns cite allowlisted sources whose
URLs and dates come from application metadata, never from the LLM, and
the printed slip fits the 40-word bound with its source and "Source
checked" date. WP3.3 wires WP3.2 retrieval into the backend turn
pipeline behind the existing internal `RetrieverPort`, adds grounded
generation through the existing Qwen adapter, fills the response
`sources` from chunk provenance, and builds the English slip
deterministically. The public device contract does not change (the WP1
schema snapshot must stay green). Refusal thresholds, no-coverage
handling, devset and golden-path gating remain WP3.4;
DSPy and SQLite persistence remain later units.

Machine and account: Mac Mini as `websvc`, application checkout
`~/projects/kaki-talkie`. Deterministic tests also run on the
development checkout with canned ports, no network and no model
services.

Prerequisites: the WP2.4 full stack (runbook 7.4.1), the WP3.1 corpus,
and the WP3.2 index and embedding model install (runbook 8.1 WP3.2).
The embedding model must be present in the real Hugging Face cache
(`$HF_HOME`, `~/models/huggingface`); if `scripts/index_corpus.py` has
not yet run on this machine, complete WP3.2 Tests 1-4 first.

New environment variables (backend process):

```text
+------------------------+--------------------------------------------+
| Variable               | Meaning                                    |
+------------------------+--------------------------------------------+
| KAKI_RETRIEVAL_MODE    | canned (default) or rag                    |
| KAKI_DATA_ROOT         | required when mode is rag; locates the     |
|                        | processed corpus and Chroma collection     |
| KAKI_QUERY_NORMALISE   | on (default) or off - the WP3.3 query      |
|                        | rewrite, switchable so the latency script  |
|                        | can report both paths                      |
| KAKI_EMBEDDING_MODEL   | optional override of the approved          |
|                        | Qwen/Qwen3-Embedding-0.6B                  |
+------------------------+--------------------------------------------+
```

The default stays `canned`, so WP1/WP2 Tier A behaviour and a stack
started in the WP2 configuration are unchanged. `scripts/dev_stack.py`
exports `KAKI_RETRIEVAL_MODE=rag` (unless already set) once WP3.3
lands, so `up` starts the grounded stack.

Start the grounded stack in a prepared terminal:

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
export HF_HOME="$HOME/models/huggingface"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp3.3"
export WP33_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp3.3/evidence.XXXXXX")"
python scripts/dev_stack.py up
```

Expected: the three services start as in runbook 7.4.1. Backend
readiness now also loads the embedding model into the backend process
(roughly 1.2 GB resident; allow up to ~60 s extra on first readiness)
and `/api/health` additionally reports `"retrieval_ready": true` when
the persistent collection is reachable and non-empty. No new package
installation is needed beyond the WP3.2 extras; no new ports are
opened.

New repository areas: `rag/src/kaki_rag/adapter.py` (the backend-facing
retriever adapter over `HybridRetriever`), a slip-builder module and a
retrieval settings block in `backend/src/kaki_backend/`, grounded-prompt
support in `services/llm/qwen_local`, one committed spoken CDC-question
audio fixture for the full-turn check, new Tier A tests in
`backend/tests/` and `rag/tests/`, the WP3.3 tier B block in
`scripts/wp_check.py`, and the `dev_stack.py` retrieval export.

One-time fixture capture (owner, once, then committed and never
regenerated - `say` output changes across macOS versions). The fixture
speaks exactly this sentence: **"How do I use my CDC vouchers?"**

```sh
cd ~/projects/kaki-talkie
say -v Samantha --file-format=WAVE --data-format=LEI16@16000 \
    -o backend/src/kaki_backend/fixtures/cdc_question.wav \
    "How do I use my CDC vouchers?"
afinfo backend/src/kaki_backend/fixtures/cdc_question.wav | grep duration
```

Expected: a WAV of roughly 1.5-2.5 seconds. Commit it with the WP3.3
change. `wp_check.py --unit WP3.3` reports a clear usage error while the
fixture is missing.

#### WP3.4 setup - refusal, no-coverage, devset, golden paths

Owner level: **G**
Status: **VERIFIED / CLOSED 12-Sep-2026.**

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.
Browser tests use Chrome through the protected simulator.
Deterministic tests run with canned/fake ports, no network and no
model services.

##### Prerequisites

The WP3.3 grounded stack (runbook 8.1 WP3.3: WP2.4 full stack, WP3.1
corpus, WP3.2 index, embedding model in `$HF_HOME`). No new package,
model, service, port or `setup.md` stage.

Before Tests 2, 3 and 5 can run, capture the three spoken fixtures
described under **Fixture capture** below. `wp_check.py --unit WP3.4
--tier B` names any missing fixture and exits 2.

##### Scope

WP3-AT-05, 08, 11, 12, 13 and all five golden paths (execution plan
1.7). This is the WP3 package gate.

WP3.4 makes the grounded pipeline refuse instead of improvise:

- Unsupported or uncovered questions return state `refused` (GP3, GP5).
- Credential actions are refused before retrieval or generation (GP4).
- A committed devset and regression runner report intent accuracy against
  the >=80% target.
- All five golden paths pass.
- WP1, WP2 and WP3.1-3.3 regressions stay green.

The public device contract does not change. `refused` has been in the
WP1 state enum since WP1.1, the response keeps its nine fields, and the
WP1 schema snapshot stays unchanged.

Deferred: print/repeat intents (WP4). Malay replies arrive in WP5.1. The
live lookup and the DSPy migration are deferred beyond the MVP
(`execution-plan.md` v1.10). A WP3.4 refusal is spoken and displayed in
English only.

##### Refusal pipeline

Four layers, evaluated in order. Each layer is deterministic and testable
offline with fake ports. None calls a model to decide whether to refuse.

**Layer 1 - Intent routing** (`orchestration/intent_router.py`)

The router classifies each transcript as `answer` or `refuse` before
retrieval. WP3.4 emits these two intents only; later units add others.

A turn is refused with reason `credential_action` when it has no
procedural marker and either:

- names an authentication act: log in, login, log on, sign in, sign on,
  unlock or authenticate; or
- mentions a credential, whatever the verb: password, passcode, PIN,
  OTP, one-time password, verification code or kata laluan.

"Reset", "verify" and "transact" are not rule words. "Reset my
password" refuses because it mentions a password. "Verify my account"
and "transact for me" do not refuse at layer 1.

The procedural markers exempt a turn from both rules:

```text
+----------+----------------------------------------------------------------+
| Language | Markers                                                        |
+----------+----------------------------------------------------------------+
| English  | how do/can/to/does/would, where do/can/is/are, what do/should  |
|          | I, steps to, guide to, process for                             |
| Malay    | macam mana, bagaimana, di mana, cara nak/untuk/mahu, apa yang  |
|          | perlu/patut/harus/kena/boleh, apa langkah/cara                 |
+----------+----------------------------------------------------------------+
```

A procedural question ("How do I reset my Singpass password?", "Macam
mana nak reset kata laluan Singpass saya?") routes to `answer`, as
design.md 8 requires. The rule matches words, not secret values; a
number pattern alone never refuses.

**Why the credential rule is inverted.** Until 13-Sep-2026 it refused
only a fixed list of disclosure verbs (what is, tell me, show me, give
me, read out, say). "Print my Singpass password" missed the list,
passed the evidence gate against the Singpass corpus and got a helpful
reply. Listing more verbs would miss the next one, so any credential
mention without a procedural marker now refuses.

**Why bare "apa" is not a marker.** "Apa kata laluan Singpass saya?"
asks for the password itself, the Malay form of "What is my Singpass
password?", which refuses. Only the procedural forms of "apa" exempt.

**Consequence.** A statement that mentions a credential without asking
how now refuses, for example "I forgot my Singpass password" or "My
Singpass OTP did not arrive". The refusal wording offers the official
steps, so the user can ask again with "how do I". The word "pin" as a
verb ("Can I pin my CDC voucher?") also refuses.

**Layer 2 - Evidence gate** (after retrieval, rag mode only)

When the best dense cosine score among retrieved chunks falls below
`KAKI_EVIDENCE_MIN_DENSE` (default `0.50`), the pipeline refuses with
reason `no_coverage` and skips generation entirely.

Dense cosine is the gate metric. BM25 and the fused reciprocal-rank score
stay diagnostic in the debug view.

**Layer 3 - Model no-coverage marker** (rag mode only)

The grounded prompt tells the model to emit `SOURCE: 0` when the
official information does not cover the question. The adapter returns
this as a typed `no_coverage` flag on `GroundedReply`, and the pipeline
refuses with reason `no_coverage`. Any generated text is discarded.

This is defence in depth for near-miss questions the gate lets through.

**Mode scoping.** Layer 1 applies in every configuration because it is
a safety rule independent of retrieval. Layers 2-3 apply only when
`KAKI_RETRIEVAL_MODE=rag`. In WP2 configuration an unsupported question
keeps its ungrounded `answered` reply, so the WP1/WP2 Tier A suites and
WP2 tier B checks are unchanged. In canned STT mode the transcript is
the fixed WP1 string, which triggers nothing.

##### Calibration

Measured 12-Sep-2026 against the four-source, 27-chunk corpus with the
approved embedding model. Re-measure (Test 1) when the corpus or
embedding model changes.

```text
+--------------------------+--------------------------------------+-------+----------+
| devset id                | Question (abbreviated)               | dense | expected |
+--------------------------+--------------------------------------+-------+----------+
| singpass-en        (GP2) | How do I reset my Singpass password? | 0.861 | answer   |
| careshield-en            | What is CareShield Life ... premiums | 0.782 | answer   |
| chas-zh                  | 怎样申请CHAS卡 ... 有补贴吗          | 0.768 | answer   |
| singpass-ms              | Macam mana nak reset kata laluan ... | 0.765 | answer   |
| cdc-en             (GP1) | How do I use my CDC vouchers?        | 0.764 | answer   |
| cdc-singlish             | CDC voucher macam mana claim ah? ... | 0.758 | answer   |
| careshield-codeswitch    | CareShield Life tu apa? ... premium  | 0.739 | answer   |
| chas-en                  | Can I use CHAS at the clinic ...     | 0.631 | answer   |
| credential-action  (GP4) | Log in to my Singpass for me ...     | 0.697 | refuse*  |
| medisave-offcorpus (GP5) | How much Medisave for my hospital... | 0.428 | refuse   |
| cc-hours-volatile        | What time does the community centre  | 0.355 | refuse   |
| hdb-offcorpus      (GP5) | How do I apply for a HDB flat?       | 0.344 | refuse   |
| chit-chat                | Good morning, how are you today?     | 0.277 | refuse   |
| weather-unsupported(GP3) | What is the weather forecast ...     | 0.235 | refuse   |
| (not in the devset)      | WP1 canned fixture transcript        | 0.278 | refuse   |
+--------------------------+--------------------------------------+-------+----------+
```

Supported questions score 0.63-0.86 and unsupported ones 0.24-0.43.
The default threshold of 0.50 sits in a 0.20-wide gap with margin on
both sides. The credential action (`*`) scores 0.697 because it
resembles a supported Singpass question. Retrieval cannot catch it,
which is why layer 1 runs first.

The community-centre hours question is volatile information, correctly
refused. The live lookup is deferred beyond the MVP, so refusal is the
designed answer here rather than a gap (`design.md` 7.5).

**Implementation probe, 12-Sep-2026:** all fourteen devset items
replayed through the real routing and gate code scored 14 of 14 on the
expected side. The probe did not exercise generation, citation or
`SOURCE: 0`, so it informs Test 3 rather than replacing it.

##### Refused turn shape

```text
+---------------------+-------------------------------------------------------+
| Field               | Value                                                 |
+---------------------+-------------------------------------------------------+
| state               | refused                                               |
| reply_text          | Fixed English string, selected by refusal_reason.     |
| display_text        | Same fixed string.                                    |
| reply_audio         | TTS of the fixed string (failure degrades to text).   |
| sources             | Empty.                                                |
| case_id             | null (cases deferred beyond the MVP).                 |
| slip_text           | Referral slip (see below).                            |
+---------------------+-------------------------------------------------------+
```

Two fixed strings, selected by `refusal_reason`:

- `no_coverage` - names the four supported topics and suggests a staff
  member.
- `credential_action` - declines the request, explains the system
  cannot perform account actions, and offers the official procedure.

These are application strings, never model text. The wording is stable
for TTS, the demo and the devset.

**Referral slip.** `slip_text` contains a heading, one line telling the
user to ask a community-centre staff member, and the user's question.
It carries no `Source:` line and no `Source checked:` date,
because a refusal has no evidence. WP3-AT-07 governs answered slips
only. The refusal slip is bound by the same 40-word device limit. If the
question exceeds the budget, the slip keeps the heading and referral
line and omits the question.

Nothing prints in WP3. The printer arrives with the Pi at WP6. This
affects the simulator receipt and the slip formatter only.

##### Debug view additions

Four diagnostic fields, absent from the public response. The WP1 turn
schema snapshot is unchanged.

```text
+----------------------+----------------------------------------------------+
| Field                | Value                                              |
+----------------------+----------------------------------------------------+
| intent               | answer or refuse                                   |
| refusal_reason       | credential_action, no_coverage, or null            |
| best_dense_score     | float (0-1) or null                                |
| evidence_min_dense   | active threshold; travels with best_dense_score    |
|                      | so evidence stays interpretable after a re-tune    |
+----------------------+----------------------------------------------------+
```

##### Environment variable

```text
+--------------------------+--------------------------------------------+
| Variable                 | Meaning                                    |
+--------------------------+--------------------------------------------+
| KAKI_EVIDENCE_MIN_DENSE  | Evidence-gate threshold on best dense      |
|                          | cosine, 0-1. Default 0.50. Invalid values  |
|                          | fail startup. Used only in rag mode.       |
+--------------------------+--------------------------------------------+
```

##### Devset and regression runner

`agent/data/devset.jsonl` holds the fourteen utterances from the
calibration table, each labelled with `expected_intent`,
`expected_source_id` (where applicable) and golden path (GP1-GP5 where
it is one). Print and repeat utterances join in WP4.2.

`scripts/run_regression.py` drives `TurnPipeline` in-process with a
transcript-injecting STT port and the configured LLM and retriever
ports. It measures routing, the evidence gate, grounding and attribution
without STT variance or audio fixtures.

Requirements: MLX-LM on 8082, `KAKI_RETRIEVAL_MODE=rag`,
`KAKI_LLM_MODE=qwen`, `KAKI_DATA_ROOT`, `HF_HOME`. Does not need
Whisper, `say` or FastAPI. May run while the stack is up (loads a second
copy of the embedding model, roughly 1.2 GB).

Output: one JSON report to stdout with per-item expected and actual
intent, state, refusal reason, cited source and best dense score, then `intent_accuracy`, `golden_paths_passed` and the
pass verdict. Exit zero only when accuracy >= 0.80 and every golden-path
item passes. Writes nothing to disk.

##### Files changed and created

Changed: `contracts/ports.py`, `contracts/turn_log.py`,
`orchestration/turn_pipeline.py`, `config.py`, `api/debug.py`, the Qwen
adapter and its test, `scripts/wp_check.py`.

Created:

- `orchestration/intent_router.py` - request rules (layer 1)
- `agent/data/devset.jsonl` - evaluation data (no `agent/src`)
- `agent/README.md` - devset format and usage
- `scripts/run_regression.py` - devset runner
- `backend/tests/unit/` - router, gate, refusal shape tests
- `scripts/tests/` - runner validation with fake ports

No new dependency.

##### Fixture capture

One-time owner task, then committed and never regenerated (same as the
WP3.3 CDC fixture).

```sh
cd ~/projects/kaki-talkie
say -v Samantha --file-format=WAVE --data-format=LEI16@16000 \
    -o backend/src/kaki_backend/fixtures/singpass_question.wav \
    "How do I reset my Singpass password?"
say -v Samantha --file-format=WAVE --data-format=LEI16@16000 \
    -o backend/src/kaki_backend/fixtures/unsupported_question.wav \
    "What is the weather forecast for tomorrow?"
for f in singpass_question unsupported_question; do
    afinfo "backend/src/kaki_backend/fixtures/$f.wav" | grep duration
done
```

Expected: two WAVs of roughly 1.5-3 seconds. Record the exact spoken
text in `backend/src/kaki_backend/fixtures/README.md`.

Fixture reuse: GP1 uses `cdc_question.wav`. GP5 uses the regression
runner's HDB and MediSave items over the text path and
`unsupported_question.wav` over HTTP.

##### WP2.4 reconciliation

In grounded configuration the WP1 canned transcript is now correctly
refused (best dense 0.278, below the 0.50 gate).
`wp_check.py --unit WP2.4` therefore submits `cdc_question.wav` instead
of `canned_reply.wav` when `KAKI_RETRIEVAL_MODE=rag`. In WP2
configuration it still uses `canned_reply.wav`.

> **Re-verification note, 12-Sep-2026.** This finding was re-verified
> after the Tier A suites were made hermetic, because the original
> observation came from a session carrying `KAKI_RETRIEVAL_MODE=rag` and
> could have been the same environment leak. It is not:
> `wp_check.py --unit WP2.4 --tier B` is a Tier B Mac runtime check that
> runs with real modes exported. The grounded mode there is deliberate
> configuration, and the refusal is the gate acting correctly on a
> transcript no official source covers.

The WP2.4 latency script gains no new option. The grounded baseline
(Test 6) passes the CDC fixture as `--input`.

---

#### WP3.4 tests - refusal, devset regression and the WP3 gate

Run in order on the Mac as `websvc` with the grounded stack running
(`scripts/dev_stack.py up`; `KAKI_RETRIEVAL_MODE=rag`). WP3.4 closes
WP-level objectives Test 3 (refusal) and Test 4 (regression), and the
8.3 gate.

##### Session setup

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
export HF_HOME="$HOME/models/huggingface"
export KAKI_RETRIEVAL_MODE=rag
export KAKI_LLM_MODE=qwen
export KAKI_LLM_URL=http://127.0.0.1:8082
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp3.4"
export WP34_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp3.4/evidence.XXXXXX")"
printf '%s\n' "$KAKI_APP_ROOT" "$WP34_EVIDENCE"
```

Leave `KAKI_EVIDENCE_MIN_DENSE` unset (default 0.50) unless Test 1 says
otherwise. If you export it, restart the backend and use the same value
for the regression runner.

##### Automated runner

Test 2 observations are also registered as one command:

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP3.4 --tier B | tee "$WP34_EVIDENCE/wp_check_wp34_tierB.json"
```

Expected: `PASS: all WP3.4 tier B checks succeeded.` The manual
commands below remain for inspection and troubleshooting.

##### Test 1: evidence-gate calibration

**Objective:** confirm the default gate still separates supported from
unsupported questions on this corpus.

```sh
cd "$KAKI_APP_ROOT"
python scripts/query_corpus.py --query "How do I use my CDC vouchers?" --top-k 3 --show-paths
python scripts/query_corpus.py --query "How do I apply for a HDB flat?" --top-k 3 --show-paths
python scripts/query_corpus.py --query "What is the weather forecast for tomorrow?" --top-k 3 --show-paths
```

**Expected:** best `dense_original` >= 0.60 for CDC; <= 0.45 for the
other two. Consistent with the calibration table.

If the corpus changed and a supported question falls below 0.50 or an
unsupported one rises above it: choose a new value in the gap, export
`KAKI_EVIDENCE_MIN_DENSE`, and record a new table in the setup block.
Copy the three outputs into `WP34_EVIDENCE`.

##### Test 2: golden paths over HTTP (WP3-AT-05/08/12)

**Objective:** prove GP1-GP5 through the route the kiosk calls, with
spoken fixtures, end to end.

Submit each fixture to `/api/device/turn` with a fresh `turn_id` and
read `/api/device/debug/last-turn` after each:

```sh
for f in cdc_question singpass_question unsupported_question; do
  curl --fail --silent --show-error --max-time 300 http://127.0.0.1:8000/api/device/turn \
    -F device_id=wp34-smoke -F session_id=wp34-smoke -F "turn_id=wp34-$f-$(date +%s)" \
    -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/$f.wav" \
    | tee "$WP34_EVIDENCE/turn_$f.json"
  curl --fail --silent http://127.0.0.1:8000/api/device/debug/last-turn \
    | tee "$WP34_EVIDENCE/debug_$f.json"
done
```

**Expected per fixture:**

- **GP1** `cdc_question` - state `answered`; `sources[0]` on
  `vouchers.cdc.gov.sg`; slip within 40 words with `Source checked:`.
- **GP2** `singpass_question` - state `answered`; `sources[0]` on
  `ask.gov.sg`; debug `intent` is `answer` (a procedural question is
  never a credential action).
- **GP3** `unsupported_question` - state `refused`; fixed no-coverage
  wording; non-null `reply_audio`; empty `sources`; null `case_id`;
  referral `slip_text` within 40 words with no `Source:` or
  `Source checked:`; debug `refusal_reason` is `no_coverage`;
  `best_dense_score` < `evidence_min_dense`; `retrieval_ms` > 0;
  `llm_ms` null.
- **GP4** - covered by the devset `credential-action` item in Test 3
  (transcript-injected, no fixture needed). The item refuses with
  `credential_action` before retrieval.
- **GP5** - covered by GP3 over HTTP (gate refused rather than
  improvised) and by HDB/MediSave items in Test 3.

Every response keeps the nine-field contract. Only `answered` and
`refused` states appear.

##### Test 3: devset regression (WP3-AT-11, GP5)

**Objective:** prove the routing, gate and grounding decisions meet the
>= 80% intent target and that every golden-path item passes.

```sh
cd "$KAKI_APP_ROOT"
python scripts/run_regression.py --help
python scripts/run_regression.py --devset agent/data/devset.jsonl \
  | tee "$WP34_EVIDENCE/regression_devset.json"
```

**Expected:** exit zero; HDB and MediSave items refused with
`no_coverage`; credential item refused with `credential_action`; eight
supported items answered with their expected `source_id`;
`intent_accuracy` >= 0.80; `golden_paths_passed` equal to
`golden_paths_total` (6 of 6). The runner counts devset items tagged
with a golden path: GP5 has two items (HDB, MediSave), so GP1-GP5 give
six.

Record the actual accuracy in this section when marking VERIFIED. A
failing item is evidence, not a reason to edit the devset. Add the
diagnosis to `WP34_EVIDENCE` and change an expected label only when the
owner has explicitly changed the requirement.

##### Test 3 result, 12-Sep-2026

Owner run, retained as `regression_devset.json`. The summary fields are:

```text
+----------------------+--------+
| Field                | Value  |
+----------------------+--------+
| items                | 14     |
| items_passed         | 14     |
| intent_accuracy      | 1.00   |
| intent_target        | 0.80   |
| golden_paths_passed  | 6 of 6 |
+----------------------+--------+
```

Every item passed all four checks: intent, state, refusal reason and
cited source. The best dense scores per item are:

```text
+--------------------------+-------+-----------+-------------------+------------------------+
| devset id                | dense | state     | refusal reason    | cited source           |
+--------------------------+-------+-----------+-------------------+------------------------+
| singpass-ms              | 0.865 | answered  | -                 | singpass-support       |
| singpass-en        (GP2) | 0.861 | answered  | -                 | singpass-support       |
| careshield-en            | 0.782 | answered  | -                 | careshield-life        |
| chas-zh                  | 0.780 | answered  | -                 | chas-about             |
| cdc-en             (GP1) | 0.765 | answered  | -                 | cdc-vouchers-residents |
| cdc-singlish             | 0.753 | answered  | -                 | cdc-vouchers-residents |
| careshield-codeswitch    | 0.752 | answered  | -                 | careshield-life        |
| chas-en                  | 0.634 | answered  | -                 | chas-about             |
| medisave-offcorpus (GP5) | 0.421 | refused   | no_coverage       | -                      |
| hdb-offcorpus      (GP5) | 0.344 | refused   | no_coverage       | -                      |
| cc-hours-volatile        | 0.316 | refused   | no_coverage       | -                      |
| chit-chat                | 0.277 | refused   | no_coverage       | -                      |
| weather-unsupported(GP3) | 0.184 | refused   | no_coverage       | -                      |
| credential-action  (GP4) | null  | refused   | credential_action | -                      |
+--------------------------+-------+-----------+-------------------+------------------------+
```

Supported items scored 0.63-0.87 and unsupported ones 0.18-0.42, so the
0.50 gate still sits in a gap of about 0.21. Three scores moved from the
calibration table by more than 0.04: `singpass-ms` 0.765 to 0.865,
`weather-unsupported` 0.235 to 0.184 and `cc-hours-volatile` 0.355 to
0.316. Every move widened the gap, and no item crossed the gate. The
credential action has a null score because layer 1 refused it before
retrieval ran.

Latency per item: refusals took 23-33 ms, and the credential action took
0.4 ms. Answers took 1.5-3.2 s. The first item (`cdc-en`) took 12.5 s,
which reflects a cold model on the first generation.

##### Test 4: browser refusal loop

**Objective:** confirm a refusal is a calm spoken experience through the
simulator, and that the receipt renders appropriately.

In Chrome through the protected simulator, ask three questions in order:

1. "What is the weather tomorrow?" - expected: speaks and displays fixed
   refusal wording; receipt area renders the referral slip.
2. "Log in to my Singpass for me" - same.
3. "How do I use my CDC vouchers?" - expected: answers with a receipt as
   in WP3.3 Test 4.

The simulator needs no change for `refused` (it types the state and
renders the receipt from `slip_text`). Record observations in
`WP34_EVIDENCE`. If it misbehaves, record it as a WP3.4 defect rather
than a web-package change.

##### Test 5: grounded latency baseline

**Objective:** record grounded p50/p95 for a supported question,
counterpart to the WP2.4 ungrounded baseline (3167/3290 ms). No
threshold applies; the five-second target remains a hypothesis.

```sh
cd "$KAKI_APP_ROOT"
python scripts/check_latency.py --runs 10 \
  --input backend/src/kaki_backend/fixtures/cdc_question.wav \
  | tee "$WP34_EVIDENCE/latency_grounded_p50_p95.json"
```

**Expected:** exit zero, ten `answered` runs, p50 and p95 reported. Do
not use `canned_reply.wav` here: in grounded configuration its
transcript is correctly refused.

##### Test 6: deterministic and tier B regression (WP3-AT-13)

**Objective:** prove WP1, WP2 and WP3.1-3.3 behaviour still hold with
refusal installed.

Rerun earlier tier B runners with the stack still up:

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP2.3 --tier B | tee "$WP34_EVIDENCE/wp_check_wp23_tierB.json"
python scripts/wp_check.py --unit WP2.4 --tier B | tee "$WP34_EVIDENCE/wp_check_wp24_tierB.json"
python scripts/wp_check.py --unit WP3.3 --tier B | tee "$WP34_EVIDENCE/wp_check_wp33_tierB.json"
```

WP3.1 and WP3.2 tier B need no rerun unless the corpus or index changed.

Then run the deterministic suites from the checkout root with no model
services:

```sh
python -m ruff check --config backend/pyproject.toml backend scripts services rag
python -m unittest discover -s rag/tests -v
python -m unittest discover -s backend/tests/contract -v
python -m unittest discover -s backend/tests/unit -v
python -m unittest discover -s scripts/tests -v
```

**Expected:** all pass. The WP1 turn schema snapshot is unchanged.
WP2.4 submits the CDC fixture per the reconciliation note.

> **Hermetic suites.** As of 12-Sep-2026 the deterministic suites clear
> their own `KAKI_*` mode switches and use a disposable
> `KAKI_DATA_ROOT`, so they give the same result with the stack up, down
> or in CI. Verified both ways: 25/25 contract and 112/112 unit tests,
> identical with all four real-mode switches exported and with none.
>
> **Corrected cause note.** Earlier notes blamed the eight contract
> failures on a Starlette 1.6 `TestClient` regression. That was wrong.
> The `StarletteDeprecationWarning` is cosmetic. The real cause was
> environment inheritance: `kaki_backend.main` builds the application at
> import time from the process environment, so the validation shell's
> mode switches sent canned tests to live services. The fix is
> `kaki_test_env.py` at the checkout root, imported by every suite.
> `AGENTS.md` 5.2 and 15 carry the matching Tier A hygiene rule. Run
> every suite command from the checkout root; an `ImportError` naming
> `kaki_test_env` means the command ran from elsewhere.

The `backend/tests/unit` suite covers with fake ports: credential-action
rules including the three Singpass adversarial cases (answers procedural,
refuses action, refuses identity query), the evidence gate above and
below threshold
with generation not invoked below it, `SOURCE: 0` parsing and the
zero/one boundary, refused response shape (referral slip without
provenance, empty sources, fixed wording, TTS invoked), and that
canned-retrieval mode never refuses for coverage. `scripts/tests` covers
the devset runner's validation and pass/fail rule with fake ports. The
web suite is unaffected; rerunning it is optional.

##### Test 7: WP3 package gate

**Objective:** close WP3 (owner level G).

Complete the 8.3 grounded end-to-end gate checklist once through the
protected simulator with the fixed question. Record the tick list with
the evidence. Report the WP3 outcome: GP1-GP5 pass, WP3-AT-01 to 13
pass or listed as not applicable (WP3-AT-09 removed by owner
decision), and the devset accuracy achieved.

##### Teardown and evidence

Stop the stack: `python scripts/dev_stack.py down`.

The corpus, index and model cache remain in place for WP4.

Retain under `WP34_EVIDENCE`:

- Application commit.
- Test 1 calibration outputs.
- Three turn/debug JSON pairs from Test 2.
- Regression report and accuracy from Test 3.
- Browser observations from Test 4.
- Grounded latency JSON from Test 5.
- Three tier B reruns from Test 6.
- Tier A suite results from Test 6.
- Completed 8.3 tick list from Test 7.

No real credentials, user audio or personal data are involved.

##### Troubleshooting

- **Supported question refused with `no_coverage`:** the gate is above
  the corpus scores. Rerun Test 1 and compare with the calibration
  table.
- **`best_dense_score` null with `retrieval_ready` true:** the retriever
  returned no chunks. Check for an empty collection (WP3.2 Test 1).
- **Regression item fails on `expected_source_id` while `answered`:**
  this is an attribution issue (WP3.3 citation), not a refusal issue.

##### Known limitations

- Refusal wording is English only until WP5.1.
- `kaki_handoff` is not built in the MVP; the refusal suggests a staff
  member in words only.
- Volatile questions (opening hours, events) are refused. The live
  lookup is deferred beyond the MVP; refusal is the designed answer
  (`design.md` 7.5).
- The devset is small by design and grows from real failures.

Owner completed Tests 1-7 on the Mac; block VERIFIED and WP3 CLOSED
12-Sep-2026.

#### WP-level objectives (owned by WP3.2-WP3.4)

- Test 1, retrieval acceptance. Objective: prove the retrieval gate this
  runbook owns - source snapshots are dated; retrieval uses clean
  text/markdown, not print-to-PDF text alone; Chroma survives a backend
  restart; every retrieved chunk carries provenance metadata; answer source
  URLs and dates come from application metadata, not the LLM.
- Test 2, grounded answer. Objective: prove a supported question (for example
  CDC vouchers) returns an answer whose source URLs and dates come from
  application metadata, not the LLM.
- Test 3, refusal. Objective: prove the deliberately unsupported question
  produces a refusal rather than an invented answer - the safety property the
  pitch depends on.
- Test 4, regression. Objective: prove WP1 and WP2 behaviour still hold with
  retrieval installed.

### 8.3 Grounded end-to-end gate

Objective: prove the full grounded flow (`setup.md` section 23 target state)
through the protected simulator, once per WP3 gate:

```text
[ ] Open protected https://talkie.lookieman.dev/sim and authenticate.
[ ] Hold talk, speak the fixed question, release (or hit the 15-second cap).
[ ] FastAPI accepts the turn with a unique turn_id.
[ ] Whisper returns a useful transcript.
[ ] Retrieval returns allowlisted official evidence.
[ ] Source metadata is application-derived, not LLM-invented.
[ ] Qwen produces a concise grounded answer.
[ ] English TTS produces playable audio.
[ ] display_text and the English slip_text receipt render.
[ ] The raw recording is deleted after transcription.
[ ] Timings are recorded.
[ ] Repeating the same turn_id does not repeat a side effect.
```

---

# 9. WP4 - memory + deterministic actions

Status: **WP4.1, WP4.2 and WP4.5 VERIFIED / CLOSED 13-Sep-2026; WP4.3 and
WP4.4 WITHDRAWN 13-Sep-2026**

### 9.1 Setup and installation

##### Known setup.md coverage

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| SQLite location, permissions, schema  | 12                  |
| Backup and restore procedure          | 12.4, 20            |
| Secrets outside Git                   | 11.4                |
+---------------------------------------+---------------------+
```

##### Components absent from setup.md

None. The owner deferred the handoff and calendar capabilities beyond the
MVP on 13-Sep-2026, so no WP4 component needs an external account, token
or integration.

Install nothing for Telegram or Google Calendar. Their absence is not a
gate failure. `setup.md` 24 continues to defer Google Calendar. Morning
scheduler automation remains deferred unless the owner reintroduces it.

##### Scope

`Prepare WP4.x` fills in: prerequisites, machine, environment,
refusal pipeline impact (if any), files changed and created, and fixture
capture.

##### Runbook writing rule

When the coding agent fills in a WP4.x section during Prepare, use the
WP3.4 block as the reference structure: titled subsections (scope,
prerequisites, pipeline impact, response shape, files, fixture capture),
one topic per subsection, specification before rationale, tables for
structured fields, and troubleshooting at the end. Do not write
unbroken prose.

#### WP4.1 setup - SQLite schema, migrations, repositories, durable turn idempotency

Owner level: **S**
Status: **VERIFIED / CLOSED 13-Sep-2026.** Compressed under section 12
"Closed block compression". Gate evidence: runbook 9.2 WP4.1 tests,
kept under `$KAKI_DATA_ROOT/wp4.1/evidence.*`.

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.

##### Delivered

WP4-AT-01, 02, 03. The backend writes every completed turn to SQLite in
one transaction before it responds. A grounded turn writes one
`turn_sources` row per response source. After a restart, the same
`turn_id` returns the stored response and calls no port. The store is
the only idempotency record; the WP1.2 memory cache is gone. The device
contract, the WP1 schema snapshot and `GET /api/device/pending` (`[]`)
are unchanged. ADR-0007 records the mechanism and owner decisions 1-6.

##### Prerequisites still in force

- `KAKI_DATA_ROOT` is absolute in every mode, canned included. If it is
  unset, the backend exits at import and names the variable and
  `$KAKI_DATA_ROOT/sqlite/kaki.db`. `scripts/kaki_env.sh` and
  `dev_stack.py` export it.
- Inspect with the macOS CLI `/usr/bin/sqlite3` 3.51.0. The backend uses
  the `.venv` Python 3.12.14 `sqlite3` library 3.53.4. Both read the
  same file.

##### Storage location and lifecycle

```text
+----------------------+------------------------------------------------------+
| Item                 | Behaviour                                            |
+----------------------+------------------------------------------------------+
| Database file        | KAKI_SQLITE_PATH, else                               |
|                      | $KAKI_DATA_ROOT/sqlite/kaki.db.                      |
| Creation             | At backend start if absent; parent directory         |
|                      | created; file mode 0600 (setup.md 12.3).             |
| Migrations           | Applied at start, in order, one transaction each;    |
|                      | version in PRAGMA user_version. A database newer     |
|                      | than the code fails startup.                         |
| Connection pragmas   | Every connection: journal_mode=WAL, foreign_keys=ON, |
|                      | busy_timeout=5000, synchronous=NORMAL.               |
| Sibling files        | kaki.db-wal and kaki.db-shm; .gitignore covers all   |
|                      | three.                                               |
| Startup log line     | "kaki_backend: SQLite database <path> at schema      |
|                      | version N" on stderr, in $KAKI_DATA_ROOT/logs/       |
|                      | backend.log.                                         |
| Mechanism            | Standard-library sqlite3; numbered SQL files in      |
|                      | kaki_backend/persistence/migrations/; no ORM.        |
+----------------------+------------------------------------------------------+
```

##### Schema (migration 0001)

`persistence/migrations/0001_initial.sql` creates four tables.
Timestamps are ISO 8601 UTC text. Migration 0002 (WP4.2) adds two
columns to `turns`.

```text
+---------------+-------------------------------------------------------------+
| Table         | Columns                                                     |
+---------------+-------------------------------------------------------------+
| devices       | device_id PK, first_seen_at, last_seen_at                   |
| sessions      | session_id PK, device_id FK, started_at, last_turn_id,      |
|               | last_completed_at                                           |
| turns         | turn_id PK, session_id FK, device_id FK, state, intent,     |
|               | refusal_reason, transcript, stt_language_json, language,    |
|               | reply_text, display_text, slip_text, reply_audio BLOB,      |
|               | case_id, stt_error, llm_error, tts_error, retrieval_error,  |
|               | normalised_query, best_dense_score, evidence_min_dense,     |
|               | cited_source_id, llm_cited_index, timings_json,             |
|               | retrieval_evidence_json, replay_count, completed_at         |
| turn_sources  | turn_id FK (ON DELETE CASCADE), position, source_id,        |
|               | source_url, page_title, captured_at, source_updated_at,     |
|               | content_hash, chunk_id, retrieval_rank, dense_score, cited; |
|               | PK (turn_id, position)                                      |
+---------------+-------------------------------------------------------------+
```

A `turns` row holds the nine response fields and the whole `TurnLog`,
so a replay and the debug view rebuild from the row alone. `reply_audio`
is raw WAV bytes; base64 exists only in the response. `turn_sources`
position 0 is the cited source. A grounded turn writes one to three
rows; refused and failed turns write none. No MVP migration creates
`cases`.

##### Turn write and replay

1. Under the process lock, look up `turns` by `turn_id`.
2. On a hit, increment `replay_count` and return the stored response.
   All nine fields are identical, `reply_audio` bytes included.
3. On a miss, run the pipeline once.
4. On completion, in one transaction: upsert `devices`, upsert
   `sessions` (advance `last_turn_id`), insert `turns` and
   `turn_sources`. Commit, then respond.
5. A crash before the commit leaves no row, so a retry re-executes.

Failed and refused turns are stored like answered ones (WP1-AT-03). The
lock serialises concurrent requests with the same `turn_id` inside one
process.

##### Debug view, health and environment

`GET /api/device/debug/last-turn` reads the newest stored turn, so it
answers after a restart. It adds `replay_count`, `completed_at` and
`schema_version`. `GET /api/health` adds `storage_ready`: true when
`SELECT 1` succeeds and `user_version` equals the latest migration.

```text
+--------------------------+--------------------------------------------+
| Variable                 | Meaning                                    |
+--------------------------+--------------------------------------------+
| KAKI_SQLITE_PATH         | Optional absolute database path. Default   |
|                          | $KAKI_DATA_ROOT/sqlite/kaki.db. A relative |
|                          | value fails startup.                       |
| KAKI_DATA_ROOT           | Required and absolute in every mode.       |
+--------------------------+--------------------------------------------+
```

##### Files that still bind later units

- `backend/src/kaki_backend/persistence/` - `database.py` (file,
  pragmas, migration runner), `repositories.py`, `migrations/`.
- `scripts/wp_check.py --unit WP4.1 --tier B`; `scripts/wp4_1_evidence.sh`.
- `scripts/dev_stack.py` - backend readiness waits for `storage_ready`.
- `scripts/kaki_env.sh` - exports `KAKI_DB`.
- `scripts/check_stt.py`, `scripts/check_wp1_integration.py` - use a
  disposable database.
- `kaki_test_env.py` gives every Tier A suite a disposable
  `KAKI_DATA_ROOT`. `TurnService.reset()` clears the four tables.
- `backend/tests/contract/test_wp4_1.py` proves the restart in-process
  and across two Python processes.

##### Open reconciliation

- Runbook 13.1 step 3 lists `storage_ready` since WP4.5 (13-Sep-2026).

#### WP4.2 setup - repeat_previous, print_previous, print policy

Owner level: **S**
Status: **VERIFIED / CLOSED 13-Sep-2026.** Compressed under section 12
"Closed block compression". Gate evidence: runbook 9.2 WP4.2 tests,
kept under `$KAKI_DATA_ROOT/wp4.2/evidence.*`.

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.

##### Delivered

WP4-AT-04, 05, 06. `repeat_previous` replays the previous spoken answer
with no retrieval, LLM or TTS call. `print_previous` returns the
previous slip unchanged with no retrieval or LLM call. Under
`on_request` nothing prints until the user asks. Ten action items and
one guard item joined the devset. The response keeps nine fields
(`acted` has been in the state enum since WP1.1), the WP1 schema
snapshot is unchanged and `GET /api/device/pending` returns `[]`. Owner
decisions 2-4 (13-Sep-2026) are the rules in "Previous-turn
resolution" and "Action turn shape".

##### Prerequisites still in force

- Fixtures `repeat_request.wav` ("Can you repeat that?") and
  `print_request.wav` ("Please print that for me."): 16 kHz mono,
  `say -v Samantha`, committed and never regenerated. Capture with
  `scripts/wp4_2_evidence.sh --capture-fixtures`, which refuses to
  overwrite, removes a zero-byte file and exits 3 when no terminal is
  available for the verdict.
- A simulator built from a WP4.2 or later checkout; the print policy
  lives in the client.
- An interactive terminal for the evidence harness.
- `say`, `afplay`, `afinfo`, `jq`, `sqlite3`, `uuidgen`, `npm`.

##### Routing

`orchestration/intent_router.py` applies these rules in order. All are
deterministic and model-free:

1. Credential action (WP3.4 layer 1). "Print my Singpass password"
   refuses with `credential_action`.
2. Procedural guard. A procedural question is never an action. The
   Malay procedural markers of WP3.4 layer 1 apply here too.
3. `repeat_previous` or `print_previous`: an action verb aimed at the
   previous reply ("that", "it", "again", "the slip") in English,
   Singlish or Malay.
4. Otherwise `answer`, which continues to the WP3.4 evidence gate.

A bare topic noun never triggers an action: "Can I use CHAS for repeat
visits?", "Hari ulang tahun saya" and "I lost my CDC voucher slip" route
to `answer`. "Print my CDC voucher slip" is a print request.
`agent/data/devset.jsonl` holds ten action items (English, Singlish,
Malay, a repeat of a refusal, a print after a repeat, and one "nothing
to act on" item per action) and the procedural guard "How do I print my
CDC vouchers?", which routes to `answer`.

##### Previous-turn resolution

- Same `session_id` as the action turn.
- The newest stored turn in state `answered` or `refused`.
- `acted` and `failed` turns are skipped, so a second repeat or a print
  after a repeat resolves to the original answer.
- The lookup reads SQLite, so it works after a restart.

If no turn qualifies, the action returns "nothing to act on".

##### Action turn shape

An action turn has its own `turn_id` and is stored like any turn:

```text
+--------------+-----------------------------+-----------------------------+---------------------------+
| Field        | repeat_previous             | print_previous              | Nothing to act on         |
+--------------+-----------------------------+-----------------------------+---------------------------+
| state        | acted                       | acted                       | acted                     |
| reply_text   | Previous reply_text         | Fixed confirmation string   | Fixed string              |
| display_text | Previous display_text       | Fixed confirmation string   | Fixed string              |
| reply_audio  | Copy of previous WAV bytes; | TTS of the confirmation     | TTS of the fixed string   |
|              | no TTS call                 | (failure degrades to text)  | (failure degrades to text)|
| slip_text    | Empty                       | Previous slip_text          | Empty                     |
| sources      | Previous sources, same order| Previous sources, same order| Empty                     |
| language     | Previous language           | en                          | en                        |
| case_id      | null                        | null                        | null                      |
+--------------+-----------------------------+-----------------------------+---------------------------+
```

Fixed strings from the router catalogue: print confirmation "Here is
your slip."; nothing to act on "I have not answered a question yet.
Please ask me first." Only `print_previous` returns a slip on an
`acted` turn, so a repeat never reprints. An action turn copies the
previous turn's `turn_sources` rows, so its own replay rebuilds from its
own rows.

##### Print policy

The backend response is the same under both policies (design.md 9.3):

```text
+------------+-------------------------------------------------------------+
| Policy     | Client prints (simulator renders the receipt) when          |
+------------+-------------------------------------------------------------+
| auto       | slip_text is non-empty.                                     |
| on_request | state is acted and slip_text is non-empty.                  |
+------------+-------------------------------------------------------------+
```

A response that does not print leaves the last receipt in place. The
simulator control defaults to `auto`. The Pi applies the same rule at
WP6.3; `auto` is the demo baseline (execution plan 9, item 7).

##### Schema (migration 0002)

`persistence/migrations/0002_previous_turn.sql` sets `user_version` 2
and adds:

```text
+-------------------+---------------------------------------------------------+
| Column on turns   | Meaning                                                 |
+-------------------+---------------------------------------------------------+
| previous_turn_id  | TEXT, nullable, REFERENCES turns (turn_id), no ON       |
|                   | DELETE rule. The turn an action resolved to; null on    |
|                   | answer, refuse and "nothing to act on" turns.           |
| action_outcome    | TEXT, nullable, CHECK resolved or nothing_to_act_on.    |
|                   | Null on answer and refuse turns.                        |
+-------------------+---------------------------------------------------------+
```

Old rows read null. The `turns_by_session` index serves the lookup.
Rollback steps are in ADR-0007; `backend/tests/unit/test_actions.py`
tests the downgrade SQL.

##### Debug view

`intent` adds `repeat_previous` and `print_previous`; `schema_version`
reads 2; `previous_turn_id` and `action_outcome` are added. On an
action turn `stt_ms` and `routing_ms` are greater than 0;
`query_rewrite_ms`, `retrieval_ms`, `llm_ms`, `best_dense_score` and
`evidence_min_dense` are null; `tts_ms` is null for a resolved repeat
and greater than 0 otherwise. No new environment variable.

##### Files that still bind later units

- `backend/src/kaki_backend/actions/` - `__init__.py`
  (`ActionOutcome`, `TurnHistory`), `repeat_action.py`,
  `print_action.py`.
- `apps/web/src/simulator/printPolicy.ts` and its Tier A test (AT-06).
- `agent/data/devset.jsonl` - action items with `after`.
- `scripts/run_regression.py` - writes a disposable database, deleted
  on exit.
- `scripts/wp_check.py --unit WP4.2 --tier B`; `scripts/wp4_2_evidence.sh`.
- `scripts/dev_stack.py` - MLX-LM runs with `PYTHONUNBUFFERED=1`.
- Schema-version checks in WP4.1 tests assert "at least 1"; only WP4.2
  asserts exactly 2.

#### WP4.5 setup - backup and restore, WP4 gate

Owner level: **G**
Status: **VERIFIED / CLOSED 13-Sep-2026.** Gate evidence: runbook 9.2
WP4.5 tests, kept under `$KAKI_DATA_ROOT/wp4.5/evidence.*`.

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.
Deterministic tests run with canned ports and no model services. Tier B
runs against the WP4.2 grounded stack and database. ADR-0008 records
the decisions behind this block.

##### Prerequisites

- The WP4.2 grounded stack and database (runbook 9.1 WP4.2). No new
  package, model, service or port.
- `/usr/bin/sqlite3` 3.51.0 and `$KAKI_DATA_ROOT/backups/` (`setup.md`
  6, 12.4).
- Free disk for one backup set and one restore copy, about 33 MB each
  on 13-Sep-2026.
- One planned stop of the live backend during the restore test.
  Whisper-server and MLX-LM stay up.
- `KAKI_SQLITE_PATH` unset. The harness refuses to start otherwise, and
  `dev_stack.py` v1.5 refuses a backend whose `KAKI_SQLITE_PATH` lies
  outside `KAKI_DATA_ROOT` (exit 2).
- An interactive terminal when the evidence harness starts at Test 1
  or 2.

##### Scope

WP4-AT-13, 14, and the WP4 package gate over WP4-AT-01 to 06. WP4.5
also delivers a backup script, a session deletion script and a restore
test.
The device contract, the WP1 schema snapshot and `GET
/api/device/pending` (`[]`) are unchanged. No migration; `user_version`
stays 2.

Withdrawn: `kaki_handoff`, `calendar_create`, the `cases` table,
pending delivery state, WP4-AT-07 to 12, and presenter controls (owner
decision 1). The simulator keeps a fresh `session_id` per page load and
starts with the `auto` print policy. Deferred: backup scheduling,
pruning code, print de-duplication (WP6.3), device retry (WP6.4),
canned-scenario selection (WP6-AT-11, WP6.5).

##### Backup set

`scripts/backup_sqlite.sh` writes one set per run to
`$KAKI_DATA_ROOT/backups/<UTC timestamp>/`. Directory mode `0700`, file
mode `0600`. The script follows `AGENTS.md` 11: `--help`, non-zero exit
on failure, no delete or overwrite. It runs by hand.

```sh
scripts/backup_sqlite.sh --help
scripts/backup_sqlite.sh
```

The script builds the set as `<timestamp>.partial` and renames it on
success; a failed run leaves the `.partial` directory for inspection. It
reads the backup database only through an `immutable=1` URI, because an
ordinary open of the WAL-mode backup leaves `-wal` and `-shm` files in the
set. `ingest_running` reads `unknown` when `pgrep` cannot list processes.
Exit codes: 0 success, 1 copy or verification failure, 2 configuration
error.

```text
+----------+-------------------------+------------------------------------------------------------+
| Item     | Source                  | Method                                                     |
+----------+-------------------------+------------------------------------------------------------+
| Database | $KAKI_DB                | sqlite3 ".backup" (setup.md 12.4); safe while backend runs |
| Corpus   | $KAKI_DATA_ROOT/corpus/ | File copy                                                  |
| Index    | $KAKI_DATA_ROOT/chroma/ | File copy; restore source of truth for retrieval (ADR-0008)|
| Manifest | Written by the script   | created_utc, git commit, source database, user_version,    |
|          |                         | turns count, integrity_check, SHA-256 per file,            |
|          |                         | ingest_running and ingest_pids from pgrep -f               |
|          |                         | index_corpus.py or ingest_corpus.py                        |
+----------+-------------------------+------------------------------------------------------------+
```

Excluded: models, caches, virtual environments and build output
(`setup.md` 20.2), `.env`, and the `wp*/` evidence directories. The
owner copies evidence off the machine at pitch freeze.

##### Restore test

The restore goes into a clean temporary data root (`setup.md` 20.3).
Test 2 holds the expected results for each step.

1. In a fresh session, send `cdc_question.wav`, then
   `repeat_request.wav`. Keep both responses and each `reply_audio`
   SHA-256.
2. Run `scripts/backup_sqlite.sh` with the backend running. This is
   Test 1.
3. Stop the live backend only. Copy the backup set into a new
   `RESTORE_ROOT` under `$KAKI_DATA_ROOT/wp4.5/`.
4. Start the backend only, with `KAKI_DATA_ROOT=$RESTORE_ROOT` and
   `KAKI_SQLITE_PATH` unset.
5. Replay both step 1 `turn_id`s, each with the other fixture's audio.
6. In a separate new session, send `cdc_question.wav`. Record the
   `llm.log` completion count after it.
7. In the step 1 session, send `repeat_request.wav`.
8. Stop the restored backend. Start the live backend.

##### In-place recovery

Status: documented, not rehearsed. Use it only to replace a damaged
live database:

1. Stop the backend: `python scripts/dev_stack.py down --only backend`.
2. Move `kaki.db`, `kaki.db-wal` and `kaki.db-shm` into a dated folder.
3. Copy the backup set's `kaki.db` to `$KAKI_DB`; `chmod 600 "$KAKI_DB"`.
4. Start the backend and check `storage_ready` is true.

##### Storage and retention

Baseline, 13-Sep-2026: `kaki.db` 31.4 MB for 44 turns; reply audio is
95% of the file; about 0.9 MB per grounded answer and per repeat. The
gate records the current figures (Test 4). ADR-0008 holds the probe.

Rules in force:

- Keep every turn until after the pitch. The MVP has no pruning.
- A repeat keeps its own copy of the reply audio.
- Take a fresh backup set before pitch freeze (`setup.md` 26).
- Before a person other than the owner speaks to the simulator, reload
  the page; reload it again when they finish. A reload starts a new
  session, so their turns form one session. Add the session to
  `$KAKI_DATA_ROOT/retention/third-party-sessions.txt` (mode `0600`):
  date, the newest `sessions.session_id` after their first turn, a
  label, no full name.
- On request, delete that whole session: its `turns` rows, action turns
  included, its `turn_sources` rows, its `sessions` row, every backup
  set that holds it and evidence files that name it. Then take a fresh
  backup set.

Delete a session with `scripts/delete_session.py`. It runs dry by
default and prints turns, action turns, `turn_sources` rows and byte
totals. `--apply` refuses unless a backup set is newer than the
session's last turn, and deletes `turn_sources`, then action turns, then
the remaining turns, then the session row, in one transaction. It lists
the backup sets that hold the session and never deletes them.

```sh
python scripts/delete_session.py --session-id <session_id>
scripts/backup_sqlite.sh
python scripts/delete_session.py --session-id <session_id> --apply
```

After `--apply`, remove the listed backup sets and evidence files that
name the session, then run `scripts/backup_sqlite.sh` again.

##### Document cleanup

```text
+----------------------------------+--------------------------------------------+-------------+
| Location                         | Edit                                       | Status      |
+----------------------------------+--------------------------------------------+-------------+
| setup.md 12-12.4                 | Database file kaki-talkie.db -> kaki.db    | Done 13-Sep |
| design.md 14                     | reply audio listed on turns; ADR-0007      | Done 13-Sep |
| execution-plan.md 10             | Current execution point WP2.1 -> WP4.5     | Done 13-Sep |
| ADR-0007 Consequences            | WP4.3/WP4.4 side-effect bullet replaced    | Done 13-Sep |
| ADR-0007 reply-audio cost        | 70-180 KB estimate points to ADR-0008      | Done 13-Sep |
| Runbook section 9 status header  | WP4.3/WP4.4 withdrawn; WP4.5 DRAFT         | Done 13-Sep |
| Runbook 9.2 WP-level Test 3      | Points to WP4.5 tests                      | Done 13-Sep |
| Runbook 13.1 step 3              | Lists storage_ready                        | Done 13-Sep |
+----------------------------------+--------------------------------------------+-------------+
```

##### Owner decisions

```text
+----+---------------------------+-------------------------------------------+-----------------+
| #  | Decision                  | Choice                                    | Status          |
+----+---------------------------+-------------------------------------------+-----------------+
| 1  | Presenter controls        | Withdrawn; a reload starts a new session  | Withdrawn 13-Sep|
| 2  | Backup mechanism          | Manual script; no schedule; never deletes | Decided 13-Sep  |
| 3  | Retention                 | Rules in "Storage and retention"          | Decided 13-Sep  |
| 4  | Retrieval restore source  | Copy chroma/; manifest ingest_running     | Decided 13-Sep  |
+----+---------------------------+-------------------------------------------+-----------------+
```

##### Files changed and created

Created: `scripts/backup_sqlite.sh`, `scripts/delete_session.py`,
`scripts/wp4_5_evidence.sh`, `scripts/tests/test_backup_sqlite.py`,
`scripts/tests/test_delete_session.py`.

Changed: `scripts/wp_check.py` (WP4.5
tier B: newest backup set readability, devset action result as a count
and a rate), `scripts/kaki_env.sh` (`WP4.5`: `KAKI_DB`, `WP45_EVIDENCE`
at `wp4.5/evidence.XXXXXX`), runbook 13.1 step 3. `scripts/dev_stack.py`
v1.5 (the `KAKI_SQLITE_PATH` guard) ships with this unit unchanged.

No simulator change: the presenter-controls code was built, then
removed when decision 1 was withdrawn. No backend source change, no
migration, no new dependency, no fixture.

##### Reconciliation

- `setup.md` 12.4 shows one backup file; WP4.5 writes a timestamped set
  in the same directory with the same `.backup` command.
- `setup.md` 20 says WP4 installs "backup automation"; a manual script
  meets it under decision 2.
- `$KAKI_DATA_ROOT/backups/` is mode `0755` (05-Sep-2026) under the
  `0700` data root. The script creates each set as `0700`.

---

### 9.2 Testing and validation

#### WP4.1 tests - durable storage and restart idempotency

Run in order on the Mac as `websvc` with the grounded stack running
(`scripts/dev_stack.py up`; `KAKI_RETRIEVAL_MODE=rag`). Test 3 restarts
the backend only; whisper-server and MLX-LM stay up.

##### Session setup

```sh
cd ~/projects/kaki-talkie
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
export HF_HOME="$HOME/models/huggingface"
export KAKI_RETRIEVAL_MODE=rag
export KAKI_LLM_MODE=qwen
export KAKI_LLM_URL=http://127.0.0.1:8082
export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"
umask 077
mkdir -p "$KAKI_DATA_ROOT/wp4.1"
export WP41_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp4.1/evidence.XXXXXX")"
printf '%s\n' "$KAKI_APP_ROOT" "$KAKI_DB" "$WP41_EVIDENCE"
```

Equivalent shortcut from bash: `source scripts/kaki_env.sh WP4.1`
exports the same variables, sets `WP41_EVIDENCE` and `KAKI_DB`, and
prints the database path. Leave `KAKI_SQLITE_PATH` unset unless you
deliberately test an alternative location. Use one terminal for Tests 2-4: `WP41_TURN` must
be the same string throughout.

##### Automated runner

Test 2, a same-`turn_id` replay against the running backend and an
in-process restart replay on a disposable database are registered as
one command:

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP4.1 --tier B | tee "$WP41_EVIDENCE/wp_check_wp41_tierB.json"
```

Expected: `PASS: all WP4.1 tier B checks succeeded.` The runner reads
the live database read-only and restarts nothing, so Test 3 stays
manual. Its in-process checks need no stack and passed on 13-Sep-2026.

##### Test 1: schema and storage readiness

**Objective:** prove the backend created and migrated the database at
start and reports it ready (setup.md 12.1-12.3).

```sh
cd "$KAKI_APP_ROOT"
python scripts/dev_stack.py status
curl --fail --silent http://127.0.0.1:8000/api/health | tee "$WP41_EVIDENCE/health.json" | jq '{storage_ready, retrieval_ready}'
ls -l "$KAKI_DB"
sqlite3 "$KAKI_DB" ".tables" "pragma user_version;" | tee "$WP41_EVIDENCE/schema.txt"
grep -i 'sqlite' "$KAKI_DATA_ROOT/logs/backend.log" | tail -2
```

**Expected:** `storage_ready` true; file mode `-rw-------`; tables
`devices sessions turn_sources turns`; `user_version` 1; the backend
log names `$KAKI_DB` and schema version 1.

##### Test 2: durable grounded turn (WP4-AT-01, 02)

**Objective:** prove one completed grounded turn is stored with one
`turn_sources` row per response source.

```sh
cd "$KAKI_APP_ROOT"
export WP41_TURN="wp41-cdc-$(date +%s)"
curl --fail --silent --show-error --max-time 300 http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp41-smoke -F session_id=wp41-smoke -F "turn_id=$WP41_TURN" \
  -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/cdc_question.wav" \
  | tee "$WP41_EVIDENCE/turn_first.json" \
  | jq '{state, case_id, source_count: (.sources | length), first_source: .sources[0].source_url}'
sqlite3 -header "$KAKI_DB" \
  "select turn_id, state, intent, replay_count, completed_at from turns where turn_id='$WP41_TURN';" \
  | tee "$WP41_EVIDENCE/turns_row.txt"
sqlite3 -header "$KAKI_DB" \
  "select position, source_id, source_url, cited, retrieval_rank, dense_score
   from turn_sources where turn_id='$WP41_TURN' order by position;" \
  | tee "$WP41_EVIDENCE/turn_sources_rows.txt"
sqlite3 -header "$KAKI_DB" \
  "select device_id, last_seen_at from devices where device_id='wp41-smoke';
   select session_id, last_turn_id from sessions where session_id='wp41-smoke';"
```

**Expected:** state `answered`, `case_id` null, `source_count` between
1 and 3, `first_source` on `vouchers.cdc.gov.sg`. One `turns` row with
`replay_count` 0. `turn_sources` row count equals `source_count`;
position 0 has `cited` 1 and the same URL as `first_source`. One
`devices` row and one `sessions` row whose `last_turn_id` is
`$WP41_TURN`.

##### Test 3: restart and replay (WP4-AT-03)

**Objective:** prove the same `turn_id` returns the stored response
after a backend restart without re-executing any stage.

The replay deliberately sends a different fixture. If the pipeline ran
again, the response would be a refusal, not the CDC answer.

```sh
cd "$KAKI_APP_ROOT"
python scripts/dev_stack.py down --only backend
python scripts/dev_stack.py up --only backend
curl --fail --silent http://127.0.0.1:8000/api/health | jq '{storage_ready, retrieval_ready}'
curl --fail --silent http://127.0.0.1:8000/api/device/debug/last-turn \
  | tee "$WP41_EVIDENCE/debug_after_restart.json" | jq '{turn_id, replay_count, completed_at}'
time curl --fail --silent --show-error --max-time 60 http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp41-smoke -F session_id=wp41-smoke -F "turn_id=$WP41_TURN" \
  -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/unsupported_question.wav" \
  -o "$WP41_EVIDENCE/turn_replay.json"
diff <(jq -S . "$WP41_EVIDENCE/turn_first.json") <(jq -S . "$WP41_EVIDENCE/turn_replay.json") \
  && echo IDENTICAL | tee "$WP41_EVIDENCE/replay_diff.txt"
sqlite3 -header "$KAKI_DB" \
  "select turn_id, replay_count from turns where turn_id='$WP41_TURN';
   select count(*) as turn_rows from turns;
   select count(*) as source_rows from turn_sources where turn_id='$WP41_TURN';" \
  | tee "$WP41_EVIDENCE/replay_rows.txt"
curl --fail --silent http://127.0.0.1:8000/api/device/debug/last-turn | jq '{turn_id, replay_count}'
```

**Expected:** `storage_ready` true after the restart. Before the
replay, the debug view already shows `$WP41_TURN` with `replay_count`
0. The replay returns in well under a second (a real grounded turn
takes about 3 s); `diff` prints nothing and `IDENTICAL` follows.
`replay_count` is 1, `turn_rows` is unchanged from Test 2 plus any
turns you ran in between, `source_rows` is unchanged. The debug view
shows `replay_count` 1 and the original `completed_at`.

Optional cross-check: `grep -c 'chat/completions'
"$KAKI_DATA_ROOT/logs/llm.log"` before and after the replay gives the
same count.

##### Test 4: failed and refused turns are stored

**Objective:** prove the two non-answered states are stored as the
first result (WP1-AT-03/04 retained) and write no provenance.

```sh
cd "$KAKI_APP_ROOT"
: > "$WP41_EVIDENCE/empty.wav"
WP41_EMPTY="wp41-empty-$(date +%s)"
WP41_REFUSED="wp41-refused-$(date +%s)"
curl --fail --silent --show-error http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp41-smoke -F session_id=wp41-smoke -F "turn_id=$WP41_EMPTY" \
  -F "audio=@$WP41_EVIDENCE/empty.wav" | jq '{state}'
curl --fail --silent --show-error --max-time 300 http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp41-smoke -F session_id=wp41-smoke -F "turn_id=$WP41_REFUSED" \
  -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/unsupported_question.wav" | jq '{state}'
sqlite3 -header "$KAKI_DB" \
  "select turn_id, state, intent, refusal_reason,
          (select count(*) from turn_sources s where s.turn_id = t.turn_id) as source_rows
   from turns t where turn_id in ('$WP41_EMPTY', '$WP41_REFUSED');" \
  | tee "$WP41_EVIDENCE/non_answered_rows.txt"
```

**Expected:** states `failed` and `refused`; two rows; the refused row
has `intent` `refuse` and `refusal_reason` `no_coverage`; `source_rows`
0 for both.

##### Test 5: deterministic and tier B regression

**Objective:** prove WP1, WP2 and WP3 behaviour still hold with the
store installed.

Rerun the tier B runners with the stack still up:

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP2.3 --tier B | tee "$WP41_EVIDENCE/wp_check_wp23_tierB.json"
python scripts/wp_check.py --unit WP2.4 --tier B | tee "$WP41_EVIDENCE/wp_check_wp24_tierB.json"
python scripts/wp_check.py --unit WP3.3 --tier B | tee "$WP41_EVIDENCE/wp_check_wp33_tierB.json"
python scripts/wp_check.py --unit WP3.4 --tier B | tee "$WP41_EVIDENCE/wp_check_wp34_tierB.json"
```

WP3.1 and WP3.2 tier B rewrite the corpus and index; rerun them only if
the corpus changed.

Then run the deterministic suites from the checkout root with no
`KAKI_*` dependency on the running stack:

```sh
python -m ruff check --config backend/pyproject.toml backend scripts services rag
python -m unittest discover -s rag/tests -v
python -m unittest discover -s backend/tests/contract -v
python -m unittest discover -s backend/tests/unit -v
python -m unittest discover -s scripts/tests -v
```

**Expected:** all pass. The WP1 turn schema snapshot is unchanged.
Counts after WP4.1 (13-Sep-2026): 30 contract, 126 unit, 48 rag
tests. Every suite creates
its database under a disposable root; `$KAKI_DB` gains no rows from
this step (compare `select count(*) from turns` before and after).

##### Teardown and evidence

Stop the stack: `python scripts/dev_stack.py down`.

The database stays in place for WP4.2. Do not delete it; later units
build on the rows this session created.

Retain under `WP41_EVIDENCE`:

- Application commit.
- Health, schema and log lines from Test 1.
- First turn JSON and the three row dumps from Test 2.
- Debug JSON, replay JSON, `replay_diff.txt` and `replay_rows.txt`
  from Test 3.
- Non-answered row dump from Test 4.
- Two tier B reruns and the Tier A suite results from Test 5.

No real credentials, user audio or personal data are involved. The
stored transcripts are the fixture sentences.

##### Troubleshooting

- **`storage_ready` false or the backend exits at start:** read
  `backend.log`. "newer than this build supports" means the checkout
  is older than the database; use current `main` or move the file
  aside. A relative `KAKI_SQLITE_PATH` or a missing
  `KAKI_DATA_ROOT` is reported by name.
- **`database is locked`:** an interactive `sqlite3` shell holds a
  write transaction. Close it; the backend waits 5 s before failing.
- **Replay returns the refusal, not the CDC answer:** `WP41_TURN`
  differs from Test 2 (new terminal, or `date` re-evaluated). Check
  `echo $WP41_TURN` against `turns_row.txt`.
- **Rows missing though the turn answered:** the backend opened a
  different file. Compare `$KAKI_DB` with the path in `backend.log`.
- **`dev_stack.py up --only backend` fails on the pidfile:** run
  `down --only backend` first; it removes the record.

##### Known limitations

- `turn_id` alone is the idempotency key, as in WP1. Two devices
  reusing one `turn_id` share a result. Clients generate UUIDs, so the
  collision risk is negligible; scoping by device is not planned.
- No retention or pruning: transcripts and reply audio accumulate.
  Size review belongs with the WP4.5 backup work.
- A storage write failure after execution returns HTTP 500 and the
  client's retry re-executes. WP4.1 has no side effect beyond TTS, so
  this is safe. No later MVP unit adds an external side effect.
- The debug view exposes the newest stored turn only. Turn history is
  caregiver-UI territory and out of MVP scope.
- `cases` and pending delivery state are absent from the MVP.
- The coding agent could not run the stack-dependent tier B checks on
  13-Sep-2026: its sandbox blocks loopback binds and data-root writes,
  and no stack was running. Tests 1-5 are the owner's evidence.

Owner completed Tests 1-5 on the Mac; block VERIFIED and WP4.1 CLOSED
13-Sep-2026.

#### WP4.2 tests - repeat, print-previous and print policy

Run in order on the Mac as `websvc` with the grounded stack running and
the simulator started from the WP4.2 checkout. Test 4 restarts the
backend only. WP4.2 closes WP-level objectives Test 2 (repeat and
print-previous).

##### Evidence harness

`scripts/wp4_2_evidence.sh` runs every test in this block. This block
holds no commands; read `scripts/wp4_2_evidence.sh --help` for usage.
The harness is evidence, not the gate. `wp_check.py` stays the
automated gate, and the owner marks this block VERIFIED.

The harness follows these rules:

```text
+----------------------+-------------------------------------------------------------+
| Topic                | Rule                                                        |
+----------------------+-------------------------------------------------------------+
| Shell                | set -euo pipefail. Any failed assertion or command exits    |
|                      | non-zero and names the check.                               |
| Preconditions        | Checked before any evidence is written. Each failure names  |
|                      | what is missing and what to run: KAKI_DATA_ROOT unset or    |
|                      | relative; database missing; backend not answering on 8000;  |
|                      | schema version not 2; a fixture missing; simulator not      |
|                      | answering on 3000; no TTY; a required tool absent.          |
| Evidence directory   | New directory under $KAKI_DATA_ROOT/wp4.2, or an empty      |
|                      | exported WP42_EVIDENCE. Path echoed at start and end.       |
| Run header           | $WP42_EVIDENCE/run-header.txt, written first: date, git     |
|                      | commit and status, KAKI_DATA_ROOT, KAKI_DB, KAKI_APP_ROOT,  |
|                      | adapter settings, package versions, approved LLM and        |
|                      | embedding models, MLX-LM, whisper.cpp and macOS versions.   |
| Transcript           | The whole run is teed to $WP42_EVIDENCE/transcript.txt,     |
|                      | beside the per-step evidence files.                         |
| turn_id              | uuidgen for every turn. Never date +%s: one-second          |
|                      | resolution can reuse a stored turn_id, which replays from   |
|                      | SQLite and passes for the wrong reason. The one deliberate  |
|                      | reuses are REPEAT_REPLAY_TURN_ID and PRINT_REPLAY_TURN_ID, |
|                      | each set once and read-only.                                |
| Sessions             | Each test that needs isolation uses a fresh uuidgen         |
|                      | session_id, so rows from earlier runs cannot satisfy it.    |
| Judgement steps      | Stop and prompt: audio, answer sense, rendered receipt.     |
|                      | The owner types yes or no and a note. The verdict is       |
|                      | written to judgements.txt. The harness never prints PASS    |
|                      | for a judgement. A "no" is recorded, then exits non-zero.   |
| wp_check reruns      | Invoked directly, one unit at a time. Stdout, stderr and    |
|                      | exit code are captured per unit into their own files and    |
|                      | reported separately. Non-zero exit fails the run. The       |
|                      | harness re-implements no check and prints no verdict on     |
|                      | wp_check's behalf.                                          |
| Clocks               | Elapsed times are recorded in observations.txt with no      |
|                      | threshold. Latency targets are hypotheses at MVP stage.     |
| Test counts          | Suite and devset counts are recorded as observations, never |
|                      | asserted. Only exit codes are asserted.                     |
| Cross-checks         | Debug-view claims are confirmed from a second source where  |
|                      | a reliable one exists: llm.log chat/completions count, with |
|                      | a positive control, and SQLite rows. No whisper.log count;  |
|                      | see "Log cross-checks".                                     |
| Teardown             | Not run. The harness prints the command for the owner.      |
+----------------------+-------------------------------------------------------------+
```

##### Log cross-checks

A log count is evidence only if the line reaches the file when the
request completes. The harness keeps one log check and drops another:

```text
+-------------+-----------------------------+----------------------------+-----------+
| Log         | Line counted                | Stream when redirected     | Harness   |
+-------------+-----------------------------+----------------------------+-----------+
| llm.log     | POST /v1/chat/completions   | stderr via http.server,    | Kept      |
|             |                             | line-buffered; stdout made |           |
|             |                             | unbuffered by dev_stack.py |           |
| whisper.log | Running whisper.cpp         | stdout, block-buffered     | Removed   |
|             | inference                   |                            |           |
+-------------+-----------------------------+----------------------------+-----------+
```

**Why the Whisper check was removed.** whisper-server writes `Running
whisper.cpp inference` to stdout, which the C runtime block-buffers when
`dev_stack.py` redirects it to a file. The count therefore lags by up to
about 40 requests. Owner evidence, 13-Sep-2026: 110 `operator():
processing` lines (stderr) against 103 `Running whisper.cpp inference`
lines (stdout). The last stdout line sat at line 2257, immediately
before `Caught signal 15` at 2258 flushed the buffer. An "up by exactly
1" or "unchanged" assertion on that count passes or fails by buffer
timing, not by behaviour.

STT is proven without it. Test 2 asserts debug `stt_ms` > 0 and routes
on the recognised transcript. Test 4 sends the other action's audio
under each replayed `turn_id`, so an identical response proves STT and
the pipeline did not run. Do not reintroduce a `whisper.log` count
unless whisper-server's stdout is made unbuffered and the count is
shown to track requests one for one.

**Why the LLM check was kept.** It is the second source for the
WP4-AT-04 criterion "calls no LLM". The counted line comes from Python's
`http.server` request log, which writes to stderr; Python 3.12 keeps
stderr line-buffered when redirected. Python block-buffers redirected
stdout, so `dev_stack.py` also sets `PYTHONUNBUFFERED=1` for
`mlx_lm.server`; no LLM log line can then lag, whichever stream a
later version uses.

Before counting "unchanged" across an action, Test 2 counts the log
before and after the ordinary answer turn and asserts the count rose.
Without this positive control, a stalled log would pass the "calls no
LLM" check for the wrong reason. Each assertion compares before and
after counts around a request, so absolute numbers do not matter.

##### Automated runner

**Objective:** record the registered WP4.2 tier B checks as the gate
reports them.

The harness runs `wp_check.py --unit WP4.2 --tier B` first. Its checks
use a fresh session over HTTP: an answer, a repeat, a print, a second
repeat, replays of the print and first repeat `turn_id`s, and a
"nothing to act on" session. Replay counts are asserted on the stored
rows. The debug check expects the second repeat, uncounted: the debug
view shows the newest executed turn, and a replay writes no row.
They read the live database read-only.

**Expected:** exit code 0, recorded with stdout and stderr.

##### Test 1: schema and storage readiness

**Objective:** prove the backend applied migration 0002 at start.

**Expected:** `storage_ready` true; `user_version` 2; `turns` has
nullable `previous_turn_id` and `action_outcome` columns; the four
WP4.1 tables unchanged;
the newest backend log line names `$KAKI_DB` at schema version 2; row
counts in `turns` and `turn_sources` recorded as observations.

##### Test 2: repeat_previous (WP4-AT-04)

**Objective:** prove a repeat replays the stored answer without
retrieval, generation or speech synthesis.

The harness sends `cdc_question.wav`, then `repeat_request.wav`, in one
fresh session.

**Expected, machine-checked:**

- First turn `answered`, `sources[0]` on `vouchers.cdc.gov.sg`.
- Repeat turn `acted`; `reply_text`, `display_text`, `language`,
  `sources` and the SHA-256 of `reply_audio` equal the first turn's.
  `slip_text` empty.
- Debug: `intent` `repeat_previous`; `previous_turn_id` is the first
  turn; `action_outcome` `resolved`; `retrieval_ms`, `llm_ms`, `tts_ms`
  and `best_dense_score` null; `stt_ms` > 0.
- SQLite: one new `turns` row with that `previous_turn_id`;
  `turn_sources` rows equal the first turn's in count and order.
- Cross-checks: `llm.log` completions rose across the answer turn
  (positive control) and stayed unchanged across the repeat.

**Expected, owner judgement:** the harness writes both reply audios to
WAV files, plays them with `afplay` and asks whether the repeat sounds
the same as the answer.

##### Test 3: print_previous (WP4-AT-05)

**Objective:** prove a print returns the stored slip unchanged and a
repeat after it still resolves to the original answer.

The harness continues the Test 2 session with `print_request.wav`,
then `repeat_request.wav` again.

**Expected, machine-checked:**

- Print turn `acted`; `slip_text` byte-equal to `turns.slip_text` of
  the Test 2 answer; `reply_text` the fixed confirmation; `sources`
  equal the answer's.
- Debug: `intent` `print_previous`; `previous_turn_id` is the Test 2
  answer, not the repeat; `retrieval_ms` and `llm_ms` null.
- Second repeat: `previous_turn_id` is still the Test 2 answer.
- Cross-checks: `llm.log` completions unchanged across both turns.

**Expected, owner judgement:** the harness prints the slip wrapped to
the 32-character receipt width and asks whether it reads as a sensible
slip for the CDC answer.

##### Test 4: action idempotency and restart

**Objective:** prove both action `turn_id`s replay from the store, and
a repeat resolves from SQLite after a restart.

The harness re-sends the Test 3 print with `PRINT_REPLAY_TURN_ID` and
the Test 2 repeat with `REPEAT_REPLAY_TURN_ID`, each with the other
action's audio. It restarts the backend only, then sends a new repeat
in the Test 2 session.

**Expected:**

- Each replay identical to its original (sorted JSON diff empty); both
  stored `replay_count` values 1; total `turns` rows unchanged.
- Debug view still on the Test 3 second repeat with `replay_count` 0.
  It shows the newest executed turn, and a replay writes no row.
- Each replay sends the other action's audio, so an identical response
  shows STT and the pipeline did not run. There is no `whisper.log`
  count (see "Log cross-checks").
- After the restart: `storage_ready` true; the new repeat is `acted`
  with `previous_turn_id` equal to the Test 2 answer.

##### Test 5: nothing to act on and session isolation

**Objective:** prove an action with no eligible previous turn in its
own session answers calmly and never reaches into another session.

The harness sends `repeat_request.wav` in a new session while the Test
2 session still holds an answer.

**Expected:** state `acted`; fixed "nothing to act on" wording;
`slip_text` empty; `sources` empty; debug `previous_turn_id` null and
`action_outcome` `nothing_to_act_on`; no `turn_sources` rows; `llm.log`
completions unchanged.

##### Test 6: devset regression

**Objective:** prove routing still meets the >= 80% intent target with
the action items added, and every golden-path item passes.

The harness runs `run_regression.py` over `agent/data/devset.jsonl`
and keeps the JSON report.

**Expected:** exit code 0. The runner's own `passed` field is true for
all ten action items and the guard item; each resolved action names its
`expected_previous_id` turn;
the procedural guard item answers from `cdc-vouchers-residents`.
Item count, accuracy and golden paths passed are recorded as
observations. A failing item is evidence, not a reason to edit the
devset.

##### Test 7: print policy in the browser (WP4-AT-06)

**Objective:** prove `on_request` prints nothing until the user asks,
and `auto` keeps today's behaviour.

The harness guides the owner through Chrome one step at a time. After
each step it reads `/api/device/debug/last-turn`, asserts a new
`turn_id`, the expected `intent` and `state`, and records the JSON. It
then asks for a verdict on what the page showed. At the end it confirms
from SQLite that all five turns share one session.

```text
+------+-------------+----------------------------------+-----------------------+--------------------------------+
| Step | Policy      | Owner says                       | Machine check         | Owner verdict                  |
+------+-------------+----------------------------------+-----------------------+--------------------------------+
| 1    | on_request  | How do I use my CDC vouchers?    | answer, answered      | Spoken answer; receipt empty   |
| 2    | on_request  | Can you repeat that?             | repeat_previous,      | Same answer heard; receipt     |
|      |             |                                  | acted, previous = 1   | still empty                    |
| 3    | on_request  | Please print that for me.        | print_previous,       | Receipt shows the step 1 slip  |
|      |             |                                  | acted, previous = 1   |                                |
| 4    | auto        | What is the weather tomorrow?    | refuse, refused       | Referral slip renders at once  |
| 5    | auto        | Can you repeat that?             | repeat_previous,      | Refusal heard again; receipt   |
|      |             |                                  | acted, previous = 4   | unchanged, not reprinted       |
+------+-------------+----------------------------------+-----------------------+--------------------------------+
```

The Tier A web test proves the same rule deterministically; this test
proves it through the real page.

##### Test 8: deterministic and tier B regression

**Objective:** prove WP1 to WP4.1 behaviour still holds with actions
installed.

The harness reruns `wp_check.py` tier B for WP2.3, WP2.4, WP3.3, WP3.4
and WP4.1, one unit at a time. It then runs ruff, the rag, contract,
unit and scripts suites, and the web lint, test and build.

This scope is the record of what WP4.2 ran on 13-Sep-2026. The
within-package regression rule (`execution-plan.md` 1.1) arrived after
this block closed. Do not copy this list into a new unit.

**Expected:** every exit code 0, each reported on its own line. The
WP1 turn schema snapshot is unchanged. Test counts are recorded as
observations. `turns` row count in `$KAKI_DB` is unchanged across the
deterministic suites.

WP3.1 and WP3.2 tier B rewrite the corpus and index; the harness does
not run them.

##### Teardown and evidence

The harness prints the teardown command and does not run it. The
database stays for WP4.5, which backs it up.

Retained under `WP42_EVIDENCE`:

- `run-header.txt`, `transcript.txt`, `observations.txt`,
  `judgements.txt`.
- Automated runner stdout, stderr and exit code.
- Per test: turn and debug JSON, SQL row dumps, log-count before and
  after, reply audio WAVs from Test 2.
- Test 6 regression report.
- Test 7 debug JSON per step.
- Test 8 per-unit wp_check files and per-suite outputs.

No real credentials, user audio or personal data are involved. Stored
transcripts are fixture sentences and the owner's Test 7 questions.

##### Troubleshooting

- **Repeat returns `refused` with `no_coverage`:** action routing did
  not match the transcript. Read debug `transcript`; Whisper may have
  misheard a short fixture. Recapture only if the transcript is wrong.
- **`previous_turn_id` points at an older turn:** the harness or
  browser changed session. The simulator starts a new session on
  page reload; do not reload during Test 7.
- **Precondition "schema version is 1":** the backend runs an older
  checkout. Restart it from the WP4.2 checkout.
- **Test 7 receipt renders under `on_request` at step 1:** the
  simulator build predates WP4.2. Rebuild and restart the simulator.
- **Test 2 fails "llm.log completions rose across the answer turn":**
  the LLM log is not current. Restart MLX-LM through `dev_stack.py`,
  which sets `PYTHONUNBUFFERED=1`; a manually started server needs the
  same export.
- **`llm.log` count moves during Tests 2-5:** something else called
  MLX-LM, for example a regression run in another terminal. Rerun
  with nothing else using the stack.
- **A debug `replay_count` reads 0 right after a replay:** expected
  when the replayed turn is not the newest executed turn. The debug view
  shows the newest stored row, and a replay stores none. Read the
  stored `turns.replay_count` for the replayed `turn_id` instead.
- **Harness exits "no TTY":** run it from Terminal, not through a
  pipe or a non-interactive session.

##### Known limitations

- TTS non-invocation on a repeat rests on debug `tts_ms` null and the
  stored row. The `say` adapter writes no log, and `say` renders the
  same text to the same bytes, so equal audio alone does not prove it.
- Action routing is rule-based English, Singlish and Malay only. Other
  phrasings fall through to `answer` and are refused by the gate.
- Statements that mention a credential without a procedural marker
  refuse, for example "I forgot my Singpass password" (runbook 8.1
  WP3.4 layer 1, "Consequence").
- The simulator print policy lives in page state and resets to `auto`
  on reload. A reload also starts a new session (`session_id` is
  created once per page load), so "previous" restarts.
- No physical print. The receipt is a simulator render until WP6.3.
- Repeats copy reply audio, about 0.8 MB each at current sizes.
- The coding agent could not run any tier B check on 13-Sep-2026: the
  stack was down, and the sandbox blocks data-root writes, `.env` reads,
  loopback binds and process substitution. Tests 1-8 are the owner's
  evidence.

Owner completed Tests 1-8 on the Mac; block VERIFIED and WP4.2 CLOSED
13-Sep-2026.

#### WP4.5 tests - backup and restore, WP4 package gate

Status: **VERIFIED / CLOSED 13-Sep-2026.**

Run in order on the Mac as `websvc` with the grounded stack running
from the WP4.5 checkout. Test 2 stops the live backend and starts one
against a restored copy.

##### Evidence harness

Run `scripts/wp4_5_evidence.sh` after `source scripts/kaki_env.sh
WP4.5`; `--help` lists its side effects. It runs Tests 1-6 and follows
the WP4.2 harness rules (runbook 9.2 WP4.2, "Evidence harness"): `uuidgen` identifiers, fresh sessions, owner verdicts for
judgements, `wp_check.py` per unit, counts as observations, no
teardown. Evidence goes to `$KAKI_DATA_ROOT/wp4.5/evidence.XXXXXX`
(`WP45_EVIDENCE`).

It also restarts the live backend before it exits, on success or
failure, and prints the live `storage_ready` value. It writes to
`$KAKI_DB` only through the backend's HTTP API. It captures
`KAKI_LIVE_DATA_ROOT` before the restore phase and reads `llm.log` from
that root for the whole run: MLX-LM keeps writing where it started, so a
`$RESTORE_ROOT/logs/llm.log` count would read 0 equals 0. It runs the
devset twice, in Test 5 and in `wp_check.py --unit WP4.5`. Test 7 has no
script.

Two options control a run. The run header records both, so each
evidence directory states what it covered:

```sh
scripts/wp4_5_evidence.sh                          # Tests 1-6, scoped
scripts/wp4_5_evidence.sh --from-test 5            # resume at Test 5
scripts/wp4_5_evidence.sh --regression package     # gate commit
```

- `--from-test N` (1-6, default 1) starts at test N and runs to the
  end. Starting at 2 reruns restore steps 1 and 2 as setup, with a new
  backup set, and skips the Test 1 assertions. Starting at 4 or later
  observes the newest existing backup set in Test 4. Only a start at 1
  or 2 needs a terminal, for the Test 2 judgement.
- `--regression scoped|package` (default `scoped`) selects the Test 6
  mode.

`wp_check.py --unit WP4.5 --tier B` is the automated gate. It verifies
the newest backup set through an immutable read (manifest hashes and
file list, integrity, foreign keys, `user_version` 2, turns count,
modes, `ingest_running` true or false) and reports the action-item
intents as a count and a rate.

##### Test 1: backup a live database

**Objective:** prove `scripts/backup_sqlite.sh` makes a complete,
consistent backup set while the backend runs (`setup.md` 12.4).

**Expected:**

- Exit code 0. A new timestamped directory, mode `0700`; files `0600`.
- `pragma integrity_check` is `ok`. `pragma foreign_key_check` is
  empty. `user_version` is 2.
- Backup `turns` count is between the live count taken just before the
  backup and the live count taken just after it, inclusive.
- Manifest SHA-256 values match the files. The manifest records
  `ingest_running`; the harness records it as an observation.
- `corpus/` and `chroma/` are present. The set holds both restore step 1
  turns.
- `--help` prints usage and exits 0. A second run creates a second
  directory and leaves the first unchanged.

##### Test 2: restore into a clean root and replay (WP4-AT-03)

**Objective:** prove the backup restores to a working database that
carries stored reply audio and replays a stored turn (`setup.md` 20.3).

The harness runs the eight steps in runbook 9.1 WP4.5 "Restore test".
Test 1 is step 2 of the same run; the restore uses its first backup
set.

**Expected, machine-checked, by step:**

- Step 1: answer `answered` from `vouchers.cdc.gov.sg`; repeat `acted`
  with `previous_turn_id` the answer.
- Step 3: port 8000 stops answering. The restored `kaki.db` exists, is
  non-empty, matches its manifest SHA-256 and holds both step 1 turns,
  all before a backend starts.
- Step 4: `dev_stack.py` prints `data root: $RESTORE_ROOT`. The restored
  backend's log names
  `$RESTORE_ROOT/sqlite/kaki.db` at schema version 2. `storage_ready`
  and `retrieval_ready` are true.
- Step 5: for both replays, the sorted JSON diff against step 1 is
  empty, the `reply_audio` SHA-256 equals step 1, and the restored
  `replay_count` is 1.
- Step 6: `answered`, `sources[0]` on `vouchers.cdc.gov.sg`. The
  `llm.log` completion count rose across the turn. This is the positive
  control, and it proves the restored corpus and index are readable.
- Step 7: `acted`; `previous_turn_id` is the step 1 answer; audio
  SHA-256 equals step 1; `llm.log` count unchanged from the step 6
  snapshot.
- Step 8: live `storage_ready` true; the live backend log names
  `$KAKI_DB`; live `turns` count equals the
  after-backup count from Test 1; the step 1 answer's live
  `replay_count` is 0.

**Expected, owner judgement:** the harness plays the step 1 audio and
the step 7 audio and asks whether they sound the same.

##### Test 3: withdrawn

Test 3 is withdrawn under owner decision 1 (runbook 9.1 WP4.5 "Owner
decisions"). The harness prints `Test 3: withdrawn under owner decision
1`, records it in `observations.txt` and moves on. It runs no browser
step and asks the owner nothing.

##### Test 4: storage observation

**Objective:** record the figures the retention rules rest on.

**Expected:** the harness records, with no threshold: `kaki.db` size,
`turns` count, total and mean `reply_audio` bytes by `intent`, backup
set size, and `df -h /` free space.

##### Test 5: action regression (WP4-AT-13)

**Objective:** prove intent accuracy meets the 80% target overall and
on the action items.

The harness runs `run_regression.py` over `agent/data/devset.jsonl`.

**Expected:**

- Exit code 0.
- Report `intent_accuracy` >= 0.80.
- Action items (`expected_intent` `repeat_previous` or
  `print_previous`): correct intents >= 0.80, reported as a count and a
  rate, for example "9 of 10, 0.90".
- `golden_paths_passed` equals `golden_paths_total`.

A failing item is evidence. Do not edit the devset to pass.

##### Test 6: regression (WP4-AT-14)

**Objective:** prove the unit's own suites hold on every run, and that
golden paths and every earlier contract hold on the gate commit.

The harness runs one of two modes, chosen with `--regression`. The run
header and the Test 6 output name the mode.

```text
+-----------+--------------------------------------------------+------------------------+
| Mode      | What it runs                                     | When                   |
+-----------+--------------------------------------------------+------------------------+
| scoped    | wp_check.py --unit WP4.5 --tier B; ruff; the     | Default. Any re-run    |
| (default) | contract suite (backend/tests/contract); the     | after a code or        |
|           | scripts suite (scripts/tests); web lint, test    | document change.       |
|           | and build (apps/web).                            |                        |
| package   | Everything in scoped, plus wp_check.py --tier B  | Required once, on the  |
|           | for WP4.1 and WP4.2, one unit at a time, before  | gate commit.           |
|           | WP4.5.                                           |                        |
+-----------+--------------------------------------------------+------------------------+
```

Package mode holds WP4.1 and WP4.2 under the within-package regression
rule of `execution-plan.md` 1.1. WP4.5 writes and reads the tables WP4.1
created, and `delete_session.py` removes the action turns WP4.2 writes,
so both units qualify on the "touches" test.

Neither mode reruns a unit from an earlier work package. WP4.5 changes
no backend, rag or retrieval source, so nothing a WP2 or WP3 check
exercises has moved. Those packages keep their cover from the
deterministic suites, X-AT-01, X-AT-03 and the golden paths in Test 5.

`wp_check.py` and `kaki_env.sh` each gained a WP4.5 branch and nothing
else. Under the shared-file exception in `execution-plan.md` 1.1 that
counts as an addition, not a change to a shared path.

Neither mode runs the rag or unit suites: WP4.5 changes no backend or
rag source.

**Expected:** every exit code 0, each reported separately. The WP1 turn
schema snapshot is unchanged: its contract test passes and `git status`
shows no change to `turn_response.schema.json`. `git ls-files` lists no `*.db`,
`*.db-wal`, `*.db-shm` or `chroma/` path (X-AT-03). The `$KAKI_DB`
`turns` count is unchanged across the deterministic suites.

##### Test 7: WP4 package gate

**Objective:** the owner confirms, at level G, that WP4 meets its
acceptance criteria on one commit. The coding agent never marks this
gate passed.

Record the gate commit first. Criterion wording is in
`execution-plan.md` 5. "Rerun" means the unit's tier B check in Test 6
package mode; closed-block evidence counts only when that rerun passes.

```text
+-----------+------------------------------------+---------------------------------------------------+-----+
| Criterion | Requirement                        | Evidence                                          | [ ] |
+-----------+------------------------------------+---------------------------------------------------+-----+
| WP4-AT-01 | Completed turn durably stored      | WP4.1 Tests 2 and 4; WP4.1 rerun                  | [ ] |
| WP4-AT-02 | One turn_sources row per source    | WP4.1 Test 2; WP4.1 rerun                         | [ ] |
| WP4-AT-03 | Restart replays, no re-execution   | WP4.1 Test 3; WP4.2 Test 4; WP4.5 Test 2          | [ ] |
| WP4-AT-04 | repeat_previous calls no LLM       | WP4.2 Test 2; WP4.5 Test 2 step 7; WP4.2 rerun    | [ ] |
| WP4-AT-05 | print_previous slip unchanged      | WP4.2 Test 3; WP4.2 rerun                         | [ ] |
| WP4-AT-06 | on_request waits for a request     | WP4.2 Test 7; web printPolicy test                | [ ] |
| WP4-AT-07 | WITHDRAWN - handoff deferred       | None required                                     | n/a |
| WP4-AT-08 | WITHDRAWN - handoff deferred       | None required                                     | n/a |
| WP4-AT-09 | WITHDRAWN - calendar deferred      | None required                                     | n/a |
| WP4-AT-10 | WITHDRAWN - no case to act on      | None required                                     | n/a |
| WP4-AT-11 | WITHDRAWN - no case to act on      | None required                                     | n/a |
| WP4-AT-12 | WITHDRAWN - no case to act on      | None required                                     | n/a |
| WP4-AT-13 | Action regression intent >= 80%    | WP4.5 Test 5                                      | [ ] |
| WP4-AT-14 | Golden paths + earlier contracts   | WP4.5 Test 5; Test 6 in package mode              | [ ] |
+-----------+------------------------------------+---------------------------------------------------+-----+
```

The owner also confirms:

```text
[ ] WP-level Test 1, durability: AT-01 to 03.
[ ] WP-level Test 2, repeat and print-previous: AT-04 to 06.
[ ] WP-level Test 3, backup and restore: WP4.5 Tests 1 and 2.
[ ] X-AT-01: WP1 turn schema snapshot unchanged (Test 6).
[ ] X-AT-03: no runtime database or vector data tracked (Test 6).
[ ] X-AT-04: no earlier acceptance test weakened; review the WP4 diffs
    under backend/tests, scripts/tests and apps/web/src/test.
[ ] Presenter controls: recorded as withdrawn under owner decision 1.
[ ] The gate commit was validated with --regression package. A scoped
    run cannot close WP4.
[ ] In-place recovery (runbook 9.1 WP4.5): accepted as documented and
    not rehearsed, or rehearsed once on a disposable copy before the
    pitch. Record which.
[ ] Document cleanup rows in runbook 9.1 WP4.5 all Done.
[ ] Known limitations below accepted.
[ ] Fresh backup set taken on the gate commit (Test 1).
[ ] execution-plan.md 10 "Current execution point" set to the next
    unit. Update it at every gate close.
```

When every box is ticked, the owner marks this block VERIFIED, WP4.5
CLOSED and the WP4 package gate CLOSED, with the date and gate commit.

##### Teardown and evidence

The harness leaves the live stack running and prints `python
scripts/dev_stack.py down`. Delete `RESTORE_ROOT` after you review the
evidence. Keep the backup set.

`WP45_EVIDENCE` keeps the WP4.2 harness files (`run-header.txt`,
`transcript.txt`, `observations.txt`, `judgements.txt`) and, per test:
the Test 1 manifest, integrity output and live counts; the Test 2 JSON,
audio hashes, row dumps, backend log lines and `llm.log` counts; the
Test 5 report; the Test 6 outputs with their mode; and the Test 7
checklist with the gate commit and the owner's signature.

##### Troubleshooting

- **A test failed mid-run:** fix the cause, then rerun with
  `--from-test N` at the failed test. The new evidence directory records
  the start test; keep both directories.
- **Restored backend logs the live path:** `KAKI_SQLITE_PATH` is set in
  the shell. Unset it and restart step 4.
- **`dev_stack.py up` exits 2 with "lies outside KAKI_DATA_ROOT":** the
  v1.5 guard found an exported `KAKI_SQLITE_PATH`. Unset it and rerun.
- **Manifest `ingest_running=unknown`:** `pgrep` could not list processes,
  for example inside a sandbox. Run the backup from Terminal;
  `wp_check.py --unit WP4.5` fails on `unknown`.
- **A `.partial` directory under `backups/`:** a backup run failed. Read
  its output, fix the cause and run again. Delete the `.partial`
  directory yourself once you have inspected it.
- **`delete_session.py --apply` refuses "no backup set is newer":** run
  `scripts/backup_sqlite.sh`, then rerun `--apply`.
- **`dev_stack.py up --only backend` fails in the restore root:** the
  live backend still holds port 8000, or its pidfile lives under the
  live root. Run `down --only backend` with the live `KAKI_DATA_ROOT`
  first.
- **Restored `retrieval_ready` false, or step 6 refuses:** read
  `ingest_running` in the manifest. If it is true, take a new backup
  with no ingest running. Otherwise rebuild the index in the restore
  root with `index_corpus.py`.
- **Step 5 returns a new answer or a refusal:** the restored copy lacks
  the step 1 turns, so the backend re-executed. The backup ran before
  step 1, or a different set was restored. Check the manifest `turns`
  count and the set path.
- **Backup `turns` count outside the before-and-after range:** the
  script backed up a different file. Compare `$KAKI_DB` with the path
  in `backend.log`.
- **`integrity_check` fails on the backup:** the file came from a plain
  copy, not `.backup`. Use the script.
- **Live backend down after a failed run:** `python scripts/dev_stack.py
  up --only backend` with the live `KAKI_DATA_ROOT`, then check
  `storage_ready`.

##### Known limitations

Runbook 9.1 WP4.5 owns the storage and in-place recovery limits. These
remain:

- A simulator reload starts a new session and resets the print policy to
  `auto`, so "previous" restarts. The Pi sets its own session boundary
  in WP6.
- The backup sits on the same SSD as the database. It protects against
  corruption and operator error, not disk loss.
- A retry that reuses a stored `turn_id` replays a non-empty
  `slip_text`. An `auto` client prints the answer twice. A replayed
  `print_previous` prints twice under either policy. The simulator never
  retries; the Pi does at WP6.4. WP6.3 owns the fix: print once per
  `turn_id`. Section 11.2 Test 3 checks it.

Owner completed the WP4.5 tests on the Mac; block VERIFIED and WP4.5
CLOSED 13-Sep-2026.

#### WP-level objectives (owned by WP4.1-WP4.5)

##### Test 1: durability

**Objective:** prove turns and sessions survive a backend restart, and a
retried `turn_id` remains idempotent across the restart. This is the
property that makes the kiosk trustworthy after a power blip.

##### Test 2: repeat and print-previous

**Objective:** prove the user-facing memory behaviours work against
persisted state.

##### Test 3: backup and restore

**Objective:** prove the `setup.md` 12.4 backup restores to a working
database (`setup.md` 20.3).

Procedure and assertions: runbook 9.2 WP4.5 tests, Tests 1 and 2.

Withdrawn: the former Test 3, case lifecycle and handoff. The MVP creates
no case and hands nothing off, so WP4-AT-07 to WP4-AT-12 are withdrawn
with it.

---

# 10. WP5 - Singapore language

Status: **DRAFT - structure fixed; `Prepare WP5.1` fills in commands**

##### Scope

`execution-plan.md` v1.10 reduced WP5 to two units:

```text
+-------+----------------------------------------+-------------------+
| IU    | Delivers                               | Runbook block     |
+-------+----------------------------------------+-------------------+
| WP5.1 | language policy + baseline Malay path  | 10.1, 10.2        |
| WP5.2 | MERaLiON viability check (30 min box)  | 10.1, 10.2 Test 4 |
+-------+----------------------------------------+-------------------+
```

WP5.3 to WP5.6 are deferred beyond the MVP. Do not write blocks for them.

### 10.1 Setup and installation

##### Known setup.md coverage

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| macOS say adapter and voice check     | 10.1                |
| Malay reply voice (Amira; Damayanti)  | 10.1.1              |
| MERaLiON-3 STT (installed ahead)      | 7.3, 8.7            |
| Deferred-component policy             | 24                  |
| Model cache and disk considerations   | 9.3, 21             |
+---------------------------------------+---------------------+
```

##### Components absent from setup.md

None. WP5.1 adds no runtime: it uses the validated whisper.cpp,
MLX-LM and `say` services, and the retrieval path WP3.2 and WP3.3
already shipped. `Prepare WP5.1` checked the host on 13-Sep-2026:
`say -v '?'` lists `Amira` (`ms_MY`) and `Damayanti` (`id_ID`).
`setup.md` v1.4 makes Amira the Malay baseline, with the compact versus
enhanced choice and the service-context check.

##### Speech data

The consented multi-speaker Singapore speech set is deferred beyond the
MVP, with the bake-off it would have served. WP5.1 records only the
owner-voice utterances its single tier B turn needs, under
`$KAKI_DATA_ROOT/wp5.1/audio/`. Treat it as a demo sample rather than a
measured corpus, and say so wherever a result rests on it.

##### Challenger installation rule

Install a challenger only when a measured baseline limitation justifies
it, and only into its own virtual environment. MERaLiON-3 is the one
exception already installed, by owner decision on 13-Sep-2026
(`setup.md` 8.7).

##### Runbook writing rule

Use the WP3.4 block (section 8.1) and the section structure standard in
section 12 as the reference for every WP5.x block the coding agent
fills in during Prepare.

#### WP5.1 setup - language policy and baseline Malay path

Owner level: **S**
Status: **READY - implemented 13-Sep-2026; owner validation pending.**

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.
Tests 1 and 2 post no audio. Test 2 needs MLX-LM for the live rewrite;
Test 3 needs the grounded stack and the demo sample. Deterministic tests
run with fake ports, no network and no model services.

##### Prerequisites

- The WP4.5 grounded stack (runbook 9.2 WP4.5): whisper.cpp on 8081
  with `-l auto`, MLX-LM on 8082, FastAPI on 8000, the four-source
  corpus, the Chroma index and the embedding model in `$HF_HOME`.
- The Malay voice from `setup.md` 10.1.1: Amira (`ms_MY`), compact or
  enhanced, confirmed over SSH. Damayanti (`id_ID`) is the fallback.
- Terminal microphone permission, once, for the demo sample capture
  below: System Settings, Privacy & Security, Microphone.

No new package, model, service, port or `setup.md` stage.

##### Scope

WP5-AT-01, 02, 03, 04 and 12. WP5.1 delivers:

- a reply-language policy (`design.md` 6.4) that picks `en` or `ms`;
- Malay reply and display text for answered, refused and acted turns;
- an English slip on every answered turn, and Latin-1 text on every slip;
- Malay speech through the existing `say` subprocess;
- three Malay reply modes behind one switch;
- a configurable query-rewrite timeout, 4 s by default.

Unchanged: the nine-field turn response and the WP1 schema snapshot
(X-AT-01), the retrieval code, the evidence gate threshold and the
health response.

Changed beyond the prepared plan: migration 0003 adds three columns to
`turns`, because the owner asked for the render fallback in the debug
view and the debug view reads SQLite. See **Reconciliation**.

Out of scope: WP5.2 and every deferred WP5 unit, Hokkien, Chinese
replies, the consented speech set.

##### Language policy

`orchestration/language_policy.py` decides the reply language once per
transcribed turn, before routing. It returns `en` or `ms`. Rules run in
order and the first that decides wins:

1. **Transcript.** Count tokens found in a closed Malay word list and a
   closed English word list (function words plus common service words).
   Scheme names (CDC, CHAS, Singpass, CareShield, MediSave, HDB, CPF) and
   discourse particles (`lah`, `leh`, `lor`, `ah`, `meh`) count for
   neither. With at least `MIN_COUNTED_TOKENS` (3) counted tokens, a
   Malay share of 0.60 or more gives `ms` and 0.40 or less gives `en`.
2. **Short utterance.** At or below `SHORT_UTTERANCE_TOKENS` (6) words,
   `KAKI_LANGUAGE_PREFERENCE` decides, whatever Whisper's label says.
   Detection is weakest on short clips, and Malay loanwords cluster
   there.
3. **STT evidence as a tie-breaker.** Whisper `ms` or `id` gives `ms`,
   and `en` gives `en`, but only when the transcript holds at least one
   counted token of that language.
4. **Configured preference** for every remaining turn, including Chinese.

STT evidence never decides alone. "CDC voucher macam mana claim ah? My
handphone got the SMS one." replies in English, and "CareShield Life tu
apa? Kena bayar premium every year ke?" replies in Malay.

`agent/data/language_cases.jsonl` holds 17 curated cases for WP5-AT-02.
Each line has `id`, `transcript`, `stt_language`, `preference`,
`expected_language` and `note`.

##### Reply modes

Every answered turn generates the English grounded answer first, exactly
as before. The citation, `SOURCE: 0`, the evidence gate and the slip all
come from that first call and do not change. For a turn the policy
decided is `ms`, `KAKI_MALAY_REPLY_MODE` then selects the spoken and
displayed reply:

```text
+---------+------------------------------------------------------------------+
| Mode    | reply_text and display_text for an ms answered turn              |
+---------+------------------------------------------------------------------+
| full    | LlmPort.render_reply rewrites the English reply into Malay. The  |
|         | call receives the English reply text alone, never the evidence   |
|         | or the transcript. language is ms. WP5-AT-01 passes in this mode |
|         | only.                                                            |
| bridge  | BRIDGE_GREETING + the English reply + BRIDGE_CLOSING, fixed      |
|         | Malay strings in orchestration/reply_language.py. No render call.|
|         | language is ms. Demo-day insurance.                              |
| english | The English reply; language en. Refusals and actions are English |
|         | too. Demo-day insurance.                                         |
+---------+------------------------------------------------------------------+
```

**Render fallback, `full` mode.** The turn uses the English reply, with
`language` `en`, when the render call:

- raises an LLM error (`render_outcome` `fallback_error`);
- returns empty text (`fallback_empty`);
- returns text whose length differs from the English reply by more than
  `RENDER_LENGTH_TOLERANCE` (0.5) of the English length
  (`fallback_length`).

A successful render records `rendered`. A fallback never fails the turn.

Refusal and action wording is a fixed Malay string in `full` and
`bridge`, because it carries no prose-quality risk.

`full` adds one LLM completion to each Malay answer. By analogy with the
1.5-3.2 s grounded answers in WP3.4 Test 3, expect roughly 1.5-3 s more.
`llm_ms` covers both calls.

##### Turn shape by language

The response keeps its nine fields. Only field values change.

```text
+--------------+----------------------------+----------------------------------+
| Field        | en turn                    | ms turn                          |
+--------------+----------------------------+----------------------------------+
| language     | en                         | ms (full, bridge); en (english,  |
|              |                            | or a full-mode render fallback)  |
| reply_text   | Unchanged                  | Per reply mode (answered);       |
|              |                            | fixed Malay (refused, acted)     |
| display_text | Unchanged                  | Same as reply_text               |
| reply_audio  | Unchanged (default voice)  | Malay voice; bridge speaks the   |
|              |                            | English body in the default      |
|              |                            | voice, joined into one WAV       |
| slip_text    | Unchanged                  | English, built from the English  |
|              |                            | answer; identical in every mode  |
| state        | Unchanged                  | Unchanged                        |
| sources      | Unchanged                  | Unchanged                        |
| case_id      | null                       | null                             |
| turn_id      | Echoed                     | Echoed                           |
+--------------+----------------------------+----------------------------------+
```

Per turn type:

- **Refused `ms`:** the `ms` entries in `REFUSAL_MESSAGES`. The referral
  slip keeps its English heading and referral line and prints the
  `You asked:` line with the transcript as captured. Malay is plain Latin
  script; the English-only rule in `design.md` 9.3 exists for Hokkien and
  CJK glyphs.
- **Acted `ms`:** `print_previous` confirms in Malay and returns the
  stored slip unchanged. "Nothing to act on" answers in Malay.
  `repeat_previous` replays the stored reply, audio and language.
- **Failed:** unchanged, English.

**Printable slips.** `slip.to_printable` runs on every slip line built
from text: answer steps, the source domain and the referral question. It
composes accents, folds typographic quotes, dashes and ellipses to ASCII,
and drops anything above U+00FF, such as CJK. A question with nothing
printable left is omitted. WP6.3 confirms the code page on the real
Xprinter.

##### Retrieval and the evidence gate

WP5.1 adds no retrieval code. The gate sees the stronger leg:

- `rag/src/kaki_rag/adapter.py` sets each chunk's `dense_score` to the
  best of its `dense_original` and `dense_normalised` scores.
- `turn_pipeline.py` `_best_dense_score` takes the best across the top
  three chunks, and that value is `best_dense_score`.

Gate values for three Malay CDC questions, top three all CDC:

```text
+----------------------------------------------+----------+----------+-------------+
| Malay question                               | original | curated  | Qwen        |
|                                              | only     | English  | rewrite     |
+----------------------------------------------+----------+----------+-------------+
| Macam mana saya boleh guna baucar CDC saya?  | 0.463    | 0.770    | owner run   |
| Baucar CDC tu boleh guna kat mana?           | 0.429    | 0.727    | owner run   |
| Saya nak tahu cara tuntut baucar CDC untuk   | 0.444    | 0.807    | owner run   |
| isi rumah saya.                              |          |          |             |
+----------------------------------------------+----------+----------+-------------+
```

The first two columns come from an in-memory probe on 13-Sep-2026 with
hand-written English queries. The Qwen column is not yet measured: the
coding agent's sandbox has no Metal device, so MLX-LM cannot start
there. Test 2 measures it, and `wp_check.py --unit WP5.1` repeats it.
Record the three values here when marking the block VERIFIED. If any
Qwen value sits within 0.10 of the gate, treat it as an owner decision
before closing.

The normalised leg is load-bearing: without it all three questions fall
below the 0.50 gate. WP5.1 protects it in two ways:

1. **Rewrite guard.** `_needs_rewrite` used to skip the rewrite when
   Whisper reported `en` for 12 words or fewer. It now skips only when
   Whisper reports `en` and the policy also returns `en`.
2. **Rewrite timeout.** `KAKI_QUERY_REWRITE_TIMEOUT_SECONDS`, default 4 s,
   replaces the fixed 2 s bound. A failed rewrite still degrades to
   original-only retrieval, and the debug view now shows it
   (`rewrite_present`, `rewrite_ms`). Test 3 asserts the rewrite existed.

##### Speech output

`SayTts.synthesize` gains a language argument. `en` runs `say` exactly
as before, with no `-v`. `ms` adds `-v "$KAKI_TTS_VOICE_MS"`. The
pipeline passes the argument only for a Malay segment, so English calls
are unchanged. A missing voice makes `say` exit non-zero, which raises
`TtsError` and degrades the turn to text. `say` output keeps its format,
`LEI16@22050` mono, so bridge segments join without resampling.

##### Environment variables

```text
+------------------------------------+---------------------------------------+
| Variable                           | Meaning                               |
+------------------------------------+---------------------------------------+
| KAKI_LANGUAGE_PREFERENCE           | en or ms. Default en. Decides short   |
|                                    | utterances and open ties. Invalid     |
|                                    | values fail startup.                  |
| KAKI_MALAY_REPLY_MODE              | full, bridge or english. Default      |
|                                    | full. Invalid values fail startup.    |
| KAKI_TTS_VOICE_MS                  | say voice for Malay. Default Amira;   |
|                                    | fallback Damayanti. Blank fails       |
|                                    | startup.                              |
| KAKI_QUERY_REWRITE_TIMEOUT_SECONDS | Rewrite timeout, 0.1-30 s. Default 4. |
|                                    | Invalid values fail startup.          |
+------------------------------------+---------------------------------------+
```

All four are read at backend start. Restart the backend after changing
one. `dev_stack.py` passes them through unchanged, because every child
inherits the shell environment. `run_regression.py` reads the same
variables, so the devset runs with the backend's configuration.
`TurnPipeline` built without these settings defaults to `english` mode,
the pre-WP5.1 behaviour.

At startup the backend writes one line to `backend.log`, next to the
SQLite line:

```text
kaki_backend: reply language preference en, Malay reply mode full, Malay voice Amira
```

The evidence harness reads the active mode and voice from this line.

##### Debug view additions

Five fields, absent from the public response:

```text
+-----------------+----------------------------------------------------------+
| Field           | Value                                                    |
+-----------------+----------------------------------------------------------+
| reply_language  | The policy decision, en or ms; null on failed turns      |
| reply_mode      | full, bridge or english; null on failed turns            |
| render_outcome  | rendered, fallback_empty, fallback_length, fallback_error|
|                 | or null when no render ran                               |
| rewrite_present | true when the turn had a normalised English query        |
| rewrite_ms      | Rewrite duration (timings query_rewrite_ms) or null      |
+-----------------+----------------------------------------------------------+
```

The first three are stored by migration 0003 (`reply_language`,
`reply_mode`, `render_outcome`, all nullable and constrained). The last
two derive from existing columns. Rows written before 0003 read null.
Rollback: with the backend stopped and a backup taken, drop the three
columns in reverse order and set `PRAGMA user_version = 2`.

##### Files changed and created

Changed:

- `contracts/ports.py`: `LlmPort.render_reply`, and a language argument
  on `TtsPort.synthesize`.
- `contracts/turn_log.py`, `persistence/repositories.py`, `api/debug.py`:
  the diagnostics above.
- `orchestration/turn_pipeline.py`: policy call, reply modes, rewrite
  guard, speech segments.
- `orchestration/intent_router.py`: `ms` refusal and action catalogues.
- `orchestration/slip.py`: `to_printable` on every slip.
- `orchestration/canned_ports.py`: canned `render_reply` and language
  argument.
- `actions/print_action.py`, `actions/repeat_action.py`: wording in the
  turn language.
- `config.py`, `main.py`: `LanguageSettings`, the Malay voice, the
  rewrite timeout and the startup line.
- `services/llm/qwen_local` adapter: the render prompt (a temporary
  constant beside the existing prompts until DSPy) and the configurable
  rewrite timeout.
- `services/tts/english` adapter: voice by language.
- `scripts/run_regression.py`, `scripts/wp_check.py`,
  `scripts/kaki_env.sh`, `scripts/wp4_5_evidence.sh`.
- Tests: `test_qwen_adapter.py`, `test_say_adapter.py`,
  `test_refusal_pipeline.py`, `rag/tests/test_adapter.py` (new tests);
  `test_actions.py`, `test_intent_router.py`, `test_action_routing.py`,
  `backend/tests/contract/test_wp4_2.py`,
  `scripts/tests/test_backup_sqlite.py` (reconciled, see below).

Created:

- `orchestration/language_policy.py` - reply-language rules
- `orchestration/reply_language.py` - reply modes, render check, WAV join
- `persistence/migrations/0003_reply_language.sql` - debug columns
- `agent/data/language_cases.jsonl` - WP5-AT-02 curated cases
- `backend/tests/unit/test_language_policy.py` - rules over the cases
- `backend/tests/unit/test_malay_reply.py` - turn shape, modes, slips,
  storage, settings
- `backend/tests/contract/test_wp5_1.py` - debug fields over HTTP
- `scripts/wp5_1_evidence.sh` - owner evidence harness (10.2)

No new dependency and no web change. The simulator already sets its
speech language from `response.language`.

##### Shared-file changes

Under the shared-file exception in `execution-plan.md` 1.1:

- `wp_check.py` gains a WP5.1 tier B branch, and `kaki_env.sh` gains a
  WP5.1 case. Both are additions.
- `wp_check.py` also relaxes two schema-version checks: WP4.2
  `live_database_at_least_schema_version_2` and WP4.5
  `backup_schema_version_at_least_2` now read "at least 2".
  `wp4_5_evidence.sh` derives its expected version from the packaged
  migrations. These change earlier units' code paths in WP4, a different
  package, so no tier B rerun follows.
- `run_regression.py` `build_pipeline` passes the language settings, and
  its silent TTS accepts a language. That is a change to a shared code
  path. It would rerun earlier WP5 units, but WP5.1 is the first, so no
  tier B rerun applies. The golden paths in Test 5 cover it.
- `dev_stack.py` is unchanged.

`wp_check.py --unit WP5.1 --tier B` checks:

- the configured Malay voice is listed by `say -v '?'` and synthesises
  non-zero audio;
- for the three probe questions: a live Qwen rewrite exists, a CDC chunk
  is in the top three, and the gate value with the rewrite and with the
  curated query is at or above `KAKI_EVIDENCE_MIN_DENSE`. It reports all
  three gate values and flags any within 0.10 of the gate;
- one Malay CDC transcript through `TurnPipeline` with live Qwen and a
  disposable database: `answered`, cites CDC, rewrite present, policy
  `ms`, `language` per mode, English slip, and in `full` mode
  `render_outcome` `rendered`.

It posts no audio and writes nothing to `$KAKI_DB`.

`kaki_env.sh WP5.1` exports `KAKI_DB`, replaces the smoke directory
with `$KAKI_DATA_ROOT/wp5.1/evidence.XXXXXX` as `WP51_EVIDENCE`, and
exports `WP51_AUDIO=$KAKI_DATA_ROOT/wp5.1/audio`.

##### Demo sample capture

One-time owner task. Record four utterances in your own voice. They are
a demo sample, not a measured corpus: one speaker, one microphone, one
room. They live under `$KAKI_DATA_ROOT`, never in Git. Keep them until
WP5.2 has used them, then delete the directory.

```text
+-----------------------+-------------------------------------------------------+
| File                  | Say                                                   |
+-----------------------+-------------------------------------------------------+
| ms_cdc.wav            | Macam mana saya boleh guna baucar CDC saya?           |
| ms_codeswitch.wav     | CareShield Life tu apa? Kena bayar premium setiap     |
|                       | tahun ke?                                             |
| en_sg_cdc.wav         | CDC voucher how to use ah? Can use at the hawker      |
|                       | centre or not?                                        |
| ms_unsupported.wav    | Esok cuaca macam mana, ada hujan tak?                 |
+-----------------------+-------------------------------------------------------+
```

Find the microphone index, then record each file. The recording stops
after 8 seconds. Start speaking when the counter appears.

```sh
source scripts/kaki_env.sh WP5.1
mkdir -p "$WP51_AUDIO"
ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | grep -A5 'audio devices'
ffmpeg -hide_banner -f avfoundation -i ":0" -t 8 -ac 1 -ar 16000 -c:a pcm_s16le \
    "$WP51_AUDIO/ms_cdc.wav"
afplay "$WP51_AUDIO/ms_cdc.wav"
```

Replace `:0` with your microphone index. Repeat the last two commands
for the other three files.

Expected: four WAVs, each 2-8 seconds, each clearly audible on
playback. Write the exact spoken text of any file that differs from the
table into `$WP51_AUDIO/README.txt`.

##### Reconciliation

- **Migration 0003.** The prepared block promised no schema change. The
  owner's render-fallback debug field needs storage, because the debug
  view reads SQLite (WP4.1). The migration only adds nullable columns.
- **Earlier schema-version assertions.** WP4.2 pinned the exact schema
  version 2 in `test_actions.py`, `test_wp4_2.py`, `wp_check.py` and the
  backup test, and WP4.5 did in its harness. They now check the WP4.2
  schema in isolation, or "at least 2", or the packaged version. What
  each test proves about migration 0002 is unchanged (X-AT-04). The
  closed WP4.2 and WP4.5 test blocks still say "schema version 2"; read
  that as "at least 2".
- **Unknown-language fallback tests.** Two tests used `ms` as a language
  without wording. Malay now has wording, so they use `zh`.
- **Rewrite timeout.** WP3.3's fixed 2 s bound is now configuration,
  default 4 s.
- **Referral slip.** The prepared block dropped `You asked:` on Malay
  turns. By owner decision it stays, within Latin-1.
- **Voice.** `setup.md` v1.4 makes Amira the Malay baseline and
  Damayanti the fallback. The harness records which variant survived the
  SSH check.
- **Runbook 8.1 WP3.4.** "Refusal wording is English only until WP5.1"
  becomes historical once WP5.1 closes. The closed block stays unchanged.

### 10.2 Testing and validation

Tiers matter here, because WP5 has one working day. Tests 1 and 2 post no
audio. Only Tests 3 and 4 need spoken input and the owner.

```text
+--------+----------------------+------+--------------------------------+
| Test   | Name                 | Tier | Acceptance                     |
+--------+----------------------+------+--------------------------------+
| 1      | Language policy      | A    | WP5-AT-01, WP5-AT-02           |
| 2      | Malay retrieval      | A/B  | WP5-AT-04                      |
| 3      | Live Malay turn      | B    | WP5-AT-03; live AT-01, AT-04   |
| 4      | MERaLiON viability   | B    | WP5-AT-08 (WP5.2, not WP5.1)   |
| 5      | Regression           | A/B  | WP5-AT-12                      |
+--------+----------------------+------+--------------------------------+
```

#### WP5.1 tests - language policy, Malay path and regression

Run on the Mac as `websvc` from the WP5.1 checkout, with the grounded
stack running (`python scripts/dev_stack.py up`). Test 3 also needs the
demo sample (runbook 10.1 WP5.1, "Demo sample capture").

##### Evidence harness

Run `scripts/wp5_1_evidence.sh` after `source scripts/kaki_env.sh
WP5.1`; `--help` lists its side effects. It runs Tests 1, 2, 3 and 5,
and prints that Test 4 belongs to WP5.2. It follows the WP4.2 harness
rules (runbook 9.2 WP4.2, "Evidence harness"): `uuidgen` identifiers,
fresh sessions, owner verdicts for judgements, `wp_check.py` per unit,
counts as observations, no teardown. Evidence goes to
`$KAKI_DATA_ROOT/wp5.1/evidence.XXXXXX` (`WP51_EVIDENCE`).

```sh
source scripts/kaki_env.sh WP5.1
scripts/wp5_1_evidence.sh --help
scripts/wp5_1_evidence.sh                  # Tests 1, 2, 3 and 5
scripts/wp5_1_evidence.sh --from-test 3    # resume at Test 3
```

`--from-test N` (1, 2, 3 or 5; default 1) starts at test N and runs to
the end. A start at 1, 2 or 3 needs a terminal for the judgements. The
run header records the start test, the active reply mode and the Malay
voice.

Test 2 posts no audio, but its measurement half reads the embedding
model, the Chroma index and the live MLX-LM rewrite. It runs on the Mac,
not in CI; its deterministic half runs anywhere.

##### Test 1: language policy (WP5-AT-01, WP5-AT-02)

**Objective:** prove the policy selects the reply language from the
transcript, the STT language evidence and the configured preference
together, and that the printed slip stays English whatever the reply
language is. Curated Malay and code-switch transcripts, fake ports, no
audio.

**Expected, machine-checked:**

- `test_language_policy.py` passes: every case in
  `agent/data/language_cases.jsonl` returns its `expected_language`; no
  case decides on STT evidence without transcript support; at or below
  six words the preference outranks Whisper's label.
- `test_malay_reply.py` passes. For a Malay transcript in `full` mode:
  `language` `ms`; `reply_text` is the render output; `display_text`
  equals `reply_text`; `slip_text` equals the slip of the English
  answer; the render call receives the English reply alone; the TTS port
  receives `ms`. Empty, length-mismatched and failed renders give the
  English reply with the matching `render_outcome`. `bridge` wraps the
  English reply and speaks three segments; `english` replies in English.
  A Malay refusal uses the `ms` catalogue and keeps `You asked:`. Every
  slip is Latin-1. The diagnostics survive storage. An English
  transcript returns the same response in every mode.
- `test_say_adapter.py` passes: `en` runs `say` with no `-v`; `ms` runs
  `-v` with the configured voice.
- Every suite reports more than zero tests.

**Expected, owner judgement:** the harness prints the fixed Malay
strings (refusals, actions, bridge greeting and closing). Are they
correct, calm Malay?

##### Test 2: Malay retrieval (WP5-AT-04)

**Objective:** prove a Malay CDC utterance retrieves CDC evidence in the
top three through the existing hybrid retriever, and that the evidence
gate sees the stronger of the original and normalised legs. A Malay
question that scores low on the original leg and high on the normalised
English leg must not refuse with `no_coverage`. Measure the gate value
with the real Qwen rewrite, not only with hand-written queries.

The harness runs the deterministic tests, then the `wp_check.py` WP5.1
retrieval probe for the three questions in the 10.1 table: original
only, with the curated English query, and with the live Qwen rewrite.

**Expected, machine-checked:**

- `rag/tests/test_adapter.py` passes, including the test that the gate
  input is the better of the two legs.
  `backend/tests/unit/test_refusal_pipeline.py` passes, including a short
  Malay transcript labelled `en` that still gets a rewrite.
- For each question: the Qwen rewrite exists; a `cdc-vouchers-residents`
  chunk is in the top three with the rewrite; the gate value with the
  rewrite and with the curated query is at or above
  `KAKI_EVIDENCE_MIN_DENSE` (default 0.50).

**Expected, observed only:** for each question, the Qwen rewrite text,
`rewrite_ms` and all three gate values. The harness prints a note when a
Qwen gate value sits within 0.10 of the gate. Copy the Qwen values into
the 10.1 table; a note is an owner decision.

##### Test 3: live Malay turn (WP5-AT-03)

**Objective:** prove spoken Malay questions complete the loop on the
real stack with a Malay reply, Malay speech and an English slip, and let
the owner judge whether the Singapore English sounds natural rather
than caricatured (`design.md` 6.4). Owner judgement on the demo sample,
one turn per utterance.

The harness posts the four demo sample files, each in a fresh session,
and reads the debug view after each. `malay language` below is `ms` in
`full` and `bridge` mode and `en` in `english` mode.

**Expected, machine-checked, by file:**

- The backend's startup line names a reply mode of `full`, `bridge` or
  `english` and a Malay voice; the harness records both.
- `ms_cdc`: state `answered`; `language` is the malay language; debug
  `reply_language` `ms` and `reply_mode` the active mode;
  `cited_source_id` `cdc-vouchers-residents`; `rewrite_present` true;
  `best_dense_score` at or above `evidence_min_dense`. `slip_text`
  starts `KAKI-TALKIE HELP`, carries `Source checked:` and contains none
  of the harness's Malay marker words. `full`: `render_outcome`
  `rendered`. `bridge`: `reply_text` starts with `BRIDGE_GREETING` and
  ends with `BRIDGE_CLOSING`. `english`: `render_outcome` null.
  `reply_audio` is non-empty.
- `ms_codeswitch`: state `answered`; `language` the malay language;
  `reply_language` `ms`; `cited_source_id` `careshield-life`;
  `rewrite_present` true; in `full` mode `render_outcome` `rendered`;
  English slip as above.
- `en_sg_cdc`: state `answered`; `language` `en`; `cited_source_id`
  `cdc-vouchers-residents`; `reply_text` does not start with
  `BRIDGE_GREETING`.
- `ms_unsupported`: state `refused`; `language` the malay language;
  `refusal_reason` `no_coverage`; `reply_text` equals the no-coverage
  string for that language; `slip_text` starts `KAKI-TALKIE REFERRAL`,
  keeps a `You asked:` line and is Latin-1.

**Expected, observed only:** the transcript, Whisper
`language_evidence`, `normalised_query`, `rewrite_ms`, `llm_ms`,
`render_outcome`, turn elapsed time and the `llm.log` completion count
per turn: 3 for a `full` Malay answer (rewrite, answer, render) and 2
for `bridge` or `english`. Also the count of `lah`, `leh` and `lor` in
the `en_sg_cdc` reply.

**Expected, owner judgement:** the harness plays each reply and shows
its display and slip text, then asks:

1. `ms_cdc`: in `full` mode, is this understandable, natural Malay a
   senior would follow? In `bridge` or `english` mode, is the reply
   acceptable as demo-day insurance?
2. Is the Malay voice intelligible?
3. Which Malay voice variant survived the `setup.md` 10.1.1 SSH check:
   Amira enhanced, Amira compact or Damayanti? The harness checks the
   backend voice matches.
4. `en_sg_cdc`: does the Singapore English sound natural, not
   caricatured? (WP5-AT-03)
5. `ms_unsupported`: is the Malay refusal calm and clear?

A "no" to question 1 in `full` mode ends the run and prints the switch
command.

##### Reply mode selection

WP5-AT-01 passes in `full` mode only. `bridge` and `english` are
demo-day insurance, not a partial pass. To rehearse one, restart the
backend with the switch and rerun Test 3:

```sh
export KAKI_MALAY_REPLY_MODE=bridge        # or english
python scripts/dev_stack.py down --only backend
python scripts/dev_stack.py up --only backend
scripts/wp5_1_evidence.sh --from-test 3
```

Record each Test 3 run here. The gate records which mode ran for the
WP5-AT-01 evidence.

```text
+-------------+---------+-----------------+--------------------+------------------+
| Date        | Mode    | Q1 verdict      | Voice variant      | Evidence dir     |
+-------------+---------+-----------------+--------------------+------------------+
|             |         |                 |                    |                  |
+-------------+---------+-----------------+--------------------+------------------+
```

##### Test 4: MERaLiON viability (WP5-AT-08)

**Objective:** decide whether MERaLiON-3 is worth adopting, inside a
30-minute timebox, and record the decision in an ADR. On expiry, record
keep-baseline and stop.

This is a viability check, not a benchmark. It runs on a one-voice demo
sample, so it answers whether MERaLiON installs, runs on the host and
transcribes Malay and code-switch clips visibly better or worse than
Whisper. The ADR states that limit alongside the decision.

##### Test 5: regression (WP5-AT-12)

**Objective:** prove the language work broke nothing. The deterministic
suites, X-AT-01, X-AT-03 and the golden paths run as always. The
within-package rule of `execution-plan.md` 1.1 decides any tier B rerun:
WP5.1 is the first unit in the package, so none applies.

The harness runs `wp_check.py --unit WP5.1 --tier B`, then the devset
regression, then the deterministic suites: ruff, and the contract,
unit, rag and scripts suites. WP5.1 changes no web code, so the web
suite does not run.

`wp_check.py` and `kaki_env.sh` each gain a WP5.1 branch; those are
additions, not changes to a shared code path. `run_regression.py` does
change a shared code path, and `wp_check.py` relaxes two WP4
schema-version checks (runbook 10.1 WP5.1, "Shared-file changes"). With
no earlier WP5 unit, neither triggers a rerun.

**Expected:**

- `wp_check.py --unit WP5.1 --tier B` exits 0.
- `run_regression.py` exits 0; `intent_accuracy` >= 0.80;
  `golden_paths_passed` equals `golden_paths_total`. The `singpass-ms`
  and `careshield-codeswitch` items still pass with their expected
  sources, now with Malay replies in `full` mode.
- Every deterministic suite exits 0, each reported separately.
- The WP1 turn schema snapshot is unchanged: its contract test passes
  and `git status` shows no change to `turn_response.schema.json`
  (X-AT-01).
- `git ls-files` lists no `*.db`, `*.db-wal`, `*.db-shm` or `chroma/`
  path (X-AT-03).
- The `$KAKI_DB` `turns` count is unchanged across the deterministic
  suites.

A failing devset item is evidence. Do not edit the devset to pass.

##### Teardown and evidence

The harness leaves the stack running and prints `python
scripts/dev_stack.py down`. Keep `$WP51_AUDIO` until WP5.2 has used it.

`WP51_EVIDENCE` keeps the WP4.2 harness files (`run-header.txt`,
`transcript.txt`, `observations.txt`, `judgements.txt`) and, per test:
the Test 1 suite outputs and the printed Malay strings; the Test 2 suite
outputs and `probe_retrieval.json`; the Test 3 turn and debug JSON,
reply WAVs, `llm.log` counts and the voice variant; the Test 5
`wp_check`, regression and suite outputs.

##### Troubleshooting

- **A Malay question gets an English reply:** read `reply_language`,
  `render_outcome`, `transcript` and `language_evidence` in the debug
  view. `reply_language` `en`: the transcript rule found too few Malay
  tokens and the turn fell to the preference; add a
  `language_cases.jsonl` case and fix the rule, or set
  `KAKI_LANGUAGE_PREFERENCE=ms` on a Malay kiosk. `reply_language` `ms`
  with a `fallback_*` outcome: the render was rejected (next item).
- **`render_outcome` is `fallback_length` or `fallback_empty`:** the
  render dropped or added content. Read the English reply in the
  evidence and rerun the turn. If it repeats, record it for the reply
  mode decision.
- **`render_outcome` is `fallback_error`:** the render call failed or
  timed out. Check `llm.log` for the third completion.
- **A Malay CDC question refuses with `no_coverage`:** read
  `rewrite_present`. If false and `rewrite_ms` is near the timeout, the
  rewrite timed out on a cold model; send one warm-up turn, or raise
  `KAKI_QUERY_REWRITE_TIMEOUT_SECONDS` and restart. If `rewrite_ms` is
  null, the rewrite was skipped; that is a WP5.1 defect in the guard.
- **`reply_audio` null with `tts_error` set on a Malay turn:** the voice
  in `KAKI_TTS_VOICE_MS` is not installed or not usable from the service
  context. Run `say -v '?' | grep -Ei 'ms_MY|id_ID'` and see `setup.md`
  10.1.1; export `KAKI_TTS_VOICE_MS=Damayanti` as the fallback.
- **Harness cannot find the startup line:** the backend runs from an
  older checkout. Restart it from the WP5.1 checkout.
- **`dev_stack.py up` or the WP4.5 harness reports schema version 3:**
  expected after WP5.1. Migration 0003 adds the debug columns.
- **Recording is silent or `ffmpeg` reports an input error:** Terminal
  lacks microphone permission, or `:0` is the wrong device. Grant the
  permission and list the devices again.

##### Known limitations

- The demo sample is one voice, one microphone and four utterances. It
  shows the path works; it does not measure Malay accuracy.
- The render check measures emptiness and length only. No automated
  check proves the Malay rendering is faithful to the English answer;
  the owner judges it in Test 3.
- Malay CDC questions depend on the normalised-query rewrite. A rewrite
  that exceeds `KAKI_QUERY_REWRITE_TIMEOUT_SECONDS` still refuses a
  question the corpus covers; the debug view now shows it.
- The language rules use closed word lists. Unseen phrasing can fall
  through to the preference.
- Failed turns stay English.
- `llm_ms` covers both the answer and the render call.
- Chinese and other languages reply in the preference language, and
  their slip question keeps only its Latin-1 characters. Hokkien is a
  stretch goal beyond the MVP.
- The Qwen-rewrite gate values in 10.1 are unmeasured until the owner
  runs Test 2.

---

# 11. WP6 - physical client + hardening

Status: **DRAFT - structure fixed; Prepare WP6.x fills in commands**

### 11.1 Setup and installation

##### Known setup.md coverage (Mac side)

Device routes through Cloudflare Access (15.4). Model services are
never published externally (15.5).

##### Components absent from setup.md

**Raspberry Pi installation.** No Pi source of truth exists yet.
`Prepare WP6.x` must either extend `setup.md` with a Pi section or
create a peer document covering:

- Pi OS and version, first-boot preparation.
- Python and system dependencies.
- ALSA device names.
- Dome button GPIO 17, LED ring GPIO 18.
- ESC/POS printer with separate power.
- systemd services.
- Service authentication.
- Optional Tailscale hardening.

##### Runbook writing rule

Use the WP3.4 block as the reference structure for every WP6.x section
the coding agent fills in during Prepare.

### 11.2 Testing and validation

##### Test 1: thin-client conformance

**Objective:** prove the Pi holds no model, RAG, prompt or
case-decision logic. Any such logic on the Pi is a gate failure.

##### Test 2: canned-mode sequence

**Objective:** prove the button, LED states, audio capture and
playback, and printer work against canned backend responses before real
inference is in the loop.

##### Test 3: network retry

**Objective:** prove a dropped connection retried with the same
`turn_id` produces exactly one answer and one print.

##### Test 4: power-cycle recovery

**Objective:** prove the kiosk returns to service after a process kill
and a power cycle without operator intervention. This is demo-day
insurance.

##### Test 5: demo run

**Objective:** execute the final demo procedure end to end on the
physical kiosk.

---

## 12. Runbook maintenance rule

For each IU:

```text
Prepare WPn.m
-> the coding agent updates this IU section only
-> owner reviews real decisions/BLOCKED items
-> owner may prepare target runtime in parallel
-> Implement WPn.m
-> the coding agent keeps this section accurate if implementation changes commands
-> owner follows this section for S/G validation
-> mark VERIFIED when completed
```

##### Section structure standard

The WP3.4 block (section 8.1) is the reference for how a completed
runbook section should read. When writing or updating a section during
Prepare or Implement, follow this structure:

- Titled subsections, one topic each: scope, prerequisites, pipeline
  impact, response shape, calibration, environment, files, fixture
  capture, reconciliation, troubleshooting.
- Specification before rationale. State what the system does, then why.
- Tables for structured fields (response shape, debug additions,
  environment variables).
- Tests as numbered subsections with objective, command, expected.
- Troubleshooting and known limitations as titled subsections at the
  end.
- No unbroken prose longer than one short paragraph.

##### Closed block compression

When the owner marks a unit VERIFIED / CLOSED, compress its setup block
to the parts that still bind later units:

- status, with a pointer to the gate evidence;
- what the unit delivered;
- prerequisites still in force;
- environment variables and files that still exist.

Move measurements, rationale and superseded estimates to the relevant
ADR, or leave them in the evidence archive. The full text stays in Git
history. Leave the unit's test block unchanged.

Installation and configuration changes go to `setup.md`. Validation changes go
to this runbook. Do not create a third operational guide. If a `Prepare WPn.m`
step introduces a component the final solution needs, add its installation to
`setup.md` and cross-reference it here.

---

## 13. Quick start reference

This section is the one place to look when you just need the stack running.
It repeats no procedure; each step names the section that owns it. Update it
whenever a WP changes a start command.

### 13.1 Start the current prototype (Mac + browser simulator)

All commands run on the Mac as `websvc`.

1. Open a terminal and set the session environment (runbook 7.4.1
   "Prepare the validation environment"): checkout root, `.venv` activation,
   `KAKI_DATA_ROOT`, the three adapter modes/URLs/timeouts and `HF_HOME`.
   For a non-evidence session you may skip the evidence-directory lines.
2. Start the model services and FastAPI with the stack helper:

   ```sh
   python scripts/dev_stack.py up
   python scripts/dev_stack.py status
   ```

   The helper starts whisper-server (8081), MLX-LM with thinking disabled
   (8082) and FastAPI (8000), all loopback-only, and waits for readiness.
   Manual alternative, one foreground terminal each, in this order:
   whisper-server (7.2.2 Test 1), MLX-LM (7.3.1), FastAPI
   (`python -m kaki_backend.main`).
3. Confirm readiness:

   ```sh
   curl --fail --silent http://127.0.0.1:8000/api/health | jq
   ```

   Expected: `status` ok with `stt_ready`, `llm_ready`, `tts_ready` and
   `storage_ready` true.
4. Start the simulator (not managed by the helper). From `apps/web`:

   ```sh
   npm start
   ```

   Build first with `npm run build` if the checkout changed. Local browser:
   `http://127.0.0.1:3000/sim`. Phone or laptop: the protected
   `https://talkie.lookieman.dev/sim` through Cloudflare Access.
5. Shut down in reverse order: Ctrl+C the simulator, then
   `python scripts/dev_stack.py down` (or Ctrl+C each owned terminal:
   FastAPI, MLX-LM, whisper-server). Never use broad process kills.

Nothing else runs today. SQLite (WP4) and Chroma (WP3) have no process to
start; Chroma will run embedded in FastAPI.

### 13.2 Start the integrated prototype (Mac + Raspberry Pi)

Status: **DRAFT - fill during Prepare WP6.x. Do not guess commands.**

The Mac side of the final prototype is 13.1 steps 1-3 unchanged, plus the
services WP3-WP5 add to the environment exports. The simulator becomes
optional; the Pi is just another client of the same contract.

`Prepare WP6.x` must complete this checklist into exact commands:

- launchd replaces `dev_stack.py` for boot-time Mac services
  (`setup.md` 17); record the reboot-test result here;
- cloudflared and Tailscale confirmed up (`setup.md` 15, 16);
- Pi power-on and systemd service start/verify commands;
- Pi service authentication check against `/api/device/*`;
- canned-mode activation and rehearsal sequence (demo insurance);
- shutdown order for demo teardown.

Until WP6, there is no supported Pi start procedure; treat any remembered
commands as stale.
