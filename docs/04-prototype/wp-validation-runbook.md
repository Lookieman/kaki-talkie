# KaKi-Talkie WP validation runbook

Version 1.19 | 13-Sep-2026 | SGLN Group 10

> This runbook now covers WP5 onward. The full record for WP1 to WP4,
> the environment model, the runbook states, the standard IU structure,
> the worktree lifecycle and the version summary block are archived in
> `wp-validation-runbook_old.md`. Section numbers are unchanged, so
> cross-references from `execution-plan.md` and from the archive still
> resolve. Sections 1 to 5 and 7 to 9 are intentionally absent.

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
# 10. WP5 - Singapore language

Status: **WP5.1 VERIFIED / CLOSED 14-Sep-2026. WP5.2 not started.**

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

Use the section structure standard in section 12 as the reference for
every WP5.x block the coding agent fills in during Prepare. The worked
example it describes is the WP3.4 block, archived in
`wp-validation-runbook_old.md` section 8.1.

#### WP5.1 setup - language policy and baseline Malay path

Owner level: **S**
Status: **VERIFIED / CLOSED 14-Sep-2026.** Gate evidence: runbook 10.2
WP5.1, "WP5.1 gate result". Validated on the uncommitted working tree
over base commit `5ad7f74`; record the WP5.1 commit hash in that section
when it is made. Compress this block under the section 12 rule after the
commit, so the full prepared text reaches Git history first.

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
- returns a different multiset of ASCII digit sequences from the English
  reply, so a changed, added or dropped number, step number or date
  (`fallback_numbers`);
- returns text whose length differs from the English reply by more than
  `RENDER_LENGTH_TOLERANCE` (0.5) of the English length
  (`fallback_length`).

**English answer guard.** The slip is composed from the first call's
answer, so that answer must be English. Test 3 on 14-Sep-2026 showed Qwen
answering "Bagaimana saya boleh guna baucah CDC saya?" in Malay despite
the prompt, which put Malay steps on the slip. The grounded prompt now
says to answer in English whatever the question's language. The pipeline
also checks the answer with `language_policy.is_english_text`. If the
answer is not English and a normalised English query exists, it asks
once more with that query against the same evidence. If the answer is
still not English, the answer is spoken and displayed, and the slip
prints its heading, `Source:`, `Source checked:` and ask-again lines with
no steps. Malay steps never reach the slip.

The render checks run in the order listed above and the first failure
is recorded. A
successful render records `rendered`. A fallback never fails the turn.
The render prompt tells the model to keep every number, date and step
number in digits, so a correct render passes the digit check.

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

- **Answered, any language:** the slip body is English, built from the
  English grounded answer: heading, steps, `Source:`, `Source checked:`
  and the ask-again line. The render never touches it, and a grounded
  answer that stays non-English after its retry leaves the steps out. It carries no transcript and has no
  `You asked:` line, so no Malay text belongs anywhere on it.
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
and drops anything above U+00FF, such as CJK. WP6.3 confirms the code
page on the real Xprinter.

**Hollow question guard.** If the cut would remove more than
`MAX_QUESTION_CHARACTERS_REMOVED` (a quarter) of the referral question's
visible characters, the slip omits the `You asked:` line and the
question. A Chinese question therefore prints the heading and referral
line only, never "You asked:" above blank space or stray fragments.
Folded quotes and dashes count as kept. The rest of the slip is built as
before.

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
| Macam mana saya boleh guna baucar CDC saya?  | 0.466    | 0.772    | 0.759       |
| Baucar CDC tu boleh guna kat mana?           | 0.427    | 0.727    | 0.685       |
| Saya nak tahu cara tuntut baucar CDC untuk   | 0.446    | 0.806    | 0.798       |
| isi rumah saya.                              |          |          |             |
+----------------------------------------------+----------+----------+-------------+
```

Measured on the Mac on 14-Sep-2026 against the live index: Test 2
(`evidence.mYtqUP`) and `wp_check.py --unit WP5.1` in Test 5
(`evidence.xw0BAj`) returned identical values. The 13-Sep-2026 in-memory
probe read within 0.003 of the first two columns. The Qwen rewrites were
"How can I use my CDC voucher?", "Where can CDC Vouchers be used in
Singapore?" and "How to claim CDC Voucher for my household?", in
408-479 ms.

The Qwen rewrite clears the 0.50 gate by 0.185-0.298, so no value sits
within the 0.10 near-gate margin and no owner decision was needed. It
scores 0.008-0.042 below the hand-written queries.

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
| render_outcome  | rendered, fallback_empty, fallback_numbers,              |
|                 | fallback_length, fallback_error, or null when no render  |
|                 | ran                                                      |
| rewrite_present | true when the turn had a normalised English query        |
| rewrite_ms      | Rewrite duration (timings query_rewrite_ms) or null      |
+-----------------+----------------------------------------------------------+
```

The first three are stored by migration 0003 (`reply_language`,
`reply_mode`, `render_outcome`, all nullable and constrained). The last
two derive from existing columns. Rows written before 0003 read null.
Rollback: with the backend stopped and a backup taken, drop the three
columns in reverse order and set `PRAGMA user_version = 2`.

Migration 0003 gained `fallback_numbers` in its constraint on 14-Sep-2026,
before release. No database had applied it: the live database read
`user_version` 2 that day. If you started a backend from the 13-Sep-2026
uncommitted build, roll that database back as above before starting this
build.

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
- `services/llm/qwen_local` grounded prompt: answer in English whatever
  the question's language. This prompt serves every grounded turn, so
  Test 5's golden paths cover the English path.
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
- `wp_check.py` also changes two schema-version checks. WP4.2
  `live_database_at_packaged_schema_version` and WP4.5
  `backup_schema_version_matches_packaged` now require the version to
  equal the packaged migration count, the same derivation as
  `wp4_5_evidence.sh`. These change earlier units' code paths in WP4, a
  different package, so no tier B rerun follows.
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
- two Malay CDC transcripts through `TurnPipeline` with live Qwen and a
  disposable database: the probe question, and the exact Whisper
  transcript that produced a Malay slip in Test 3. Each must be
  `answered`, cite CDC, have a rewrite, policy `ms` and `language` per
  mode. Its slip body must have steps, be English and have no
  `You asked:` line. In `full` mode `render_outcome` must be `rendered`.

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
  backup test, and WP4.5 did in its harness. The WP4.2 migration tests
  now build the WP4.2 schema in isolation (migrations 0001-0002) where
  the exact version 2 matters. Everywhere else the expected version is
  the count of packaged `NNNN_*.sql` files, counted from disk rather than
  from the loader under test. A later migration raises the expectation
  only when its file ships; a file the loader skips or fails to apply
  fails the check. What
  each test proves about migration 0002 is unchanged (X-AT-04). The
  archived WP4.2 and WP4.5 test blocks still say "schema version 2";
  read that as "the packaged version".
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
  receives `ms`. Empty, altered-number, length-mismatched and failed
  renders give the English reply with the matching `render_outcome`; a
  render that changes "31 December" to "13 Disember" records
  `fallback_numbers`. `bridge` wraps the
  English reply and speaks three segments; `english` replies in English.
  A Malay refusal uses the `ms` catalogue and keeps `You asked:`. A
  question that loses more than a quarter of its characters to the
  Latin-1 cut drops the line. Every slip is Latin-1. The diagnostics survive storage. An English
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
  starts `KAKI-TALKIE HELP` and carries `Source checked:`. Its body, the
  lines between the heading and `Source:`, is English whatever the reply
  language: the harness reports "Malay words found = none" and saves the
  body as `ms_cdc_slip_body.txt`. It has no `You asked:` line; only the
  referral slip carries the transcript. The harness also records the
  body's line count; 0 means the grounded answer stayed non-English after
  its retry. `full`: `render_outcome`
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
for `bridge` or `english`, plus 1 when the English answer guard asked
again. Also the count of `lah`, `leh` and `lor` in
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
| 14-Sep-2026 | full    | yes             | Amira enhanced     | evidence.xw0BAj  |
+-------------+---------+-----------------+--------------------+------------------+
```

The owner selected `full`, the configured default, so WP5-AT-01 passes in
its full form. `bridge` and `english` were not rehearsed; they remain
demo-day insurance.

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
- **Answered slip body is Malay, or has no steps:** the grounded model
  answered in Malay. A Malay body means the backend runs a build without
  the English answer guard; restart it from the current checkout. No
  steps means the retry with the normalised query also came back
  non-English; check that `normalised_query` is English and record the
  turn.
- **`render_outcome` is `fallback_numbers`:** the render changed, dropped
  or spelled out a number, step number or date. The rejected render is
  not stored; the turn's `reply_text` is the English reply. Rerun the
  turn, and if it repeats, record it for the reply mode decision.
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
- The render check covers emptiness, digit sequences and length. It
  catches a changed figure or dropped date, but not a changed word, a
  swapped scheme name or a number written out in Malay words; the owner
  judges the wording in Test 3.
- Malay CDC questions depend on the normalised-query rewrite. A rewrite
  that exceeds `KAKI_QUERY_REWRITE_TIMEOUT_SECONDS` still refuses a
  question the corpus covers; the debug view now shows it.
- The language rules use closed word lists. Unseen phrasing can fall
  through to the preference.
- Failed turns stay English.
- The English answer guard uses the same closed word lists. A Malay
  answer with few listed words can pass as English; the Malay marker
  checks on the slip body are the second line of defence.
- `llm_ms` covers both the answer and the render call.
- Chinese and other languages reply in the preference language, and
  their referral slip omits the question. Hokkien is a
  stretch goal beyond the MVP.
- **Slip step parser drops text before a year (WP3.3 defect, found in
  Test 3).** `slip.extract_steps` reads a number followed by ". " as a
  numbered-step marker. In "The vouchers are valid until 31 December
  2027. Ensure you keep your voucher link safe…", it treats "2027." as
  step marker and keeps only the text after it. The 14-Sep-2026
  `ms_cdc` slip therefore printed one step and lost the main instruction
  and the validity date. The slip stays English and within 40 words, so
  WP5.1 acceptance holds. The defect predates WP5.1 and affects English
  turns too. It is recorded for an owner decision on when to fix it,
  before the WP6 printer work at the latest.
- WP5.1 was validated on the uncommitted working tree, not on a commit.

##### WP5.1 gate result

Owner level S, closed 14-Sep-2026 on the Mac as `websvc`. Base commit
`5ad7f74` with the WP5.1 changes uncommitted. WP5.1 commit: record here.

The evidence spans two harness runs. Each covers tests on the final
build or re-proves them there:

```text
+------+----------------------+-------------------+-----------------------------------+
| Test | Run                  | Result            | Final-build cover                 |
+------+----------------------+-------------------+-----------------------------------+
| 1    | evidence.mYtqUP      | Suites passed;    | Test 5 reran all unit suites on   |
|      | 14-Sep 17:42         | Malay strings yes | the final build (206 passed). The |
|      |                      |                   | Malay fixed strings are unchanged |
|      |                      |                   | since the verdict.                |
| 2    | evidence.mYtqUP      | All probe checks  | wp_check WP5.1 in Test 5 repeated |
|      |                      | passed            | the probe with identical values.  |
| 3    | evidence.xw0BAj      | All checks        | Final build.                      |
|      | 14-Sep 21:43         | passed; 4 yes     |                                   |
|      | (--from-test 3)      | verdicts          |                                   |
| 4    | -                    | WP5.2, not run    | -                                 |
| 5    | evidence.xw0BAj      | All checks passed | Final build.                      |
+------+----------------------+-------------------+-----------------------------------+
```

The three earlier Test 3 runs (`evidence.mYtqUP`, `evidence.HPXIb7`,
`evidence.FBflc9`) failed on the `ms_cdc` slip body: Qwen answered the
Malay question in Malay and the slip printed Malay steps. The English
answer guard (10.1, "Reply modes") fixed it. In the passing run the
first grounded call answered in English, with 3 completions and no
retry. Keep all four directories.

Acceptance:

```text
+-----------+-------------------------------------------+--------------------------------------+
| Criterion | Requirement                               | Evidence                             |
+-----------+-------------------------------------------+--------------------------------------+
| WP5-AT-01 | Curated Malay -> Malay reply/display +    | Test 1 suites; Test 3 ms_cdc and     |
|           | English slip                              | ms_codeswitch in full mode: language |
|           |                                           | ms, render rendered, slip body       |
|           |                                           | English; Q1 yes                      |
| WP5-AT-02 | Curated code-switch cases match expected  | 17 cases in language_cases.jsonl;    |
|           | response language                         | Test 3 ms_codeswitch ms, en_sg_cdc en|
| WP5-AT-03 | SG English natural, not exaggerated       | Test 3 Q3 yes; en_sg_cdc particle    |
|           |                                           | count 0                              |
| WP5-AT-04 | Malay CDC utterance retrieves CDC in top 3| Test 2 and wp_check: top 3 all CDC,  |
|           |                                           | Qwen gate 0.685-0.798; Test 3 ms_cdc |
|           |                                           | cites cdc-vouchers-residents         |
| WP5-AT-12 | Golden paths + earlier contracts green    | Test 5: devset 25 items, intent 1.00,|
|           |                                           | golden paths 6 of 6; suites green;   |
|           |                                           | X-AT-01 and X-AT-03 held             |
+-----------+-------------------------------------------+--------------------------------------+
```

Test 3 observations, `evidence.xw0BAj`:

```text
+----------------+--------------------------------------+-------+-----------+---------+-------+
| File           | Transcript (Whisper)                 | Lang  | State     | Rewrite | Turn  |
+----------------+--------------------------------------+-------+-----------+---------+-------+
| ms_cdc         | Bagaimana saya boleh guna baucah     | ms    | answered  | 560 ms  | 7.5 s |
|                | CDC saya?                            |       |           |         |       |
| ms_codeswitch  | Care Shield Life itu apa? Kena bayar | ms    | answered  | 551 ms  | 5.9 s |
|                | premium setiap tahunkah?             |       |           |         |       |
| en_sg_cdc      | CDC voucher how to use that? Can you | en    | answered  | 497 ms  | 6.8 s |
|                | use it at the Hawker Centre or not?  |       |           |         |       |
| ms_unsupported | Esok, cuaca macam mana ada huja tak? | ms    | refused   | 515 ms  | 2.3 s |
+----------------+--------------------------------------+-------+-----------+---------+-------+
```

- Malay answers took 3.6-5.1 s of `llm_ms` for the answer plus render,
  against 2.0 s for the English answer.
- The `ms_unsupported` referral slip printed "You asked:" with the Malay
  transcript verbatim.
- The re-recorded `ms_codeswitch` (18:08) and `ms_unsupported` (18:18)
  clips transcribed cleanly. Whisper labelled `ms_unsupported` Malay at
  probability 0.45.
- The transcript holds three "FAIL: command exited non-zero" lines, at
  the two `You asked:` checks and the particle count. They are the ERR
  trap reporting an intended non-zero `grep` inside a check. The run did
  not stop, and each belonging check reads "check ok". The other three
  FAIL lines are expected output from the scripts suite's negative tests.

Test 5, `evidence.xw0BAj`: `wp_check.py --unit WP5.1 --tier B` exit 0,
including both text turns (probe and live Whisper transcript) with
English slip bodies and the Amira voice (85,897 frames). ruff clean;
contract 40, unit 206, rag 69, scripts 73, all passed. The `$KAKI_DB`
turns count stayed at 77 across the suites.

Owner completed Tests 1, 2, 3 and 5 on the Mac; block VERIFIED and WP5.1
CLOSED 14-Sep-2026. `execution-plan.md` 10 "Current execution point"
moves to WP5.2 at the owner's next plan update.

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

Use the section structure standard in section 12 for every WP6.x section
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

The WP3.4 block, archived in `wp-validation-runbook_old.md` section 8.1,
is the reference for how a completed runbook section should read. When writing or updating a section during
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
