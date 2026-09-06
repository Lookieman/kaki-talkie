# KaKi-Talkie WP validation runbook

Version 1.0 | 06-Sep-2026 | SGLN Group 10

Repository location: `docs/04-prototype/wp-validation-runbook.md`

This is the **single operational source of truth** for project-owner installation, setup, configuration, service start/stop, manual validation, evidence collection and teardown.

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
Status: **READY — implemented; owner Mac smoke pending**

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
Status: **READY — implementation authorised; owner Mac smoke pending**.
The owner's 07-Sep-2026 implementation instruction resolves the prior B1/B2
planning blockers with the configuration and CLI contract below. Commands for
new application code are the implementation contract; verify them on Windows
before reporting implementation complete. Mac execution is owner-only.

Scope: WP2-AT-02/03/07/08 — useful English transcription, language evidence,
default audio deletion and explicit test retention. Baseline: Whisper
large-v3-turbo through `whisper.cpp`. Owner review and Mac smoke are required.

### WP2.2 machines, accounts and directories

- Windows: existing development account, `C:\projects\kaki-talkie-wp2.2`,
  worktree `.venv`; deterministic checks only. No Whisper model/build required.
- Mac Mini M4 Pro: `websvc`, macOS 14+ and the existing application checkout
  with Python 3.11+ `.venv`. Start in that checkout; capture its actual path
  below rather than assuming an undocumented installation directory.
- Mac prerequisite installation: the owner's existing administrator/Homebrew
  owner account when required; run the model service as `websvc`, never root.
- No Raspberry Pi prerequisites. No Cloudflare routing changes or model port
  exposure. No Qwen, real TTS, MERaLiON, RAG or DSPy installation.

In a Mac terminal as `websvc`, from the application checkout root:

```sh
whoami
pwd
uname -m
sw_vers -productVersion
test -f backend/pyproject.toml
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate"
python --version
export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
export WP22_RUNTIME="/Users/websvc/kaki-runtimes/whisper.cpp-v1.7.6"
export WP22_MODELS="$KAKI_DATA_ROOT/models/whisper.cpp"
export WP22_MODEL="$WP22_MODELS/ggml-large-v3-turbo.bin"
umask 077
mkdir -p /Users/websvc/kaki-runtimes "$WP22_MODELS" "$KAKI_DATA_ROOT/wp2.2"
export WP22_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp2.2/smoke.XXXXXX")"
printf '%s\n' "$KAKI_APP_ROOT" "$WP22_EVIDENCE"
```

Expected: `websvc`, `arm64`, supported OS/Python, successful file check and a
new private evidence directory outside Git. Stop on any failed prerequisite.
`WP22_*` are shell helpers for this procedure, not implemented backend settings.
Repeat exports in each terminal, using the same printed evidence directory
instead of creating another one. Do not overwrite an existing runtime checkout.

### WP2.2 one-time tools and backend prerequisites

Check the Mac tools first:

```sh
xcode-select --print-path
xcrun clang --version
git --version
curl --version
/opt/homebrew/bin/brew --version
```

If Command Line Tools are absent, the owner installs them and completes the
macOS dialogue with `xcode-select --install`, then repeats the first two checks.
This command is documented by [Apple](https://developer.apple.com/library/archive/technotes/tn2339/_index.html).

If Homebrew is absent, its owner installs it from an administrator login using
the [official installer](https://brew.sh/), then returns to `websvc`:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

As the existing Homebrew owner, install CMake; do not use `sudo brew`:

```sh
/opt/homebrew/bin/brew install cmake
/opt/homebrew/bin/cmake --version
```

The package command is verified against the [CMake formula](https://formulae.brew.sh/formula/cmake).
The source build requires CMake 3.14+ via its bundled
[ggml configuration](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/ggml/CMakeLists.txt).
If the installed CMake/toolchain cannot configure this revision, retain the
error and treat that machine's build as blocked; do not guess compatibility flags.

Back as `websvc`, from `KAKI_APP_ROOT` with its `.venv` active, the existing
repository dependency command is:

```sh
python -m pip install --only-binary=av -e 'backend[test,dev]'
python -c "import av, fastapi, httpx; print('PyAV', av.__version__); print('backend dependencies available')"
```

Expected: PyAV 18.1.0 and successful imports. Install the adapter separately
as documented below. No global Python installation.

### WP2.2 pinned runtime and model installation

Use the verified `v1.7.6` source tag for this procedure; it is a reproducible
selection, not a claim that it is the latest release. From `websvc`'s terminal:

```sh
git clone --branch v1.7.6 --depth 1 https://github.com/ggml-org/whisper.cpp.git "$WP22_RUNTIME"
cd "$WP22_RUNTIME"
git describe --tags --exact-match
git rev-parse HEAD
/opt/homebrew/bin/cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_SERVER=ON
/opt/homebrew/bin/cmake --build build -j 4 --config Release
test -x build/bin/whisper-server
./build/bin/whisper-server --help
```

Expected: tag `v1.7.6`, recorded commit SHA, successful build and server help.
Build steps derive from the [pinned README](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/README.md)
and [CMake options](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/CMakeLists.txt).
No Core ML conversion or separate FFmpeg binary is needed for this WAV path.

Still in `WP22_RUNTIME`:

```sh
sh ./models/download-ggml-model.sh large-v3-turbo "$WP22_MODELS"
test -s "$WP22_MODEL"
shasum -a 256 "$WP22_MODEL"
```

Model: `large-v3-turbo`, upstream converted artifact
`ggerganov/whisper.cpp/ggml-large-v3-turbo.bin`; local cache is exactly
`/Users/websvc/kaki-talkie-data/models/whisper.cpp/ggml-large-v3-turbo.bin`.
The [pinned downloader](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/models/download-ggml-model.sh)
supports this identifier and destination argument, fetching from Hugging Face.
It skips an existing file. A non-empty file/hash alone does not establish a good
download: successful model loading below is mandatory. Record the hash for
repeatability; no independently verified expected hash is asserted here.
If download/loading fails, preserve the error and inspect the specific artifact
before retrying; do not silently substitute another model or delete shared caches.

### WP2.2 service start order and readiness

For the upstream-only smoke, start only Whisper. Use a foreground terminal as
`websvc`, working directory `WP22_RUNTIME`. First inspect the proposed port:

```sh
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Expected before start: no listener (normally exit 1). If occupied, identify it;
do not kill an existing service or silently change the documented port.

```sh
cd "$WP22_RUNTIME"
./build/bin/whisper-server --host 127.0.0.1 --port 8080 -m "$WP22_MODEL" -l auto
```

The [server usage](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/examples/server/README.md)
verifies these flags. Do not enable `--convert`, debug dumps or transcript
printing. Use only the synthetic fixture during this preparation smoke.

In a second `websvc` terminal:

```sh
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8080/health
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Expected: HTTP 200 with `{"status":"ok"}` and only `127.0.0.1:8080` listening.
Retry manually while the model loads; record startup errors instead of treating
a listening socket alone as ready. The [server source](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/examples/server/server.cpp)
defines readiness, multipart handling and verbose language evidence. Without
conversion, it reads uploaded audio from memory rather than writing a WAV file.

Application start order: Whisper -> CLI readiness check -> configured FastAPI
backend -> optional existing simulator. Public `/api/health` aggregation remains
WP2.4 scope. The standalone CLI does not require FastAPI to be running.

### WP2.2 fixed English upstream smoke

Use the existing synthetic `backend/src/kaki_backend/fixtures/canned_reply.wav`;
its provenance and exact text are in the adjacent README. Do not use the WP2.1
tone fixture to assess transcription. From the application checkout, with the
exports above and its `.venv` active:

```sh
cd "$KAKI_APP_ROOT"
curl --fail --silent --show-error --max-time 120 \
  http://127.0.0.1:8080/inference \
  -F "file=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/canned_reply.wav" \
  -F response_format=verbose_json \
  -o "$WP22_EVIDENCE/transcription.json"
python -m json.tool "$WP22_EVIDENCE/transcription.json"
```

The [upstream request example](https://github.com/ggml-org/whisper.cpp/blob/v1.7.6/examples/server/README.md)
specifies multipart `file` and `response_format`. The pinned source supplies
`text`, `language`, `detected_language` and `detected_language_probability` in
verbose output. Expect a useful rendering of the fixture's two sentences;
capitalisation, punctuation and spelling of the product name may differ.
Expect English language evidence, a finite probability between zero and one,
and no error object. Do not manufacture evidence by merely echoing the configured
language. The 120-second curl limit bounds this manual diagnostic; it is not a
product latency target or the future adapter timeout.

This checks the upstream runtime only. It does not prove WP2-AT-02/03 through
the application adapter, nor the application's audio deletion/retention gates.
The deliberate source fixture remains in Git; default deletion applies to
per-request copies/resources, not deletion of the curated fixture itself.

### WP2.2 application configuration and smoke

As `websvc`, from `KAKI_APP_ROOT` with `.venv` active, install the adapter into
the same application environment (the C++ model remains a separate process):

```sh
python -m pip install -e services/stt/whisper_cpp
python -c "from kaki_whisper_cpp.adapter import WhisperStt; print('Whisper adapter import OK')"
export KAKI_STT_MODE=whisper
export KAKI_WHISPER_URL=http://127.0.0.1:8080
export KAKI_STT_TIMEOUT_SECONDS=30
export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data
python scripts/check_stt.py --help
python scripts/check_stt.py --readiness
```

The adapter package declares HTTPX >=0.27,<1, already used by backend tests.
`KAKI_STT_MODE` accepts `canned` (default) or `whisper`; invalid values fail
startup. The URL must be HTTP with a literal loopback address, port and no
credentials/path/query. Readiness uses a two-second network timeout; transcription
uses the configured finite 0.1–120-second network timeout (default 30 seconds).
These are network-operation bounds, not an end-to-end latency acceptance target.
Redirects/proxies are disabled and response size is capped at 256 KiB.
No runtime model loading occurs inside FastAPI. `.env.example` is documentation;
export settings explicitly, because the application does not auto-load `.env`.

After Whisper is ready, start the backend in a separate foreground terminal with
these exports and `.venv` active:

```sh
cd "$KAKI_APP_ROOT"
python -m kaki_backend.main
```

Expect `127.0.0.1:8000`; check `lsof -nP -iTCP:8000 -sTCP:LISTEN` and
`curl --fail http://127.0.0.1:8000/api/health`. The existing health JSON remains
unchanged; STT readiness is checked by the CLI. The CLI runs the same configured
adapter/pipeline directly and does not require a running backend or simulator.

Run the owner fixture smoke from the application checkout:

```sh
python scripts/check_stt.py --input backend/src/kaki_backend/fixtures/canned_reply.wav
python scripts/check_stt.py --input backend/src/kaki_backend/fixtures/canned_reply.wav --retain-test-audio --consent-to-retain
```

The CLI reports JSON with the selected test transcript, language evidence,
timings, audio release, retry/selection checks and any retained path. It runs an
original turn, a same-ID retry and an unselected control turn. Expect useful
English text, language evidence, released input buffers, one execution for the
original/retry pair, and two total STT calls including the control. Inspect the
text against the fixed fixture; no invented transcription accuracy threshold.
Default mode writes no audio. Retain mode writes exactly one original input copy
under `KAKI_DATA_ROOT/wp2.2/retained`, with a generated filename; the retry and
unselected control must create no copies. The source fixture itself is preserved.

Both retention flags and an explicit `--input` are required. There is no public
API parameter or environment variable enabling retention. `KAKI_DATA_ROOT` is
required only for explicit retention and must be an absolute path outside a Git
checkout. Ordinary backend logs contain language evidence and safe failure codes,
not raw audio or transcript text; transcript output is limited to the deliberate
owner CLI test. Normalised WAV and original request buffers are released before
later canned stages; the upload spool is closed before processing begins.

To exercise the real HTTP route with this synthetic fixture:

```sh
curl --fail --silent --show-error --max-time 120 http://127.0.0.1:8000/api/device/turn \
  -F device_id=wp22-smoke -F session_id=wp22-smoke -F turn_id=wp22-smoke-1 \
  -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/canned_reply.wav"
```

Expect `answered` with the unchanged nine-field response and clearly canned
reply/audio; only transcription is real in WP2.2. Retry the same request to
check the first response is retained. Use a fresh turn ID for each new test.

Stop Whisper with Ctrl+C. `python scripts/check_stt.py --readiness` and the
fixture CLI must exit non-zero with safe diagnostics. Submit the HTTP request
with a fresh turn ID: expect HTTP 200, `failed`, calm non-empty text and no
invented speech audio. Restart Whisper, repeat readiness and the fixture command,
and use a fresh HTTP turn ID to prove recovery. Reusing a completed failed turn
ID deliberately returns its first failure. Deterministic tests cover malformed
responses, empty input, timeouts, cancellation, resource release before later
stages and retention isolation without requiring actual model failures.

After examining the printed retained path, delete only that file interactively;
replace the placeholder with the exact generated basename from the CLI:

```sh
rm -i "$KAKI_DATA_ROOT/wp2.2/retained/<printed-basename>"
```

The placeholder is output-dependent, not a literal filename. Do not delete the
whole data root. Rerun the default CLI and confirm no new retained file appears.
Record observations under `WP22_EVIDENCE`. Mac smoke remains pending until the
owner runs these procedures; automated evidence does not substitute for it.

### WP2.2 deterministic regression checks

Existing executable checks, Windows development account, worktree root:

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

Install the adapter into the Windows `.venv` with
`.\.venv\Scripts\python.exe -m pip install -e services/stt/whisper_cpp`.
Set `KAKI_STT_MODE=canned` for deterministic regression. Expected: all pass
without a model service. Adapter tests are discovered in backend/tests/unit.
Required added coverage: response parsing,
language evidence, readiness, bounded failures, success/error cleanup, explicit
retention isolation and idempotent retries. Preserve earlier behavioural assertions.

### WP2.2 stop, evidence and limitations

For upstream failure/restart smoke, press Ctrl+C in the foreground Whisper
terminal. Confirm shutdown from the second terminal:

```sh
lsof -nP -iTCP:8080 -sTCP:LISTEN
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8080/health
```

Expected: no listener and curl connection failure. Restart with the same server
command, repeat readiness and fixed-fixture smoke. Never use broad process kills.
For the eventual application stack stop in reverse order: optional simulator,
FastAPI, then Whisper, using Ctrl+C in each owned foreground terminal. Use the targeted retained-file
teardown above; do not improvise recursive deletion.

Keep the runtime build, model cache and synthetic transcript evidence for reruns;
no uninstall is required. After review, the owner may remove just this smoke's
generated transcript (with `WP22_EVIDENCE` still set to its printed directory):

```sh
rm -i "$WP22_EVIDENCE/transcription.json"
```

Retain under the run's evidence directory: application path/commit, OS/architecture,
Python/CMake/compiler versions, Whisper tag/SHA, model SHA-256, exact command
results, readiness/listener observations, synthetic transcript/language output,
regression results and eventual deletion/retention/failure/recovery observations.
Record consent and disposal of deliberately retained test audio separately; never
collect ordinary user audio as gate evidence.

Sources were inspected on 07-Sep-2026; no Mac build, model load or smoke has been
executed by Codex. Model source download follows upstream's model repository
`main`; record the downloaded hash. Real speech usefulness, Mac compatibility
and actual cleanup remain owner validation. Memory release is not a promise of
forensic RAM erasure. WP2.1 Mac smoke remains pending as recorded in section 7.1.
Full health aggregation, debug UI, Qwen, real TTS and latency measurement remain
WP2.3/WP2.4 work. B1/B2 are resolved by the approved implementation contract
above. Mark VERIFIED only after the owner completes the application smoke.

## 7.3 WP2.3 - MLX/Qwen generation

Owner level: **S**  
Status: **DRAFT - exact Qwen checkpoint must be selected during Prepare**

Machine: Mac Mini  
User: `websvc`

Locked runtime family: MLX-LM with a small quantised Qwen-class instruct model.

`Prepare WP2.3` must document:

- service-specific virtual environment;
- MLX-LM installation/verification;
- exact approved Qwen model identifier;
- model cache location;
- adapter/start/readiness/stop commands;
- fixed transcript input;
- five-run <=60-word response check;
- failure/recovery check;
- evidence.

Do not introduce RAG, DSPy or SEA-LION.

## 7.4 WP2.4 - macOS say + full WP2 gate

Owner level: **G**  
Status: **DRAFT - finalise after WP2.1-WP2.3**

Machine: Mac Mini + protected Chrome browser on laptop/phone  
User: `websvc`

Baseline English TTS: macOS `say`.

`Prepare WP2.4` must document:

- exact service start order;
- `dev_up`/`dev_down` usage if implemented;
- `/api/health` readiness checks;
- protected debug-panel URL;
- fixed end-to-end questions;
- empty/silence/failure checks supported by the implementation;
- exact latency-script `--help` command;
- exact ten-run latency command;
- p50/p95 evidence location;
- WP1 regression command;
- shutdown verification.

Package-gate outcome:

- real English speech-in -> speech-out works;
- transcript and timing fields are visible;
- replies are clearly labelled ungrounded in WP2;
- raw-audio deletion remains proven;
- p50/p95 are recorded, with no invented threshold;
- WP1 contract regression remains green.

---

# 8. WP3 - grounded knowledge + refusal

Status: **DRAFT**

Before each WP3 IU implementation, `Prepare WP3.x` must populate its exact operational section.

Expected operational topics:

- `KAKI_DATA_ROOT` directory preparation;
- allowlisted source ingestion;
- runtime snapshot/processed paths;
- embedding runtime/model;
- Chroma storage;
- ingestion script `--help` and example;
- deterministic retrieval tests;
- golden-path/regression commands;
- provenance/source-date checks;
- refusal/insufficient-evidence checks;
- secret-redaction tests;
- teardown/reindex recovery.

Generated corpus snapshots belong under `KAKI_DATA_ROOT`. Commit only intentional, small, non-sensitive deterministic fixtures/evidence.

Golden-path acceptance is defined in the execution plan; operational commands live here.

---

# 9. WP4 - memory + actions + case closure

Status: **DRAFT**

Expected operational topics:

- SQLite path, migration and backup/restore;
- restart/durable-idempotency checks;
- repeat/print previous behaviour;
- pending/case lifecycle;
- Google Calendar test account/calendar and confirmation procedure;
- handoff adapter decision;
- presenter controls where retained.

### Handoff-channel decision

The exact kaki handoff channel is not locked before WP4.3.

During `Prepare WP4.3`, choose one of:

```text
A. logging/test adapter only for MVP;
B. Telegram adapter;
C. another explicitly approved bounded channel.
```

If Telegram is not selected, do not install/configure Telegram and do not treat its absence as a failed gate.

The core WP4 requirement is durable case creation + idempotent handoff behaviour behind `HandoffPort`; the selected real external channel is a separate MVP choice.

Morning scheduler automation remains deferred unless the owner explicitly reintroduces it.

---

# 10. WP5 - Singapore language + improvement

Status: **DRAFT**

Expected operational topics:

- Malay regression path;
- consent-cleared SG speech set;
- MERaLiON challenger environment and bake-off;
- SEA-LION challenger environment and bake-off;
- OmniVoice challenger environment and human review;
- DSPy migration/evaluation;
- model/cache locations and RAM/disk considerations;
- baseline/challenger sequential run procedure;
- p50/p95 and quality evidence;
- promote/keep/reject decision record;
- allowlisted live-lookup gate.

Challenger failures do not block the working baseline. Do not install every challenger into one shared runtime by default.

Exact challenger installation commands must be verified during the relevant `Prepare WP5.x` step. Do not guess them in advance.

---

# 11. WP6 - physical client + hardening

Status: **DRAFT**

Expected Tier C operational topics:

- Raspberry Pi OS/version;
- first-boot preparation;
- Python/system dependencies;
- ALSA capture/playback device names;
- dome button/GPIO;
- LED states;
- ESC/POS printer + separate power;
- systemd install/start/restart;
- service authentication;
- network retry with same `turn_id`;
- optional Tailscale hardening;
- canned-mode sequence;
- alternate connectivity path;
- process-kill/power-cycle recovery;
- SD-card image/restore;
- final demo-run procedure.

The Pi must remain a thin client. Model/RAG/prompt/case-decision logic on the Pi is a gate failure.

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

If you are unsure what to install, start, test or stop, this runbook is the place to fix. Do not create another operational guide.
