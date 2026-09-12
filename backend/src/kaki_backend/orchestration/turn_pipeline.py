# v2.0 | 12-Sep-2026 | Drop transcript redaction; keep credential-action and coverage refusal.
# v1.9 | 12-Sep-2026 | Redact secrets, route credential actions and refuse without evidence.
# v1.8 | 12-Sep-2026 | Attribute answers to the cited evidence, not the top-ranked chunk.
# v1.7 | 11-Sep-2026 | Ground answers in retrieved evidence with provenance and a real slip.
# v1.6 | 09-Sep-2026 | Speak generated replies, display them, and log the transcript for debug.
# v1.5 | 09-Sep-2026 | Handle real LLM failures and degrade to text when speech is unavailable.
# v1.4 | 07-Sep-2026 | Handle real STT failures and release audio before downstream stages.
# v1.3 | 06-Sep-2026 | Normalise audio before canned inference and time preparation.
# v1.2 | 05-Sep-2026 | Add fixture-labelled receipts and prerecorded failure audio.
# v1.1 | 04-Sep-2026 | Compose canned ports and record complete WP1 timing shape.
# v1.0 | 02-Sep-2026 | Return deterministic canned turns without inference or state.

"""Transcribe, retrieve evidence, then generate a grounded reply and its slip.

With retrieval active (`KAKI_RETRIEVAL_MODE=rag`) every answer turn
retrieves top evidence and grounds generation in it; source URLs and dates
in the response come only from chunk provenance, never from the LLM. The
normalised-query rewrite is guarded (skipped for short English transcripts)
and degrades silently to original-only retrieval.

WP3.4 makes the turn refuse rather than improvise, in three layers whose
order is the point (runbook 8.1 WP3.4):

1. intent routing refuses a credential action before retrieval or
   generation run at all;
2. the evidence gate refuses when the best dense similarity falls below the
   configured threshold, without calling the model;
3. the model's own `SOURCE: 0` no-coverage signal refuses even when the gate
   passed, and its text is discarded rather than spoken.

Layer 1 is a safety rule and applies in every configuration. Layers 2 and 3
need retrieval, so in the WP2 configuration an unsupported question keeps
its ungrounded answered reply exactly as before.

The pipeline does not redact volunteered credentials (design.md 8, owner
decision 12-Sep-2026): a transcript has already passed through the STT
service and the network, so redacting it here cannot protect the value and
would promise a defence the MVP does not have. A volunteered secret flows
through like any other text; raw-audio deletion after transcription remains
the limit the system can actually enforce.
"""

from time import perf_counter  #v1.1

from kaki_backend.contracts.ports import LlmPort, RetrieverPort, SttPort, TtsPort  #v1.1
from kaki_backend.contracts.ports import LlmError, SttError, Transcription, TtsError  #v1.6
from kaki_backend.contracts.ports import EvidenceChunk, LanguageEvidence  #v1.7
from kaki_backend.orchestration.audio_lifecycle import TestAudioRetention, TurnAudio
from kaki_backend.contracts.responses import SourceRecord, TurnResponse, TurnState  #v1.7
from kaki_backend.contracts.turn_log import EvidenceScore, TurnExecution, TurnLog, TurnTimings  #v1.7
from kaki_backend.config import DEFAULT_EVIDENCE_MIN_DENSE  #v1.9
from kaki_backend.orchestration.citation import select_cited_evidence  #v1.8
from kaki_backend.orchestration.intent_router import (  #v1.9
    Intent,
    RefusalReason,
    refusal_message,
    route,
)
from kaki_backend.orchestration.slip import (  #v1.9
    build_refusal_slip,
    build_slip,
    extract_steps,
)
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


SHORT_TRANSCRIPT_WORDS = 12  #v1.7


def _needs_rewrite(transcript: str, evidence: LanguageEvidence | None) -> bool:  #v1.7
    """Skip the rewrite only for a short transcript with English STT evidence."""
    is_english = evidence is not None and evidence.language.lower().startswith("en")
    return not (is_english and len(transcript.split()) <= SHORT_TRANSCRIPT_WORDS)


def _format_evidence(evidence: tuple[EvidenceChunk, ...]) -> str:  #v1.7
    """Render retrieved chunks as numbered context blocks for grounded generation."""
    blocks = []
    for number, chunk in enumerate(evidence, start=1):
        heading = " > ".join(chunk.heading_path)
        title = chunk.source.page_title + (f" - {heading}" if heading else "")
        blocks.append(f"[{number}] {title}\n{chunk.text}")
    return "\n\n".join(blocks)


def _source_records(  #v1.8
    evidence: tuple[EvidenceChunk, ...], cited: EvidenceChunk | None,
) -> list[SourceRecord]:
    """Return the evidence sources de-duplicated by URL, the cited one first.

    The answer's own source leads so that it is unambiguously the primary
    one and agrees with the printed slip; the remaining retrieved sources
    follow in rank order as the record of what was consulted.
    """
    ordered = list(evidence)
    if cited is not None:
        ordered.sort(key=lambda chunk: chunk.source.source_url != cited.source.source_url)
    records: list[SourceRecord] = []
    seen: set[str] = set()
    for chunk in ordered:
        if chunk.source.source_url not in seen:
            seen.add(chunk.source.source_url)
            records.append(chunk.source)
    return records


def _best_dense_score(evidence: tuple[EvidenceChunk, ...]) -> float | None:  #v1.9
    """Return the highest dense similarity among the retrieved chunks, if any.

    The dense cosine score is the gate's input because it is comparable
    across queries. The fused score is rank-based (the top result scores
    about 1/61 whatever it contains) and the lexical score is corpus-scaled,
    so neither separates a covered question from an uncovered one.
    """
    scores = [chunk.dense_score for chunk in evidence if chunk.dense_score is not None]
    return max(scores) if scores else None


class TurnPipeline:  #v1.1
    """Run the turn path behind replaceable model ports, grounded when configured."""  #v1.7

    def __init__(  #v1.1
        self,
        stt: SttPort | None = None,
        llm: LlmPort | None = None,
        tts: TtsPort | None = None,
        retriever: RetrieverPort | None = None,
        *,
        retrieval_active: bool = False,  #v1.7
        query_normalise: bool = True,  #v1.7
        evidence_min_dense: float = DEFAULT_EVIDENCE_MIN_DENSE,  #v1.9
    ) -> None:
        """Select supplied ports or the existing deterministic canned adapters.

        `retrieval_active` mirrors the configured retrieval mode: when false
        the retrieval and rewrite stages are never invoked and their timings
        stay null, preserving the WP1/WP2 behaviour exactly.
        `evidence_min_dense` is the WP3.4 refusal gate and applies only when
        retrieval is active.
        """  #v1.9
        self._stt = stt or CannedSttPort()  #v1.1
        self._llm = llm or CannedLlmPort()  #v1.1
        self._tts = tts or CannedTtsPort()  #v1.1
        self._retriever = retriever or CannedRetrieverPort()  #v1.1
        self._retrieval_active = retrieval_active  #v1.7
        self._query_normalise = query_normalise  #v1.7
        self._evidence_min_dense = evidence_min_dense  #v1.9
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

        llm_error = None  #v1.5
        retrieval_error = None  #v1.7
        normalised_query = None  #v1.7
        evidence: tuple[EvidenceChunk, ...] = ()  #v1.7
        cited: EvidenceChunk | None = None  #v1.8
        llm_cited_index = None  #v1.8
        intent = None  #v1.9
        refusal_reason: RefusalReason | None = None  #v1.9
        best_dense = None  #v1.9
        if transcription is not None:
            transcript = transcription.text  #v2.0

            routing_started_at = perf_counter()  #v1.1
            language = "en"  #v1.1
            # Layer 1: refuse a credential action before any downstream stage.
            routing = route(transcript)  #v2.0
            intent = routing.intent.value  #v1.9
            refusal_reason = routing.refusal_reason  #v1.9
            timings.routing_ms = (perf_counter() - routing_started_at) * 1000  #v1.1

            if refusal_reason is None and self._retrieval_active:  #v1.9
                if self._query_normalise and _needs_rewrite(transcript, transcription.evidence):
                    rewrite_started_at = perf_counter()
                    try:
                        normalised_query = self._llm.rewrite_query(transcript)
                    except LlmError:
                        # Degrade to original-only retrieval; never fail the turn here.
                        normalised_query = None
                    finally:
                        timings.query_rewrite_ms = (
                            perf_counter() - rewrite_started_at
                        ) * 1000
                retrieval_started_at = perf_counter()
                try:
                    evidence = self._retriever.retrieve(transcript, normalised_query)
                except Exception:
                    # A broken evidence store must not produce an ungrounded answer.
                    retrieval_error = "unavailable"
                finally:
                    timings.retrieval_ms = (perf_counter() - retrieval_started_at) * 1000
                if retrieval_error is None:  #v1.9
                    # Layer 2: no usable evidence means refuse, without generating.
                    best_dense = _best_dense_score(evidence)
                    if best_dense is None or best_dense < self._evidence_min_dense:
                        refusal_reason = RefusalReason.NO_COVERAGE

            if retrieval_error is not None:  #v1.7
                response = self._failed_response(turn_id).model_copy(update={
                    "reply_text": "The information service is not available right now. "
                    "Please try again shortly.",
                    "display_text": "Please try again shortly.",
                    "reply_audio": None,
                })
            elif refusal_reason is None:  #v1.9
                llm_started_at = perf_counter()  #v1.1
                try:  #v1.5
                    if evidence:  #v1.8
                        grounded = self._llm.generate_grounded(
                            transcript, evidence=_format_evidence(evidence)
                        )
                        if grounded.no_coverage:  #v1.9
                            # Layer 3: discard the text; never speak a partial
                            # answer beside a no-coverage verdict.
                            refusal_reason = RefusalReason.NO_COVERAGE
                        else:  #v1.9
                            reply_text = grounded.text
                            llm_cited_index = grounded.cited_index
                            cited = select_cited_evidence(evidence, reply_text, llm_cited_index)
                    else:  #v1.8
                        reply_text = self._llm.generate(transcript)
                except LlmError as error:  #v1.5
                    llm_error = error.code
                    response = self._failed_response(turn_id).model_copy(update={
                        "reply_text": "The reply service is not available right now. "
                        "Please try again shortly.",
                        "display_text": "Please try again shortly.",
                        "reply_audio": None,
                    })
                finally:  #v1.5
                    timings.llm_ms = (perf_counter() - llm_started_at) * 1000  #v1.1

            # A failed stage has already built its own response above; only a
            # turn that got through it has a reply to shape.
            if retrieval_error is None and llm_error is None:  #v1.9
                if refusal_reason is not None:
                    # Whichever layer refused, the wording is the router's,
                    # not the model's, so the spoken output stays stable.
                    intent = Intent.REFUSE.value
                    message = refusal_message(refusal_reason, language)
                    reply_text = message.reply_text
                    display_text = message.display_text
                    slip_text = build_refusal_slip(transcript)
                    sources: list[SourceRecord] = []
                    state = TurnState.REFUSED
                else:
                    display_text = reply_text  #v1.6
                    sources = _source_records(evidence, cited)  #v1.8
                    state = TurnState.ANSWERED
                    if sources:  #v1.7
                        # sources[0] is the cited source, so slip and response agree.
                        slip_text = build_slip(extract_steps(reply_text), sources[0])
                    else:  # The ungrounded WP1/WP2 path keeps its sample slip.
                        slip_text = (
                            "KAKI-TALKIE TEST\n"
                            "This is a sample English slip.\n"
                            "No advice was generated. No retrieval occurred.\n"  #v1.2
                            "Source: canned test fixture\n"  #v1.2
                            "Source checked: 05-Sep-2026 (fixture date)"  #v1.2
                        )

        tts_error = None  #v1.6
        if transcription is not None and llm_error is None and retrieval_error is None:  #v1.7
            tts_started_at = perf_counter()  #v1.1
            try:  #v1.5
                reply_audio = self._tts.synthesize(reply_text)  #v1.1
            except TtsError as error:  #v1.6
                # Losing speech must not lose the answer; degrade to text only.
                tts_error = error.code
                reply_audio = None
            except ValueError:  #v1.5
                # The canned engine has no recording for generated text; answer as text only.
                tts_error = "unavailable"  #v1.6
                reply_audio = None
            timings.tts_ms = (perf_counter() - tts_started_at) * 1000  #v1.1
            response = TurnResponse(  #v1.1
                turn_id=turn_id,
                reply_audio=reply_audio,
                reply_text=reply_text,
                display_text=display_text,  #v1.9
                slip_text=slip_text,  #v1.7
                language=language,
                state=state,  #v1.9
                case_id=None,
                sources=sources,  #v1.7
            )

        timings.overall_ms = (perf_counter() - request_started_at) * 1000  #v1.1
        log = TurnLog(  #v1.1
            turn_id=turn_id,
            device_id=device_id,
            session_id=session_id,
            state=response.state,
            timings=timings,
            transcript=transcript if transcription else None,  #v1.9
            intent=intent,  #v1.9
            refusal_reason=refusal_reason.value if refusal_reason else None,  #v1.9
            best_dense_score=best_dense,  #v1.9
            evidence_min_dense=(  #v1.9
                self._evidence_min_dense if self._retrieval_active else None
            ),
            stt_language=transcription.evidence if transcription else None,
            stt_error=stt_error,
            llm_error=llm_error,  #v1.5
            tts_error=tts_error,  #v1.6
            retrieval_error=retrieval_error,  #v1.7
            normalised_query=normalised_query,  #v1.7
            cited_source_id=cited.source_id if cited else None,  #v1.8
            llm_cited_index=llm_cited_index,  #v1.8
            retrieval_evidence=[  #v1.7
                EvidenceScore(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    retrieval_rank=rank,  #v1.8
                    fused_score=chunk.fused_score,
                    dense_score=chunk.dense_score,
                    lexical_score=chunk.lexical_score,
                    cited=cited is not None and chunk.chunk_id == cited.chunk_id,  #v1.8
                )
                for rank, chunk in enumerate(evidence, start=1)  #v1.8
            ],
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
