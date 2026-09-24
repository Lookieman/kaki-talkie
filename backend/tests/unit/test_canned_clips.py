# v1.0 | 24-Sep-2026 | WP6.8 voice revision: canned-reply clips with fallback to the wrapped port.
"""Prove canned replies play their clip and everything else reaches the wrapped port.

The wrapper must never let a clip speak words the screen does not show, and
must never make a missing or broken clip cost the turn its audio.
"""

import io
import unittest
import wave
from base64 import b64decode

from kaki_backend.actions.book_action import BOOKING_REPLIES
from kaki_backend.orchestration.canned_clips import (
    CannedClip,
    CannedClipTts,
    canned_clip_registry,
    is_playable_wav,
)
from kaki_backend.orchestration.intent_router import RefusalReason, refusal_message


def pcm_wav(seconds: float = 0.2, rate: int = 22050) -> bytes:
    """Return mono 16-bit PCM WAV silence."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(rate)
        recording.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


class RecordingTts:
    """Stand in for the say adapter and record how it was called."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def ready(self) -> bool:
        return True

    def synthesize(self, *args, **kwargs):
        self.calls.append(("synthesize", args, kwargs))
        return "data:audio/wav;base64,U0FZ"  # "SAY"


def build(clips: dict[str, bytes]) -> tuple[CannedClipTts, RecordingTts, io.StringIO]:
    """Wrap a recording port with the real registry and an in-memory clip store."""
    inner = RecordingTts()
    log = io.StringIO()
    tts = CannedClipTts(inner, clip_reader=clips.get, log_stream=log)
    return tts, inner, log


def decoded(data_url: str) -> bytes:
    return b64decode(data_url.split(",", 1)[1])


class CannedClipTests(unittest.TestCase):
    def test_exact_canned_reply_plays_its_clip(self):
        clip = pcm_wav()
        tts, inner, log = build({"booking_reply.en.wav": clip})
        audio = tts.synthesize(BOOKING_REPLIES["en"])
        self.assertEqual(decoded(audio), clip)
        self.assertEqual(inner.calls, [])
        self.assertIn("tts_source=clip message_id=booking_reply language=en", log.getvalue())

    def test_language_selects_the_matching_clip(self):
        english, malay = pcm_wav(0.1), pcm_wav(0.3)
        tts, _, _ = build({"no_coverage.en.wav": english, "no_coverage.ms.wav": malay})
        en_text = refusal_message(RefusalReason.NO_COVERAGE, "en").reply_text
        ms_text = refusal_message(RefusalReason.NO_COVERAGE, "ms").reply_text
        self.assertEqual(decoded(tts.synthesize(en_text)), english)
        self.assertEqual(decoded(tts.synthesize(ms_text, language="ms")), malay)

    def test_missing_clip_falls_back_to_the_wrapped_port(self):
        tts, inner, log = build({})
        self.assertEqual(tts.synthesize(BOOKING_REPLIES["en"]), "data:audio/wav;base64,U0FZ")
        # English keeps the pipeline's exact call shape: no language argument.
        self.assertEqual(inner.calls, [("synthesize", (BOOKING_REPLIES["en"],), {})])
        self.assertIn("tts_source=say language=en", log.getvalue())

    def test_invalid_clip_falls_back(self):
        for bad in (b"", b"not a wav", pcm_wav(0.0)):
            with self.subTest(bad=bad[:12]):
                tts, inner, _ = build({"booking_reply.en.wav": bad})
                tts.synthesize(BOOKING_REPLIES["en"])
                self.assertEqual(len(inner.calls), 1)

    def test_edited_copy_never_plays_a_stale_clip(self):
        tts, inner, _ = build({"booking_reply.en.wav": pcm_wav()})
        tts.synthesize(BOOKING_REPLIES["en"] + " Extra words.")
        self.assertEqual(len(inner.calls), 1)

    def test_live_answer_reaches_the_wrapped_port_with_its_language(self):
        tts, inner, log = build({"booking_reply.en.wav": pcm_wav()})
        tts.synthesize("Buka pautan SMS daripada CDC.", language="ms")
        self.assertEqual(
            inner.calls, [("synthesize", ("Buka pautan SMS daripada CDC.",), {"language": "ms"})]
        )
        self.assertNotIn("Buka", log.getvalue())  # reply text is never logged

    def test_fallback_source_names_the_wrapped_engine(self):
        log = io.StringIO()
        tts = CannedClipTts(
            RecordingTts(), fallback_source="canned", clip_reader=lambda name: None,
            log_stream=log,
        )
        tts.synthesize("anything")
        self.assertIn("tts_source=canned", log.getvalue())

    def test_readiness_is_the_wrapped_ports(self):
        tts, _, _ = build({})
        self.assertTrue(tts.ready())

    def test_registry_covers_every_canned_reply_once(self):
        registry = canned_clip_registry()
        filenames = [entry.filename for entry in registry]
        self.assertEqual(len(filenames), len(set(filenames)))
        for required in ("booking_reply.en.wav", "no_coverage.en.wav"):
            self.assertIn(required, filenames)
        self.assertIn(CannedClip("booking_reply", "en", BOOKING_REPLIES["en"]), registry)

    def test_packaged_clips_are_playable_when_present(self):
        # A committed clip must be valid PCM; an unrecorded one is allowed.
        from kaki_backend.orchestration.canned_clips import read_packaged_clip

        for entry in canned_clip_registry():
            audio = read_packaged_clip(entry.filename)
            if audio is not None:
                with self.subTest(clip=entry.filename):
                    self.assertTrue(is_playable_wav(audio))


if __name__ == "__main__":
    unittest.main()
