# v1.3 | 11-Sep-2026 | Report retrieval readiness; the first grounded probe warms the model.
# v1.2 | 09-Sep-2026 | Report live STT/LLM/TTS readiness alongside status and version.
# v1.1 | 05-Sep-2026 | Include the application version in health responses.
# v1.0 | 02-Sep-2026 | Report availability of the canned backend.

"""Report process health and bounded per-port readiness probes."""

from fastapi import APIRouter, Request  #v1.1

router = APIRouter()


@router.get("/api/health")
def health(request: Request) -> dict[str, object]:  #v1.2
    """Return status, version and live model-port readiness.

    Each readiness probe is bounded by its adapter's short network timeout,
    so a stopped model service turns its flag false without failing health.
    """
    ports = request.app.state.model_ports  #v1.2
    return {
        "status": "ok",
        "version": request.app.version,  #v1.1
        "stt_ready": ports["stt"].ready(),  #v1.2
        "llm_ready": ports["llm"].ready(),  #v1.2
        "tts_ready": ports["tts"].ready(),  #v1.2
        "retrieval_ready": ports["retriever"].ready(),  #v1.3
    }
