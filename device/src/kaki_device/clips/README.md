# Thinking-filler clips (WP6.8 voice revision)

The Pi plays these two clips while a turn is in flight
(`thinking_filler.py`). The owner records them with ElevenLabs, outside the
repository. The simulator plays the same two recordings from
`apps/web/public/`, under hyphenated names.

## Behaviour

1. The first clip plays once, as the thinking state starts.
2. The second clip plays once, only if the answer has not arrived
   `filler_second_delay_seconds` after the thinking state started. The
   default is 5 s.
3. The answer stops whichever clip is sounding. Neither clip plays after the
   answer starts.
4. A missing or invalid clip means silence for that stage. It never delays or
   fails the turn.

The device config flag `thinking_filler` (default `true`) switches both clips
on or off. Environment overrides are `KAKI_DEVICE_THINKING_FILLER=false` and
`KAKI_DEVICE_FILLER_SECOND_DELAY_SECONDS=5`.

## Clips

The exact text below is copied from `FIRST_CLIP_TEXT` and
`SECOND_CLIP_TEXT` in `thinking_filler.py`, which match `FILLER_TEXTS` in
`apps/web/src/simulator/filler.ts`. Record it word for word.

| Stage | Pi file (this folder) | Simulator file (`apps/web/public/`) | Exact text to record |
| --- | --- | --- | --- |
| 1 | `thinking_filler_1.en.wav` | `thinking-filler-1.wav` | Wait ah, I check for you. |
| 2 | `thinking_filler_2.en.wav` | `thinking-filler-2.wav` | Almost there ah, Auntie. Wait a bit more. |

Use PCM WAV at 22.05 kHz, 16-bit, mono, the format of the backend reply
audio. The Pi converts every sound to 48 kHz stereo before `aplay`, reading
the header, so the source rate is never assumed.

## Import a clip

If the ElevenLabs export is not already 22.05 kHz mono 16-bit WAV, convert it
on the Mac first:

```sh
afconvert -f WAVE -d LEI16@22050 -c 1 ~/Downloads/filler1.wav /tmp/thinking_filler_1.en.wav
```

Copy it to both destinations:

```sh
cp /tmp/thinking_filler_1.en.wav device/src/kaki_device/clips/thinking_filler_1.en.wav
cp /tmp/thinking_filler_1.en.wav apps/web/public/thinking-filler-1.wav
```

Verify that it is non-empty before committing:

```sh
python3 -c "import wave;w=wave.open('device/src/kaki_device/clips/thinking_filler_1.en.wav');print(w.getnframes()/w.getframerate(),'s')"
```

Expected: roughly 1.5 s for stage 1 and 2-3 s for stage 2. A 0.0 s file or
a `wave.Error` means the export is empty or not PCM WAV. The Pi installs the
device package in editable mode, so after pulling the new clips, restart the
kiosk service. The filler loads its clips once, at start-up.
