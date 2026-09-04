# v1.0 | 02-Sep-2026 | Define device-turn output, states and source provenance.

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class TurnState(str, Enum):
    ANSWERED = "answered"
    REFUSED = "refused"
    HANDED_OFF = "handed_off"
    ACTED = "acted"
    FAILED = "failed"


class SourceRecord(BaseModel):
    """Application-derived provenance; canned responses have no source records."""

    source_url: str
    page_title: str
    captured_at: datetime
    source_updated_at: date | None = None
    content_hash: str | None = None


class TurnResponse(BaseModel):
    """Shared device response; unavailable audio and case references are null."""

    turn_id: str
    reply_audio: str | None
    reply_text: str
    display_text: str
    slip_text: str
    language: str
    state: TurnState
    case_id: str | None
    sources: list[SourceRecord]
