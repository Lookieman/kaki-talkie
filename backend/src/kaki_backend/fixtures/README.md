# WP1 spoken test fixtures

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
