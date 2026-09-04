# v1.0 | 02-Sep-2026 | Route multipart uploads to canned turn orchestration.

from typing import Annotated

from fastapi import APIRouter, Depends

from kaki_backend.contracts.requests import TurnRequest
from kaki_backend.contracts.responses import TurnResponse
from kaki_backend.orchestration.turn_pipeline import create_canned_turn

router = APIRouter()


@router.post("/api/device/turn", response_model=TurnResponse)
async def device_turn(request: Annotated[TurnRequest, Depends()]) -> TurnResponse:
    try:
        first_byte = await request.audio.read(1)
        return create_canned_turn(request.turn_id, has_audio=bool(first_byte))
    finally:
        await request.audio.close()
