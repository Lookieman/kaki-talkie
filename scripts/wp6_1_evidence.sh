#!/usr/bin/env bash
# v1.0 | 16-Sep-2026 | Owner evidence harness for runbook 11.2 WP6.1 Tests 1-4.
#
# Capture WP6.1 validation evidence on the Mac by running the runbook 11.2
# WP6.1 test block in order: Tests 1-4.
#
# This is the owner's evidence harness, not the gate. It asserts the runbook's
# expected observations and stops with a non-zero exit at the first failed
# assertion. scripts/wp_check.py stays the automated gate: the harness records
# what each wp_check run reported, with its exit code. The judgement step
# (Test 3, the frames a user would see) stops and asks the owner, who types
# yes or no; the verdict is written to judgements.txt and a "no" ends the run.
#
# WP6.1 ships mock I/O only, so every step here runs on the Mac with no Pi, no
# button, no microphone and no printer. Tests 2 and 3 need the grounded stack
# because the device posts real turns to it.
#
# Usage:
#   scripts/wp6_1_evidence.sh [--from-test N]
#   scripts/wp6_1_evidence.sh -h|--help
#
# Options:
#   --from-test N     Start at test N (1-4, default 1) and run to the end.
#                     A start at 3 or earlier needs an interactive terminal
#                     for the owner judgement.
#
# Prerequisites: the device package is installed (python -m pip install -e
# device); the shell has the WP6.1 environment (source scripts/kaki_env.sh
# WP6.1); for Tests 2 and 3 the grounded stack is running (python
# scripts/dev_stack.py up) and the committed spoken fixture exists.
#
# Side effects:
#   - Creates $WP61_EVIDENCE (a new directory under $KAKI_DATA_ROOT/wp6.1
#     unless an empty one is already exported); transcript.txt receives the run.
#   - Test 2 and Test 3 post device turns to the live backend, which stores
#     them in $KAKI_DB as any device turn would. Each uses its own device_id.
#   - Writes a slip log under $WP61_EVIDENCE instead of printing (WP6.3 brings
#     the printer).
#   - Runs the deterministic device suite and the thin-client inspection.
#   - Does not stop the stack. It prints the teardown command instead.
#
# Exit status: 0 when every step ran, every assertion held and every verdict
# was yes; 1 on a failed assertion, failed command or a "no" verdict; 2 on a
# usage or precondition error.

set -Eeuo pipefail

BACKEND_URL="http://127.0.0.1:8000"
FIXTURE_RELATIVE="backend/src/kaki_backend/fixtures/cdc_question.wav"
CDC_HOST="vouchers.cdc.gov.sg"

usage() {
    awk 'NR > 2 && /^#/ { sub(/^# ?/, ""); print; next } NR > 2 { exit }' "$0"
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
    1|2|3|4) ;;
    *) usage_error "--from-test must be 1 to 4, got: $FROM_TEST" ;;
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
FIXTURE="$KAKI_APP_ROOT/$FIXTURE_RELATIVE"

has_tty() {
    { : </dev/tty; } 2>/dev/null
}

# ---------------------------------------------------------------------------
# Preconditions, checked before any evidence is written.
# ---------------------------------------------------------------------------

case "${KAKI_DATA_ROOT:-}" in
    /*) ;;
    "") precondition "KAKI_DATA_ROOT is unset." "source scripts/kaki_env.sh WP6.1" ;;
    *) precondition "KAKI_DATA_ROOT is not absolute: $KAKI_DATA_ROOT" \
           "export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data" ;;
esac

for tool in jq curl python git; do
    command -v "$tool" >/dev/null || precondition "$tool is not on PATH." \
        "install $tool (setup.md 5.2)"
done

python -c "import kaki_device" 2>/dev/null || precondition \
    "python cannot import kaki_device." \
    "python -m pip install -e device  (from $KAKI_APP_ROOT)"

[ -s "$FIXTURE" ] || precondition "the spoken fixture is missing: $FIXTURE_RELATIVE" \
    "restore it from Git; fixtures are committed (runbook 8.1 WP3.3)"

if [ "$FROM_TEST" -le 3 ]; then
    has_tty || precondition "no interactive terminal; Test 3 has an owner judgement step." \
        "run scripts/wp6_1_evidence.sh from Terminal, not through a pipe"
fi

if [ "$FROM_TEST" -le 3 ]; then
    curl --fail --silent --max-time 10 "$BACKEND_URL/api/health" >/dev/null || precondition \
        "the backend is not answering on 127.0.0.1:8000." \
        "python scripts/dev_stack.py up  then  python scripts/dev_stack.py status"
fi

# ---------------------------------------------------------------------------
# Evidence directory, run header, transcript.
# ---------------------------------------------------------------------------

umask 077
if [ -n "${WP61_EVIDENCE:-}" ]; then
    [ -d "$WP61_EVIDENCE" ] || precondition "WP61_EVIDENCE does not exist: $WP61_EVIDENCE" \
        "unset WP61_EVIDENCE to let the harness create a new directory"
    [ -z "$(ls -A "$WP61_EVIDENCE")" ] || precondition \
        "WP61_EVIDENCE already holds evidence: $WP61_EVIDENCE" \
        "source scripts/kaki_env.sh WP6.1 again, or unset WP61_EVIDENCE"
else
    mkdir -p "$KAKI_DATA_ROOT/wp6.1"
    WP61_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp6.1/evidence.XXXXXX")"
fi
readonly WP61_EVIDENCE
export WP61_EVIDENCE KAKI_APP_ROOT
SLIP_LOG="$WP61_EVIDENCE/slips.log"

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
    printf 'KaKi-Talkie WP6.1 evidence run header\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    header_item "git uncommitted changes" git -C "$KAKI_APP_ROOT" status --short
    printf 'harness start test: %s (tests before it did not run)\n\n' "$FROM_TEST"
    printf 'KAKI_APP_ROOT: %s\nKAKI_DATA_ROOT: %s\nWP61_EVIDENCE: %s\n\n' \
        "$KAKI_APP_ROOT" "$KAKI_DATA_ROOT" "$WP61_EVIDENCE"
    header_item "python" python --version
    header_item "kaki-device version" python -c \
        "import importlib.metadata as m; print(m.version('kaki-device'))"
    header_item "pygame (optional display extra)" python -c \
        "import pygame; print(pygame.version.ver)"
    header_item "backend health" curl --fail --silent --max-time 30 "$BACKEND_URL/api/health"
} > "$WP61_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP61_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP61_EVIDENCE"
printf 'Start test: %s\n' "$FROM_TEST"

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
    printf '%s = %s\n' "$1" "$2" >> "$WP61_EVIDENCE/observations.txt"
}

judge() {
    local step="$1" question="$2" answer="" note=""
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
        >> "$WP61_EVIDENCE/judgements.txt"
    printf 'owner verdict recorded for %s: %s\n' "$step" "$answer"
    [ "$answer" = "yes" ] || fail "owner verdict no for $step: $note"
}

run_wp_check() {
    local unit="$1" tier="$2" tag rc=0
    tag="$(printf '%s' "$unit" | tr -d '.' | tr '[:upper:]' '[:lower:]')"
    local stdout_file="$WP61_EVIDENCE/wp_check_${tag}_tier${tier}.json"
    local stderr_file="$WP61_EVIDENCE/wp_check_${tag}_tier${tier}.stderr.txt"
    python scripts/wp_check.py --unit "$unit" --tier "$tier" \
        --evidence "$WP61_EVIDENCE" \
        >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$WP61_EVIDENCE/wp_check_${tag}_tier${tier}.exit.txt"
    cat "$stderr_file"
    printf 'wp_check %s tier %s exit code: %s (as reported by wp_check)\n' "$unit" "$tier" "$rc"
    [ "$rc" -eq 0 ] || fail "wp_check $unit tier $tier exited $rc; see $stderr_file"
}

run_suite() {
    local name="$1" rc=0
    shift
    local output_file="$WP61_EVIDENCE/tier_a_${name}.txt"
    (cd "$KAKI_APP_ROOT" && "$@") >"$output_file" 2>&1 || rc=$?
    cat "$output_file"
    printf 'tier A %s exit code: %s\n' "$name" "$rc"
    [ "$rc" -eq 0 ] || fail "tier A $name exited $rc; see $output_file"
}

ran_count() {
    grep -Eo '^Ran [0-9]+ tests?' "$WP61_EVIDENCE/tier_a_$1.txt" | awk '{print $2}' | tail -1
}

# ---------------------------------------------------------------------------
# Tests, one function each. The dispatcher at the end honours --from-test.
# ---------------------------------------------------------------------------

# Test 1: thin-client conformance and the device suite (WP6-AT-13).
test1_thin_client() {
    section "Test 1: thin-client conformance (WP6-AT-13)"
    run_wp_check WP6.1 A
    local report="$WP61_EVIDENCE/wp_check_wp61_tierA.json"
    observe "test1_device_sources" "$(jq -r '.device_sources | length' "$report")"
    observe "test1_device_suite_tests_ran" "$(jq -r '.suite_tests_ran' "$report")"
    jq -r '.findings | to_entries[] | "\(.key) findings = \(.value | length)"' "$report"
    check "every thin-client rule is clean" "$(jq -r '[.findings[] | length] | add' "$report")" "0"
    check "every WP6.1 tier A check passed" "$(jq -r '.checks | all' "$report")" "true"

    run_suite ruff python -m ruff check --config backend/pyproject.toml \
        backend scripts services rag device
    run_suite device python -m unittest discover -s device/tests -t device/tests -v
    observe "test1_device_tests_ran" "$(ran_count device)"
}

# Test 2: one scripted mock turn through the real backend.
test2_mock_turn() {
    section "Test 2: scripted mock turn against the live stack"
    run_wp_check WP6.1 B
    local report="$WP61_EVIDENCE/wp_check_wp61_tierB.json"
    for field in state turn_id session_id printed spoke spoken_seconds display_states \
                 pending_items slip_first_line; do
        observe "test2_$field" "$(jq -c ".$field" "$report")"
    done
    check "backend answered the mock turn" "$(jq -r '.state' "$report")" "answered"
    check "device reported no local error" "$(jq -r '.error_code' "$report")" "null"
    check "every WP6.1 tier B check passed" "$(jq -r '.checks | all' "$report")" "true"
}

# Test 3: the frames a user would see, from a headless mock run.
test3_frames() {
    section "Test 3: rendered frames for one mock turn"
    local device_id="wp61-frames-$(date +%s)"
    KAKI_DEVICE_DEVICE_ID="$device_id" \
    KAKI_DEVICE_MOCK__AUDIO_PATH="$FIXTURE" \
        python -m kaki_device.main --mock --headless --turns 1 \
        --slip-log "$SLIP_LOG" > "$WP61_EVIDENCE/mock_run.txt" 2>&1 \
        || fail "the mock run exited non-zero; see mock_run.txt"
    cat "$WP61_EVIDENCE/mock_run.txt"
    observe "test3_device_id" "$device_id"
    check_true "the mock run reported an answered turn" \
        'grep -q "state=answered" "$WP61_EVIDENCE/mock_run.txt"'
    check_true "the mock run printed a slip" 'grep -q "printed=True" "$WP61_EVIDENCE/mock_run.txt"'
    check_true "a slip reached the slip log" '[ -s "$SLIP_LOG" ]'
    check_true "the slip names the CDC source" 'grep -q "$CDC_HOST" "$SLIP_LOG"'

    python scripts/wp6_1_frames.py --fixture "$FIXTURE" \
        > "$WP61_EVIDENCE/frames.txt" 2>&1 || fail "frame capture failed; see frames.txt"
    cat "$WP61_EVIDENCE/frames.txt"
    judge "test3-frames" \
        "Do these four screens read clearly for someone standing a metre from the kiosk?"
}

# Test 4: recovery and boundaries that need no hardware.
test4_recovery() {
    section "Test 4: failure recovery and session boundary"
    python scripts/wp6_1_frames.py --recovery > "$WP61_EVIDENCE/recovery.txt" 2>&1 \
        || fail "recovery check failed; see recovery.txt"
    cat "$WP61_EVIDENCE/recovery.txt"
    check_true "a backend failure shows the error frame" \
        'grep -q "error frame shown: yes" "$WP61_EVIDENCE/recovery.txt"'
    check_true "the loop returns to idle after a failure" \
        'grep -q "returned to idle: yes" "$WP61_EVIDENCE/recovery.txt"'
    check_true "an idle kiosk rotates its session" \
        'grep -q "session rotated: yes" "$WP61_EVIDENCE/recovery.txt"'
    observe "test4_pending_items" \
        "$(curl --fail --silent --max-time 10 "$BACKEND_URL/api/device/pending" | jq -c '.')"
}

teardown() {
    section "Teardown"
    printf 'The stack is still running. Stop it when you are done:\n'
    printf '  python scripts/dev_stack.py down\n\n'
    printf 'Harness finished with no failed assertion and no "no" verdict. This is\n'
    printf 'evidence, not the WP6.1 sign-off: review it, then mark runbook 11.1 WP6.1\n'
    printf 'VERIFIED yourself.\n'
    printf 'Evidence: %s\n' "$WP61_EVIDENCE"
}

[ "$FROM_TEST" -gt 1 ] || test1_thin_client
[ "$FROM_TEST" -gt 2 ] || test2_mock_turn
[ "$FROM_TEST" -gt 3 ] || test3_frames
test4_recovery
teardown
