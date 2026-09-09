# v1.0 | 09-Sep-2026 | Provide the WP2.4 owner CLI for the p50/p95 end-to-end latency baseline.
"""Record the end-to-end turn latency baseline against the running local stack.

Sends the given deliberate test audio through `POST /api/device/turn` for the
requested number of runs, each with a fresh `turn_id`, and reports per-run
wall-clock milliseconds plus the p50 and p95 over all runs as JSON. Latency
values are recorded, never judged: no pass threshold exists in WP2 (runbook
7.4.2 Test 5). The full stack must already be running.

Side effects: sends `--runs` real turns to the configured backend, which
transcribes, generates and synthesises each one. Nothing is written to disk.
Exit status is zero only when every run completes as `answered`; 2 indicates
a usage or configuration error.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx

BACKEND_URL = "http://127.0.0.1:8000"
MAX_RUNS = 100


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Return the nearest-rank percentile of an ascending non-empty list."""
    if not sorted_values or not 0 < fraction <= 1:
        raise ValueError("percentile requires values and a fraction in (0, 1].")
    rank = math.ceil(fraction * len(sorted_values))
    return sorted_values[rank - 1]


def build_parser() -> argparse.ArgumentParser:
    """Describe the run count, test audio and backend endpoint."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--runs", type=int, default=10,
        help=f"Number of sequential turns to time, 1-{MAX_RUNS} (default 10)",
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Deliberate test audio to submit each run"
    )
    parser.add_argument(
        "--url", default=BACKEND_URL, help=f"Backend base URL (default {BACKEND_URL})"
    )
    parser.add_argument(
        "--timeout-seconds", type=float, default=120.0,
        help="Per-request network timeout in seconds (default 120)",
    )
    return parser


def run_measurement(
    args: argparse.Namespace, transport: httpx.BaseTransport | None = None,
) -> int:
    """Time the requested turns and print the JSON report; return non-zero on failure."""
    if not 1 <= args.runs <= MAX_RUNS:
        print(f"FAIL: --runs must be between 1 and {MAX_RUNS}.", file=sys.stderr)
        return 2
    if not math.isfinite(args.timeout_seconds) or args.timeout_seconds <= 0:
        print("FAIL: --timeout-seconds must be a positive number.", file=sys.stderr)
        return 2
    try:
        audio = args.input.read_bytes()
    except OSError as error:
        print(f"FAIL: cannot read input: {error}", file=sys.stderr)
        return 2
    if not audio:
        print("FAIL: input audio is empty.", file=sys.stderr)
        return 2

    session_id = f"check-latency-{uuid4().hex[:8]}"
    runs: list[dict[str, object]] = []
    with httpx.Client(
        timeout=args.timeout_seconds, trust_env=False, follow_redirects=False,
        transport=transport,
    ) as client:
        for _ in range(args.runs):
            turn_id = f"{session_id}-{uuid4().hex[:12]}"
            started = perf_counter()
            try:
                response = client.post(
                    args.url + "/api/device/turn",
                    data={
                        "device_id": "check-latency",
                        "session_id": session_id,
                        "turn_id": turn_id,
                    },
                    files={"audio": (args.input.name, audio, "audio/wav")},
                )
                state = response.json().get("state") if response.status_code == 200 else None
            except (httpx.HTTPError, ValueError):
                state = None
            elapsed_ms = (perf_counter() - started) * 1000
            runs.append({
                "turn_id": turn_id,
                "state": state,
                "elapsed_ms": round(elapsed_ms, 1),
            })

    elapsed = sorted(float(run["elapsed_ms"]) for run in runs)
    report = {
        "url": args.url,
        "runs": runs,
        "p50_ms": percentile(elapsed, 0.50),
        "p95_ms": percentile(elapsed, 0.95),
    }
    print(json.dumps(report, indent=2))
    if all(run["state"] == "answered" for run in runs):
        print(f"PASS: {args.runs} answered runs recorded; no latency threshold applies.",
              file=sys.stderr)
        return 0
    print("FAIL: at least one run did not complete as answered.", file=sys.stderr)
    return 1


def main() -> int:
    """Parse arguments and run the latency measurement against the real backend."""
    return run_measurement(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
