# v3.2 | 20-Sep-2026 | WP6.1 tier B builds its BackendClient with KAKI_DEVICE_TOKEN; it was the one live device client v3.1 missed.
# v3.1 | 20-Sep-2026 | Add WP6.4 (tier A auth/retry/systemd checks, tier B live auth and replay); live tier B clients carry the device bearer token.
# v3.0 | 20-Sep-2026 | Add WP6.2 (tier A hardware-layer checks, tier C Pi service checks) and tier C; allow gpiozero on the device.
# v2.9 | 19-Sep-2026 | Keep every suite's full output: --evidence writes <suite>.output.txt; JSON tails hold 20 lines.
# v2.8 | 18-Sep-2026 | Add WP6.6: admin-surface suites (tier A) and the live admin flow (tier B).
# v2.7 | 16-Sep-2026 | Add WP6.1: thin-client static inspection (tier A) and a scripted mock turn (tier B).
# v2.6 | 14-Sep-2026 | WP5.1 text turn also runs the live Whisper transcript; the slip body must be English with steps.
# v2.5 | 14-Sep-2026 | WP4.2 and WP4.5 schema checks equal the packaged migration count.
# v2.4 | 13-Sep-2026 | Add the WP5.1 voice, Malay retrieval and Malay text-turn checks.
# v2.3 | 13-Sep-2026 | Add the WP4.5 backup readability and devset action checks.
# v2.2 | 13-Sep-2026 | WP4.2: debug check matches the newest-turn contract; add a repeat replay.
# v2.1 | 13-Sep-2026 | Add the WP4.2 action checks; WP4.1 accepts later schema versions.
# v2.0 | 13-Sep-2026 | Add the WP4.1 durable-turn and restart-replay checks.
# v1.9 | 12-Sep-2026 | Drop the credential fixture and secret checks from WP3.4.
# v1.8 | 12-Sep-2026 | Add the WP3.4 refusal checks; speak a supported question in rag mode.
# v1.7 | 12-Sep-2026 | Check the answer is attributed to the evidence it actually used.
# v1.6 | 12-Sep-2026 | Load HF_TOKEN from the project-root .env before embedding checks.
# v1.5 | 11-Sep-2026 | Add the WP3.3 grounded-turn checks; scope retrieval use by mode.
# v1.4 | 10-Sep-2026 | Add the WP3.2 indexing and hybrid-retrieval checks.
# v1.3 | 10-Sep-2026 | Accept manual-capture sources in the WP3.1 ingestion checks.
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
  `KAKI_DATA_ROOT` and the installed `kaki-rag` package; runs the ingestion
  twice over `rag/corpus/allowlist.yaml`, checking dated snapshots, full
  per-chunk provenance and hash/chunk stability. Manual-capture sources
  read their owner-seeded snapshots and are never fetched; only
  `capture: auto` sources need the network. Needs no model services.
- WP3.2 tier B - vector indexing and hybrid retrieval (WP3-AT-03/04/10).
  Requires `KAKI_DATA_ROOT` with the WP3.1 processed corpus,
  `python -m pip install -e "rag[retrieve,embed]"` and a cached embedding
  model (network once for the first download). Builds the persistent index
  twice, checks idempotency and restart survival, runs the CDC/CHAS
  acceptance queries and the committed multilingual fixture pairs, and
  proves one query from a fresh process via `scripts/query_corpus.py`.
  Needs no Whisper, MLX-LM or FastAPI process.
- WP3.3 tier B - grounded turn with application provenance and the slip
  contract (WP3-AT-06/07). Requires the full stack in the grounded
  configuration (`KAKI_RETRIEVAL_MODE=rag`, runbook 8.1 WP3.3) and
  `KAKI_DATA_ROOT` pointing at the corpus that stack serves. Submits the
  committed spoken CDC-question fixture and verifies the answer's sources
  against the allowlist and stored chunk provenance.
- WP3.4 tier B - refusal and the golden paths (WP3-AT-05/12). Requires the
  same grounded configuration as WP3.3 and the three committed spoken
  fixtures. Submits each one, then checks that supported questions still
  answer with the source they used and that an uncovered question refuses
  without generating, with a referral slip claiming no provenance. GP4
  (credential action) is proven over the text path by
  `scripts/run_regression.py`, so it needs no fixture here.
- WP4.1 tier B - durable turns and replay (WP4-AT-01/02/03). First proves a
  restart replay in-process against a disposable data root under the system
  temporary directory, with canned ports. Then, against the running stack,
  submits one turn, reads the live database read-only to check its `turns`
  and `turn_sources` rows, and replays the same turn_id with different audio.
  Requires `KAKI_DATA_ROOT` (and `KAKI_SQLITE_PATH` if the backend uses it).
  The backend restart itself stays a manual step (runbook 9.2 WP4.1 Test 3).
- WP4.2 tier B - repeat_previous and print_previous (WP4-AT-04/05). Requires
  the grounded stack, `KAKI_DATA_ROOT` and the two WP4.2 spoken fixtures. In
  one fresh session submits an answer, a repeat, a print and a second repeat;
  replays the print's and the first repeat's turn_ids with different audio;
  then repeats in a second fresh session with nothing to act on. Reads the live database read-only and
  asserts its exact schema version.
- WP4.5 tier B - backup readability and devset action accuracy (WP4-AT-13).
  Requires a backup set from `scripts/backup_sqlite.sh` and the grounded
  configuration for `scripts/run_regression.py`. Verifies the newest set's
  manifest hashes, integrity, foreign keys, schema version and turns count
  through an immutable read, then reports the action-item intents as a count
  and a rate, for example `9 of 10, 0.90`.
- WP6.1 tier A - thin-client static inspection (WP6-AT-13) plus the device
  suite. Reads `device/` only: import allowlist, dependency allowlist,
  forbidden model/retrieval/prompt/SQL tokens, request paths and environment
  names. Needs no backend, no hardware and no network.
- WP6.1 tier B - one scripted mock turn against the running stack. Requires
  the grounded stack and KAKI_DEVICE_TOKEN (WP6.4); posts one fixture turn
  through the device loop with mock I/O and checks the loop rendered, spoke
  and printed from the response alone.
- WP6.2 tier A - the hardware layer without hardware: the device suite (GPIO
  and ALSA fakes, debounce, cap/release, countdown), the WP6-AT-13 inspection
  and a direct conversion golden (16 kHz mono in, 48 kHz stereo S16_LE out).
- WP6.2 tier C - service-level checks run ON THE PI from the cloned checkout
  with the device venv: arecord/aplay present, gpiozero importable, the
  configured ALSA card resolvable, the kiosk process running, the backend
  reachable and its newest stored turn from this device. Owner actions are
  never simulated; the physical proofs stay in runbook 11.2 WP6.2.
- WP6.4 tier A - device auth, same-turn_id retry and recovery, deterministically
  (WP6-AT-04/05/10). Runs the WP6.4 backend contract suite (fail-closed
  bearer auth, rejection before any state change, the in-flight duplicate
  turn_id race) and the device suite (token header, retry, retrying frame,
  placeholder copy), re-runs the WP6-AT-13 inspection, pins the WP6.8
  placeholder copy and statically checks infra/pi/kaki-device.service
  (Restart=always, StartLimitIntervalSec=0). No backend, no network.
- WP6.4 tier B - live device auth and the single-answer replay on the running
  stack. Requires KAKI_DEVICE_TOKEN (runbook 11.2 WP6.4). An unauthenticated
  and a wrong-token turn are refused with no state change, an authenticated
  turn answers, and its turn_id replayed with different audio returns the
  identical stored answer with replay_count 1. Tier C (systemd kill and
  power-cycle recovery, WP6-AT-10) is manual owner validation at the Pi and
  is deliberately not scripted here.
- WP6.6 tier A - the admin-surface suites (auth, config, push, override) run
  hermetically from the checkout root, the thin-client inspection stays clean
  and the packaged schema version is 4. No backend, no network.
- WP6.6 tier B - the live admin flow: an unauthenticated request is refused,
  a config change flips a real turn's reply language with no restart, a push
  is delivered exactly once with its pre-synthesised audio, and pending stays
  [] without an identity. Requires the grounded stack and KAKI_ADMIN_TOKEN.
- WP5.1 tier B - Malay voice, Malay retrieval and one Malay text turn
  (WP5-AT-01, 04). Requires the grounded configuration, MLX-LM on 8082 and
  the Chroma index. Checks the configured Malay voice is listed by `say` and
  speaks; measures three Malay CDC questions original-only, with curated
  English queries and with the live Qwen rewrite; then runs one Malay CDC
  transcript through `TurnPipeline` against a disposable database.

Side effects: WP2.3 tier B sends five fixed-transcript generation requests to
the local LLM service. WP2.4 tier B synthesises one fixed sentence locally
and submits one packaged fixture turn (fresh `turn_id`) to the running
backend, which transcribes, generates and synthesises it, writing nothing to
disk. WP3.1 tier B fetches every allowlisted official page over the network
twice and writes snapshots and processed chunks under
`$KAKI_DATA_ROOT/corpus`. WP3.2 tier B embeds the processed corpus twice
and writes the vector collection under `$KAKI_DATA_ROOT/chroma`; one fixed
query also runs `scripts/query_corpus.py` in a subprocess. WP3.4 tier B
submits three packaged fixture turns (fresh `turn_id`s) and writes
nothing. WP4.1 tier B writes a disposable database under the system temporary
directory, removed on exit, and submits one fixture turn plus its replay to the
running backend, which stores them in the live database. WP4.2 tier B submits
six turns plus two replays to the running backend, which stores them in the
live database. WP4.5 tier B writes nothing: it reads the newest backup set
and runs the devset regression, which uses its own disposable database. WP5.1
tier B synthesises one Malay sentence locally, sends three rewrite requests and
one Malay turn's completions to the local LLM, reads the Chroma index and
writes only a disposable database under the system temporary directory. WP6.4
tier B submits one fixture turn (fresh turn_id), its replay and two requests
the backend refuses before any state change; the executed turn is stored in
the live database.
Exit status is zero only when every check passes; 2 indicates a
usage or configuration error.

Every check that shells out to a test suite keeps that suite's whole output.
`--evidence DIR` (or `KAKI_WP_EVIDENCE`) writes one `<suite>.output.txt` per
suite into DIR, and the JSON report carries the last 20 lines of each, so a
failed run names the failing test and its traceback without a rerun.
"""

import argparse
import ast  #v2.7
import tomllib  #v2.7
import hashlib  #v2.3
import io
import json
import os
import re
import shutil  #v3.0
import sqlite3  #v2.0
import stat  #v2.0
import subprocess  #v2.3
import sys
import tempfile  #v2.0
import wave
from pathlib import Path
from base64 import b64decode
from contextlib import closing  #v2.0
from functools import partial  #v2.3
from importlib.resources import files
from time import perf_counter
from uuid import uuid4

import httpx

# The backend is installed on the development machines and the Mac, never on
# the Pi (setup.md 29.6). Tier C runs on the Pi, so these imports are guarded:
# every tier A and B check still fails loudly if run where they are missing,
# because the names it needs are None (#v3.0).
try:
    from dotenv import load_dotenv  #v1.6
    from kaki_backend.config import APPROVED_QWEN_MODEL, LlmSettings, TtsSettings
    from kaki_backend.config import StorageSettings  #v2.0
    from kaki_backend.config import LanguageSettings, RetrievalSettings  #v2.4
    from kaki_backend.contracts.ports import LlmError, TtsError
    from kaki_backend.orchestration.canned_ports import CannedLlmPort, CannedSttPort
except ImportError:  #v3.0
    load_dotenv = None
    APPROVED_QWEN_MODEL = LlmSettings = TtsSettings = StorageSettings = None
    LanguageSettings = RetrievalSettings = LlmError = TtsError = None
    CannedLlmPort = CannedSttPort = None

# The WP3.2/WP3.3 checks embed with a Hugging Face model, whose `HF_TOKEN`
# lives in the untracked project-root .env; a real export wins.
if load_dotenv is not None:
    load_dotenv()  #v1.6

GENERATION_RUNS = 5
MAX_REPLY_WORDS = 60
FIXED_TRANSCRIPT = "What time does the community centre open tomorrow morning?"

# Suite output handling, shared by every unit and both tiers (v2.9). A one-line
# tail loses the failing test's name, assertion and traceback, which is the
# detail the owner needs from an evidence directory that cannot be rerun.
SUITE_TAIL_LINES = 20  #v2.9
# One assertion that prints a base64 data URL is a single 300 kB line, which
# makes the JSON report unreadable. The tail truncates the line; the output
# file keeps it whole.
SUITE_TAIL_LINE_CHARS = 400  #v2.9
EVIDENCE_DIRECTORY: Path | None = None  #v2.9


def _evidence_directory() -> Path | None:  #v2.9
    """Return the directory suite output is written to, or None when unset.

    `--evidence` wins; `KAKI_WP_EVIDENCE` is the fallback, so a harness that
    exports the run's evidence path needs no argument change.
    """
    if EVIDENCE_DIRECTORY is not None:
        return EVIDENCE_DIRECTORY
    configured = os.environ.get("KAKI_WP_EVIDENCE", "").strip()
    return Path(configured) if configured else None


def _tail_lines(text: str) -> list[str]:  #v2.9
    """Return the last SUITE_TAIL_LINES lines, each capped at SUITE_TAIL_LINE_CHARS."""
    lines = text.strip().splitlines()[-SUITE_TAIL_LINES:]
    return [
        line if len(line) <= SUITE_TAIL_LINE_CHARS
        else f"{line[:SUITE_TAIL_LINE_CHARS]}... [{len(line)} chars; see the output file]"
        for line in lines
    ]


def run_suite(name: str, command: list[str], *, cwd: Path | None = None,
              timeout: int = 600) -> tuple[subprocess.CompletedProcess, dict[str, object]]:  #v2.9
    """Run one test suite and keep all of its output.

    Returns the completed process and the record to put in the JSON report:
    exit code, tests run, the last `SUITE_TAIL_LINES` lines of the combined
    output, and the path of the `<name>.output.txt` file written under the
    evidence directory. Stdout and stderr stay separate on the returned
    process, so a caller that parses a JSON stdout still can.

    Side effect: writes one file per suite when an evidence directory is
    configured. A directory that cannot be written is reported in
    `output_error` rather than failing the check, because the suite result
    matters more than its transcript.
    """
    completed = subprocess.run(command, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
    combined = (
        f"$ {' '.join(command)}\n"
        f"exit code: {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout}"
        f"--- stderr ---\n{completed.stderr}"
    )
    ran = re.search(r"^Ran (\d+) tests?", completed.stderr, re.MULTILINE)
    record: dict[str, object] = {
        "exit_code": completed.returncode,
        "tests_ran": int(ran.group(1)) if ran else 0,
        "tail": _tail_lines(combined),
        "output_path": None,
    }
    directory = _evidence_directory()
    if directory is not None:
        destination = directory / f"{name}.output.txt"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            destination.write_text(combined, encoding="utf-8")
            record["output_path"] = str(destination)
        except OSError as error:
            record["output_error"] = f"{destination}: {error}"
    return completed, record


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


def _device_headers() -> dict[str, str]:  #v3.1
    """Return the WP6.4 device bearer header from KAKI_DEVICE_TOKEN, or nothing.

    Every /api/device/* route requires it since WP6.4; /api/health does not,
    and sending it there is harmless. Live tier B checks attach it as their
    client's default headers, so a stack without the token configured still
    fails with a readable 401/403 rather than a crash here.
    """
    token = os.environ.get("KAKI_DEVICE_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}
FIXED_SPEECH_SENTENCE = "KaKi-Talkie text to speech is working."
POSITIVE_STAGES = ("audio_preparation_ms", "stt_ms", "routing_ms", "llm_ms", "tts_ms",
                   "overall_ms")


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

    # A grounded stack refuses the canned fixture's transcript by design, so
    # this check speaks a supported question there instead (runbook 8.1 WP3.4).
    grounded = os.environ.get("KAKI_RETRIEVAL_MODE", "canned") == "rag"  #v1.8
    fixture_name = GROUNDED_TURN_FIXTURE if grounded else UNGROUNDED_TURN_FIXTURE  #v1.8
    report["turn_fixture"] = fixture_name  #v1.8
    fixture = files("kaki_backend").joinpath(f"fixtures/{fixture_name}").read_bytes()
    turn_id = f"wp24-check-{uuid4().hex[:12]}"
    canned_reply = CannedLlmPort().generate("")
    canned_transcript = CannedSttPort().transcribe(b"x").text
    try:
        with httpx.Client(timeout=180, trust_env=False, follow_redirects=False,
                          headers=_device_headers()) as client:  #v3.1
            health = client.get(BACKEND_URL + "/api/health").json()
            turn_started = perf_counter()
            turn = client.post(
                BACKEND_URL + "/api/device/turn",
                data={"device_id": "wp24-check", "session_id": "wp24-check",
                      "turn_id": turn_id},
                files={"audio": (fixture_name, fixture, "audio/wav")},  #v1.8
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
    # Retrieval use is scoped by configuration (WP3.3): unused in the WP2
    # configuration, used on every answer turn in the grounded one.
    retrieval_mode = os.environ.get("KAKI_RETRIEVAL_MODE", "canned")  #v1.5
    report["retrieval_mode"] = retrieval_mode  #v1.5
    if grounded:  #v1.5
        checks["retrieval_used_when_grounded"] = (
            isinstance(timings.get("retrieval_ms"), (int, float))
            and timings["retrieval_ms"] > 0
        )
    else:  #v1.5
        checks["retrieval_stays_unused"] = timings.get("retrieval_ms") is None
    checks["live_lookup_stays_unused"] = timings.get("live_lookup_ms") is None  #v1.5
    return report, checks


ALLOWLIST_PATH = Path(__file__).resolve().parents[1] / "rag/corpus/allowlist.yaml"
DATED_SNAPSHOT_DIRECTORY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_processed_chunks(processed_path: str) -> list[dict[str, object]]:
    """Read the processed chunk records an ingestion report points at."""
    lines = Path(processed_path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def check_wp31_tier_b() -> tuple[dict[str, object], dict[str, bool]]:
    """Prove WP3-AT-01/02 with two ingestion runs over the committed allowlist.

    Requires an absolute `KAKI_DATA_ROOT`, seeded snapshots for every
    manual source, `python -m pip install -e rag`, and network access only
    for `capture: auto` sources (runbook 8.1 WP3.1).
    """  #v1.3
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
        "allowlist_has_four_or_more_sources": len(first.results) >= 4,  #v1.3
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
            result.status in ("unchanged", "manual") for result in second.results  #v1.3
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


CDC_QUERY = "How do I use my CDC vouchers?"
CHAS_QUERY = "CHAS"
MULTILINGUAL_FIXTURES = (
    Path(__file__).resolve().parents[1] / "rag/tests/fixtures/multilingual_queries.jsonl"
)
QUERY_CLI = Path(__file__).resolve().parent / "query_corpus.py"
RETRIEVAL_TOP_K = 3
FRESH_PROCESS_TIMEOUT_SECONDS = 300


def check_wp32_tier_b() -> tuple[dict[str, object], dict[str, bool]]:
    """Prove WP3-AT-03/04/10 over the persistent index (runbook 8.2 WP3.2).

    Requires an absolute `KAKI_DATA_ROOT` holding the WP3.1 processed
    corpus and the `kaki-rag` retrieve/embed extras installed.
    """  #v1.4
    import subprocess

    try:
        from kaki_rag.retrieve.chunks import PROCESSED_RELATIVE_PATH, CorpusError, load_chunks
        from kaki_rag.retrieve.embedding import SentenceTransformerEmbedder
        from kaki_rag.retrieve.hybrid import ALL_PATHS, HybridRetriever, RetrievalQuery
        from kaki_rag.retrieve.index import build_index
        from kaki_rag.retrieve.vector_store import ChromaVectorStore
    except ImportError as error:
        raise ValueError(
            f'install the retrieval extras first: python -m pip install -e '
            f'"rag[retrieve,embed]" ({error})'
        ) from None

    data_root = Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if not data_root.is_absolute():
        raise ValueError("export an absolute KAKI_DATA_ROOT first (runbook 8.1 WP3.2).")
    processed_path = data_root / PROCESSED_RELATIVE_PATH

    try:
        embedder = SentenceTransformerEmbedder()
        store = ChromaVectorStore.persistent(data_root)
        first = build_index(processed_path, embedder, store)
        second = build_index(processed_path, embedder, store)
        chunks = load_chunks(processed_path)
    except (CorpusError, OSError) as error:
        raise ValueError(str(error)) from None
    reopened = ChromaVectorStore.persistent(data_root)
    retriever = HybridRetriever(chunks, embedder, reopened)

    report: dict[str, object] = {
        "data_root": str(data_root),
        "model": embedder.model_id,
        "first_build": first.as_dict(),
        "second_build": second.as_dict(),
        "reopened_collection_count": reopened.count(),
    }
    checks = {
        "first_build_succeeded": first.succeeded,
        "rebuild_is_idempotent": (
            second.succeeded
            and second.removed_stale == 0
            and second.collection_count == first.collection_count
        ),
        "reopened_collection_matches_corpus": reopened.count() == len(chunks),
    }

    cdc_results = retriever.retrieve(RetrievalQuery(original=CDC_QUERY), RETRIEVAL_TOP_K)
    chas_results = retriever.retrieve(RetrievalQuery(original=CHAS_QUERY), RETRIEVAL_TOP_K)
    report["cdc_query"] = {
        "query": CDC_QUERY,
        "top_sources": [result.chunk.source_id for result in cdc_results],
    }
    report["chas_query"] = {
        "query": CHAS_QUERY,
        "top_sources": [result.chunk.source_id for result in chas_results],
        "path_ranks": [result.path_ranks for result in chas_results],
    }
    checks["cdc_query_returns_cdc_evidence_in_top_three"] = any(
        result.chunk.source_id == "cdc-vouchers-residents" for result in cdc_results
    )
    checks["chas_exact_term_ranked_by_lexical_path"] = any(
        result.chunk.source_id == "chas-about" and "lexical_original" in result.path_ranks
        for result in chas_results
    )
    checks["every_result_carries_provenance"] = all(
        all(result.chunk.provenance.get(field) for field in
            ("source_url", "page_title", "captured_at"))
        for result in (*cdc_results, *chas_results)
    )

    pairs = [
        json.loads(line)
        for line in MULTILINGUAL_FIXTURES.read_text(encoding="utf-8").splitlines()
    ]
    exercised_paths: set[str] = set()
    fixture_outcomes: list[dict[str, object]] = []
    for pair in pairs:
        results = retriever.retrieve(
            RetrievalQuery(original=pair["original"], normalised=pair["normalised"]),
            RETRIEVAL_TOP_K,
        )
        top_sources = [result.chunk.source_id for result in results]
        for result in results:
            exercised_paths.update(result.path_ranks)
        fixture_outcomes.append({
            "label": pair["label"], "expected": pair["expected_source_id"],
            "top_sources": top_sources,
            "hit": pair["expected_source_id"] in top_sources,
        })
    report["multilingual_pairs"] = fixture_outcomes
    report["exercised_paths"] = sorted(exercised_paths)
    checks["multilingual_pairs_hit_expected_sources"] = bool(fixture_outcomes) and all(
        outcome["hit"] for outcome in fixture_outcomes
    )
    checks["original_and_normalised_paths_all_exercised"] = exercised_paths >= set(ALL_PATHS)

    fresh = subprocess.run(
        [sys.executable, str(QUERY_CLI), "--query", CDC_QUERY,
         "--top-k", str(RETRIEVAL_TOP_K)],
        capture_output=True, text=True, timeout=FRESH_PROCESS_TIMEOUT_SECONDS,
    )
    try:
        fresh_sources = [
            result["source_id"] for result in json.loads(fresh.stdout)["results"]
        ]
    except (ValueError, KeyError, TypeError):
        fresh_sources = []
    report["fresh_process_query"] = {
        "exit_status": fresh.returncode, "top_sources": fresh_sources,
    }
    checks["fresh_process_query_survives_restart"] = (
        fresh.returncode == 0 and "cdc-vouchers-residents" in fresh_sources
    )
    return report, checks


CDC_QUESTION_SENTENCE = "How do I use my CDC vouchers?"  #v1.5
CDC_SOURCE_ID = "cdc-vouchers-residents"  #v1.5
MAX_SLIP_WORDS = 40  #v1.5
GROUNDED_TURN_TIMEOUT_SECONDS = 300  #v1.5
# In the grounded configuration the WP1 canned fixture is correctly refused
# (its transcript scores 0.278 best dense, below the 0.50 gate), so the WP2.4
# full-loop check must speak a supported question instead (runbook 8.1 WP3.4).
GROUNDED_TURN_FIXTURE = "cdc_question.wav"  #v1.8
UNGROUNDED_TURN_FIXTURE = "canned_reply.wav"  #v1.8


def check_wp33_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v1.5
    """Prove WP3-AT-06/07 through one grounded turn over the running stack.

    Requires the full stack in the grounded configuration
    (`KAKI_RETRIEVAL_MODE=rag`, runbook 8.1 WP3.3) and `KAKI_DATA_ROOT`
    pointing at the corpus that stack serves, so the response provenance can
    be verified against the stored chunk metadata byte-for-byte.
    """
    from datetime import datetime

    from urllib.parse import urlsplit

    from kaki_rag.ingest.fetch import load_allowlist

    if os.environ.get("KAKI_RETRIEVAL_MODE", "canned") != "rag":
        raise ValueError("export KAKI_RETRIEVAL_MODE=rag before running WP3.3 tier B.")
    data_root = Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if not data_root.is_absolute():
        raise ValueError("export an absolute KAKI_DATA_ROOT first (runbook 8.1 WP3.3).")

    allowlist = load_allowlist(ALLOWLIST_PATH)
    cdc_url = next(
        (source.url for source in allowlist.sources if source.source_id == CDC_SOURCE_ID),
        None,
    )
    chunks = _load_processed_chunks(str(data_root / "corpus/processed/chunks.jsonl"))
    captured_by_url: dict[str, set[str]] = {}
    for record in chunks:
        provenance = record.get("provenance") or {}
        captured_by_url.setdefault(str(provenance.get("source_url")), set()).add(
            str(provenance.get("captured_at"))
        )

    try:
        fixture = files("kaki_backend").joinpath("fixtures/cdc_question.wav").read_bytes()
    except (FileNotFoundError, OSError):
        raise ValueError(
            "the committed spoken fixture backend/src/kaki_backend/fixtures/"
            "cdc_question.wav is missing; generate and commit it once "
            "(runbook 8.1 WP3.3)."
        ) from None
    turn_id = f"wp33-check-{uuid4().hex[:12]}"
    canned_reply = CannedLlmPort().generate("")
    report: dict[str, object] = {
        "backend_url": BACKEND_URL,
        "question_sentence": CDC_QUESTION_SENTENCE,
        "turn_id": turn_id,
    }
    try:
        with httpx.Client(
            timeout=GROUNDED_TURN_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False,
            headers=_device_headers(),  #v3.1
        ) as client:
            health = client.get(BACKEND_URL + "/api/health").json()
            turn = client.post(
                BACKEND_URL + "/api/device/turn",
                data={"device_id": "wp33-check", "session_id": "wp33-check",
                      "turn_id": turn_id},
                files={"audio": ("cdc_question.wav", fixture, "audio/wav")},
            ).json()
            debug = client.get(BACKEND_URL + "/api/device/debug/last-turn").json()
    except (httpx.HTTPError, ValueError):
        print("FAIL: the grounded stack is not reachable; start it first (runbook 8.1 "
              "WP3.3).", file=sys.stderr)
        return report, {"stack_reachable": False}

    report["health"] = health
    sources = turn.get("sources") or []
    slip_text = str(turn.get("slip_text") or "")
    timings = debug.get("timings_ms") or {}
    report["turn"] = {
        "state": turn.get("state"), "reply_text": turn.get("reply_text"),
        "display_text": turn.get("display_text"), "slip_text": slip_text,
        "sources": sources,
    }
    report["debug"] = {
        "transcript": debug.get("transcript"),
        "normalised_query": debug.get("normalised_query"),
        "retrieval_evidence": debug.get("retrieval_evidence"),
        "timings_ms": timings,
    }

    checks = {
        "stack_reachable": True,
        "health_reports_all_ready": health.get("status") == "ok" and all(
            health.get(flag) is True
            for flag in ("stt_ready", "llm_ready", "tts_ready", "retrieval_ready")
        ),
        "turn_answered": turn.get("state") == "answered",
        "reply_is_generated_not_canned": bool(
            str(turn.get("reply_text") or "").strip()
        ) and turn.get("reply_text") != canned_reply,
        "display_text_non_empty": bool(str(turn.get("display_text") or "").strip()),
        "transcript_is_real": bool(debug.get("transcript")),
        "retrieval_timed": isinstance(timings.get("retrieval_ms"), (int, float))
        and timings["retrieval_ms"] > 0,
        "sources_non_empty": bool(sources),
        "cdc_source_cited": cdc_url is not None and any(
            record.get("source_url") == cdc_url for record in sources
        ),
        "every_source_allowlisted": bool(sources) and all(
            urlsplit(str(record.get("source_url"))).hostname in allowlist.allowed_domains
            for record in sources
        ),
        "source_dates_application_derived": bool(sources) and all(
            any(
                datetime.fromisoformat(str(record.get("captured_at")))
                == datetime.fromisoformat(stored)
                for stored in captured_by_url.get(str(record.get("source_url")), ())
            )
            for record in sources
        ),
        "evidence_scores_logged": bool(debug.get("retrieval_evidence")) and all(
            isinstance(entry.get("fused_score"), (int, float))
            and (entry.get("dense_score") is not None
                 or entry.get("lexical_score") is not None)
            for entry in debug.get("retrieval_evidence") or []
        ),
    }

    # The answer must be attributed to the evidence it actually used, and the
    # response must lead with that source so the slip cannot disagree.
    url_by_source_id = {source.source_id: source.url for source in allowlist.sources}  #v1.7
    cited_source_id = debug.get("cited_source_id")  #v1.7
    evidence_log = debug.get("retrieval_evidence") or []  #v1.7
    checks["answer_attributed_to_one_evidence_source"] = cited_source_id is not None
    checks["response_leads_with_the_cited_source"] = (
        bool(sources) and cited_source_id is not None
        and sources[0].get("source_url") == url_by_source_id.get(cited_source_id)
    )
    checks["evidence_log_keeps_retrieval_rank_order"] = (
        [entry.get("retrieval_rank") for entry in evidence_log]
        == list(range(1, len(evidence_log) + 1))
    )

    slip_words = slip_text.split()
    primary = sources[0] if sources else {}
    primary_domain = urlsplit(str(primary.get("source_url") or "")).hostname or ""
    checked_date = ""
    if primary.get("captured_at"):
        checked_date = datetime.fromisoformat(
            str(primary["captured_at"])
        ).strftime("%d-%b-%Y")
    checks["slip_within_40_words"] = 0 < len(slip_words) <= MAX_SLIP_WORDS
    checks["slip_names_source_domain_not_url"] = (
        bool(primary_domain) and primary_domain in slip_text and "http" not in slip_text
    )
    checks["slip_shows_source_checked_date"] = (
        bool(checked_date) and f"Source checked: {checked_date}" in slip_text
    )
    checks["slip_has_ask_again_line"] = "Ask KaKi-Talkie again" in slip_text
    return report, checks


# GP4 has no fixture: the credential-action refusal is proven over the text
# path by the devset item in `scripts/run_regression.py` (runbook 8.2 WP3.4
# Test 2), which needs no audio.
WP34_FIXTURES = {  #v1.9
    "cdc_question.wav": "GP1",
    "singpass_question.wav": "GP2",
    "unsupported_question.wav": "GP3",
}


def _submit_turn(client: httpx.Client, fixture_name: str) -> tuple[dict, dict]:  #v1.8
    """Submit one packaged spoken fixture and return its response and diagnostics."""
    audio = files("kaki_backend").joinpath(f"fixtures/{fixture_name}").read_bytes()
    turn_id = f"wp34-check-{uuid4().hex[:12]}"
    turn = client.post(
        BACKEND_URL + "/api/device/turn",
        data={"device_id": "wp34-check", "session_id": "wp34-check", "turn_id": turn_id},
        files={"audio": (fixture_name, audio, "audio/wav")},
    ).json()
    debug = client.get(BACKEND_URL + "/api/device/debug/last-turn").json()
    return turn, debug


def check_wp34_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v1.8
    """Prove WP3-AT-05/12 over the running grounded stack.

    Submits the three committed spoken fixtures (runbook 8.1 WP3.4) and checks
    GP1-GP3: supported questions still answer with the source they used, and
    an uncovered question refuses without generating, with a referral slip
    that claims no provenance. GP4 (credential action, WP3-AT-08) is proven
    over the text path by the devset runner. Requires the grounded
    configuration and `KAKI_DATA_ROOT`.
    """  #v1.9
    if os.environ.get("KAKI_RETRIEVAL_MODE", "canned") != "rag":
        raise ValueError("export KAKI_RETRIEVAL_MODE=rag before running WP3.4 tier B.")
    data_root = Path(os.environ.get("KAKI_DATA_ROOT", ""))
    if not data_root.is_absolute():
        raise ValueError("export an absolute KAKI_DATA_ROOT first (runbook 8.1 WP3.4).")

    missing = [
        name for name in WP34_FIXTURES
        if not files("kaki_backend").joinpath(f"fixtures/{name}").is_file()
    ]
    if missing:
        raise ValueError(
            "the committed spoken fixtures "
            + ", ".join(f"backend/src/kaki_backend/fixtures/{name}" for name in missing)
            + " are missing; capture them once with `say` (runbook 8.1 WP3.4)."
        )

    report: dict[str, object] = {"backend_url": BACKEND_URL, "turns": {}}
    try:
        with httpx.Client(
            timeout=GROUNDED_TURN_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False,
            headers=_device_headers(),  #v3.1
        ) as client:
            health = client.get(BACKEND_URL + "/api/health").json()
            turns = {
                name: _submit_turn(client, name) for name in WP34_FIXTURES
            }
    except (httpx.HTTPError, ValueError):
        print("FAIL: the grounded stack is not reachable; start it first (runbook 8.1 "
              "WP3.4).", file=sys.stderr)
        return report, {"stack_reachable": False}

    report["health"] = health
    for name, (turn, debug) in turns.items():
        report["turns"][name] = {  # type: ignore[index]
            "golden_path": WP34_FIXTURES[name],
            "state": turn.get("state"),
            "reply_text": turn.get("reply_text"),
            "display_text": turn.get("display_text"),
            "slip_text": turn.get("slip_text"),
            "sources": turn.get("sources"),
            "intent": debug.get("intent"),
            "refusal_reason": debug.get("refusal_reason"),
            "transcript": debug.get("transcript"),
            "best_dense_score": debug.get("best_dense_score"),
            "evidence_min_dense": debug.get("evidence_min_dense"),
            "timings_ms": debug.get("timings_ms"),
        }

    cdc_turn, _ = turns["cdc_question.wav"]
    singpass_turn, singpass_debug = turns["singpass_question.wav"]
    refused_turn, refused_debug = turns["unsupported_question.wav"]

    checks = {
        "stack_reachable": True,
        "health_reports_all_ready": health.get("status") == "ok" and all(
            health.get(flag) is True
            for flag in ("stt_ready", "llm_ready", "tts_ready", "retrieval_ready")
        ),
        # GP1 and GP2: supported questions still answer, with their own source.
        "gp1_cdc_answered": cdc_turn.get("state") == "answered",
        "gp2_singpass_answered": singpass_turn.get("state") == "answered",
        "gp2_cites_the_singpass_source": (
            singpass_debug.get("cited_source_id") == "singpass-support"
        ),
        "gp2_is_not_mistaken_for_a_credential_action": (
            singpass_debug.get("intent") == "answer"
        ),
        # GP3 and GP5: no coverage refuses instead of improvising.
        "gp3_unsupported_refused": refused_turn.get("state") == "refused",
        "gp3_reason_is_no_coverage": refused_debug.get("refusal_reason") == "no_coverage",
        "gp3_scored_below_the_gate": (
            isinstance(refused_debug.get("best_dense_score"), (int, float))
            and isinstance(refused_debug.get("evidence_min_dense"), (int, float))
            and refused_debug["best_dense_score"] < refused_debug["evidence_min_dense"]
        ),
        "gp3_did_not_generate": (refused_debug.get("timings_ms") or {}).get("llm_ms") is None,
        "gp3_has_no_sources": not refused_turn.get("sources"),
    }

    # The refused turn speaks fixed wording and prints a slip claiming no source.
    slip = str(refused_turn.get("slip_text") or "")  #v1.9
    report["gp3_slip_text"] = slip
    checks["gp3_refusal_is_spoken_and_displayed"] = bool(
        str(refused_turn.get("reply_text") or "").strip()
    ) and bool(str(refused_turn.get("display_text") or "").strip())
    checks["gp3_refusal_has_audio"] = refused_turn.get("reply_audio") is not None
    checks["gp3_referral_slip_within_40_words"] = 0 < len(slip.split()) <= MAX_SLIP_WORDS
    checks["gp3_referral_slip_claims_no_provenance"] = (
        "Source checked" not in slip and "Source:" not in slip and "http" not in slip
    )
    return report, checks


def _restart_replay_in_process() -> tuple[dict[str, object], dict[str, bool]]:  #v2.0
    """Store a canned turn, reopen the database with a fresh service and replay it.

    Uses a disposable data root so the live database is untouched. The replay
    sends empty audio: re-execution would return a failed turn instead.
    """
    import asyncio

    from kaki_backend.orchestration.idempotency import TurnService
    from kaki_backend.orchestration.turn_pipeline import TurnPipeline
    from kaki_backend.persistence.database import Database
    from kaki_backend.persistence.repositories import TurnRepository

    fixture = files("kaki_backend").joinpath(f"fixtures/{UNGROUNDED_TURN_FIXTURE}").read_bytes()
    fields = dict(device_id="wp41-check", session_id="wp41-check", turn_id="wp41-restart",
                  audio_preparation_ms=0.0)
    with tempfile.TemporaryDirectory(prefix="kaki-wp41-check-") as scratch:
        settings = StorageSettings.from_environment({"KAKI_DATA_ROOT": scratch})
        first_database = Database.open(settings.path)
        first_pipeline = TurnPipeline()
        first = asyncio.run(TurnService(first_pipeline, TurnRepository(first_database)).process(
            audio=fixture, request_started_at=perf_counter(), **fields,
        ))
        restarted_pipeline = TurnPipeline()
        restarted_database = Database.open(settings.path)
        replay = asyncio.run(
            TurnService(restarted_pipeline, TurnRepository(restarted_database)).process(
                audio=b"", request_started_at=perf_counter(), **fields,
            )
        )
        stored = TurnRepository(restarted_database).find("wp41-restart")
        file_mode = stat.S_IMODE(os.stat(settings.path).st_mode)
        schema_version = restarted_database.schema_version()
    report = {"schema_version": schema_version, "file_mode": oct(file_mode),
              "first_state": first.state.value, "replay_state": replay.state.value}
    checks = {
        "disposable_database_is_owner_only": file_mode == 0o600,
        # At least: later migrations raise it; WP4.2 asserts the exact value.
        "disposable_database_at_least_schema_version_1": schema_version >= 1,  #v2.1
        "first_execution_ran_once": first_pipeline.execution_count == 1,
        "restart_replay_did_not_execute": restarted_pipeline.execution_count == 0,
        "restart_replay_identical": replay.model_dump() == first.model_dump(),
        "restart_replay_counted": stored is not None and stored.replay_count == 1,
    }
    return report, checks


def check_wp41_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v2.0
    """Prove WP4-AT-01/02/03 in-process and against the running stack.

    The in-process part needs no services. The stack part needs the backend
    running with the same `KAKI_DATA_ROOT`/`KAKI_SQLITE_PATH` as this shell,
    because it reads that database read-only to inspect the stored rows.
    """
    live_path = StorageSettings.from_environment().path
    grounded = os.environ.get("KAKI_RETRIEVAL_MODE", "canned") == "rag"
    fixture_name = GROUNDED_TURN_FIXTURE if grounded else UNGROUNDED_TURN_FIXTURE
    replay_fixture = "unsupported_question.wav" if grounded else "empty_audio.wav"
    report: dict[str, object] = {
        "backend_url": BACKEND_URL, "database": live_path, "turn_fixture": fixture_name,
        "replay_fixture": replay_fixture,
    }
    in_process_report, checks = _restart_replay_in_process()
    report["in_process"] = in_process_report

    turn_id = f"wp41-check-{uuid4().hex[:12]}"
    fields = {"device_id": "wp41-check", "session_id": "wp41-check", "turn_id": turn_id}
    audio = files("kaki_backend").joinpath(f"fixtures/{fixture_name}").read_bytes()
    replay_audio = files("kaki_backend").joinpath(f"fixtures/{replay_fixture}").read_bytes()
    try:
        with httpx.Client(
            timeout=GROUNDED_TURN_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False,
            headers=_device_headers(),  #v3.1
        ) as client:
            health = client.get(BACKEND_URL + "/api/health").json()
            started = perf_counter()
            first = client.post(BACKEND_URL + "/api/device/turn", data=fields,
                                files={"audio": (fixture_name, audio, "audio/wav")}).json()
            first_ms = (perf_counter() - started) * 1000
            started = perf_counter()
            replay = client.post(BACKEND_URL + "/api/device/turn", data=fields,
                                 files={"audio": (replay_fixture, replay_audio,
                                                  "audio/wav")}).json()
            replay_ms = (perf_counter() - started) * 1000
            debug = client.get(BACKEND_URL + "/api/device/debug/last-turn").json()
    except (httpx.HTTPError, ValueError):
        print("FAIL: the backend stack is not reachable; start it first (runbook 9.2 WP4.1).",
              file=sys.stderr)
        checks["stack_reachable"] = False
        return report, checks
    checks["stack_reachable"] = True

    try:
        with closing(sqlite3.connect(f"file:{live_path}?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            turn_row = connection.execute(
                "SELECT state, replay_count FROM turns WHERE turn_id = ?", (turn_id,)
            ).fetchone()
            source_rows = connection.execute(
                "SELECT source_url, cited FROM turn_sources WHERE turn_id = ? ORDER BY position",
                (turn_id,),
            ).fetchall()
    except sqlite3.Error as error:
        raise ValueError(f"cannot read {live_path} read-only: {error}") from None
    sources = first.get("sources") or []
    report.update({
        "health": health, "turn_id": turn_id, "first_state": first.get("state"),
        "first_elapsed_ms": round(first_ms, 1), "replay_elapsed_ms": round(replay_ms, 1),
        "stored_row": dict(turn_row) if turn_row is not None else None,
        "stored_source_rows": [dict(row) for row in source_rows],
        "debug_replay_count": debug.get("replay_count"),
    })
    checks.update({
        "health_reports_storage_ready": health.get("storage_ready") is True,
        "live_turn_stored": turn_row is not None and turn_row["state"] == first.get("state"),
        "one_source_row_per_response_source": [row["source_url"] for row in source_rows]
        == [source.get("source_url") for source in sources],
        "cited_source_stored_first": not sources or (
            bool(source_rows) and source_rows[0]["cited"] == 1
        ),
        "replay_identical_despite_different_audio": replay == first,
        "replay_counted_once": turn_row is not None and turn_row["replay_count"] == 1,
        "replay_faster_than_execution": replay_ms < first_ms,
        "debug_view_reads_the_stored_turn": debug.get("turn_id") == turn_id
        and debug.get("replay_count") == 1,
    })
    if grounded:
        checks["grounded_turn_answered_with_sources"] = (
            first.get("state") == "answered" and bool(sources)
        )
    return report, checks


WP42_SCHEMA_VERSION = 2  #v2.1
MIGRATION_FILE_GLOB = "[0-9][0-9][0-9][0-9]_*.sql"  #v2.5


def packaged_schema_version() -> int:  #v2.5
    """Count the packaged migration files: the schema version this checkout migrates to.

    Migrations are numbered contiguously from 0001, so the file count is the
    version, the same derivation as `scripts/wp4_5_evidence.sh`. It raises
    the expectation only when a migration file ships.
    """
    from kaki_backend.persistence import migrations as migrations_package

    return len(list(Path(migrations_package.__file__).parent.glob(MIGRATION_FILE_GLOB)))


WP42_FIXTURES = ("repeat_request.wav", "print_request.wav")  #v2.1


def _wp42_post(client: httpx.Client, session_id: str, fixture_name: str,
               turn_id: str | None = None) -> tuple[dict, dict, str, float]:  #v2.1
    """Submit one packaged fixture; return response, debug view, turn_id and elapsed ms."""
    turn_id = turn_id or f"wp42-check-{uuid4().hex}"
    audio = files("kaki_backend").joinpath(f"fixtures/{fixture_name}").read_bytes()
    started = perf_counter()
    turn = client.post(
        BACKEND_URL + "/api/device/turn",
        data={"device_id": "wp42-check", "session_id": session_id, "turn_id": turn_id},
        files={"audio": (fixture_name, audio, "audio/wav")},
    ).json()
    elapsed_ms = (perf_counter() - started) * 1000
    debug = client.get(BACKEND_URL + "/api/device/debug/last-turn").json()
    return turn, debug, turn_id, elapsed_ms


def _stage_nulls(debug: dict, *stages: str) -> bool:  #v2.1
    timings = debug.get("timings_ms") or {}
    return all(timings.get(stage) is None for stage in stages)


def check_wp42_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v2.1
    """Prove WP4-AT-04/05 against the running grounded stack (runbook 9.2 WP4.2).

    The print policy (WP4-AT-06) is a client rule (design.md 9.3) proven by
    the web suite and the owner's browser test, so it is not checked here.
    """
    if os.environ.get("KAKI_RETRIEVAL_MODE", "canned") != "rag":
        raise ValueError("export KAKI_RETRIEVAL_MODE=rag before running WP4.2 tier B.")
    live_path = StorageSettings.from_environment().path
    missing = [name for name in (GROUNDED_TURN_FIXTURE, *WP42_FIXTURES)
               if not files("kaki_backend").joinpath(f"fixtures/{name}").is_file()]
    if missing:
        raise ValueError(
            "missing spoken fixtures " + ", ".join(missing)
            + "; capture them once with scripts/wp4_2_evidence.sh --capture-fixtures "
            "(runbook 9.1 WP4.2)."
        )

    session = f"wp42-check-{uuid4().hex}"
    lonely_session = f"wp42-check-empty-{uuid4().hex}"
    report: dict[str, object] = {"backend_url": BACKEND_URL, "database": live_path,
                                 "session_id": session}
    try:
        with httpx.Client(
            timeout=GROUNDED_TURN_TIMEOUT_SECONDS, trust_env=False, follow_redirects=False,
            headers=_device_headers(),  #v3.1
        ) as client:
            health = client.get(BACKEND_URL + "/api/health").json()
            answer, answer_debug, answer_id, answer_ms = _wp42_post(
                client, session, GROUNDED_TURN_FIXTURE)
            repeat, repeat_debug, repeat_id, repeat_ms = _wp42_post(
                client, session, "repeat_request.wav")
            printed, print_debug, print_id, print_ms = _wp42_post(
                client, session, "print_request.wav")
            second, second_debug, second_id, _ = _wp42_post(
                client, session, "repeat_request.wav")
            # Different audio under each turn_id: re-execution would swap the action.
            replay, _, _, replay_ms = _wp42_post(
                client, session, "repeat_request.wav", turn_id=print_id)
            repeat_replay, replays_debug, _, repeat_replay_ms = _wp42_post(  #v2.2
                client, session, "print_request.wav", turn_id=repeat_id)
            lonely, lonely_debug, lonely_id, _ = _wp42_post(
                client, lonely_session, "repeat_request.wav")
    except (httpx.HTTPError, ValueError):
        print("FAIL: the grounded stack is not reachable; start it first (runbook 9.2 WP4.2).",
              file=sys.stderr)
        return report, {"stack_reachable": False}

    try:
        with closing(sqlite3.connect(f"file:{live_path}?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
            rows = {
                row["turn_id"]: dict(row) for row in connection.execute(
                    "SELECT turn_id, state, intent, previous_turn_id, action_outcome, "
                    "replay_count, slip_text FROM turns WHERE session_id IN (?, ?)",
                    (session, lonely_session),
                )
            }
            source_rows = {
                turn_id: [tuple(row) for row in connection.execute(
                    "SELECT position, source_id, source_url, chunk_id, cited "
                    "FROM turn_sources WHERE turn_id = ? ORDER BY position", (turn_id,))]
                for turn_id in (answer_id, repeat_id, print_id)
            }
    except sqlite3.Error as error:
        raise ValueError(f"cannot read {live_path} read-only: {error}") from None

    report.update({
        "health": health, "schema_version": schema_version,
        "packaged_schema_version": packaged_schema_version(),  #v2.5
        "turn_ids": {"answer": answer_id, "repeat": repeat_id, "print": print_id,
                     "second_repeat": second_id, "nothing_to_act_on": lonely_id},
        "elapsed_ms": {"answer": round(answer_ms, 1), "repeat": round(repeat_ms, 1),
                       "print": round(print_ms, 1), "print_replay": round(replay_ms, 1),
                       "repeat_replay": round(repeat_replay_ms, 1)},  #v2.2
        "transcripts": {"repeat": repeat_debug.get("transcript"),
                        "print": print_debug.get("transcript")},
        "stored_rows": rows,
    })
    answer_row = rows.get(answer_id) or {}
    checks = {
        "stack_reachable": True,
        "health_reports_storage_ready": health.get("storage_ready") is True,
        # The live backend migrates to the packaged version; WP4.2's 0002 is within it.  #v2.5
        "live_database_at_packaged_schema_version": schema_version == packaged_schema_version()
        and schema_version >= WP42_SCHEMA_VERSION,
        "answer_answered_with_sources": answer.get("state") == "answered"
        and bool(answer.get("sources")),
        "answer_has_null_action_fields": answer_debug.get("previous_turn_id") is None
        and answer_debug.get("action_outcome") is None,
        # WP4-AT-04
        "repeat_routed": repeat_debug.get("intent") == "repeat_previous",
        "repeat_acted": repeat.get("state") == "acted",
        "repeat_text_audio_sources_unchanged": all(
            repeat.get(field) == answer.get(field)
            for field in ("reply_text", "display_text", "reply_audio", "language", "sources")
        ),
        "repeat_slip_empty": repeat.get("slip_text") == "",
        "repeat_resolved_to_answer": repeat_debug.get("previous_turn_id") == answer_id
        and repeat_debug.get("action_outcome") == "resolved",
        "repeat_no_retrieval_llm_or_tts": _stage_nulls(
            repeat_debug, "retrieval_ms", "llm_ms", "tts_ms", "query_rewrite_ms"),
        "repeat_stt_ran": ((repeat_debug.get("timings_ms") or {}).get("stt_ms") or 0) > 0,
        # WP4-AT-05
        "print_routed": print_debug.get("intent") == "print_previous",
        "print_acted": printed.get("state") == "acted",
        "print_slip_equals_stored_answer_slip": bool(answer_row)
        and printed.get("slip_text") == answer_row.get("slip_text")
        and printed.get("slip_text") == answer.get("slip_text"),
        "print_resolved_to_answer_not_repeat": print_debug.get("previous_turn_id") == answer_id,
        "print_no_retrieval_or_llm": _stage_nulls(print_debug, "retrieval_ms", "llm_ms"),
        "second_repeat_resolves_to_answer": second_debug.get("previous_turn_id") == answer_id
        and second.get("reply_text") == answer.get("reply_text"),
        "action_rows_copy_answer_sources": bool(source_rows[answer_id])
        and source_rows[repeat_id] == source_rows[answer_id]
        and source_rows[print_id] == source_rows[answer_id],
        "action_rows_store_previous_turn": (rows.get(repeat_id) or {}).get("previous_turn_id")
        == answer_id and (rows.get(print_id) or {}).get("previous_turn_id") == answer_id,
        # Idempotency of an action turn_id.
        "print_replay_identical": replay == printed,
        "print_replay_counted_in_store": (rows.get(print_id) or {}).get("replay_count") == 1,
        "repeat_replay_identical": repeat_replay == repeat,  #v2.2
        "repeat_replay_counted_in_store": (rows.get(repeat_id) or {}).get("replay_count") == 1,
        # The debug view shows the newest *executed* turn (runbook 9.1 WP4.1
        # "Debug view additions"). A replay writes no row, so after replaying
        # two older turns it still shows the second repeat, uncounted.
        "debug_view_stays_on_newest_executed_turn_after_replays": (  #v2.2
            replays_debug.get("turn_id") == second_id
            and replays_debug.get("replay_count") == 0
        ),
        # Nothing to act on, in a session with no stored turn.
        "nothing_to_act_on_acted_without_slip": lonely.get("state") == "acted"
        and lonely.get("slip_text") == "" and lonely.get("sources") == [],
        "nothing_to_act_on_distinguished": lonely_debug.get("action_outcome")
        == "nothing_to_act_on" and lonely_debug.get("previous_turn_id") is None,
    }
    return report, checks


WP45_SCHEMA_VERSION = 2  #v2.3
WP45_ACTION_INTENTS = ("repeat_previous", "print_previous")  #v2.3
WP45_INTENT_TARGET = 0.80  #v2.3
WP45_REGRESSION_TIMEOUT_SECONDS = 3600  #v2.3
REGRESSION_CLI = Path(__file__).resolve().parent / "run_regression.py"  #v2.3
BACKUP_SET_NAME = re.compile(r"^\d{8}T\d{6}Z$")  #v2.3


def _read_backup_manifest(set_directory: Path) -> tuple[dict[str, str], dict[str, str]]:  #v2.3
    """Split a backup manifest into its fields and its per-file SHA-256 values."""
    fields: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for line in (set_directory / "manifest.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("sha256:"):
            relative, digest = line[len("sha256:"):].rsplit("=", 1)
            hashes[relative] = digest
        elif "=" in line:
            name, value = line.split("=", 1)
            fields[name] = value
    return fields, hashes


def _sha256_file(path: Path) -> str:  #v2.3
    """Return the hex SHA-256 of one file, read in blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(partial(handle.read, 1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_backup_readability(data_root: Path) -> tuple[dict[str, object], dict[str, bool]]:  #v2.3
    """Verify the newest backup set without changing it (runbook 9.2 WP4.5 Test 1).

    Reads the database through an immutable URI, so no -wal or -shm file is
    created inside the set.
    """
    backups = data_root / "backups"
    sets = sorted(path for path in backups.glob("*")
                  if path.is_dir() and BACKUP_SET_NAME.match(path.name)) if backups.is_dir() else []
    if not sets:
        print(f"FAIL: no backup set under {backups}; run scripts/backup_sqlite.sh first.",
              file=sys.stderr)
        return {"backups": str(backups)}, {"backup_set_exists": False}
    newest = sets[-1]
    fields, hashes = _read_backup_manifest(newest)
    present = sorted(str(path.relative_to(newest)) for path in newest.rglob("*")
                     if path.is_file() and path.name != "manifest.txt")
    mismatched = [name for name, digest in hashes.items()
                  if not (newest / name).is_file() or _sha256_file(newest / name) != digest]
    database = newest / "kaki.db"
    try:
        with closing(sqlite3.connect(f"file:{database}?immutable=1", uri=True)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_problems = connection.execute("PRAGMA foreign_key_check").fetchall()
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            turns = connection.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
            audio_turns = connection.execute(
                "SELECT COUNT(*) FROM turns WHERE reply_audio IS NOT NULL").fetchone()[0]
    except sqlite3.Error as error:
        print(f"FAIL: cannot read {database}: {error}", file=sys.stderr)
        return {"backup_set": str(newest)}, {"backup_set_exists": True,
                                              "backup_database_readable": False}
    modes_owner_only = stat.S_IMODE(newest.stat().st_mode) == 0o700 and all(
        stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)
        for path in newest.rglob("*")
    )
    report = {
        "backup_set": str(newest), "backup_sets": len(sets), "manifest": fields,
        "files_hashed": len(hashes), "hash_mismatches": mismatched,
        "integrity_check": integrity, "foreign_key_problems": len(foreign_key_problems),
        "user_version": user_version, "turns": turns, "turns_with_reply_audio": audio_turns,
    }
    checks = {
        "backup_set_exists": True,
        "backup_database_readable": True,
        "backup_integrity_ok": integrity == "ok",
        "backup_foreign_keys_ok": not foreign_key_problems,
        "backup_schema_version_matches_packaged": user_version == packaged_schema_version()  #v2.5
        and user_version >= WP45_SCHEMA_VERSION,
        "manifest_user_version_matches": fields.get("user_version") == str(user_version),
        "manifest_turns_matches": fields.get("turns") == str(turns),
        "manifest_lists_every_file": sorted(hashes) == present,
        "manifest_hashes_match": not mismatched,
        "manifest_records_ingest_state": fields.get("ingest_running") in {"true", "false"},
        "backup_holds_database_corpus_and_index": database.is_file()
        and (newest / "corpus").is_dir() and (newest / "chroma").is_dir(),
        "backup_modes_owner_only": modes_owner_only,
        "backup_left_no_sidecar_files": not any(
            path.name.endswith(("-wal", "-shm")) for path in newest.rglob("*")
        ),
    }
    return report, checks


def _check_devset_actions() -> tuple[dict[str, object], dict[str, bool]]:  #v2.3
    """Run the devset regression and report the action-item result as a count and a rate."""
    completed, suite_record = run_suite(  #v2.9
        "run_regression.py", [sys.executable, str(REGRESSION_CLI)],
        timeout=WP45_REGRESSION_TIMEOUT_SECONDS,
    )
    try:
        regression = json.loads(completed.stdout)
    except ValueError:
        print(f"FAIL: run_regression.py printed no JSON report:\n{completed.stderr}",
              file=sys.stderr)
        return ({"regression_exit_code": completed.returncode,
                 "regression_tail": suite_record["tail"],
                 "regression_output": suite_record["output_path"]},
                {"regression_report_readable": False})
    actions = [result for result in regression["results"]
               if result["expected_intent"] in WP45_ACTION_INTENTS]
    correct = sum(1 for result in actions if result["actual_intent"] == result["expected_intent"])
    rate = correct / len(actions) if actions else 0.0
    report = {
        "regression_exit_code": completed.returncode,
        "regression_stderr_tail": suite_record["tail"],  #v2.9
        "regression_output": suite_record["output_path"],  #v2.9
        "items": regression["items"],
        "intent_accuracy": regression["intent_accuracy"],
        "action_items_result": f"{correct} of {len(actions)}, {rate:.2f}",
        "action_items_correct": correct,
        "action_items_total": len(actions),
        "golden_paths": f"{regression['golden_paths_passed']} of "
                        f"{regression['golden_paths_total']}",
    }
    checks = {
        "regression_report_readable": True,
        "regression_exit_code_0": completed.returncode == 0,
        "intent_accuracy_at_least_0_80": regression["intent_accuracy"] >= WP45_INTENT_TARGET,
        "action_items_present": bool(actions),
        "action_item_intents_at_least_0_80": bool(actions) and rate >= WP45_INTENT_TARGET,
        "all_golden_paths_passed": regression["golden_paths_passed"]
        == regression["golden_paths_total"],
    }
    return report, checks


def check_wp45_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v2.3
    """Prove WP4-AT-13 and backup readability (runbook 9.2 WP4.5 Tests 1 and 5).

    Needs the grounded configuration for the devset regression and a backup
    set written by scripts/backup_sqlite.sh. Reads the newest set read-only and
    never opens the live database.
    """
    if os.environ.get("KAKI_RETRIEVAL_MODE", "canned") != "rag":
        raise ValueError("export KAKI_RETRIEVAL_MODE=rag before running WP4.5 tier B.")
    StorageSettings.from_environment()  # validates KAKI_DATA_ROOT and KAKI_SQLITE_PATH
    data_root = Path(os.environ["KAKI_DATA_ROOT"])
    backup_report, checks = _check_backup_readability(data_root)
    devset_report, devset_checks = _check_devset_actions()
    checks.update(devset_checks)
    if "action_items_result" in devset_report:
        print(f"action items: {devset_report['action_items_result']}", file=sys.stderr)
    return {"backup": backup_report, "devset": devset_report}, checks


WP51_CDC_SOURCE_ID = "cdc-vouchers-residents"  #v2.4
# The runbook 10.1 WP5.1 probe questions with their curated English queries.
WP51_PROBES = (  #v2.4
    ("Macam mana saya boleh guna baucar CDC saya?", "How to use CDC vouchers"),
    ("Baucar CDC tu boleh guna kat mana?", "Where can CDC vouchers be used"),
    ("Saya nak tahu cara tuntut baucar CDC untuk isi rumah saya.",
     "How to claim CDC vouchers for household"),
)
WP51_MALAY_SENTENCE = "Baucar CDC boleh digunakan di kedai yang menyertai program ini."  #v2.4
# A gate value closer than this to the threshold is reported as near the gate.
WP51_NEAR_GATE_MARGIN = 0.10  #v2.4
WP51_MALAY_MARKERS = re.compile(  #v2.4
    r"\b(?:saya|anda|boleh|untuk|dengan|dan|yang|ini|itu|tidak|baucar|guna|kedai)\b",
    re.IGNORECASE,
)


def _wp51_voice() -> tuple[dict[str, object], dict[str, bool]]:  #v2.4
    """Check the configured Malay voice is installed and speaks non-empty audio."""
    tts = TtsSettings.from_environment()
    listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=30)
    listed = [line.split()[0] for line in listing.stdout.splitlines() if line.strip()]
    malay_lines = [line.strip() for line in listing.stdout.splitlines()
                   if "ms_MY" in line or "id_ID" in line]
    frames = -1
    error = None
    if tts.malay_voice in listed:
        from kaki_say_tts.adapter import SayTts

        try:
            audio = SayTts(timeout_seconds=tts.timeout_seconds, malay_voice=tts.malay_voice)
            frames = _decode_wav_frames(audio.synthesize(WP51_MALAY_SENTENCE, language="ms"))
        except TtsError as failure:
            error = failure.code
    report = {"malay_voice": tts.malay_voice, "installed_malay_and_indonesian_voices": malay_lines,
              "malay_speech_frames": frames, "malay_speech_error": error}
    return report, {
        "configured_malay_voice_is_listed": tts.malay_voice in listed,
        "malay_voice_speaks_non_empty_audio": frames > 0,
    }


def _gate_value(evidence) -> float | None:  #v2.4
    scores = [chunk.dense_score for chunk in evidence if chunk.dense_score is not None]
    return round(max(scores), 3) if scores else None


def _wp51_retrieval(threshold: float) -> tuple[dict[str, object], dict[str, bool]]:  #v2.4
    """Measure the gate value per Malay probe: original only, curated query, live rewrite."""
    from kaki_rag.adapter import KakiRagRetriever

    retrieval = RetrievalSettings.from_environment()
    retriever = KakiRagRetriever(retrieval.data_root, model_id=retrieval.embedding_model)
    llm = LlmSettings.from_environment().create_port()
    probes = []
    checks: dict[str, bool] = {}
    for number, (question, curated) in enumerate(WP51_PROBES, start=1):
        started = perf_counter()
        try:
            rewrite = llm.rewrite_query(question)
            rewrite_error = None
        except LlmError as failure:
            rewrite, rewrite_error = None, failure.code
        rewrite_ms = round((perf_counter() - started) * 1000, 1)
        measured = {"original_only": retriever.retrieve(question, None),
                    "curated_query": retriever.retrieve(question, curated)}
        if rewrite is not None:
            measured["qwen_rewrite"] = retriever.retrieve(question, rewrite)
        values = {leg: _gate_value(evidence) for leg, evidence in measured.items()}
        qwen_value = values.get("qwen_rewrite")
        probes.append({
            "question": question, "curated_query": curated, "qwen_rewrite": rewrite,
            "rewrite_error": rewrite_error, "rewrite_ms": rewrite_ms, "gate_values": values,
            "qwen_margin_over_gate": round(qwen_value - threshold, 3)
            if qwen_value is not None else None,
            "qwen_top3_sources": [chunk.source_id for chunk in measured.get("qwen_rewrite", ())],
        })
        qwen_top3 = [chunk.source_id for chunk in measured.get("qwen_rewrite", ())]
        checks[f"probe{number}_qwen_rewrite_present"] = rewrite is not None
        checks[f"probe{number}_qwen_top3_holds_cdc"] = WP51_CDC_SOURCE_ID in qwen_top3
        checks[f"probe{number}_qwen_gate_value_at_or_above_threshold"] = (
            qwen_value is not None and qwen_value >= threshold
        )
        checks[f"probe{number}_curated_gate_value_at_or_above_threshold"] = (
            values["curated_query"] is not None and values["curated_query"] >= threshold
        )
    near = [probe["question"] for probe in probes
            if probe["qwen_margin_over_gate"] is not None
            and probe["qwen_margin_over_gate"] < WP51_NEAR_GATE_MARGIN]
    if near:
        print(f"NOTE: Qwen-rewrite gate values within {WP51_NEAR_GATE_MARGIN} of the "
              f"{threshold} gate for: {near}. Report this to the owner as a decision.",
              file=sys.stderr)
    return {"threshold": threshold, "near_gate_margin": WP51_NEAR_GATE_MARGIN,
            "near_gate_questions": near, "probes": probes}, checks


# Malay CDC transcripts for the text turn: the probe question, and the exact
# Whisper transcript whose grounded answer came back Malay in Test 3
# (14-Sep-2026), which put Malay steps on the slip.  #v2.6
WP51_TEXT_TURNS = (  #v2.6
    ("probe", WP51_PROBES[0][0]),
    ("live_whisper", "Bagaimana saya boleh guna baucah CDC saya?"),
)


def _wp51_slip_body(slip_text: str) -> str:  #v2.6
    """Return the answered slip's lines between the heading and the Source: line."""
    body = []
    for line in slip_text.splitlines()[1:]:
        if line.startswith("Source: "):
            break
        body.append(line)
    return "\n".join(body)


def _wp51_text_turn() -> tuple[dict[str, object], dict[str, bool]]:  #v2.6
    """Run Malay CDC transcripts through the configured pipeline on a disposable store."""
    from kaki_backend.orchestration.language_policy import is_english_text
    from kaki_backend.orchestration.reply_language import BRIDGE_GREETING
    from run_regression import InjectedStt, build_pipeline, open_history, silent_audio

    language = LanguageSettings.from_environment()
    expected_language = "en" if language.malay_reply_mode == "english" else "ms"
    reports: dict[str, object] = {"reply_mode": language.malay_reply_mode}
    checks: dict[str, bool] = {}
    for tag, transcript in WP51_TEXT_TURNS:
        stt = InjectedStt()
        stt.speak(transcript, "ms")
        with tempfile.TemporaryDirectory(prefix="kaki-wp51-") as directory:
            pipeline = build_pipeline(stt, open_history(directory))
            execution = pipeline.execute(
                device_id="wp51-check", session_id=f"wp51-{uuid4()}",
                turn_id=f"wp51-{tag}-{uuid4()}", audio=silent_audio(),
                audio_preparation_ms=0.0, request_started_at=perf_counter(),
            )
        response, log = execution.response, execution.log
        slip_lines = response.slip_text.splitlines()
        body = _wp51_slip_body(response.slip_text)
        reports[tag] = {
            "transcript": transcript, "state": response.state.value,
            "language": response.language, "reply_text": response.reply_text,
            "slip_text": response.slip_text, "render_outcome": log.render_outcome,
            "normalised_query": log.normalised_query, "best_dense_score": log.best_dense_score,
            "cited_source_id": log.cited_source_id, "timings_ms": log.timings.model_dump(),
        }
        prefix = f"malay_turn_{tag}"
        checks.update({
            f"{prefix}_answered": response.state.value == "answered",
            f"{prefix}_cites_cdc": log.cited_source_id == WP51_CDC_SOURCE_ID,
            f"{prefix}_rewrite_present": log.normalised_query is not None,
            f"{prefix}_policy_decided_ms": log.reply_language == "ms",
            f"{prefix}_language_{expected_language}": response.language == expected_language,
            f"{prefix}_slip_heading": bool(slip_lines) and slip_lines[0] == "KAKI-TALKIE HELP",
            f"{prefix}_slip_body_has_steps": bool(body.strip()),
            f"{prefix}_slip_body_is_english": is_english_text(body)
            and WP51_MALAY_MARKERS.search(body) is None,
            f"{prefix}_slip_has_no_you_asked_line": "You asked:" not in slip_lines,
        })
        if language.malay_reply_mode == "full":
            checks[f"{prefix}_render_outcome_rendered"] = log.render_outcome == "rendered"
        elif language.malay_reply_mode == "bridge":
            checks[f"{prefix}_reply_starts_with_bridge_greeting"] = (
                response.reply_text.startswith(BRIDGE_GREETING)
            )
    return reports, checks


def check_wp51_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v2.4
    """Prove the Malay voice, Malay retrieval and a Malay text turn (runbook 10.2 WP5.1).

    Needs the grounded configuration, MLX-LM and the Chroma index; posts
    nothing to the backend and never opens the live database.
    """
    if os.environ.get("KAKI_RETRIEVAL_MODE", "canned") != "rag":
        raise ValueError("export KAKI_RETRIEVAL_MODE=rag before running WP5.1 tier B.")
    if os.environ.get("KAKI_LLM_MODE", "canned") != "qwen":
        raise ValueError("export KAKI_LLM_MODE=qwen before running WP5.1 tier B.")
    retrieval = RetrievalSettings.from_environment()
    voice_report, checks = _wp51_voice()
    retrieval_report, retrieval_checks = _wp51_retrieval(retrieval.evidence_min_dense)
    turn_report, turn_checks = _wp51_text_turn()
    checks.update(retrieval_checks)
    checks.update(turn_checks)
    return {"voice": voice_report, "retrieval": retrieval_report, "text_turn": turn_report}, checks


# ---------------------------------------------------------------------------
# WP6.1: the device stays a thin client (WP6-AT-13).
# ---------------------------------------------------------------------------

DEVICE_ROOT = Path(__file__).resolve().parent.parent / "device"  #v2.7
# Everything the thin client may import: the standard library plus one HTTP
# client, pygame for drawing, gpiozero for the dome button (WP6.2, from apt -
# setup.md 29.3) and its own package. gpiozero is deliberately absent from
# DEVICE_ALLOWED_DEPENDENCIES: it is never a pyproject dependency (owner
# decision, 20-Sep-2026).
DEVICE_ALLOWED_IMPORTS = frozenset({"httpx", "pygame", "gpiozero", "kaki_device"})  #v3.0
DEVICE_ALLOWED_DEPENDENCIES = frozenset({"httpx", "pygame"})  #v2.7
# Modules that would mean the Pi had started thinking for itself.
DEVICE_FORBIDDEN_IMPORTS = frozenset({  #v2.7
    "kaki_backend", "kaki_rag", "kaki_qwen_local", "kaki_whisper_cpp", "kaki_say_tts",
    "chromadb", "sentence_transformers", "transformers", "mlx", "mlx_lm", "dspy",
    "torch", "sqlite3", "fastapi", "uvicorn",
})
# Text that would mean model, retrieval, prompt, case or SQL logic on the Pi.
DEVICE_FORBIDDEN_TOKENS = (  #v2.7
    ":8081", ":8082", "/v1/chat/completions", "/v1/models", "SYSTEM_PROMPT",
    "GROUNDED_SYSTEM_PROMPT", "RENDER_SYSTEM_PROMPT", "REWRITE_SYSTEM_PROMPT",
    "evidence_min_dense", "best_dense_score", "refusal_reason", "no_coverage",
    "INSERT INTO", "SELECT ", "CREATE TABLE", "cited_source", "devset",
)
# The device calls these paths and no others (design.md 5).
DEVICE_ALLOWED_PATHS = frozenset({"/api/device/turn", "/api/device/pending", "/api/health"})  #v2.7
DEVICE_PATH_LITERAL = re.compile(r"[\"']((?:/api|/v1)[a-zA-Z0-9_/.-]*)[\"']")  #v2.7
DEVICE_ENVIRONMENT_LITERAL = re.compile(r"[\"'](KAKI_[A-Z0-9_]+)[\"']")  #v2.7
DEVICE_ENVIRONMENT_PREFIX = "KAKI_DEVICE_"  #v2.7


def _device_sources() -> list[Path]:  #v2.7
    """Return every Python file the device ships, tests excluded."""
    return sorted((DEVICE_ROOT / "src").rglob("*.py"))


def _imported_names(tree: ast.AST) -> set[str]:  #v2.7
    """Return the top-level module names a parsed file imports."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def thin_client_findings(root: Path | None = None) -> dict[str, list[str]]:  #v2.7
    """Inspect the device package for anything that is not a thin client.

    Returns one list of human-readable findings per rule; empty lists mean the
    package passed. Pure static reading: no import, no execution, no network.
    """
    root = DEVICE_ROOT if root is None else root
    sources = sorted((root / "src").rglob("*.py"))
    findings: dict[str, list[str]] = {
        "imports": [], "dependencies": [], "tokens": [], "paths": [], "environment": [],
    }
    if not sources:
        findings["imports"].append(f"no device sources found under {root}/src")
        return findings

    standard = set(sys.stdlib_module_names)
    for path in sources:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root)
        for name in sorted(_imported_names(ast.parse(text, filename=str(path)))):
            if name in DEVICE_FORBIDDEN_IMPORTS:
                findings["imports"].append(f"{relative} imports {name}")
            elif name not in standard and name not in DEVICE_ALLOWED_IMPORTS:
                findings["imports"].append(f"{relative} imports unapproved {name}")
        for token in DEVICE_FORBIDDEN_TOKENS:
            if token in text:
                findings["tokens"].append(f"{relative} contains {token!r}")
        for literal in DEVICE_PATH_LITERAL.findall(text):
            if literal not in DEVICE_ALLOWED_PATHS:
                findings["paths"].append(f"{relative} requests {literal}")
        for name in DEVICE_ENVIRONMENT_LITERAL.findall(text):
            if not name.startswith(DEVICE_ENVIRONMENT_PREFIX):
                findings["environment"].append(f"{relative} reads {name}")

    # Runtime dependencies only: `build-system.requires` is what builds the
    # wheel on a developer machine, not what the kiosk imports.
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = manifest.get("project", {})
    declared = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared.extend(extra)
    for requirement in declared:
        name = re.split(r"[><=!~\[ ]", requirement, maxsplit=1)[0].strip().lower()
        if name not in DEVICE_ALLOWED_DEPENDENCIES:
            findings["dependencies"].append(f"pyproject.toml declares {requirement}")
    return findings


def check_wp61_tier_a() -> tuple[dict[str, object], dict[str, bool]]:  #v2.7
    """Prove the device is a thin client and its own suite passes (WP6-AT-13).

    Deterministic: reads `device/` and runs `device/tests`. No backend, no
    hardware, no network.
    """
    findings = thin_client_findings()
    suite, suite_record = run_suite(  #v2.9
        "device_tests",
        [sys.executable, "-m", "unittest", "discover", "-s", str(DEVICE_ROOT / "tests"),
         "-t", str(DEVICE_ROOT / "tests")],
    )
    report = {
        "device_root": str(DEVICE_ROOT),
        "device_sources": [str(path.relative_to(DEVICE_ROOT)) for path in _device_sources()],
        "findings": findings,
        "suite_exit_code": suite.returncode,
        "suite_tests_ran": suite_record["tests_ran"],
        "suite_tail": suite_record["tail"],
        "suite_output": suite_record["output_path"],
    }
    checks = {f"no_{rule}_findings": not found for rule, found in findings.items()}
    checks["device_suite_passed"] = suite.returncode == 0
    checks["device_suite_ran_tests"] = report["suite_tests_ran"] > 0
    return report, checks


def check_wp61_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v2.7
    """Drive one scripted mock turn through the device loop against the live stack.

    Uses the mock button, microphone, speaker and printer, so it needs no
    hardware, and posts one committed fixture to the running backend. Writes
    nothing except the turn the backend stores, as any device turn does.
    Needs KAKI_DEVICE_TOKEN since WP6.4: this check builds the BackendClient
    directly rather than through load_config, so it passes the token
    explicitly, exactly as the kiosk's own entry point does (#v3.2).
    """
    token = os.environ.get("KAKI_DEVICE_TOKEN", "").strip()  #v3.2
    if not token:  #v3.2
        raise ValueError("export KAKI_DEVICE_TOKEN before running WP6.1 tier B "
                         "(runbook 11.1 WP6.1; the device path fails closed since WP6.4).")
    sys.path.insert(0, str(DEVICE_ROOT / "src"))
    from kaki_device.api_client import BackendClient
    from kaki_device.config import DeviceConfig, MockSettings
    from kaki_device.mock_io import (
        CollectingDisplay, FixtureMicrophone, LoggingPrinter, RecordingSpeaker,
        ScriptedButton, fixed_measure,
    )
    from kaki_device.state_machine import TurnLoop

    fixture = Path(str(files("kaki_backend").joinpath("fixtures", "cdc_question.wav")))
    if not fixture.is_file():
        raise ValueError(f"the spoken fixture is missing: {fixture}")
    config = DeviceConfig(
        device_id=f"wp61-check-{uuid4()}", mock=MockSettings(audio_path=fixture),
    )
    display, printer, speaker = CollectingDisplay(), LoggingPrinter(), RecordingSpeaker()
    loop = TurnLoop(
        config, BackendClient(config.backend_url, timeout_seconds=300, token=token),  #v3.2
        button=ScriptedButton(), microphone=FixtureMicrophone(config.mock.audio_path),
        speaker=speaker, printer=printer, display=display, measure=fixed_measure(),
    )
    pending = loop.poll_pending()
    outcome = loop.run_turn()
    report = {
        "device_id": config.device_id, "turn_id": outcome.turn_id,
        "session_id": outcome.session_id, "state": outcome.state,
        "error_code": outcome.error_code, "printed": outcome.printed,
        "spoke": outcome.spoke, "truncated": outcome.truncated,
        "display_states": display.states, "pending_items": len(pending),
        "slip_first_line": printer.slips[0].splitlines()[0] if printer.slips else None,
        "spoken_seconds": round(speaker.durations[0], 2) if speaker.durations else 0.0,
    }
    return report, {
        "turn_completed_without_local_error": outcome.error_code is None,
        "backend_state_is_a_contract_state": outcome.state in {
            "answered", "refused", "acted", "handed_off", "failed"
        },
        "display_showed_recording_thinking_then_answer": display.states == [
            "recording", "thinking", "answer"
        ],
        "reply_audio_played": outcome.spoke and report["spoken_seconds"] > 0,
        "slip_printed_under_auto_policy": outcome.printed,
        "pending_is_empty": not pending,
    }


# ---------------------------------------------------------------------------
# WP6.2: physical I/O - button, audio, live countdown.
# ---------------------------------------------------------------------------


def _import_kaki_device():  #v3.0
    """Make the device package importable from the checkout and return it."""
    source = str(DEVICE_ROOT / "src")
    if source not in sys.path:
        sys.path.insert(0, source)
    import kaki_device
    return kaki_device


def check_wp62_tier_a() -> tuple[dict[str, object], dict[str, bool]]:  #v3.0
    """Prove the hardware layer deterministically (WP6-AT-01/02 at tier A).

    Runs the device suite (which exercises the GPIO and ALSA fakes), re-runs
    the WP6-AT-13 inspection with the WP6.2 allowlist, and converts one
    16 kHz mono WAV directly, pinning the design.md 4.3 playback contract:
    everything becomes 48 kHz stereo S16_LE. No hardware, no network.
    """
    _import_kaki_device()
    from kaki_device.alsa_audio import convert_to_playback
    from kaki_device.mock_io import silent_wav

    findings = thin_client_findings()
    suite, suite_record = run_suite(
        "device_tests",
        [sys.executable, "-m", "unittest", "discover", "-s", str(DEVICE_ROOT / "tests"),
         "-t", str(DEVICE_ROOT / "tests")],
    )
    converted = convert_to_playback(silent_wav(seconds=1.0, framerate=16000))
    with wave.open(io.BytesIO(converted), "rb") as playback:
        playback_format = (
            playback.getnchannels(), playback.getsampwidth(), playback.getframerate(),
        )
        playback_seconds = playback.getnframes() / playback.getframerate()
    report = {
        "findings": findings,
        "suite_exit_code": suite.returncode,
        "suite_tests_ran": suite_record["tests_ran"],
        "suite_tail": suite_record["tail"],
        "suite_output": suite_record["output_path"],
        "playback_format": {
            "channels": playback_format[0], "sample_width_bytes": playback_format[1],
            "rate": playback_format[2], "seconds": round(playback_seconds, 3),
        },
    }
    checks = {f"no_{rule}_findings": not found for rule, found in findings.items()}
    checks["device_suite_passed"] = suite.returncode == 0
    checks["device_suite_ran_tests"] = suite_record["tests_ran"] > 0
    checks["playback_is_48k_stereo_s16"] = playback_format == (2, 2, 48000)
    checks["playback_duration_preserved"] = abs(playback_seconds - 1.0) < 0.02
    return report, checks


def check_wp62_tier_c() -> tuple[dict[str, object], dict[str, bool]]:  #v3.0
    """Service-level assertions on the Pi; no owner action is simulated.

    Runs on the Raspberry Pi from the cloned checkout with the device venv
    (runbook 11.2 WP6.2). Reads the device configuration from `KAKI_DEVICE_*`
    exports and, when set, the file named by `KAKI_DEVICE_CONFIG`. The
    physical proofs - press, rattle, hold, listen, read the panel - stay with
    the owner; this checks only that the services those proofs need exist.
    """
    kaki_device = _import_kaki_device()
    del kaki_device
    from kaki_device.config import load_config

    config = load_config(os.environ.get("KAKI_DEVICE_CONFIG") or None)
    report: dict[str, object] = {
        "device_id": config.device_id, "backend_url": config.backend_url,
        "audio_card": config.audio.card, "button_pin": config.button.pin,
    }
    checks: dict[str, bool] = {
        "arecord_installed": shutil.which("arecord") is not None,
        "aplay_installed": shutil.which("aplay") is not None,
        "audio_card_configured": bool(config.audio.card),
    }
    try:
        import gpiozero  # noqa: F401
        checks["gpiozero_importable"] = True
    except ImportError:
        checks["gpiozero_importable"] = False

    if checks["arecord_installed"] and config.audio.card:
        listing = subprocess.run(
            ["arecord", "-L"], capture_output=True, text=True, timeout=30,
        )
        # `plughw:CARD=Speak` must resolve to a listed card name such as
        # `plughw:CARD=Speak,DEV=0`; match on the CARD= identity.
        identity = config.audio.card.split(":", 1)[-1].split(",", 1)[0]
        checks["audio_card_resolvable"] = listing.returncode == 0 and identity in listing.stdout
        report["alsa_identity_sought"] = identity
    else:
        checks["audio_card_resolvable"] = False

    kiosk = subprocess.run(
        ["pgrep", "-f", "kaki_device.main"], capture_output=True, text=True, timeout=30,
    )
    checks["kiosk_process_running"] = kiosk.returncode == 0
    report["kiosk_pids"] = kiosk.stdout.split()

    with httpx.Client(base_url=config.backend_url, timeout=30,
                      headers=({"Authorization": f"Bearer {config.token}"}
                               if config.token else {})) as client:  #v3.1
        try:
            health = client.get("/api/health")
            checks["backend_reachable"] = health.status_code == 200
            report["backend_health"] = health.json() if health.status_code == 200 else None
        except httpx.HTTPError as error:
            checks["backend_reachable"] = False
            report["backend_health"] = f"unreachable: {error}"
        try:
            debug = client.get("/api/device/debug/last-turn")
            last_device = debug.json().get("device_id") if debug.status_code == 200 else None
            report["last_turn_device_id"] = last_device
            checks["backend_received_a_turn_from_this_device"] = (
                last_device == config.device_id
            )
        except (httpx.HTTPError, ValueError):
            report["last_turn_device_id"] = None
            checks["backend_received_a_turn_from_this_device"] = False
    return report, checks


# ---------------------------------------------------------------------------
# WP6.6: the demo admin surface.
# ---------------------------------------------------------------------------

WP66_SUITES = (  #v2.8
    ("backend/tests/contract", "test_wp6_6.py"),
    ("backend/tests/unit", "test_admin_store.py"),
    ("backend/tests/unit", "test_language_override.py"),
)
WP66_SCHEMA_VERSION = 4  #v2.8
WP66_MESSAGE_KEY = "cdc-vouchers-available"  #v2.8
WP66_PUSH_FIXTURES = ("push_cdc_en.wav", "push_cdc_ms.wav")  #v2.8


def check_wp66_tier_a() -> tuple[dict[str, object], dict[str, bool]]:  #v2.8
    """Prove the admin surface deterministically (WP6-AT-15/16/17 at tier A).

    Runs the three WP6.6 suites from the checkout root so `kaki_test_env`
    sanitises the environment, re-runs the WP6-AT-13 inspection (the unit
    must not have touched the device), and pins the packaged schema version.
    """
    root = Path(__file__).resolve().parent.parent
    report: dict[str, object] = {"suites": {}}
    checks: dict[str, bool] = {}
    for directory, pattern in WP66_SUITES:
        completed, record = run_suite(  #v2.9
            pattern,
            [sys.executable, "-m", "unittest", "discover", "-s", directory, "-p", pattern],
            cwd=root,
        )
        report["suites"][pattern] = record
        checks[f"{pattern}_passed"] = completed.returncode == 0
        checks[f"{pattern}_ran_tests"] = record["tests_ran"] > 0
    findings = thin_client_findings()
    report["thin_client_findings"] = findings
    checks["device_still_a_thin_client"] = not any(findings.values())
    report["packaged_schema_version"] = packaged_schema_version()
    checks["packaged_schema_version_is_4"] = packaged_schema_version() == WP66_SCHEMA_VERSION
    report["push_fixtures_present"] = {
        name: Path(str(files("kaki_backend").joinpath("fixtures", name))).is_file()
        for name in WP66_PUSH_FIXTURES
    }
    return report, checks


def _admin_request(client: httpx.Client, method: str, path: str, token: str | None,
                   body: dict | None = None) -> httpx.Response:  #v2.8
    """Send one admin request with or without the bearer token."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.request(method, path, headers=headers, json=body)


def check_wp66_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v2.8
    """Prove the live admin flow on the running stack (WP6-AT-15/16/17).

    Needs KAKI_ADMIN_TOKEN in the environment and the grounded stack. Uses a
    scratch device_id throughout and restores its configuration to `auto`, so
    the kiosk's own configuration is never touched. Posts one real turn, which
    the backend stores like any other.
    """
    token = os.environ.get("KAKI_ADMIN_TOKEN", "").strip()
    if not token:
        raise ValueError("export KAKI_ADMIN_TOKEN before running WP6.6 tier B.")
    for name in WP66_PUSH_FIXTURES:
        if not Path(str(files("kaki_backend").joinpath("fixtures", name))).is_file():
            raise ValueError(
                f"the push fixture {name} is missing: run "
                "scripts/wp6_6_evidence.sh --capture-fixtures first."
            )
    device_id = f"wp66-check-{uuid4().hex[:8]}"
    report: dict[str, object] = {"device_id": device_id}
    checks: dict[str, bool] = {}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=300,
                      headers=_device_headers()) as client:  #v3.1
        unauthenticated = _admin_request(
            client, "POST", "/api/admin/config", None,
            {"device_id": device_id, "reply_language": "ms"},
        )
        checks["unauthenticated_request_rejected"] = unauthenticated.status_code == 401
        state = _admin_request(client, "GET", "/api/admin/state", token)
        checks["state_readable_with_token"] = state.status_code == 200
        checks["rejected_write_changed_nothing"] = device_id not in [
            row["device_id"] for row in state.json().get("config", [])
        ]

        configured = _admin_request(client, "POST", "/api/admin/config", token,
                                    {"device_id": device_id, "reply_language": "ms"})
        checks["config_accepted"] = configured.status_code == 200

        fixture = files("kaki_backend").joinpath("fixtures", "cdc_question.wav").read_bytes()
        turn = client.post(
            "/api/device/turn",
            data={"device_id": device_id, "session_id": device_id,
                  "turn_id": f"wp66-{uuid4().hex[:8]}"},
            files={"audio": ("cdc_question.wav", fixture, "audio/wav")},
        )
        body = turn.json() if turn.status_code == 200 else {}
        debug = client.get("/api/device/debug/last-turn").json()
        report["turn"] = {"status": turn.status_code, "state": body.get("state"),
                          "language": body.get("language"),
                          "language_override": debug.get("language_override")}
        checks["override_turn_answered"] = body.get("state") == "answered"
        checks["override_turn_replied_in_ms_without_restart"] = body.get("language") == "ms"
        checks["override_recorded_on_the_turn"] = debug.get("language_override") == "ms"

        pushed = _admin_request(client, "POST", "/api/admin/push", token,
                                {"device_id": device_id})
        checks["push_accepted"] = pushed.status_code == 200
        first = client.get(f"/api/device/pending?device_id={device_id}").json()
        second = client.get(f"/api/device/pending?device_id={device_id}").json()
        anonymous = client.get("/api/device/pending").json()
        report["pending"] = {"first": len(first), "second": len(second),
                             "anonymous": len(anonymous)}
        checks["push_delivered_once"] = len(first) == 1 and second == []
        checks["pending_empty_without_identity"] = anonymous == []
        if first:
            item = first[0]
            report["nudge"] = {"id": item.get("id"), "language": item.get("language"),
                               "text": item.get("text", "")[:60],
                               "audio_bytes": len(item.get("audio") or "")}
            checks["nudge_is_the_seeded_malay_message"] = (
                item.get("id") == WP66_MESSAGE_KEY and item.get("language") == "ms"
            )
            checks["nudge_carries_presynthesised_audio"] = bool(item.get("audio"))
        restore = _admin_request(client, "POST", "/api/admin/config", token,
                                 {"device_id": device_id, "reply_language": "auto"})
        checks["scratch_config_restored_to_auto"] = restore.status_code == 200
    return report, checks


# ---------------------------------------------------------------------------
# WP6.4: device service auth, same-turn_id retry, systemd recovery.
# ---------------------------------------------------------------------------

WP64_SERVICE_UNIT = "infra/pi/kaki-device.service"  #v3.1
# The WP6.8 ergonomics pass replaces this placeholder copy; tier A pins the
# exact strings so a silent rewrite cannot slip past the owner sign-off.
WP64_RETRYING_TITLE = "Checking again..."  #v3.1
WP64_CONNECTION_ERROR_BODY = "Cannot connect. Press the button to try again."  #v3.1


def check_wp64_tier_a() -> tuple[dict[str, object], dict[str, bool]]:  #v3.1
    """Prove auth, retry and recovery deterministically (WP6-AT-04/05/10 at tier A).

    Runs the WP6.4 backend contract suite (auth boundaries, fail-closed, the
    in-flight duplicate turn_id race) and the device suite (bearer header,
    same-turn_id retry, retrying frame, placeholder copy), re-runs the
    WP6-AT-13 inspection, checks the placeholder screen copy carries its
    WP6.8 replacement marker, and statically checks the systemd unit:
    Restart=always with StartLimitIntervalSec=0, running kaki_device.main
    against /etc/kaki/device.toml. No backend, no hardware, no network.
    """
    root = Path(__file__).resolve().parent.parent
    report: dict[str, object] = {"suites": {}}
    checks: dict[str, bool] = {}
    contract, contract_record = run_suite(
        "test_wp6_4.py",
        [sys.executable, "-m", "unittest", "discover", "-s", "backend/tests/contract",
         "-p", "test_wp6_4.py"],
        cwd=root,
    )
    report["suites"]["test_wp6_4.py"] = contract_record
    checks["backend_wp64_suite_passed"] = contract.returncode == 0
    checks["backend_wp64_suite_ran_tests"] = contract_record["tests_ran"] > 0
    device, device_record = run_suite(
        "device_tests",
        [sys.executable, "-m", "unittest", "discover", "-s", str(DEVICE_ROOT / "tests"),
         "-t", str(DEVICE_ROOT / "tests")],
    )
    report["suites"]["device_tests"] = device_record
    checks["device_suite_passed"] = device.returncode == 0
    checks["device_suite_ran_tests"] = device_record["tests_ran"] > 0

    findings = thin_client_findings()
    report["thin_client_findings"] = findings
    checks["device_still_a_thin_client"] = not any(findings.values())

    _import_kaki_device()
    from kaki_device.display import layout as device_layout
    layout_source = (DEVICE_ROOT / "src/kaki_device/display/layout.py").read_text(
        encoding="utf-8"
    )
    report["placeholder_copy"] = {
        "retrying_title": device_layout.RETRYING_TITLE,
        "connection_error_body": device_layout.CONNECTION_ERROR_BODY,
    }
    checks["retrying_copy_is_the_agreed_placeholder"] = (
        device_layout.RETRYING_TITLE == WP64_RETRYING_TITLE
    )
    checks["failure_copy_is_the_agreed_placeholder"] = (
        device_layout.CONNECTION_ERROR_BODY == WP64_CONNECTION_ERROR_BODY
    )
    checks["placeholder_copy_marked_for_wp68"] = "TODO(WP6.8)" in layout_source

    unit_path = root / WP64_SERVICE_UNIT
    unit_text = unit_path.read_text(encoding="utf-8") if unit_path.is_file() else ""
    report["service_unit"] = WP64_SERVICE_UNIT
    checks["service_unit_present"] = bool(unit_text)
    checks["service_unit_restarts_always"] = "Restart=always" in unit_text
    checks["service_unit_never_exhausts_restarts"] = "StartLimitIntervalSec=0" in unit_text
    checks["service_unit_runs_the_device_main"] = "-m kaki_device.main" in unit_text
    checks["service_unit_reads_etc_kaki_device_toml"] = "/etc/kaki/device.toml" in unit_text
    checks["service_unit_enabled_at_boot"] = "WantedBy=graphical.target" in unit_text
    return report, checks


def check_wp64_tier_b() -> tuple[dict[str, object], dict[str, bool]]:  #v3.1
    """Prove auth and the single-answer retry on the running stack (WP6-AT-04/05).

    Needs KAKI_DEVICE_TOKEN in the environment and the grounded stack. An
    unauthenticated and a wrongly-authenticated turn are refused with no
    state change; an authenticated turn answers; a replay of its turn_id
    with different audio returns the identical stored response and the debug
    view records the replay. Posts two real turns' worth of requests, of
    which the backend executes one.
    """
    token = os.environ.get("KAKI_DEVICE_TOKEN", "").strip()
    if not token:
        raise ValueError("export KAKI_DEVICE_TOKEN before running WP6.4 tier B.")
    fixture = files("kaki_backend").joinpath("fixtures", "cdc_question.wav").read_bytes()
    turn_id = f"wp64-check-{uuid4().hex[:12]}"
    fields = {"device_id": "wp64-check", "session_id": "wp64-check", "turn_id": turn_id}
    report: dict[str, object] = {"turn_id": turn_id}
    checks: dict[str, bool] = {}

    def post_turn(client: httpx.Client, audio_name: str, audio: bytes,
                  headers: dict[str, str] | None = None) -> httpx.Response:
        return client.post(
            "/api/device/turn", data=fields,
            files={"audio": (audio_name, audio, "audio/wav")},
            headers=headers,
        )

    try:
        with httpx.Client(
            base_url=BACKEND_URL, timeout=300, trust_env=False, follow_redirects=False,
            headers=_device_headers(),
        ) as client:
            checks["health_open_without_a_token"] = (
                httpx.get(BACKEND_URL + "/api/health", timeout=30).status_code == 200
            )
            before = client.get("/api/device/debug/last-turn")
            before_id = before.json().get("turn_id") if before.status_code == 200 else None

            unauthenticated = post_turn(client, "cdc_question.wav", fixture,
                                        headers={"Authorization": ""})
            wrong = post_turn(client, "cdc_question.wav", fixture,
                              headers={"Authorization": "Bearer wrong-token"})
            checks["unauthenticated_turn_rejected"] = unauthenticated.status_code == 401
            checks["wrong_token_rejected"] = wrong.status_code == 401
            after = client.get("/api/device/debug/last-turn")
            after_id = after.json().get("turn_id") if after.status_code == 200 else None
            checks["rejection_changed_no_state"] = before_id == after_id
            checks["pending_needs_the_token_too"] = (
                httpx.get(BACKEND_URL + "/api/device/pending", timeout=30).status_code
                == 401
            )

            first = post_turn(client, "cdc_question.wav", fixture)
            checks["authenticated_turn_answered"] = (
                first.status_code == 200 and first.json().get("state") == "answered"
            )
            # WP6-AT-04, server half: the same turn_id with different audio is
            # served the single stored answer; re-execution would differ.
            replay = post_turn(client, "different.wav", b"")
            checks["replay_returns_the_identical_answer"] = (
                replay.status_code == 200 and replay.json() == first.json()
            )
            debug = client.get("/api/device/debug/last-turn").json()
            report["replayed_turn"] = {
                "turn_id": debug.get("turn_id"),
                "replay_count": debug.get("replay_count"),
                "state": debug.get("state"),
            }
            checks["replay_recorded_not_reexecuted"] = (
                debug.get("turn_id") == turn_id and debug.get("replay_count") == 1
            )
    except (httpx.HTTPError, ValueError):
        print("FAIL: the backend stack is not reachable; start it first "
              "(runbook 11.2 WP6.4).", file=sys.stderr)
        return report, {"stack_reachable": False}
    return report, checks


REGISTRY = {
    ("WP2.3", "B"): check_wp23_tier_b,
    ("WP2.4", "B"): check_wp24_tier_b,
    ("WP3.1", "B"): check_wp31_tier_b,
    ("WP3.2", "B"): check_wp32_tier_b,
    ("WP3.3", "B"): check_wp33_tier_b,  #v1.5
    ("WP3.4", "B"): check_wp34_tier_b,  #v1.8
    ("WP4.1", "B"): check_wp41_tier_b,  #v2.0
    ("WP4.2", "B"): check_wp42_tier_b,  #v2.1
    ("WP4.5", "B"): check_wp45_tier_b,  #v2.3
    ("WP5.1", "B"): check_wp51_tier_b,  #v2.4
    ("WP6.1", "A"): check_wp61_tier_a,  #v2.7
    ("WP6.1", "B"): check_wp61_tier_b,  #v2.7
    ("WP6.2", "A"): check_wp62_tier_a,  #v3.0
    ("WP6.2", "C"): check_wp62_tier_c,  #v3.0
    ("WP6.4", "A"): check_wp64_tier_a,  #v3.1
    ("WP6.4", "B"): check_wp64_tier_b,  #v3.1
    ("WP6.6", "A"): check_wp66_tier_a,  #v2.8
    ("WP6.6", "B"): check_wp66_tier_b,  #v2.8
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
        "--tier", required=True, choices=["A", "B", "C"],
        help="Test tier: A deterministic developer checks, B Mac runtime checks, "
             "C Raspberry Pi service checks (run on the Pi)",
    )
    parser.add_argument(  #v2.9
        "--evidence", metavar="DIR", default=None,
        help="Directory to write each suite's full output to as <suite>.output.txt. "
             "Created if absent. Defaults to $KAKI_WP_EVIDENCE, or nothing when unset.",
    )
    return parser


def main() -> int:
    """Run the registered checks for the requested unit/tier and print a JSON report.

    Side effect: with `--evidence` (or `KAKI_WP_EVIDENCE`) set, each suite the
    checks run leaves its full output in that directory.
    """
    global EVIDENCE_DIRECTORY  #v2.9
    args = build_parser().parse_args()
    if args.evidence:
        EVIDENCE_DIRECTORY = Path(args.evidence).expanduser()
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
    directory = _evidence_directory()  #v2.9
    if directory is not None:
        print(f"Suite output: {directory}/<suite>.output.txt", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
