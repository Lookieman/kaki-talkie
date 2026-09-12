# KaKi-Talkie coding-agent instructions

Version 1.5 | 12-Sep-2026 | SGLN Group 10

> v1.5 adds the Tier A environment-hygiene rule to sections 5.2 and 15,
> after leaked `KAKI_*` mode switches sent the backend contract tests to
> live services and produced eight false failures.
> v1.4 made the Mac Mini the development machine as well as the runtime
> host, allowed agent sessions from a local terminal, a browser or the
> Claude mobile app, and replaced named-agent wording with vendor-neutral
> wording.

This file governs coding-agent behaviour in the `kaki-talkie` repository.

The purpose of these rules is to keep the coding agent safe **without requiring the owner to write perfect prompts**. The agent should use the repository documents to infer the intended workflow, make ordinary implementation choices independently, and stop only for decisions that genuinely change the product or architecture.

---

## 1. Authority and document roles

Use the documents for different purposes:

1. `docs/04-prototype/design.md` - architecture source of truth and hard system boundaries.
2. `docs/04-prototype/execution-plan.md` - work-package scope, implementation-unit boundaries, acceptance criteria and delivery gates.
3. `docs/04-prototype/wp-validation-runbook.md` - **single operational source of truth** for installation, setup, configuration, service start/stop, owner testing, evidence and teardown.
4. `AGENTS.md` - coding-agent behaviour, code conventions, safety and decision rules.
5. Component READMEs and ADRs - component concepts and durable local decisions.
6. Existing implementation details.

Do not duplicate operational WP procedures in the execution plan, root README, component READMEs or completion reports. Link to the runbook instead.

If documents conflict, use the decision model in section 2 rather than mechanically preserving both statements.

Do not modify `design.md`, `execution-plan.md` or `AGENTS.md` unless the owner explicitly asks for documentation maintenance or a baseline change.

---

## 2. Decision model: locked, changeable, implementation-selected

Not every sentence in the repository has the same rigidity.

### 2.1 Locked architecture

These require an explicit owner decision before changing:

- the Raspberry Pi remains a thin client;
- FastAPI remains the application orchestrator;
- simulator and Pi use the same backend device contract;
- model runtimes remain behind ports/interfaces;
- raw turn audio is deleted after transcription by default;
- secrets and credentials are not committed;
- public/backend security boundaries;
- Singpass remains information guidance only;
- printed slips remain English-only for the MVP unless explicitly revised;
- user-facing side effects remain bounded and idempotent;
- the WP1 turn contract does not change silently.

### 2.2 Baselined but changeable MVP choices

These are current choices, not constitutional rules. The owner's latest explicit direction may revise them without a large design exercise:

- exact model checkpoint inside an approved model family;
- challenger adoption;
- optional Tailscale Serve;
- browser compatibility beyond the primary acceptance browser;
- optional Hokkien path;
- exact handoff channel such as Telegram;
- optional presenter/nudge features;
- optional optimisations and convenience tooling.

When the owner explicitly changes one of these, follow the new direction and identify the minimum documentation that must be reconciled. Do not argue for the stale baseline merely because it appears in an older section.

### 2.3 Implementation choices

Proceed without asking for approval when the choice remains inside the active implementation unit and architecture boundary. Examples:

- helper functions and class decomposition;
- internal data structures;
- fixture organisation;
- private error-handling structure;
- naming of internal helpers;
- file placement inside an already-approved ownership area;
- a small library behind an existing port when no architecture choice is changed.

Record material choices in the completion report. Create an ADR only when a decision is durable enough to matter later.

---

## 3. Interpret owner intent robustly

The owner should not need to write legal-contract prompts.

When a prompt clearly names an implementation unit, treat that named unit as the primary scope.

If another sentence contains an obvious stale or mismatched unit reference, do not derail the task. Use the clearly stated intended unit, mention the mismatch briefly, and continue unless the ambiguity could materially change scope.

When the latest explicit owner instruction conflicts with a baselined-but-changeable choice, treat the latest instruction as the proposed new baseline. Surface the documentation consequence concisely instead of trying to preserve both interpretations.

Stop for clarification only when two plausible interpretations would materially change:

- product scope;
- a public API/contract;
- security or privacy behaviour;
- data retention;
- an external integration;
- an irreversible side effect;
- a locked architecture boundary;
- the active implementation-unit boundary.

Do **not** stop for ordinary low-level implementation choices.

---

## 4. Normal implementation-unit workflow

The normal owner interaction has two commands.

### Prepare

When asked `Prepare WPn.m`:

1. read `design.md`, this file, `execution-plan.md` and the active runbook section;
2. inspect the relevant existing implementation;
3. update **only the active WPn.m runbook section** with the exact owner prerequisites and validation procedure;
4. report concisely:
   - expected files/areas to change;
   - product/architecture decisions requiring owner input, if any;
   - development dependencies;
   - Mac Mini/Pi runtime prerequisites documented in the runbook;
   - read-only local probes run during preparation, with their numbers;
   - any `BLOCKED` item;
5. do not implement application code yet.

### Runbook structure

`wp-validation-runbook.md` follows one section structure for every work-package unit. When updating the runbook:

- edit only the active unit's section;
- keep the established element order: owner level, status line, machine and user, setup cross-reference to `setup.md`, objective-led tests, evidence paths;
- state each test as objective, command, expected observation;
- do not restructure, reformat or renumber other sections;
- do not duplicate `setup.md` installation steps; cross-reference them.

The structure of the WP2.2 section is the reference example.

The file list is a planning aid, not an inflexible whitelist. During implementation, the agent may add a necessary file inside the active unit's expected ownership areas without stopping. Report the deviation at completion. Stop only if the additional file crosses an ownership/scope boundary.

### Implement

When asked `Implement WPn.m`:

1. use the prepared runbook as the owner setup/test contract;
2. implement only the active unit;
3. make ordinary implementation choices independently;
4. run applicable Tier A and earlier deterministic regression tests;
5. update the active runbook section if implementation changes a documented command, prerequisite or expected result;
6. stop at the unit boundary;
7. provide the concise completion report in section 16.

Do not require the owner to repeat the safeguards from this file in every prompt.

---

## 5. Development and runtime environments

The Mac Mini is the development machine and the runtime host.

```text
+------------------------+---------------------------------------------------+
| Environment            | Role                                              |
+------------------------+---------------------------------------------------+
| Mac Mini (websvc)      | Coding agent, Git worktrees, Tier A tests,        |
|                        | runtime, local models, Tier B commands            |
| Raspberry Pi           | Thin client and Tier C hardware validation        |
| Phone/laptop browser   | Owner interaction smoke and gate ceremonies       |
+------------------------+---------------------------------------------------+
```

### 5.1 Agent sessions

The owner starts an agent session in one of three ways. The rules below apply to all three:

1. a terminal on the Mac Mini;
2. Claude Code remote control in a browser;
3. Claude Code remote control in the Claude mobile app.

Remote sessions run inside `tmux` under the `websvc` account. Assume the owner may be reading the session on a phone.

Therefore:

- keep output short and scannable;
- do not start long-running foreground processes inside the session;
- do not run interactive full-screen programs that need a real terminal;
- group related shell commands so the owner approves fewer prompts;
- never kill, rename or detach the owner's `tmux` session.

### 5.2 What the agent may do on the Mac Mini

The agent shares a machine with the runtime. Sharing a machine is not permission to operate it.

Proceed without asking:

- read repository files, runtime logs and the contents of `KAKI_DATA_ROOT`;
- run Tier A tests;
- run a read-only probe against an already-running service or an already-built index, such as scoring queries to calibrate a threshold;
- run a read-only script that the active unit owns.

Ask the owner first:

- installing or upgrading any package, binary, model or service;
- starting, stopping or restarting `whisper.cpp`, `mlx_lm.server` or the backend;
- writing to, re-seeding, re-ingesting or deleting anything under `KAKI_DATA_ROOT`;
- running a Tier B or Tier C owner procedure from the runbook;
- any command that changes the machine outside the worktree.

Report every read-only probe in the completion report, with the command and the numbers it produced. If a probe sets a threshold, a default or an acceptance expectation, the probe must be reproducible from a committed script. A number that exists only in a session transcript is not evidence.

Run Tier A tests with the `KAKI_*` mode switches cleared. A session started from the owner's `tmux` window inherits the live runtime exports (`KAKI_STT_MODE`, `KAKI_LLM_MODE`, `KAKI_TTS_MODE`, `KAKI_RETRIEVAL_MODE` and the service URLs), which sends canned tests to real services and produces failures that no code change can fix. Clear them before you conclude anything from a red Tier A run.

### 5.3 Validation ownership stays with the owner

The agent can now execute a Tier B command. It still does not own Tier B validation.

- The owner performs S and G ceremonies from the runbook.
- The agent never marks a runbook section `VERIFIED`.
- The agent never records owner evidence on the owner's behalf.
- Mac and Pi package, runtime, model and infrastructure preparation belongs in `wp-validation-runbook.md`, not in a session transcript.

Do not claim to have installed, configured or tested anything on the Raspberry Pi.

### 5.4 Worktrees and shared runtime data

Worktrees live on the Mac Mini. One `KAKI_DATA_ROOT` serves the machine, and the running services use it.

Two worktrees must not write to the same data root at the same time. If the active unit needs to write generated data, point `KAKI_DATA_ROOT` at a unit-scoped directory and document that in the runbook section.

---

## 6. Scope discipline

Implement only the named implementation unit.

Do not:

- pre-build a later unit merely because the next step is obvious;
- perform unrelated refactors;
- reformat unrelated files;
- rename unrelated files;
- introduce speculative adapters or placeholder modules;
- add a framework because it may be useful later;
- change a public contract to make implementation easier.

Create directories only when their first real implementation needs them.

If useful later work is discovered, record it as deferred work and continue with the active unit.

---

## 7. Architecture ownership

The Mac Mini does the thinking. Clients stay deliberately simple.

```text
backend/       FastAPI contract, orchestration, persistence and actions
services/      Replaceable STT, LLM and TTS implementations
rag/           Ingestion, provenance, retrieval and live lookup
agent/         DSPy behaviour/evaluation when the execution plan permits it
apps/web/      Simulator and protected test/evidence surfaces
device/        Thin Raspberry Pi client only
infra/         Host/network/deployment documentation and configuration
scripts/       Human-operated development and validation utilities
```

Application code depends on ports/interfaces rather than model-vendor APIs directly.

Never put model inference, retrieval, prompts, case decisions or business rules in `device/`.

Generated corpus snapshots, processed corpus data, Chroma data and SQLite runtime files live under `KAKI_DATA_ROOT`, outside the Git working tree. Small, deliberate, non-sensitive deterministic test fixtures/evidence may be committed when a test requires them.

---

## 8. Dependency handling

### Development dependencies

The agent may add project-local dependencies when the active unit needs them.

- Python dependencies belong in the repository-root `.venv` and the project dependency files.
- npm dependencies belong in the relevant `package.json` and lock file.
- Do not install Python packages globally.
- Do not use `--break-system-packages`.
- Do not run `brew` without owner approval. Homebrew changes the machine, not the worktree.

Report material dependency additions in the completion summary.

### Mac Mini and Pi runtime dependencies

The agent does not install them, even though it now runs on the Mac Mini.

Before code implementation depends on a new runtime package, binary, model, cache, environment variable or service, the active runbook section must document:

- machine and user;
- working directory;
- exact install command;
- exact verification command;
- model identifier and cache location where applicable;
- configuration/environment variables;
- start/readiness/stop commands where applicable;
- expected successful observation.

If the exact instruction is genuinely unresolved, mark it `BLOCKED - VERIFY BEFORE IMPLEMENTATION` rather than inventing a command.

---

## 9. Python style

Prefer clear Python over clever Python.

- Keep module-level configuration/constants together in a visible location.
- Declare local variables close to their first use.
- Use descriptive names.
- Keep functions cohesive and reasonably short.
- Prefer named functions over lambdas when they improve readability.
- A small lambda is acceptable when a named function would add more noise than clarity.
- Keep adapters small and testable.
- Keep side effects visible.
- Use typed models/contracts where the design defines structured data.
- Use British English in comments and docstrings.

Do not force all local variable declarations to the top of a function.

---

## 10. Python documentation contract

Every human-authored Python module must have a module docstring explaining its purpose and important constraints.

Every class must have a class docstring describing its responsibility.

Every public function and public method must have a useful docstring describing purpose and, where relevant:

- important arguments;
- return value;
- side effects;
- failure/exception behaviour;
- non-obvious constraints.

A trivial private helper may omit a docstring when its name and implementation are self-explanatory. Non-obvious private helpers must be documented.

Docstrings explain intent and behaviour. Do not restate the signature mechanically.

---

## 11. Human-operated script contract

A script intended for the owner to run manually is incomplete until its use is discoverable without reading source code.

For a Python CLI:

- provide `-h` and `--help`;
- use clear argument names and help text;
- validate required arguments;
- return non-zero on failure;
- avoid destructive defaults;
- document material side effects;
- include a module docstring explaining what the script does and when to use it.

If the script is part of an owner setup or test procedure, the active runbook section must contain at least one verified example command.

The worktree setup and cleanup helpers follow this contract.

---

## 12. Code change history

Where practical, maintain a top-of-file version history in human-authored code using comment syntax valid for that file type. This is a coding convention, not an acceptance gate.

Newest version first.

```python
# v1.3 | 06-Sep-2026 | Description of current change
# v1.2 | 05-Sep-2026 | Previous change
# v1.1 | 03-Sep-2026 | Earlier change
```

Use `DD-Mon-YYYY`.

Missing or imperfect change-history metadata must not block implementation, validation, commit, merge or CI.

Inline `#vX.Y` markers (and equivalents in other languages) are optional and must not be enforced as a gate. Existing markers may remain; do not mass-edit untouched code to add, remove or standardise them.

The agent must not create or maintain tooling whose sole purpose is enforcing change-history metadata. Do not introduce a replacement history checker, policy framework, pre-commit hook or equivalent enforcement mechanism for it.

Use equivalent valid comments in TypeScript/JavaScript/CSS/shell where applicable.

Do not add invalid comments to JSON, lock files, generated files, binaries or vendored files.


---

## 13. Prompting and DSPy

The KaKi-Talkie build order overrides generic prompting preferences.

Start with the simplest reliable implementation. Do not introduce DSPy before its planned execution-plan unit.

When the active unit reaches the DSPy migration, prefer DSPy signatures/modules over hand-built prompt strings unless the architecture is explicitly revised.

Do not pull MERaLiON, SEA-LION, OmniVoice or other challenger work into earlier baseline units.

---

## 14. Secrets, privacy and logging

Never commit credentials, tokens, private keys, service-account files, raw user audio by default, runtime databases or generated vector stores.

`.env.example` documents names using blank or safe example values.

Runtime logs go to the configured runtime/data/log location, not tracked source directories by default.

Do not log credentials, access tokens or volunteered authentication secrets.

If a user volunteers a password, OTP or authentication secret, do not intentionally persist it. Refusal depends on the requested action/context, not merely on a number pattern.

---

## 15. Git and test safeguards

### Git

- Do not commit or push unless explicitly instructed.
- Do not force-push.
- Do not rewrite published history.
- Do not run `git reset --hard`, `git clean`, broad restore/checkout or branch deletion unless explicitly instructed.
- Do not discard uncommitted user work.
- Inspect an existing file before editing it.
- Prefer targeted edits over replacing a complete file with a template.

### Tests

Tests are gates, not obstacles.

Do not delete, weaken, skip or rewrite an acceptance test merely to obtain a green run.

A Tier A test must not depend on the shell environment, on a running service, or on the state of the live `KAKI_DATA_ROOT`. Write Tier A tests so they set their own mode switches to canned defaults and use a temporary data root. A test that passes only because a service happens to be up has stopped being a test.

When an earlier test genuinely conflicts with an approved current requirement, report the mismatch and reconcile implementation + test together. This is not considered test weakening when the owner has explicitly changed the requirement.

A Tier B or Tier C test that the agent did not run is not a failure. Name the tests you skipped and say why. The owner runs them from the runbook.

---

## 16. Completion report

Keep completion reports short.

Report:

```text
Implemented:
Files changed:
Development dependencies:
Tests run/results:
Tests not run and why:
Runbook section/status:
Decisions or limitations:
Later scope untouched: yes/no
```

Under `Decisions or limitations`, name any read-only local probe you ran and the numbers it produced.

For S/G validation, point to the exact runbook section. Do not reproduce the procedure.

Report a file-plan deviation only when it is meaningful. Do not stop mid-implementation merely because one necessary helper/test file inside the approved ownership area was not predicted during preparation.
