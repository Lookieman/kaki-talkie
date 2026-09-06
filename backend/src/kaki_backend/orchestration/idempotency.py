# v1.1 | 07-Sep-2026 | Keep STT off the event loop and preserve idempotency on cancellation.
# v1.0 | 04-Sep-2026 | Provide process-local completed-turn idempotency.

"""Serialise turns through completed execution, including a disconnected caller.

Blocking model I/O runs in a worker. Cancellation waits for that bounded worker
before releasing the lock, so a retry cannot execute the same turn concurrently.
"""

import asyncio

from kaki_backend.contracts.responses import TurnResponse
from kaki_backend.contracts.turn_log import TurnLog
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.orchestration.audio_lifecycle import TestAudioRetention, TurnAudio


class TurnService:
    """Execute each turn_id once and retain its first completed response in memory."""

    def __init__(self, pipeline: TurnPipeline) -> None:
        """Own a pipeline and its process-local completion cache."""
        self._pipeline = pipeline
        self._responses: dict[str, TurnResponse] = {}
        self._logs: list[TurnLog] = []
        self._lock = asyncio.Lock()

    @property
    def logs(self) -> tuple[TurnLog, ...]:
        """Expose internal diagnostics for tests; audio and transcript are excluded."""
        return tuple(self._logs)

    @property
    def execution_count(self) -> int:
        """Return the number of first executions, excluding cached retries."""
        return self._pipeline.execution_count

    async def process(
        self,
        *,
        device_id: str,
        session_id: str,
        turn_id: str,
        audio: bytes | TurnAudio,
        audio_preparation_ms: float,
        request_started_at: float,
        retention: TestAudioRetention | None = None,
    ) -> TurnResponse:
        """Return the first result once; release request audio even for queued/cached turns.

        Retention is an internal capability for an explicitly consented CLI test,
        not an option exposed by the public HTTP route.
        """
        owned = audio if isinstance(audio, TurnAudio) else TurnAudio(audio)
        del audio
        try:
            async with self._lock:
                stored_response = self._responses.get(turn_id)
                if stored_response is not None:
                    return stored_response.model_copy(deep=True)
                job = asyncio.create_task(asyncio.to_thread(
                    self._pipeline.execute,
                    device_id=device_id, session_id=session_id, turn_id=turn_id,
                    audio=owned, audio_preparation_ms=audio_preparation_ms,
                    request_started_at=request_started_at, retention=retention,
                ))
                cancelled = False
                while not job.done():
                    try:
                        await asyncio.shield(job)
                    except asyncio.CancelledError:
                        cancelled = True
                execution = job.result()
                self._responses[turn_id] = execution.response.model_copy(deep=True)
                self._logs.append(execution.log)
                if cancelled:
                    raise asyncio.CancelledError
                return execution.response
        finally:
            owned.clear()

    def reset(self) -> None:
        """Clear process-local state for deterministic test isolation."""
        self._responses.clear()
        self._logs.clear()
        self._pipeline.execution_count = 0
