# Simulator public assets

## Thinking-filler clips (WP6.8 voice revision)

The simulator plays two canned lines while a grounded turn is in flight
(`src/simulator/filler.ts`):

1. `thinking-filler-1.wav` plays once, as the thinking state starts.
2. `thinking-filler-2.wav` plays once, only if the answer has not arrived
   5 s later.

The answer stops whichever clip is sounding, and neither clip plays after the
answer starts. A missing clip means silence, never a failed turn.

The owner records the clips with ElevenLabs. The Pi plays the same recordings
from `device/src/kaki_device/clips/`, under underscore names. That folder's
`README.md` holds the full import steps.

The table below lists the exact text, copied from `FILLER_TEXTS` in
`src/simulator/filler.ts`, and the format.

| File | Exact spoken text | Format |
| --- | --- | --- |
| `thinking-filler-1.wav` | `Wait ah, I check for you.` | PCM WAV, 22.05 kHz, 16-bit, mono |
| `thinking-filler-2.wav` | `Almost there ah, Auntie. Wait a bit more.` | PCM WAV, 22.05 kHz, 16-bit, mono |

Copy each clip into place, then verify that it is non-empty before
committing:

```bash
cp /tmp/thinking_filler_1.en.wav apps/web/public/thinking-filler-1.wav
python3 -c "import wave;w=wave.open('apps/web/public/thinking-filler-1.wav');print(w.getnframes()/w.getframerate(),'s')"
```

Expected: roughly 1.5 s for the first clip and 2-3 s for the second. A 0.0 s
file means the export is empty.

The wording is the owner's to change. If it changes, update `FILLER_TEXTS`
and the Pi's `FIRST_CLIP_TEXT` and `SECOND_CLIP_TEXT` together, then
re-record both copies.
