# v1.2 | 14-Sep-2026 | Slip body stays English when the grounded model answers a Malay question in Malay.
# v1.1 | 14-Sep-2026 | Digit-sequence render check; referral question dropped when the Latin-1 cut hollows it.
# v1.0 | 13-Sep-2026 | WP5.1 Malay turn shape, reply modes, render fallback, slips and storage.
"""Verify the WP5.1 Malay path through the pipeline with fake ports (WP5-AT-01).

Covers, for a Malay transcript: the render pass sees the English reply alone;
the citation, gate and slip come from the English answer; empty, altered-number,
length and error renders fall back to the English reply and say so; bridge and english
modes; Malay refusal and action wording; the referral slip keeps the question
within Latin-1; speech is synthesised per language and joined; and the
diagnostics survive storage (migration 0003). An English transcript is
unchanged by any mode.
"""

import io
import sqlite3
import tempfile
import unittest
import wave
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from kaki_backend.config import LanguageSettings, LlmSettings, TtsSettings
from kaki_backend.contracts.ports import (
    EvidenceChunk,
    GroundedReply,
    LanguageEvidence,
    LlmError,
    Transcription,
)
from kaki_backend.contracts.responses import SourceRecord
from kaki_backend.orchestration.intent_router import (
    ActionMessageKind,
    RefusalReason,
    action_message,
    refusal_message,
)
from kaki_backend.orchestration.language_policy import is_english_text
from kaki_backend.orchestration.reply_language import (
    BRIDGE_CLOSING,
    BRIDGE_GREETING,
    RENDER_LENGTH_TOLERANCE,
    RenderOutcome,
    check_render,
    digit_sequences,
)
from kaki_backend.orchestration.slip import (
    MAX_QUESTION_CHARACTERS_REMOVED,
    REFERRAL_HEADING,
    REFERRAL_LINE,
    build_refusal_slip,
    build_slip,
    extract_steps,
    removed_share,
    to_printable,
)
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.persistence.database import Database
from kaki_backend.persistence.repositories import TurnRepository

MALAY_QUESTION = "Macam mana saya boleh guna baucar CDC saya?"
ENGLISH_QUESTION = "How do I use my CDC vouchers?"
MALAY_UNSUPPORTED = "Esok cuaca macam mana, ada hujan tak?"
ENGLISH_REPLY = (
    "1. Open the SMS link from CDC. 2. Show the QR code at the shop. "
    "3. Use them by 31 December 2026."
)
MALAY_RENDER = (
    "1. Buka pautan SMS daripada CDC. 2. Tunjukkan kod QR di kedai. "
    "3. Gunakan sebelum 31 Disember 2026."
)

CDC_SOURCE = SourceRecord(
    source_url="https://vouchers.cdc.gov.sg/residents/",
    page_title="CDC Vouchers for residents",
    captured_at=datetime(2026, 9, 10, 11, 6, 44, tzinfo=timezone.utc),
)
EVIDENCE = (
    EvidenceChunk(
        chunk_id="chunk-1", source_id="cdc-vouchers-residents",
        heading_path=("Claiming vouchers",),
        text="Households claim CDC Vouchers through the SMS link.",
        source=CDC_SOURCE, fused_score=0.0325, dense_score=0.77, lexical_score=4.0,
    ),
)


def wav_data_url(frames: int, marker: int = 1) -> str:
    """Return a 22.05 kHz mono PCM WAV data URL with a recognisable frame count."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(22050)
        recording.writeframes(bytes([marker, 0]) * frames)
    return "data:audio/wav;base64," + b64encode(buffer.getvalue()).decode("ascii")


def upload() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


class FakeStt:
    def __init__(self, text: str, label: str | None = "ms") -> None:
        self.text = text
        self.label = label

    def ready(self) -> bool:
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        evidence = LanguageEvidence(language=self.label) if self.label else None
        return Transcription(text=self.text, evidence=evidence)


class FakeLlm:
    """Record every call; the render result is configurable."""

    def __init__(self, render: str | Exception = MALAY_RENDER) -> None:
        self.render = render
        self.grounded_calls: list[tuple[str, str]] = []
        self.render_calls: list[tuple[tuple, dict]] = []
        self.rewrite_calls: list[str] = []

    def ready(self) -> bool:
        return True

    def generate(self, transcript: str) -> str:
        return ENGLISH_REPLY

    def generate_grounded(
        self, transcript: str, *, evidence: str, persona: str = "plain",
    ) -> GroundedReply:  # WP6.8 persona argument
        self.grounded_calls.append((transcript, evidence))
        return GroundedReply(text=ENGLISH_REPLY, cited_index=1)

    def rewrite_query(self, transcript: str) -> str:
        self.rewrite_calls.append(transcript)
        return "how to use CDC vouchers"

    def render_reply(self, *args, **kwargs) -> str:
        self.render_calls.append((args, kwargs))
        if isinstance(self.render, Exception):
            raise self.render
        return self.render


# The grounded answer Qwen gave in Test 3 (evidence.HPXIb7, ms_cdc): Malay,
# despite the English prompt, for "Bagaimana saya boleh guna baucah CDC saya?".
LIVE_MALAY_ANSWER = (
    "Anda boleh guna baucah CDC dengan membuka pautan dalam SMS yang dikirimkan. "
    "Pastikan pautan masih valid dan gunakan untuk belanja seperti biasa."
)
NORMALISED_QUERY = "how to use CDC vouchers"


class MalayAnsweringLlm(FakeLlm):
    """Answer a Malay question in Malay, and the English query in English (or Malay again)."""

    def __init__(self, english_on_retry: bool = True) -> None:
        super().__init__(render=MALAY_RENDER)
        self.english_on_retry = english_on_retry

    def generate_grounded(
        self, transcript: str, *, evidence: str, persona: str = "plain",
    ) -> GroundedReply:  # WP6.8 persona argument
        self.grounded_calls.append((transcript, evidence))
        if transcript == NORMALISED_QUERY and self.english_on_retry:
            return GroundedReply(text=ENGLISH_REPLY, cited_index=1)
        return GroundedReply(text=LIVE_MALAY_ANSWER, cited_index=1)


def slip_body(slip_text: str) -> str:
    """Return the lines between the heading and the Source: line."""
    lines = slip_text.splitlines()[1:]
    body = []
    for line in lines:
        if line.startswith("Source: "):
            break
        body.append(line)
    return "\n".join(body)


class FakeRetriever:
    def ready(self) -> bool:
        return True

    def retrieve(self, original_query, normalized_query):
        return EVIDENCE


class RecordingTts:
    """Return a WAV per call whose length encodes the call order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def ready(self) -> bool:
        return True

    def synthesize(self, reply_text: str, language: str = "en") -> str | None:
        self.calls.append((reply_text, language))
        return wav_data_url(frames=100 * len(self.calls))


class HistoryStub:
    def __init__(self, previous=None) -> None:
        self.previous = previous

    def previous_content_turn(self, session_id: str):
        return self.previous


def run(transcript=MALAY_QUESTION, *, label="ms", mode="full", preference="en",
        llm=None, history=None):
    """Execute one grounded turn and return the execution with its fake ports."""
    llm = llm or FakeLlm()
    tts = RecordingTts()
    pipeline = TurnPipeline(
        stt=FakeStt(transcript, label), llm=llm, tts=tts, retriever=FakeRetriever(),
        retrieval_active=True, history=history,
        language_preference=preference, malay_reply_mode=mode,
    )
    execution = pipeline.execute(
        device_id="malay-test", session_id="malay-test", turn_id=f"malay-{mode}",
        audio=upload(), audio_preparation_ms=0.0, request_started_at=perf_counter(),
    )
    return execution, llm, tts


def english_slip() -> str:
    return build_slip(extract_steps(ENGLISH_REPLY), CDC_SOURCE)


class FullModeTests(unittest.TestCase):
    """WP5-AT-01: a Malay question gets a Malay reply and display with an English slip."""

    def test_malay_reply_display_and_english_slip(self):
        execution, llm, tts = run()
        response, log = execution.response, execution.log
        self.assertEqual(response.state.value, "answered")
        self.assertEqual(response.language, "ms")
        self.assertEqual(response.reply_text, MALAY_RENDER)
        self.assertEqual(response.display_text, MALAY_RENDER)
        self.assertEqual(response.slip_text, english_slip())
        self.assertEqual(response.sources, [CDC_SOURCE])
        self.assertEqual(tts.calls, [(MALAY_RENDER, "ms")])
        self.assertEqual((log.reply_language, log.reply_mode, log.render_outcome),
                         ("ms", "full", "rendered"))
        self.assertEqual(log.cited_source_id, "cdc-vouchers-residents")
        self.assertEqual(log.llm_cited_index, 1)

    def test_render_receives_the_english_reply_alone(self):
        _, llm, _ = run()
        self.assertEqual(llm.render_calls, [((ENGLISH_REPLY, "ms"), {})])
        self.assertEqual(len(llm.grounded_calls), 1)
        self.assertEqual(llm.grounded_calls[0][0], MALAY_QUESTION)

    def test_failed_renders_fall_back_to_the_english_reply_and_record_why(self):
        cases = (
            ("   ", "fallback_empty"),
            (MALAY_RENDER.replace("31 Disember", "30 Disember"), "fallback_numbers"),
            (MALAY_RENDER.replace(" 2026", ""), "fallback_numbers"),
            ("1. Ya. 2. Ok. 3. 31 2026.", "fallback_length"),
            (MALAY_RENDER + " Sila" * 40, "fallback_length"),
            (LlmError("timeout"), "fallback_error"),
        )
        for render, outcome in cases:
            with self.subTest(outcome=outcome, render=str(render)[:20]):
                execution, _, tts = run(llm=FakeLlm(render=render))
                response = execution.response
                self.assertEqual(response.state.value, "answered")
                self.assertEqual(response.reply_text, ENGLISH_REPLY)
                self.assertEqual(response.display_text, ENGLISH_REPLY)
                self.assertEqual(response.language, "en")
                self.assertEqual(response.slip_text, english_slip())
                self.assertEqual(tts.calls, [(ENGLISH_REPLY, "en")])
                self.assertEqual(execution.log.render_outcome, outcome)
                self.assertIsNone(execution.log.llm_error)

    def test_render_that_alters_a_number_falls_back_to_english(self):
        altered = MALAY_RENDER.replace("31 Disember", "13 Disember")
        execution, _, tts = run(llm=FakeLlm(render=altered))
        self.assertEqual(execution.response.reply_text, ENGLISH_REPLY)
        self.assertEqual(execution.response.language, "en")
        self.assertEqual(execution.log.render_outcome, "fallback_numbers")
        self.assertEqual(tts.calls, [(ENGLISH_REPLY, "en")])

    def test_digit_check_compares_multisets_not_sets_or_order(self):
        english = "1. Pay 50 dollars. 2. Then pay 50 more by 2026."
        self.assertEqual(check_render(english, "2. Bayar 50. 1. Kemudian 50 lagi, 2026 ya."),
                         RenderOutcome.RENDERED)
        self.assertEqual(check_render(english, "1. Bayar 50 ringgit. 2. Kemudian 2026 ya."),
                         RenderOutcome.FALLBACK_NUMBERS)
        self.assertEqual(digit_sequences("CDC 2026-09-10, 1,000"),
                         digit_sequences("1 000 dan 2026 09 10 CDC"))

    def test_numbers_are_checked_before_length(self):
        self.assertEqual(check_render(ENGLISH_REPLY, "Ya."), RenderOutcome.FALLBACK_NUMBERS)

    def test_length_check_uses_the_documented_tolerance(self):
        english = "x" * 100
        limit = int(100 * RENDER_LENGTH_TOLERANCE)
        self.assertEqual(check_render(english, "y" * (100 + limit)), RenderOutcome.RENDERED)
        self.assertEqual(check_render(english, "y" * (100 - limit)), RenderOutcome.RENDERED)
        self.assertEqual(check_render(english, "y" * (101 + limit)),
                         RenderOutcome.FALLBACK_LENGTH)
        self.assertEqual(check_render(english, "y" * (99 - limit)),
                         RenderOutcome.FALLBACK_LENGTH)

    def test_english_question_is_unchanged_by_every_mode(self):
        baseline, _, _ = run(ENGLISH_QUESTION, label="en", mode="english")
        for mode in ("full", "bridge"):
            with self.subTest(mode=mode):
                execution, llm, tts = run(ENGLISH_QUESTION, label="en", mode=mode)
                self.assertEqual(llm.render_calls, [])
                self.assertEqual(tts.calls, [(ENGLISH_REPLY, "en")])
                self.assertEqual(execution.response.model_dump(exclude={"turn_id"}),
                                 baseline.response.model_dump(exclude={"turn_id"}))
                self.assertIsNone(execution.log.render_outcome)


class EnglishSlipOnMalayTurnTests(unittest.TestCase):
    """WP5-AT-01 regression: a Malay turn's slip body is English in every mode."""

    def test_slip_body_is_english_when_the_answer_is_english(self):
        for mode in ("full", "bridge", "english"):
            with self.subTest(mode=mode):
                execution, _, _ = run(mode=mode)
                body = slip_body(execution.response.slip_text)
                self.assertTrue(body.strip())
                self.assertTrue(is_english_text(body), body)
                self.assertNotIn("You asked:", execution.response.slip_text)

    def test_malay_grounded_answer_is_regenerated_from_the_english_query(self):
        for mode in ("full", "bridge", "english"):
            with self.subTest(mode=mode):
                llm = MalayAnsweringLlm()
                execution, _, _ = run(mode=mode, llm=llm)
                response = execution.response
                self.assertEqual([call[0] for call in llm.grounded_calls],
                                 [MALAY_QUESTION, NORMALISED_QUERY])
                self.assertEqual(llm.grounded_calls[0][1], llm.grounded_calls[1][1])
                self.assertEqual(response.slip_text, english_slip())
                self.assertTrue(is_english_text(slip_body(response.slip_text)))
                self.assertEqual(response.state.value, "answered")
                if mode == "full":
                    self.assertEqual(response.reply_text, MALAY_RENDER)
                    self.assertEqual(llm.render_calls, [((ENGLISH_REPLY, "ms"), {})])

    def test_render_never_reaches_the_slip(self):
        execution, _, _ = run(llm=FakeLlm(render=MALAY_RENDER))
        self.assertEqual(execution.response.reply_text, MALAY_RENDER)
        self.assertNotIn("Buka", execution.response.slip_text)
        self.assertEqual(execution.response.slip_text, english_slip())

    def test_still_malay_after_retry_prints_provenance_without_steps(self):
        llm = MalayAnsweringLlm(english_on_retry=False)
        execution, _, _ = run(llm=llm)
        response = execution.response
        self.assertEqual(len(llm.grounded_calls), 2)
        self.assertEqual(response.state.value, "answered")
        self.assertEqual(slip_body(response.slip_text), "")
        self.assertEqual(response.slip_text, build_slip([], CDC_SOURCE))
        self.assertNotIn("Anda", response.slip_text)

    def test_english_answer_makes_one_grounded_call(self):
        llm = FakeLlm()
        run(llm=llm)
        self.assertEqual(len(llm.grounded_calls), 1)


class BridgeAndEnglishModeTests(unittest.TestCase):
    def test_bridge_wraps_the_english_reply_and_speaks_three_segments(self):
        execution, llm, tts = run(mode="bridge")
        response = execution.response
        self.assertEqual(response.reply_text, f"{BRIDGE_GREETING} {ENGLISH_REPLY} {BRIDGE_CLOSING}")
        self.assertEqual(response.display_text, response.reply_text)
        self.assertEqual(response.language, "ms")
        self.assertEqual(response.slip_text, english_slip())
        self.assertEqual(llm.render_calls, [])
        self.assertEqual(tts.calls, [(BRIDGE_GREETING, "ms"), (ENGLISH_REPLY, "en"),
                                     (BRIDGE_CLOSING, "ms")])
        with wave.open(io.BytesIO(b64decode(response.reply_audio.split(",", 1)[1]))) as joined:
            self.assertEqual(joined.getnframes(), 100 + 200 + 300)
        self.assertEqual((execution.log.reply_mode, execution.log.render_outcome),
                         ("bridge", None))

    def test_english_mode_replies_in_english_throughout(self):
        execution, llm, tts = run(mode="english")
        self.assertEqual(execution.response.reply_text, ENGLISH_REPLY)
        self.assertEqual(execution.response.language, "en")
        self.assertEqual(llm.render_calls, [])
        self.assertEqual((execution.log.reply_language, execution.log.reply_mode),
                         ("ms", "english"))


class RefusalAndActionTests(unittest.TestCase):
    def refuse(self, mode: str):
        pipeline = TurnPipeline(
            stt=FakeStt(MALAY_UNSUPPORTED), llm=FakeLlm(), tts=RecordingTts(),
            retriever=FakeRetriever(), retrieval_active=True,
            evidence_min_dense=0.99, malay_reply_mode=mode,
        )
        return pipeline.execute(
            device_id="d", session_id="s", turn_id="t", audio=upload(),
            audio_preparation_ms=0.0, request_started_at=perf_counter(),
        )

    def test_malay_refusal_uses_malay_wording_and_keeps_the_question(self):
        for mode in ("full", "bridge"):
            with self.subTest(mode=mode):
                response = self.refuse(mode).response
                message = refusal_message(RefusalReason.NO_COVERAGE, "ms")
                self.assertEqual(response.state.value, "refused")
                self.assertEqual(response.language, "ms")
                self.assertEqual(response.reply_text, message.reply_text)
                self.assertEqual(response.display_text, message.display_text)
                lines = response.slip_text.splitlines()
                self.assertEqual(lines[0], "KAKI-TALKIE REFERRAL")
                self.assertIn("You asked:", lines)
                self.assertIn(MALAY_UNSUPPORTED, response.slip_text)

    def test_english_mode_refusal_is_english(self):
        response = self.refuse("english").response
        self.assertEqual(response.language, "en")
        self.assertEqual(response.reply_text,
                         refusal_message(RefusalReason.NO_COVERAGE, "en").reply_text)

    def test_malay_print_confirms_in_malay_and_returns_the_stored_slip(self):
        answered, _, _ = run()
        pipeline = TurnPipeline(
            stt=FakeStt("Tolong cetak slip itu.", "ms"), llm=FakeLlm(), tts=RecordingTts(),
            retriever=FakeRetriever(), retrieval_active=True,
            history=HistoryStub(answered), malay_reply_mode="full",
        )
        response = pipeline.execute(
            device_id="d", session_id="s", turn_id="print", audio=upload(),
            audio_preparation_ms=0.0, request_started_at=perf_counter(),
        ).response
        confirmation = action_message(ActionMessageKind.PRINT_CONFIRMATION, "ms")
        self.assertEqual(response.state.value, "acted")
        self.assertEqual(response.reply_text, confirmation.reply_text)
        self.assertEqual(response.language, "ms")
        self.assertEqual(response.slip_text, answered.response.slip_text)

    def test_malay_nothing_to_act_on_answers_in_malay(self):
        pipeline = TurnPipeline(
            stt=FakeStt("Boleh ulang sekali lagi?", "ms"), llm=FakeLlm(), tts=RecordingTts(),
            retriever=FakeRetriever(), retrieval_active=True, malay_reply_mode="full",
        )
        response = pipeline.execute(
            device_id="d", session_id="s", turn_id="repeat", audio=upload(),
            audio_preparation_ms=0.0, request_started_at=perf_counter(),
        ).response
        self.assertEqual(response.reply_text,
                         action_message(ActionMessageKind.NOTHING_TO_ACT_ON, "ms").reply_text)


class PrintableSlipTests(unittest.TestCase):
    def test_to_printable_folds_punctuation_and_drops_non_latin_1(self):
        self.assertEqual(to_printable("Don’t “wait” — go…"), "Don't \"wait\" - go...")
        self.assertEqual(to_printable("Café naïve"), "Café naïve")
        self.assertEqual(to_printable("我想申请 CHAS 卡"), "CHAS")
        for text in ("Don’t “wait” — go…", "我想申请 CHAS 卡", "Baucar CDC tu?"):
            self.assertTrue(all(ord(character) <= 0xFF for character in to_printable(text)))

    def test_non_latin_question_is_dropped_rather_than_printed_hollow(self):
        for question in ("我想知道怎样申请CHAS卡，去诊所看病有补贴吗？", "我想申请 CHAS 卡"):
            with self.subTest(question=question):
                self.assertGreater(removed_share(question), MAX_QUESTION_CHARACTERS_REMOVED)
                self.assertEqual(build_refusal_slip(question),
                                 f"{REFERRAL_HEADING}\n{REFERRAL_LINE}")

    def test_question_within_the_removal_limit_still_prints(self):
        # 3 of 12 visible characters removed: exactly a quarter, so it prints.
        question = "Baucar CDC 卡卡卡"
        self.assertEqual(removed_share(question), 0.25)
        self.assertIn("You asked:", build_refusal_slip(question).splitlines())
        self.assertIn("Baucar CDC.", build_refusal_slip(question))
        # Folded punctuation is kept, not removed.
        self.assertEqual(removed_share("Don’t “wait”…"), 0.0)
        self.assertIn("You asked:", build_refusal_slip(MALAY_UNSUPPORTED).splitlines())

    def test_question_beyond_the_removal_limit_is_dropped(self):
        question = "Baucar CDC 卡卡卡卡"  # 4 of 13 removed
        self.assertGreater(removed_share(question), MAX_QUESTION_CHARACTERS_REMOVED)
        self.assertNotIn("You asked:", build_refusal_slip(question))

    def test_every_slip_is_latin_1(self):
        for mode in ("full", "bridge", "english"):
            execution, _, _ = run(mode=mode)
            self.assertTrue(all(ord(c) <= 0xFF for c in execution.response.slip_text))


class StorageTests(unittest.TestCase):
    """Migration 0003 stores the diagnostics the debug view reads."""

    def setUp(self) -> None:
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.database = Database.open(Path(scratch.name) / "kaki.db")

    def test_diagnostics_round_trip(self):
        repository = TurnRepository(self.database)
        execution, _, _ = run(llm=FakeLlm(render="Ya."))
        repository.record(execution)
        stored = repository.find(execution.response.turn_id).log
        self.assertEqual((stored.reply_language, stored.reply_mode, stored.render_outcome),
                         ("ms", "full", "fallback_numbers"))

    def test_values_are_constrained(self):
        with self.database.connect() as connection, self.assertRaises(sqlite3.IntegrityError):
            connection.executescript(
                "INSERT INTO devices VALUES ('d', 'now', 'now');"
                "INSERT INTO sessions VALUES ('s', 'd', 'now', NULL, NULL);"
                "INSERT INTO turns (turn_id, session_id, device_id, state, language, reply_text,"
                " display_text, slip_text, timings_json, retrieval_evidence_json, completed_at,"
                " reply_mode) VALUES ('t', 's', 'd', 'answered', 'en', 'r', 'd', '', '{}',"
                " '[]', 'now', 'partial');"
            )


class SettingsTests(unittest.TestCase):
    def test_language_defaults_and_validation(self):
        self.assertEqual(LanguageSettings.from_environment({}), LanguageSettings("en", "full"))
        self.assertEqual(
            LanguageSettings.from_environment(
                {"KAKI_LANGUAGE_PREFERENCE": "ms", "KAKI_MALAY_REPLY_MODE": "english"}
            ),
            LanguageSettings("ms", "english"),
        )
        for env in ({"KAKI_LANGUAGE_PREFERENCE": "zh"}, {"KAKI_MALAY_REPLY_MODE": "partial"}):
            with self.subTest(env=env), self.assertRaises(ValueError):
                LanguageSettings.from_environment(env)

    def test_malay_voice_defaults_to_amira_and_rejects_blank(self):
        self.assertEqual(TtsSettings.from_environment({}).malay_voice, "Amira")
        self.assertEqual(
            TtsSettings.from_environment({"KAKI_TTS_VOICE_MS": "Damayanti"}).malay_voice,
            "Damayanti",
        )
        with self.assertRaises(ValueError):
            TtsSettings.from_environment({"KAKI_TTS_VOICE_MS": "  "})

    def test_rewrite_timeout_defaults_to_four_seconds_and_is_bounded(self):
        self.assertEqual(LlmSettings.from_environment({}).rewrite_timeout_seconds, 4.0)
        self.assertEqual(
            LlmSettings.from_environment(
                {"KAKI_QUERY_REWRITE_TIMEOUT_SECONDS": "6"}
            ).rewrite_timeout_seconds,
            6.0,
        )
        for value in ("0", "31", "soon"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                LlmSettings.from_environment({"KAKI_QUERY_REWRITE_TIMEOUT_SECONDS": value})

    def test_pipeline_rejects_unknown_settings(self):
        with self.assertRaises(ValueError):
            TurnPipeline(malay_reply_mode="partial")
        with self.assertRaises(ValueError):
            TurnPipeline(language_preference="zh")


if __name__ == "__main__":
    unittest.main()
