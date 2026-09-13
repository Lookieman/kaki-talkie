# ADR 0008: MVP backup, retention and presenter controls

Date: 13-Sep-2026

Status: accepted for WP4.5 by owner decision, 13-Sep-2026, covering decisions
2 and 3 and the index copy. Decision 1 was accepted, then withdrawn on
13-Sep-2026. Operational steps live in runbook 9.1 and 9.2 WP4.5; this record
keeps the evidence and the reasons.

## Context

WP4.1 made SQLite the turn record (ADR-0007) and WP4.2 added actions that
read it. WP4.5 must prove the backup restores (`setup.md` 20.3), take a
position on growth before the 25-Sep-2026 pitch, and settle the "presenter
controls" that `execution-plan.md` 5 named without defining.

## Decision 1: presenter controls - Withdrawn

Status: withdrawn by owner decision, 13-Sep-2026. WP4.5 builds no presenter
controls. The simulator keeps a fresh `session_id` per page load and starts
with the `auto` print policy. The Pi sets its own session boundary in WP6.

**Reason for withdrawal.** A reload starting a new session is acceptable
behaviour for the 25-Sep-2026 pitch. The New session button only had value
because persistence existed, so both go. Owner Test 3 step 2 failed on
13-Sep-2026 with `previous_turn_id: null`, and the fix is not worth the owner
time to re-validate this close to the pitch.

**History.** Execution plan v1.0 (commit `8fc64e0`, 02-Sep-2026) defined
presenter controls as: trigger a nudge, move case time to the next day, and
select a canned scenario in the simulator. The v1.7 withdrawals removed
pending delivery state and the `cases` table, so the first two controls had
nothing to act on. Canned-scenario selection belongs to WP6-AT-11 at WP6.5,
and `AGENTS.md` 6 forbids building it early. The name therefore had no
buildable content, and the scope needed an owner decision.

**Rejected alternative: session controls in browser storage.** The accepted
and then withdrawn design kept `session_id` and the print policy in browser
storage, with a New session button that started a new `session_id`, cleared
the receipt and kept the policy. It changed nothing in the backend or the
device contract. The analysis, kept so it need not be repeated:

- WP4.2 left "previous" tied to the page. A reload started a new session, so
  "Can you repeat that?" answered "I have not answered a question yet", and
  the policy fell back to `auto`. A closed tab or a browser crash does the
  same.
- `sessionStorage` survives a reload only. `localStorage` survives a reload,
  a closed tab and a browser crash, so it was the chosen store.
- The cost of `localStorage`: two tabs on one browser profile share one
  session, and a rehearsal session persists until someone presses New
  session.
- A blocked store needs a page-memory fallback.

## Decision 2: manual backup set, index copied

`scripts/backup_sqlite.sh` runs by hand and never deletes. Each set holds
the database (`sqlite3 .backup`, WAL-safe while the backend runs), `corpus/`,
`chroma/` and a manifest. No `launchd` schedule in the MVP.

The set copies `chroma/` instead of rebuilding it at restore. The copied
index is the restore source of truth for retrieval. Rebuilding needs the
embedding model and time, and `index_corpus.py` stays the fallback. A copy
taken during an ingest could be inconsistent, so the manifest records whether
`pgrep -f` found `index_corpus.py` or `ingest_corpus.py`. The restore test's
grounded question proves the index survived.

## Decision 3: keep every turn through the pitch

- Keep every turn until after the pitch. The MVP builds no pruning code.
- A repeat keeps its own copy of the reply audio.
- Sessions with a person other than the owner are tagged and deleted whole
  on request. This rule is in force now.

**Reason for no pruning.** Rehearsal volume through 25-Sep-2026 stays in the
hundreds of turns, under 1 GB. Pruning code would add a delete path, a
foreign-key ordering problem and tests, with no pitch benefit.

**Reason for the third-party rule.** Ergonomics testing with an older adult
happens before the pitch, and audience members may speak on 25-Sep-2026.
Their transcripts are personal data now, so the rule cannot wait for a pilot.
Reloading the simulator page before and after their turns starts a new
session each time, so the deletion unit is a whole session.
`scripts/delete_session.py` performs the deletion.

## Evidence: the 13-Sep-2026 storage probe

A copy of the live database, taken on 13-Sep-2026, held 44 turns in 15
sessions. The file was 31.4 MB; `reply_audio` was 29.7 MB of it (95%).

```text
+------------------------------------+------+-------------------+----------------+
| Turn kind                          | Rows | reply_audio mean  | Other columns  |
+------------------------------------+------+-------------------+----------------+
| answered (grounded)                | 19   | 909 KB (max 921)  | 1.6 KB         |
| refused                            | 3    | 519 KB            | 1.3 KB         |
| repeat_previous, resolved          | 12   | 888 KB (a copy)   | 0.7 KB         |
| repeat_previous, nothing to act on | 4    | 148 KB            | 0.4 KB         |
| print_previous                     | 5    | 44 KB             | 0.6 KB         |
| failed                             | 1    | 147 KB            | 0.3 KB         |
+------------------------------------+------+-------------------+----------------+
```

**Growth rate.** About 0.9 MB per grounded answer and 0.9 MB per repeat. An
answer, repeat and print together add 1.8 MB. One hundred answers add about
90 MB; one thousand add about 0.9 GB. Each backup set adds another full copy.

**Correction to ADR-0007.** WP4.1 estimated 70-180 KB per turn from the
committed canned fixtures. The `say` adapter writes 16-bit mono PCM at
22,050 Hz (`LEI16@22050`), 44.1 KB per second of speech, and a grounded reply
runs about 20 seconds. The WP4.2 probe of nine turns measured 806 KB mean and
944 KB maximum; the 44-turn probe above supersedes both.

## Alternative rejected: a pointer instead of a copied BLOB

A repeat could store no audio and follow `previous_turn_id` when read.

```text
+------------------+-----------------------------------+-----------------------------------+
| Aspect           | Copied BLOB (kept)                | Pointer via previous_turn_id      |
+------------------+-----------------------------------+-----------------------------------+
| Storage          | +0.9 MB per repeat                | About 0 per repeat                |
| Replay read      | One row                           | Two rows; a new repository read   |
|                  |                                   | path                              |
| Pruning          | Each action row replays alone     | Removing an answer breaks every   |
|                  |                                   | repeat that points at it          |
| Evidence         | WP4-AT-04 hashes the action row   | WP4.2 checks need rework          |
| Migration        | None                              | None (column exists)              |
+------------------+-----------------------------------+-----------------------------------+
```

On 13-Sep-2026 no read path uses `previous_turn_id` for behaviour. The
repository copies it into the turn log; the debug view, `run_regression.py`,
`wp_check.py` and `wp4_2_evidence.sh` read it for checks. Resolution picks
the newest answered or refused turn in the session.

The saving is 0.9 MB per repeat, and repeats are rare outside test runs.
That does not pay for a second read path and weaker replay evidence.

## Consequences

- `previous_turn_id` references `turns` with no `ON DELETE` rule, and every
  connection sets `foreign_keys=ON`. Deleting an answer that an action turn
  references fails. Any deletion, pruning or third-party request included,
  removes a whole session, or its action turns before their answers.
- A backup set holds every transcript. Deleting a third-party session also
  means removing each backup set that holds it and taking a fresh one.
- The backup set shares the SSD with the database. It covers corruption and
  operator error, not disk loss.
- Lowering the TTS sample rate would shrink every row. It changes reply
  bytes and the audio pipeline, so it needs its own decision.
- After the pitch, any use with real users needs an age-based retention
  rule, decided by the owner.
