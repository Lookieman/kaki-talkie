# Spoken test fixtures

## WP3 spoken question fixtures

Captured on the Mac Mini with macOS `say`, voice Samantha, PCM WAV at 16 kHz,
16-bit, mono (capture commands: runbook 8.1 WP3.3 and 8.1 WP3.4). They are
committed once and never regenerated, because `say` output changes across
macOS versions and the checks compare behaviour, not audio.

| File | Exact spoken text | Used by |
| --- | --- | --- |
| `cdc_question.wav` | How do I use my CDC vouchers? | GP1, WP3.3/WP3.4 tier B, grounded latency |
| `singpass_question.wav` | How do I reset my Singpass password? | GP2, WP3.4 tier B |
| `unsupported_question.wav` | What is the weather forecast for tomorrow? | GP3, WP3.4 tier B |

GP4, the credential-action refusal, needs no spoken fixture: it is proven over
the text path by the `credential-action` devset item in
`scripts/run_regression.py`. The earlier credential-request fixture was
dropped with secret redaction (design.md 8, owner decision 12-Sep-2026).

In the grounded configuration (`KAKI_RETRIEVAL_MODE=rag`) the WP2.4 full-loop
check speaks `cdc_question.wav` rather than `canned_reply.wav`: the canned
transcript scores below the WP3.4 evidence gate and is correctly refused, so
it can no longer stand in for a supported question there.

## WP1 spoken test fixtures

These are prerecorded, synthetic English speech fixtures, produced on 05-Sep-2026
with the installed Windows System.Speech engine, Microsoft David Desktop voice,
default rate/volume, and PCM WAV output at 16 kHz, 16-bit, mono.
No user audio, credentials, official-source material, or retrieved information is included.

| File | Exact spoken text |
| --- | --- |
| `canned_reply.wav` | This is a KaKi-Talkie test reply. Your audio has not been interpreted. |
| `empty_audio.wav` | No audio was received. Please try recording again. |

The operating-system speech engine was used once to create these assets. It is
not an application dependency, is not run in CI, and is never invoked by the backend.
WP2's macOS `say` baseline is unchanged and has not been implemented here.

The backend packages these WAVs and encodes their bytes into the existing
`reply_audio` field as `data:audio/wav;base64,...`. There is no added audio endpoint.
Only the exact successful canned wording is supported by `CannedTtsPort`; it does
not pretend that the same recording can speak arbitrary generated text.
The zero-byte failure path reads its fixed fixture directly, leaving uninvoked
model-stage timings null as required by the earlier gate.

The receipt's `Source: canned test fixture` and `Source checked: 05-Sep-2026
(fixture date)` describe this fixed test scenario. They are not official provenance
or a claim that retrieval/source checking occurred. The API's `sources` remains empty.

Automated checks validate decodable PCM, duration, nonzero samples, and packaged
asset identity. The owner must still listen to both fixtures during the manual gate.
