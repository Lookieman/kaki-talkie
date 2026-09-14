# v1.3 | 13-Sep-2026 | WP5.1: build the pipeline with the configured language settings.
# v1.2 | 13-Sep-2026 | Run WP4.2 action items in sessions on a disposable database.
# v1.1 | 12-Sep-2026 | Drop the redaction check; redaction is no longer performed.
# v1.0 | 12-Sep-2026 | Provide the WP3.4 devset regression over the real turn pipeline.
"""Measure routing, refusal and grounding decisions over the committed devset.

Drives the real `TurnPipeline` in-process with a transcript-injecting STT port
and the configured LLM and retriever ports, so it exercises the production
routing rules, evidence gate, grounded generation and citation attribution
without speech-recognition variance or audio fixtures. Reports intent accuracy
against the WP3-AT-11 target and whether every golden-path item passed.

Requires MLX-LM on its loopback port and the grounded configuration
(`KAKI_RETRIEVAL_MODE=rag`, `KAKI_LLM_MODE=qwen`, `KAKI_DATA_ROOT`, `HF_HOME`)
per runbook 8.2 WP3.4 Test 4. It needs no Whisper, no `say` and no FastAPI, and
it may run while the stack is up: it loads its own copy of the embedding model,
so expect roughly 1.2 GB of additional resident memory.

WP4.2 action items (`repeat_previous`, `print_previous`) resolve from stored
turns, so every executed item is recorded in a disposable SQLite database.
Each item runs in its own session unless it names an earlier item in `after`,
in which case it joins that item's session. An action item also checks which
turn it resolved to, its outcome, and that the repeated text or printed slip
is unchanged from that turn.

Speech is deliberately not synthesised. A no-op TTS port keeps the measurement
about decisions rather than audio, so `reply_audio` is null in every result.

Side effects: sends one generation request per supported item to the local LLM
service, plus one query rewrite where the guard calls for it. Writes one
disposable SQLite database under the system temporary directory, removed on
exit; the live database is never opened. Exit status is zero only when intent accuracy meets the target and every
golden-path item passes; 2 indicates a usage or configuration error.
"""

import argparse
import io
import json
import sys
import tempfile  #v1.2
import wave
from pathlib import Path
from time import perf_counter

from kaki_backend.config import LanguageSettings, LlmSettings, RetrievalSettings  #v1.3
from kaki_backend.contracts.ports import LanguageEvidence, Transcription
from kaki_backend.contracts.turn_log import TurnExecution  #v1.2
from kaki_backend.orchestration.intent_router import ACTION_INTENTS, Intent  #v1.2
from kaki_backend.orchestration.turn_pipeline import TurnPipeline
from kaki_backend.persistence.database import Database  #v1.2
from kaki_backend.persistence.repositories import TurnRepository  #v1.2

DEFAULT_DEVSET = Path(__file__).resolve().parents[1] / "agent/data/devset.jsonl"
INTENT_TARGET = 0.80
REQUIRED_FIELDS = ("id", "utterance", "expected_intent")
ACTION_INTENT_VALUES = frozenset(intent.value for intent in ACTION_INTENTS)  #v1.2


class InjectedStt:
    """Return a fixed transcript, ignoring the audio it is handed.

    The devset is text, and speech recognition is measured separately (WP2.2).
    Injecting here keeps every other production stage in the measurement.
    """

    def __init__(self) -> None:
        """Start with no transcript; `speak` sets the one for the next turn."""
        self._transcript = ""
        self._language = "en"

    def speak(self, transcript: str, language: str) -> None:
        """Set the transcript the next `transcribe` call returns."""
        self._transcript = transcript
        self._language = language

    def ready(self) -> bool:
        """Report readiness; the injected port has no runtime to check."""
        return True

    def transcribe(self, audio: bytes) -> Transcription:
        """Return the injected transcript with its declared language evidence."""
        return Transcription(
            text=self._transcript,
            evidence=LanguageEvidence(language=self._language),
        )


class SilentTts:
    """Accept any reply text and synthesise nothing.

    Speech adds seconds per item and proves nothing about a routing decision,
    so the runner deliberately reports a null `reply_audio`.
    """

    def ready(self) -> bool:
        """Report readiness; there is no engine to check."""
        return True

    def synthesize(self, reply_text: str, language: str = "en") -> str | None:  #v1.3
        """Return no audio reference, which the contract permits."""
        return None


def silent_audio() -> bytes:
    """Return a short valid 16 kHz mono PCM WAV for the pipeline to normalise."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


def load_devset(path: Path) -> list[dict[str, object]]:
    """Read and validate the devset, raising ValueError with the offending line."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"cannot read the devset: {error}") from None
    items: list[dict[str, object]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            raise ValueError(f"{path} line {number} is not valid JSON.") from None
        missing = [field for field in REQUIRED_FIELDS if not item.get(field)]
        if missing:
            raise ValueError(f"{path} line {number} is missing {', '.join(missing)}.")
        after = item.get("after")  #v1.2
        if after is not None and after not in {earlier["id"] for earlier in items}:
            raise ValueError(
                f"{path} line {number}: after {after!r} must name an earlier item."
            )
        items.append(item)
    if not items:
        raise ValueError(f"{path} contains no devset items.")
    return items


def open_history(directory: str) -> TurnRepository:  #v1.2
    """Open a disposable turn store for the run; the caller owns the directory."""
    return TurnRepository(Database.open(Path(directory) / "regression.db"))


def build_pipeline(stt: InjectedStt, history: TurnRepository) -> TurnPipeline:  #v1.2
    """Assemble the pipeline from configuration, with STT, TTS and the store replaced."""
    retrieval = RetrievalSettings.from_environment()
    language = LanguageSettings.from_environment()  #v1.3
    return TurnPipeline(
        stt=stt,
        llm=LlmSettings.from_environment().create_port(),
        tts=SilentTts(),
        retriever=retrieval.create_port(),
        retrieval_active=retrieval.active,
        query_normalise=retrieval.normalise,
        evidence_min_dense=retrieval.evidence_min_dense,
        history=history,  #v1.2
        language_preference=language.preference,  #v1.3
        malay_reply_mode=language.malay_reply_mode,  #v1.3
    )


def turn_id_for(item_id: object) -> str:  #v1.2
    """Return the deterministic turn_id a devset item runs under."""
    return f"regression-{item_id}"


def _action_checks(item: dict[str, object], execution: TurnExecution,
                   executed: dict[str, TurnExecution]) -> dict[str, bool]:  #v1.2
    """Check an action item's resolution, outcome and unchanged stored content."""
    log, response = execution.log, execution.response
    expected_previous = item.get("expected_previous_id")
    checks = {
        "previous_turn": log.previous_turn_id == (
            turn_id_for(expected_previous) if expected_previous else None
        ),
        "action_outcome": log.action_outcome == item.get("expected_action_outcome"),
    }
    previous = executed.get(str(expected_previous)) if expected_previous else None
    if previous is None:
        checks["content_unchanged"] = not response.slip_text and not response.sources
    elif log.intent == Intent.REPEAT_PREVIOUS.value:
        checks["content_unchanged"] = (
            response.reply_text == previous.response.reply_text
            and response.sources == previous.response.sources and not response.slip_text
        )
    else:
        checks["content_unchanged"] = (
            response.slip_text == previous.response.slip_text
            and response.sources == previous.response.sources
        )
    return checks


def evaluate(item: dict[str, object], pipeline: TurnPipeline, stt: InjectedStt,
             audio: bytes, session_id: str,
             executed: dict[str, TurnExecution]) -> tuple[dict[str, object], object]:  #v1.2
    """Run one devset item and compare the outcome with its expected fields.

    Returns the result record and the execution, which the caller stores so
    later action items can resolve to it.
    """
    stt.speak(str(item["utterance"]), str(item.get("language") or "en"))
    started = perf_counter()
    execution = pipeline.execute(
        device_id="run-regression", session_id=session_id,  #v1.2
        turn_id=turn_id_for(item["id"]), audio=audio,
        audio_preparation_ms=0.0, request_started_at=started,
    )
    response, log = execution.response, execution.log
    cited = log.cited_source_id
    expected_source = item.get("expected_source_id")
    is_action = item["expected_intent"] in ACTION_INTENT_VALUES  #v1.2
    checks = {
        "intent": log.intent == item["expected_intent"],
        "state": response.state.value == item.get("expected_state", response.state.value),
        "refusal_reason": log.refusal_reason == item.get("expected_refusal_reason"),
    }
    if is_action:  #v1.2
        # An action cites nothing itself; it carries the resolved turn's sources.
        checks.update(_action_checks(item, execution, executed))
    else:
        checks["cited_source"] = (
            cited == expected_source if expected_source else not response.sources
        )
    return {
        "id": item["id"],
        "golden_path": item.get("golden_path"),
        "language": item.get("language"),
        "expected_intent": item["expected_intent"],
        "actual_intent": log.intent,
        "expected_state": item.get("expected_state"),
        "actual_state": response.state.value,
        "expected_refusal_reason": item.get("expected_refusal_reason"),
        "actual_refusal_reason": log.refusal_reason,
        "expected_source_id": expected_source,
        "cited_source_id": cited,
        "best_dense_score": log.best_dense_score,
        "evidence_min_dense": log.evidence_min_dense,
        "previous_turn_id": getattr(log, "previous_turn_id", None),  #v1.2
        "action_outcome": getattr(log, "action_outcome", None),  #v1.2
        "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        "checks": checks,
        "passed": all(checks.values()),
    }, execution


def build_parser() -> argparse.ArgumentParser:
    """Describe the devset selection and the intent target."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--devset", type=Path, default=DEFAULT_DEVSET,
        help=f"Devset JSONL to run (default {DEFAULT_DEVSET})",
    )
    parser.add_argument(
        "--intent-target", type=float, default=INTENT_TARGET,
        help=f"Minimum intent accuracy to pass, 0-1 (default {INTENT_TARGET})",
    )
    return parser


def run_regression(args: argparse.Namespace) -> int:
    """Run every devset item, print the JSON report and return the exit status."""
    if not 0 < args.intent_target <= 1:
        print("FAIL: --intent-target must be between 0 and 1.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="kaki-regression-") as scratch:  #v1.2
        try:
            items = load_devset(args.devset)
            stt = InjectedStt()
            history = open_history(scratch)
            pipeline = build_pipeline(stt, history)
        except ValueError as error:
            print(f"FAIL: {error}", file=sys.stderr)
            return 2
        results = run_items(items, pipeline, stt, history)
    return report_results(args, results)


def run_items(items: list[dict[str, object]], pipeline: TurnPipeline, stt: InjectedStt,
              history: TurnRepository) -> list[dict[str, object]]:  #v1.2
    """Run items in file order, recording each so later action items can resolve."""
    audio = silent_audio()
    sessions: dict[str, str] = {}
    executed: dict[str, TurnExecution] = {}
    results = []
    for item in items:
        item_id = str(item["id"])
        after = item.get("after")
        sessions[item_id] = sessions[str(after)] if after else f"regression-session-{item_id}"
        result, execution = evaluate(item, pipeline, stt, audio, sessions[item_id], executed)
        history.record(execution)
        executed[item_id] = execution
        results.append(result)
    return results


def report_results(args: argparse.Namespace, results: list[dict[str, object]]) -> int:  #v1.2
    """Print the JSON report and return the exit status for the run."""
    intent_matches = sum(1 for result in results if result["checks"]["intent"])
    golden = [result for result in results if result["golden_path"]]
    golden_passed = [result for result in golden if result["passed"]]
    accuracy = intent_matches / len(results)
    report = {
        "devset": str(args.devset),
        "items": len(results),
        "results": results,
        "intent_accuracy": round(accuracy, 4),
        "intent_target": args.intent_target,
        "golden_paths_passed": len(golden_passed),
        "golden_paths_total": len(golden),
        "items_passed": sum(1 for result in results if result["passed"]),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    failures = [result["id"] for result in results if not result["passed"]]
    golden_failures = [result["id"] for result in golden if not result["passed"]]
    if accuracy < args.intent_target:
        print(f"FAIL: intent accuracy {accuracy:.2%} is below the "
              f"{args.intent_target:.0%} target; failing items: "
              f"{', '.join(failures)}", file=sys.stderr)
        return 1
    if golden_failures:
        print(f"FAIL: golden-path items did not pass: {', '.join(golden_failures)}",
              file=sys.stderr)
        return 1
    if failures:
        print(f"PASS: intent accuracy {accuracy:.2%} and all golden paths passed; "
              f"non-gating items still failing: {', '.join(failures)}", file=sys.stderr)
        return 0
    print(f"PASS: intent accuracy {accuracy:.2%}; all {len(results)} items and "
          f"{len(golden)} golden paths passed.", file=sys.stderr)
    return 0


def main() -> int:
    """Parse arguments and run the devset regression against the local stack."""
    return run_regression(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
