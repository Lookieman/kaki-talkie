# v1.4 | 12-Sep-2026 | Read the WP3.4 evidence-gate threshold from the environment.
# v1.3 | 11-Sep-2026 | Select canned or rag retrieval and the query-normalise switch.
# v1.2 | 09-Sep-2026 | Select canned or macOS say speech alongside the STT and LLM choices.
# v1.1 | 09-Sep-2026 | Select canned or local Qwen generation alongside the STT choice.
# v1.0 | 07-Sep-2026 | Select canned or local Whisper STT without loading models.
"""Read explicit STT/LLM/TTS configuration; retain mode is deliberately not an environment setting."""

import math
import os
from dataclasses import dataclass
from typing import Mapping

from kaki_backend.contracts.ports import LlmPort, RetrieverPort, SttPort, TtsPort
from kaki_backend.orchestration.canned_ports import (
    CannedLlmPort,
    CannedRetrieverPort,  #v1.3
    CannedSttPort,
    CannedTtsPort,
)

APPROVED_QWEN_MODEL = "mlx-community/Qwen3-8B-4bit"
APPROVED_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"  #v1.3
# The WP3.4 evidence gate. Calibrated 12-Sep-2026 on the four-source corpus:
# supported questions scored 0.63-0.86 best dense cosine, unsupported ones
# 0.24-0.43, so 0.50 sits in the gap (runbook 8.1 WP3.4).
DEFAULT_EVIDENCE_MIN_DENSE = 0.50  #v1.4


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


def _evidence_threshold(env: Mapping[str, str]) -> float:  #v1.4
    """Parse the evidence-gate threshold as a finite similarity between 0 and 1."""
    message = "KAKI_EVIDENCE_MIN_DENSE must be a number between 0 and 1."
    try:
        threshold = float(env.get("KAKI_EVIDENCE_MIN_DENSE", DEFAULT_EVIDENCE_MIN_DENSE))
    except ValueError:
        raise ValueError(message) from None
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError(message)
    return threshold


@dataclass(frozen=True)
class RetrievalSettings:  #v1.3
    """Select the retriever port; canned (no retrieval) remains the default.

    `rag` mode reads the WP3.1 processed corpus and the WP3.2 persistent
    Chroma collection under `KAKI_DATA_ROOT`, loading the approved embedding
    model in the backend process behind the port. `normalise` controls the
    WP3.3 query-rewrite step so the latency script can compare both paths.
    `evidence_min_dense` is the WP3.4 refusal gate; it is recorded on every
    turn alongside the score it judged, so evidence stays interpretable
    after a re-tune.
    """  #v1.4

    mode: str = "canned"
    data_root: str = ""
    normalise: bool = True
    embedding_model: str = APPROVED_EMBEDDING_MODEL
    evidence_min_dense: float = DEFAULT_EVIDENCE_MIN_DENSE  #v1.4

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "RetrievalSettings":
        """Read process exports; reject unknown modes and a missing data root."""
        env = os.environ if environment is None else environment
        mode = env.get("KAKI_RETRIEVAL_MODE", "canned")
        if mode not in {"canned", "rag"}:
            raise ValueError("KAKI_RETRIEVAL_MODE must be canned or rag.")
        normalise = env.get("KAKI_QUERY_NORMALISE", "on")
        if normalise not in {"on", "off"}:
            raise ValueError("KAKI_QUERY_NORMALISE must be on or off.")
        data_root = env.get("KAKI_DATA_ROOT", "")
        if mode == "rag" and not os.path.isabs(data_root):
            raise ValueError(
                "KAKI_RETRIEVAL_MODE=rag requires an absolute KAKI_DATA_ROOT (runbook 8.1)."
            )
        model = env.get("KAKI_EMBEDDING_MODEL", APPROVED_EMBEDDING_MODEL)
        return cls(
            mode, data_root, normalise == "on", model,
            _evidence_threshold(env),  #v1.4
        )

    @property
    def active(self) -> bool:
        """True when real retrieval is configured for this process."""
        return self.mode == "rag"

    def create_port(self) -> RetrieverPort:
        """Construct the selected retriever; perform no loading or model I/O."""
        if self.mode == "canned":
            return CannedRetrieverPort()
        from kaki_rag.adapter import KakiRagRetriever

        return KakiRagRetriever(self.data_root, model_id=self.embedding_model)


@dataclass(frozen=True)
class TtsSettings:
    """Select the TTS port and bounded synthesis waits; canned mode remains the default."""

    mode: str = "canned"
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "TtsSettings":
        """Read process exports and reject unsupported modes or unbounded timeouts."""
        env = os.environ if environment is None else environment
        mode = env.get("KAKI_TTS_MODE", "canned")
        if mode not in {"canned", "say"}:
            raise ValueError("KAKI_TTS_MODE must be canned or say.")
        timeout = _bounded_timeout(env, "KAKI_TTS_TIMEOUT_SECONDS", "30", 120)
        return cls(mode, timeout)

    def create_port(self) -> TtsPort:
        """Construct the selected adapter; perform no synthesis or readiness I/O."""
        if self.mode == "canned":
            return CannedTtsPort()
        from kaki_say_tts.adapter import SayTts

        return SayTts(timeout_seconds=self.timeout_seconds)
