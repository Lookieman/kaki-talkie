# v1.0 | 07-Sep-2026 | Release per-turn audio and retain only explicit CLI test inputs.
"""Own mutable request audio; default turns never create retained recordings.

The explicit test-retention capability is passed only by the owner CLI. No
public request field or global retention setting selects it. Releasing buffers
is a lifetime guarantee, not forensic memory erasure.
"""

import os
from pathlib import Path
from uuid import uuid4


class TurnAudio:
    """Own a request buffer shared by the route, service and transcription stage."""

    def __init__(self, data: bytes | bytearray) -> None:
        """Copy caller input into a mutable buffer whose lifetime we control."""
        self.data = bytearray(data)

    def clear(self) -> None:
        """Release the owned payload, including references held by caller frames."""
        self.data.clear()


class TestAudioRetention:
    """Save one explicitly consented test recording outside any Git checkout."""

    def __init__(self, data_root: Path, *, consent: bool) -> None:
        """Validate consent and an absolute external data root; write nothing yet."""
        if consent is not True or not data_root.is_absolute():
            raise ValueError("Test retention needs explicit consent and an absolute data root.")
        self.directory = (data_root / "wp2.2" / "retained").resolve()
        if any((parent / ".git").exists()
               for parent in (self.directory, *self.directory.parents)):
            raise ValueError("Retained test audio must be outside a Git checkout.")
        self.path: Path | None = None

    def save(self, audio: TurnAudio) -> None:
        """Create one private, non-overwriting raw input copy after successful STT.

        File names never incorporate client identifiers. A failed write removes
        only its newly created partial file and propagates the I/O error.
        """
        if self.path is not None:
            raise ValueError("A retention selection can save only one test input.")
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / f"input-{uuid4().hex}.audio"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(audio.data)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        self.path = path
