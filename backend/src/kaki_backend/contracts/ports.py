# v1.2 | 09-Sep-2026 | Carry LLM readiness and safe generation failures behind the port.
# v1.1 | 07-Sep-2026 | Carry typed STT evidence and safe failures behind the port.
# v1.0 | 04-Sep-2026 | Define replaceable WP1 inference and retrieval ports.

"""Define internal model ports without changing the public device contract."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from kaki_backend.contracts.responses import SourceRecord


class LanguageEvidence(BaseModel):
    """Preserve runtime language evidence; it is not the reply-language policy."""

    model_config = ConfigDict(frozen=True, strict=True)
    language: str = Field(min_length=1, max_length=64)
    probability: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class Transcription(BaseModel):
    """Return recognised text and optional genuine language evidence internally."""

    model_config = ConfigDict(frozen=True, strict=True)
    text: str = Field(min_length=1, max_length=16384)
    evidence: LanguageEvidence | None = None


class SttError(RuntimeError):
    """Indicate a controlled STT failure without retaining a vendor response."""

    def __init__(self, code: str) -> None:
        """Restrict diagnostics to safe codes rather than audio or response text."""
        self.code = code if code in {
            "unavailable", "timeout", "invalid_response", "empty_transcript", "invalid_audio"
        } else "unavailable"
        super().__init__(self.code)


class SttPort(Protocol):
    """Transcribe normalised audio and report readiness behind a runtime boundary."""

    def transcribe(self, audio: bytes) -> Transcription:
        """Return recognition evidence for 16 kHz mono PCM WAV or raise SttError."""

    def ready(self) -> bool:
        """Check current runtime readiness without transcribing or loading a model."""


class LlmError(RuntimeError):
    """Indicate a controlled generation failure without retaining a vendor response."""

    def __init__(self, code: str) -> None:
        """Restrict diagnostics to safe codes rather than transcripts or response text."""
        self.code = code if code in {
            "unavailable", "timeout", "invalid_response", "empty_reply"
        } else "unavailable"
        super().__init__(self.code)


class LlmPort(Protocol):
    """Generate conversational text independently of the selected model runtime."""
    def generate(self, transcript: str) -> str:
        """Return conversational response text for the current turn or raise LlmError."""

    def ready(self) -> bool:
        """Check current runtime readiness without generating or loading a model."""


class TtsPort(Protocol):
    """Provide speech output independently of the selected speech engine."""
    def synthesize(self, reply_text: str) -> str | None:
        """Return an audio reference when speech output is available."""


class RetrieverPort(Protocol):
    """Retrieve application-owned evidence independently of its storage engine."""
    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[SourceRecord, ...]:
        """Return application-owned evidence provenance for a bounded query."""
