# v1.0 | 04-Sep-2026 | Provide process-local completed-turn idempotency.

import asyncio

from kaki_backend.contracts.responses import TurnResponse
from kaki_backend.contracts.turn_log import TurnLog
from kaki_backend.orchestration.turn_pipeline import TurnPipeline


class TurnService:
    """Execute each turn_id once and retain its first completed response in memory."""

    def __init__(self, pipeline: TurnPipeline) -> None:
        self._pipeline = pipeline
        self._responses: dict[str, TurnResponse] = {}
        self._logs: list[TurnLog] = []
        self._lock = asyncio.Lock()

    @property
    def logs(self) -> tuple[TurnLog, ...]:
        return tuple(self._logs)

    @property
    def execution_count(self) -> int:
        return self._pipeline.execution_count

    async def process(
        self,
        *,
        device_id: str,
        session_id: str,
        turn_id: str,
        audio: bytes,
        audio_preparation_ms: float,
        request_started_at: float,
    ) -> TurnResponse:
        async with self._lock:
            stored_response = self._responses.get(turn_id)
            if stored_response is not None:
                return stored_response.model_copy(deep=True)

            execution = self._pipeline.execute(
                device_id=device_id,
                session_id=session_id,
                turn_id=turn_id,
                audio=audio,
                audio_preparation_ms=audio_preparation_ms,
                request_started_at=request_started_at,
            )
            self._responses[turn_id] = execution.response.model_copy(deep=True)
            self._logs.append(execution.log)
            return execution.response

    def reset(self) -> None:
        """Clear process-local state for deterministic test isolation."""
        self._responses.clear()
        self._logs.clear()
        self._pipeline.execution_count = 0
