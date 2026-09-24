# Canned-reply clips (WP6.8 voice revision)

These are pre-rendered recordings of the backend's fixed replies. The owner
records them with ElevenLabs, outside the repository. The backend reads them
through `CannedClipTts` (`orchestration/canned_clips.py`), which wraps the
configured TTS port. ElevenLabs is not a runtime dependency, and no API key
belongs in this repository.

## How a clip is chosen

A clip plays only when the reply text matches its registry entry exactly.
Anything else falls back to the configured engine (`say` in the live
configuration). The fallback covers a missing file, an invalid WAV, a live
answer, and copy edited after the clip was recorded. A stale clip therefore
never speaks words the screen does not show: re-record it after any wording
change.

Each `synthesize` call writes one line to the backend's stderr:
`tts_source=clip message_id=<id> language=<lang>` or
`tts_source=say language=<lang>`. Reply text is never logged.

## Naming and format

Name each file `<message_id>.<language>.wav`. The IDs are `booking_reply`
and the `RefusalReason` and `ActionMessageKind` values. The registry
(`canned_clip_registry()`) lists every entry. An entry with no file uses
`say`.

Use PCM WAV at 22.05 kHz, 16-bit, mono. That matches the `say` reply audio
and the push fixtures. The Pi and the browser read the header, so a
different rate still plays, but keep one format.

## Clips in scope for the pitch

The exact text is copied from the code. Record it word for word. Speak the
acronyms `CDC` and `CHAS` as letters, which is how the `say` path voices them.

| File | Exact text to record | Source of the text |
| --- | --- | --- |
| `booking_reply.en.wav` | Okay Auntie, done already! I book for you. Go to the main office on level 1 to collect your vouchers, can? Your receipt is on the screen. | `actions/book_action.py` `BOOKING_REPLIES["en"]` |
| `no_coverage.en.wav` | Aiyo, sorry Auntie, this one I cannot find leh. I can help with Singpass, CDC Vouchers, CHAS and CareShield Life. For other things, you go ask the community centre staff, they sure can help you. | `orchestration/intent_router.py` `REFUSAL_MESSAGES["en"][NO_COVERAGE]` |

The push clip is not in this folder. `push_cdc_en.wav` overwrites the
existing fixture at `backend/src/kaki_backend/fixtures/push_cdc_en.wav`,
because the `pending_messages` row names that file. Its text is
`Good news: new CDC vouchers are available. Press the button to ask me about
them.` (migration `0004_admin_surface.sql` and
`scripts/seed_push_message.py` `BODY_EN`).

## Import a clip

If the ElevenLabs export is not already 22.05 kHz mono 16-bit WAV, convert it
on the Mac first:

```sh
afconvert -f WAVE -d LEI16@22050 -c 1 ~/Downloads/booking_reply.wav /tmp/booking_reply.en.wav
```

Copy it into place:

```sh
cp /tmp/booking_reply.en.wav backend/src/kaki_backend/clips/booking_reply.en.wav
```

Verify that it is non-empty before committing:

```sh
python3 -c "import wave;w=wave.open('backend/src/kaki_backend/clips/booking_reply.en.wav');print(w.getnframes()/w.getframerate(),'s')"
```

Expected: a duration of a few seconds. A 0.0 s file or a `wave.Error` means
the export is empty or not PCM WAV. Clips are read on each turn, so no
restart is needed. Ask for a booking. The stderr line should read
`tts_source=clip message_id=booking_reply language=en`.
