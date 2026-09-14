#!/usr/bin/env bash
# v1.3 | 13-Sep-2026 | Expect the packaged schema version; WP5.1 added migration 0003.
# v1.2 | 13-Sep-2026 | Package mode reruns WP4.1 and WP4.2 only (execution-plan.md 1.1).
# v1.1 | 13-Sep-2026 | Add --from-test and --regression scoped|package; Test 3 withdrawn.
# v1.0 | 13-Sep-2026 | Owner evidence harness for runbook 9.2 WP4.5 Tests 1-6.
#
# Capture WP4.5 validation evidence on the Mac by running the runbook 9.2
# WP4.5 test block in order: the restore reference turns, Tests 1-6.
#
# This is the owner's evidence harness, not the gate. It asserts the runbook's
# expected observations and stops with a non-zero exit at the first failed
# assertion. scripts/wp_check.py stays the automated gate: the harness records
# what each wp_check run reported, with its exit code. The judgement step (the
# restored audio in Test 2) stops and asks the owner, who types yes or no; the verdict is
# written to judgements.txt and a "no" ends the run. Test 3 is withdrawn under
# owner decision 1: the harness prints that and moves on. Test 7, the WP4
# package gate, is the owner's and is not scripted.
#
# Usage:
#   scripts/wp4_5_evidence.sh [--from-test N] [--regression scoped|package]
#   scripts/wp4_5_evidence.sh -h|--help
#
# Options:
#   --from-test N     Start at test N (1-6, default 1) and run to the end.
#                     Starting at 2 reruns restore steps 1 and 2 as setup
#                     (reference turns and a new backup set) without the
#                     Test 1 assertions. Starting at 4 or later observes the
#                     newest existing backup set in Test 4.
#   --regression MODE scoped (default): ruff, the contract and scripts
#                     suites, web lint, test and build, and wp_check.py
#                     --unit WP4.5 --tier B. package: scoped plus wp_check.py
#                     tier B for WP4.1 and WP4.2, one unit at a time. The gate
#                     commit needs package. Package mode stays inside WP4 under
#                     the within-package regression rule (execution-plan.md
#                     1.1): a unit reruns an earlier unit of the same work
#                     package, and only when it touches that unit's code.
# The run header and Test 6 output record both values.
#
# Prerequisites: the grounded stack is running (python scripts/dev_stack.py up)
# from the WP4.5 checkout; the shell has the WP4.5 environment (source
# scripts/kaki_env.sh WP4.5) with KAKI_SQLITE_PATH unset; the spoken fixtures
# exist; the run is in an interactive terminal when it starts at Test 1 or 2.
#
# Restore safety rules:
#   - KAKI_LIVE_DATA_ROOT is captured before the restore phase. llm.log is
#     read from that root for the whole run, because MLX-LM keeps writing
#     where it started.
#   - The restored kaki.db must exist, be non-empty and match its manifest
#     hash before a backend starts under $RESTORE_ROOT.
#   - The live database is written only through the backend HTTP API.
#   - On exit, success or failure, the harness stops a restored backend,
#     restarts the live backend if it stopped it, and prints the live
#     storage_ready value.
#
# Side effects:
#   - Creates $WP45_EVIDENCE (a new directory under $KAKI_DATA_ROOT/wp4.5
#     unless an empty one is already exported); transcript.txt receives the run.
#   - Posts turns to the live backend (restore step 1, wp_check runs). All
#     are stored in $KAKI_DB, as intended.
#   - Runs scripts/backup_sqlite.sh twice from Test 1, once from Test 2: new
#     backup sets under $KAKI_DATA_ROOT/backups. None is deleted.
#   - Stops the live backend once, runs a backend against a restored copy in
#     $KAKI_DATA_ROOT/wp4.5/restore.XXXXXX, then restarts the live backend.
#     Whisper-server and MLX-LM keep running. The restore copy is kept for
#     review; delete it yourself afterwards.
#   - Runs the devset regression twice when Test 5 runs (Test 5, and
#     wp_check WP4.5 in Test 6), each loading a second embedding model.
#   - Runs the deterministic suites and the web lint, test and build (Test 6).
#     The build rewrites apps/web/.next; restart the simulator afterwards.
#   - Does not stop the stack. It prints the teardown command instead.
#
# Exit status: 0 when every step ran, every assertion held and every verdict
# was yes; 1 on a failed assertion, failed command or a "no" verdict; 2 on a
# usage or precondition error.

set -Eeuo pipefail

BACKEND_URL="http://127.0.0.1:8000"
SMOKE_DEVICE="wp45-smoke"
CDC_HOST="vouchers.cdc.gov.sg"
INTENT_TARGET="0.80"
FIXTURE_DIR_RELATIVE="backend/src/kaki_backend/fixtures"
SCHEMA_SNAPSHOT="backend/tests/contract/snapshots/turn_response.schema.json"
LLM_LOG_PATTERN="POST /v1/chat/completions"
# Package mode adds these before WP4.5. Only WP4 units qualify: WP4.5 writes
# the tables WP4.1 created and deletes the action turns WP4.2 writes. Earlier
# work packages are out of scope under execution-plan.md 1.1.  #v1.2
PACKAGE_TIER_B_UNITS="WP4.1 WP4.2"  #v1.2

usage() {
    awk 'NR > 6 && /^#/ { sub(/^# ?/, ""); print; next } NR > 6 { exit }' "$0"  #v1.2
}

usage_error() {  #v1.1
    printf '%s\n\n' "$1" >&2  #v1.1
    usage >&2  #v1.1
    exit 2  #v1.1
}  #v1.1

FROM_TEST=1  #v1.1
REGRESSION_MODE="scoped"  #v1.1
while [ "$#" -gt 0 ]; do  #v1.1
    case "$1" in  #v1.1
        -h|--help) usage; exit 0 ;;  #v1.1
        --from-test)  #v1.1
            [ "$#" -ge 2 ] || usage_error "--from-test needs a test number."  #v1.1
            FROM_TEST="$2"; shift 2 ;;  #v1.1
        --regression)  #v1.1
            [ "$#" -ge 2 ] || usage_error "--regression needs scoped or package."  #v1.1
            REGRESSION_MODE="$2"; shift 2 ;;  #v1.1
        *) usage_error "Unknown argument: $1" ;;  #v1.1
    esac  #v1.1
done  #v1.1
case "$FROM_TEST" in  #v1.1
    1|2|3|4|5|6) ;;  #v1.1
    *) usage_error "--from-test must be 1 to 6, got: $FROM_TEST" ;;  #v1.1
esac  #v1.1
case "$REGRESSION_MODE" in  #v1.1
    scoped|package) ;;  #v1.1
    *) usage_error "--regression must be scoped or package, got: $REGRESSION_MODE" ;;  #v1.1
esac  #v1.1
readonly FROM_TEST REGRESSION_MODE  #v1.1

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
# Migrations are numbered contiguously from 0001, so their count is the schema
# version this checkout's backend migrates to.  #v1.3
EXPECTED_SCHEMA_VERSION="$(find "$KAKI_APP_ROOT/backend/src/kaki_backend/persistence/migrations" \
    -name '[0-9][0-9][0-9][0-9]_*.sql' | wc -l | tr -d ' ')"  #v1.3

has_tty() {
    { : </dev/tty; } 2>/dev/null
}

# ---------------------------------------------------------------------------
# Preconditions, checked before any evidence is written.
# ---------------------------------------------------------------------------

case "${KAKI_DATA_ROOT:-}" in
    /*) ;;
    "") precondition "KAKI_DATA_ROOT is unset." "source scripts/kaki_env.sh WP4.5" ;;
    *) precondition "KAKI_DATA_ROOT is not absolute: $KAKI_DATA_ROOT" \
           "export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data" ;;
esac
if [ -n "${KAKI_SQLITE_PATH:-}" ]; then
    precondition "KAKI_SQLITE_PATH is set to $KAKI_SQLITE_PATH." \
        "unset KAKI_SQLITE_PATH; the restore test needs the database to follow KAKI_DATA_ROOT"
fi

# The live root, fixed for the whole run. Nothing below reassigns it.
KAKI_LIVE_DATA_ROOT="$KAKI_DATA_ROOT"
KAKI_DB="$KAKI_LIVE_DATA_ROOT/sqlite/kaki.db"
LLM_LOG="$KAKI_LIVE_DATA_ROOT/logs/llm.log"
readonly KAKI_LIVE_DATA_ROOT KAKI_DB LLM_LOG

for tool in jq sqlite3 uuidgen curl afplay base64 shasum npm git stat du df; do
    command -v "$tool" >/dev/null || precondition "$tool is not on PATH." \
        "install $tool (setup.md 5.2); macOS provides afplay, uuidgen, stat, du and df"
done

[ -f "$KAKI_DB" ] || precondition "the database is missing: $KAKI_DB" \
    "python scripts/dev_stack.py up  (the backend creates the database at start)"

curl --fail --silent --max-time 10 "$BACKEND_URL/api/health" >/dev/null || precondition \
    "the backend is not answering on 127.0.0.1:8000." \
    "python scripts/dev_stack.py up  then  python scripts/dev_stack.py status"

schema_version="$(sqlite3 "$KAKI_DB" 'pragma user_version;')"
[ "$schema_version" = "$EXPECTED_SCHEMA_VERSION" ] || precondition \
    "the database is at schema version $schema_version, not $EXPECTED_SCHEMA_VERSION." \
    "restart the backend from the WP4.5 checkout"

for name in cdc_question.wav repeat_request.wav; do
    [ -s "$FIXTURE_DIR/$name" ] || precondition "the fixture $FIXTURE_DIR_RELATIVE/$name is missing." \
        "restore it from Git; fixtures are committed (runbook 9.1 WP4.2)"
done

for script in scripts/backup_sqlite.sh scripts/dev_stack.py scripts/run_regression.py; do
    [ -f "$KAKI_APP_ROOT/$script" ] || precondition "$script is missing." "use the WP4.5 checkout"
done

if [ "$FROM_TEST" -le 2 ]; then  #v1.1
    has_tty || precondition "no interactive terminal; Test 2 has an owner judgement step." \
        "run scripts/wp4_5_evidence.sh from Terminal, not through a pipe"
fi  #v1.1

python -c "import kaki_backend" 2>/dev/null || precondition "python cannot import kaki_backend." \
    "source \"$KAKI_APP_ROOT/.venv/bin/activate\""

for setting in KAKI_RETRIEVAL_MODE=rag KAKI_LLM_MODE=qwen KAKI_TTS_MODE=say KAKI_STT_MODE=whisper; do
    name="${setting%%=*}"
    wanted="${setting#*=}"
    actual="${!name:-}"
    [ "$actual" = "$wanted" ] || precondition "$name is '${actual:-unset}', expected '$wanted'." \
        "source scripts/kaki_env.sh WP4.5"
done

for log in "$LLM_LOG" "$KAKI_LIVE_DATA_ROOT/logs/backend.log"; do
    [ -f "$log" ] || precondition "log not found: $log" \
        "start the stack with python scripts/dev_stack.py up, which writes the service logs"
done

# ---------------------------------------------------------------------------
# Evidence directory, run header, transcript.
# ---------------------------------------------------------------------------

umask 077
if [ -n "${WP45_EVIDENCE:-}" ]; then
    [ -d "$WP45_EVIDENCE" ] || precondition "WP45_EVIDENCE does not exist: $WP45_EVIDENCE" \
        "unset WP45_EVIDENCE to let the harness create a new directory"
    [ -z "$(ls -A "$WP45_EVIDENCE")" ] || precondition \
        "WP45_EVIDENCE already holds evidence: $WP45_EVIDENCE" \
        "source scripts/kaki_env.sh WP4.5 again, or unset WP45_EVIDENCE"
else
    mkdir -p "$KAKI_LIVE_DATA_ROOT/wp4.5"
    WP45_EVIDENCE="$(mktemp -d "$KAKI_LIVE_DATA_ROOT/wp4.5/evidence.XXXXXX")"
fi
readonly WP45_EVIDENCE
export WP45_EVIDENCE KAKI_APP_ROOT

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
    printf 'KaKi-Talkie WP4.5 evidence run header\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    header_item "git uncommitted changes" git -C "$KAKI_APP_ROOT" status --short
    printf 'harness start test: %s (tests before it did not run)\nregression mode: %s\n\n' \
        "$FROM_TEST" "$REGRESSION_MODE"  #v1.1
    printf 'KAKI_APP_ROOT: %s\nKAKI_LIVE_DATA_ROOT: %s\nKAKI_DB: %s\nLLM_LOG: %s\nWP45_EVIDENCE: %s\n\n' \
        "$KAKI_APP_ROOT" "$KAKI_LIVE_DATA_ROOT" "$KAKI_DB" "$LLM_LOG" "$WP45_EVIDENCE"
    header_item "database schema version" sqlite3 "$KAKI_DB" "pragma user_version;"
    header_item "macOS version" sw_vers -productVersion
    header_item "sqlite3 CLI" sqlite3 --version
    header_item "bash" bash --version
    header_item "node" node --version
    header_item "python" python --version
    header_item "backend health" curl --fail --silent --max-time 30 "$BACKEND_URL/api/health"
    header_item "dev_stack.py version line" head -1 scripts/dev_stack.py
    header_item "backup_sqlite.sh version line" sed -n 2p scripts/backup_sqlite.sh
} > "$WP45_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP45_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP45_EVIDENCE"
printf 'Live data root: %s\n' "$KAKI_LIVE_DATA_ROOT"
printf 'Live database: %s\n' "$KAKI_DB"
printf 'Start test: %s; regression mode: %s\n' "$FROM_TEST" "$REGRESSION_MODE"  #v1.1

# ---------------------------------------------------------------------------
# Live backend restoration on exit.
# ---------------------------------------------------------------------------

LIVE_BACKEND_STOPPED=0
RESTORED_BACKEND_STARTED=0
RESTORE_ROOT=""

live_stack() {
    env -u KAKI_SQLITE_PATH KAKI_DATA_ROOT="$KAKI_LIVE_DATA_ROOT" python scripts/dev_stack.py "$@"
}

restored_stack() {
    env -u KAKI_SQLITE_PATH KAKI_DATA_ROOT="$RESTORE_ROOT" python scripts/dev_stack.py "$@"
}

on_exit() {
    local status=$?
    trap - ERR
    set +e
    if [ "$RESTORED_BACKEND_STARTED" = 1 ]; then
        printf '\nExit: stopping the restored backend under %s\n' "$RESTORE_ROOT"
        restored_stack down --only backend
    fi
    if [ "$LIVE_BACKEND_STOPPED" = 1 ]; then
        printf '\nExit: restarting the live backend under %s\n' "$KAKI_LIVE_DATA_ROOT"
        live_stack up --only backend
    fi
    printf '\nlive backend storage_ready: %s\n' \
        "$(curl --fail --silent --max-time 30 "$BACKEND_URL/api/health" | jq -r '.storage_ready' 2>/dev/null || printf 'unreachable')"
    printf 'live backend log: %s\n' \
        "$(grep -i 'sqlite' "$KAKI_LIVE_DATA_ROOT/logs/backend.log" | tail -1)"
    exit "$status"
}
trap on_exit EXIT

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
    printf '%s = %s\n' "$1" "$2" >> "$WP45_EVIDENCE/observations.txt"
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
        >> "$WP45_EVIDENCE/judgements.txt"
    printf 'owner verdict recorded for %s: %s\n' "$step" "$answer"
    [ "$answer" = "yes" ] || fail "owner verdict no for $step: $note"
}

live_sql() {
    sqlite3 "$KAKI_DB" "$1"
}

restored_sql() {
    sqlite3 "$RESTORE_ROOT/sqlite/kaki.db" "$1"
}

# Read a backup database without leaving -wal or -shm files in the set.
backup_sql() {
    sqlite3 "file:$1/kaki.db?immutable=1" "$2"
}

new_uuid() {
    uuidgen | tr '[:upper:]' '[:lower:]'
}

new_turn_id() {
    printf '%s-%s' "$1" "$(new_uuid)"
}

# Count matching llm.log lines in the live root after a short flush pause.
llm_count() {
    sleep 1
    grep -c "$LLM_LOG_PATTERN" "$LLM_LOG" || true
}

# POST one fixture; write the response to <tag>.json and the debug view to debug_<tag>.json.
post_turn() {
    local tag="$1" session="$2" turn_id="$3" audio="$4" seconds
    seconds="$(curl --fail --silent --show-error --max-time 300 "$BACKEND_URL/api/device/turn" \
        -F "device_id=$SMOKE_DEVICE" -F "session_id=$session" -F "turn_id=$turn_id" \
        -F "audio=@$audio" -o "$WP45_EVIDENCE/$tag.json" -w '%{time_total}')" \
        || fail "POST /api/device/turn ($tag) failed"
    curl --fail --silent "$BACKEND_URL/api/device/debug/last-turn" -o "$WP45_EVIDENCE/debug_$tag.json" \
        || fail "GET /api/device/debug/last-turn after $tag failed"
    observe "${tag}_elapsed_seconds" "$seconds"
    jq -c '{state, reply_text, sources: (.sources | length)}' "$WP45_EVIDENCE/$tag.json"
    jq -c '{turn_id, intent, transcript, previous_turn_id, action_outcome}' "$WP45_EVIDENCE/debug_$tag.json"
}

field() {
    jq -r "$2" "$WP45_EVIDENCE/$1.json"
}

# Decode a response's reply_audio into a WAV file and print its SHA-256.
audio_sha() {
    jq -r '.reply_audio // empty' "$WP45_EVIDENCE/$1.json" \
        | sed 's#^data:audio/wav;base64,##' | base64 -D > "$WP45_EVIDENCE/$1_reply.wav"
    [ -s "$WP45_EVIDENCE/$1_reply.wav" ] || fail "$1 carries no reply audio"
    shasum -a 256 < "$WP45_EVIDENCE/$1_reply.wav" | awk '{print $1}'
}

source_host() {
    field "$1" '.sources[0].source_url' | sed -E 's#^https?://([^/:]+).*#\1#'
}

health_field() {
    curl --fail --silent --max-time 60 "$BACKEND_URL/api/health" | jq -r ".$1"
}

file_mode() {
    stat -f '%Lp' "$1"
}

# Return the newest completed backup set, for a run that skipped restore step 2.  #v1.1
latest_backup_set() {  #v1.1
    local newest  #v1.1
    newest="$(find "$KAKI_LIVE_DATA_ROOT/backups" -mindepth 1 -maxdepth 1 -type d \
        -name '[0-9]*T[0-9]*Z' 2>/dev/null | LC_ALL=C sort | tail -1)"  #v1.1
    [ -n "$newest" ] || fail "no backup set under $KAKI_LIVE_DATA_ROOT/backups; start at Test 1 or 2"  #v1.1
    printf '%s\n' "$newest"  #v1.1
}  #v1.1

# List every file in a set with its hash and modification time, sorted.
set_fingerprint() {
    (cd "$1" && find . -type f | LC_ALL=C sort | while IFS= read -r path; do
        printf '%s %s %s\n' "$(shasum -a 256 "$path" | awk '{print $1}')" \
            "$(stat -f '%m' "$path")" "$path"
    done)
}

run_wp_check() {
    local unit="$1" tag rc=0
    tag="$(printf '%s' "$unit" | tr -d '.' | tr '[:upper:]' '[:lower:]')"
    local stdout_file="$WP45_EVIDENCE/wp_check_${tag}_tierB.json"
    local stderr_file="$WP45_EVIDENCE/wp_check_${tag}_tierB.stderr.txt"
    python scripts/wp_check.py --unit "$unit" --tier B >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$WP45_EVIDENCE/wp_check_${tag}_tierB.exit.txt"
    cat "$stdout_file" "$stderr_file"
    printf 'wp_check %s tier B exit code: %s (as reported by wp_check)\n' "$unit" "$rc"
    [ "$rc" -eq 0 ] || fail "wp_check $unit tier B exited $rc; see $stderr_file"
}

run_suite() {
    local name="$1" directory="$2" rc=0
    shift 2
    local output_file="$WP45_EVIDENCE/tier_a_${name}.txt"
    (cd "$directory" && "$@") >"$output_file" 2>&1 || rc=$?
    cat "$output_file"
    printf 'tier A %s exit code: %s\n' "$name" "$rc"
    [ "$rc" -eq 0 ] || fail "tier A $name exited $rc; see $output_file"
}

ran_count() {
    grep -Eo '^Ran [0-9]+ tests?' "$WP45_EVIDENCE/tier_a_$1.txt" | awk '{print $2}' | tail -1
}

# ---------------------------------------------------------------------------
# Tests, one function each. The dispatcher at the end honours --from-test.  #v1.1
# ---------------------------------------------------------------------------

# Restore steps 1 and 2: reference turns, then the first backup set (Tests 1 and 2 need both).
restore_reference_and_backup() {  #v1.1
    section "Restore step 1: reference answer and repeat"
    REF_SESSION="wp45-session-$(new_uuid)"
    ANSWER_TURN_ID="$(new_turn_id wp45-answer)"
    REPEAT_TURN_ID="$(new_turn_id wp45-repeat)"
    printf 'REF_SESSION=%s\nANSWER_TURN_ID=%s\nREPEAT_TURN_ID=%s\n' \
        "$REF_SESSION" "$ANSWER_TURN_ID" "$REPEAT_TURN_ID"

    post_turn ref_answer "$REF_SESSION" "$ANSWER_TURN_ID" "$FIXTURE_DIR/cdc_question.wav"
    post_turn ref_repeat "$REF_SESSION" "$REPEAT_TURN_ID" "$FIXTURE_DIR/repeat_request.wav"
    check "reference answer state" "$(field ref_answer .state)" "answered"
    check "reference answer sources[0] host" "$(source_host ref_answer)" "$CDC_HOST"
    check "reference repeat state" "$(field ref_repeat .state)" "acted"
    check "reference repeat previous_turn_id" "$(field debug_ref_repeat .previous_turn_id)" "$ANSWER_TURN_ID"
    ANSWER_AUDIO_SHA="$(audio_sha ref_answer)"
    REPEAT_AUDIO_SHA="$(audio_sha ref_repeat)"
    observe "reference_answer_audio_sha256" "$ANSWER_AUDIO_SHA"
    observe "reference_repeat_audio_sha256" "$REPEAT_AUDIO_SHA"

    section "Restore step 2: take the first backup set"  #v1.1
    backup_rc=0
    turns_before_backup="$(live_sql 'select count(*) from turns;')"
    scripts/backup_sqlite.sh > "$WP45_EVIDENCE/backup_first.stdout.txt" \
        2> "$WP45_EVIDENCE/backup_first.stderr.txt" || backup_rc=$?
    turns_after_backup="$(live_sql 'select count(*) from turns;')"
    cat "$WP45_EVIDENCE/backup_first.stdout.txt" "$WP45_EVIDENCE/backup_first.stderr.txt"
    observe "test1_live_turns_before_backup" "$turns_before_backup"
    observe "test1_live_turns_after_backup" "$turns_after_backup"
    check "backup_sqlite.sh exit code" "$backup_rc" "0"
    BACKUP_SET="$(sed -n 's/^Backup set: //p' "$WP45_EVIDENCE/backup_first.stdout.txt")"
    check_true "backup set directory exists under the live backups directory" \
        '[ -d "$BACKUP_SET" ] && [ "$(dirname "$BACKUP_SET")" = "$KAKI_LIVE_DATA_ROOT/backups" ]'
}

# Test 1: backup a live database; assertions on the set from restore step 2.
test1_backup_assertions() {  #v1.1
    section "Test 1: backup a live database"  #v1.1
    cp "$BACKUP_SET/manifest.txt" "$WP45_EVIDENCE/backup_manifest.txt"
    check "set directory mode" "$(file_mode "$BACKUP_SET")" "700"
    check "subdirectories not 0700" "$(find "$BACKUP_SET" -type d ! -perm 700 | wc -l | tr -d ' ')" "0"
    check "files not 0600" "$(find "$BACKUP_SET" -type f ! -perm 600 | wc -l | tr -d ' ')" "0"
    backup_sql "$BACKUP_SET" "pragma integrity_check; pragma foreign_key_check; pragma user_version;" \
        > "$WP45_EVIDENCE/backup_integrity.txt"
    check "backup integrity_check" "$(backup_sql "$BACKUP_SET" 'pragma integrity_check;')" "ok"
    check "backup foreign_key_check" "$(backup_sql "$BACKUP_SET" 'pragma foreign_key_check;')" ""
    check "backup user_version" "$(backup_sql "$BACKUP_SET" 'pragma user_version;')" "$EXPECTED_SCHEMA_VERSION"
    backup_turns="$(backup_sql "$BACKUP_SET" 'select count(*) from turns;')"
    observe "test1_backup_turns" "$backup_turns"
    check_true "backup turns count within the live before and after counts ($turns_before_backup..$turns_after_backup)" \
        '[ "$backup_turns" -ge "$turns_before_backup" ] && [ "$backup_turns" -le "$turns_after_backup" ]'
    check "manifest turns equals backup turns" "$(sed -n 's/^turns=//p' "$BACKUP_SET/manifest.txt")" "$backup_turns"
    check "backup holds the reference answer" \
        "$(backup_sql "$BACKUP_SET" "select count(*) from turns where turn_id in ('$ANSWER_TURN_ID', '$REPEAT_TURN_ID');")" "2"
    mismatches=0
    listed=0
    while IFS= read -r line; do
        relative="${line#sha256:}"
        relative="${relative%=*}"
        digest="${line##*=}"
        listed=$((listed + 1))
        actual="$(shasum -a 256 "$BACKUP_SET/$relative" | awk '{print $1}')"
        [ "$actual" = "$digest" ] || { printf 'hash mismatch: %s\n' "$relative"; mismatches=$((mismatches + 1)); }
    done < <(grep '^sha256:' "$BACKUP_SET/manifest.txt")
    check "manifest SHA-256 mismatches" "$mismatches" "0"
    check "manifest lists every file in the set" "$listed" \
        "$(find "$BACKUP_SET" -type f ! -name manifest.txt | wc -l | tr -d ' ')"
    check_true "corpus/ and chroma/ present" '[ -d "$BACKUP_SET/corpus" ] && [ -d "$BACKUP_SET/chroma" ]'
    observe "test1_ingest_running" "$(sed -n 's/^ingest_running=//p' "$BACKUP_SET/manifest.txt")"

    help_rc=0
    scripts/backup_sqlite.sh --help > "$WP45_EVIDENCE/backup_help.txt" 2>&1 || help_rc=$?
    check "backup_sqlite.sh --help exit code" "$help_rc" "0"
    check_true "--help prints usage" 'grep -q "^Usage:" "$WP45_EVIDENCE/backup_help.txt"'

    set_fingerprint "$BACKUP_SET" > "$WP45_EVIDENCE/backup_first_fingerprint_before.txt"
    sleep 2
    second_rc=0
    scripts/backup_sqlite.sh > "$WP45_EVIDENCE/backup_second.stdout.txt" \
        2> "$WP45_EVIDENCE/backup_second.stderr.txt" || second_rc=$?
    cat "$WP45_EVIDENCE/backup_second.stdout.txt" "$WP45_EVIDENCE/backup_second.stderr.txt"
    check "second backup exit code" "$second_rc" "0"
    SECOND_SET="$(sed -n 's/^Backup set: //p' "$WP45_EVIDENCE/backup_second.stdout.txt")"
    check_true "second run created a second directory" '[ -d "$SECOND_SET" ] && [ "$SECOND_SET" != "$BACKUP_SET" ]'
    set_fingerprint "$BACKUP_SET" > "$WP45_EVIDENCE/backup_first_fingerprint_after.txt"
    check "first set unchanged by the second run" \
        "$(cat "$WP45_EVIDENCE/backup_first_fingerprint_after.txt")" \
        "$(cat "$WP45_EVIDENCE/backup_first_fingerprint_before.txt")"
}

# Test 2: restore into a clean root and replay (restore steps 3-8).
test2_restore_and_replay() {  #v1.1
    section "Test 2, step 3: stop the live backend and build the restore root"
    live_stack down --only backend || fail "dev_stack.py down --only backend (live) failed"
    LIVE_BACKEND_STOPPED=1
    check_true "port 8000 no longer answers" '! curl --silent --max-time 5 "$BACKEND_URL/api/health" >/dev/null'
    RESTORE_ROOT="$(mktemp -d "$KAKI_LIVE_DATA_ROOT/wp4.5/restore.XXXXXX")"
    printf 'RESTORE_ROOT=%s\n' "$RESTORE_ROOT"
    observe "restore_root" "$RESTORE_ROOT"
    mkdir -p "$RESTORE_ROOT/sqlite"
    cp "$BACKUP_SET/kaki.db" "$RESTORE_ROOT/sqlite/kaki.db"
    chmod 600 "$RESTORE_ROOT/sqlite/kaki.db"
    cp -R "$BACKUP_SET/corpus" "$RESTORE_ROOT/corpus"
    cp -R "$BACKUP_SET/chroma" "$RESTORE_ROOT/chroma"
    # A mistyped path would start a backend on a fresh empty database with storage_ready true.
    check_true "restored kaki.db exists and is non-empty" '[ -s "$RESTORE_ROOT/sqlite/kaki.db" ]'
    check "restored kaki.db matches the manifest hash" \
        "$(shasum -a 256 "$RESTORE_ROOT/sqlite/kaki.db" | awk '{print $1}')" \
        "$(sed -n 's/^sha256:kaki.db=//p' "$BACKUP_SET/manifest.txt")"
    check "restored copy holds the reference turns" \
        "$(restored_sql "select count(*) from turns where turn_id in ('$ANSWER_TURN_ID', '$REPEAT_TURN_ID');")" "2"

    section "Test 2, step 4: start the backend under the restore root"
    restored_up_rc=0
    restored_stack up --only backend > "$WP45_EVIDENCE/restored_backend_up.txt" 2>&1 || restored_up_rc=$?
    RESTORED_BACKEND_STARTED=1
    cat "$WP45_EVIDENCE/restored_backend_up.txt"
    check "dev_stack.py up --only backend (restore root) exit code" "$restored_up_rc" "0"
    check_true "dev_stack.py printed the restore root as its data root" \
        'grep -qxF "data root: $RESTORE_ROOT" "$WP45_EVIDENCE/restored_backend_up.txt"'
    grep -i 'sqlite' "$RESTORE_ROOT/logs/backend.log" | tail -1 > "$WP45_EVIDENCE/restored_backend_log_sqlite.txt" \
        || fail "no SQLite line in $RESTORE_ROOT/logs/backend.log"
    case "$(cat "$WP45_EVIDENCE/restored_backend_log_sqlite.txt")" in
        *"$RESTORE_ROOT/sqlite/kaki.db"*"schema version $EXPECTED_SCHEMA_VERSION"*)
            printf 'check ok: restored backend log names %s/sqlite/kaki.db at schema version %s\n' \
                "$RESTORE_ROOT" "$EXPECTED_SCHEMA_VERSION" ;;
        *) fail "restored backend log does not name $RESTORE_ROOT/sqlite/kaki.db at schema version $EXPECTED_SCHEMA_VERSION" ;;
    esac
    curl --fail --silent "$BACKEND_URL/api/health" -o "$WP45_EVIDENCE/restored_health.json" \
        || fail "GET /api/health on the restored backend failed"
    check "restored storage_ready" "$(jq -r .storage_ready "$WP45_EVIDENCE/restored_health.json")" "true"
    check "restored retrieval_ready" "$(jq -r .retrieval_ready "$WP45_EVIDENCE/restored_health.json")" "true"

    section "Test 2, step 5: replay both reference turns from the restored copy"
    # Each replay sends the other fixture: re-execution would change the response.
    post_turn restored_answer_replay "$REF_SESSION" "$ANSWER_TURN_ID" "$FIXTURE_DIR/repeat_request.wav"
    post_turn restored_repeat_replay "$REF_SESSION" "$REPEAT_TURN_ID" "$FIXTURE_DIR/cdc_question.wav"
    for pair in "ref_answer restored_answer_replay" "ref_repeat restored_repeat_replay"; do
        original="${pair% *}"
        replayed="${pair#* }"
        if diff <(jq -S . "$WP45_EVIDENCE/$original.json") <(jq -S . "$WP45_EVIDENCE/$replayed.json") \
            > "$WP45_EVIDENCE/${replayed}_diff.txt"; then
            printf 'check ok: %s identical to %s (diff empty)\n' "$replayed" "$original"
        else
            cat "$WP45_EVIDENCE/${replayed}_diff.txt"
            fail "$replayed differs from $original; see ${replayed}_diff.txt"
        fi
    done
    check "answer replay audio sha256" "$(audio_sha restored_answer_replay)" "$ANSWER_AUDIO_SHA"
    check "repeat replay audio sha256" "$(audio_sha restored_repeat_replay)" "$REPEAT_AUDIO_SHA"
    check "restored answer replay_count" \
        "$(restored_sql "select replay_count from turns where turn_id='$ANSWER_TURN_ID';")" "1"
    check "restored repeat replay_count" \
        "$(restored_sql "select replay_count from turns where turn_id='$REPEAT_TURN_ID';")" "1"

    section "Test 2, step 6: new grounded question in a separate session (positive control)"
    llm_before_question="$(llm_count)"
    post_turn restored_question "wp45-restore-question-$(new_uuid)" "$(new_turn_id wp45-question)" \
        "$FIXTURE_DIR/cdc_question.wav"
    LLM_SNAPSHOT="$(llm_count)"
    observe "test2_llm_log_before_question" "$llm_before_question"
    observe "test2_llm_log_after_question" "$LLM_SNAPSHOT"
    check "restored question state" "$(field restored_question .state)" "answered"
    check "restored question sources[0] host" "$(source_host restored_question)" "$CDC_HOST"
    check_true "cross-check control: live llm.log completions rose across the question" \
        '[ "$LLM_SNAPSHOT" -gt "$llm_before_question" ]'

    section "Test 2, step 7: new repeat in the reference session"
    post_turn restored_repeat "$REF_SESSION" "$(new_turn_id wp45-restored-repeat)" "$FIXTURE_DIR/repeat_request.wav"
    llm_after_repeat="$(llm_count)"
    observe "test2_llm_log_after_repeat" "$llm_after_repeat"
    check "restored repeat state" "$(field restored_repeat .state)" "acted"
    check "restored repeat previous_turn_id" "$(field debug_restored_repeat .previous_turn_id)" "$ANSWER_TURN_ID"
    check "restored repeat audio sha256 equals the reference answer" "$(audio_sha restored_repeat)" "$ANSWER_AUDIO_SHA"
    check "cross-check: live llm.log completions unchanged across the repeat" "$llm_after_repeat" "$LLM_SNAPSHOT"

    printf 'Playing the reference answer, then the repeat served from the restored copy.\n'
    afplay "$WP45_EVIDENCE/ref_answer_reply.wav"
    afplay "$WP45_EVIDENCE/restored_repeat_reply.wav"
    judge "test2-audio" "Did the repeat from the restored copy sound the same as the reference answer?"

    section "Test 2, step 8: switch back to the live backend"
    restored_stack down --only backend || fail "dev_stack.py down --only backend (restore root) failed"
    RESTORED_BACKEND_STARTED=0
    live_up_rc=0
    live_stack up --only backend > "$WP45_EVIDENCE/live_backend_up.txt" 2>&1 || live_up_rc=$?
    cat "$WP45_EVIDENCE/live_backend_up.txt"
    check "dev_stack.py up --only backend (live) exit code" "$live_up_rc" "0"
    LIVE_BACKEND_STOPPED=0
    check "live storage_ready" "$(health_field storage_ready)" "true"
    case "$(grep -i 'sqlite' "$KAKI_LIVE_DATA_ROOT/logs/backend.log" | tail -1)" in
        *"$KAKI_DB"*) printf 'check ok: live backend log names %s\n' "$KAKI_DB" ;;
        *) fail "the live backend log does not name $KAKI_DB" ;;
    esac
    check "live turns equal the after-backup count" "$(live_sql 'select count(*) from turns;')" "$turns_after_backup"
    check "live reference answer replay_count" \
        "$(live_sql "select replay_count from turns where turn_id='$ANSWER_TURN_ID';")" "0"
    printf 'Restore copy kept for review: %s\n' "$RESTORE_ROOT"
}

# Test 3: withdrawn under owner decision 1 (runbook 9.1 WP4.5 "Owner decisions").  #v1.1
test3_withdrawn() {  #v1.1
    section "Test 3: withdrawn under owner decision 1"  #v1.1
    printf 'Presenter controls left WP4.5 on 13-Sep-2026. No browser step runs; the owner is not asked.\n'  #v1.1
    observe "test3" "withdrawn under owner decision 1"  #v1.1
}  #v1.1

# Test 4: storage observation. A resumed run observes the newest backup set.
test4_storage_observation() {  #v1.1
    BACKUP_SET="${BACKUP_SET:-$(latest_backup_set)}"  #v1.1
    section "Test 4: storage observation"
    observe "test4_kaki_db_bytes" "$(stat -f '%z' "$KAKI_DB")"
    observe "test4_turns" "$(live_sql 'select count(*) from turns;')"
    live_sql "select coalesce(intent, '-') as intent, count(*) as turns,
                     coalesce(sum(length(reply_audio)), 0) as audio_bytes,
                     cast(coalesce(avg(length(reply_audio)), 0) as integer) as mean_audio_bytes
              from turns group by 1 order by 1;" | tee "$WP45_EVIDENCE/storage_by_intent.txt"
    observe "test4_reply_audio_bytes_total" "$(live_sql 'select coalesce(sum(length(reply_audio)), 0) from turns;')"
    observe "test4_backup_set_kilobytes" "$(du -sk "$BACKUP_SET" | awk '{print $1}')"
    df -h / | tee "$WP45_EVIDENCE/disk_free.txt"
    observe "test4_disk_free" "$(df -h / | awk 'NR == 2 {print $4}')"
}

# Test 5: action regression (WP4-AT-13).
test5_action_regression() {  #v1.1
    section "Test 5: action regression (WP4-AT-13)"
    regression_rc=0
    python scripts/run_regression.py --devset agent/data/devset.jsonl \
        > "$WP45_EVIDENCE/regression_devset.json" 2> "$WP45_EVIDENCE/regression_devset.stderr.txt" \
        || regression_rc=$?
    cat "$WP45_EVIDENCE/regression_devset.stderr.txt"
    printf 'run_regression.py exit code: %s (as reported by the runner)\n' "$regression_rc"
    check "run_regression.py exit code" "$regression_rc" "0"
    report="$WP45_EVIDENCE/regression_devset.json"
    observe "test5_items" "$(jq -r .items "$report")"
    observe "test5_intent_accuracy" "$(jq -r .intent_accuracy "$report")"
    check "intent_accuracy >= $INTENT_TARGET" "$(jq -r ".intent_accuracy >= $INTENT_TARGET" "$report")" "true"
    action_filter='[.results[] | select(.expected_intent == "repeat_previous" or .expected_intent == "print_previous")]'
    action_total="$(jq -r "$action_filter | length" "$report")"
    action_correct="$(jq -r "$action_filter | map(select(.actual_intent == .expected_intent)) | length" "$report")"
    action_result="$(awk -v correct="$action_correct" -v total="$action_total" \
        'BEGIN { printf "%d of %d, %.2f", correct, total, (total > 0 ? correct / total : 0) }')"
    observe "test5_action_items_result" "$action_result"
    check_true "action items present" '[ "$action_total" -gt 0 ]'
    check "action item intents >= $INTENT_TARGET ($action_result)" \
        "$(awk -v correct="$action_correct" -v total="$action_total" -v target="$INTENT_TARGET" \
            'BEGIN { print (total > 0 && correct / total >= target) ? "true" : "false" }')" "true"
    check "golden paths passed equals total" "$(jq -r .golden_paths_passed "$report")" "$(jq -r .golden_paths_total "$report")"
}

# Test 6: regression in the selected mode (WP4-AT-14 needs package mode on the gate commit).
test6_regression() {  #v1.1
    section "Test 6: regression mode $REGRESSION_MODE"  #v1.1
    observe "test6_regression_mode" "$REGRESSION_MODE"  #v1.1
    if [ "$REGRESSION_MODE" = "package" ]; then  #v1.1
        for unit in $PACKAGE_TIER_B_UNITS; do  #v1.1
            run_wp_check "$unit"  #v1.1
        done  #v1.1
    fi  #v1.1
    run_wp_check WP4.5  #v1.1

    section "Test 6: deterministic suites ($REGRESSION_MODE mode)"  #v1.1
    turns_before_suites="$(live_sql 'select count(*) from turns;')"
    run_suite ruff "$KAKI_APP_ROOT" python -m ruff check --config backend/pyproject.toml backend scripts services rag
    run_suite contract "$KAKI_APP_ROOT" python -m unittest discover -s backend/tests/contract -v
    run_suite scripts "$KAKI_APP_ROOT" python -m unittest discover -s scripts/tests -v
    run_suite web_lint "$KAKI_APP_ROOT/apps/web" npm run lint
    run_suite web_test "$KAKI_APP_ROOT/apps/web" npm test
    run_suite web_build "$KAKI_APP_ROOT/apps/web" npm run build
    observe "test6_contract_tests_ran" "$(ran_count contract)"
    observe "test6_scripts_tests_ran" "$(ran_count scripts)"
    observe "test6_web_tests" "$(grep -Eo 'Tests +[0-9]+ passed' "$WP45_EVIDENCE/tier_a_web_test.txt" | tail -1)"
    check_true "WP1 turn schema snapshot test passed" \
        'grep -q "test_turn_response_schema_matches_snapshot .* ok" "$WP45_EVIDENCE/tier_a_contract.txt"'
    check "WP1 turn schema snapshot file unchanged from HEAD" \
        "$(git -C "$KAKI_APP_ROOT" status --porcelain -- "$SCHEMA_SNAPSHOT")" ""
    tracked_runtime="$(git -C "$KAKI_APP_ROOT" ls-files | grep -E '\.db$|\.db-wal$|\.db-shm$|(^|/)chroma/' || true)"
    printf '%s\n' "$tracked_runtime" > "$WP45_EVIDENCE/tracked_runtime_files.txt"
    check "tracked *.db, *.db-wal, *.db-shm or chroma/ paths (X-AT-03)" "$tracked_runtime" ""
    check "live turns unchanged by the deterministic suites" \
        "$(live_sql 'select count(*) from turns;')" "$turns_before_suites"
}

# Teardown: printed, not run.
teardown() {  #v1.1
    section "Teardown"
    printf 'The stack is still running. Stop it when you are done:\n'
    printf '  python scripts/dev_stack.py down\n'
    printf 'The web build replaced apps/web/.next; restart npm start before further browser use.\n'
    printf 'Review, then delete the restore copy: %s\n' "${RESTORE_ROOT:-not created in this run}"
    printf 'Keep the backup sets: %s and %s\n\n' "${BACKUP_SET:-not created in this run}" "${SECOND_SET:-not created in this run}"
    printf 'Harness finished with no failed assertion and no "no" verdict. This is evidence,\n'
    printf 'not the WP4 gate: review it, then complete runbook 9.2 WP4.5 Test 7 yourself.\n'
    printf 'Evidence: %s\n' "$WP45_EVIDENCE"
}

# ---------------------------------------------------------------------------
# Run from the requested test to the end.  #v1.1
# ---------------------------------------------------------------------------

if [ "$FROM_TEST" -le 2 ]; then  #v1.1
    if [ "$FROM_TEST" -eq 2 ]; then  #v1.1
        printf '\nResuming at Test 2: restore steps 1 and 2 run as setup; Test 1 assertions do not.\n'  #v1.1
    fi  #v1.1
    restore_reference_and_backup  #v1.1
fi  #v1.1
[ "$FROM_TEST" -gt 1 ] || test1_backup_assertions  #v1.1
[ "$FROM_TEST" -gt 2 ] || test2_restore_and_replay  #v1.1
[ "$FROM_TEST" -gt 3 ] || test3_withdrawn  #v1.1
[ "$FROM_TEST" -gt 4 ] || test4_storage_observation  #v1.1
[ "$FROM_TEST" -gt 5 ] || test5_action_regression  #v1.1
test6_regression  #v1.1
teardown  #v1.1
