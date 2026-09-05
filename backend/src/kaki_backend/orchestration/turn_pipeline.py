# v1.2 | 05-Sep-2026 | Add fixture-labelled receipts and prerecorded failure audio.
# v1.1 | 04-Sep-2026 | Compose canned ports and record complete WP1 timing shape.
# v1.0 | 02-Sep-2026 | Return deterministic canned turns without inference or state.

from time import perf_counter  #v1.1

from kaki_backend.contracts.ports import LlmPort, RetrieverPort, SttPort, TtsPort  #v1.1
from kaki_backend.contracts.responses import TurnResponse, TurnState
from kaki_backend.contracts.turn_log import TurnExecution, TurnLog, TurnTimings  #v1.1
from kaki_backend.orchestration.canned_ports import (  #v1.1
    CannedLlmPort,
    CannedRetrieverPort,
    CannedSttPort,
    CannedTtsPort,
    canned_audio,  #v1.2
)


class TurnPipeline:  #v1.1
    """Run the deterministic WP1 path behind replaceable model ports."""  #v1.1

    def __init__(  #v1.1
        self,
        stt: SttPort | None = None,
        llm: LlmPort | None = None,
        tts: TtsPort | None = None,
        retriever: RetrieverPort | None = None,
    ) -> None:
        self._stt = stt or CannedSttPort()  #v1.1
        self._llm = llm or CannedLlmPort()  #v1.1
        self._tts = tts or CannedTtsPort()  #v1.1
        self._retriever = retriever or CannedRetrieverPort()  #v1.1
        self.execution_count = 0  #v1.1

    def execute(  #v1.1
        self,
        *,
        device_id: str,
        session_id: str,
        turn_id: str,
        audio: bytes,
        audio_preparation_ms: float,
        request_started_at: float,
    ) -> TurnExecution:
        self.execution_count += 1  #v1.1
        timings = TurnTimings(audio_preparation_ms=audio_preparation_ms)  #v1.1

        if not audio:  #v1.1
            response = self._failed_response(turn_id)  #v1.1
        else:
            stt_started_at = perf_counter()  #v1.1
            transcript = self._stt.transcribe(audio)  #v1.1
            timings.stt_ms = (perf_counter() - stt_started_at) * 1000  #v1.1

            routing_started_at = perf_counter()  #v1.1
            language = "en"  #v1.1
            timings.routing_ms = (perf_counter() - routing_started_at) * 1000  #v1.1

            llm_started_at = perf_counter()  #v1.1
            reply_text = self._llm.generate(transcript)  #v1.1
            timings.llm_ms = (perf_counter() - llm_started_at) * 1000  #v1.1

            tts_started_at = perf_counter()  #v1.1
            reply_audio = self._tts.synthesize(reply_text)  #v1.1
            timings.tts_ms = (perf_counter() - tts_started_at) * 1000  #v1.1
            response = TurnResponse(  #v1.1
                turn_id=turn_id,
                reply_audio=reply_audio,
                reply_text=reply_text,
                display_text="KaKi-Talkie test reply.",
                slip_text=(
                    "KAKI-TALKIE TEST\n"
                    "This is a sample English slip.\n"
                    "No advice was generated. No retrieval occurred.\n"  #v1.2
                    "Source: canned test fixture\n"  #v1.2
                    "Source checked: 05-Sep-2026 (fixture date)"  #v1.2
                ),
                language=language,
                state=TurnState.ANSWERED,
                case_id=None,
                sources=[],
            )

        timings.overall_ms = (perf_counter() - request_started_at) * 1000  #v1.1
        log = TurnLog(  #v1.1
            turn_id=turn_id,
            device_id=device_id,
            session_id=session_id,
            state=response.state,
            timings=timings,
        )
        return TurnExecution(response=response, log=log)  #v1.1

    @staticmethod  #v1.1
    def _failed_response(turn_id: str) -> TurnResponse:  #v1.1
        return TurnResponse(  #v1.1
            turn_id=turn_id,
            reply_audio=canned_audio("empty_audio.wav"),  #v1.2
            reply_text="No audio was received. Please try recording again.",
            display_text="Please try recording again.",
            slip_text="",
            language="en",
            state=TurnState.FAILED,
            case_id=None,
            sources=[],
        )
