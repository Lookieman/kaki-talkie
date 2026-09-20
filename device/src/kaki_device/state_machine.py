# v1.1 | 20-Sep-2026 | WP6.2: the recording frame counts down live via the microphone's progress.
# v1.0 | 16-Sep-2026 | WP6.1 turn loop: idle, record, wait, speak, print, error.
"""Run the kiosk's turn loop against ports, deciding nothing the backend owns.

The loop is the whole device behaviour, and it is deliberately small:

    idle -> recording -> thinking -> answer (speak, maybe print) -> idle

An interrupted answer goes straight back to recording, and any local failure
shows the error frame and returns to idle. The device never decides what a
turn means: it posts audio, renders `display_text`, speaks `reply_audio` and
prints `slip_text`. Every branch here is on local conditions or on the
contract's `state` field as text.

Two behaviours are worth stating plainly, because they are owner decisions
rather than obvious defaults.

**Interruption.** A button press while the answer is playing stops the speech
and starts a new recording. There is no double-press gesture: the owner
withdrew the AT-03 double-press repeat on 16-Sep-2026, so one button does one
thing at every moment, which is also easier to explain to an elderly user.

**Sessions.** A session groups turns so "repeat that" and "print that" resolve
against the right answer (WP4.2). The Pi owns the boundary that WP4.5 left to
it: a new session at start-up, and a new one whenever the kiosk has been idle
past the configured interval, so the next user never inherits a stranger's
answer.
"""

from dataclasses import dataclass
from threading import Thread
from time import monotonic
from time import sleep as time_sleep
from typing import Callable
from uuid import uuid4

from kaki_device.api_client import ApiError, BackendClient, TurnResult, UnplayableAudio
from kaki_device.api_client import decode_reply_audio
from kaki_device.config import DeviceConfig
from kaki_device.display import layout
from kaki_device.display.layout import DisplayState, Measure
from kaki_device.io_ports import AudioCaptureError, PlaybackError, PrinterError

# How long an idle wait blocks before the loop looks around again: short
# enough to rotate a stale session promptly, long enough not to spin.
IDLE_POLL_SECONDS = 1.0


@dataclass(frozen=True)
class TurnOutcome:
    """What one interaction did, for the caller, the tests and the evidence log."""

    turn_id: str
    session_id: str
    state: str | None = None
    interrupted: bool = False
    printed: bool = False
    spoke: bool = False
    truncated: bool = False
    error_code: str | None = None

    @property
    def failed_locally(self) -> bool:
        """True when the device could not complete the turn itself."""
        return self.error_code is not None


class TurnLoop:
    """Drive one kiosk through its states using injected ports and clock."""

    def __init__(
        self, config: DeviceConfig, client: BackendClient, *, button, microphone,
        speaker, printer, display, measure: Measure,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], None] = time_sleep,
        new_id: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        """Wire the ports; nothing here touches hardware until the loop runs."""
        self._config = config
        self._client = client
        self._button = button
        self._microphone = microphone
        self._speaker = speaker
        self._printer = printer
        self._display = display
        self._measure = measure
        self._clock = clock
        self._sleep = sleep
        self._new_id = new_id
        self._session_id = new_id()
        self._last_activity_at = clock()
        self.outcomes: list[TurnOutcome] = []
        self._stopped = False

    @property
    def session_id(self) -> str:
        """Return the session the next turn will use."""
        return self._session_id

    def stop(self) -> None:
        """Ask `run_forever` to return after the current turn."""
        self._stopped = True

    # -- frames -----------------------------------------------------------

    def _show(self, frame) -> None:
        self._display.show(frame)

    def show_idle(self) -> None:
        """Render the resting prompt."""
        self._show(layout.idle_frame(
            self._config.display_width, self._config.display_height, self._measure
        ))

    def _show_recording(self, seconds_left: float) -> None:
        self._show(layout.recording_frame(
            self._config.display_width, self._config.display_height, self._measure,
            seconds_left,
        ))

    def _show_thinking(self, state: DisplayState = DisplayState.THINKING) -> None:
        self._show(layout.thinking_frame(
            self._config.display_width, self._config.display_height, self._measure, state,
        ))

    def _show_answer(self, display_text: str):
        frame = layout.answer_frame(
            self._config.display_width, self._config.display_height, self._measure,
            display_text,
        )
        self._show(frame)
        return frame

    def _show_error(self) -> None:
        self._show(layout.error_frame(
            self._config.display_width, self._config.display_height, self._measure
        ))

    # -- sessions ---------------------------------------------------------

    def _rotate_session_if_idle(self) -> None:
        """Start a new session when the kiosk has been idle past the interval."""
        if self._clock() - self._last_activity_at >= self._config.session_idle_seconds:
            self._session_id = self._new_id()
            self._last_activity_at = self._clock()

    # -- one turn ---------------------------------------------------------

    def run_turn(self) -> TurnOutcome:
        """Record, submit, render, speak and maybe print one interaction.

        Returns the outcome instead of raising: a kiosk recovers to idle from
        every local failure. `interrupted` reports that the user pressed the
        button during playback, which the caller answers with a new turn.
        """
        self._rotate_session_if_idle()
        turn_id = self._new_id()
        session_id = self._session_id
        self._last_activity_at = self._clock()

        self._show_recording(self._config.record_seconds)
        try:
            audio = self._microphone.record(
                max_seconds=self._config.record_seconds,
                on_progress=self._show_recording,
            )
        except AudioCaptureError:
            self._show_error()
            return self._record_outcome(TurnOutcome(
                turn_id=turn_id, session_id=session_id, error_code="capture_failed",
            ))

        self._show_thinking()
        try:
            result = self._client.submit_turn(
                device_id=self._config.device_id, session_id=session_id,
                turn_id=turn_id, audio=audio,
            )
        except ApiError as error:
            self._show_error()
            return self._record_outcome(TurnOutcome(
                turn_id=turn_id, session_id=session_id, error_code=error.code,
            ))

        frame = self._show_answer(result.display_text)
        interrupted = self._speak(result)
        printed = self._print_if_configured(result)
        self._last_activity_at = self._clock()
        return self._record_outcome(TurnOutcome(
            turn_id=turn_id, session_id=session_id, state=result.state,
            interrupted=interrupted, printed=printed,
            spoke=result.reply_audio is not None, truncated=frame.truncated,
        ))

    def _record_outcome(self, outcome: TurnOutcome) -> TurnOutcome:
        self.outcomes.append(outcome)
        return outcome

    def _speak(self, result: TurnResult) -> bool:
        """Play the reply and watch the button; return True when interrupted.

        Unplayable or absent audio is not a turn failure: the answer is on the
        display and the user can read it, so the loop carries on.
        """
        try:
            audio = decode_reply_audio(result.reply_audio)
        except UnplayableAudio:
            return False
        if audio is None:
            return False
        try:
            return self._play_watching_button(audio)
        except PlaybackError:
            return False

    def _play_watching_button(self, audio: bytes) -> bool:
        """Play audio, stopping early when the button is pressed."""
        playback = Thread(target=self._speaker.play, args=(audio,), daemon=True)
        playback.start()
        interrupted = False
        while playback.is_alive():
            if self._button.is_pressed():
                self._button.wait_for_press(timeout_seconds=0)
                self._speaker.stop()
                interrupted = True
                break
            self._sleep(0.01)
        playback.join(timeout=1.0)
        return interrupted

    def _print_if_configured(self, result: TurnResult) -> bool:
        """Print the slip when the client policy says to, and the turn has one.

        design.md 9.3 puts the policy on the client: the backend always
        produces `slip_text`, and `auto` prints it. A printer failure is
        recorded and swallowed, because WP6-AT-09 requires the spoken answer
        to survive a dead printer.
        """
        if self._config.print_policy != "auto" or not result.has_slip:
            return False
        try:
            self._printer.print_slip(result.slip_text)
        except PrinterError:
            return False
        return True

    # -- the loop ---------------------------------------------------------

    def poll_pending(self) -> list[dict]:
        """Ask the backend for due follow-ups.

        The MVP backend always returns an empty list (handoff and calendar are
        deferred beyond the MVP), so this exists to keep the contract exercised
        and to fail safely if it ever returns something.
        """
        try:
            return self._client.pending()
        except ApiError:
            return []

    def run_forever(self) -> None:
        """Wait for presses and run turns until `stop` is called.

        An interrupted answer starts the next recording immediately: the press
        that stopped the speech is the press that starts the new turn.
        """
        self.show_idle()
        while not self._stopped:
            if not self._button.wait_for_press(timeout_seconds=IDLE_POLL_SECONDS):
                self._rotate_session_if_idle()
                continue
            outcome = self.run_turn()
            while outcome.interrupted and not self._stopped:
                outcome = self.run_turn()
            self.show_idle()
