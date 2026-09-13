# KaKi-Talkie WP validation runbook

Version 1.15 | 13-Sep-2026 | SGLN Group 10

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

Deferred: print/repeat intents (WP4), live lookup (WP5.6), Malay replies
(WP5.1), DSPy migration (WP5.5). A WP3.4 refusal is spoken and displayed
in English only.

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
refused until the WP5.6 live lookup exists.

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
- Volatile questions (opening hours, events) are refused until WP5.6.
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

Status: **WP4.1 and WP4.2 VERIFIED / CLOSED 13-Sep-2026; later WP4.x DRAFT -
structure fixed; Prepare WP4.x fills in commands**

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
Status: **VERIFIED / CLOSED 13-Sep-2026.**

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.
Deterministic tests run with canned ports, no network and no model
services. Tier B runs against the WP3.4 grounded stack.

##### Prerequisites

The WP3.4 grounded stack (runbook 8.1 WP3.4). No new package, model,
service or port. `setup.md` 12 covers permissions and backup, but names
the file `kaki-talkie.db`; the implemented default is `kaki.db` (see
"Reconciliation").

Two prerequisites are new in kind, not in installation:

- `KAKI_DATA_ROOT` must be absolute in every backend configuration,
  canned included. Until WP4.1 only `rag` mode required it. If it is
  unset, the backend exits at import with a message naming the variable
  and `$KAKI_DATA_ROOT/sqlite/kaki.db`. `scripts/kaki_env.sh` and
  `dev_stack.py` already export it.
- `$KAKI_DATA_ROOT/sqlite/` exists on the Mac (created 05-Sep-2026,
  empty on 13-Sep-2026). The backend creates the file itself.

Inspection uses the macOS built-in CLI, `/usr/bin/sqlite3` 3.51.0. The
backend uses the Python `sqlite3` module (library 3.53.4 in the
`.venv`, Python 3.12.14). Both read the same file.

##### Scope

WP4-AT-01, 02, 03. WP4.1 makes the turn record durable:

- A completed turn is written to SQLite in one transaction before the
  response is returned (AT-01).
- A grounded turn writes one `turn_sources` row per response source
  (AT-02).
- After a backend restart the same `turn_id` returns the stored
  response without running STT, retrieval, the LLM or TTS (AT-03).
- The process-memory response cache from WP1.2 is removed; the store
  is the only idempotency record.

The public device contract does not change. The response keeps its
nine fields, the WP1 schema snapshot stays unchanged and
`GET /api/device/pending` still returns `[]`.

Deferred to a later unit: repeat/print intents and print policy (WP4.2),
backup automation and the restore test (WP4.5), device credentials and
pairing columns (WP6.4). Each later unit adds its own migration.

Deferred beyond the MVP: the `cases` table, handoff (WP4.3), calendar
(WP4.4) and pending delivery state. No MVP migration creates `cases`, so
migration 0001 creates `devices`, `sessions`, `turns` and `turn_sources`
only.

##### Storage location and lifecycle

```text
+----------------------+------------------------------------------------------+
| Item                 | Behaviour                                            |
+----------------------+------------------------------------------------------+
| Database file        | KAKI_SQLITE_PATH, else                               |
|                      | $KAKI_DATA_ROOT/sqlite/kaki.db.                      |
| Creation             | At backend start if absent; parent directory         |
|                      | created; file mode 0600 (setup.md 12.3 satisfied     |
|                      | without a manual chmod).                             |
| Migrations           | Applied at backend start, in order, each in its own  |
|                      | transaction; version kept in PRAGMA user_version.    |
|                      | A database newer than the code fails startup.        |
| Connection pragmas   | Applied on every connection: journal_mode=WAL,       |
|                      | foreign_keys=ON, busy_timeout=5000,                  |
|                      | synchronous=NORMAL (ADR-0007).                       |
| Sibling files        | WAL creates kaki.db-wal and kaki.db-shm next to the  |
|                      | database; .gitignore already covers all three.       |
| Startup log line     | "kaki_backend: SQLite database <path> at schema      |
|                      | version N" on stderr, so a path mismatch between     |
|                      | shells is visible in $KAKI_DATA_ROOT/logs/           |
|                      | backend.log.                                         |
| Mechanism            | Standard-library sqlite3; numbered SQL files in      |
|                      | kaki_backend/persistence/migrations/; no ORM.        |
+----------------------+------------------------------------------------------+
```

Standard-library SQLite is enough for one writer process on one machine
and adds no dependency. ADR-0007 records the mechanism, the pragmas and
the reply-audio deviation from design.md 14.

##### Schema (migration 0001)

Four tables in `persistence/migrations/0001_initial.sql`. Timestamps
are ISO 8601 UTC text.

```text
+---------------+-------------------------------------------------------------+
| Table         | Columns                                                     |
+---------------+-------------------------------------------------------------+
| devices       | device_id PK, first_seen_at, last_seen_at                   |
| sessions      | session_id PK, device_id FK, started_at, last_turn_id,     |
|               | last_completed_at                                           |
| turns         | turn_id PK, session_id FK, device_id FK, state, intent,     |
|               | refusal_reason, transcript, stt_language_json, language,    |
|               | reply_text, display_text, slip_text, reply_audio BLOB,      |
|               | case_id,                                                    |
|               | stt_error, llm_error, tts_error, retrieval_error,           |
|               | normalised_query, best_dense_score, evidence_min_dense,     |
|               | cited_source_id, llm_cited_index, timings_json,             |
|               | retrieval_evidence_json, replay_count, completed_at         |
| turn_sources  | turn_id FK, position, source_id, source_url, page_title,    |
|               | captured_at, source_updated_at, content_hash, chunk_id,     |
|               | retrieval_rank, dense_score, cited; PK (turn_id, position)  |
+---------------+-------------------------------------------------------------+
```

`turns` holds every field of the nine-field response plus every field
of the internal `TurnLog`, so both the replayed response and the debug
view are rebuilt from the row alone after a restart.

`turn_sources` follows design.md 14 and adds `chunk_id`,
`retrieval_rank`, `dense_score` and `cited` so the row records which
chunk the answer was attributed to. `position` mirrors the response's
`sources` order: position 0 is the cited source. One row per
de-duplicated source, not per retrieved chunk; with top-3 retrieval a
grounded turn writes one to three rows. Refused and failed turns write
none.

`cases` is not created here, and no MVP migration creates it. The handoff
and follow-up capability it served is deferred beyond the MVP. If the
owner reintroduces it, the new table carries `opened_by_turn_id`
referencing `turns`, so no existing table needs a rebuild (ADR-0007).

##### Turn write and replay

The request path, in order:

1. Under the existing process lock, look up `turns` by `turn_id`.
2. On a hit, increment `replay_count`, rebuild the response from the
   row and return it. No port is called.
3. On a miss, run the pipeline once in the worker thread, as today.
4. On completion, write in one transaction: upsert `devices`, upsert
   `sessions` (advancing `last_turn_id`), insert `turns`, insert
   `turn_sources`. Commit, then respond.
5. A crash before the commit leaves no row, so the client's retry
   re-executes. Only a completed turn is idempotent. This is the WP1.2
   rule, now durable.

Failed and refused turns are stored like answered ones: WP1-AT-03
promises the stored first result, whatever it was.

The lock stays because two concurrent requests with the same `turn_id`
must still serialise through one execution inside the process; the
database guarantees durability, not in-flight de-duplication.

##### Response shape

Unchanged. The retry response is compared field by field in Test 3:

```text
+---------------------+-------------------------------------------------------+
| Field               | First response versus replay                          |
+---------------------+-------------------------------------------------------+
| turn_id             | Identical.                                            |
| reply_audio         | Identical bytes (stored as a WAV BLOB, re-encoded).   |
| reply_text          | Identical.                                            |
| display_text        | Identical.                                            |
| slip_text           | Identical.                                            |
| language            | Identical.                                            |
| state               | Identical.                                            |
| case_id             | null in both (cases deferred beyond MVP).             |
| sources             | Identical list, same order.                           |
+---------------------+-------------------------------------------------------+
```

##### Debug view additions

`GET /api/device/debug/last-turn` reads the newest stored turn instead
of the process-memory log, so it answers after a restart and before any
new turn. All existing fields keep their names and meaning. Three
fields are added; none is in the public response and the WP1 schema
snapshot is unchanged.

```text
+----------------------+----------------------------------------------------+
| Field                | Value                                              |
+----------------------+----------------------------------------------------+
| replay_count         | Times this turn_id was served from the store       |
|                      | (0 after first execution).                         |
| completed_at         | ISO 8601 UTC timestamp of the stored execution.    |
| schema_version       | PRAGMA user_version of the open database.          |
+----------------------+----------------------------------------------------+
```

##### Health addition

`GET /api/health` gains `storage_ready`: true when a `SELECT 1` on the
database succeeds and `user_version` equals the code's latest
migration. Additive; the four existing readiness flags are unchanged
(WP2-AT-10).

##### Environment variables

```text
+--------------------------+--------------------------------------------+
| Variable                 | Meaning                                    |
+--------------------------+--------------------------------------------+
| KAKI_SQLITE_PATH         | Absolute path of the database file.        |
|                          | Optional. Default                          |
|                          | $KAKI_DATA_ROOT/sqlite/kaki.db.            |
|                          | A relative value fails startup.            |
| KAKI_DATA_ROOT           | Now required (absolute) in every mode,     |
|                          | because the default database path derives  |
|                          | from it. Previously required in rag mode   |
|                          | only.                                      |
+--------------------------+--------------------------------------------+
```

The owner updated `.env.example`; the coding agent does not read or edit
`.env*` files.

##### Tier A hygiene

`kaki_test_env.py` already gives every deterministic suite a disposable
`KAKI_DATA_ROOT` and removes any stray `KAKI_*` export, so the suites
create their database under the temporary root and never touch
`/Users/websvc/kaki-talkie-data`. No change to `kaki_test_env.py` is
expected.

`backend/tests/contract/test_wp4_1.py` proves the restart twice: with
a fresh service and database handle in-process, and across two separate
Python processes that share only a disposable `KAKI_DATA_ROOT`. The
second process sends different audio and must return the first
response with an execution count of 0. `TurnService.reset()` keeps its
name and now clears the four tables.

##### Retention

Each turn row stores its transcript (design.md 14, baselined) and its
reply audio as raw WAV bytes in a BLOB. Base64 exists only in the
response. A spoken reply is a WAV of roughly 70-180 KB (the committed
fixtures span 70-178 KB), so the database grows by about that much per
turn. No
pruning exists in WP4.1. Backup and size review belong to WP4.5 and
`setup.md` 20.

##### Owner decisions

Approved 13-Sep-2026 and recorded in ADR-0007:

```text
+----+------------------------------------+-------------------------------------+
| #  | Decision                           | Choice                              |
+----+------------------------------------+-------------------------------------+
| 1  | Module path                        | kaki_backend/persistence/           |
|    |                                    | (design.md 18).                     |
| 2  | Reply audio on the turn row        | Raw WAV BLOB; replay makes no TTS   |
|    |                                    | call. No pruning in WP4.1.          |
| 3  | design.md 14 has no audio column   | Deviation recorded in ADR-0007;     |
|    |                                    | design.md unchanged in WP4.1.       |
| 4  | KAKI_DATA_ROOT                     | Required in every mode; default     |
|    |                                    | database $KAKI_DATA_ROOT/sqlite/    |
|    |                                    | kaki.db; no memory fallback.        |
| 5  | cases table                        | Deferred beyond MVP with handoff.   |
|    |                                    | If revived, opened_by_turn_id       |
|    |                                    | references turns.                   |
| 6  | Mechanism                          | stdlib sqlite3, user_version, SQL   |
|    |                                    | files; no ORM, no dependency.       |
+----+------------------------------------+-------------------------------------+
```

##### Files changed and created

Changed, under `backend/src/kaki_backend/` unless a path is given:

- `config.py` - `StorageSettings`; data root required
- `main.py` - open and migrate the database, log its path, wire the store
- `orchestration/idempotency.py` - store-backed replay and write
- `orchestration/turn_pipeline.py` - link each response source to its
  evidence chunk
- `contracts/turn_log.py` - `SourceLink`
- `api/health.py`, `api/debug.py`
- `backend/pyproject.toml` - package the SQL migrations
- `backend/README.md` - replace the in-memory cache paragraph
- `scripts/wp_check.py` - WP4.1 tier B
- `scripts/dev_stack.py` - backend readiness requires `storage_ready`
- `scripts/kaki_env.sh` - `KAKI_DB` for WP4.1
- `scripts/check_stt.py`, `scripts/check_wp1_integration.py` -
  disposable databases
- `backend/tests/contract/test_api.py`, `test_wp1_4.py` - health shape
- `backend/tests/unit/test_audio_normalisation.py`,
  `scripts/tests/test_dev_stack.py`

Created:

- `persistence/__init__.py`
- `persistence/database.py` - file creation, pragmas, migration runner
- `persistence/migrations/__init__.py` - migration discovery
- `persistence/migrations/0001_initial.sql` - four tables
- `persistence/repositories.py` - record, replay, find, newest, clear
- `backend/tests/unit/test_persistence.py` - 21 tests
- `backend/tests/contract/test_wp4_1.py` - 5 tests, AT-01/02/03
- `docs/decisions/adr-0007-sqlite-persistence.md`

No new dependency.

##### Fixture capture

None. Tests reuse `cdc_question.wav` and `unsupported_question.wav`
from WP3.3 and WP3.4.

##### Reconciliation

- `dev_stack.py` already required an absolute `KAKI_DATA_ROOT` and
  passed it to every child, including `--only backend`; a new test
  proves it. Backend readiness now also waits for `storage_ready`.
- `check_stt.py` and `check_wp1_integration.py` import or start the
  backend path, so each now uses a disposable database. Neither writes
  turns into the live data root.
- The WP1.2 contract tests (`test_wp1_2.py`) keep their assertions;
  `execution_count` and `logs` stay available on the service.
- `setup.md` 12 names the file `kaki-talkie.db` in 12, 12.2, 12.3 and
  12.4; the implemented default is `kaki.db`. 12.4 already backs up with
  `sqlite3 .backup`, which is WAL-safe. Reconcile the file name in
  `setup.md` as a separate documentation change.
- Runbook 13.1 step 3 does not yet list `storage_ready`; `dev_stack.py
  status` already requires it.

#### WP4.2 setup - repeat_previous, print_previous, print policy

Owner level: **S**
Status: **VERIFIED / CLOSED 13-Sep-2026.**

Machine: Mac Mini as `websvc`, checkout `~/projects/kaki-talkie`.
Deterministic tests run with canned ports, no network and no model
services. Tier B runs against the WP4.1 grounded stack and database.
Browser tests use Chrome through the simulator.

##### Prerequisites

The WP4.1 grounded stack and its database (runbook 9.1 WP4.1). No new
package, model, service or port.

New in kind, not in installation:

- Two spoken fixtures, `repeat_request.wav` and `print_request.wav`
  (see "Fixture capture").
- The simulator built from the WP4.2 checkout, because the print
  policy rule lives in the client.
- An interactive terminal. The evidence harness stops for owner
  verdicts and refuses to run without a TTY.
- macOS built-ins `say`, `afplay` and `afinfo`, plus `jq`, `sqlite3`,
  `uuidgen` and `npm`, already used by earlier units.

##### Scope

WP4-AT-04, 05, 06. WP4.2 answers two deterministic requests from stored
state:

- `repeat_previous` replays the previous turn's spoken answer. No
  retrieval, LLM or TTS call (AT-04).
- `print_previous` returns the previous turn's slip unchanged. No
  retrieval or LLM call (AT-05).
- Under the `on_request` print policy nothing prints until the user
  asks (AT-06).
- Devset action items join the regression runner. WP4-AT-13 measures
  them at WP4.5.

The public device contract does not change. `acted` has been in the
WP1 state enum since WP1.1, the response keeps its nine fields, and the
WP1 schema snapshot stays unchanged. `GET /api/device/pending` still
returns `[]`.

Deferred: backup and the WP4 gate (WP4.5), the physical printer and
its failure handling (WP6.3), Malay action wording (WP5.1).

Deferred beyond the MVP: `kaki_handoff`, `calendar_create`, the
`cases` table and pending delivery state. WP4.2 adds none of them.

##### Routing

Action routing adds a rule layer to `orchestration/intent_router.py`.
Rules run in this order, all deterministic and model-free:

1. Credential action (WP3.4 layer 1, unchanged). Safety first.
2. Procedural guard. A procedural question is never an action: "How
   do I print my CDC vouchers?" routes to `answer`.
3. `repeat_previous` or `print_previous`: an action verb aimed at the
   previous reply ("that", "it", "again", "the slip"), in English,
   Singlish or Malay.
4. Otherwise `answer`, which continues to the WP3.4 evidence gate and
   `SOURCE: 0` layers.

The rule is keyword-and-anaphora based. A bare topic noun never
triggers an action: "Can I use CHAS for repeat visits?", "Hari ulang
tahun saya" and "I lost my CDC voucher slip" route to `answer`. "Print
my CDC voucher slip" is a print request. Credential rules run first, so
"Print my Singpass password" refuses with `credential_action` and no
action can capture a credential request. The Malay procedural markers
of runbook 8.1 WP3.4 layer 1 guard both credential and action rules.
The ten action items and the guard item below are in the devset:

```text
+------------------------------------+-----------------+---------------------------+
| Utterance                          | Intent          | Why it is in the set      |
+------------------------------------+-----------------+---------------------------+
| Can you repeat that?               | repeat_previous | English baseline          |
| Say again lah, I didn't catch that.| repeat_previous | Singlish                  |
| Boleh ulang sekali lagi?           | repeat_previous | Malay                     |
| Sorry, can you say that again?     | repeat_previous | Repeat of a refusal       |
| Please repeat that.                | repeat_previous | Nothing to act on         |
| Please print that for me.          | print_previous  | English baseline          |
| Can print the slip for me ah?      | print_previous  | Singlish                  |
| Tolong cetak slip itu.             | print_previous  | Malay                     |
| Print it again please.             | print_previous  | Print after a repeat      |
| Can I have the receipt?            | print_previous  | Nothing to act on         |
| How do I print my CDC vouchers?    | answer          | Procedural guard          |
+------------------------------------+-----------------+---------------------------+
```

Action routing precedes retrieval because retrieval cannot catch it.
The 13-Sep-2026 probe scored the five action utterances at best dense
0.26-0.34, below the 0.50 gate, so today they are refused as
`no_coverage`. The guard question scored 0.725 and answers from
`cdc-vouchers-residents`.

##### Previous-turn resolution

An action resolves its target from SQLite at execution time:

- Same `session_id` as the action turn.
- The most recent stored turn in state `answered` or `refused`.
- `acted` and `failed` turns are skipped. A repeat after a print, or a
  second repeat, resolves to the same original answer.
- The lookup reads the store, not process memory, so it works after a
  backend restart.

If no turn qualifies, the action returns the "nothing to act on"
response below.

##### Action turn shape

The action turn is a new turn with its own `turn_id`, stored like any
other. The fields depend on the outcome:

```text
+--------------+-----------------------------+-----------------------------+---------------------------+
| Field        | repeat_previous             | print_previous              | Nothing to act on         |
+--------------+-----------------------------+-----------------------------+---------------------------+
| state        | acted                       | acted                       | acted                     |
| reply_text   | Previous reply_text         | Fixed confirmation string   | Fixed string              |
| display_text | Previous display_text       | Fixed confirmation string   | Fixed string              |
| reply_audio  | Previous stored WAV bytes;  | TTS of the confirmation     | TTS of the fixed string   |
|              | no TTS call                 | (failure degrades to text)  | (failure degrades to text)|
| slip_text    | Empty                       | Previous slip_text,         | Empty                     |
|              |                             | unchanged                   |                           |
| sources      | Previous sources, same order| Previous sources, same order| Empty                     |
| language     | Previous language           | en                          | en                        |
| case_id      | null                        | null                        | null                      |
+--------------+-----------------------------+-----------------------------+---------------------------+
```

The fixed strings are application strings in the router's catalogue,
never model text:

- print confirmation: "Here is your slip.";
- nothing to act on: "I have not answered a question yet. Please ask
  me first."

`slip_text` carries the print signal. Only `print_previous` returns a
non-empty slip on an `acted` turn, so a repeat never reprints.

The public response of a "nothing to act on" turn looks like any other
`acted` turn with an empty slip. The debug field `action_outcome`
separates it: `resolved` for a real action, `nothing_to_act_on` for the
no-op.

An action turn copies the previous turn's `turn_sources` rows, so a
replay of the action `turn_id` rebuilds the same response from its own
rows.

##### Print policy

design.md 9.3 fixes this: the backend always produces `slip_text`, and
the device applies its configured print policy, `auto` or `on_request`.
WP4.2 implements the client rule below; the backend response is the
same whatever the policy.

```text
+------------+-------------------------------------------------------------+
| Policy     | Client prints (simulator renders the receipt) when          |
+------------+-------------------------------------------------------------+
| auto       | slip_text is non-empty. Today's simulator behaviour.        |
| on_request | state is acted and slip_text is non-empty.                  |
+------------+-------------------------------------------------------------+
```

A response that does not print leaves the last receipt in place, as a
real printer would.

The simulator gains a print-policy control on the page, default
`auto`, held in page state only. The Pi applies the same rule at WP6.3
from its own configuration; `auto` stays the demo baseline (execution
plan 9, item 7). The rule is presentation logic on two fields, so the
thin-client boundary holds.

##### Schema (migration 0002)

Two additive columns in `persistence/migrations/0002_previous_turn.sql`:

```text
+-----------+-------------------+------------------------------------------------+
| Table     | Column            | Meaning                                        |
+-----------+-------------------+------------------------------------------------+
| turns     | previous_turn_id  | TEXT, nullable, REFERENCES turns (turn_id).    |
|           |                   | The turn an action resolved to; null for       |
|           |                   | answer and refuse turns and for "nothing to    |
|           |                   | act on".                                       |
| turns     | action_outcome    | TEXT, nullable, CHECK resolved or              |
|           |                   | nothing_to_act_on. Null on answer and refuse   |
|           |                   | turns.                                         |
+-----------+-------------------+------------------------------------------------+
```

`PRAGMA user_version` becomes 2. The existing `turns_by_session` index
serves the lookup. No existing row changes; old rows read null.

Rollback, recorded in ADR-0007: stop the backend, back up with
`.backup`, drop `action_outcome` then `previous_turn_id`, set
`user_version` to 1, then run the WP4.1 commit. The downgrade SQL is
tested in `backend/tests/unit/test_actions.py`.

##### Debug view additions

Two fields, absent from the public response. `intent` gains two values
and `schema_version` reads 2.

```text
+----------------------+----------------------------------------------------+
| Field                | Value                                              |
+----------------------+----------------------------------------------------+
| previous_turn_id     | turn_id the action resolved to, or null            |
| action_outcome       | resolved, nothing_to_act_on, or null on answer and |
|                      | refuse turns                                       |
| intent               | now also repeat_previous or print_previous         |
+----------------------+----------------------------------------------------+
```

Stage timings on an action turn: `stt_ms` and `routing_ms` greater
than 0; `query_rewrite_ms`, `retrieval_ms` and `llm_ms` null; `tts_ms`
null for a resolved repeat and greater than 0 otherwise.
`best_dense_score` and `evidence_min_dense` are null.

##### Environment variables

None. The print policy is simulator page state and, at WP6.3, Pi
configuration. `health.storage_ready` now requires `user_version` 2.

##### Retention

A repeat stores its own copy of the previous reply audio. The
13-Sep-2026 probe of the live database measured stored reply audio at
806 KB on average and 944 KB at most over nine turns, so each repeat
adds roughly 0.8 MB. No pruning; size review stays with WP4.5.

##### Owner decisions

Approved 13-Sep-2026. Where the print policy lives is not a decision:
design.md 9.3 already places it on the client.

```text
+----+-------------------------------+---------------------------------------------+
| #  | Decision                      | Choice                                      |
+----+-------------------------------+---------------------------------------------+
| 2  | Action response semantics     | state acted; repeat has an empty slip;      |
|    |                               | print speaks a fixed confirmation           |
| 3  | What "previous" means         | Same session; newest answered or refused    |
|    |                               | turn; acted and failed turns skipped        |
| 4  | Nothing to act on             | state acted, fixed wording, no slip; debug  |
|    |                               | action_outcome distinguishes the no-op      |
+----+-------------------------------+---------------------------------------------+
```

##### Files changed and created

Changed, under `backend/src/kaki_backend/` unless a path is given:

- `orchestration/intent_router.py` - action rules, two intents, fixed
  strings
- `orchestration/turn_pipeline.py` - action branch after routing
- `persistence/repositories.py` - previous-turn lookup, the two new
  columns
- `persistence/migrations/0001_initial.sql` - header comment only
- `contracts/turn_log.py` - `previous_turn_id`, `action_outcome`
- `api/debug.py`, `main.py` - fields and wiring
- `backend/README.md`
- `agent/data/devset.jsonl`, `agent/README.md` - action items, `after`
- `scripts/run_regression.py` - `after` sessions, disposable database
- `scripts/wp_check.py` - WP4.2 tier B; WP4.1 schema check "at least"
- `scripts/wp4_1_evidence.sh` - Test 1 schema check "at least"
- `scripts/kaki_env.sh` - `KAKI_DB` for WP4.2
- `scripts/dev_stack.py`, `scripts/tests/test_dev_stack.py` - MLX-LM
  runs with `PYTHONUNBUFFERED=1`
- `backend/tests/unit/test_persistence.py`,
  `backend/tests/contract/test_wp4_1.py` - schema check "at least"
- `scripts/tests/test_run_regression.py` - action items
- `apps/web/src/simulator/Simulator.tsx` - policy control, receipt rule
- `apps/web/src/app/globals.css` - policy control style
- `backend/src/kaki_backend/fixtures/README.md`
- `docs/decisions/adr-0007-sqlite-persistence.md` - migration 0002,
  rollback

Created:

- `actions/__init__.py` - `ActionOutcome`, the `TurnHistory` reader
- `actions/repeat_action.py`, `actions/print_action.py` (design.md 18)
- `persistence/migrations/0002_previous_turn.sql`
- `backend/tests/unit/test_action_routing.py`,
  `backend/tests/unit/test_actions.py`
- `backend/tests/contract/test_wp4_2.py` - AT-04/05 over the API
- `apps/web/src/simulator/printPolicy.ts`,
  `apps/web/src/test/printPolicy.test.ts` - AT-06
- `scripts/wp4_2_evidence.sh` - owner evidence harness
- `repeat_request.wav`, `print_request.wav` - owner-captured

No new dependency.

##### Fixture capture

One-time owner task, then committed and never regenerated (same as the
WP3.4 fixtures). Run `scripts/wp4_2_evidence.sh --capture-fixtures`.

Expected: two 16 kHz mono WAVs of roughly 1-3 seconds, spoken with
`say -v Samantha`: "Can you repeat that?" and "Please print that for
me." The harness plays each one, asks for a verdict and refuses to
overwrite an existing file. The exact text is already in
`fixtures/README.md`.

The harness removes a file it just wrote if `afinfo` reports zero
audio bytes. Exit 3 means the files were written but no terminal was
available for the listening verdict.

Captured by the owner on 13-Sep-2026 from a logged-in Terminal. The
coding agent's sandbox could not capture them: `say` wrote a WAV header
with zero audio bytes, and the sandbox blocks the harness's process
substitution.

The devset covers the Singlish and Malay utterances over the text
path; they need no fixture.

##### Reconciliation

- Migration 0002 moves the schema to version 2. The WP4.1
  schema-version checks in `wp_check.py`, `test_persistence.py`,
  `test_wp4_1.py` and `wp4_1_evidence.sh` Test 1 now assert "at least
  1". Only WP4.2 asserts exactly 2. The requirement changed, so this is
  not test weakening (AGENTS.md 15). The failed-migration test keeps its
  exact value, because it uses its own two-step migration set.
- The stale `0001_initial.sql` header comment, which said WP4.3 creates
  `cases` in migration 0002, now says `cases` is deferred beyond the
  MVP. Only the comment changed; the SQL is identical, so databases
  already at version 1 are unaffected. ADR-0007 is updated to match.
- `run_regression.py` now writes a disposable database, deleted on
  exit. Its docstring says so.
- ADR-0007 estimated reply audio at 70-180 KB per turn. The live
  database measured 806 KB on average; the ADR now records both.

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

Withdrawn: the former Test 3, case lifecycle and handoff. The MVP creates
no case and hands nothing off, so WP4-AT-07 to WP4-AT-12 are withdrawn
with it.

---

# 10. WP5 - Singapore language + improvement

Status: **DRAFT - structure fixed; Prepare WP5.x fills in commands**

### 10.1 Setup and installation

##### Known setup.md coverage

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

##### Components absent from setup.md

**Singapore speech set.** `Prepare WP5.x` documents its collection,
consent record and storage under `KAKI_DATA_ROOT`.

##### Challenger installation rule

Install a challenger only when a measured baseline limitation justifies
it, and only into its own virtual environment. Do not guess installation
commands in advance; verify them during the relevant `Prepare WP5.x`.

##### Runbook writing rule

Use the WP3.4 block as the reference structure for every WP5.x section
the coding agent fills in during Prepare.

### 10.2 Testing and validation

##### Test 1: Malay regression

**Objective:** prove the baseline handles the Malay path the design
promises before any challenger work starts.

##### Test 2: bake-off

**Objective:** run baseline and challenger sequentially on the same
speech set and record quality plus p50/p95, so the promote/keep/reject
decision rests on evidence.

##### Test 3: decision record

**Objective:** prove each bake-off ends in a recorded decision.
Challenger failures do not block the working baseline.

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
```

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

   Expected: `status` ok with `stt_ready`, `llm_ready` and `tts_ready` true.
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
