# v2.7 | 21-Sep-2026 | WP6.7: dispatch the booking action and carry its case reference.
# v2.6 | 21-Sep-2026 | WP6.8: pass the configured reply persona to grounded generation.
# v2.5 | 18-Sep-2026 | WP6.6: per-device admin override of the reply language, read per turn.
# v2.4 | 14-Sep-2026 | Keep the slip English: retry a non-English grounded answer with the English query.
# v2.3 | 13-Sep-2026 | WP5.1: reply-language policy, Malay reply modes, speech language.
# v2.2 | 13-Sep-2026 | Answer repeat_previous and print_previous from stored turns.
# v2.1 | 13-Sep-2026 | Link each response source to its evidence chunk for durable storage.
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

WP4.2 adds deterministic actions after routing. `repeat_previous` and
`print_previous` resolve the previous turn in the session from the store and
return an `acted` turn without retrieval or generation; a resolved repeat
also replays the stored audio instead of synthesising (runbook 9.1 WP4.2).

WP5.1 decides the reply language once per transcribed turn (runbook 10.1
WP5.1). The English grounded answer is always generated first; its citation,
no-coverage signal, evidence gate and slip are unchanged. Only then does the
Malay reply mode shape what a Malay turn speaks and displays. The language
decision also guards the query rewrite: the rewrite is skipped only when STT
and the policy both say English, because Malay retrieval depends on it.
Failed turns stay English.

The grounded model can answer a Malay question in Malay despite its English
prompt, and the slip is composed from that answer. So the answer is checked
before anything uses it: a non-English answer is regenerated once from the
normalised English query against the same evidence. If it is still not
English, the answer is spoken but the slip prints its heading and
provenance with no steps, never Malay steps (WP5-AT-01, design.md 9.3).

The pipeline does not redact volunteered credentials (design.md 8, owner
decision 12-Sep-2026): a transcript has already passed through the STT
service and the network, so redacting it here cannot protect the value and
would promise a defence the MVP does not have. A volunteered secret flows
through like any other text; raw-audio deletion after transcription remains
the limit the system can actually enforce.
"""

from time import perf_counter  #v1.1
from typing import Callable  #v2.5

from kaki_backend.contracts.ports import LlmPort, RetrieverPort, SttPort, TtsPort  #v1.1
from kaki_backend.contracts.ports import LlmError, SttError, Transcription, TtsError  #v1.6
from kaki_backend.contracts.ports import EvidenceChunk, LanguageEvidence  #v1.7
from kaki_backend.orchestration.audio_lifecycle import TestAudioRetention, TurnAudio
from kaki_backend.contracts.responses import SourceRecord, TurnResponse, TurnState  #v1.7
from kaki_backend.contracts.turn_log import EvidenceScore, TurnExecution, TurnLog, TurnTimings  #v1.7
from kaki_backend.contracts.turn_log import SourceLink  #v2.1
from kaki_backend.actions import ActionOutcome, NoTurnHistory, TurnHistory  #v2.2
from kaki_backend.actions.book_action import book_appointment  #v2.7
from kaki_backend.actions.print_action import print_previous  #v2.2
from kaki_backend.actions.repeat_action import repeat_previous  #v2.2
from kaki_backend.config import DEFAULT_EVIDENCE_MIN_DENSE  #v1.9
from kaki_backend.config import DEFAULT_PERSONA_NAME  #v2.6
from kaki_backend.orchestration.citation import select_cited_evidence  #v1.8
from kaki_backend.orchestration.language_policy import ENGLISH, decide_reply_language  #v2.3
from kaki_backend.orchestration.language_policy import is_english_text  #v2.4
from kaki_backend.orchestration.reply_language import (  #v2.3
    ReplyMode,
    compose_answer,
    fixed_wording_language,
    join_wav_data_urls,
)
from kaki_backend.orchestration.intent_router import (  #v1.9
    ACTION_INTENTS,  #v2.2
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


def _needs_rewrite(
    transcript: str, evidence: LanguageEvidence | None, reply_language: str,
) -> bool:  #v2.3
    """Skip the rewrite only for a short transcript that STT and the policy both call English.

    Before WP5.1 the STT label alone decided, so a short Malay question that
    Whisper labelled `en` lost its normalised query and refused.
    """
    is_english = evidence is not None and evidence.language.lower().startswith("en")
    return not (
        is_english and reply_language == ENGLISH
        and len(transcript.split()) <= SHORT_TRANSCRIPT_WORDS
    )


def _format_evidence(evidence: tuple[EvidenceChunk, ...]) -> str:  #v1.7
    """Render retrieved chunks as numbered context blocks for grounded generation."""
    blocks = []
    for number, chunk in enumerate(evidence, start=1):
        heading = " > ".join(chunk.heading_path)
        title = chunk.source.page_title + (f" - {heading}" if heading else "")
        blocks.append(f"[{number}] {title}\n{chunk.text}")
    return "\n\n".join(blocks)


def _source_chunks(  #v2.1
    evidence: tuple[EvidenceChunk, ...], cited: EvidenceChunk | None,
) -> list[EvidenceChunk]:
    """Return one representative chunk per source URL, the cited source first.

    The answer's own source leads so that it is unambiguously the primary
    one and agrees with the printed slip; the remaining retrieved sources
    follow in rank order as the record of what was consulted. The cited
    chunk represents its own URL; any other URL is represented by its
    best-ranked chunk.
    """
    ordered = list(evidence)
    if cited is not None:
        ordered.sort(key=lambda chunk: chunk.chunk_id != cited.chunk_id)  #v2.1
        ordered.sort(key=lambda chunk: chunk.source.source_url != cited.source.source_url)
    chunks: list[EvidenceChunk] = []
    seen: set[str] = set()
    for chunk in ordered:
        if chunk.source.source_url not in seen:
            seen.add(chunk.source.source_url)
            chunks.append(chunk)
    return chunks


def _source_links(  #v2.1
    evidence: tuple[EvidenceChunk, ...], chunks: list[EvidenceChunk],
    cited: EvidenceChunk | None,
) -> list[SourceLink]:
    """Describe each representative chunk for the `turn_sources` record."""
    ranks = {chunk.chunk_id: rank for rank, chunk in enumerate(evidence, start=1)}
    return [
        SourceLink(
            source_id=chunk.source_id, chunk_id=chunk.chunk_id,
            retrieval_rank=ranks[chunk.chunk_id], dense_score=chunk.dense_score,
            cited=cited is not None and chunk.chunk_id == cited.chunk_id,
        )
        for chunk in chunks
    ]


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
        history: TurnHistory | None = None,  #v2.2
        language_preference: str = ENGLISH,  #v2.3
        malay_reply_mode: str = ReplyMode.ENGLISH.value,  #v2.3
        reply_language_for: Callable[[str], str] | None = None,  #v2.5
        persona: str = DEFAULT_PERSONA_NAME,  #v2.6
    ) -> None:
        """Select supplied ports or the existing deterministic canned adapters.

        `retrieval_active` mirrors the configured retrieval mode: when false
        the retrieval and rewrite stages are never invoked and their timings
        stay null, preserving the WP1/WP2 behaviour exactly.
        `evidence_min_dense` is the WP3.4 refusal gate and applies only when
        retrieval is active. `history` is the stored-turn reader the WP4.2
        actions resolve from; without one, every action has nothing to act on.

        `language_preference` and `malay_reply_mode` are the WP5.1 settings.
        The constructor defaults to `english` mode, the pre-WP5.1 behaviour,
        so a pipeline built without language settings never renders; the
        backend and the regression runner pass the configured values.
        """  #v2.3
        self._stt = stt or CannedSttPort()  #v1.1
        self._llm = llm or CannedLlmPort()  #v1.1
        self._tts = tts or CannedTtsPort()  #v1.1
        self._retriever = retriever or CannedRetrieverPort()  #v1.1
        self._retrieval_active = retrieval_active  #v1.7
        self._query_normalise = query_normalise  #v1.7
        self._evidence_min_dense = evidence_min_dense  #v1.9
        self._history = history or NoTurnHistory()  #v2.2
        self._language_preference = language_preference  #v2.3
        # WP6.6: the per-device admin override (design.md 5.5), consulted once
        # per transcribed turn. None keeps the pre-WP6.6 behaviour exactly;
        # 'auto' from the store returns the decision to the policy.
        self._reply_language_for = reply_language_for  #v2.5
        # WP6.8: the reply register appended to the grounded system prompt.
        # It reaches the port per call, not at construction, so the persona
        # can later become a per-turn decision without rebuilding the port.
        self._persona = persona  #v2.6
        self._reply_mode = ReplyMode(malay_reply_mode)  #v2.3
        if language_preference not in ("en", "ms"):  #v2.3
            raise ValueError("language_preference must be en or ms.")
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
        source_chunks: list[EvidenceChunk] = []  #v2.1
        action: ActionOutcome | None = None  #v2.2
        reply_language = None  #v2.3
        language_override = None  #v2.5
        render_outcome = None  #v2.3
        speech_segments: tuple[tuple[str, str], ...] = ()  #v2.3
        slip_steps_english = True  #v2.4
        if transcription is not None:
            transcript = transcription.text  #v2.0

            routing_started_at = perf_counter()  #v1.1
            language = "en"  #v1.1
            reply_language = decide_reply_language(  #v2.3
                transcript, transcription.evidence, self._language_preference
            ).language
            if self._reply_language_for is not None:  #v2.5
                # The admin override wins over the policy; the policy's own
                # decision stays visible in the evidence as what it would have
                # said, and stt_language is never rewritten.
                configured = self._reply_language_for(device_id)
                if configured in ("en", "ms"):
                    language_override = configured
                    reply_language = configured
            fixed_language = fixed_wording_language(reply_language, self._reply_mode)  #v2.3
            # Layer 1: refuse a credential action before any downstream stage.
            routing = route(transcript)  #v2.0
            intent = routing.intent.value  #v1.9
            refusal_reason = routing.refusal_reason  #v1.9
            timings.routing_ms = (perf_counter() - routing_started_at) * 1000  #v1.1

            if routing.intent in ACTION_INTENTS:  #v2.2
                # Actions answer from the store: no retrieval, gate or model.
                if routing.intent is Intent.BOOK_APPOINTMENT:  #v2.7
                    # WP6.7: a booking stands on its own, so it reads no
                    # previous turn and cannot fail to resolve one.
                    action = book_appointment(fixed_language)
                else:
                    previous = self._history.previous_content_turn(session_id)
                    if routing.intent is Intent.REPEAT_PREVIOUS:
                        action = repeat_previous(previous, fixed_language)  #v2.3
                    else:
                        action = print_previous(previous, fixed_language)  #v2.3

            if refusal_reason is None and action is None and self._retrieval_active:  #v2.2
                if self._query_normalise and _needs_rewrite(  #v2.3
                    transcript, transcription.evidence, reply_language
                ):
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
            elif refusal_reason is None and action is None:  #v2.2
                llm_started_at = perf_counter()  #v1.1
                try:  #v1.5
                    if evidence:  #v1.8
                        evidence_text = _format_evidence(evidence)  #v2.4
                        grounded = self._llm.generate_grounded(
                            transcript, evidence=evidence_text, persona=self._persona,  #v2.6
                        )
                        if (not grounded.no_coverage and not is_english_text(grounded.text)
                                and normalised_query):  #v2.4
                            # The slip needs English steps; ask again in English.
                            grounded = self._llm.generate_grounded(
                                normalised_query, evidence=evidence_text,
                                persona=self._persona,  #v2.6
                            )
                        if grounded.no_coverage:  #v1.9
                            # Layer 3: discard the text; never speak a partial
                            # answer beside a no-coverage verdict.
                            refusal_reason = RefusalReason.NO_COVERAGE
                        else:  #v1.9
                            reply_text = grounded.text
                            slip_steps_english = is_english_text(reply_text)  #v2.4
                            llm_cited_index = grounded.cited_index
                            cited = select_cited_evidence(evidence, reply_text, llm_cited_index)
                    else:  #v1.8
                        reply_text = self._llm.generate(transcript)
                    if refusal_reason is None:  #v2.3
                        # The English answer is settled; the reply mode shapes
                        # only what a Malay turn speaks and displays.
                        composed = compose_answer(
                            reply_text, reply_language, self._reply_mode, self._llm
                        )
                        render_outcome = composed.render_outcome
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
                if action is not None:  #v2.2
                    reply_text = action.reply_text
                    display_text = action.display_text
                    slip_text = action.slip_text
                    sources = list(action.sources)
                    language = action.language
                    speech_segments = ((reply_text, language),)  #v2.3
                    state = TurnState.ACTED
                elif refusal_reason is not None:
                    # Whichever layer refused, the wording is the router's,
                    # not the model's, so the spoken output stays stable.
                    intent = Intent.REFUSE.value
                    language = fixed_language  #v2.3
                    message = refusal_message(refusal_reason, language)
                    reply_text = message.reply_text
                    display_text = message.display_text
                    slip_text = build_refusal_slip(transcript)
                    sources: list[SourceRecord] = []
                    speech_segments = ((reply_text, language),)  #v2.3
                    state = TurnState.REFUSED
                else:
                    english_reply = reply_text  #v2.3
                    reply_text = composed.text  #v2.3
                    language = composed.language  #v2.3
                    speech_segments = composed.segments  #v2.3
                    # WP6.8 (owner decision, 21-Sep-2026): reply_text and
                    # display_text both keep the written form. The spoken
                    # form is produced inside the say adapter, so only the
                    # bytes handed to the engine carry its control sequences.
                    display_text = reply_text  #v1.6
                    source_chunks = _source_chunks(evidence, cited)  #v2.1
                    sources = [chunk.source for chunk in source_chunks]  #v2.1
                    state = TurnState.ANSWERED
                    if sources:  #v1.7
                        # sources[0] is the cited source, so slip and response agree.
                        # The slip always comes from the English answer (design.md 9.3).
                        # A still-non-English answer prints provenance without steps.
                        steps = extract_steps(english_reply) if slip_steps_english else []  #v2.4
                        slip_text = build_slip(steps, sources[0])  #v2.4
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
            if action is not None and not action.speak:  #v2.2
                # A resolved repeat replays the stored bytes; TTS is not called.
                reply_audio = action.reply_audio
            else:
                tts_started_at = perf_counter()  #v1.1
                try:  #v1.5
                    reply_audio = self._speak(speech_segments)  #v2.3
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
                # WP6.7: only a booking sets this today; every other path
                # leaves the WP1 field null exactly as before.
                case_id=action.case_id if action is not None else None,  #v2.7
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
            evidence_min_dense=(  #v2.2
                self._evidence_min_dense
                if self._retrieval_active and action is None else None
            ),
            stt_language=transcription.evidence if transcription else None,
            stt_error=stt_error,
            llm_error=llm_error,  #v1.5
            tts_error=tts_error,  #v1.6
            retrieval_error=retrieval_error,  #v1.7
            normalised_query=normalised_query,  #v1.7
            cited_source_id=cited.source_id if cited else None,  #v1.8
            llm_cited_index=llm_cited_index,  #v1.8
            source_links=(  #v2.2
                list(action.source_links) if action is not None
                else _source_links(evidence, source_chunks, cited)
            ),
            previous_turn_id=action.previous_turn_id if action else None,  #v2.2
            action_outcome=action.kind.value if action else None,  #v2.2
            reply_language=reply_language if response.state is not TurnState.FAILED else None,  #v2.3
            language_override=(  #v2.5
                language_override if response.state is not TurnState.FAILED else None
            ),
            reply_mode=(  #v2.3
                self._reply_mode.value if response.state is not TurnState.FAILED else None
            ),
            render_outcome=render_outcome.value if render_outcome else None,  #v2.3
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

    def _speak(self, segments: tuple[tuple[str, str], ...]) -> str | None:  #v2.3
        """Synthesise each `(text, language)` segment in order and join them into one WAV.

        An English segment calls `synthesize(text)` exactly as before WP5.1;
        only a non-English segment passes its language. A single segment is
        returned as synthesised. Raises TtsError or ValueError like the port.
        """
        audio = []
        for text, segment_language in segments:
            if segment_language == ENGLISH:
                audio.append(self._tts.synthesize(text))
            else:
                audio.append(self._tts.synthesize(text, language=segment_language))
        if len(audio) == 1:
            return audio[0]
        if any(part is None for part in audio):
            return None
        return join_wav_data_urls(audio)

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
