# KaKi-Talkie coding-agent instructions

Version 1.0 | 02-Sep-2026 | SGLN Group 10

This file governs coding-agent behaviour in the `kaki-talkie` repository.

The authoritative MVP architecture and scope are in `docs/04-prototype/design.md`. The build sequence and package gates are in `docs/04-prototype/execution-plan.md`. This file defines how an agent is allowed to work inside those boundaries.

---

## 1. Authority and precedence

Use this precedence order:

1. `docs/04-prototype/design.md` - single source of truth for architecture, scope, interfaces and locked decisions.
2. The work package explicitly named by the user in `docs/04-prototype/execution-plan.md`.
3. This `AGENTS.md` - repository, coding, testing and safety rules.
4. Component README files and ADRs.
5. Existing implementation details.

If two documents conflict, do not silently reconcile them in code. Follow the higher-authority source and report the conflict.

Do not modify `design.md`, `execution-plan.md` or `AGENTS.md` unless the user explicitly asks for that document to be changed.

---

## 2. Work-package boundary

When asked to implement a work package:

- implement only the named work package;
- preserve all acceptance tests from earlier gates;
- do not pre-build later-package features merely because they appear obvious;
- do not create speculative adapters, services, directories or placeholder modules;
- create a directory only when its first real implementation file is required;
- preserve existing repository artefacts and content unless the active work package requires a change.

If work outside the active package would be useful, report it as a later task rather than implementing it.

---

## 3. Decisions: what the agent may decide

### 3.1 Implementation decisions may proceed

The agent may make low-level choices that remain inside a locked design boundary, for example:

- internal class or function decomposition;
- a parsing technique;
- test-fixture structure;
- a library used behind an already-defined port where the design has not fixed the implementation;
- internal error-handling structure;
- file placement inside an already-defined ownership area.

Record a short ADR or decision note only when the choice is durable or materially affects future work.

### 3.2 Design decisions must stop

Do not autonomously change or invent:

- request or response contracts;
- authentication or authorisation behaviour;
- security boundaries;
- personal-data retention rules;
- public network exposure;
- side-effect semantics or confirmation behaviour;
- repository ownership boundaries;
- model/business logic on the Raspberry Pi;
- MVP scope or P1 requirements;
- new external integrations;
- user interaction semantics.

If implementation requires one of these changes, stop that part of the work and report the required design decision.

---

## 4. Architecture boundaries

The Mac Mini does the thinking. Clients stay deliberately simple.

### Backend

`backend/` owns:

- the public FastAPI contract;
- orchestration;
- state and persistence;
- deterministic actions;
- case and follow-up behaviour.

Application code depends on ports/interfaces, not directly on model-vendor APIs.

### Services

`services/` owns replaceable STT, LLM and TTS adapters.

Do not leak model-runtime dependencies into orchestration code.

### RAG

`rag/` owns ingestion, provenance, retrieval, Chroma integration and the later allowlisted live-lookup path.

Generated corpus snapshots, processed corpus data, Chroma data and SQLite runtime files live under `KAKI_DATA_ROOT`, not in the Git working tree.

### Agent

`agent/` owns DSPy behavioural modules and regression/evaluation data. DSPy must not block the first working grounded vertical slice.

### Device

`device/` is a thin Raspberry Pi client.

Never put these in `device/`:

- LLM or STT model calls;
- retrieval or Chroma logic;
- prompts or DSPy modules;
- intent classification;
- business rules;
- case-state decisions;
- calendar or handoff orchestration.

If device code needs to understand an intent beyond sending a user/device action to the API, stop and re-check the design.

---

## 5. Locked initial implementation baselines

Unless `design.md` is revised:

- FastAPI binds to `127.0.0.1:8000`;
- health/readiness is `GET /api/health`;
- STT baseline is Whisper large-v3-turbo through `whisper.cpp`;
- LLM baseline is a small quantised Qwen-class model through MLX-LM;
- initial English TTS baseline is macOS `say`;
- Chroma is behind `RetrieverPort`;
- printed slips are English-only;
- raw audio is deleted after transcription by default;
- Tailscale Serve is optional and must not become a work-package gate.

Do not substitute another baseline simply because it is more familiar.

---

## 6. Code change history

Every human-authored code file created or modified in this project must carry a version history at the top using comment syntax valid for that file type.

### 6.1 Python, shell and comment-capable YAML

```python
# v1.2 | 02-Sep-2026 | Description of change
# v1.1 | 01-Sep-2026 | Previous change
# v1.0 | 31-Aug-2026 | First version
```

Only the specific code lines changed for the current version receive the matching inline tag:

```python
MAX_RECORD_SECONDS = 15  #v1.2
```

### 6.2 TypeScript and JavaScript

```typescript
// v1.2 | 02-Sep-2026 | Description of change
// v1.1 | 01-Sep-2026 | Previous change
// v1.0 | 31-Aug-2026 | First version
```

Changed lines use the same language-valid comment form:

```typescript
const maxRecordSeconds = 15; //v1.2
```

### 6.3 CSS

```css
/* v1.2 | 02-Sep-2026 | Description of change */
/* v1.1 | 01-Sep-2026 | Previous change */
/* v1.0 | 31-Aug-2026 | First version */
```

Changed declarations may use a valid CSS comment after the declaration where practical:

```css
max-width: 32ch; /* v1.2 */
```

### 6.4 Files that do not support comments

Do not add comments that make the file invalid.

Exclude formats such as:

- JSON;
- lock files;
- generated files;
- binary files;
- third-party vendored files.

Track changes for these through Git and the nearest owning source file or project changelog.

### 6.5 Rules

- newest version entry first;
- use `DD-Mon-YYYY` dates;
- use the exact version tag for changed lines;
- mark only lines changed in that version;
- do not add `#changed`, `// changed`, timestamps, usernames or prose such as `modified here` to inline markers;
- do not add version markers to untouched lines merely because a surrounding block changed;
- documentation Markdown files are not code files and do not require inline version tags unless explicitly requested.

---

## 7. Python style

- Declare variables explicitly.
- Avoid lambda functions unless they are genuinely the clearest option.
- Prefer readable, testable functions over dense expressions.
- Keep adapters small.
- Keep side effects visible.
- Use typed models/contracts where the design defines structured data.
- Do not hide configuration in magic constants when it belongs in config.

---

## 8. Secrets, privacy and runtime data

Never commit:

- passwords;
- OTPs;
- Cloudflare service tokens;
- Tailscale credentials;
- Google/Telegram credentials;
- device secrets;
- API keys;
- service-account files;
- raw user audio by default;
- runtime SQLite or Chroma databases.

`.env.example` documents variable names only, with blank or example-safe values.

Runtime application data belongs under the configured `KAKI_DATA_ROOT` baseline `/Users/websvc/kaki-talkie-data`.

If a user volunteers a password, OTP or other authentication secret, do not intentionally persist that secret. Redact it from stored transcript/log content. Do not treat every six-digit number as an OTP; Singapore postal codes are also six digits. Refusal depends on the requested action/context, not number shape alone.

---

## 9. Git safeguards

- Never push directly to `main`.
- Use a short-lived branch with the project prefix conventions when branch creation is part of the user's workflow.
- Do not commit or push unless explicitly instructed.
- Do not force-push.
- Do not rewrite published history.
- Do not run destructive Git commands such as `git reset --hard`, `git clean -fd`, broad checkout/restore, or branch deletion unless the user explicitly requests them.
- Do not discard uncommitted user work.
- Before editing an existing file, inspect its current contents and preserve unrelated changes.
- Do not replace a complete existing file with a new template when a targeted edit is sufficient.

---

## 10. Test integrity

Tests are gates, not obstacles.

The agent must not:

- delete a failing acceptance test merely to obtain a green run;
- weaken an assertion to fit the implementation without a design reason;
- mark a failing test skipped/xfailed solely to pass the gate;
- alter an earlier work-package test contract without explicit approval;
- change the WP1 turn-schema snapshot without a design revision.

When a test exposes a genuine design conflict, report the conflict instead of making the test lie.

---

## 11. Test tiers

### Tier A - hosted CI

Expected to run without the Mac Mini model stack:

- lint/format checks;
- unit tests;
- contract tests;
- deterministic fixtures;
- simulator build/tests;
- turn-schema snapshot;
- code change-log lint.

### Tier B - Mac Mini gate

Run where local inference/runtime services exist:

- Whisper integration;
- Qwen/MLX-LM integration;
- TTS integration;
- Chroma/RAG integration;
- regression and golden-path suite;
- latency measurements;
- model bake-offs when the active package requires them.

### Tier C - physical-device gate

Run only when device hardware is involved:

- GPIO/button;
- USB speakerphone;
- thermal printer;
- LED ring;
- boot/service recovery;
- network and canned-mode rehearsal.

Do not make Tier B or Tier C model/hardware tests mandatory on ordinary hosted CI without an appropriate runner.

---

## 12. Acceptance-gate behaviour

For an active work package:

1. run its automated acceptance tests;
2. run all earlier deterministic regression/contract gates that apply;
3. report tests not executable in the current environment rather than pretending they passed;
4. do not declare the package complete until its Definition of Done is satisfied or the user explicitly accepts a partial gate.

After WP3 exists, maintain a small must-pass golden-path suite for trust-critical behaviours in addition to percentage-based regression metrics.

---

## 13. External commands and installations

Prefer the existing repository scripts and installed stack.

Do not autonomously introduce:

- Docker or Kubernetes;
- Redis or PostgreSQL;
- message queues;
- observability platforms;
- cloud LLM fallbacks;
- new public ports;
- unrestricted web browsing/agents;
- new external integrations.

A component may be added only when the active work package and `design.md` require it, or the user explicitly approves a design change.

---

## 14. Completion report

At the end of a coding task, report concisely:

- files created;
- files modified;
- behaviour implemented;
- tests run and results;
- tests not run and why;
- any design conflict, open risk or deferred later-package work;
- no claim that a manual/device test passed unless it was actually run.
