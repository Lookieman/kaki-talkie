# v1.1 | 13-Sep-2026 | WP5.1: Malay speech uses the configured voice; English stays unchanged.
# v1.0 | 09-Sep-2026 | Cover say synthesis bounds, sanitised failures and TTS settings.

"""Deterministic say-adapter and TTS-settings tests; the real binary is never invoked."""

import io
import subprocess
import unittest
import wave
from base64 import b64decode
from pathlib import Path
from unittest.mock import patch

from kaki_backend.config import TtsSettings
from kaki_backend.contracts.ports import TtsError
from kaki_backend.orchestration.canned_ports import CannedTtsPort
from kaki_say_tts.adapter import MAX_TEXT_CHARS, SayTts


def pcm_wav(channels: int = 1, frames: int = 220) -> bytes:
    """Return a small deterministic PCM WAV payload."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(2)
        recording.setframerate(22050)
        recording.writeframes(b"\x01\x00" * frames * channels)
    return buffer.getvalue()


class FakeRunner:
    """Record the synthesis invocation and write configured bytes to the output path."""

    def __init__(self, output: bytes | None = None, error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.command: list[str] | None = None
        self.text: str | None = None
        self.output_path: Path | None = None

    def __call__(self, command, text, timeout_seconds) -> None:
        self.command = list(command)
        self.text = text
        self.output_path = Path(self.command[2])
        if self.error is not None:
            raise self.error
        if self.output is not None:
            self.output_path.write_bytes(self.output)


class SayAdapterTests(unittest.TestCase):
    def test_valid_synthesis_returns_wav_data_url_and_deletes_temp_file(self) -> None:
        runner = FakeRunner(output=pcm_wav())
        result = SayTts(runner=runner).synthesize("Hello Sabariah.")
        prefix, encoded = result.split(",", 1)
        self.assertEqual(prefix, "data:audio/wav;base64")
        self.assertEqual(b64decode(encoded, validate=True), pcm_wav())
        self.assertFalse(runner.output_path.exists())

    def test_text_travels_on_stdin_not_the_command_line(self) -> None:
        runner = FakeRunner(output=pcm_wav())
        SayTts(runner=runner).synthesize("--dangerous looking text")
        self.assertEqual(runner.text, "--dangerous looking text")
        self.assertNotIn("--dangerous looking text", runner.command)
        self.assertEqual(runner.command[0], "say")
        self.assertEqual(runner.command[-2:], ["-f", "-"])

    def test_english_runs_without_a_voice_flag(self) -> None:  #v1.1
        for call in (lambda adapter: adapter.synthesize("Hello."),
                     lambda adapter: adapter.synthesize("Hello.", language="en")):
            runner = FakeRunner(output=pcm_wav())
            call(SayTts(runner=runner))
            self.assertNotIn("-v", runner.command)

    def test_malay_uses_the_configured_voice(self) -> None:  #v1.1
        runner = FakeRunner(output=pcm_wav())
        SayTts(runner=runner).synthesize("Baucar CDC.", language="ms")
        self.assertEqual(runner.command[runner.command.index("-v") + 1], "Amira")
        self.assertEqual(runner.command[-2:], ["-f", "-"])
        runner = FakeRunner(output=pcm_wav())
        SayTts(runner=runner, malay_voice="Damayanti").synthesize("Baucar CDC.", language="ms")
        self.assertEqual(runner.command[runner.command.index("-v") + 1], "Damayanti")

    def test_blank_or_flag_like_voice_names_are_rejected(self) -> None:  #v1.1
        for voice in ("", "   ", "-o", "x" * 65):
            with self.subTest(voice=voice), self.assertRaises(ValueError):
                SayTts(malay_voice=voice)

    def test_blank_and_oversized_text_are_rejected_before_running(self) -> None:
        runner = FakeRunner(output=pcm_wav())
        adapter = SayTts(runner=runner)
        for text in ("", "   ", "x" * (MAX_TEXT_CHARS + 1)):
            with self.subTest(length=len(text)):
                with self.assertRaises(TtsError) as caught:
                    adapter.synthesize(text)
                self.assertEqual(caught.exception.code, "invalid_text")
        self.assertIsNone(runner.command)

    def test_runner_failures_map_to_safe_codes(self) -> None:
        cases = (
            (subprocess.TimeoutExpired(cmd="say", timeout=1), "timeout"),
            (FileNotFoundError("say missing"), "unavailable"),
            (TtsError("unavailable"), "unavailable"),
        )
        for error, expected_code in cases:
            with self.subTest(code=expected_code):
                runner = FakeRunner(error=error)
                with self.assertRaises(TtsError) as caught:
                    SayTts(runner=runner).synthesize("Hello.")
                self.assertEqual(caught.exception.code, expected_code)
                self.assertFalse(runner.output_path.exists())

    def test_non_wav_stereo_and_empty_output_are_rejected(self) -> None:
        for output in (b"not audio at all", pcm_wav(channels=2), pcm_wav(frames=0), b""):
            with self.subTest(size=len(output)):
                runner = FakeRunner(output=output)
                with self.assertRaises(TtsError) as caught:
                    SayTts(runner=runner).synthesize("Hello.")
                self.assertEqual(caught.exception.code, "invalid_output")
                self.assertFalse(runner.output_path.exists())

    def test_ready_reflects_binary_availability_only(self) -> None:
        adapter = SayTts(runner=FakeRunner())
        with patch("kaki_say_tts.adapter.shutil.which", return_value="/usr/bin/say"):
            self.assertTrue(adapter.ready())
        with patch("kaki_say_tts.adapter.shutil.which", return_value=None):
            self.assertFalse(adapter.ready())

    def test_timeout_bounds_are_enforced(self) -> None:
        for timeout in (0.0, 121.0, float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    SayTts(timeout_seconds=timeout)


class TtsSettingsTests(unittest.TestCase):
    def test_default_mode_stays_canned(self) -> None:
        settings = TtsSettings.from_environment({})
        self.assertEqual(settings.mode, "canned")
        self.assertIsInstance(settings.create_port(), CannedTtsPort)

    def test_say_mode_creates_the_say_adapter(self) -> None:
        settings = TtsSettings.from_environment(
            {"KAKI_TTS_MODE": "say", "KAKI_TTS_TIMEOUT_SECONDS": "5"}
        )
        self.assertEqual(settings.timeout_seconds, 5.0)
        self.assertIsInstance(settings.create_port(), SayTts)

    def test_say_mode_passes_the_malay_voice(self) -> None:  #v1.1
        port = TtsSettings.from_environment(
            {"KAKI_TTS_MODE": "say", "KAKI_TTS_VOICE_MS": "Damayanti"}
        ).create_port()
        self.assertEqual(port._voices, {"ms": "Damayanti"})

    def test_invalid_mode_and_timeout_fail_startup(self) -> None:
        for environment in (
            {"KAKI_TTS_MODE": "espeak"},
            {"KAKI_TTS_MODE": "say", "KAKI_TTS_TIMEOUT_SECONDS": "0"},
            {"KAKI_TTS_MODE": "say", "KAKI_TTS_TIMEOUT_SECONDS": "nan"},
            {"KAKI_TTS_MODE": "say", "KAKI_TTS_TIMEOUT_SECONDS": "121"},
        ):
            with self.subTest(environment=environment):
                with self.assertRaises(ValueError):
                    TtsSettings.from_environment(environment)


if __name__ == "__main__":
    unittest.main()
