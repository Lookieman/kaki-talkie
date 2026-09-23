# v1.3 | 23-Sep-2026 | WP6.5: idle pending poll cadence and nudge delivery.
# v1.2 | 20-Sep-2026 | WP6.4: retrying frame during client retries; connection copy.
# v1.1 | 20-Sep-2026 | WP6.2: countdown frames from microphone progress ticks.
# v1.0 | 16-Sep-2026 | WP6.1 turn loop: turn ids, recording cap, interruption, print, recovery.
"""Drive the whole kiosk loop with mock ports and a fake clock.

This is the unit's main test: it proves the behaviour the Pi will show a user,
without a Pi. Everything is injected, so the run is deterministic except the
one interruption test that needs real playback timing.
"""

import contextlib  #v1.3
import io
import unittest
import wave
from base64 import b64encode
from itertools import count
from pathlib import Path
from time import monotonic
from unittest.mock import patch  #v1.3

from kaki_device.api_client import AUDIO_DATA_URL_PREFIX, ApiError, TurnResult
from kaki_device.config import DeviceConfig, MockSettings
from kaki_device.display import layout  # WP6.4 error copy
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
from kaki_device.state_machine import NUDGE_HOLD_SECONDS, TurnLoop  #v1.3

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

    def __init__(self, results=None, error: ApiError | None = None,
                 nudges=None, pending_error: ApiError | None = None) -> None:
        self.results = list(results or [turn_result()])
        self.error = error
        self.submissions: list[dict] = []
        # WP6.5: one scripted list per poll; exhausted polls return [].
        self.nudges = [list(batch) for batch in (nudges or [])]
        self.pending_error = pending_error
        self.pending_calls = 0
        self.pending_device_ids: list[str | None] = []

    def submit_turn(self, *, device_id: str, session_id: str, turn_id: str, audio: bytes,
                    on_retry=None):  # WP6.4: the loop passes its retry callback
        self.submissions.append({
            "device_id": device_id, "session_id": session_id,
            "turn_id": turn_id, "audio": audio,
        })
        if self.error is not None:
            raise self.error
        return self.results[min(len(self.submissions), len(self.results)) - 1]

    def pending(self, device_id=None):
        self.pending_calls += 1
        self.pending_device_ids.append(device_id)
        if self.pending_error is not None:
            raise self.pending_error
        return self.nudges.pop(0) if self.nudges else []


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

    def test_pending_sends_the_configured_device_id(self):
        # WP6.5: the poll names this kiosk, so the backend can hand its
        # queued pushes over; a failure still reads as nothing due.
        client = FakeClient()
        loop, _, _ = build_loop(client=client)
        self.assertEqual(loop.poll_pending(), [])
        self.assertEqual(client.pending_calls, 1)
        self.assertEqual(client.pending_device_ids, [DeviceConfig().device_id])


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

    def test_a_connection_failure_shows_the_connection_wording(self):
        # WP6.4: exhausted retries get the "Cannot connect" placeholder copy;
        # a non-connection failure keeps the generic message.
        for code, expected_body in (
            ("timeout", layout.CONNECTION_ERROR_BODY),
            ("unavailable", layout.CONNECTION_ERROR_BODY),
            ("invalid_response", layout.ERROR_BODY),
            ("rejected", layout.ERROR_BODY),
        ):
            with self.subTest(code=code):
                loop, ports, _ = build_loop(client=FakeClient(error=ApiError(code)))
                loop.run_turn()
                error = ports["display"].frames[-1]
                self.assertEqual(error.state, DisplayState.ERROR)
                self.assertIn(expected_body, error.text)

    def test_a_client_retry_shows_the_retrying_frame_and_keeps_the_turn_id(self):
        # WP6.4 (WP6-AT-04): the loop hands the client an on_retry callback;
        # a retrying client shows RETRYING and the answer still arrives.
        class RetryingClient(FakeClient):
            def submit_turn(self, *, device_id, session_id, turn_id, audio,
                            on_retry=None):
                if on_retry is not None:
                    on_retry(2)  # the client decided to retry the same turn_id
                return super().submit_turn(
                    device_id=device_id, session_id=session_id,
                    turn_id=turn_id, audio=audio,
                )

        loop, ports, _ = build_loop(client=RetryingClient())
        outcome = loop.run_turn()
        self.assertEqual(outcome.state, "answered")
        states = [frame.state for frame in ports["display"].frames]
        self.assertIn(DisplayState.RETRYING, states)
        self.assertLess(states.index(DisplayState.RETRYING),
                        states.index(DisplayState.ANSWER))

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


class NudgeTests(unittest.TestCase):
    """WP6.5: an idle kiosk polls for admin pushes and plays each one once."""

    class IdleButton:
        """Time out idle wakes, advancing the fake clock, then stop the loop."""

        def __init__(self, clock, wakes: int) -> None:
            self._clock = clock
            self._wakes = wakes
            self.loop = None

        def wait_for_press(self, timeout_seconds: float) -> bool:
            self._clock.advance(timeout_seconds)
            self._wakes -= 1
            if self._wakes <= 0:
                self.loop.stop()
            return False

        def is_pressed(self) -> bool:
            return False

    def idle_loop(self, wakes: int, **kwargs):
        """Build a loop whose button idles `wakes` times and then stops it."""
        clock = FakeClock()
        button = self.IdleButton(clock, wakes)
        loop, ports, _ = build_loop(clock=clock, button=button, **kwargs)
        button.loop = loop
        return loop, ports

    @staticmethod
    def nudge(**overrides) -> dict:
        item = {
            "id": "cdc-vouchers-available", "kind": "nudge",
            "text": "Good news: new CDC vouchers are available.",
            "language": "en", "audio": wav_data_url(),
            "pushed_at": "2026-09-23T00:00:00Z",
        }
        item.update(overrides)
        return item

    def test_idle_polls_every_three_seconds_not_every_wake(self):
        # Four 1-second wakes cross the 3-second gate exactly once.
        client = FakeClient()
        loop, _ = self.idle_loop(4, client=client)
        loop.run_forever()
        self.assertEqual(client.pending_calls, 1)
        self.assertEqual(client.pending_device_ids, [DeviceConfig().device_id])

    def test_a_nudge_is_shown_played_once_and_logged_once(self):
        # WP6-AT-23: seven wakes give two polls; the nudge arrives on the
        # first and must not replay on the second.
        client = FakeClient(nudges=[[self.nudge()]])
        loop, ports = self.idle_loop(7, client=client)
        with contextlib.redirect_stderr(io.StringIO()) as log:
            loop.run_forever()
        self.assertEqual(client.pending_calls, 2)
        answers = [frame for frame in ports["display"].frames
                   if frame.state is DisplayState.ANSWER]
        self.assertEqual(len(answers), 1)
        self.assertIn("Good news", answers[0].text)
        self.assertEqual(len(ports["speaker"].played), 1)
        self.assertTrue(ports["speaker"].played[0].startswith(b"RIFF"))
        self.assertEqual(ports["display"].states[-1], DisplayState.IDLE.value)
        lines = [line for line in log.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertIn("cdc-vouchers-available", lines[0])

    def test_text_only_and_unplayable_audio_hold_then_idle(self):
        # WP6-AT-24: no audio still shows the text; never an error frame.
        for audio in (None, "https://example.gov.sg/nudge.wav"):
            with self.subTest(audio=audio):
                client = FakeClient(nudges=[[self.nudge(audio=audio)]])
                loop, ports = self.idle_loop(4, client=client)
                naps: list[float] = []
                loop._sleep = naps.append
                with contextlib.redirect_stderr(io.StringIO()) as log:
                    loop.run_forever()
                self.assertEqual(ports["speaker"].played, [])
                self.assertIn(NUDGE_HOLD_SECONDS, naps)
                frames = ports["display"].frames
                self.assertTrue(any(f.state is DisplayState.ANSWER for f in frames))
                self.assertNotIn(DisplayState.ERROR, [f.state for f in frames])
                self.assertEqual(frames[-1].state, DisplayState.IDLE)
                lines = [line for line in log.getvalue().splitlines() if line.strip()]
                self.assertEqual(len(lines), 1)

    def test_a_failed_poll_changes_nothing_and_logs_nothing(self):
        # WP6-AT-24, failure half: idle stays idle, silently.
        client = FakeClient(pending_error=ApiError("unavailable"))
        loop, ports = self.idle_loop(4, client=client)
        with contextlib.redirect_stderr(io.StringIO()) as log:
            loop.run_forever()
        self.assertEqual(client.pending_calls, 1)
        self.assertEqual(ports["display"].states, [DisplayState.IDLE.value])
        self.assertEqual(log.getvalue(), "")

    def test_a_press_during_nudge_playback_interrupts_it(self):
        # WP6-AT-25, playback half. Real timing, like the answer
        # interruption test: the press lands while the clip is sounding.
        speaker = RecordingSpeaker(realtime=True, clock=monotonic)
        button = ScriptedButton()
        loop, _, _ = build_loop(speaker=speaker, button=button, clock=monotonic)
        loop._sleep = lambda seconds: button.press()
        with contextlib.redirect_stderr(io.StringIO()):
            interrupted = loop._deliver_nudges([self.nudge(audio=wav_data_url(0.4))])
        self.assertTrue(interrupted)
        self.assertEqual(speaker.interruptions, 1)
        self.assertFalse(speaker.is_playing())

    def test_the_interrupting_press_starts_a_new_turn(self):
        # WP6-AT-25, wiring half: run_forever answers an interrupting press
        # with a recording, exactly like an interrupted answer.
        client = FakeClient(nudges=[[self.nudge()]])
        loop, _ = self.idle_loop(4, client=client)
        with patch.object(loop, "_deliver_nudges", return_value=True):
            loop.run_forever()
        self.assertEqual(len(client.submissions), 1)



if __name__ == "__main__":
    unittest.main()
