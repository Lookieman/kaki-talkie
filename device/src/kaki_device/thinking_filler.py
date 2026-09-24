# v1.0 | 24-Sep-2026 | WP6.8 voice revision: two-stage thinking filler on the Pi.
"""Cover a slow turn's silence with at most two short canned clips.

A grounded turn takes several seconds, and silence reads as a dead kiosk.
The filler plays from the moment the thinking state starts:

1. `thinking_filler_1.en.wav` plays once, immediately;
2. `thinking_filler_2.en.wav` plays once, only if the answer is still
   missing `second_delay_seconds` after the thinking state started (default
   5 s, `filler_second_delay_seconds` in the device config).

The properties below are the reason this class exists, so they are enforced
here rather than left to the loop:

- neither clip ever plays after `stop()`, which the loop calls the moment the
  answer (or an error) arrives. `stop()` cuts a clip that is still sounding,
  so the answer never overlaps it;
- a missing or invalid clip means silence for that stage. It never delays or
  fails the turn: the clips are validated once at load, and a playback error
  is swallowed.

The clips are static recordings packaged with the device, so this module
decides nothing about a turn's content (WP6-AT-13). Playback runs on a
background thread because `SpeakerPort.play` blocks while the loop is itself
blocked in `submit_turn`.
"""

import io
import wave
from importlib.resources import files
from threading import Event, Lock, Thread
from time import monotonic
from typing import Callable

from kaki_device.io_ports import PlaybackError

CLIP_DIRECTORY = "clips"
FIRST_CLIP = "thinking_filler_1.en.wav"
SECOND_CLIP = "thinking_filler_2.en.wav"
# What each clip says. The device never speaks these strings itself; they
# record the wording the owner captures, so the clip and the code agree.
FIRST_CLIP_TEXT = "Wait ah, I check for you."
SECOND_CLIP_TEXT = "Almost there ah, Auntie. Wait a bit more."
# How long `start` waits for the playback thread to take the first clip, so
# the first clip always begins before the turn can finish. Bounded, so a
# stuck thread can never delay the turn noticeably.
START_HANDSHAKE_SECONDS = 0.5
# How long `stop` keeps cutting playback while the thread winds down. A
# clip that had just been handed to the speaker when the answer arrived is
# stopped again until the thread exits.
STOP_GRACE_SECONDS = 1.0
STOP_POLL_SECONDS = 0.02

ClipReader = Callable[[str], bytes | None]


def read_packaged_clip(filename: str) -> bytes | None:
    """Return a packaged device clip's bytes, or None when it is not there."""
    try:
        return files("kaki_device").joinpath(CLIP_DIRECTORY, filename).read_bytes()
    except (FileNotFoundError, OSError):
        return None


def playable_clip(audio: bytes | None) -> bytes | None:
    """Return `audio` when it is a readable, non-empty PCM WAV, else None."""
    if not audio:
        return None
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            if recording.getframerate() <= 0 or recording.getnframes() <= 0:
                return None
    except (wave.Error, EOFError):
        return None
    return audio


class ThinkingFiller:
    """Play the first clip at once and the second after a delay, until stopped."""

    def __init__(self, speaker, first: bytes | None, second: bytes | None, *,
                 second_delay_seconds: float,
                 clock: Callable[[], float] = monotonic) -> None:
        """Hold validated clip bytes; either may be None, which means silence."""
        self._speaker = speaker
        self._first = playable_clip(first)
        self._second = playable_clip(second)
        self._delay = max(0.0, second_delay_seconds)
        self._clock = clock
        self._lock = Lock()
        self._cancelled = Event()
        self._playing = False
        self._thread: Thread | None = None

    @classmethod
    def from_package(cls, speaker, second_delay_seconds: float,
                     reader: ClipReader = read_packaged_clip) -> "ThinkingFiller":
        """Load both clips from the device package; a missing file is silence."""
        return cls(
            speaker, reader(FIRST_CLIP), reader(SECOND_CLIP),
            second_delay_seconds=second_delay_seconds,
        )

    def start(self) -> None:
        """Begin the filler for one turn; returns within a bounded handshake."""
        self.stop()
        if self._first is None and self._second is None:
            return
        cancelled = Event()
        first_taken = Event()
        with self._lock:
            self._cancelled = cancelled
        thread = Thread(
            target=self._run, args=(cancelled, first_taken, self._clock()), daemon=True,
        )
        self._thread = thread
        thread.start()
        first_taken.wait(timeout=START_HANDSHAKE_SECONDS)

    def stop(self) -> None:
        """Cancel any pending clip and cut the one sounding; safe when idle."""
        with self._lock:
            self._cancelled.set()
        thread = self._thread
        self._thread = None
        if thread is None:
            return
        deadline = self._clock() + STOP_GRACE_SECONDS
        while thread.is_alive() and self._clock() < deadline:
            with self._lock:
                playing = self._playing
            if playing:
                self._speaker.stop()
            thread.join(timeout=STOP_POLL_SECONDS)

    def _run(self, cancelled: Event, first_taken: Event, started_at: float) -> None:
        """Play stage one, wait out the delay, then play stage two unless cancelled."""
        self._play_unless_cancelled(self._first, cancelled, first_taken)
        remaining = self._delay - (self._clock() - started_at)
        if cancelled.wait(timeout=max(0.0, remaining)):
            return
        self._play_unless_cancelled(self._second, cancelled)

    def _play_unless_cancelled(self, clip: bytes | None, cancelled: Event,
                               taken: Event | None = None) -> None:
        """Claim the speaker under the lock so `stop` can always see and cut it."""
        with self._lock:
            claimed = clip is not None and not cancelled.is_set()
            self._playing = claimed
        if taken is not None:
            taken.set()
        if not claimed:
            return
        try:
            self._speaker.play(clip)
        except PlaybackError:
            pass  # a filler that cannot play is silence, never a turn failure
        finally:
            with self._lock:
                self._playing = False
