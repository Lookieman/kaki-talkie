# v1.0 | 06-Sep-2026 | Decode bounded uploads to in-memory 16 kHz mono PCM WAV.
"""Normalise uploaded audio without retaining recordings or invoking inference."""

import io
import wave

import av

SAMPLE_RATE = 16000
MAX_INPUT_BYTES = 8 * 1024 * 1024
# Allow recorder/container rounding beyond the client's 15-second cap.
MAX_SECONDS = 16
MAX_SAMPLES = SAMPLE_RATE * MAX_SECONDS


class AudioNormalisationError(ValueError):
    """Indicate empty, unsupported, malformed or oversized audio input."""


def normalise_audio(audio: bytes) -> bytes:
    """Return mono 16-bit PCM WAV; reject unusable or over-limit input.

    Decode only the first audio stream. Input and output remain in memory;
    filenames, external URLs and model services are never passed to the decoder.
    """
    if not audio or len(audio) > MAX_INPUT_BYTES:
        raise AudioNormalisationError("Audio is empty or exceeds the 8 MiB input limit.")
    pcm = bytearray()
    try:
        options = {"protocol_whitelist": "pipe", "format_whitelist": "wav,matroska,webm,ogg,mov"}
        with av.open(io.BytesIO(audio), options=options) as source:
            if not source.streams.audio:
                raise AudioNormalisationError("No audio stream was found.")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
            for frame in source.decode(source.streams.audio[0]):
                for converted in resampler.resample(frame):
                    _append_pcm(pcm, converted)
            for converted in resampler.resample(None):
                _append_pcm(pcm, converted)
    except (av.FFmpegError, ValueError, OverflowError) as exc:
        raise AudioNormalisationError("Audio could not be decoded within the input limits.") from exc
    if not pcm:
        raise AudioNormalisationError("Audio contains no samples.")
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(SAMPLE_RATE)
        recording.writeframes(pcm)
    return output.getvalue()


def _append_pcm(pcm: bytearray, frame: av.AudioFrame) -> None:
    """Copy sample bytes without FFmpeg plane padding and bound decoded duration."""
    size = frame.samples * 2
    if len(pcm) + size > MAX_SAMPLES * 2:
        raise AudioNormalisationError("Audio exceeds the 16-second decoding limit.")
    pcm.extend(bytes(frame.planes[0])[:size])
