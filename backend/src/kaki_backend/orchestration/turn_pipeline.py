# v1.4 | 07-Sep-2026 | Handle real STT failures and release audio before downstream stages.
# v1.3 | 06-Sep-2026 | Normalise audio before canned inference and time preparation.
# v1.2 | 05-Sep-2026 | Add fixture-labelled receipts and prerecorded failure audio.
# v1.1 | 04-Sep-2026 | Compose canned ports and record complete WP1 timing shape.
# v1.0 | 02-Sep-2026 | Return deterministic canned turns without inference or state.

"""Transcribe and release audio before the still-canned generation/speech stages."""

from time import perf_counter  #v1.1

from kaki_backend.contracts.ports import LlmPort, RetrieverPort, SttPort, TtsPort  #v1.1
from kaki_backend.contracts.ports import SttError, Transcription
from kaki_backend.orchestration.audio_lifecycle import TestAudioRetention, TurnAudio
from kaki_backend.contracts.responses import TurnResponse, TurnState
from kaki_backend.contracts.turn_log import TurnExecution, TurnLog, TurnTimings  #v1.1
from kaki_backend.orchestration.audio_normalisation import (  #v1.3
    AudioNormalisationError,  #v1.3
    normalise_audio,  #v1.3
)  #v1.3
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
        """Select supplied ports or the existing deterministic canned adapters."""  #v1.3
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
        audio: bytes | TurnAudio,
        audio_preparation_ms: float,
        request_started_at: float,
        retention: TestAudioRetention | None = None,
    ) -> TurnExecution:
        """Normalise once per execution; return a failed turn for unusable audio."""  #v1.3
        self.execution_count += 1  #v1.1
        timings = TurnTimings(audio_preparation_ms=audio_preparation_ms)  #v1.1

        owned = audio if isinstance(audio, TurnAudio) else TurnAudio(audio)
        del audio
        transcription = None
        stt_error = None
        try:
            transcription = self._transcribe(owned, timings, retention)
        except AudioNormalisationError:
            response = self._failed_response(turn_id)
        except SttError as error:
            stt_error = error.code
            response = self._failed_response(turn_id).model_copy(update={
                "reply_text": "Speech recognition did not succeed. Please try recording again.",
                "reply_audio": None,
            })

        if transcription is not None:
            transcript = transcription.text

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
            stt_language=transcription.evidence if transcription else None,
            stt_error=stt_error,
        )
        return TurnExecution(response=response, log=log)  #v1.1

    def _transcribe(
        self, audio: TurnAudio, timings: TurnTimings, retention: TestAudioRetention | None,
    ) -> Transcription:
        """Own raw and normalised audio only through STT, including every failure path."""
        prepared = None
        try:
            started = perf_counter()
            try:
                prepared = normalise_audio(audio.data)
            finally:
                timings.audio_preparation_ms += (perf_counter() - started) * 1000
            started = perf_counter()
            try:
                result = self._stt.transcribe(prepared)
                if not result.text.strip():
                    raise SttError("empty_transcript")
            finally:
                timings.stt_ms = (perf_counter() - started) * 1000
            if retention is not None:
                retention.save(audio)
            return result
        finally:
            prepared = None
            audio.clear()

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
