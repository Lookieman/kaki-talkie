# v1.4 | 12-Sep-2026 | Drop transcript_redacted; redaction is no longer performed.
# v1.3 | 12-Sep-2026 | Expose the routing intent, refusal reason, redaction and gate audit.
# v1.2 | 12-Sep-2026 | Expose the cited source alongside the retrieval evidence.
# v1.1 | 11-Sep-2026 | Expose retrieval evidence scores and the normalised query.
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
        "intent": log.intent,  #v1.3
        "refusal_reason": log.refusal_reason,  #v1.3
        "transcript": log.transcript,
        "best_dense_score": log.best_dense_score,  #v1.3
        "evidence_min_dense": log.evidence_min_dense,  #v1.3
        "language_evidence": (
            log.stt_language.model_dump() if log.stt_language is not None else None
        ),
        "stt_error": log.stt_error,
        "llm_error": log.llm_error,
        "tts_error": log.tts_error,
        "retrieval_error": log.retrieval_error,  #v1.1
        "normalised_query": log.normalised_query,  #v1.1
        "cited_source_id": log.cited_source_id,  #v1.2
        "llm_cited_index": log.llm_cited_index,  #v1.2
        "retrieval_evidence": [  #v1.1
            record.model_dump() for record in log.retrieval_evidence
        ],
        "timings_ms": log.timings.model_dump(),
    }
