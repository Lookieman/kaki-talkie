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
live database. Exit status is zero only when every check passes; 2 indicates a
usage or configuration error.
"""

import argparse
import io
import json
import os
import re
import sqlite3  #v2.0
import stat  #v2.0
import sys
import tempfile  #v2.0
import wave
from pathlib import Path
from base64 import b64decode
from contextlib import closing  #v2.0
from importlib.resources import files
from time import perf_counter
from uuid import uuid4

import httpx
from dotenv import load_dotenv  #v1.6

from kaki_backend.config import APPROVED_QWEN_MODEL, LlmSettings, TtsSettings
from kaki_backend.config import StorageSettings  #v2.0
from kaki_backend.contracts.ports import LlmError, TtsError
from kaki_backend.orchestration.canned_ports import CannedLlmPort, CannedSttPort

# The WP3.2/WP3.3 checks embed with a Hugging Face model, whose `HF_TOKEN`
# lives in the untracked project-root .env; a real export wins.
load_dotenv()  #v1.6

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
        with httpx.Client(timeout=180, trust_env=False, follow_redirects=False) as client:
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
        "live_database_at_exact_schema_version_2": schema_version == WP42_SCHEMA_VERSION,
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


REGISTRY = {
    ("WP2.3", "B"): check_wp23_tier_b,
    ("WP2.4", "B"): check_wp24_tier_b,
    ("WP3.1", "B"): check_wp31_tier_b,
    ("WP3.2", "B"): check_wp32_tier_b,
    ("WP3.3", "B"): check_wp33_tier_b,  #v1.5
    ("WP3.4", "B"): check_wp34_tier_b,  #v1.8
    ("WP4.1", "B"): check_wp41_tier_b,  #v2.0
    ("WP4.2", "B"): check_wp42_tier_b,  #v2.1
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
