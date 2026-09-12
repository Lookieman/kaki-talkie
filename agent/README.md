# agent/ - behaviour development data

Version 1.1 | 12-Sep-2026 | SGLN Group 10

This directory holds **data only**. There is no `agent/src`, no
`pyproject.toml` and no DSPy dependency anywhere in the repository yet.
`AGENTS.md` 13 and `design.md` 11 place DSPy at its own execution-plan unit
(WP5.5); creating the package before then would be the speculative scaffolding
`AGENTS.md` 6 forbids.

## `data/devset.jsonl`

The WP3.4 regression set (WP3-AT-11), grown from the representative utterances
`design.md` 12.2 asks for. One JSON object per line, deliberately flat: a
single input field plus explicit expected fields, so the WP5.5 DSPy migration
is a loader change rather than a rewrite.

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier, used in reports |
| `utterance` | The only input: what the user says |
| `expected_intent` | `answer` or `refuse` |
| `expected_state` | Expected public turn state |
| `expected_source_id` | Allowlisted source the answer must cite, or null |
| `expected_refusal_reason` | `no_coverage`, `credential_action` or null |
| `golden_path` | `GP1`-`GP5` where the item is a golden path, else null |
| `language` | Language label, for reading the report |
| `note` | Why the item is in the set |

Fourteen items: eight supported questions across English, Singlish, Malay,
Chinese and code-switched phrasings, five no-coverage refusals, and one
credential action.

Run it with `scripts/run_regression.py` (runbook 8.2 WP3.4 Test 4). The runner
drives the real turn pipeline over the text path, so it measures routing, the
evidence gate, grounding and attribution without speech-recognition variance.

### Growing the set

Add an utterance whenever a real failure is found, which is what `design.md`
12.2 intends. Do not change an expected label to make a run green: a failing
item is evidence. Labels change only when the owner has explicitly changed the
requirement.

Print and repeat utterances join the set at WP4.2, when those intents exist.
They are absent rather than expected-to-fail, so the accuracy figure stays
meaningful.

## Not here

Raw or user audio, real credentials, and anything derived from a real person's
speech. The one secret-shaped string in the set is synthetic and belongs to
nobody. The system does not redact volunteered credentials (design.md 8), so
that string travels through the pipeline like any other text when the set runs.
