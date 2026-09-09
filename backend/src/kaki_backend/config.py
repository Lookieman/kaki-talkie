# v1.1 | 09-Sep-2026 | Select canned or local Qwen generation alongside the STT choice.
# v1.0 | 07-Sep-2026 | Select canned or local Whisper STT without loading models.
"""Read explicit STT/LLM configuration; retain mode is deliberately not an environment setting."""

import math
import os
from dataclasses import dataclass
from typing import Mapping

from kaki_backend.contracts.ports import LlmPort, SttPort
from kaki_backend.orchestration.canned_ports import CannedLlmPort, CannedSttPort

APPROVED_QWEN_MODEL = "mlx-community/Qwen3-8B-4bit"


def _bounded_timeout(env: Mapping[str, str], name: str, default: str, upper: float) -> float:
    """Parse a finite timeout export within 0.1 and the given upper bound."""
    message = f"{name} must be between 0.1 and {upper:g}."
    try:
        timeout = float(env.get(name, default))
    except ValueError:
        raise ValueError(message) from None
    if not math.isfinite(timeout) or not 0.1 <= timeout <= upper:
        raise ValueError(message)
    return timeout


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
        timeout = _bounded_timeout(env, "KAKI_STT_TIMEOUT_SECONDS", "30", 120)
        return cls(mode, env.get("KAKI_WHISPER_URL", "http://127.0.0.1:8080"), timeout)

    def create_port(self) -> SttPort:
        """Construct the selected adapter; perform no inference or readiness I/O."""
        if self.mode == "canned":
            return CannedSttPort()
        from kaki_whisper_cpp.adapter import WhisperStt

        return WhisperStt(self.url, timeout_seconds=self.timeout_seconds)


@dataclass(frozen=True)
class LlmSettings:
    """Select the LLM port and bounded network waits; canned mode remains the default."""

    mode: str = "canned"
    url: str = "http://127.0.0.1:8082"
    timeout_seconds: float = 120.0

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "LlmSettings":
        """Read process exports and reject unsupported modes or unbounded timeouts."""
        env = os.environ if environment is None else environment
        mode = env.get("KAKI_LLM_MODE", "canned")
        if mode not in {"canned", "qwen"}:
            raise ValueError("KAKI_LLM_MODE must be canned or qwen.")
        timeout = _bounded_timeout(env, "KAKI_LLM_TIMEOUT_SECONDS", "120", 300)
        return cls(mode, env.get("KAKI_LLM_URL", "http://127.0.0.1:8082"), timeout)

    def create_port(self) -> LlmPort:
        """Construct the selected adapter; perform no inference or readiness I/O."""
        if self.mode == "canned":
            return CannedLlmPort()
        from kaki_qwen_local.adapter import QwenLlm

        return QwenLlm(self.url, model=APPROVED_QWEN_MODEL, timeout_seconds=self.timeout_seconds)
