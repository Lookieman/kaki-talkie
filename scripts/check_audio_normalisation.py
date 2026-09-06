# v1.0 | 06-Sep-2026 | Expose a non-overwriting owner smoke for audio normalisation.
"""Convert deliberate test audio to WAV for WP2.1 owner validation.

Reads an explicitly selected input and creates one output file. Never overwrites
existing files. Keep recordings and generated outputs outside the Git checkout.
"""

import argparse
import io
import sys
import wave
from pathlib import Path

from kaki_backend.orchestration.audio_normalisation import (
    AudioNormalisationError,
    MAX_INPUT_BYTES,
    normalise_audio,
)


def main() -> int:
    """Validate arguments, create a new WAV and report metadata; return non-zero on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Deliberate test audio to read")
    parser.add_argument("--output", type=Path, required=True, help="New WAV path; parent must exist")
    args = parser.parse_args()
    try:
        with args.input.open("rb") as source:
            converted = normalise_audio(source.read(MAX_INPUT_BYTES + 1))
        with args.output.open("xb") as destination:
            destination.write(converted)
        with wave.open(io.BytesIO(converted), "rb") as recording:
            print(
                f"PASS: {recording.getframerate()} Hz, {recording.getnchannels()} channel, "
                f"{recording.getsampwidth() * 8}-bit PCM, {recording.getnframes()} frames, "
                f"{recording.getnframes() / recording.getframerate():.3f} seconds"
            )
    except (OSError, AudioNormalisationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
