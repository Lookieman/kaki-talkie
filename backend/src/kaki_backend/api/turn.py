# v1.1 | 04-Sep-2026 | Apply in-memory idempotency and timing to canned turns.
# v1.0 | 02-Sep-2026 | Route multipart uploads to canned turn orchestration.

from time import perf_counter  #v1.1
from typing import Annotated

from fastapi import APIRouter, Depends, Request  #v1.1

from kaki_backend.contracts.requests import TurnRequest
from kaki_backend.contracts.responses import TurnResponse
from kaki_backend.orchestration.idempotency import TurnService  #v1.1

router = APIRouter()


def get_turn_service(request: Request) -> TurnService:  #v1.1
    return request.app.state.turn_service  #v1.1


@router.post("/api/device/turn", response_model=TurnResponse)
async def device_turn(  #v1.1
    request: Annotated[TurnRequest, Depends()],  #v1.1
    turn_service: Annotated[TurnService, Depends(get_turn_service)],  #v1.1
) -> TurnResponse:
    request_started_at = perf_counter()  #v1.1
    try:
        audio_read_started_at = perf_counter()  #v1.1
        audio = await request.audio.read()  #v1.1
        audio_preparation_ms = (perf_counter() - audio_read_started_at) * 1000  #v1.1
        return await turn_service.process(  #v1.1
            device_id=request.device_id,  #v1.1
            session_id=request.session_id,  #v1.1
            turn_id=request.turn_id,  #v1.1
            audio=audio,  #v1.1
            audio_preparation_ms=audio_preparation_ms,  #v1.1
            request_started_at=request_started_at,  #v1.1
        )
    finally:
        await request.audio.close()
