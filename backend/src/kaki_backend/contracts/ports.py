# v1.6 | 12-Sep-2026 | Carry the model's no-coverage signal on the grounded reply.
# v1.5 | 12-Sep-2026 | Return the cited evidence block from grounded generation.
# v1.4 | 11-Sep-2026 | Carry evidence text and scores through retrieval; ground generation.
# v1.3 | 09-Sep-2026 | Carry TTS readiness and safe synthesis failures behind the port.
# v1.2 | 09-Sep-2026 | Carry LLM readiness and safe generation failures behind the port.
# v1.1 | 07-Sep-2026 | Carry typed STT evidence and safe failures behind the port.
# v1.0 | 04-Sep-2026 | Define replaceable WP1 inference and retrieval ports.

"""Define internal model ports without changing the public device contract."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator  #v1.6

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


class GroundedReply(BaseModel):  #v1.5
    """A grounded answer together with the evidence block the model used.

    `text` already has the citation marker removed, so it is safe to speak
    and display; the marker must never reach the kiosk. `cited_index` is the
    1-based position in the evidence list passed to generation, or None when
    the model returned no usable citation and the caller must fall back.

    `no_coverage` reports that the model judged the supplied evidence unable
    to answer the question. It takes precedence over any text: the caller
    refuses with fixed wording rather than speaking a partial answer beside
    a no-coverage signal, so `text` is empty in that case. Evidence blocks
    are numbered from one precisely so that zero can carry this meaning
    unambiguously.
    """  #v1.6

    model_config = ConfigDict(frozen=True, strict=True)
    text: str = Field(default="", max_length=16384)  #v1.6
    cited_index: int | None = Field(default=None, ge=1)
    no_coverage: bool = False  #v1.6

    @model_validator(mode="after")  #v1.6
    def _answer_must_have_text(self) -> "GroundedReply":
        """Keep an answering reply non-empty; only a refusal may carry no text."""
        if not self.no_coverage and not self.text.strip():
            raise ValueError("A grounded reply must have text unless it reports no coverage.")
        return self


class LlmPort(Protocol):
    """Generate conversational text independently of the selected model runtime."""
    def generate(self, transcript: str) -> str:  #v1.5
        """Return conversational response text for the current turn or raise LlmError."""

    def generate_grounded(self, transcript: str, *, evidence: str) -> GroundedReply:  #v1.5
        """Answer strictly from `evidence` and report which block was used.

        `evidence` is preformatted application-retrieved context, numbered
        from one; it is reference data and never instructions to the model.
        Raises LlmError for blank or oversized input and on any transport or
        parsing failure.
        """

    def rewrite_query(self, transcript: str) -> str:  #v1.4
        """Return a concise normalised English search query or raise LlmError.

        Bounded tightly (small completion, short timeout); callers degrade to
        original-only retrieval on failure rather than failing the turn.
        """

    def ready(self) -> bool:
        """Check current runtime readiness without generating or loading a model."""


class TtsError(RuntimeError):
    """Indicate a controlled synthesis failure without retaining engine output."""

    def __init__(self, code: str) -> None:
        """Restrict diagnostics to safe codes rather than reply text or engine errors."""
        self.code = code if code in {
            "unavailable", "timeout", "invalid_text", "invalid_output"
        } else "unavailable"
        super().__init__(self.code)


class TtsPort(Protocol):
    """Provide speech output independently of the selected speech engine."""
    def synthesize(self, reply_text: str) -> str | None:
        """Return an audio reference when speech output is available or raise TtsError."""

    def ready(self) -> bool:
        """Check current engine readiness without synthesising speech."""


class EvidenceChunk(BaseModel):  #v1.4
    """One retrieved evidence unit: clean text plus application-owned provenance.

    Scores are diagnostic (dense cosine similarity and lexical BM25 where the
    path found the chunk); WP3.4 derives refusal thresholds from them. The
    `source` record is the only origin of user-facing URLs and dates.
    """

    model_config = ConfigDict(frozen=True)
    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    heading_path: tuple[str, ...] = ()
    text: str = Field(min_length=1)
    source: SourceRecord
    fused_score: float
    dense_score: float | None = None
    lexical_score: float | None = None


class RetrieverPort(Protocol):
    """Retrieve application-owned evidence independently of its storage engine."""
    def retrieve(
        self, original_query: str, normalized_query: str | None
    ) -> tuple[EvidenceChunk, ...]:  #v1.4
        """Return ranked evidence with provenance for a bounded query."""

    def ready(self) -> bool:  #v1.4
        """Check that the evidence store (and its embedder) is usable."""
