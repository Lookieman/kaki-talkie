# v1.0 | 04-Sep-2026 | Define deterministic WP1 turn timing and log records.

from pydantic import BaseModel

from kaki_backend.contracts.responses import TurnResponse, TurnState


class TurnTimings(BaseModel):
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
    turn_id: str
    device_id: str
    session_id: str
    state: TurnState
    timings: TurnTimings


class TurnExecution(BaseModel):
    response: TurnResponse
    log: TurnLog
