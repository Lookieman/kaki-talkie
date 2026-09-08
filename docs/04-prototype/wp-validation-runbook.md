# KaKi-Talkie WP validation runbook

Version 1.2 | 07-Sep-2026 | SGLN Group 10

Repository location: `docs/04-prototype/wp-validation-runbook.md`

`setup.md` is the source of truth for Mac backend installation and configuration. This runbook is the source of truth for work-package validation: what to test, why, in what order, and what evidence to keep. Each WP setup section cross-references `setup.md` and adds only components that the final solution needs and `setup.md` does not cover.

`design.md` defines architecture. `execution-plan.md` defines scope and acceptance. This runbook explains exactly what the owner does at the keyboard.

---

## 1. Environment model

```text
+--------------------------+-----------------------------+-------------------------+
| Environment              | Primary purpose             | Codex                   |
+--------------------------+-----------------------------+-------------------------+
| Windows gaming desktop   | Development and Tier A      | Installed here          |
| Mac Mini                 | Runtime and Tier B tests    | Not installed           |
| Raspberry Pi             | Thin client/Tier C tests    | Not installed           |
| Phone/laptop browser     | Interaction smoke/gates     | Not applicable          |
+--------------------------+-----------------------------+-------------------------+
```

Rules:

- Code is created in an isolated Windows worktree.
- Mac Mini/Pi preparation is performed manually by the owner.
- Do not assume a Windows package also exists on the Mac.
- Runtime/model caches stay outside the Git repository.
- Generated application data uses `KAKI_DATA_ROOT` where applicable.
- Chrome is the primary simulator acceptance browser; Safari is optional/non-gating.

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

Codex completion reports point here instead of duplicating these procedures.

---

## 4. Development worktree lifecycle

Machine: Windows gaming desktop  
Repository: `C:\projects\kaki-talkie`

### 4.1 Before creating a worktree

```powershell
git switch main
git pull --ff-only
git status
```

`main` must be clean and current before setup.

### 4.2 Create an IU worktree

Use the repository helper after its pre-WP2 contract update:

```powershell
python scripts\setup_wp_worktree.py --help
```

Example:

```powershell
python scripts\setup_wp_worktree.py `
    --unit WP2.1 `
    --slug audio-normalisation `
    --run-baseline
```

The helper creates the sibling worktree, local feature branch and worktree-local development environment. It does not commit, merge or push.

Point the temporary Codex project only at the new worktree.

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

```powershell
cd C:\projects\kaki-talkie
python scripts\cleanup_wp_worktree.py --help
python scripts\cleanup_wp_worktree.py --unit WP2.1
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
Status: **READY - implementation authorised; owner Mac smoke pending**.
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
Status: **DRAFT - structure fixed; Prepare WP2.3 fills in adapter commands**

Machine: Mac Mini. User: `websvc`. Locked runtime family: MLX-LM with a small
quantised Qwen-class instruct model. Do not introduce RAG, DSPy or SEA-LION.

### 7.3.1 Setup and installation

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

Components crucial to the solution and absent from `setup.md`:

- Exact model identifier. Selected 07-Sep-2026: `mlx-community/Qwen3-8B-4bit`.
  Record any change here with a date.
- Thinking-mode suppression. Qwen3 emits `<think>` blocks by default; the
  adapter must disable them (`enable_thinking=False` in the chat template) so
  the kiosk does not stream silence while the model deliberates.
- The LLM adapter package under `services/llm/`. `Prepare WP2.3` documents its
  installation, start, readiness and stop commands.

### 7.3.2 Testing and validation

`Prepare WP2.3` supplies exact commands. The tests and objectives are fixed:

- Test 1, LLM service readiness. Objective: prove the model loads once, stays
  resident across turns, and serves only on `127.0.0.1:8082`.
- Test 2, bounded generation. Objective: prove a fixed transcript input yields
  a concise reply - five runs, each 60 words or fewer - because long replies
  break spoken delivery for elderly users.
- Test 3, failure and recovery. Objective: prove FastAPI returns a calm
  `failed` response while the LLM service is down and recovers without an
  application restart.
- Test 4, WP1 regression. Objective: prove the contract still holds with the
  LLM adapter installed (Test 5 command set from 7.2.2).

## 7.4 WP2.4 - macOS say + full WP2 gate

Owner level: **G**  
Status: **DRAFT - finalise after WP2.1-WP2.3**

Machine: Mac Mini plus a protected Chrome browser on a laptop or phone.
User: `websvc`. Baseline English TTS: macOS `say`.

### 7.4.1 Setup and installation

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| macOS say TTS adapter and conversion  | 10.1                |
| FastAPI runtime and configuration     | 11                  |
| Next.js simulator                     | 14                  |
| Cloudflare access to the simulator    | 15                  |
| Latency measures to record            | 18.1                |
+---------------------------------------+---------------------+
```

Component crucial to the solution and absent from `setup.md`: the latency
measurement script (repository deliverable). `Prepare WP2.4` documents its
`--help` and the exact ten-run command.

### 7.4.2 Testing and validation

- Test 1, service stack readiness. Objective: prove the documented start order
  brings every service healthy and `/api/health` reflects it.
- Test 2, end-to-end voice loop. Objective: prove real English speech in
  produces speech out through the simulator, with transcript and timing fields
  visible - the core demo path. Use the fixed questions and expected flow in
  `setup.md` 23.
- Test 3, degraded input. Objective: prove empty audio and silence produce
  calm, well-formed responses rather than hangs or crashes.
- Test 4, latency baseline. Objective: record p50/p95 over ten runs against the
  `setup.md` 18.1 measures. The five-second target is a hypothesis; record, do
  not invent a pass threshold.
- Test 5, WP1 regression and shutdown. Objective: prove the contract holds and
  the stack stops cleanly in reverse order.

Package-gate outcome: real English speech-in to speech-out works; replies are
clearly labelled ungrounded in WP2; raw-audio deletion remains proven; p50/p95
are recorded; WP1 regression is green.

---

# 8. WP3 - grounded knowledge + refusal

Status: **DRAFT - structure fixed; Prepare WP3.x fills in commands**

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
  how chunks are embedded. `Prepare WP3.x` selects and records it, then adds
  it to `setup.md`.
- The ingestion script (repository deliverable) and its example invocation.

Generated corpus snapshots belong under `KAKI_DATA_ROOT`. Commit only
intentional, small, non-sensitive deterministic fixtures.

### 8.2 Testing and validation

- Test 1, retrieval acceptance. Objective: prove the `setup.md` 13.4 gate -
  dated snapshots, provenance on every retrieved chunk, Chroma surviving a
  backend restart.
- Test 2, grounded answer. Objective: prove a supported question (for example
  CDC vouchers) returns an answer whose source URLs and dates come from
  application metadata, not the LLM.
- Test 3, refusal. Objective: prove the deliberately unsupported question
  produces a refusal rather than an invented answer - the safety property the
  pitch depends on.
- Test 4, regression. Objective: prove WP1 and WP2 behaviour still hold with
  retrieval installed.

---

# 9. WP4 - memory + actions + case closure

Status: **DRAFT - structure fixed; Prepare WP4.x fills in commands**

### 9.1 Setup and installation

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| SQLite location, permissions, schema  | 12                  |
| Backup and restore procedure          | 12.4, 20            |
| Secrets outside Git                   | 11.4                |
+---------------------------------------+---------------------+
```

Components crucial to the solution and absent from `setup.md`:

- Google Calendar integration. `setup.md` 24 defers it deliberately. Add it
  to `setup.md` only when `Prepare WP4.x` locks the action scope, including
  the test account and calendar.
- The handoff channel. Decide during `Prepare WP4.3`:

```text
A. logging/test adapter only for MVP;
B. Telegram adapter;
C. another explicitly approved bounded channel.
```

If Telegram is not selected, do not install or configure it, and do not treat
its absence as a failed gate. The core WP4 requirement is durable case
creation plus idempotent handoff behaviour behind `HandoffPort`. Morning
scheduler automation remains deferred unless the owner reintroduces it.

### 9.2 Testing and validation

- Test 1, durability. Objective: prove turns, sessions and cases survive a
  backend restart, and a retried `turn_id` remains idempotent across the
  restart - the property that makes the kiosk trustworthy after a power blip.
- Test 2, repeat and print-previous. Objective: prove the user-facing memory
  behaviours work against persisted state.
- Test 3, case lifecycle and handoff. Objective: prove a pending case is
  created once, handed off once, and closed, with no duplicate side effects.
- Test 4, backup and restore. Objective: prove the `setup.md` 12.4 backup
  restores to a working database (`setup.md` 20.3).

---

# 10. WP5 - Singapore language + improvement

Status: **DRAFT - structure fixed; Prepare WP5.x fills in commands**

### 10.1 Setup and installation

```text
+---------------------------------------+---------------------+
| Component                             | setup.md section    |
+---------------------------------------+---------------------+
| Challenger virtual environments       | 7.3                 |
| Multilingual TTS (deferred)           | 10.2                |
| Deferred-component policy             | 24                  |
| Model cache and disk considerations   | 9.3, 21             |
+---------------------------------------+---------------------+
```

Component crucial to the solution and absent from `setup.md`: the
consent-cleared Singapore speech set for regression and bake-offs. `Prepare
WP5.x` documents its collection, consent record and storage under
`KAKI_DATA_ROOT`.

Install a challenger only when a measured baseline limitation justifies it,
and only into its own environment. Do not guess challenger installation
commands in advance; verify them during the relevant `Prepare WP5.x`.

### 10.2 Testing and validation

- Test 1, Malay regression. Objective: prove the baseline handles the Malay
  path the design promises before any challenger work starts.
- Test 2, bake-off. Objective: run baseline and challenger sequentially on the
  same speech set and record quality plus p50/p95, so the promote, keep or
  reject decision rests on evidence.
- Test 3, decision record. Objective: prove each bake-off ends in a recorded
  decision. Challenger failures do not block the working baseline.

---

# 11. WP6 - physical client + hardening

Status: **DRAFT - structure fixed; Prepare WP6.x fills in commands**

### 11.1 Setup and installation

`setup.md` covers the Mac backend only. The Raspberry Pi has no installation
source of truth yet. `Prepare WP6.x` must either extend `setup.md` with a Pi
section or create a peer document, covering: Pi OS and version, first-boot
preparation, Python and system dependencies, ALSA device names, dome button
GPIO 17, LED ring GPIO 18, ESC/POS printer with separate power, systemd
services, service authentication, and the optional Tailscale hardening.

The Mac-side pieces the Pi depends on are already in `setup.md`: device routes
through Cloudflare Access (15.4) and the never-publish-model-services rule
(15.5).

### 11.2 Testing and validation

- Test 1, thin-client conformance. Objective: prove the Pi holds no model, RAG,
  prompt or case-decision logic. Any such logic on the Pi is a gate failure.
- Test 2, canned-mode sequence. Objective: prove the button, LED states, audio
  capture and playback, and printer work against canned backend responses
  before real inference is in the loop.
- Test 3, network retry. Objective: prove a dropped connection retried with the
  same `turn_id` produces exactly one answer and one print.
- Test 4, power-cycle recovery. Objective: prove the kiosk returns to service
  after a process kill and a power cycle without operator intervention -
  demo-day insurance.
- Test 5, demo run. Objective: execute the final demo procedure end to end on
  the physical kiosk.

---

## 12. Runbook maintenance rule

For each IU:

```text
Prepare WPn.m
-> Codex updates this IU section only
-> owner reviews real decisions/BLOCKED items
-> owner may prepare target runtime in parallel
-> Implement WPn.m
-> Codex keeps this section accurate if implementation changes commands
-> owner follows this section for S/G validation
-> mark VERIFIED when completed
```

Installation and configuration changes go to `setup.md`. Validation changes go
to this runbook. Do not create a third operational guide. If a `Prepare WPn.m`
step introduces a component the final solution needs, add its installation to
`setup.md` and cross-reference it here.
