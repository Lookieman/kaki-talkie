# KaKi-Talkie WP validation runbook

Version 1.8 | 10-Sep-2026 | SGLN Group 10

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

Status: **WP3.1 VERIFIED / CLOSED 10-Sep-2026; WP3.2-WP3.4 DRAFT - structure
fixed; Prepare WP3.x fills in commands**

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

### 8.2 Testing and validation

#### WP3.1 tests - ingestion, idempotency and regression

Run in order on the Mac as `websvc` with the WP3.1 exports active. The
WP-level Tests 1-4 further below belong to WP3.2-WP3.4; WP3.1 owns only
the snapshot/clean/provenance parts proven here.

Automated runner: the objective observations of Tests 1 and 2 are also
registered as one command, which runs the real ingestion twice and checks
dated snapshots, full provenance and hash/chunk stability:

```sh
cd "$KAKI_APP_ROOT"
python scripts/wp_check.py --unit WP3.1 --tier B
```

Expected: a JSON report and `PASS: all WP3.1 tier B checks succeeded.`
Copy the report into `WP31_EVIDENCE`. The manual commands below remain
for inspection and troubleshooting.

##### WP3.1 Test 1: dated snapshot ingestion (WP3-AT-01)

Objective: prove one owner command captures every allowlisted source into
a dated, never-hand-edited snapshot and produces cleaned, chunked output
in which every chunk carries full provenance metadata.

```sh
cd "$KAKI_APP_ROOT"
python scripts/ingest_corpus.py --help
python scripts/ingest_corpus.py --allowlist rag/corpus/allowlist.yaml
```

Expected: exit zero; a summary (JSON to stdout) listing each `source_id`
with its status, content hash, snapshot path and chunk count. Manual
sources report status `manual` and read their newest seeded snapshot;
they are never fetched live. Under
`KAKI_DATA_ROOT/corpus/snapshots/<date>/` there is one seeded capture
(`<source_id>.md`) and one capture-metadata file
(`<source_id>.meta.json`) per allowlisted source. Under
`KAKI_DATA_ROOT/corpus/processed/`, `chunks.jsonl` holds the chunk
records and `pages/<source_id>.md` holds the cleaned page for human
inspection; chunk records hold clean markdown/text and all eight
provenance fields
(`source_url`, `page_title`, `scheme`, `captured_at`, `source_updated_at`,
`content_hash`, `freshness_class`, `valid_until`; the last two may be
explicit nulls where the source offers no value). `captured_at` derives
from the snapshot, not the clock at chunking time. Spot-check one chunk
against the official page. A manual source with no seeded snapshot must
be reported as failed, exit non-zero, name that source and leave other
sources' snapshots intact. Copy the summary into `WP31_EVIDENCE`.

##### WP3.1 Test 2: unchanged re-ingestion is stable (WP3-AT-02)

Objective: prove re-running ingestion over unchanged sources keeps
content hashes stable and creates no duplicate chunks, so later Chroma
upserts (WP3.2) can rely on stable chunk identity.

Rerun the Test 1 ingestion command, then compare its summary with the
Test 1 summary.

Expected: exit zero; every source reported with an identical content
hash (manual sources report status `manual` in both runs); identical
chunk counts and chunk identifiers; no second snapshot copy of
unchanged content and no appended/duplicated chunk records in the
processed store. Seeded markdown is static, so hash and chunk-identity
stability hold by construction; this test proves the pipeline does not
break them. Copy the second summary into `WP31_EVIDENCE` alongside the
first.

##### WP3.1 Test 3: deterministic offline regression

Objective: prove the new corpus code is covered by network-free tests and
that prior WP1/WP2 Tier A behaviour still holds with `kaki-rag`
installed (WP3-AT-13 stays green as WP3 grows).

From the development checkout root with its virtual environment active
and no model services running:

```sh
python -m ruff check --config backend/pyproject.toml backend scripts services rag
python -m unittest discover -s rag/tests -v
python -m unittest discover -s backend/tests/contract -v
python -m unittest discover -s backend/tests/unit -v
python -m unittest discover -s scripts/tests -v
```

Expected: all pass without network access. `rag/tests` must cover, from
committed fixtures: allowlist validation (non-allowlisted URL rejected;
`capture` field accepted), cleaning of a fixture markdown page and a
fixture HTML page, heading-aware chunking within the roughly
300-500-token guidance, presence of all eight provenance fields, and
hash/chunk-identity stability across a repeated run. The web suite
and `scripts/check_wp1_integration.py` are unaffected by WP3.1 (no
backend or web change); rerunning them is optional.

##### WP3.1 teardown and evidence

Nothing to stop: the CLI exits after each run. Snapshots and processed
chunks remain in place as the working corpus for WP3.2; do not delete
them as cleanup. Retain under `WP31_EVIDENCE`: application commit,
Python version, install verification output, both ingestion summaries and
the regression results. No audio, credentials or personal data are
involved.

Troubleshooting: if ingestion reports a manual source as failed, check
that its seeded snapshot exists under the newest snapshot date with a
matching `.meta.json` (`scripts/seed_snapshot.py --list` shows the
allowlisted source-ids). If cleaning produces empty or junk text for a
seeded markdown file, fix the markdown at its source extraction and
re-seed with `--force`; do not hand-edit the processed output.

Known limitations: no embeddings, vector store, retrieval, grounded
answering or refusal behaviour yet - those are WP3.2-WP3.4. Mark this
block VERIFIED only after the owner completes Tests 1-2 on the Mac.

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
