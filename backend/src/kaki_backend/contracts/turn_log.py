# v1.7 | 12-Sep-2026 | Drop transcript_redacted; redaction is no longer performed.
# v1.6 | 12-Sep-2026 | Record the routing intent, refusal reason, redaction and gate audit.
# v1.5 | 12-Sep-2026 | Keep evidence in retrieval rank order and record the cited source.
# v1.4 | 11-Sep-2026 | Record query-rewrite timing and evidence scores for WP3.4 thresholds.
# v1.3 | 09-Sep-2026 | Retain the transcript and TTS failure code for the protected debug view.
# v1.2 | 09-Sep-2026 | Record safe LLM failure codes alongside the STT diagnostics.
# v1.1 | 07-Sep-2026 | Record STT evidence and safe codes without audio or transcript logs.
# v1.0 | 04-Sep-2026 | Define deterministic WP1 turn timing and log records.

"""Keep internal stage diagnostics separate from the unchanged public response."""

from pydantic import BaseModel

from kaki_backend.contracts.responses import TurnResponse, TurnState
from kaki_backend.contracts.ports import LanguageEvidence


class TurnTimings(BaseModel):
    """Record elapsed milliseconds; stages not invoked remain null."""
    audio_preparation_ms: float
    stt_ms: float | None = None
    routing_ms: float | None = None
    query_rewrite_ms: float | None = None  #v1.4
    retrieval_ms: float | None = None
    live_lookup_ms: float | None = None
    llm_ms: float | None = None
    tts_ms: float | None = None
    overall_ms: float | None = None
    time_to_first_audio_ms: float | None = None


class EvidenceScore(BaseModel):  #v1.4
    """One retrieved chunk's diagnostic scores for the protected debug view.

    WP3.4 derives refusal/no-coverage thresholds from these real numbers;
    no chunk text is retained here. `retrieval_rank` is the 1-based position
    the retriever returned, preserved even when the response reorders its
    sources, so the WP4 `turn_sources` table can persist true retrieval order.
    """
    chunk_id: str
    source_id: str
    retrieval_rank: int  #v1.5
    fused_score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    cited: bool = False  #v1.5


class TurnLog(BaseModel):
    """Store safe in-memory diagnostics; the transcript feeds the protected debug view.

    Audio is never retained here. The transcript is application data by design
    (the debug/test view shows it and WP4 persists it); no other recognised
    content or vendor payload is kept.
    """
    turn_id: str
    device_id: str
    session_id: str
    state: TurnState
    timings: TurnTimings
    transcript: str | None = None  #v1.3
    intent: str | None = None  #v1.6
    refusal_reason: str | None = None  #v1.6
    # The score the evidence gate judged and the threshold it judged against.
    # Both are recorded so captured evidence stays interpretable after a
    # re-tune of KAKI_EVIDENCE_MIN_DENSE (runbook 8.1 WP3.4).
    best_dense_score: float | None = None  #v1.6
    evidence_min_dense: float | None = None  #v1.6
    stt_language: LanguageEvidence | None = None
    stt_error: str | None = None
    llm_error: str | None = None  #v1.2
    tts_error: str | None = None  #v1.3
    retrieval_error: str | None = None  #v1.4
    normalised_query: str | None = None  #v1.4
    # Always in retrieval rank order; the response may present its sources
    # cited-first, but the diagnostic record keeps what retrieval actually did.
    retrieval_evidence: list[EvidenceScore] = []  #v1.4
    cited_source_id: str | None = None  #v1.5
    llm_cited_index: int | None = None  #v1.5


class TurnExecution(BaseModel):
    """Return the public reply together with its internal diagnostics."""
    response: TurnResponse
    log: TurnLog
