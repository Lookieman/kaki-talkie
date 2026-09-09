# v1.2 | 10-Sep-2026 | Add the WP3.1 corpus ingestion and idempotency checks.
# v1.1 | 09-Sep-2026 | Add the WP2.4 speech, readiness and full-loop checks.
# v1.0 | 09-Sep-2026 | Provide the WP2.3 owner checks behind a per-unit check runner.
"""Run the automated owner checks for one work-package unit and tier.

The script is a registry of independent, rerunnable validation checks keyed by
implementation unit and test tier (`A` = deterministic developer checks,
`B` = Mac runtime checks against live local services). Only units registered
here are supported; earlier units keep their existing dedicated scripts.

Currently registered:
- WP2.3 tier B - MLX/Qwen bounded generation. Reads `KAKI_LLM_MODE`,
  `KAKI_LLM_URL` and `KAKI_LLM_TIMEOUT_SECONDS` like the backend and expects
  the MLX-LM service on 127.0.0.1:8082 (runbook 7.3).
- WP2.4 tier B - macOS say speech, health readiness and the real full turn.
  Reads `KAKI_TTS_MODE`/`KAKI_TTS_TIMEOUT_SECONDS` for the direct synthesis
  check and expects the complete stack (Whisper, MLX-LM, FastAPI in real
  modes) already running per runbook 7.4.1.
- WP3.1 tier B - grounded-corpus ingestion (WP3-AT-01/02). Requires
  `KAKI_DATA_ROOT` and the installed `kaki-rag` package; runs the real
  ingestion twice over `rag/corpus/allowlist.yaml`, checking dated
  snapshots, full per-chunk provenance and hash/chunk stability. Needs no
  model services.

Side effects: WP2.3 tier B sends five fixed-transcript generation requests to
the local LLM service. WP2.4 tier B synthesises one fixed sentence locally
and submits one packaged fixture turn (fresh `turn_id`) to the running
backend, which transcribes, generates and synthesises it, writing nothing to
disk. WP3.1 tier B fetches every allowlisted official page over the network
twice and writes snapshots and processed chunks under
`$KAKI_DATA_ROOT/corpus`. Exit status is zero only when every check passes;
2 indicates a usage or configuration error.
"""

import argparse
import io
import json
import os
import re
import sys
import wave
from pathlib import Path
from base64 import b64decode
from importlib.resources import files
from time import perf_counter
from uuid import uuid4

import httpx

from kaki_backend.config import APPROVED_QWEN_MODEL, LlmSettings, TtsSettings
from kaki_backend.contracts.ports import LlmError, TtsError
from kaki_backend.orchestration.canned_ports import CannedLlmPort, CannedSttPort

GENERATION_RUNS = 5
MAX_REPLY_WORDS = 60
FIXED_TRANSCRIPT = "What time does the community centre open tomorrow morning?"


def check_wp23_tier_b() -> tuple[dict[str, object], dict[str, bool]]:
    """Prove readiness and five bounded generations through the real adapter.

    Returns the printable report body and the named pass/fail checks. Requires
    `KAKI_LLM_MODE=qwen` and a resident model on the configured loopback port.
    """
    settings = LlmSettings.from_environment()
    report: dict[str, object] = {
        "mode": settings.mode,
        "url": settings.url,
        "model": APPROVED_QWEN_MODEL,
        "transcript": FIXED_TRANSCRIPT,
        "runs": [],
    }
    checks = {
        "mode_is_qwen": settings.mode == "qwen",
        "default_mode_stays_canned": LlmSettings.from_environment({}).mode == "canned",
    }
    if not checks["mode_is_qwen"]:
        print("FAIL: export KAKI_LLM_MODE=qwen before running WP2.3 tier B.", file=sys.stderr)
        checks["service_ready"] = False
        return report, checks

    port = settings.create_port()
    checks["service_ready"] = port.ready()
    if not checks["service_ready"]:
        print("FAIL: LLM service is not ready; start it first (runbook 7.3.1).", file=sys.stderr)
        return report, checks

    runs: list[dict[str, object]] = []
    for _ in range(GENERATION_RUNS):
        started = perf_counter()
        try:
            reply = port.generate(FIXED_TRANSCRIPT)
            error = None
        except LlmError as failure:
            reply = None
            error = failure.code
        latency_ms = (perf_counter() - started) * 1000
        words = len(reply.split()) if reply else 0
        runs.append({
            "reply": reply, "words": words,
            "latency_ms": round(latency_ms, 1), "error": error,
        })
    report["runs"] = runs
    checks["all_runs_generated"] = all(run["error"] is None for run in runs)
    checks["all_replies_non_empty"] = all(run["words"] > 0 for run in runs)
    checks["all_replies_within_60_words"] = all(
        0 < int(run["words"]) <= MAX_REPLY_WORDS for run in runs
    )
    checks["no_think_content"] = all(
        "<think>" not in (run["reply"] or "") for run in runs
    )
    return report, checks


BACKEND_URL = "http://127.0.0.1:8000"
FIXED_SPEECH_SENTENCE = "KaKi-Talkie text to speech is working."
POSITIVE_STAGES = ("audio_preparation_ms", "stt_ms", "routing_ms", "llm_ms", "tts_ms",
                   "overall_ms")
UNUSED_STAGES = ("retrieval_ms", "live_lookup_ms")


def _decode_wav_frames(data_url: object) -> int:
    """Return the PCM frame count of a WAV data URL, or -1 when it is not one."""
    if not isinstance(data_url, str) or not data_url.startswith("data:audio/wav;base64,"):
        return -1
    try:
        payload = b64decode(data_url.split(",", 1)[1], validate=True)
        with wave.open(io.BytesIO(payload), "rb") as recording:
            if recording.getcomptype() != "NONE":
                return -1
            return recording.getnframes()
    except (ValueError, wave.Error, EOFError):
        return -1


def check_wp24_tier_b() -> tuple[dict[str, object], dict[str, bool]]:
    """Prove say speech, health readiness and one real full turn over HTTP.

    Requires `KAKI_TTS_MODE=say` in this shell and the full real-mode stack
    already running (runbook 7.4.1). Covers WP2-AT-05/06/09/10.
    """
    settings = TtsSettings.from_environment()
    report: dict[str, object] = {"tts_mode": settings.mode, "backend_url": BACKEND_URL}
    checks = {
        "tts_mode_is_say": settings.mode == "say",
        "default_tts_mode_stays_canned": TtsSettings.from_environment({}).mode == "canned",
    }
    if not checks["tts_mode_is_say"]:
        print("FAIL: export KAKI_TTS_MODE=say before running WP2.4 tier B.", file=sys.stderr)
        return report, checks

    port = settings.create_port()
    checks["say_engine_ready"] = port.ready()
    try:
        speech = port.synthesize(FIXED_SPEECH_SENTENCE)
        say_frames = _decode_wav_frames(speech)
    except TtsError as failure:
        report["say_error"] = failure.code
        say_frames = -1
    report["say_speech_frames"] = say_frames
    checks["say_speech_is_playable_wav"] = say_frames > 0

    fixture = files("kaki_backend").joinpath("fixtures/canned_reply.wav").read_bytes()
    turn_id = f"wp24-check-{uuid4().hex[:12]}"
    canned_reply = CannedLlmPort().generate("")
    canned_transcript = CannedSttPort().transcribe(b"x").text
    try:
        with httpx.Client(timeout=180, trust_env=False, follow_redirects=False) as client:
            health = client.get(BACKEND_URL + "/api/health").json()
            turn_started = perf_counter()
            turn = client.post(
                BACKEND_URL + "/api/device/turn",
                data={"device_id": "wp24-check", "session_id": "wp24-check",
                      "turn_id": turn_id},
                files={"audio": ("canned_reply.wav", fixture, "audio/wav")},
            ).json()
            report["turn_elapsed_ms"] = round((perf_counter() - turn_started) * 1000, 1)
            debug = client.get(BACKEND_URL + "/api/device/debug/last-turn").json()
    except (httpx.HTTPError, ValueError):
        print("FAIL: the backend stack is not reachable; start it first (runbook 7.4.1).",
              file=sys.stderr)
        checks["stack_reachable"] = False
        return report, checks
    checks["stack_reachable"] = True

    report["health"] = health
    checks["health_reports_all_ready"] = all(
        health.get(name) is True for name in ("stt_ready", "llm_ready", "tts_ready")
    ) and health.get("status") == "ok"

    reply_frames = _decode_wav_frames(turn.get("reply_audio"))
    report["turn"] = {
        "turn_id": turn.get("turn_id"), "state": turn.get("state"),
        "reply_text": turn.get("reply_text"), "display_text": turn.get("display_text"),
        "reply_audio_frames": reply_frames,
    }
    checks["turn_answered"] = turn.get("state") == "answered"
    checks["reply_text_non_empty"] = bool(str(turn.get("reply_text") or "").strip())
    checks["display_text_non_empty"] = bool(str(turn.get("display_text") or "").strip())
    checks["reply_is_generated_not_canned"] = turn.get("reply_text") != canned_reply
    checks["reply_audio_is_playable_wav"] = reply_frames > 0

    timings = debug.get("timings_ms") or {}
    report["debug"] = debug
    transcript = debug.get("transcript")
    checks["transcript_is_real"] = bool(transcript) and transcript != canned_transcript
    checks["language_evidence_present"] = debug.get("language_evidence") is not None
    checks["invoked_stage_timings_positive"] = all(
        isinstance(timings.get(stage), (int, float)) and timings.get(stage) > 0
        for stage in POSITIVE_STAGES
    )
    checks["retrieval_stays_unused"] = all(
        timings.get(stage) is None for stage in UNUSED_STAGES
    )
    return report, checks


ALLOWLIST_PATH = Path(__file__).resolve().parents[1] / "rag/corpus/allowlist.yaml"
DATED_SNAPSHOT_DIRECTORY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_processed_chunks(processed_path: str) -> list[dict[str, object]]:
    """Read the processed chunk records an ingestion report points at."""
    lines = Path(processed_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def check_wp31_tier_b() -> tuple[dict[str, object], dict[str, bool]]:
    """Prove WP3-AT-01/02 with two real ingestion runs over the committed allowlist.

    Requires an absolute `KAKI_DATA_ROOT`, network access to the allowlisted
    official domains and `python -m pip install -e rag` (runbook 8.1 WP3.1).
    """
    from kaki_rag.ingest.metadata import (
        PROVENANCE_FIELDS,
        REQUIRED_PROVENANCE_FIELDS,
    )
    from kaki_rag.ingest.pipeline import run_ingestion

    data_root = Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if not data_root.is_absolute():
        raise ValueError("export an absolute KAKI_DATA_ROOT first (runbook 8.1 WP3.1).")

    try:
        first = run_ingestion(ALLOWLIST_PATH, data_root)
        first_chunk_ids = [
            record.get("chunk_id") for record in _load_processed_chunks(first.processed_path)
        ]
        second = run_ingestion(ALLOWLIST_PATH, data_root)
    except OSError as error:
        raise ValueError(f"cannot use the data root: {error}") from None
    report: dict[str, object] = {
        "allowlist": str(ALLOWLIST_PATH),
        "data_root": str(data_root),
        "first_run": first.as_dict(),
        "second_run": second.as_dict(),
    }

    chunks = _load_processed_chunks(second.processed_path)
    chunk_ids = [record.get("chunk_id") for record in chunks]
    snapshot_paths = [
        Path(result.snapshot_path) for result in first.results if result.snapshot_path
    ]
    checks = {
        "allowlist_has_five_or_more_sources": len(first.results) >= 5,
        "first_run_ingested_every_source": first.succeeded,
        "every_source_has_a_dated_snapshot": bool(snapshot_paths) and len(
            snapshot_paths
        ) == len(first.results) and all(
            path.is_file()
            and DATED_SNAPSHOT_DIRECTORY.match(path.parent.name) is not None
            and path.with_suffix(".meta.json").is_file()
            for path in snapshot_paths
        ),
        "every_chunk_carries_full_provenance": bool(chunks) and all(
            isinstance(record.get("provenance"), dict)
            and set(record["provenance"]) == set(PROVENANCE_FIELDS)
            and all(record["provenance"][field] for field in REQUIRED_PROVENANCE_FIELDS)
            for record in chunks
        ),
        "every_chunk_text_is_non_empty": bool(chunks) and all(
            str(record.get("text", "")).strip() for record in chunks
        ),
        "no_duplicate_chunk_ids": len(chunk_ids) == len(set(chunk_ids)),
        "second_run_reports_every_source_unchanged": all(
            result.status == "unchanged" for result in second.results
        ),
        "content_hashes_stable_across_runs": all(
            before.content_hash == after.content_hash
            for before, after in zip(first.results, second.results)
        ),
        "snapshots_not_duplicated_across_runs": all(
            before.snapshot_path == after.snapshot_path
            for before, after in zip(first.results, second.results)
        ),
        "chunk_identity_stable_across_runs": first_chunk_ids == chunk_ids,
    }
    return report, checks


REGISTRY = {
    ("WP2.3", "B"): check_wp23_tier_b,
    ("WP2.4", "B"): check_wp24_tier_b,
    ("WP3.1", "B"): check_wp31_tier_b,
}


def build_parser() -> argparse.ArgumentParser:
    """Describe the unit/tier selection; only registered combinations run."""
    supported = ", ".join(f"{unit} tier {tier}" for unit, tier in sorted(REGISTRY))
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--unit", required=True, help=f"Implementation unit to check (supported: {supported})"
    )
    parser.add_argument(
        "--tier", required=True, choices=["A", "B"],
        help="Test tier: A deterministic developer checks, B Mac runtime checks",
    )
    return parser


def main() -> int:
    """Run the registered checks for the requested unit/tier and print a JSON report."""
    args = build_parser().parse_args()
    runner = REGISTRY.get((args.unit, args.tier))
    if runner is None:
        supported = ", ".join(f"{unit} tier {tier}" for unit, tier in sorted(REGISTRY))
        print(
            f"FAIL: {args.unit} tier {args.tier} is not covered by wp_check.py. "
            f"Supported: {supported}. Earlier units use their dedicated scripts.",
            file=sys.stderr,
        )
        return 2
    try:
        report, checks = runner()
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    print(json.dumps(
        {"unit": args.unit, "tier": args.tier, **report, "checks": checks}, indent=2
    ))
    if all(checks.values()):
        print(f"PASS: all {args.unit} tier {args.tier} checks succeeded.", file=sys.stderr)
        return 0
    failed = ", ".join(sorted(name for name, passed in checks.items() if not passed))
    print(f"FAIL: {failed}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
