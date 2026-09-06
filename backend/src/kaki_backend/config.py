# v1.0 | 07-Sep-2026 | Select canned or local Whisper STT without loading models.
"""Read explicit STT configuration; retain mode is deliberately not an environment setting."""

import math
import os
from dataclasses import dataclass
from typing import Mapping

from kaki_backend.contracts.ports import SttPort
from kaki_backend.orchestration.canned_ports import CannedSttPort


@dataclass(frozen=True)
class SttSettings:
    """Select the STT port and bounded network waits; canned mode remains the default."""

    mode: str = "canned"
    url: str = "http://127.0.0.1:8080"
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "SttSettings":
        """Read process exports and reject unsupported modes or unbounded timeouts."""
        env = os.environ if environment is None else environment
        mode = env.get("KAKI_STT_MODE", "canned")
        if mode not in {"canned", "whisper"}:
            raise ValueError("KAKI_STT_MODE must be canned or whisper.")
        try:
            timeout = float(env.get("KAKI_STT_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ValueError("KAKI_STT_TIMEOUT_SECONDS must be between 0.1 and 120.") from None
        if not math.isfinite(timeout) or not 0.1 <= timeout <= 120:
            raise ValueError("KAKI_STT_TIMEOUT_SECONDS must be between 0.1 and 120.")
        return cls(mode, env.get("KAKI_WHISPER_URL", "http://127.0.0.1:8080"), timeout)

    def create_port(self) -> SttPort:
        """Construct the selected adapter; perform no inference or readiness I/O."""
        if self.mode == "canned":
            return CannedSttPort()
        from kaki_whisper_cpp.adapter import WhisperStt

        return WhisperStt(self.url, timeout_seconds=self.timeout_seconds)
