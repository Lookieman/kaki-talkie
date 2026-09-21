# Simulator public assets

## `thinking-filler.wav` (WP6.8)

The canned "Wait ah" line the simulator plays once while a grounded turn is
in flight. It is a committed asset, captured once on the Mac Mini and never
regenerated, following the spoken-fixture convention in
`backend/src/kaki_backend/fixtures/README.md`.

| Property | Value |
| --- | --- |
| Exact spoken text | `Wait ah, I check for you.` |
| Voice | Jamie (Enhanced), `en_GB` |
| Rate | 150 wpm |
| Format | PCM WAV, 22.05 kHz, 16-bit, mono |

Capture command, run once by the owner in a logged-in GUI session (Enhanced
voices produce a zero-length file outside one):

```bash
say -v Jamie -r 150 -o apps/web/public/thinking-filler.wav \
    --data-format=LEI16@22050 "Wait ah, I check for you."
```

Verify it is non-empty before committing:

```bash
python3 -c "import wave;w=wave.open('apps/web/public/thinking-filler.wav');print(w.getnframes()/w.getframerate(),'s')"
```

Expected: roughly 1.5 seconds. A 0.0 s file means `say` could not reach the
speech service; re-run it from a Terminal window in the desktop session.

The wording is provisional and is the owner's to change: re-run the capture
with new words and update the table above. The simulator plays whatever is
committed here, once per turn, never looped (`src/simulator/filler.ts`).
