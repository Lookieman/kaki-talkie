# v1.7 | 13-Sep-2026 | WP5.1: expose the reply language, mode, render outcome and rewrite audit.
# v1.6 | 13-Sep-2026 | Expose the action's previous turn and its outcome.
# v1.5 | 13-Sep-2026 | Read the newest stored turn and expose its replay history.
# v1.4 | 12-Sep-2026 | Drop transcript_redacted; redaction is no longer performed.
# v1.3 | 12-Sep-2026 | Expose the routing intent, refusal reason, redaction and gate audit.
# v1.2 | 12-Sep-2026 | Expose the cited source alongside the retrieval evidence.
# v1.1 | 11-Sep-2026 | Expose retrieval evidence scores and the normalised query.
# v1.0 | 09-Sep-2026 | Expose the most recent turn's diagnostics for the protected debug view.
"""Serve the design section 13 debug/test view of the last completed turn.

The route returns only the newest stored turn: transcript, language evidence,
state, safe stage error codes, stage timings and its replay history. It reads
SQLite, so it answers after a backend restart. It never returns audio. FastAPI itself binds to loopback only; remote access exists solely
through the protected `/api/device/*` path.
"""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/device/debug/last-turn")
def last_turn(request: Request) -> dict[str, object]:
    """Return the newest turn's diagnostics or a controlled 404 before any turn."""
    stored = request.app.state.turn_service.last_turn()  #v1.5
    if stored is None:
        raise HTTPException(status_code=404, detail="No completed turns yet.")
    log = stored.log  #v1.5
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
        # WP5.1: Malay retrieval depends on the rewrite, so its presence and
        # duration are shown directly (runbook 10.1 WP5.1).
        "rewrite_present": log.normalised_query is not None,  #v1.7
        "rewrite_ms": log.timings.query_rewrite_ms,  #v1.7
        "reply_language": log.reply_language,  #v1.7
        "reply_mode": log.reply_mode,  #v1.7
        "render_outcome": log.render_outcome,  #v1.7
        "cited_source_id": log.cited_source_id,  #v1.2
        "llm_cited_index": log.llm_cited_index,  #v1.2
        "retrieval_evidence": [  #v1.1
            record.model_dump() for record in log.retrieval_evidence
        ],
        "previous_turn_id": log.previous_turn_id,  #v1.6
        "action_outcome": log.action_outcome,  #v1.6
        "timings_ms": log.timings.model_dump(),
        "replay_count": stored.replay_count,  #v1.5
        "completed_at": stored.completed_at,  #v1.5
        "schema_version": request.app.state.database.schema_version(),  #v1.5
    }
