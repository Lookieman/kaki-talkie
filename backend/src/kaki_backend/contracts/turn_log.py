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
    retrieval_ms: float | None = None
    live_lookup_ms: float | None = None
    llm_ms: float | None = None
    tts_ms: float | None = None
    overall_ms: float | None = None
    time_to_first_audio_ms: float | None = None


class TurnLog(BaseModel):
    """Store safe in-memory diagnostics without retaining arbitrary recognised secrets."""
    turn_id: str
    device_id: str
    session_id: str
    state: TurnState
    timings: TurnTimings
    stt_language: LanguageEvidence | None = None
    stt_error: str | None = None


class TurnExecution(BaseModel):
    """Return the public reply together with its internal diagnostics."""
    response: TurnResponse
    log: TurnLog
