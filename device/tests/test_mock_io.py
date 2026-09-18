# v1.0 | 16-Sep-2026 | WP6.1 mock hardware: fixtures, scheduling, interruption, slip logging.
"""Prove the mocks behave as the tests and the mock run assume.

The mocks stand in for hardware in every other test, so their own behaviour
has to be pinned: a mock that silently returns nothing would make the loop
tests pass for the wrong reason.
"""

import io
import tempfile
import unittest
import wave
from pathlib import Path

from kaki_device.io_ports import AudioCaptureError
from kaki_device.mock_io import (
    CollectingDisplay,
    FixtureMicrophone,
    LoggingPrinter,
    RecordingSpeaker,
    ScriptedButton,
    fixed_measure,
    silent_wav,
)


class ButtonTests(unittest.TestCase):
    def test_a_manual_press_is_consumed_once(self):
        button = ScriptedButton()
        self.assertFalse(button.wait_for_press(timeout_seconds=0))
        button.press()
        self.assertTrue(button.is_pressed())
        self.assertTrue(button.wait_for_press(timeout_seconds=0))
        self.assertFalse(button.wait_for_press(timeout_seconds=0))

    def test_a_scheduled_press_fires_once_its_time_arrives(self):
        now = [100.0]
        button = ScriptedButton((0.5,), clock=lambda: now[0])
        self.assertFalse(button.wait_for_press(timeout_seconds=0))
        now[0] += 0.6
        self.assertTrue(button.wait_for_press(timeout_seconds=0))
        self.assertFalse(button.wait_for_press(timeout_seconds=0))
        self.assertEqual(len(button.presses), 1)


class MicrophoneTests(unittest.TestCase):
    def test_default_recording_is_valid_pcm_wav(self):
        audio = FixtureMicrophone().record(max_seconds=15.0)
        with wave.open(io.BytesIO(audio), "rb") as recording:
            self.assertEqual(recording.getnchannels(), 1)
            self.assertEqual(recording.getframerate(), 16000)
            self.assertGreater(recording.getnframes(), 0)

    def test_a_fixture_file_is_returned_unchanged(self):
        directory = Path(tempfile.mkdtemp(prefix="kaki-mic."))
        path = directory / "cdc.wav"
        payload = silent_wav(0.2)
        path.write_bytes(payload)
        self.assertEqual(FixtureMicrophone(path).record(max_seconds=15.0), payload)

    def test_a_missing_or_empty_fixture_raises_capture_error(self):
        directory = Path(tempfile.mkdtemp(prefix="kaki-mic."))
        empty = directory / "empty.wav"
        empty.write_bytes(b"")
        for path in (directory / "missing.wav", empty):
            with self.subTest(path=path.name), self.assertRaises(AudioCaptureError):
                FixtureMicrophone(path).record(max_seconds=15.0)


class SpeakerTests(unittest.TestCase):
    def test_playback_records_what_it_played_and_its_duration(self):
        speaker = RecordingSpeaker()
        audio = silent_wav(0.5)
        speaker.play(audio)
        self.assertEqual(speaker.played, [audio])
        self.assertAlmostEqual(speaker.durations[0], 0.5, places=2)
        self.assertFalse(speaker.is_playing())

    def test_unreadable_audio_reports_zero_duration_rather_than_raising(self):
        self.assertEqual(RecordingSpeaker.duration_seconds(b"not audio"), 0.0)

    def test_stop_without_playback_is_harmless(self):
        speaker = RecordingSpeaker()
        speaker.stop()
        self.assertEqual(speaker.interruptions, 0)


class PrinterAndDisplayTests(unittest.TestCase):
    def test_slips_are_collected_and_appended_to_the_log(self):
        directory = Path(tempfile.mkdtemp(prefix="kaki-printer."))
        log = directory / "slips.log"
        printer = LoggingPrinter(log)
        printer.print_slip("KAKI-TALKIE HELP\nOpen the SMS link.")
        printer.print_slip("KAKI-TALKIE REFERRAL\nAsk a staff member.")
        self.assertEqual(len(printer.slips), 2)
        written = log.read_text(encoding="utf-8")
        self.assertIn("KAKI-TALKIE HELP", written)
        self.assertIn("KAKI-TALKIE REFERRAL", written)

    def test_the_display_keeps_frames_in_order_and_closes(self):
        display = CollectingDisplay()
        self.assertFalse(display.closed)
        display.close()
        self.assertTrue(display.closed)
        self.assertEqual(display.frames, [])


class MeasureTests(unittest.TestCase):
    def test_the_fixed_measure_grows_with_text_and_size(self):
        measure = fixed_measure()
        self.assertGreater(measure("longer text", 40), measure("short", 40))
        self.assertGreater(measure("same", 52), measure("same", 34))


if __name__ == "__main__":
    unittest.main()
