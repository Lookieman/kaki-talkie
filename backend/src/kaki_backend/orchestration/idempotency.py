# v1.2 | 13-Sep-2026 | Replace the process-memory cache with the durable SQLite turn store.
# v1.1 | 07-Sep-2026 | Keep STT off the event loop and preserve idempotency on cancellation.
# v1.0 | 04-Sep-2026 | Provide process-local completed-turn idempotency.

"""Serialise turns through completed execution, including a disconnected caller.

Blocking model I/O runs in a worker. Cancellation waits for that bounded worker
before releasing the lock, so a retry cannot execute the same turn concurrently.

The durable turn store is the only idempotency record (WP4-AT-03): a turn_id
already stored, including one completed before a backend restart, is served
from SQLite and calls no port. A turn is stored before its response returns,
so only a completed turn is idempotent; a crash before the commit leaves no
row and the client's retry executes again. The lock remains because the store
guarantees durability, not in-flight de-duplication of concurrent requests.
"""

import asyncio

from kaki_backend.contracts.responses import TurnResponse
from kaki_backend.contracts.turn_log import TurnLog
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.orchestration.audio_lifecycle import TestAudioRetention, TurnAudio
from kaki_backend.persistence.repositories import StoredTurn, TurnRepository  #v1.2


class TurnService:
    """Execute each turn_id once and serve every later request for it from the turn store."""

    def __init__(self, pipeline: TurnPipeline, turns: TurnRepository) -> None:  #v1.2
        """Own a pipeline and the durable store that records its completed turns."""
        self._pipeline = pipeline
        self._turns = turns  #v1.2
        self._logs: list[TurnLog] = []
        self._lock = asyncio.Lock()

    @property
    def logs(self) -> tuple[TurnLog, ...]:
        """Expose this process's executed-turn diagnostics for tests; audio is excluded."""
        return tuple(self._logs)

    @property
    def execution_count(self) -> int:
        """Return the number of first executions, excluding stored replays."""
        return self._pipeline.execution_count

    def last_turn(self) -> StoredTurn | None:  #v1.2
        """Return the most recently executed stored turn, surviving restarts."""
        return self._turns.newest()

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
        """Return the stored result once; release request audio even for queued/replayed turns.

        Side effects: a first execution writes the completed turn to SQLite
        before returning; a replay increments its stored replay count. A
        storage failure propagates, so the client's retry executes again.

        Retention is an internal capability for an explicitly consented CLI test,
        not an option exposed by the public HTTP route.
        """
        owned = audio if isinstance(audio, TurnAudio) else TurnAudio(audio)
        del audio
        try:
            async with self._lock:
                stored_response = self._turns.replay(turn_id)  #v1.2
                if stored_response is not None:
                    return stored_response
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
                self._turns.record(execution)  #v1.2
                self._logs.append(execution.log)
                if cancelled:
                    raise asyncio.CancelledError
                return execution.response
        finally:
            owned.clear()

    def reset(self) -> None:
        """Clear stored turns and process-local state for deterministic test isolation."""
        self._turns.clear()  #v1.2
        self._logs.clear()
        self._pipeline.execution_count = 0
