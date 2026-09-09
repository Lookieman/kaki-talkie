# v1.5 | 09-Sep-2026 | Configure the TTS port, health readiness and the debug view route.
# v1.4 | 09-Sep-2026 | Configure the LLM port while preserving localhost and canned defaults.
# v1.3 | 07-Sep-2026 | Configure the STT port while preserving localhost and canned defaults.
# v1.2 | 05-Sep-2026 | Provide the explicit localhost-only WP1 launcher.
# v1.1 | 04-Sep-2026 | Register pending and initialise WP1.2 turn semantics.
# v1.0 | 02-Sep-2026 | Bootstrap the backend with health and canned turn routes.

"""Bootstrap the local orchestrator; model processes are started independently."""

from fastapi import FastAPI

from kaki_backend.api.debug import router as debug_router  #v1.5
from kaki_backend.api.health import router as health_router
from kaki_backend.api.pending import router as pending_router  #v1.1
from kaki_backend.api.turn import router as turn_router
from kaki_backend.orchestration.idempotency import TurnService  #v1.1
from kaki_backend.orchestration.turn_pipeline import TurnPipeline  #v1.1
from kaki_backend.config import LlmSettings, SttSettings, TtsSettings

app = FastAPI(title="KaKi-Talkie", version="0.1.0")
app.state.model_ports = {  #v1.5
    "stt": SttSettings.from_environment().create_port(),
    "llm": LlmSettings.from_environment().create_port(),  #v1.4
    "tts": TtsSettings.from_environment().create_port(),  #v1.5
}
app.state.turn_service = TurnService(TurnPipeline(  #v1.4
    stt=app.state.model_ports["stt"],
    llm=app.state.model_ports["llm"],  #v1.4
    tts=app.state.model_ports["tts"],  #v1.5
))
app.include_router(health_router)
app.include_router(pending_router)  #v1.1
app.include_router(turn_router)
app.include_router(debug_router)  #v1.5


def run() -> None:  #v1.2
    """Start FastAPI on loopback regardless of generic Uvicorn environment settings."""
    import uvicorn  #v1.2

    uvicorn.run(app, host="127.0.0.1", port=8000)  #v1.2


if __name__ == "__main__":  #v1.2
    run()  #v1.2
