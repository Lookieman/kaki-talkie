# v1.0 | 20-Sep-2026 | WP6.2 ALSA audio: conversion goldens, capture cap/release, playback.
"""Prove the ALSA ports without ALSA, via injected processes and clocks.

The conversion tests are the design.md 4.3 contract in executable form: every
sound becomes 48 kHz stereo S16_LE, whatever the source WAV says about
itself. The capture tests pin the two ways a recording ends - the button
released, and the 15-second cap (WP6-AT-02) - and that the countdown ticks.
"""

import io
import unittest
import wave

from kaki_device.alsa_audio import AlsaMicrophone, AlsaSpeaker, convert_to_playback
from kaki_device.io_ports import AudioCaptureError, PlaybackError
from kaki_device.mock_io import silent_wav


def wav_bytes(seconds=0.5, framerate=16000, channels=1, sampwidth=2) -> bytes:
    """Build a silent WAV in an arbitrary source format."""
    frames = int(framerate * seconds)
    silence = {1: b"\x80", 2: b"\x00\x00", 4: b"\x00" * 4}[sampwidth]
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(sampwidth)
        out.setframerate(framerate)
        out.writeframes(silence * frames * channels)
    return buffer.getvalue()


def wav_format(audio: bytes) -> tuple[int, int, int, int]:
    """Return (channels, sampwidth, framerate, frames) of a WAV."""
    with wave.open(io.BytesIO(audio), "rb") as source:
        return (source.getnchannels(), source.getsampwidth(),
                source.getframerate(), source.getnframes())


class ConversionTests(unittest.TestCase):
    def test_16k_mono_becomes_48k_stereo_s16(self):
        converted = convert_to_playback(wav_bytes(seconds=1.0))
        channels, width, rate, frames = wav_format(converted)
        self.assertEqual((channels, width, rate), (2, 2, 48000))
        self.assertAlmostEqual(frames / rate, 1.0, places=2)

    def test_the_source_header_is_read_not_assumed(self):
        converted = convert_to_playback(wav_bytes(framerate=22050, channels=2))
        channels, width, rate, frames = wav_format(converted)
        self.assertEqual((channels, width, rate), (2, 2, 48000))
        self.assertAlmostEqual(frames / rate, 0.5, places=2)

    def test_8_bit_unsigned_input_converts_to_silence_not_a_dc_thump(self):
        converted = convert_to_playback(wav_bytes(sampwidth=1))
        with wave.open(io.BytesIO(converted), "rb") as out:
            frames = out.readframes(out.getnframes())
        loudest = max(
            abs(int.from_bytes(frames[i:i + 2], "little", signed=True))
            for i in range(0, len(frames), 2)
        )
        self.assertLess(loudest, 512)  # 8-bit midpoint 0x80 must land near zero

    def test_a_48k_stereo_source_passes_through_with_the_same_length(self):
        source = wav_bytes(seconds=0.25, framerate=48000, channels=2)
        self.assertEqual(wav_format(convert_to_playback(source))[3],
                         wav_format(source)[3])

    def test_unreadable_bytes_raise_playback_error(self):
        for bad in (b"", b"not audio at all", b"RIFF....WAVE"):
            with self.subTest(bad=bad[:8]):
                with self.assertRaises(PlaybackError):
                    convert_to_playback(bad)


class FakeClock:
    """A clock the fake sleep advances, so capture timing is deterministic."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeProcess:
    """Stand in for an arecord/aplay Popen."""

    def __init__(self, stdout: bytes = b"", stderr: bytes = b"",
                 exits_immediately: bool = False, returncode_when_done: int = 0):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self._exited = exits_immediately
        self.returncode = returncode_when_done if exits_immediately else None
        self.terminated = False
        self.communicated: bytes | None = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = -15
        return self.returncode

    def communicate(self, input=None):
        self.communicated = input
        if self.returncode is None:
            self.returncode = 0
        return b"", self.stderr.getvalue()


def popen_factory(process: FakeProcess, commands: list[list[str]]):
    """Return a Popen stand-in that records the command and hands back `process`."""
    def popen(command, **kwargs):
        commands.append(list(command))
        return process
    return popen


PCM_HALF_SECOND = b"\x00\x00" * 8000  # 0.5 s at 16 kHz mono S16_LE


class MicrophoneTests(unittest.TestCase):
    def build(self, process: FakeProcess, held=None):
        clock = FakeClock()
        commands: list[list[str]] = []
        microphone = AlsaMicrophone(
            "plughw:CARD=USB", 16000, held=held,
            popen=popen_factory(process, commands),
            clock=clock, sleep=clock.advance,
        )
        return microphone, commands, clock

    def test_blank_card_is_refused_at_construction(self):
        with self.assertRaises(AudioCaptureError):
            AlsaMicrophone("   ")

    def test_records_raw_16k_mono_from_the_configured_card(self):
        process = FakeProcess(stdout=PCM_HALF_SECOND)
        microphone, commands, _ = self.build(process)
        audio = microphone.record(max_seconds=1.0)
        self.assertEqual(commands[0][:4], ["arecord", "-q", "-D", "plughw:CARD=USB"])
        self.assertIn("raw", commands[0])
        with wave.open(io.BytesIO(audio), "rb") as recording:
            self.assertEqual(
                (recording.getnchannels(), recording.getsampwidth(),
                 recording.getframerate()),
                (1, 2, 16000),
            )
        self.assertTrue(process.terminated)

    def test_the_cap_ends_an_unreleased_recording(self):
        process = FakeProcess(stdout=PCM_HALF_SECOND)
        microphone, _, clock = self.build(process, held=lambda: True)
        microphone.record(max_seconds=2.0)
        self.assertGreaterEqual(clock.now, 2.0)
        self.assertTrue(process.terminated)

    def test_releasing_the_button_ends_the_recording_before_the_cap(self):
        held_states = iter([True, True, False])
        process = FakeProcess(stdout=PCM_HALF_SECOND)
        microphone, _, clock = self.build(
            process, held=lambda: next(held_states, False)
        )
        microphone.record(max_seconds=15.0)
        self.assertLess(clock.now, 1.0)
        self.assertTrue(process.terminated)

    def test_release_is_ignored_when_stop_when_released_is_off(self):
        process = FakeProcess(stdout=PCM_HALF_SECOND)
        microphone, _, clock = self.build(process, held=lambda: False)
        microphone.record(max_seconds=1.0, stop_when_released=False)
        self.assertGreaterEqual(clock.now, 1.0)

    def test_the_countdown_ticks_down_while_recording(self):
        process = FakeProcess(stdout=PCM_HALF_SECOND)
        microphone, _, _ = self.build(process, held=lambda: True)
        seen: list[float] = []
        microphone.record(max_seconds=1.0, on_progress=seen.append)
        self.assertGreater(len(seen), 2)
        self.assertEqual(seen, sorted(seen, reverse=True))
        self.assertLessEqual(seen[0], 1.0)

    def test_a_missing_arecord_names_the_package(self):
        def popen(command, **kwargs):
            raise FileNotFoundError(command[0])
        microphone = AlsaMicrophone("plughw:CARD=USB", popen=popen)
        with self.assertRaises(AudioCaptureError) as caught:
            microphone.record(max_seconds=1.0)
        self.assertIn("alsa-utils", str(caught.exception))

    def test_an_arecord_that_captures_nothing_is_an_error_with_its_stderr(self):
        process = FakeProcess(stderr=b"arecord: main:831: audio open error: No such device",
                              exits_immediately=True, returncode_when_done=1)
        microphone, _, _ = self.build(process)
        with self.assertRaises(AudioCaptureError) as caught:
            microphone.record(max_seconds=1.0)
        self.assertIn("No such device", str(caught.exception))


class SpeakerTests(unittest.TestCase):
    def test_blank_card_is_refused_at_construction(self):
        with self.assertRaises(PlaybackError):
            AlsaSpeaker("")

    def test_play_converts_first_and_pipes_wav_to_aplay_on_the_card(self):
        process = FakeProcess()
        commands: list[list[str]] = []
        speaker = AlsaSpeaker("plughw:CARD=USB", popen=popen_factory(process, commands))
        speaker.play(silent_wav(0.2))
        self.assertEqual(commands[0][:4], ["aplay", "-q", "-D", "plughw:CARD=USB"])
        channels, width, rate, _ = wav_format(process.communicated)
        self.assertEqual((channels, width, rate), (2, 2, 48000))

    def test_unplayable_bytes_raise_before_any_process_starts(self):
        commands: list[list[str]] = []
        speaker = AlsaSpeaker("card", popen=popen_factory(FakeProcess(), commands))
        with self.assertRaises(PlaybackError):
            speaker.play(b"not audio")
        self.assertEqual(commands, [])

    def test_an_aplay_failure_raises_with_its_stderr(self):
        process = FakeProcess(stderr=b"aplay: playback open error")
        process.communicate = lambda input=None: (
            setattr(process, "returncode", 1), (b"", b"aplay: playback open error")
        )[1]
        speaker = AlsaSpeaker("card", popen=popen_factory(process, []))
        with self.assertRaises(PlaybackError) as caught:
            speaker.play(silent_wav(0.1))
        self.assertIn("playback open error", str(caught.exception))

    def test_stop_terminates_a_running_playback_without_error(self):
        process = FakeProcess()

        def communicate(input=None):
            # A stopped aplay exits -15; play() must treat that as normal.
            speaker.stop()
            process.communicated = input
            return b"", b""

        process.communicate = communicate
        speaker = AlsaSpeaker("card", popen=popen_factory(process, []))
        speaker.play(silent_wav(0.1))
        self.assertTrue(process.terminated)

    def test_is_playing_tracks_the_process_lifetime(self):
        speaker = AlsaSpeaker("card", popen=popen_factory(FakeProcess(), []))
        self.assertFalse(speaker.is_playing())
        speaker.stop()  # safe with nothing playing
        speaker.play(silent_wav(0.1))
        self.assertFalse(speaker.is_playing())  # playback completed


if __name__ == "__main__":
    unittest.main()
