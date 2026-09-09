# v1.0 | 09-Sep-2026 | Provide the WP2.3 owner checks behind a per-unit check runner.
"""Run the automated owner checks for one work-package unit and tier.

The script is a registry of independent, rerunnable validation checks keyed by
implementation unit and test tier (`A` = deterministic developer checks,
`B` = Mac runtime checks against live local services). Only units registered
here are supported; earlier units keep their existing dedicated scripts.

Currently registered: WP2.3 tier B - MLX/Qwen bounded generation. Reads
`KAKI_LLM_MODE`, `KAKI_LLM_URL` and `KAKI_LLM_TIMEOUT_SECONDS` like the
backend and expects the MLX-LM service on 127.0.0.1:8082 (runbook 7.3).

Side effects: WP2.3 tier B sends five fixed-transcript generation requests to
the local LLM service. Nothing is written to disk. Exit status is zero only
when every check passes; 2 indicates a usage or configuration error.
"""

import argparse
import json
import sys
from time import perf_counter

from kaki_backend.config import APPROVED_QWEN_MODEL, LlmSettings
from kaki_backend.contracts.ports import LlmError

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


REGISTRY = {
    ("WP2.3", "B"): check_wp23_tier_b,
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
