# v1.0 | 09-Sep-2026 | Cover speech wiring, text-only degrade and debug transcript logging.

"""Pipeline-level TTS behaviour: speech passes through, failures never lose the answer."""

import io
import unittest
import wave
from time import perf_counter

from kaki_backend.contracts.ports import TtsError
from kaki_backend.orchestration.turn_pipeline import TurnPipeline


def synthetic_audio() -> bytes:
    audio_buffer = io.BytesIO()
    with wave.open(audio_buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return audio_buffer.getvalue()


class FakeTts:
    """Return a fixed audio reference for any reply text."""

    def ready(self) -> bool:
        return True

    def synthesize(self, reply_text: str) -> str | None:
        self.spoken_text = reply_text
        return "data:audio/wav;base64,QUJD"


class FailingTts:
    """Raise a sanitised synthesis failure for every reply."""

    def ready(self) -> bool:
        return False

    def synthesize(self, reply_text: str) -> str | None:
        raise TtsError("timeout")


def execute(pipeline: TurnPipeline):
    return pipeline.execute(
        device_id="tts-test", session_id="tts-test", turn_id="tts-test-turn",
        audio=synthetic_audio(), audio_preparation_ms=0.0,
        request_started_at=perf_counter(),
    )


class TtsPipelineTests(unittest.TestCase):
    def test_generated_reply_is_spoken_and_displayed(self) -> None:
        speech = FakeTts()
        execution = execute(TurnPipeline(tts=speech))
        response = execution.response
        self.assertEqual(response.state.value, "answered")
        self.assertEqual(response.reply_audio, "data:audio/wav;base64,QUJD")
        self.assertEqual(speech.spoken_text, response.reply_text)
        self.assertEqual(response.display_text, response.reply_text)
        self.assertIsNone(execution.log.tts_error)
        self.assertGreater(execution.log.timings.tts_ms, 0)

    def test_tts_failure_degrades_to_text_without_failing_the_turn(self) -> None:
        execution = execute(TurnPipeline(tts=FailingTts()))
        response = execution.response
        self.assertEqual(response.state.value, "answered")
        self.assertIsNone(response.reply_audio)
        self.assertTrue(response.reply_text)
        self.assertEqual(execution.log.tts_error, "timeout")
        self.assertGreater(execution.log.timings.tts_ms, 0)

    def test_transcript_is_logged_for_the_debug_view(self) -> None:
        execution = execute(TurnPipeline())
        self.assertTrue(execution.log.transcript)
        self.assertEqual(execution.log.state.value, "answered")


if __name__ == "__main__":
    unittest.main()
