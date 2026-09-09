# v1.0 | 09-Sep-2026 | Expose the most recent turn's diagnostics for the protected debug view.
"""Serve the design section 13 debug/test view of the last completed turn.

The route returns only the newest in-memory turn log: transcript, language
evidence, state, safe stage error codes and stage timings. It never returns
audio. FastAPI itself binds to loopback only; remote access exists solely
through the protected `/api/device/*` path.
"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/device/debug/last-turn")
def last_turn(request: Request) -> dict[str, object]:
    """Return the newest turn's diagnostics or a controlled 404 before any turn."""
    logs = request.app.state.turn_service.logs
    if not logs:
        raise HTTPException(status_code=404, detail="No completed turns yet.")
    log = logs[-1]
    return {
        "turn_id": log.turn_id,
        "state": log.state.value,
        "transcript": log.transcript,
        "language_evidence": (
            log.stt_language.model_dump() if log.stt_language is not None else None
        ),
        "stt_error": log.stt_error,
        "llm_error": log.llm_error,
        "tts_error": log.tts_error,
        "timings_ms": log.timings.model_dump(),
    }
