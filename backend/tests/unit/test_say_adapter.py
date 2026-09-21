# v1.3 | 21-Sep-2026 | Acronyms spoken as plain letters; literal mode read case aloud.
# v1.2 | 21-Sep-2026 | WP6.8: English voice, speaking rate and the spoken form.
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
from kaki_say_tts.spoken_form import to_spoken_form


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

    # WP6.8 replaced the WP5.1 behaviour asserted here: English no longer
    # falls through to the system voice, it names Jamie like Malay names
    # Amira, and both speak at the configured rate.
    def test_english_uses_the_configured_voice_and_rate(self) -> None:  #v1.2
        for call in (lambda adapter: adapter.synthesize("Hello."),
                     lambda adapter: adapter.synthesize("Hello.", language="en")):
            runner = FakeRunner(output=pcm_wav())
            call(SayTts(runner=runner))
            self.assertEqual(runner.command[runner.command.index("-v") + 1], "Jamie")
            self.assertEqual(runner.command[runner.command.index("-r") + 1], "150")

    def test_a_configured_rate_reaches_the_command(self) -> None:  #v1.2
        runner = FakeRunner(output=pcm_wav())
        SayTts(runner=runner, rate_wpm=120).synthesize("Hello.")
        self.assertEqual(runner.command[runner.command.index("-r") + 1], "120")

    def test_rates_outside_the_documented_range_are_rejected(self) -> None:  #v1.2
        for rate in (0, 79, 301, 1000):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                SayTts(rate_wpm=rate)

    def test_an_unknown_language_falls_back_to_the_system_voice(self) -> None:  #v1.2
        runner = FakeRunner(output=pcm_wav())
        SayTts(runner=runner).synthesize("Hello.", language="ta")
        self.assertNotIn("-v", runner.command)

    def test_the_spoken_form_reaches_say_while_the_caller_text_is_untouched(self) -> None:
        # WP6-AT-22: only the bytes handed to `say` carry the spoken form.
        runner = FakeRunner(output=pcm_wav())
        written = "1. Open the SMS link. 2. Show your CDC card (it is free)."
        SayTts(runner=runner).synthesize(written)
        self.assertNotIn("1.", runner.text)
        self.assertIn("C D C", runner.text)
        self.assertIn("[[slnc 400]]", runner.text)
        self.assertNotIn("(", runner.text)

    def test_acronyms_are_spoken_as_plain_letters_never_literal_mode(self) -> None:
        # WP6.4 Tier C, 21-Sep-2026: [[char LTRL]] announced case, so the Pi
        # read "Capital C, Capital D, Capital C". Plain spaced letters are
        # the fix; literal mode must never come back.
        self.assertEqual(
            to_spoken_form("Bring your CDC card and reply to the SMS."),
            "Bring your C D C card and reply to the S M S.",
        )
        for written in ("CDC", "CHAS", "NRIC", "PIN", "OTP", "SMS", "ATM", "MRT"):
            with self.subTest(acronym=written):
                spoken = to_spoken_form(written)
                self.assertEqual(spoken, " ".join(written))
                self.assertNotIn("[[char", spoken)

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
            with self.subTest(voice=voice, language="en"):  #v1.2
                with self.assertRaises(ValueError):
                    SayTts(english_voice=voice)

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

    def test_say_mode_passes_both_voices(self) -> None:  #v1.2
        # WP6.8 added the English voice beside the WP5.1 Malay one.
        port = TtsSettings.from_environment(
            {"KAKI_TTS_MODE": "say", "KAKI_TTS_VOICE_MS": "Damayanti"}
        ).create_port()
        self.assertEqual(port._voices, {"ms": "Damayanti", "en": "Jamie"})

    def test_say_mode_passes_the_configured_english_voice_and_rate(self) -> None:  #v1.2
        port = TtsSettings.from_environment({
            "KAKI_TTS_MODE": "say", "KAKI_TTS_VOICE_EN": "Daniel",
            "KAKI_TTS_RATE_WPM": "130",
        }).create_port()
        self.assertEqual(port._voices["en"], "Daniel")
        self.assertEqual(port._rate, 130)

    def test_defaults_are_jamie_amira_at_150_wpm(self) -> None:  #v1.2
        settings = TtsSettings.from_environment({})
        self.assertEqual(
            (settings.english_voice, settings.malay_voice, settings.rate_wpm),
            ("Jamie", "Amira", 150),
        )

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
