# v1.2 | 12-Sep-2026 | Build the application from the canned environment, not the shell's.
# v1.1 | 07-Sep-2026 | Keep audio assertions with the typed STT result.
# v1.0 | 06-Sep-2026 | Verify browser decoding, PCM conversion, failure bounds and integration.
"""Exercise real decoding without model services, microphone capture or retained user audio."""

import asyncio
import io
import math
import struct
import unittest
import wave
from pathlib import Path
from time import perf_counter
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from kaki_backend.contracts.ports import Transcription
from kaki_backend.orchestration.audio_normalisation import (
    AudioNormalisationError,
    MAX_INPUT_BYTES,
    normalise_audio,
)
from kaki_backend.orchestration.idempotency import TurnService
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_test_env import canned_backend  #v1.2

# This module posts a turn through the real application, which is built at
# import time from the environment; without the canned sanitiser a validation
# shell's KAKI_STT_MODE=whisper would send it to a live Whisper service.
app = canned_backend().app  #v1.2

CHROME = Path(__file__).resolve().parents[1] / "fixtures/audio/chrome-tone.webm"


def tone(seconds: float = 0.2, rate: int = 48000, channels: int = 2) -> bytes:
    """Build deterministic non-silent PCM input with independently known duration."""
    pcm = bytearray()
    for index in range(round(seconds * rate)):
        value = round(8000 * math.sin(2 * math.pi * 440 * index / rate))
        pcm.extend(struct.pack("<h", value) * channels)
    result = io.BytesIO()
    with wave.open(result, "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(2)
        recording.setframerate(rate)
        recording.writeframes(pcm)
    return result.getvalue()


class AudioNormalisationTests(unittest.TestCase):
    """Prove the WP2.1 output contract using real decoder and resampler execution."""

    def assert_pcm(self, data: bytes, duration: float, tolerance: float = 0.001) -> None:
        """Check WAV metadata, duration and non-silent sample data independently."""
        with wave.open(io.BytesIO(data), "rb") as recording:
            self.assertEqual(recording.getframerate(), 16000)
            self.assertEqual(recording.getnchannels(), 1)
            self.assertEqual(recording.getsampwidth(), 2)
            self.assertEqual(recording.getcomptype(), "NONE")
            self.assertAlmostEqual(recording.getnframes() / 16000, duration, delta=tolerance)
            self.assertTrue(any(recording.readframes(recording.getnframes())))

    def test_current_chrome_webm_opus(self) -> None:
        """Satisfy WP2-AT-01 with actual Chrome MediaRecorder output."""
        self.assert_pcm(normalise_audio(CHROME.read_bytes()), 1, 0.1)

    def test_stereo_resampling_and_resampler_flush(self) -> None:
        """Preserve all samples including the delayed resampler tail."""
        self.assert_pcm(normalise_audio(tone()), 0.2)

    def test_already_normalised_pcm(self) -> None:
        """Preserve the PCM payload of an already-compatible input."""
        original = tone(rate=16000, channels=1)
        self.assertEqual(normalise_audio(original), original)

    def test_invalid_empty_and_oversized_input(self) -> None:
        """Reject unusable input instead of passing arbitrary bytes to STT."""
        for data in (b"", b"not audio", b"RIFF", b"x" * (MAX_INPUT_BYTES + 1), tone(0)):
            with self.subTest(size=len(data)), self.assertRaises(AudioNormalisationError):
                normalise_audio(data)

    def test_decoded_duration_bound(self) -> None:
        """Reject compressed/decoded audio exceeding the documented duration bound."""
        with self.assertRaises(AudioNormalisationError):
            normalise_audio(tone(16.1, rate=16000, channels=1))

    def test_stt_receives_pcm_and_retry_does_not_normalise_again(self) -> None:
        """Keep preparation inside idempotent execution and include its timing."""
        stt = Mock()
        stt.transcribe.return_value = Transcription(text="test")
        service = TurnService(TurnPipeline(stt=stt))

        async def run_turns() -> None:
            """Issue one original request and a retry with different bytes."""
            fields = dict(device_id="test", session_id="test", turn_id="test",
                          audio_preparation_ms=0.0, request_started_at=perf_counter())
            first = await service.process(audio=CHROME.read_bytes(), **fields)
            second = await service.process(audio=b"invalid retry", **fields)
            self.assertEqual(first, second)

        with patch("kaki_backend.orchestration.turn_pipeline.normalise_audio",
                   wraps=normalise_audio) as normaliser:
            asyncio.run(run_turns())
            normaliser.assert_called_once()
        stt.transcribe.assert_called_once()
        self.assert_pcm(stt.transcribe.call_args.args[0], 1, 0.1)
        self.assertGreater(service.logs[0].timings.audio_preparation_ms, 0)

    def test_malformed_http_turn_does_not_invoke_inference(self) -> None:
        """Return the existing failed response shape and close the turn cleanly."""
        app.state.turn_service.reset()
        with TestClient(app) as client:
            response = client.post("/api/device/turn",
                                   data=dict(device_id="test", session_id="test", turn_id="bad"),
                                   files={"audio": ("fake.wav", b"invalid", "audio/wav")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "failed")
        self.assertIsNone(app.state.turn_service.logs[0].timings.stt_ms)


if __name__ == "__main__":
    unittest.main()
