# v1.0 | 20-Sep-2026 | WP6.2 Jabra capture and playback over ALSA, with one conversion path.
"""Record and play through the Jabra Speak using ALSA directly (design.md 4.3).

Capture runs `arecord` on the configured card at 16 kHz mono S16_LE, the only
format the Jabra captures. The stream is raw PCM read incrementally, so the
loop can stop it the moment the button is released, cap it at the recording
limit (WP6-AT-02) and tick the on-screen countdown while it runs; the WAV
header is written here afterwards, so it is always correct.

Playback is one function for every sound: `convert_to_playback` reads each
WAV's own header — never assuming the TTS output format — and converts to
48 kHz stereo S16_LE before `aplay`, because the Jabra plays 16 kHz audio too
fast. No path bypasses the conversion.

ALSA is used directly, not PipeWire, so the WP6.4 systemd service will work
without a desktop session. `arecord`/`aplay` come from apt (`alsa-utils`,
setup.md 29.3); running them as subprocesses keeps the device package free of
audio dependencies, which the WP6-AT-13 inspection enforces.

`audioop` is deprecated (removed in Python 3.13); the Pi runs the 3.11 this
package pins, and the conversion is three calls that would otherwise be
hand-written loops. Revisit if the device Python ever moves past 3.12.
"""

import io
import subprocess
import wave
from threading import Thread
from time import monotonic
from time import sleep as time_sleep
from typing import Callable

import audioop  # deprecated in 3.12, removed in 3.13; see the module docstring

from kaki_device.config import DEFAULT_CAPTURE_RATE, DEFAULT_PLAYBACK_RATE
from kaki_device.io_ports import AudioCaptureError, PlaybackError, Progress

# How often the capture loop looks at the clock and the button, and updates
# the countdown. Coarser would make release feel laggy; finer would spin.
CAPTURE_TICK_SECONDS = 0.1
# Signals a deliberate terminate() sends; not capture or playback failures.
_TERMINATED_RETURNCODES = (0, -15)


def convert_to_playback(audio: bytes, rate: int = DEFAULT_PLAYBACK_RATE) -> bytes:
    """Return `audio` as a 48 kHz (or `rate`) stereo S16_LE WAV.

    Reads the source format from the WAV header. Raises PlaybackError for
    bytes that are not a readable PCM WAV, which the loop treats as "the
    answer stays on the display" rather than a turn failure.
    """
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            channels = source.getnchannels()
            width = source.getsampwidth()
            source_rate = source.getframerate()
            frames = source.readframes(source.getnframes())
    except (wave.Error, EOFError) as error:
        raise PlaybackError(f"not a readable WAV: {error}") from None
    if channels not in (1, 2) or width not in (1, 2, 3, 4) or source_rate <= 0:
        raise PlaybackError(
            f"unsupported WAV format: {channels} channel(s), "
            f"{width * 8}-bit, {source_rate} Hz."
        )
    if width == 1:
        # 8-bit WAV is unsigned; make it signed before widening.
        frames = audioop.bias(frames, 1, -128)
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
    if source_rate != rate:
        frames, _ = audioop.ratecv(frames, 2, channels, source_rate, rate, None)
    if channels == 1:
        frames = audioop.tostereo(frames, 2, 1.0, 1.0)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as converted:
        converted.setnchannels(2)
        converted.setsampwidth(2)
        converted.setframerate(rate)
        converted.writeframes(frames)
    return buffer.getvalue()


class AlsaMicrophone:
    """Record 16 kHz mono S16_LE from the Jabra; satisfies `MicrophonePort`.

    `held` reports whether the button is still down; releasing it ends the
    recording when `stop_when_released` asks for that, which is the
    hold-to-talk half of WP6-AT-02. The clock cap is the other half.
    """

    def __init__(self, card: str, rate: int = DEFAULT_CAPTURE_RATE, *,
                 held: Callable[[], bool] | None = None,
                 popen: Callable = subprocess.Popen,
                 clock: Callable[[], float] = monotonic,
                 sleep: Callable[[float], None] = time_sleep) -> None:
        """Remember the card and rate; `popen`, `clock` and `sleep` exist for tests."""
        if not card.strip():
            raise AudioCaptureError(
                "audio.card is not configured; set the stable ALSA name "
                "(runbook 11.1 WP6.2)."
            )
        self._card = card
        self._rate = rate
        self._held = held
        self._popen = popen
        self._clock = clock
        self._sleep = sleep

    def record(self, max_seconds: float, stop_when_released: bool = True,
               on_progress: Progress | None = None) -> bytes:
        """Capture until release or the cap, and return complete WAV bytes.

        Raises AudioCaptureError when arecord is missing, exits at once, or
        captures nothing. Deliberate termination at release or cap is the
        normal path, not an error.
        """
        command = [
            "arecord", "-q", "-D", self._card, "-t", "raw",
            "-f", "S16_LE", "-c", "1", "-r", str(self._rate),
        ]
        try:
            process = self._popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise AudioCaptureError(
                "arecord not found; install alsa-utils (setup.md 29.3)."
            ) from None

        chunks: list[bytes] = []

        def drain() -> None:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    return
                chunks.append(chunk)

        reader = Thread(target=drain, daemon=True)
        reader.start()
        started = self._clock()
        while True:
            elapsed = self._clock() - started
            if elapsed >= max_seconds:
                break
            if stop_when_released and self._held is not None and not self._held():
                break
            if process.poll() is not None:
                break
            if on_progress is not None:
                on_progress(max(0.0, max_seconds - elapsed))
            self._sleep(CAPTURE_TICK_SECONDS)

        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
        reader.join(timeout=1.0)

        pcm = b"".join(chunks)
        pcm = pcm[: len(pcm) // 2 * 2]  # a terminated stream may end mid-sample
        if not pcm:
            detail = _stderr_tail(process)
            raise AudioCaptureError(
                f"arecord captured nothing from {self._card!r}"
                + (f": {detail}" if detail else ".")
            )
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(self._rate)
            recording.writeframes(pcm)
        return buffer.getvalue()


class AlsaSpeaker:
    """Play every sound through aplay after conversion; satisfies `SpeakerPort`."""

    def __init__(self, card: str, playback_rate: int = DEFAULT_PLAYBACK_RATE, *,
                 popen: Callable = subprocess.Popen) -> None:
        """Remember the card and target rate; `popen` exists for tests."""
        if not card.strip():
            raise PlaybackError(
                "audio.card is not configured; set the stable ALSA name "
                "(runbook 11.1 WP6.2)."
            )
        self._card = card
        self._rate = playback_rate
        self._popen = popen
        self._process = None

    def play(self, audio: bytes) -> None:
        """Convert and play WAV bytes; `stop` from another thread ends it early.

        Raises PlaybackError when the bytes are not playable, aplay is
        missing, or aplay fails other than by being stopped.
        """
        wav = convert_to_playback(audio, self._rate)
        try:
            process = self._popen(
                ["aplay", "-q", "-D", self._card, "-t", "wav", "-"],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            raise PlaybackError(
                "aplay not found; install alsa-utils (setup.md 29.3)."
            ) from None
        self._process = process
        stderr = b""
        try:
            _, stderr = process.communicate(input=wav)
        except BrokenPipeError:
            pass  # stopped mid-write; the returncode below is the verdict
        finally:
            self._process = None
        if process.returncode not in _TERMINATED_RETURNCODES:
            detail = _last_line(stderr)
            raise PlaybackError(
                f"aplay exited {process.returncode} on {self._card!r}"
                + (f": {detail}" if detail else ".")
            )

    def stop(self) -> None:
        """Stop playback immediately; safe to call when nothing is playing."""
        process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def is_playing(self) -> bool:
        """Report whether an aplay process is currently running."""
        process = self._process
        return process is not None and process.poll() is None


def _last_line(text: bytes | str | None) -> str:
    """Return the last non-empty line of captured output, or an empty string."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    lines = (text or "").strip().splitlines()
    return lines[-1] if lines else ""


def _stderr_tail(process) -> str:
    """Return the last stderr line of a finished process, or an empty string."""
    stream = getattr(process, "stderr", None)
    if stream is None:
        return ""
    try:
        return _last_line(stream.read())
    except (OSError, ValueError):
        return ""
