#!/usr/bin/env bash
# v1.1 | 19-Sep-2026 | Fix the Test 2 jq filter (escaped quotes reached jq literally) and
#                      read every jq value through jq_read, which fails loudly.
# v1.0 | 18-Sep-2026 | Owner evidence harness for runbook 11.2 WP6.6 Tests 1-4.
#
# Capture WP6.6 validation evidence on the Mac by running the runbook 11.2
# WP6.6 test block in order: Tests 1-4.
#
# This is the owner's evidence harness, not the gate. It asserts the runbook's
# expected observations and stops with a non-zero exit at the first failed
# assertion. scripts/wp_check.py stays the automated gate: the harness records
# what each wp_check run reported, with its exit code. The judgement steps
# (the Malay push audio in Test 3, the admin page in Test 4) stop and ask the
# owner, who types yes or no; the verdict is written to judgements.txt and a
# "no" ends the run.
#
# Modes:
#   scripts/wp6_6_evidence.sh                     run the WP6.6 test block
#   scripts/wp6_6_evidence.sh --from-test N       resume at test N (1-4)
#   scripts/wp6_6_evidence.sh --capture-fixtures  create the two push WAVs
#   scripts/wp6_6_evidence.sh -h|--help           show this text
#
# Prerequisites for the test block: the grounded stack is running (python
# scripts/dev_stack.py up) from the WP6.6 checkout; the shell has the WP6.6
# environment (source scripts/kaki_env.sh WP6.6) with KAKI_ADMIN_TOKEN set;
# both push fixtures exist; an interactive terminal for Tests 3 and 4. Test 4
# also wants the simulator running (cd apps/web && npm run build && npm start)
# for the owner's browser steps.
#
# Side effects of the test block:
#   - Creates $WP66_EVIDENCE (a new directory under $KAKI_DATA_ROOT/wp6.6
#     unless an empty one is already exported); transcript.txt receives the run.
#   - Writes admin state (config and pushes) for scratch device ids and for
#     the simulator identity web-simulator, restoring each to auto and
#     draining every queued push before it exits.
#   - Posts real turns to the live backend (wp_check WP6.1 and WP6.6 tier B),
#     stored in $KAKI_DB as intended.
#   - Runs the deterministic suites; the WP6.1 tier A and B reruns are the
#     WP6.6 regression scope (execution-plan.md v1.13 section 7).
#   - Does not stop the stack. It prints the teardown command instead.
#
# Side effects of --capture-fixtures: writes push_cdc_en.wav and
# push_cdc_ms.wav into backend/src/kaki_backend/fixtures/ with macOS say,
# refuses to overwrite either file, removes a file it just wrote if it holds
# no audio, and records format, duration and the owner's listening verdicts.
#
# Exit status: 0 when every step ran, every assertion held and every verdict
# was yes; 1 on a failed assertion, failed command or a "no" verdict; 2 on a
# usage or precondition error; 3 when fixtures were written but no terminal
# was available for the owner's listening verdict.

set -Eeuo pipefail

BACKEND_URL="http://127.0.0.1:8000"
FIXTURE_DIR_RELATIVE="backend/src/kaki_backend/fixtures"
SCHEMA_SNAPSHOT="backend/tests/contract/snapshots/turn_response.schema.json"
MESSAGE_KEY="cdc-vouchers-available"
SIMULATOR_DEVICE="web-simulator"
# The provisional wording, spoken by the same voices the reply path uses.
PUSH_EN_TEXT="Good news: new CDC vouchers are available. Press the button to ask me about them."
PUSH_MS_TEXT="Berita baik: baucar CDC baharu sudah tersedia. Tekan butang untuk bertanya kepada saya."

usage() {
    awk 'NR > 2 && /^#/ { sub(/^# ?/, ""); print; next } NR > 2 { exit }' "$0"
}

usage_error() {
    printf '%s\n\n' "$1" >&2
    usage >&2
    exit 2
}

FROM_TEST=1
CAPTURE=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --capture-fixtures) CAPTURE=1; shift ;;
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
readonly FROM_TEST CAPTURE

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
FIXTURE_DIR="$KAKI_APP_ROOT/$FIXTURE_DIR_RELATIVE"

has_tty() {
    { : </dev/tty; } 2>/dev/null
}

# ---------------------------------------------------------------------------
# Fixture capture mode: no evidence directory, no backend needed.
# ---------------------------------------------------------------------------

capture_one() {
    local name="$1" voice="$2" text="$3" target="$FIXTURE_DIR/$1"
    if [ -s "$target" ]; then
        printf 'SKIP: %s already exists; delete it first to re-capture.\n' "$name"
        return 0
    fi
    say -v "$voice" --file-format=WAVE --data-format=LEI16@22050 -o "$target" "$text" \
        || fail "say failed for $name"
    if [ ! -s "$target" ]; then
        rm -f "$target"
        fail "$name was written empty; is the $voice voice installed (setup.md 10.1.1)?"
    fi
    afinfo "$target" | grep -E "duration|data format" || true
    afplay "$target"
}

if [ "$CAPTURE" = 1 ]; then
    command -v say >/dev/null || precondition "say is not on PATH." "run on the Mac"
    capture_one push_cdc_en.wav Samantha "$PUSH_EN_TEXT"
    capture_one push_cdc_ms.wav Amira "$PUSH_MS_TEXT"
    has_tty || { printf 'No terminal: listen to both files and confirm them yourself.\n'; exit 3; }
    printf '\nBoth files exist under %s.\n' "$FIXTURE_DIR_RELATIVE"
    read -r -p 'Did both recordings sound right (yes/no)? ' verdict </dev/tty
    [ "$verdict" = "yes" ] || { printf 'Delete the bad file and re-run.\n'; exit 1; }
    printf 'Captured. Commit both files with the WP6.6 change.\n'
    exit 0
fi

# ---------------------------------------------------------------------------
# Preconditions for the test block.
# ---------------------------------------------------------------------------

case "${KAKI_DATA_ROOT:-}" in
    /*) ;;
    "") precondition "KAKI_DATA_ROOT is unset." "source scripts/kaki_env.sh WP6.6" ;;
    *) precondition "KAKI_DATA_ROOT is not absolute: $KAKI_DATA_ROOT" \
           "export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data" ;;
esac

for tool in jq curl python git sqlite3 afplay base64; do
    command -v "$tool" >/dev/null || precondition "$tool is not on PATH." \
        "install $tool (setup.md 5.2)"
done

[ -n "${KAKI_ADMIN_TOKEN:-}" ] || precondition "KAKI_ADMIN_TOKEN is unset." \
    "add it to the project-root .env (setup.md 11.4), then source scripts/kaki_env.sh WP6.6"

for name in push_cdc_en.wav push_cdc_ms.wav; do
    [ -s "$FIXTURE_DIR/$name" ] || precondition "the push fixture $name is missing." \
        "scripts/wp6_6_evidence.sh --capture-fixtures"
done

curl --fail --silent --max-time 10 "$BACKEND_URL/api/health" >/dev/null || precondition \
    "the backend is not answering on 127.0.0.1:8000." \
    "python scripts/dev_stack.py up  then  python scripts/dev_stack.py status"

if [ "$FROM_TEST" -le 4 ]; then
    has_tty || precondition "no interactive terminal; Tests 3 and 4 have owner judgements." \
        "run scripts/wp6_6_evidence.sh from Terminal, not through a pipe"
fi

# ---------------------------------------------------------------------------
# Evidence directory, run header, transcript.
# ---------------------------------------------------------------------------

umask 077
if [ -n "${WP66_EVIDENCE:-}" ]; then
    [ -d "$WP66_EVIDENCE" ] || precondition "WP66_EVIDENCE does not exist: $WP66_EVIDENCE" \
        "unset WP66_EVIDENCE to let the harness create a new directory"
    [ -z "$(ls -A "$WP66_EVIDENCE")" ] || precondition \
        "WP66_EVIDENCE already holds evidence: $WP66_EVIDENCE" \
        "source scripts/kaki_env.sh WP6.6 again, or unset WP66_EVIDENCE"
else
    mkdir -p "$KAKI_DATA_ROOT/wp6.6"
    WP66_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp6.6/evidence.XXXXXX")"
fi
readonly WP66_EVIDENCE
export WP66_EVIDENCE KAKI_APP_ROOT

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
    printf 'KaKi-Talkie WP6.6 evidence run header\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    header_item "git uncommitted changes" git -C "$KAKI_APP_ROOT" status --short
    printf 'harness start test: %s (tests before it did not run)\n\n' "$FROM_TEST"
    printf 'KAKI_APP_ROOT: %s\nKAKI_DATA_ROOT: %s\nWP66_EVIDENCE: %s\n' \
        "$KAKI_APP_ROOT" "$KAKI_DATA_ROOT" "$WP66_EVIDENCE"
    printf 'KAKI_ADMIN_TOKEN: set (value withheld)\n\n'
    header_item "python" python --version
    header_item "backend health" curl --fail --silent --max-time 30 "$BACKEND_URL/api/health"
    header_item "backend admin startup line" sh -c \
        "grep 'admin surface' '$KAKI_DATA_ROOT/logs/backend.log' | tail -1"
    header_item "push fixture formats" sh -c \
        "afinfo '$FIXTURE_DIR/push_cdc_en.wav' '$FIXTURE_DIR/push_cdc_ms.wav' | grep -E 'File:|duration|data format'"
} > "$WP66_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP66_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP66_EVIDENCE"
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

# Read one value with jq into JQ_VALUE. Call it as a command, never inside
# $(...): `fail` cannot stop the run from a command-substitution subshell, so
# a jq that dies would reach `check` as an empty string and look like a failed
# assertion. A tool that dies must say so. Arguments after the file go to jq,
# for example --arg.
JQ_VALUE=""
jq_read() {
    local filter="$1" file="$2" rc=0 error=""
    shift 2
    JQ_VALUE="$(jq -r "$@" "$filter" "$file" 2>"$WP66_EVIDENCE/jq-error.txt")" || rc=$?
    if [ "$rc" -ne 0 ]; then
        error="$(tr '\n' ' ' < "$WP66_EVIDENCE/jq-error.txt")"
        fail "jq exited $rc on $file for filter: $filter${error:+ - $error}"
    fi
}

observe() {
    printf 'observation: %s = %s\n' "$1" "$2"
    printf '%s = %s\n' "$1" "$2" >> "$WP66_EVIDENCE/observations.txt"
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
        >> "$WP66_EVIDENCE/judgements.txt"
    printf 'owner verdict recorded for %s: %s\n' "$step" "$answer"
    [ "$answer" = "yes" ] || fail "owner verdict no for $step: $note"
}

run_wp_check() {
    local unit="$1" tier="$2" tag rc=0
    tag="$(printf '%s' "$unit" | tr -d '.' | tr '[:upper:]' '[:lower:]')"
    local stdout_file="$WP66_EVIDENCE/wp_check_${tag}_tier${tier}.json"
    local stderr_file="$WP66_EVIDENCE/wp_check_${tag}_tier${tier}.stderr.txt"
    python scripts/wp_check.py --unit "$unit" --tier "$tier" \
        --evidence "$WP66_EVIDENCE" \
        >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$WP66_EVIDENCE/wp_check_${tag}_tier${tier}.exit.txt"
    cat "$stderr_file"
    printf 'wp_check %s tier %s exit code: %s (as reported by wp_check)\n' "$unit" "$tier" "$rc"
    [ "$rc" -eq 0 ] || fail "wp_check $unit tier $tier exited $rc; see $stderr_file"
}

run_suite() {
    local name="$1" rc=0
    shift
    local output_file="$WP66_EVIDENCE/tier_a_${name}.txt"
    (cd "$KAKI_APP_ROOT" && "$@") >"$output_file" 2>&1 || rc=$?
    cat "$output_file"
    printf 'tier A %s exit code: %s\n' "$name" "$rc"
    [ "$rc" -eq 0 ] || fail "tier A $name exited $rc; see $output_file"
}

admin() {
    KAKI_ADMIN_DEFAULT_DEVICE="${ADMIN_TARGET:-kaki-pi-01}" scripts/wp6_6_admin.sh "$@"
}

# ---------------------------------------------------------------------------
# Tests, one function each. The dispatcher at the end honours --from-test.
# ---------------------------------------------------------------------------

# Test 1: deterministic gate plus the WP6.1 tier A regression rerun.
test1_deterministic() {
    section "Test 1: WP6.6 tier A and the WP6.1 tier A rerun"
    run_wp_check WP6.6 A
    run_wp_check WP6.1 A
    run_suite ruff python -m ruff check --config backend/pyproject.toml \
        backend scripts services rag device
    run_suite contract python -m unittest discover -s backend/tests/contract
    run_suite unit python -m unittest discover -s backend/tests/unit
    run_suite web_test sh -c "cd apps/web && npm test"
    check "WP1 turn schema snapshot file unchanged from HEAD (X-AT-01)" \
        "$(git -C "$KAKI_APP_ROOT" status --porcelain -- "$SCHEMA_SNAPSHOT")" ""
}

# Test 2: the live admin flow through wp_check, plus the loopback curl script.
test2_live_flow() {
    section "Test 2: live admin flow (wp_check WP6.6 tier B)"
    run_wp_check WP6.6 B

    section "Test 2: the loopback curl fallback (WP6-AT-18)"
    ADMIN_TARGET="wp66-curl-$(date +%s)"
    admin state | tee "$WP66_EVIDENCE/curl_state_before.json" >/dev/null
    admin config ms --device "$ADMIN_TARGET" | tee "$WP66_EVIDENCE/curl_config.json"
    admin push --device "$ADMIN_TARGET" | tee "$WP66_EVIDENCE/curl_push.json"
    admin state | tee "$WP66_EVIDENCE/curl_state_after.json"
    jq_read '[.config[] | select(.device_id == $d) | .reply_language] | last' \
        "$WP66_EVIDENCE/curl_state_after.json" --arg d "$ADMIN_TARGET"
    check "curl config took effect" "$JQ_VALUE" "ms"
    jq_read '.messages[0].state + ":" + .messages[0].target_device_id' \
        "$WP66_EVIDENCE/curl_state_after.json"
    check "curl push is queued for the curl device" "$JQ_VALUE" "queued:$ADMIN_TARGET"
    # Drain and restore the scratch device so nothing leaks into later tests.
    curl --fail --silent "$BACKEND_URL/api/device/pending?device_id=$ADMIN_TARGET" >/dev/null
    admin config auto --device "$ADMIN_TARGET" >/dev/null
    observe "test2_curl_device" "$ADMIN_TARGET"
}

# Test 3: the push a user would hear, delivered once, in Malay.
test3_push_audio() {
    section "Test 3: the delivered nudge, heard once"
    local device="wp66-audio-$(date +%s)"
    admin config ms --device "$device" >/dev/null
    admin push --device "$device" >/dev/null
    curl --fail --silent "$BACKEND_URL/api/device/pending?device_id=$device" \
        > "$WP66_EVIDENCE/nudge.json"
    jq_read 'length' "$WP66_EVIDENCE/nudge.json"
    check "one nudge delivered" "$JQ_VALUE" "1"
    jq_read '.[0].language' "$WP66_EVIDENCE/nudge.json"
    check "the nudge is Malay for an ms device" "$JQ_VALUE" "ms"
    curl --fail --silent "$BACKEND_URL/api/device/pending?device_id=$device" \
        > "$WP66_EVIDENCE/nudge_second_poll.json"
    jq_read 'length' "$WP66_EVIDENCE/nudge_second_poll.json"
    check "a second poll replays nothing" "$JQ_VALUE" "0"
    jq_read '.[0].audio // empty' "$WP66_EVIDENCE/nudge.json"
    printf '%s' "$JQ_VALUE" \
        | sed 's#^data:audio/wav;base64,##' | base64 -D > "$WP66_EVIDENCE/nudge.wav"
    check_true "the nudge carries pre-synthesised audio" '[ -s "$WP66_EVIDENCE/nudge.wav" ]'
    afplay "$WP66_EVIDENCE/nudge.wav"
    judge "test3-nudge-audio" "Was that the Malay CDC-vouchers announcement, clear and calm?"
    admin config auto --device "$device" >/dev/null
    observe "test3_device" "$device"
}

# Test 4: the admin page steering the simulator, and the WP6.1 tier B rerun.
test4_page_and_regression() {
    section "Test 4: admin page against the simulator (owner steps)"
    printf 'In Chrome:\n'
    printf '  1. Open http://127.0.0.1:3000/admin, enter the admin token once.\n'
    printf '  2. The status line names the target. For this rehearsal the target is\n'
    printf '     the simulator: run  scripts/wp6_6_admin.sh config ms --device %s\n' "$SIMULATOR_DEVICE"
    printf '     (the page steers the Pi by default; the simulator stands in today).\n'
    printf '  3. In a second tab open http://127.0.0.1:3000/sim and ask the CDC question;\n'
    printf '     the reply should be Malay.\n'
    printf '  4. Push:  scripts/wp6_6_admin.sh push --device %s\n' "$SIMULATOR_DEVICE"
    printf '     Within 3 seconds the simulator shows and speaks the announcement, once.\n'
    printf '  5. Restore: scripts/wp6_6_admin.sh config auto --device %s\n\n' "$SIMULATOR_DEVICE"
    judge "test4-admin-page" \
        "Did the page's four buttons and status line work one-handed, and did the simulator speak the push exactly once?"
    # Leave the simulator identity clean whatever the owner did above.
    admin config auto --device "$SIMULATOR_DEVICE" >/dev/null
    curl --fail --silent "$BACKEND_URL/api/device/pending?device_id=$SIMULATOR_DEVICE" >/dev/null

    section "Test 4: WP6.1 tier B rerun (the WP6.6 regression scope)"
    run_wp_check WP6.1 B
}

teardown() {
    section "Teardown"
    printf 'The stack is still running. Stop it when you are done:\n'
    printf '  python scripts/dev_stack.py down\n\n'
    printf 'Harness finished with no failed assertion and no "no" verdict. This is\n'
    printf 'evidence, not the WP6.6 sign-off: review it, then mark runbook 11.1 WP6.6\n'
    printf 'VERIFIED yourself.\n'
    printf 'Evidence: %s\n' "$WP66_EVIDENCE"
}

[ "$FROM_TEST" -gt 1 ] || test1_deterministic
[ "$FROM_TEST" -gt 2 ] || test2_live_flow
[ "$FROM_TEST" -gt 3 ] || test3_push_audio
test4_page_and_regression
teardown
