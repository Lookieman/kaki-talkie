#!/usr/bin/env bash
# v1.2 | 14-Sep-2026 | Answered slips: English body named plainly, offending words printed, no You asked: line.
# v1.1 | 13-Sep-2026 | Implement WP5.1: english mode, live Qwen rewrite probe, rewrite and render asserts, voice variant.
# v1.0 | 13-Sep-2026 | Owner evidence harness for runbook 10.2 WP5.1 Tests 1, 2, 3 and 5.
#
# Capture WP5.1 validation evidence on the Mac by running the runbook 10.2
# WP5.1 test block in order: Tests 1, 2, 3 and 5.
#
# This is the owner's evidence harness, not the gate. It asserts the runbook's
# expected observations and stops with a non-zero exit at the first failed
# assertion. scripts/wp_check.py stays the automated gate: the harness records
# what each wp_check run reported, with its exit code. Judgement steps (Test 1
# Malay strings, Test 3 replies) stop and ask the owner, who types yes or no;
# the verdict is written to judgements.txt and a "no" ends the run. Test 4
# belongs to WP5.2: the harness prints that and moves on.
#
# Run it after Implement WP5.1. It depends on the names runbook 10.1 WP5.1
# fixes: language_policy.py, reply_language.py (BRIDGE_GREETING,
# BRIDGE_CLOSING), the ms catalogues in intent_router.py, the three test
# modules and the backend startup line naming the Malay reply mode.
#
# Usage:
#   scripts/wp5_1_evidence.sh [--from-test N]
#   scripts/wp5_1_evidence.sh -h|--help
#
# Options:
#   --from-test N     Start at test N (1, 2, 3 or 5; default 1) and run to the
#                     end. Test 4 is WP5.2 and never runs here. A start at 1,
#                     2 or 3 needs an interactive terminal for the judgements.
# The run header records the start test and the backend's reply mode.
#
# Prerequisites: the grounded stack is running (python scripts/dev_stack.py up)
# from the WP5.1 checkout; the shell has the WP5.1 environment (source
# scripts/kaki_env.sh WP5.1); the four demo sample files exist under
# $WP51_AUDIO when the run starts at Test 3 or earlier (runbook 10.1 WP5.1,
# "Demo sample capture").
#
# Side effects:
#   - Creates $WP51_EVIDENCE (a new directory under $KAKI_DATA_ROOT/wp5.1
#     unless an empty one is already exported); transcript.txt receives the run.
#   - Test 2 loads the embedding model (about 1.2 GB) in-process, reads the
#     Chroma index and sends three rewrite requests to MLX-LM.
#   - Test 3 posts four demo sample turns to the live backend. All are stored
#     in $KAKI_DB, as intended. The demo sample files are read, never changed.
#   - Test 5 runs wp_check.py WP5.1 tier B and the devset regression; both use
#     their own disposable databases and live Qwen. It also runs the
#     deterministic suites.
#   - Plays reply audio through afplay in Test 3.
#   - Does not stop the stack or restart the backend. It prints the commands.
#
# Exit status: 0 when every step ran, every assertion held and every verdict
# was yes; 1 on a failed assertion, failed command or a "no" verdict; 2 on a
# usage or precondition error.

set -Eeuo pipefail

BACKEND_URL="http://127.0.0.1:8000"
SMOKE_DEVICE="wp51-smoke"
CDC_SOURCE_ID="cdc-vouchers-residents"
CARESHIELD_SOURCE_ID="careshield-life"
INTENT_TARGET="0.80"
SCHEMA_SNAPSHOT="backend/tests/contract/snapshots/turn_response.schema.json"
LLM_LOG_PATTERN="POST /v1/chat/completions"
DEMO_FILES="ms_cdc ms_codeswitch en_sg_cdc ms_unsupported"
# Malay words that never belong on an answered slip. The slip body must be
# English whatever the reply language (WP5-AT-01, design.md 9.3); a match
# fails Test 3.
MALAY_MARKERS="saya|anda|boleh|untuk|dengan|dan|yang|ini|itu|tidak|baucar|guna|kedai"
PLANNED_FILES=(
    "backend/src/kaki_backend/orchestration/language_policy.py"
    "backend/src/kaki_backend/orchestration/reply_language.py"
    "agent/data/language_cases.jsonl"
    "backend/tests/unit/test_language_policy.py"
    "backend/tests/unit/test_malay_reply.py"
)

usage() {
    awk 'NR > 5 && /^#/ { sub(/^# ?/, ""); print; next } NR > 5 { exit }' "$0"
}

usage_error() {
    printf '%s\n\n' "$1" >&2
    usage >&2
    exit 2
}

FROM_TEST=1
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --from-test)
            [ "$#" -ge 2 ] || usage_error "--from-test needs a test number."
            FROM_TEST="$2"; shift 2 ;;
        *) usage_error "Unknown argument: $1" ;;
    esac
done
case "$FROM_TEST" in
    1|2|3|5) ;;
    4) usage_error "--from-test 4 is WP5.2's MERaLiON check; this harness does not run it." ;;
    *) usage_error "--from-test must be 1, 2, 3 or 5, got: $FROM_TEST" ;;
esac
readonly FROM_TEST

precondition() {
    printf 'PRECONDITION FAILED: %s\n' "$1" >&2
    printf 'Fix: %s\n' "$2" >&2
    exit 2
}

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

trap 'printf "FAIL: command exited non-zero at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

KAKI_APP_ROOT="${KAKI_APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$KAKI_APP_ROOT"

has_tty() {
    { : </dev/tty; } 2>/dev/null
}

# ---------------------------------------------------------------------------
# Preconditions, checked before any evidence is written.
# ---------------------------------------------------------------------------

case "${KAKI_DATA_ROOT:-}" in
    /*) ;;
    "") precondition "KAKI_DATA_ROOT is unset." "source scripts/kaki_env.sh WP5.1" ;;
    *) precondition "KAKI_DATA_ROOT is not absolute: $KAKI_DATA_ROOT" \
           "export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data" ;;
esac
KAKI_DB="${KAKI_DB:-${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}}"
WP51_AUDIO="${WP51_AUDIO:-$KAKI_DATA_ROOT/wp5.1/audio}"
LLM_LOG="$KAKI_DATA_ROOT/logs/llm.log"
BACKEND_LOG="$KAKI_DATA_ROOT/logs/backend.log"
EVIDENCE_MIN_DENSE="${KAKI_EVIDENCE_MIN_DENSE:-0.50}"
readonly KAKI_DB WP51_AUDIO LLM_LOG BACKEND_LOG EVIDENCE_MIN_DENSE

for tool in jq sqlite3 uuidgen curl afplay base64 git say; do
    command -v "$tool" >/dev/null || precondition "$tool is not on PATH." \
        "install $tool (setup.md 5.2); macOS provides afplay, uuidgen and say"
done

for path in "${PLANNED_FILES[@]}"; do
    [ -f "$KAKI_APP_ROOT/$path" ] || precondition "$path is missing." \
        "run this harness after Implement WP5.1, from the WP5.1 checkout"
done

python -c "import kaki_backend" 2>/dev/null || precondition "python cannot import kaki_backend." \
    "source \"$KAKI_APP_ROOT/.venv/bin/activate\""

[ -f "$KAKI_DB" ] || precondition "the database is missing: $KAKI_DB" \
    "python scripts/dev_stack.py up  (the backend creates the database at start)"

curl --fail --silent --max-time 10 "$BACKEND_URL/api/health" >/dev/null || precondition \
    "the backend is not answering on 127.0.0.1:8000." \
    "python scripts/dev_stack.py up  then  python scripts/dev_stack.py status"

for setting in KAKI_RETRIEVAL_MODE=rag KAKI_LLM_MODE=qwen KAKI_TTS_MODE=say KAKI_STT_MODE=whisper; do
    name="${setting%%=*}"
    wanted="${setting#*=}"
    actual="${!name:-}"
    [ "$actual" = "$wanted" ] || precondition "$name is '${actual:-unset}', expected '$wanted'." \
        "source scripts/kaki_env.sh WP5.1"
done

for log in "$LLM_LOG" "$BACKEND_LOG"; do
    [ -f "$log" ] || precondition "log not found: $log" \
        "start the stack with python scripts/dev_stack.py up, which writes the service logs"
done

BACKEND_REPLY_MODE="$(sed -n 's/.*Malay reply mode \([a-z]*\),.*/\1/p' "$BACKEND_LOG" | tail -1)"
BACKEND_MALAY_VOICE="$(sed -n 's/.*Malay voice \(.*\)$/\1/p' "$BACKEND_LOG" | tail -1)"
case "$BACKEND_REPLY_MODE" in
    full|bridge|english) ;;
    *) precondition "backend.log has no WP5.1 startup line naming the Malay reply mode." \
           "restart the backend from the WP5.1 checkout: python scripts/dev_stack.py down --only backend; python scripts/dev_stack.py up --only backend" ;;
esac
if [ -n "${KAKI_MALAY_REPLY_MODE:-}" ] && [ "$KAKI_MALAY_REPLY_MODE" != "$BACKEND_REPLY_MODE" ]; then
    precondition "the shell exports KAKI_MALAY_REPLY_MODE=$KAKI_MALAY_REPLY_MODE but the backend runs $BACKEND_REPLY_MODE." \
        "restart the backend from this shell: python scripts/dev_stack.py down --only backend; python scripts/dev_stack.py up --only backend"
fi
readonly BACKEND_REPLY_MODE BACKEND_MALAY_VOICE

if [ "$FROM_TEST" -le 3 ]; then
    has_tty || precondition "no interactive terminal; Tests 1 and 3 have owner judgement steps." \
        "run scripts/wp5_1_evidence.sh from Terminal, not through a pipe"
    for name in $DEMO_FILES; do
        [ -s "$WP51_AUDIO/$name.wav" ] || precondition "the demo sample file $WP51_AUDIO/$name.wav is missing." \
            "record it (runbook 10.1 WP5.1, \"Demo sample capture\")"
    done
fi

# ---------------------------------------------------------------------------
# Evidence directory, run header, transcript.
# ---------------------------------------------------------------------------

umask 077
if [ -n "${WP51_EVIDENCE:-}" ]; then
    [ -d "$WP51_EVIDENCE" ] || precondition "WP51_EVIDENCE does not exist: $WP51_EVIDENCE" \
        "unset WP51_EVIDENCE to let the harness create a new directory"
    [ -z "$(ls -A "$WP51_EVIDENCE")" ] || precondition \
        "WP51_EVIDENCE already holds evidence: $WP51_EVIDENCE" \
        "source scripts/kaki_env.sh WP5.1 again, or unset WP51_EVIDENCE"
else
    mkdir -p "$KAKI_DATA_ROOT/wp5.1"
    WP51_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp5.1/evidence.XXXXXX")"
fi
readonly WP51_EVIDENCE
export WP51_EVIDENCE KAKI_APP_ROOT

header_item() {
    local label="$1" output
    shift
    if output="$("$@" 2>&1)"; then
        printf '%s:\n%s\n\n' "$label" "$output"
    else
        printf '%s:\nunavailable (%s)\n\n' "$label" "$output"
    fi
}

{
    printf 'KaKi-Talkie WP5.1 evidence run header\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    header_item "git uncommitted changes" git -C "$KAKI_APP_ROOT" status --short
    printf 'harness start test: %s (tests before it did not run)\n' "$FROM_TEST"
    printf 'backend Malay reply mode: %s\nbackend Malay voice: %s\n\n' "$BACKEND_REPLY_MODE" "$BACKEND_MALAY_VOICE"
    printf 'KAKI_APP_ROOT: %s\nKAKI_DATA_ROOT: %s\nKAKI_DB: %s\nWP51_AUDIO: %s\nWP51_EVIDENCE: %s\n' \
        "$KAKI_APP_ROOT" "$KAKI_DATA_ROOT" "$KAKI_DB" "$WP51_AUDIO" "$WP51_EVIDENCE"
    printf 'KAKI_EVIDENCE_MIN_DENSE: %s\nKAKI_LANGUAGE_PREFERENCE: %s\nKAKI_TTS_VOICE_MS: %s\n\n' \
        "$EVIDENCE_MIN_DENSE" "${KAKI_LANGUAGE_PREFERENCE:-unset}" "${KAKI_TTS_VOICE_MS:-unset}"
    header_item "backend language startup line" sh -c "grep 'Malay reply mode' '$BACKEND_LOG' | tail -1"
    header_item "installed Malay and Indonesian voices" sh -c "say -v '?' | grep -Ei 'ms_MY|id_ID'"
    header_item "macOS version" sw_vers -productVersion
    header_item "python" python --version
    header_item "backend health" curl --fail --silent --max-time 30 "$BACKEND_URL/api/health"
} > "$WP51_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP51_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP51_EVIDENCE"
printf 'Demo sample: %s\n' "$WP51_AUDIO"
printf 'Start test: %s; backend Malay reply mode: %s\n' "$FROM_TEST" "$BACKEND_REPLY_MODE"

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

section() {
    printf '\n=== %s\n' "$*"
}

check() {
    if [ "$2" != "$3" ]; then
        fail "$1: expected '$3', got '$2'"
    fi
    printf 'check ok: %s = %s\n' "$1" "$2"
}

check_true() {
    check "$1" "$(if eval "$2"; then echo true; else echo false; fi)" "true"
}

observe() {
    printf 'observation: %s = %s\n' "$1" "$2"
    printf '%s = %s\n' "$1" "$2" >> "$WP51_EVIDENCE/observations.txt"
}

# Ask the owner; a "no" fails the run with the optional hint.
judge() {
    local step="$1" question="$2" hint="${3:-}" answer="" note=""
    printf '\nJUDGEMENT %s: %s\n' "$step" "$question"
    while [ "$answer" != "yes" ] && [ "$answer" != "no" ]; do
        read -r -p 'Type yes or no: ' answer </dev/tty
    done
    while :; do
        read -r -p 'Note (required for no): ' note </dev/tty
        [ "$answer" = "yes" ] || [ -n "$note" ] && break
    done
    printf '%s | %s | verdict=%s | note=%s | question=%s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$step" "$answer" "${note:-none}" "$question" \
        >> "$WP51_EVIDENCE/judgements.txt"
    printf 'owner verdict recorded for %s: %s\n' "$step" "$answer"
    if [ "$answer" != "yes" ]; then
        [ -z "$hint" ] || printf '%s\n' "$hint"
        fail "owner verdict no for $step: $note"
    fi
}

live_sql() {
    sqlite3 "$KAKI_DB" "$1"
}

new_uuid() {
    uuidgen | tr '[:upper:]' '[:lower:]'
}

llm_count() {
    sleep 1
    grep -c "$LLM_LOG_PATTERN" "$LLM_LOG" || true
}

field() {
    jq -r "$2" "$WP51_EVIDENCE/$1.json"
}

# Print a Python expression's value from the backend package.
backend_value() {
    python -c "$1"
}

run_suite() {
    local name="$1" rc=0
    shift
    local output_file="$WP51_EVIDENCE/tier_a_${name}.txt"
    (cd "$KAKI_APP_ROOT" && "$@") >"$output_file" 2>&1 || rc=$?
    cat "$output_file"
    printf 'tier A %s exit code: %s\n' "$name" "$rc"
    [ "$rc" -eq 0 ] || fail "tier A $name exited $rc; see $output_file"
}

ran_count() {
    grep -Eo '^Ran [0-9]+ tests?' "$WP51_EVIDENCE/tier_a_$1.txt" | awk '{print $2}' | tail -1
}

check_ran() {
    local count
    count="$(ran_count "$1")"
    observe "tier_a_${1}_tests_ran" "${count:-0}"
    check_true "$1 ran more than zero tests" '[ "${count:-0}" -gt 0 ]'
}

run_wp_check() {
    local unit="$1" tag rc=0
    tag="$(printf '%s' "$unit" | tr -d '.' | tr '[:upper:]' '[:lower:]')"
    local stdout_file="$WP51_EVIDENCE/wp_check_${tag}_tierB.json"
    local stderr_file="$WP51_EVIDENCE/wp_check_${tag}_tierB.stderr.txt"
    python scripts/wp_check.py --unit "$unit" --tier B >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$WP51_EVIDENCE/wp_check_${tag}_tierB.exit.txt"
    cat "$stdout_file" "$stderr_file"
    printf 'wp_check %s tier B exit code: %s (as reported by wp_check)\n' "$unit" "$rc"
    [ "$rc" -eq 0 ] || fail "wp_check $unit tier B exited $rc; see $stderr_file"
}

# The gate input: the best dense_* path score across the returned chunks.
gate_value() {
    jq -r '[.results[].path_scores | to_entries[] | select(.key | startswith("dense_")) | .value] | max // 0' "$1"
}

at_least() {
    awk -v value="$1" -v floor="$2" 'BEGIN { print (value + 0 >= floor + 0) ? "true" : "false" }'
}

# POST one demo sample file; write <tag>.json and debug_<tag>.json.
post_turn() {
    local tag="$1" audio="$2" seconds
    seconds="$(curl --fail --silent --show-error --max-time 300 "$BACKEND_URL/api/device/turn" \
        -F "device_id=$SMOKE_DEVICE" -F "session_id=wp51-session-$(new_uuid)" \
        -F "turn_id=wp51-$tag-$(new_uuid)" \
        -F "audio=@$audio" -o "$WP51_EVIDENCE/$tag.json" -w '%{time_total}')" \
        || fail "POST /api/device/turn ($tag) failed"
    curl --fail --silent "$BACKEND_URL/api/device/debug/last-turn" -o "$WP51_EVIDENCE/debug_$tag.json" \
        || fail "GET /api/device/debug/last-turn after $tag failed"
    observe "${tag}_elapsed_seconds" "$seconds"
    observe "${tag}_transcript" "$(field "debug_$tag" .transcript)"
    observe "${tag}_language_evidence" "$(jq -c .language_evidence "$WP51_EVIDENCE/debug_$tag.json")"
    observe "${tag}_normalised_query" "$(field "debug_$tag" .normalised_query)"
    observe "${tag}_query_rewrite_ms" "$(field "debug_$tag" .timings_ms.query_rewrite_ms)"
    observe "${tag}_llm_ms" "$(field "debug_$tag" .timings_ms.llm_ms)"
}

# Decode reply_audio to <tag>_reply.wav; fail when absent.
save_audio() {
    jq -r '.reply_audio // empty' "$WP51_EVIDENCE/$1.json" \
        | sed 's#^data:audio/wav;base64,##' | base64 -D > "$WP51_EVIDENCE/$1_reply.wav"
    [ -s "$WP51_EVIDENCE/$1_reply.wav" ] || fail "$1 carries no reply audio"
}

show_turn() {
    printf '\n--- %s\nreply_text:\n%s\n\ndisplay_text:\n%s\n\nslip_text:\n%s\n' "$1" \
        "$(field "$1" .reply_text)" "$(field "$1" .display_text)" "$(field "$1" .slip_text)"
}

# Record which Malay voice variant survived the setup.md 10.1.1 SSH check.
record_voice_variant() {
    local choice="" variant=""
    printf '\nVOICE VARIANT (setup.md 10.1.1): which Malay voice survived the service-context (SSH) check?\n'
    printf '  1) Amira, enhanced\n  2) Amira, compact\n  3) Damayanti (fallback)\n'
    while :; do
        read -r -p 'Type 1, 2 or 3: ' choice </dev/tty
        case "$choice" in
            1) variant="Amira enhanced"; break ;;
            2) variant="Amira compact"; break ;;
            3) variant="Damayanti"; break ;;
        esac
    done
    observe "malay_voice_variant" "$variant"
    printf '%s | voice-variant | %s | backend voice=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$variant" "$BACKEND_MALAY_VOICE" >> "$WP51_EVIDENCE/judgements.txt"
    check "backend Malay voice matches the recorded variant" "$BACKEND_MALAY_VOICE" "${variant%% *}"
}

# An answered slip is English whatever the reply language. Its body is every
# line between the heading and the "Source:" line. It carries no transcript,
# so it has no "You asked:" line; only the referral slip does.  #v1.2
check_english_slip() {
    local slip body malay_words
    slip="$(field "$1" .slip_text)"
    check "$1 slip heading" "$(printf '%s\n' "$slip" | head -1)" "KAKI-TALKIE HELP"
    check_true "$1 slip carries Source checked:" 'printf "%s" "$slip" | grep -q "Source checked:"'
    body="$(printf '%s\n' "$slip" | sed -n '2,$p' | sed '/^Source: /,$d')"
    printf '%s\n' "$body" > "$WP51_EVIDENCE/${1}_slip_body.txt"
    # No steps means the grounded answer stayed non-English after its retry.
    observe "${1}_slip_body_lines" "$(printf '%s\n' "$body" | grep -c . || true)"
    malay_words="$(printf '%s\n' "$body" | grep -Eiwo "$MALAY_MARKERS" | tr '[:upper:]' '[:lower:]' \
        | sort -u | paste -sd, - || true)"
    check "$1 slip body is English: Malay words found" "${malay_words:-none}" "none"
    check_true "$1 answered slip has no You asked: line" \
        '! printf "%s\n" "$slip" | grep -qx "You asked:"'
}

# ---------------------------------------------------------------------------
# Tests, one function each. The dispatcher at the end honours --from-test.
# ---------------------------------------------------------------------------

# Test 1: language policy, turn shape and speech language (WP5-AT-01, 02).
test1_language_policy() {
    section "Test 1: language policy (WP5-AT-01, WP5-AT-02)"
    run_suite language_policy python -m unittest discover -s backend/tests/unit -p 'test_language_policy.py' -v
    run_suite malay_reply python -m unittest discover -s backend/tests/unit -p 'test_malay_reply.py' -v
    run_suite say_adapter python -m unittest discover -s backend/tests/unit -p 'test_say_adapter.py' -v
    check_ran language_policy
    check_ran malay_reply
    check_ran say_adapter
    observe "test1_language_cases" "$(grep -c . agent/data/language_cases.jsonl)"

    python - > "$WP51_EVIDENCE/malay_fixed_strings.txt" <<'PY'
from kaki_backend.orchestration.intent_router import ACTION_MESSAGES, REFUSAL_MESSAGES
from kaki_backend.orchestration.reply_language import BRIDGE_CLOSING, BRIDGE_GREETING

for catalogue in (REFUSAL_MESSAGES, ACTION_MESSAGES):
    for kind, message in catalogue["ms"].items():
        print(f"{kind.value}\n  reply:   {message.reply_text}\n  display: {message.display_text}")
print(f"bridge greeting\n  {BRIDGE_GREETING}")
print(f"bridge closing\n  {BRIDGE_CLOSING}")
PY
    cat "$WP51_EVIDENCE/malay_fixed_strings.txt"
    judge "test1-malay-strings" "Are these fixed Malay strings correct, calm Malay?"
}

# Test 2: Malay retrieval through the existing retriever (WP5-AT-04).
test2_malay_retrieval() {
    section "Test 2: Malay retrieval (WP5-AT-04)"
    run_suite rag_adapter python -m unittest discover -s rag/tests -p 'test_adapter.py' -v
    run_suite refusal_pipeline python -m unittest discover -s backend/tests/unit -p 'test_refusal_pipeline.py' -v
    check_ran rag_adapter
    check_ran refusal_pipeline

    # Real index and live rewrite: the wp_check probe measures each question
    # original-only, with the curated English query and with the Qwen rewrite.
    local probes="$WP51_EVIDENCE/probe_retrieval.json" number near
    python - > "$probes" 2> "$WP51_EVIDENCE/probe_retrieval.stderr.txt" <<'PY' \
        || fail "the Malay retrieval probe failed; see probe_retrieval.stderr.txt"
import json
import sys

sys.path.insert(0, "scripts")
import wp_check  # noqa: E402
from kaki_backend.config import RetrievalSettings  # noqa: E402

report, checks = wp_check._wp51_retrieval(RetrievalSettings.from_environment().evidence_min_dense)
print(json.dumps({"report": report, "checks": checks}, indent=2, ensure_ascii=False))
PY
    cat "$WP51_EVIDENCE/probe_retrieval.stderr.txt"
    for number in 1 2 3; do
        observe "test2_probe${number}_question" "$(jq -r ".report.probes[$((number - 1))].question" "$probes")"
        observe "test2_probe${number}_qwen_rewrite" "$(jq -r ".report.probes[$((number - 1))].qwen_rewrite" "$probes")"
        observe "test2_probe${number}_rewrite_ms" "$(jq -r ".report.probes[$((number - 1))].rewrite_ms" "$probes")"
        observe "test2_probe${number}_gate_values" "$(jq -c ".report.probes[$((number - 1))].gate_values" "$probes")"
        observe "test2_probe${number}_qwen_margin_over_gate" "$(jq -r ".report.probes[$((number - 1))].qwen_margin_over_gate" "$probes")"
    done
    jq -r '.checks | to_entries[] | "\(.key) = \(.value)"' "$probes"
    check "every Malay retrieval probe check passed" "$(jq -r '.checks | all' "$probes")" "true"
    near="$(jq -c '.report.near_gate_questions' "$probes")"
    observe "test2_near_gate_questions" "$near"
    if [ "$near" != "[]" ]; then
        printf 'NOTE: a Qwen-rewrite gate value sits within %s of the gate. Report it to the owner as a decision.\n' \
            "$(jq -r '.report.near_gate_margin' "$probes")"
    fi
}

# Test 3: live Malay turns on the demo sample (WP5-AT-03; live AT-01, AT-04).
test3_live_turns() {
    section "Test 3: live Malay turns (backend reply mode $BACKEND_REPLY_MODE)"
    observe "test3_reply_mode" "$BACKEND_REPLY_MODE"
    local greeting closing no_coverage_ms before after reply
    greeting="$(backend_value 'from kaki_backend.orchestration.reply_language import BRIDGE_GREETING; print(BRIDGE_GREETING)')"
    closing="$(backend_value 'from kaki_backend.orchestration.reply_language import BRIDGE_CLOSING; print(BRIDGE_CLOSING)')"
    no_coverage_ms="$(backend_value 'from kaki_backend.orchestration.intent_router import RefusalReason, refusal_message; print(refusal_message(RefusalReason.NO_COVERAGE, "ms").reply_text)')"
    [ -n "$greeting" ] && [ -n "$closing" ] || fail "BRIDGE_GREETING or BRIDGE_CLOSING is empty"
    local malay_language="ms"
    [ "$BACKEND_REPLY_MODE" != "english" ] || malay_language="en"
    [ "$BACKEND_REPLY_MODE" != "english" ] || no_coverage_ms="$(backend_value 'from kaki_backend.orchestration.intent_router import RefusalReason, refusal_message; print(refusal_message(RefusalReason.NO_COVERAGE, "en").reply_text)')"

    for name in $DEMO_FILES; do
        before="$(llm_count)"
        post_turn "$name" "$WP51_AUDIO/$name.wav"
        after="$(llm_count)"
        observe "${name}_llm_completions" "$((after - before))"
        save_audio "$name"
    done

    printf '\nms_cdc\n'
    check "ms_cdc state" "$(field ms_cdc .state)" "answered"
    check "ms_cdc language" "$(field ms_cdc .language)" "$malay_language"
    check "ms_cdc debug reply_language" "$(field debug_ms_cdc .reply_language)" "ms"
    check "ms_cdc debug reply_mode" "$(field debug_ms_cdc .reply_mode)" "$BACKEND_REPLY_MODE"
    check "ms_cdc cited_source_id" "$(field debug_ms_cdc .cited_source_id)" "$CDC_SOURCE_ID"
    check "ms_cdc rewrite_present" "$(field debug_ms_cdc .rewrite_present)" "true"
    observe "ms_cdc_rewrite_ms" "$(field debug_ms_cdc .rewrite_ms)"
    check "ms_cdc best_dense_score >= evidence_min_dense" \
        "$(jq -r '.best_dense_score != null and .best_dense_score >= .evidence_min_dense' "$WP51_EVIDENCE/debug_ms_cdc.json")" "true"
    check_english_slip ms_cdc
    reply="$(field ms_cdc .reply_text)"
    observe "ms_cdc_render_outcome" "$(field debug_ms_cdc .render_outcome)"
    case "$BACKEND_REPLY_MODE" in
        full)
            check "ms_cdc render_outcome (a fallback means the Malay render was rejected)" \
                "$(field debug_ms_cdc .render_outcome)" "rendered" ;;
        bridge)
            check_true "ms_cdc bridge reply starts with BRIDGE_GREETING" '[[ "$reply" == "$greeting"* ]]'
            check_true "ms_cdc bridge reply ends with BRIDGE_CLOSING" '[[ "$reply" == *"$closing" ]]' ;;
        english)
            check "ms_cdc render_outcome" "$(field debug_ms_cdc .render_outcome)" "null" ;;
    esac

    printf '\nms_codeswitch\n'
    check "ms_codeswitch state" "$(field ms_codeswitch .state)" "answered"
    check "ms_codeswitch language" "$(field ms_codeswitch .language)" "$malay_language"
    check "ms_codeswitch debug reply_language" "$(field debug_ms_codeswitch .reply_language)" "ms"
    check "ms_codeswitch cited_source_id" "$(field debug_ms_codeswitch .cited_source_id)" "$CARESHIELD_SOURCE_ID"
    check "ms_codeswitch rewrite_present" "$(field debug_ms_codeswitch .rewrite_present)" "true"
    [ "$BACKEND_REPLY_MODE" != "full" ] || check "ms_codeswitch render_outcome" \
        "$(field debug_ms_codeswitch .render_outcome)" "rendered"
    check_english_slip ms_codeswitch

    printf '\nen_sg_cdc\n'
    check "en_sg_cdc state" "$(field en_sg_cdc .state)" "answered"
    check "en_sg_cdc language" "$(field en_sg_cdc .language)" "en"
    check "en_sg_cdc cited_source_id" "$(field debug_en_sg_cdc .cited_source_id)" "$CDC_SOURCE_ID"
    reply="$(field en_sg_cdc .reply_text)"
    check_true "en_sg_cdc reply does not start with BRIDGE_GREETING" '[[ "$reply" != "$greeting"* ]]'
    observe "en_sg_cdc_particle_count" "$(printf '%s' "$reply" | grep -Eiwo 'lah|leh|lor' | wc -l | tr -d ' ')"

    printf '\nms_unsupported\n'
    check "ms_unsupported state" "$(field ms_unsupported .state)" "refused"
    check "ms_unsupported language" "$(field ms_unsupported .language)" "$malay_language"
    check "ms_unsupported refusal_reason" "$(field debug_ms_unsupported .refusal_reason)" "no_coverage"
    check "ms_unsupported reply_text is the ms no-coverage string" "$(field ms_unsupported .reply_text)" "$no_coverage_ms"
    check "ms_unsupported slip heading" "$(field ms_unsupported .slip_text | head -1)" "KAKI-TALKIE REFERRAL"
    check_true "ms_unsupported slip keeps the You asked: line" 'field ms_unsupported .slip_text | grep -qx "You asked:"'
    check "ms_unsupported slip text is Latin-1" "$(python -c 'import json, sys; text = json.load(open(sys.argv[1]))["slip_text"]; print(all(ord(c) <= 255 for c in text))' "$WP51_EVIDENCE/ms_unsupported.json")" "True"

    show_turn ms_cdc
    afplay "$WP51_EVIDENCE/ms_cdc_reply.wav"
    case "$BACKEND_REPLY_MODE" in
        full)
            judge "test3-q1-malay-reply-full" "Is this understandable, natural Malay a senior would follow?" \
                "For demo-day insurance: export KAKI_MALAY_REPLY_MODE=bridge (or english); python scripts/dev_stack.py down --only backend; python scripts/dev_stack.py up --only backend; scripts/wp5_1_evidence.sh --from-test 3. WP5-AT-01 passes in full mode only." ;;
        bridge)
            judge "test3-q1-malay-reply-bridge" "Is the English answer with a Malay greeting and closing acceptable as demo-day insurance?" ;;
        english)
            judge "test3-q1-english-reply" "Is the English answer acceptable as demo-day insurance?" ;;
    esac
    show_turn ms_codeswitch
    afplay "$WP51_EVIDENCE/ms_codeswitch_reply.wav"
    judge "test3-q2-malay-voice" "Is the Malay voice ($BACKEND_MALAY_VOICE) intelligible?"
    record_voice_variant
    show_turn en_sg_cdc
    afplay "$WP51_EVIDENCE/en_sg_cdc_reply.wav"
    judge "test3-q3-sg-english" "Does the Singapore English sound natural, not caricatured? (WP5-AT-03)"
    show_turn ms_unsupported
    afplay "$WP51_EVIDENCE/ms_unsupported_reply.wav"
    judge "test3-q4-malay-refusal" "Is the Malay refusal calm and clear?"
    printf '\nRecord the reply mode and voice variant under "Reply mode selection" in runbook 10.2 WP5.1.\n'
}

# Test 4: WP5.2's check; not run here.
test4_not_in_wp51() {
    section "Test 4: MERaLiON viability belongs to WP5.2"
    printf 'This harness does not run Test 4.\n'
    observe "test4" "belongs to WP5.2; not run by the WP5.1 harness"
}

# Test 5: regression (WP5-AT-12).
test5_regression() {
    section "Test 5: regression (WP5-AT-12)"
    run_wp_check WP5.1

    local regression_rc=0 report id
    python scripts/run_regression.py --devset agent/data/devset.jsonl \
        > "$WP51_EVIDENCE/regression_devset.json" 2> "$WP51_EVIDENCE/regression_devset.stderr.txt" \
        || regression_rc=$?
    cat "$WP51_EVIDENCE/regression_devset.stderr.txt"
    printf 'run_regression.py exit code: %s (as reported by the runner)\n' "$regression_rc"
    check "run_regression.py exit code" "$regression_rc" "0"
    report="$WP51_EVIDENCE/regression_devset.json"
    observe "test5_items" "$(jq -r .items "$report")"
    observe "test5_intent_accuracy" "$(jq -r .intent_accuracy "$report")"
    check "intent_accuracy >= $INTENT_TARGET" "$(jq -r ".intent_accuracy >= $INTENT_TARGET" "$report")" "true"
    check "golden paths passed equals total" "$(jq -r .golden_paths_passed "$report")" "$(jq -r .golden_paths_total "$report")"
    for id in singpass-ms careshield-codeswitch; do
        check "devset item $id passed" "$(jq -r --arg id "$id" '.results[] | select(.id == $id) | .passed' "$report")" "true"
    done

    section "Test 5: deterministic suites"
    local turns_before_suites tracked_runtime
    turns_before_suites="$(live_sql 'select count(*) from turns;')"
    run_suite ruff python -m ruff check --config backend/pyproject.toml backend scripts services rag
    run_suite contract python -m unittest discover -s backend/tests/contract -v
    run_suite unit python -m unittest discover -s backend/tests/unit -v
    run_suite rag python -m unittest discover -s rag/tests -v
    run_suite scripts python -m unittest discover -s scripts/tests -v
    for suite in contract unit rag scripts; do
        observe "test5_${suite}_tests_ran" "$(ran_count "$suite")"
    done
    check_true "WP1 turn schema snapshot test passed" \
        'grep -q "test_turn_response_schema_matches_snapshot .* ok" "$WP51_EVIDENCE/tier_a_contract.txt"'
    check "WP1 turn schema snapshot file unchanged from HEAD (X-AT-01)" \
        "$(git -C "$KAKI_APP_ROOT" status --porcelain -- "$SCHEMA_SNAPSHOT")" ""
    tracked_runtime="$(git -C "$KAKI_APP_ROOT" ls-files | grep -E '\.db$|\.db-wal$|\.db-shm$|(^|/)chroma/' || true)"
    printf '%s\n' "$tracked_runtime" > "$WP51_EVIDENCE/tracked_runtime_files.txt"
    check "tracked *.db, *.db-wal, *.db-shm or chroma/ paths (X-AT-03)" "$tracked_runtime" ""
    check "live turns unchanged by the deterministic suites" \
        "$(live_sql 'select count(*) from turns;')" "$turns_before_suites"
    printf 'The web suite does not run: WP5.1 changes no web code.\n'
}

# Teardown: printed, not run.
teardown() {
    section "Teardown"
    printf 'The stack is still running. Stop it when you are done:\n'
    printf '  python scripts/dev_stack.py down\n'
    printf 'Keep the demo sample until WP5.2 has used it: %s\n\n' "$WP51_AUDIO"
    printf 'Harness finished with no failed assertion and no "no" verdict. This is evidence,\n'
    printf 'not the WP5.1 sign-off: review it, record the reply mode in runbook 10.2 WP5.1,\n'
    printf 'then mark the block VERIFIED yourself.\n'
    printf 'Evidence: %s\n' "$WP51_EVIDENCE"
}

# ---------------------------------------------------------------------------
# Run from the requested test to the end.
# ---------------------------------------------------------------------------

[ "$FROM_TEST" -gt 1 ] || test1_language_policy
[ "$FROM_TEST" -gt 2 ] || test2_malay_retrieval
[ "$FROM_TEST" -gt 3 ] || test3_live_turns
[ "$FROM_TEST" -gt 4 ] || test4_not_in_wp51
test5_regression
teardown
