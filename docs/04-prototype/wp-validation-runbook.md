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
.\.venv\Scripts\python.exe scripts/check_code_history.py
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

The existing history checker currently rejects header-only new files, contrary to
AGENTS.md section 12. Its gate remains unresolved pending the owner's decision on
a separate narrow tooling correction; no initial-line tags have been added to
circumvent that rule. Mark VERIFIED only after the owner completes the Mac smoke.

```text
WP2.1 output: 16000 Hz / mono / signed 16-bit PCM WAV
Later gates: transcription, language evidence, retain mode, full speech loop
```

Do not introduce STT, LLM or TTS in WP2.1.

## 7.2 WP2.2 - whisper.cpp STT

Owner level: **S**  
Status: **DRAFT - prepare before implementation**

Locked baseline: Whisper large-v3-turbo through `whisper.cpp`.

Machine: Mac Mini  
User: `websvc`

`Prepare WP2.2` must make this section READY and document:

- upstream/runtime source location outside the app repo;
- build/install commands;
- exact model identifier/file;
- model/cache location;
- adapter configuration;
- readiness/start/stop commands;
- fixed English fixture;
- transcript/language-evidence check;
- raw-audio deletion check;
- deliberate retain/test-mode check;
- failure/restart check;
- evidence to retain.

Do not introduce Qwen, TTS or MERaLiON in this IU.

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
