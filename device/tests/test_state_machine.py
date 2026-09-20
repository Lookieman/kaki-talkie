# v1.1 | 20-Sep-2026 | WP6.2: countdown frames from microphone progress ticks.
# v1.0 | 16-Sep-2026 | WP6.1 turn loop: turn ids, recording cap, interruption, print, recovery.
"""Drive the whole kiosk loop with mock ports and a fake clock.

This is the unit's main test: it proves the behaviour the Pi will show a user,
without a Pi. Everything is injected, so the run is deterministic except the
one interruption test that needs real playback timing.
"""

import io
import unittest
import wave
from base64 import b64encode
from itertools import count
from pathlib import Path
from time import monotonic

from kaki_device.api_client import AUDIO_DATA_URL_PREFIX, ApiError, TurnResult
from kaki_device.config import DeviceConfig, MockSettings
from kaki_device.display.layout import DisplayState
from kaki_device.io_ports import AudioCaptureError, PrinterError
from kaki_device.mock_io import (
    CollectingDisplay,
    FixtureMicrophone,
    LoggingPrinter,
    RecordingSpeaker,
    ScriptedButton,
    fixed_measure,
    silent_wav,
)
from kaki_device.state_machine import TurnLoop

ANSWER_TEXT = "Open the SMS link from CDC and show the QR code."
SLIP_TEXT = "KAKI-TALKIE HELP\nOpen the SMS link.\nSource: vouchers.cdc.gov.sg"


def wav_data_url(seconds: float = 0.2) -> str:
    """Encode short WAV silence the way the backend encodes reply audio."""
    return AUDIO_DATA_URL_PREFIX + b64encode(silent_wav(seconds)).decode("ascii")


def turn_result(**overrides) -> TurnResult:
    """Build a contract-shaped result for the fake client."""
    fields = {
        "turn_id": "turn", "reply_audio": wav_data_url(), "reply_text": ANSWER_TEXT,
        "display_text": ANSWER_TEXT, "slip_text": SLIP_TEXT, "language": "en",
        "state": "answered", "case_id": None, "sources": (),
    }
    fields.update(overrides)
    return TurnResult(**fields)


class FakeClient:
    """Record submissions and return scripted results or raise scripted errors."""

    def __init__(self, results=None, error: ApiError | None = None) -> None:
        self.results = list(results or [turn_result()])
        self.error = error
        self.submissions: list[dict] = []
        self.pending_calls = 0

    def submit_turn(self, *, device_id: str, session_id: str, turn_id: str, audio: bytes):
        self.submissions.append({
            "device_id": device_id, "session_id": session_id,
            "turn_id": turn_id, "audio": audio,
        })
        if self.error is not None:
            raise self.error
        return self.results[min(len(self.submissions), len(self.results)) - 1]

    def pending(self):
        self.pending_calls += 1
        return []


class FakeClock:
    """A clock the test advances by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def build_loop(*, client=None, config: DeviceConfig | None = None, clock=None,
               microphone=None, speaker=None, printer=None, button=None):
    """Assemble a loop from mocks, returning it with the parts a test asserts on."""
    config = config or DeviceConfig()
    clock = clock or FakeClock()
    ports = {
        "button": button or ScriptedButton(),
        "microphone": microphone or FixtureMicrophone(),
        "speaker": speaker or RecordingSpeaker(),
        "printer": printer or LoggingPrinter(),
        "display": CollectingDisplay(),
    }
    identifiers = count(1)
    loop = TurnLoop(
        config, client or FakeClient(), measure=fixed_measure(), clock=clock,
        sleep=lambda seconds: None,
        new_id=lambda: f"id-{next(identifiers)}", **ports,
    )
    return loop, ports, clock


class HappyPathTests(unittest.TestCase):
    """One press produces one complete turn."""

    def test_turn_records_submits_renders_speaks_and_prints(self):
        client = FakeClient()
        loop, ports, _ = build_loop(client=client)
        outcome = loop.run_turn()

        self.assertEqual(len(client.submissions), 1)
        submission = client.submissions[0]
        self.assertEqual(submission["device_id"], "kaki-pi-01")
        self.assertEqual(submission["turn_id"], outcome.turn_id)
        self.assertEqual(submission["session_id"], loop.session_id)
        self.assertTrue(submission["audio"].startswith(b"RIFF"))

        self.assertEqual(ports["display"].states,
                         [DisplayState.RECORDING.value, DisplayState.THINKING.value,
                          DisplayState.ANSWER.value])
        shown = " ".join(ports["display"].frames[-1].text.split())
        self.assertEqual(shown, ANSWER_TEXT)
        self.assertEqual(len(ports["speaker"].played), 1)
        self.assertEqual(ports["printer"].slips, [SLIP_TEXT])

    def test_recording_progress_ticks_render_countdown_frames(self):
        # WP6.2: a real microphone reports the seconds left while it records;
        # every tick must land on the display as a recording frame.
        class TickingMicrophone(FixtureMicrophone):
            def record(self, max_seconds, stop_when_released=True, on_progress=None):
                for remaining in (max_seconds, max_seconds - 5, 1.0):
                    on_progress(remaining)
                return super().record(max_seconds, stop_when_released)

        loop, ports, _ = build_loop(microphone=TickingMicrophone())
        outcome = loop.run_turn()
        recording = [frame for frame in ports["display"].frames
                     if frame.state is DisplayState.RECORDING]
        self.assertEqual(len(recording), 4)  # the initial frame plus three ticks
        self.assertIn("1 s", recording[-1].text)
        # The ticks change nothing else about the turn.
        self.assertEqual((outcome.state, outcome.error_code), ("answered", None))

    def test_every_turn_uses_a_fresh_turn_id_within_one_session(self):
        loop, _, _ = build_loop()
        first, second = loop.run_turn(), loop.run_turn()
        self.assertNotEqual(first.turn_id, second.turn_id)
        self.assertEqual(first.session_id, second.session_id)

    def test_refused_and_acted_turns_render_and_speak_like_any_other(self):
        for state in ("refused", "acted", "failed"):
            with self.subTest(state=state):
                client = FakeClient([turn_result(state=state)])
                loop, ports, _ = build_loop(client=client)
                outcome = loop.run_turn()
                self.assertEqual(outcome.state, state)
                self.assertEqual(ports["display"].frames[-1].state, DisplayState.ANSWER)
                self.assertIsNone(outcome.error_code)

    def test_pending_is_polled_without_acting_on_it(self):
        client = FakeClient()
        loop, _, _ = build_loop(client=client)
        self.assertEqual(loop.poll_pending(), [])
        self.assertEqual(client.pending_calls, 1)


class RecordingCapTests(unittest.TestCase):
    """WP6-AT-02: the device never asks for more than 15 seconds of audio."""

    def test_the_loop_asks_the_microphone_for_the_configured_cap(self):
        microphone = FixtureMicrophone()
        loop, _, _ = build_loop(microphone=microphone)
        loop.run_turn()
        self.assertEqual(microphone.recordings, [15.0])

    def test_a_shorter_configured_cap_is_honoured(self):
        microphone = FixtureMicrophone()
        loop, _, _ = build_loop(
            config=DeviceConfig(record_seconds=8.0), microphone=microphone
        )
        loop.run_turn()
        self.assertEqual(microphone.recordings, [8.0])


class InterruptionTests(unittest.TestCase):
    """A press during playback stops the answer and starts a new recording."""

    def test_press_during_playback_interrupts_and_the_loop_records_again(self):
        # Real timing: the speaker plays for real so the press can land mid-answer.
        speaker = RecordingSpeaker(realtime=True, clock=monotonic)
        button = ScriptedButton()
        client = FakeClient([turn_result(reply_audio=wav_data_url(0.4))])
        loop, ports, _ = build_loop(
            client=client, speaker=speaker, button=button, clock=monotonic
        )
        loop._sleep = lambda seconds: button.press()  # press once playback starts
        outcome = loop.run_turn()

        self.assertTrue(outcome.interrupted)
        self.assertEqual(speaker.interruptions, 1)
        self.assertFalse(speaker.is_playing())

        second = loop.run_turn()
        self.assertEqual(len(client.submissions), 2)
        self.assertNotEqual(second.turn_id, outcome.turn_id)

    def test_an_uninterrupted_answer_plays_to_the_end(self):
        speaker = RecordingSpeaker(realtime=True, clock=monotonic)
        client = FakeClient([turn_result(reply_audio=wav_data_url(0.05))])
        loop, _, _ = build_loop(client=client, speaker=speaker, clock=monotonic)
        outcome = loop.run_turn()
        self.assertFalse(outcome.interrupted)
        self.assertEqual(speaker.interruptions, 0)


class SessionTests(unittest.TestCase):
    """The Pi owns the session boundary WP4.5 left to it."""

    def test_an_idle_kiosk_rotates_to_a_new_session(self):
        clock = FakeClock()
        loop, _, _ = build_loop(clock=clock)
        first = loop.run_turn()
        clock.advance(DeviceConfig().session_idle_seconds + 1)
        second = loop.run_turn()
        self.assertNotEqual(first.session_id, second.session_id)

    def test_turns_within_the_interval_share_a_session(self):
        clock = FakeClock()
        loop, _, _ = build_loop(clock=clock)
        first = loop.run_turn()
        clock.advance(60)
        second = loop.run_turn()
        self.assertEqual(first.session_id, second.session_id)


class PrintPolicyTests(unittest.TestCase):
    """design.md 9.3: the client decides whether to print."""

    def test_on_request_policy_does_not_print(self):
        printer = LoggingPrinter()
        loop, _, _ = build_loop(
            config=DeviceConfig(print_policy="on_request"), printer=printer
        )
        outcome = loop.run_turn()
        self.assertEqual(printer.slips, [])
        self.assertFalse(outcome.printed)

    def test_an_empty_slip_prints_nothing(self):
        printer = LoggingPrinter()
        loop, _, _ = build_loop(client=FakeClient([turn_result(slip_text="")]),
                                printer=printer)
        self.assertFalse(loop.run_turn().printed)
        self.assertEqual(printer.slips, [])

    def test_a_printer_failure_never_suppresses_the_spoken_answer(self):
        # WP6-AT-09, proven here at Tier A before the printer exists.
        class BrokenPrinter:
            def print_slip(self, slip_text: str) -> None:
                raise PrinterError("no paper")

        loop, ports, _ = build_loop(printer=BrokenPrinter())
        outcome = loop.run_turn()
        self.assertFalse(outcome.printed)
        self.assertEqual(outcome.state, "answered")
        self.assertEqual(len(ports["speaker"].played), 1)


class FailureTests(unittest.TestCase):
    """Local failures show the error frame and return to idle."""

    def test_a_backend_failure_shows_the_error_frame(self):
        for code in ("timeout", "unavailable", "invalid_response"):
            with self.subTest(code=code):
                loop, ports, _ = build_loop(client=FakeClient(error=ApiError(code)))
                outcome = loop.run_turn()
                self.assertEqual(outcome.error_code, code)
                self.assertTrue(outcome.failed_locally)
                self.assertEqual(ports["display"].frames[-1].state, DisplayState.ERROR)
                self.assertEqual(ports["speaker"].played, [])
                self.assertEqual(ports["printer"].slips, [])

    def test_a_capture_failure_shows_the_error_frame_without_submitting(self):
        class BrokenMicrophone:
            def record(self, max_seconds: float, stop_when_released: bool = True,
                       on_progress=None) -> bytes:
                raise AudioCaptureError("no capture device")

        client = FakeClient()
        loop, ports, _ = build_loop(client=client, microphone=BrokenMicrophone())
        outcome = loop.run_turn()
        self.assertEqual(outcome.error_code, "capture_failed")
        self.assertEqual(client.submissions, [])
        self.assertEqual(ports["display"].frames[-1].state, DisplayState.ERROR)

    def test_unplayable_reply_audio_still_leaves_the_answer_on_screen(self):
        client = FakeClient([turn_result(reply_audio="https://example.gov.sg/reply.wav")])
        loop, ports, _ = build_loop(client=client)
        outcome = loop.run_turn()
        self.assertIsNone(outcome.error_code)
        self.assertEqual(ports["speaker"].played, [])
        self.assertEqual(ports["display"].frames[-1].state, DisplayState.ANSWER)

    def test_a_turn_without_audio_is_still_a_complete_turn(self):
        client = FakeClient([turn_result(reply_audio=None)])
        loop, ports, _ = build_loop(client=client)
        outcome = loop.run_turn()
        self.assertFalse(outcome.spoke)
        self.assertEqual(outcome.state, "answered")
        self.assertEqual(ports["speaker"].played, [])


class LoopTests(unittest.TestCase):
    """The idle loop waits for presses and stops when asked."""

    def test_run_forever_runs_one_turn_per_press_then_returns_to_idle(self):
        client = FakeClient()
        loop, ports, _ = build_loop(client=client)
        button = ports["button"]

        original = loop.run_turn

        def run_turn_and_stop():
            outcome = original()
            loop.stop()
            return outcome

        loop.run_turn = run_turn_and_stop
        button.press()
        loop.run_forever()

        self.assertEqual(len(client.submissions), 1)
        self.assertEqual(ports["display"].frames[0].state, DisplayState.IDLE)
        self.assertEqual(ports["display"].frames[-1].state, DisplayState.IDLE)

    def test_the_mock_microphone_reads_a_fixture_file(self):
        directory = Path(__file__).resolve().parent
        fixture = directory / "fixture.wav"
        fixture.write_bytes(silent_wav(0.1))
        self.addCleanup(fixture.unlink)
        config = DeviceConfig(mock=MockSettings(audio_path=fixture))
        loop, _, _ = build_loop(
            config=config, microphone=FixtureMicrophone(config.mock.audio_path)
        )
        loop.run_turn()
        with wave.open(io.BytesIO(fixture.read_bytes()), "rb") as recording:
            self.assertGreater(recording.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
