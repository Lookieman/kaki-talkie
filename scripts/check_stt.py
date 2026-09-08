# v1.0 | 08-Sep-2026 | Provide the WP2.2 owner CLI for STT readiness, lifecycle and retention.
"""Check the configured STT path for WP2.2 owner validation.

Reads `KAKI_STT_MODE`, `KAKI_WHISPER_URL` and `KAKI_STT_TIMEOUT_SECONDS` like
the backend. `--readiness` reports whether the configured STT port is ready.
`--input` runs an original turn, a same-ID retry and an unselected control
turn through the real pipeline, then reports transcript, language evidence,
timings, audio release, idempotency and retention checks as JSON.

Side effects: `--input` calls the local STT service (twice when checks pass).
With `--retain-test-audio --consent-to-retain` it also writes exactly one copy
of the input under `KAKI_DATA_ROOT/wp2.2/retained`; nothing else is written.
Exit status is zero only when every applicable check passes.
"""

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from kaki_backend.config import SttSettings
from kaki_backend.contracts.ports import SttPort, Transcription
from kaki_backend.orchestration.audio_lifecycle import TestAudioRetention, TurnAudio
from kaki_backend.orchestration.audio_normalisation import MAX_INPUT_BYTES
from kaki_backend.orchestration.idempotency import TurnService
from kaki_backend.orchestration.turn_pipeline import TurnPipeline


class RecordingStt:
    """Wrap the configured STT port to count calls and capture the last result.

    The capture exists so this owner CLI can print the transcript and language
    evidence; the backend itself never logs them.
    """

    def __init__(self, inner: SttPort) -> None:
        """Delegate to the real port; record nothing until it is used."""
        self.inner = inner
        self.calls = 0
        self.last: Transcription | None = None

    def ready(self) -> bool:
        """Report the wrapped port's readiness unchanged."""
        return self.inner.ready()

    def transcribe(self, audio: bytes) -> Transcription:
        """Count the call and keep the typed result for CLI reporting."""
        self.calls += 1
        self.last = self.inner.transcribe(audio)
        return self.last


def build_parser() -> argparse.ArgumentParser:
    """Describe the two CLI actions and the explicit retention flags."""
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--readiness", action="store_true", help="Report STT readiness and exit"
    )
    action.add_argument(
        "--input", type=Path, help="Deliberate test audio to run through the pipeline"
    )
    parser.add_argument(
        "--retain-test-audio", action="store_true",
        help="Retain the original test input; requires --consent-to-retain",
    )
    parser.add_argument(
        "--consent-to-retain", action="store_true",
        help="Confirm explicit consent to retain the test input",
    )
    return parser


def check_readiness(settings: SttSettings) -> int:
    """Print mode, URL and readiness; return zero only when the port is ready."""
    ready = settings.create_port().ready()
    print(json.dumps({"mode": settings.mode, "url": settings.url, "ready": ready}, indent=2))
    if not ready:
        print("FAIL: STT port is not ready.", file=sys.stderr)
        return 1
    return 0


def evidence_report(transcription: Transcription | None) -> dict[str, object]:
    """Summarise captured language evidence and whether it is well formed."""
    if transcription is None or transcription.evidence is None:
        return {"present": False, "language": None, "probability": None, "well_formed": False}
    probability = transcription.evidence.probability
    well_formed = probability is None or (math.isfinite(probability) and 0 <= probability <= 1)
    return {
        "present": True,
        "language": transcription.evidence.language,
        "probability": probability,
        "well_formed": well_formed,
    }


def count_retained_files(data_root: Path) -> int:
    """Count files in the retained-audio directory; a missing directory counts zero."""
    directory = data_root / "wp2.2" / "retained"
    if not directory.is_dir():
        return 0
    return sum(1 for entry in directory.iterdir() if entry.is_file())


async def run_turns(
    service: TurnService, audio: bytes, retention: TestAudioRetention | None,
) -> tuple[dict[str, object], list[bool]]:
    """Run original, same-ID retry and control turns; report responses and buffer release."""
    turn_id = f"check-stt-{uuid4().hex[:12]}"
    released: list[bool] = []
    responses = []
    for label, current_id, current_retention in (
        ("original", turn_id, retention),
        ("retry", turn_id, None),
        ("control", f"{turn_id}-control", None),
    ):
        owned = TurnAudio(audio)
        response = await service.process(
            device_id="check-stt", session_id="check-stt", turn_id=current_id,
            audio=owned, audio_preparation_ms=0.0, request_started_at=perf_counter(),
            retention=current_retention,
        )
        released.append(len(owned.data) == 0)
        responses.append((label, response))
    original, retry, control = (response for _, response in responses)
    summary: dict[str, object] = {
        "state": original.state.value,
        "retry_matches_original": retry.model_dump() == original.model_dump(),
        "control_state": control.state.value,
    }
    return summary, released


def check_transcription(args: argparse.Namespace, settings: SttSettings) -> int:
    """Run the three-turn lifecycle and print the JSON report; return non-zero on failure."""
    if args.retain_test_audio != args.consent_to_retain:
        print(
            "FAIL: --retain-test-audio and --consent-to-retain must be used together.",
            file=sys.stderr,
        )
        return 2
    retention = None
    data_root = Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if args.retain_test_audio:
        if not data_root.is_absolute():
            print("FAIL: retention requires an absolute KAKI_DATA_ROOT.", file=sys.stderr)
            return 2
        retention = TestAudioRetention(data_root, consent=True)
    try:
        audio = args.input.read_bytes()
    except OSError as error:
        print(f"FAIL: cannot read input: {error}", file=sys.stderr)
        return 2
    if not audio or len(audio) > MAX_INPUT_BYTES:
        print("FAIL: input is empty or exceeds the supported size.", file=sys.stderr)
        return 2

    port = RecordingStt(settings.create_port())
    if not port.ready():
        print("FAIL: STT port is not ready; start the model service first.", file=sys.stderr)
        return 1
    retained_before = count_retained_files(data_root) if data_root.is_absolute() else 0

    service = TurnService(TurnPipeline(stt=port))
    turns, released = asyncio.run(run_turns(service, audio, retention))

    retained_after = count_retained_files(data_root) if data_root.is_absolute() else 0
    evidence = evidence_report(port.last)
    transcript = port.last.text if port.last is not None else None
    timings = [log.timings.model_dump() for log in service.logs]
    checks = {
        "turn_answered": turns["state"] == "answered",
        "transcript_non_empty": bool(transcript),
        "language_evidence": bool(evidence["present"]) and bool(evidence["well_formed"]),
        "audio_released_every_turn": all(released),
        "single_execution_for_retry": turns["retry_matches_original"]
        and service.execution_count == 2,
        "two_stt_calls_including_control": port.calls == 2,
        "retention_as_selected": (
            retention is not None and retention.path is not None
            and retained_after == retained_before + 1
            if args.retain_test_audio
            else retained_after == retained_before
        ),
    }
    if settings.mode != "whisper":
        # Canned mode carries no genuine language evidence; do not fail on it.
        checks["language_evidence"] = evidence["present"] is False
    report = {
        "mode": settings.mode,
        "url": settings.url,
        "transcript": transcript,
        "language_evidence": evidence,
        "turns": turns,
        "stt_calls": port.calls,
        "pipeline_executions": service.execution_count,
        "timings_ms": timings,
        "retained_path": str(retention.path) if retention and retention.path else None,
        "checks": checks,
    }
    print(json.dumps(report, indent=2))
    if all(checks.values()):
        print("PASS: all WP2.2 STT checks succeeded.", file=sys.stderr)
        return 0
    failed = ", ".join(sorted(name for name, passed in checks.items() if not passed))
    print(f"FAIL: {failed}", file=sys.stderr)
    return 1


def main() -> int:
    """Dispatch readiness or transcription checks using backend configuration rules."""
    args = build_parser().parse_args()
    try:
        settings = SttSettings.from_environment()
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    if args.readiness:
        return check_readiness(settings)
    return check_transcription(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
