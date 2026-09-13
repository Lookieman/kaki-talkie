#!/usr/bin/env bash
# v1.2 | 13-Sep-2026 | Drop the buffered whisper.log cross-checks; add an llm.log positive control.
# v1.1 | 13-Sep-2026 | Test 4 replays the repeat too; the debug check follows the newest-turn contract.
# v1.0 | 13-Sep-2026 | Owner evidence harness for runbook 9.2 WP4.2 Tests 1-8 and fixture capture.
#
# Capture WP4.2 validation evidence on the Mac by running the runbook 9.2
# WP4.2 test block in order: the automated runner, then Tests 1-8.
#
# This is the owner's evidence harness, not the gate. It runs every
# machine-decided step, asserts the runbook's expected observations and stops
# with a non-zero exit at the first failed assertion. scripts/wp_check.py stays
# the automated gate: the harness records what each wp_check run reported, with
# its exit code, and prints no verdict on its behalf. Judgement steps (audio,
# answer sense, the rendered receipt) stop and ask the owner, who types yes or
# no; the verdict is written to judgements.txt and a "no" ends the run with a
# non-zero exit. The owner marks the runbook block VERIFIED.
#
# Modes:
#   scripts/wp4_2_evidence.sh                     run the WP4.2 test block
#   scripts/wp4_2_evidence.sh --capture-fixtures  create the two spoken fixtures
#   scripts/wp4_2_evidence.sh -h | --help         show this text
#
# Prerequisites for the test block: the grounded stack is running
# (python scripts/dev_stack.py up) from the WP4.2 checkout, the simulator is
# built and started from the same checkout (cd apps/web && npm run build &&
# npm start), the shell has the WP4.2 environment (source scripts/kaki_env.sh
# WP4.2), both fixtures exist, and the run is in an interactive terminal.
#
# Side effects of the test block:
#   - Creates $WP42_EVIDENCE (a new directory under $KAKI_DATA_ROOT/wp4.2
#     unless an empty one is already exported) and writes evidence there,
#     starting with run-header.txt; transcript.txt receives the whole run.
#   - Posts turns to the live backend (Tests 2-5); wp_check and the owner's
#     browser steps post their own. All are stored in $KAKI_DB, as intended.
#   - Restarts the backend only, through dev_stack.py (Test 4).
#   - Runs the devset regression (Test 6), which loads a second embedding model.
#   - Runs the deterministic suites and the web lint, test and build (Test 8).
#     The build rewrites apps/web/.next; restart the simulator afterwards.
#   - Does not stop the stack. It prints the teardown command instead.
#
# Side effects of --capture-fixtures: writes repeat_request.wav and
# print_request.wav into backend/src/kaki_backend/fixtures/ with macOS say,
# refuses to overwrite either file, removes a file it just wrote if it holds no
# audio, and records the format, duration and owner verdicts in $WP42_EVIDENCE.
#
# Exit status: 0 when every step ran, every assertion held and every verdict
# was yes; 1 on a failed assertion, failed command or a "no" verdict; 2 on a
# usage or precondition error; 3 when fixtures were written but no terminal
# was available for the owner's listening verdict.

set -Eeuo pipefail

BACKEND_URL="http://127.0.0.1:8000"
SIMULATOR_URL="http://127.0.0.1:3000/sim"
SMOKE_DEVICE="wp42-smoke"
CDC_HOST="vouchers.cdc.gov.sg"
EXPECTED_SCHEMA_VERSION=2
PRINT_CONFIRMATION="Here is your slip."
NOTHING_TO_ACT_ON="I have not answered a question yet. Please ask me first."
RECEIPT_WIDTH=32
FIXTURE_DIR_RELATIVE="backend/src/kaki_backend/fixtures"
FIXTURE_VOICE="Samantha"
REPEAT_FIXTURE="repeat_request.wav"
REPEAT_TEXT="Can you repeat that?"
PRINT_FIXTURE="print_request.wav"
PRINT_TEXT="Please print that for me."
# Written per request by http.server to stderr, which stays line-buffered when
# redirected; dev_stack.py also sets PYTHONUNBUFFERED=1 for MLX-LM. There is no
# whisper.log cross-check: whisper-server writes its per-inference line to
# block-buffered stdout, so the count lags (runbook 9.2 WP4.2 "Log cross-checks").
LLM_LOG_PATTERN="POST /v1/chat/completions"

usage() {
    sed -n '4,47p' "$0" | sed 's/^# \{0,1\}//'
}

MODE="tests"
case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    --capture-fixtures) MODE="capture" ;;
    "") ;;
    *) printf 'Unknown argument: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    printf 'Too many arguments.\n\n' >&2; usage >&2; exit 2
fi

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

require_tools() {
    local tool
    for tool in "$@"; do
        command -v "$tool" >/dev/null || precondition "$tool is not on PATH." \
            "install $tool (setup.md 5.2); macOS provides say, afinfo, afplay and uuidgen"
    done
}

# Use an exported empty WP42_EVIDENCE, or create a new directory under the data root.
prepare_evidence_dir() {
    umask 077
    if [ -n "${WP42_EVIDENCE:-}" ]; then
        [ -d "$WP42_EVIDENCE" ] || precondition "WP42_EVIDENCE does not exist: $WP42_EVIDENCE" \
            "unset WP42_EVIDENCE to let the harness create a new directory"
        [ -z "$(ls -A "$WP42_EVIDENCE")" ] || precondition \
            "WP42_EVIDENCE already holds evidence: $WP42_EVIDENCE" \
            "unset WP42_EVIDENCE to let the harness create a new directory"
    else
        if [ -z "${KAKI_DATA_ROOT:-}" ]; then
            precondition "KAKI_DATA_ROOT is unset." \
                "source scripts/kaki_env.sh WP4.2  (or export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data)"
        fi
        mkdir -p "$KAKI_DATA_ROOT/wp4.2" || precondition \
            "cannot create $KAKI_DATA_ROOT/wp4.2." "check the data root permissions (setup.md 12.3)"
        WP42_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp4.2/evidence.XXXXXX")"
    fi
    export WP42_EVIDENCE
}

# Ask the owner for a verdict; record it; a "no" ends the run. Never prints PASS.
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
        >> "$WP42_EVIDENCE/judgements.txt"
    printf 'owner verdict recorded for %s: %s\n' "$step" "$answer"
    if [ "$answer" = "no" ]; then
        fail "owner verdict no for $step: $note"
    fi
}

# ---------------------------------------------------------------------------
# Mode: capture the two spoken fixtures.
# ---------------------------------------------------------------------------

capture_fixture() {
    local name="$1" text="$2" path="$FIXTURE_DIR/$1" info audio_bytes duration
    say -v "$FIXTURE_VOICE" --file-format=WAVE --data-format=LEI16@16000 -o "$path" "$text"
    info="$(afinfo "$path")"
    printf '%s\n' "$info" > "$WP42_EVIDENCE/afinfo_${name%.wav}.txt"
    audio_bytes="$(printf '%s\n' "$info" | awk -F': *' '/^audio bytes/ {print $2}')"
    duration="$(printf '%s\n' "$info" | awk '/estimated duration/ {print $3}')"
    if [ -z "$audio_bytes" ] || [ "$audio_bytes" -eq 0 ]; then
        rm -f "$path"
        fail "say wrote $name with no audio (audio bytes ${audio_bytes:-unknown}); removed it. Run from a logged-in Terminal session where say can speak."
    fi
    case "$info" in
        *"1 ch,  16000 Hz, Int16"*) printf 'check ok: %s is 16 kHz mono Int16\n' "$name" ;;
        *) rm -f "$path"; fail "$name is not 16 kHz mono Int16; removed it" ;;
    esac
    printf '%s | text=%s | voice=%s | duration_seconds=%s | audio_bytes=%s | sha256=%s\n' \
        "$name" "$text" "$FIXTURE_VOICE" "$duration" "$audio_bytes" \
        "$(shasum -a 256 "$path" | awk '{print $1}')" >> "$WP42_EVIDENCE/fixtures.txt"
    printf 'observation: %s duration %s s (no threshold)\n' "$name" "$duration"
}

if [ "$MODE" = "capture" ]; then
    require_tools say afinfo afplay shasum
    for name in "$REPEAT_FIXTURE" "$PRINT_FIXTURE"; do
        if [ -e "$FIXTURE_DIR/$name" ]; then
            precondition "$FIXTURE_DIR_RELATIVE/$name already exists; fixtures are never regenerated." \
                "keep it, or delete it deliberately (git rm) before recapturing"
        fi
    done
    prepare_evidence_dir
    exec > >(tee -a "$WP42_EVIDENCE/transcript.txt") 2>&1
    printf 'Evidence: %s\n' "$WP42_EVIDENCE"
    { date; date -u; git -C "$KAKI_APP_ROOT" rev-parse HEAD; sw_vers -productVersion; } \
        > "$WP42_EVIDENCE/run-header.txt" 2>&1
    capture_fixture "$REPEAT_FIXTURE" "$REPEAT_TEXT"
    capture_fixture "$PRINT_FIXTURE" "$PRINT_TEXT"
    if ! has_tty; then
        printf 'Fixtures written, but no terminal is available for the listening verdict.\n'
        printf 'Listen with afplay and record the verdict before committing them.\n'
        printf 'Evidence: %s\n' "$WP42_EVIDENCE"
        exit 3
    fi
    afplay "$FIXTURE_DIR/$REPEAT_FIXTURE"
    judge "capture-repeat" "Did you hear exactly \"$REPEAT_TEXT\", clearly?"
    afplay "$FIXTURE_DIR/$PRINT_FIXTURE"
    judge "capture-print" "Did you hear exactly \"$PRINT_TEXT\", clearly?"
    printf 'Record the exact text in %s/README.md, then commit both fixtures.\n' "$FIXTURE_DIR_RELATIVE"
    printf 'Evidence: %s\n' "$WP42_EVIDENCE"
    exit 0
fi

# ---------------------------------------------------------------------------
# Preconditions for the test block, checked before any evidence is written.
# ---------------------------------------------------------------------------

if [ -z "${KAKI_DATA_ROOT:-}" ]; then
    precondition "KAKI_DATA_ROOT is unset." \
        "source scripts/kaki_env.sh WP4.2  (or run the runbook 9.2 WP4.1 Session setup block)"
fi
case "$KAKI_DATA_ROOT" in
    /*) ;;
    *) precondition "KAKI_DATA_ROOT is not absolute: $KAKI_DATA_ROOT" \
           "export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data" ;;
esac

require_tools jq sqlite3 uuidgen curl afplay base64 shasum fold npm

KAKI_DB="${KAKI_DB:-${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}}"
if [ ! -f "$KAKI_DB" ]; then
    precondition "the database is missing: $KAKI_DB" \
        "python scripts/dev_stack.py up  (the backend creates the database at start)"
fi

if ! curl --fail --silent --max-time 10 "$BACKEND_URL/api/health" >/dev/null; then
    precondition "the backend is not answering on 127.0.0.1:8000." \
        "python scripts/dev_stack.py up  then  python scripts/dev_stack.py status"
fi

schema_version="$(sqlite3 "$KAKI_DB" 'pragma user_version;')"
if [ "$schema_version" != "$EXPECTED_SCHEMA_VERSION" ]; then
    precondition "the database is at schema version $schema_version, not $EXPECTED_SCHEMA_VERSION." \
        "restart the backend from the WP4.2 checkout: python scripts/dev_stack.py down --only backend && python scripts/dev_stack.py up --only backend"
fi

for name in cdc_question.wav "$REPEAT_FIXTURE" "$PRINT_FIXTURE"; do
    if [ ! -s "$FIXTURE_DIR/$name" ]; then
        precondition "the fixture $FIXTURE_DIR_RELATIVE/$name is missing." \
            "scripts/wp4_2_evidence.sh --capture-fixtures  (runbook 9.1 WP4.2 Fixture capture)"
    fi
done

if ! curl --fail --silent --max-time 10 "$SIMULATOR_URL" >/dev/null; then
    precondition "the simulator is not answering on $SIMULATOR_URL." \
        "cd apps/web && npm run build && npm start  (from the WP4.2 checkout)"
fi

if ! has_tty; then
    precondition "no interactive terminal; the block has owner judgement steps." \
        "run scripts/wp4_2_evidence.sh from Terminal, not through a pipe"
fi

if ! python -c "import kaki_backend" 2>/dev/null; then
    precondition "python cannot import kaki_backend." "source \"$KAKI_APP_ROOT/.venv/bin/activate\""
fi

for setting in KAKI_RETRIEVAL_MODE=rag KAKI_LLM_MODE=qwen KAKI_TTS_MODE=say KAKI_STT_MODE=whisper; do
    name="${setting%%=*}"
    wanted="${setting#*=}"
    actual="${!name:-}"
    if [ "$actual" != "$wanted" ]; then
        precondition "$name is '${actual:-unset}', expected '$wanted'." "source scripts/kaki_env.sh WP4.2"
    fi
done

LLM_LOG="$KAKI_DATA_ROOT/logs/llm.log"
for log in "$LLM_LOG" "$KAKI_DATA_ROOT/logs/backend.log"; do
    [ -f "$log" ] || precondition "log not found: $log" \
        "start the stack with python scripts/dev_stack.py up, which writes the service logs"
done

# ---------------------------------------------------------------------------
# Evidence directory, run header, transcript.
# ---------------------------------------------------------------------------

prepare_evidence_dir
export KAKI_DB KAKI_APP_ROOT

header_item() {
    local label="$1" output
    shift
    if output="$("$@" 2>&1)"; then
        printf '%s:\n%s\n\n' "$label" "$output"
    else
        printf '%s:\nunavailable (%s)\n\n' "$label" "$output"
    fi
}

python_identity() {
    python - <<'EOF'
import sqlite3
import sys
from importlib.metadata import PackageNotFoundError, version

from kaki_backend.config import APPROVED_EMBEDDING_MODEL, APPROVED_QWEN_MODEL

print("python", sys.version.split()[0])
print("python sqlite3 library", sqlite3.sqlite_version)
for package in ("kaki-backend", "kaki-rag", "kaki-whisper-cpp", "kaki-qwen-local",
                "kaki-say-tts"):
    try:
        print(package, version(package))
    except PackageNotFoundError:
        print(package, "not installed")
print("approved LLM model", APPROVED_QWEN_MODEL)
print("approved embedding model", APPROVED_EMBEDDING_MODEL)
EOF
}

env_settings_dump() {
    local name
    for name in KAKI_STT_MODE KAKI_WHISPER_URL KAKI_STT_TIMEOUT_SECONDS KAKI_LLM_MODE \
        KAKI_LLM_URL KAKI_LLM_TIMEOUT_SECONDS KAKI_TTS_MODE KAKI_TTS_TIMEOUT_SECONDS \
        KAKI_RETRIEVAL_MODE KAKI_QUERY_NORMALISE KAKI_EVIDENCE_MIN_DENSE KAKI_EMBEDDING_MODEL \
        KAKI_SQLITE_PATH HF_HOME; do
        printf '%s=%s\n' "$name" "${!name:-unset}"
    done
}

HF_HOME_DIR="${HF_HOME:-$HOME/models/huggingface}"
WHISPER_MODEL="${KAKI_WHISPER_MODEL:-$HOME/models/whisper/ggml-large-v3-turbo.bin}"
LLM_PYTHON="${KAKI_LLM_PYTHON:-$HOME/.venvs/kaki-llm/bin/python}"

{
    printf 'KaKi-Talkie WP4.2 evidence run header\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    header_item "git uncommitted changes" git -C "$KAKI_APP_ROOT" status --short
    printf 'KAKI_APP_ROOT: %s\nKAKI_DATA_ROOT: %s\nKAKI_DB: %s\nWP42_EVIDENCE: %s\n\n' \
        "$KAKI_APP_ROOT" "$KAKI_DATA_ROOT" "$KAKI_DB" "$WP42_EVIDENCE"
    header_item "database schema version" sqlite3 "$KAKI_DB" "pragma user_version;"
    header_item "adapter settings" env_settings_dump
    header_item "macOS version (identifies the say engine)" sw_vers -productVersion
    header_item "sqlite3 CLI" sqlite3 --version
    header_item "node" node --version
    header_item "backend Python packages and approved models" python_identity
    header_item "backend health" curl --fail --silent --max-time 30 "$BACKEND_URL/api/health"
    header_item "mlx-lm" "$LLM_PYTHON" -c "import mlx_lm; print('mlx-lm', mlx_lm.__version__)"
    header_item "MLX-LM served models" curl --fail --silent --max-time 10 http://127.0.0.1:8082/v1/models
    header_item "Qwen snapshot" ls "$HF_HOME_DIR/hub/models--mlx-community--Qwen3-8B-4bit/snapshots"
    header_item "embedding snapshot" ls "$HF_HOME_DIR/hub/models--Qwen--Qwen3-Embedding-0.6B/snapshots"
    header_item "whisper.cpp describe" git -C "$HOME/src/whisper.cpp" describe --tags --always
    header_item "whisper.cpp commit" git -C "$HOME/src/whisper.cpp" rev-parse HEAD
    header_item "whisper model sha256" shasum -a 256 "$WHISPER_MODEL"
    header_item "fixture sha256" shasum -a 256 "$FIXTURE_DIR/$REPEAT_FIXTURE" "$FIXTURE_DIR/$PRINT_FIXTURE"
} > "$WP42_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP42_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP42_EVIDENCE"
printf 'Database: %s\n' "$KAKI_DB"
printf 'Run header written: %s/run-header.txt\n' "$WP42_EVIDENCE"

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

observe() {
    printf 'observation: %s = %s\n' "$1" "$2"
    printf '%s = %s\n' "$1" "$2" >> "$WP42_EVIDENCE/observations.txt"
}

sql() {
    sqlite3 "$KAKI_DB" "$1"
}

new_uuid() {
    uuidgen | tr '[:upper:]' '[:lower:]'
}

new_turn_id() {
    printf '%s-%s' "$1" "$(new_uuid)"
}

# Count matching log lines after a short flush pause; zero matches is a count, not an error.
log_count() {
    sleep 1
    grep -c "$2" "$1" || true
}

# POST one fixture; write the response to <tag>.json and the debug view to debug_<tag>.json.
post_turn() {
    local tag="$1" session="$2" turn_id="$3" audio="$4" seconds
    if ! seconds="$(curl --fail --silent --show-error --max-time 300 "$BACKEND_URL/api/device/turn" \
        -F "device_id=$SMOKE_DEVICE" -F "session_id=$session" -F "turn_id=$turn_id" \
        -F "audio=@$audio" -o "$WP42_EVIDENCE/$tag.json" -w '%{time_total}')"; then
        fail "POST /api/device/turn ($tag) failed"
    fi
    if ! curl --fail --silent "$BACKEND_URL/api/device/debug/last-turn" \
        -o "$WP42_EVIDENCE/debug_$tag.json"; then
        fail "GET /api/device/debug/last-turn after $tag failed"
    fi
    observe "${tag}_elapsed_seconds" "$seconds"
    jq -c '{state, reply_text, slip_words: (.slip_text | split(" ") | length), sources: (.sources | length)}' \
        "$WP42_EVIDENCE/$tag.json"
    jq -c '{turn_id, intent, transcript, previous_turn_id, action_outcome, timings_ms}' \
        "$WP42_EVIDENCE/debug_$tag.json"
}

field() {
    jq -r "$2" "$WP42_EVIDENCE/$1.json"
}

audio_to_wav() {
    jq -r '.reply_audio // empty' "$WP42_EVIDENCE/$1.json" \
        | sed 's#^data:audio/wav;base64,##' | base64 -D > "$WP42_EVIDENCE/$2"
}

source_rows() {
    sql "select position, source_id, source_url, chunk_id, cited from turn_sources
         where turn_id='$1' order by position;"
}

run_wp_check() {
    local unit="$1" tag rc=0
    tag="$(printf '%s' "$unit" | tr -d '.' | tr '[:upper:]' '[:lower:]')"
    local stdout_file="$WP42_EVIDENCE/wp_check_${tag}_tierB.json"
    local stderr_file="$WP42_EVIDENCE/wp_check_${tag}_tierB.stderr.txt"
    python scripts/wp_check.py --unit "$unit" --tier B >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$WP42_EVIDENCE/wp_check_${tag}_tierB.exit.txt"
    cat "$stdout_file" "$stderr_file"
    printf 'wp_check %s tier B exit code: %s (as reported by wp_check)\n' "$unit" "$rc"
    [ "$rc" -eq 0 ] || fail "wp_check $unit tier B exited $rc; see $stderr_file"
}

run_suite() {
    local name="$1" directory="$2" rc=0
    shift 2
    local output_file="$WP42_EVIDENCE/tier_a_${name}.txt"
    (cd "$directory" && "$@") >"$output_file" 2>&1 || rc=$?
    cat "$output_file"
    printf 'tier A %s exit code: %s\n' "$name" "$rc"
    [ "$rc" -eq 0 ] || fail "tier A $name exited $rc; see $output_file"
}

ran_count() {
    grep -Eo '^Ran [0-9]+ tests?' "$WP42_EVIDENCE/tier_a_$1.txt" | awk '{print $2}' | tail -1
}

wait_for_owner() {
    printf '\nOWNER ACTION: %s\n' "$1"
    read -r -p 'Press Enter when done. ' _ </dev/tty
}

# ---------------------------------------------------------------------------
# Automated runner.
# ---------------------------------------------------------------------------

section "Automated runner: wp_check WP4.2 tier B"
run_wp_check WP4.2

# ---------------------------------------------------------------------------
# Test 1: schema and storage readiness.
# ---------------------------------------------------------------------------

section "Test 1: schema and storage readiness"
curl --fail --silent "$BACKEND_URL/api/health" -o "$WP42_EVIDENCE/health.json" || fail "GET /api/health failed"
jq '{storage_ready, retrieval_ready}' "$WP42_EVIDENCE/health.json"
check "health storage_ready" "$(jq -r '.storage_ready' "$WP42_EVIDENCE/health.json")" "true"
sqlite3 "$KAKI_DB" ".tables" "pragma user_version;" "pragma table_info(turns);" > "$WP42_EVIDENCE/schema.txt"
cat "$WP42_EVIDENCE/schema.txt"
check "user_version" "$(sql 'pragma user_version;')" "$EXPECTED_SCHEMA_VERSION"
check "tables" "$(sql "select group_concat(name, ' ') from (select name from sqlite_master where type='table' order by name);")" \
    "devices sessions turn_sources turns"
check "previous_turn_id nullable" "$(sql "select \"notnull\" from pragma_table_info('turns') where name='previous_turn_id';")" "0"
check "action_outcome nullable" "$(sql "select \"notnull\" from pragma_table_info('turns') where name='action_outcome';")" "0"
grep -i 'sqlite' "$KAKI_DATA_ROOT/logs/backend.log" | tail -1 > "$WP42_EVIDENCE/backend_log_sqlite.txt" \
    || fail "no SQLite line in backend.log"
case "$(cat "$WP42_EVIDENCE/backend_log_sqlite.txt")" in
    *"$KAKI_DB"*"schema version $EXPECTED_SCHEMA_VERSION"*) printf 'check ok: backend log names %s at schema version %s\n' "$KAKI_DB" "$EXPECTED_SCHEMA_VERSION" ;;
    *) fail "backend log does not name $KAKI_DB at schema version $EXPECTED_SCHEMA_VERSION" ;;
esac
observe "test1_turn_rows" "$(sql 'select count(*) from turns;')"
observe "test1_turn_source_rows" "$(sql 'select count(*) from turn_sources;')"

# ---------------------------------------------------------------------------
# Test 2: repeat_previous (WP4-AT-04).
# ---------------------------------------------------------------------------

section "Test 2: repeat_previous (WP4-AT-04)"
# Tests 2-4 share this session; Test 4 repeats in it after the restart.
ACTION_SESSION_ID="wp42-session-$(new_uuid)"
readonly ACTION_SESSION_ID
ANSWER_TURN_ID="$(new_turn_id wp42-answer)"
# Test 4 replays this repeat on purpose; the id is set once, here.
REPEAT_REPLAY_TURN_ID="$(new_turn_id wp42-repeat)"
readonly ANSWER_TURN_ID REPEAT_REPLAY_TURN_ID
printf 'ACTION_SESSION_ID=%s\nANSWER_TURN_ID=%s\nREPEAT_REPLAY_TURN_ID=%s\n' \
    "$ACTION_SESSION_ID" "$ANSWER_TURN_ID" "$REPEAT_REPLAY_TURN_ID"

llm_before_answer="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
post_turn answer "$ACTION_SESSION_ID" "$ANSWER_TURN_ID" "$FIXTURE_DIR/cdc_question.wav"
llm_after_answer="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
observe "test2_llm_log_before_answer" "$llm_before_answer"
observe "test2_llm_log_after_answer" "$llm_after_answer"
# Positive control: the count must move for a turn that calls the model, or
# "unchanged" on the repeat below would prove nothing.
check "cross-check control: llm.log completions rose across the answer turn" \
    "$([ "$llm_after_answer" -gt "$llm_before_answer" ] && echo true || echo false)" "true"
check "answer state" "$(field answer .state)" "answered"
check "answer sources[0] host" \
    "$(field answer '.sources[0].source_url' | sed -E 's#^https?://([^/:]+).*#\1#')" "$CDC_HOST"

llm_before="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
post_turn repeat "$ACTION_SESSION_ID" "$REPEAT_REPLAY_TURN_ID" "$FIXTURE_DIR/$REPEAT_FIXTURE"
llm_after="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
observe "test2_repeat_transcript" "$(field debug_repeat .transcript)"

check "repeat state" "$(field repeat .state)" "acted"
for key in reply_text display_text language; do
    check "repeat $key unchanged" "$(field repeat ".$key")" "$(field answer ".$key")"
done
check "repeat sources unchanged" "$(field repeat '.sources | tojson')" "$(field answer '.sources | tojson')"
check "repeat slip_text" "$(field repeat .slip_text)" ""
audio_to_wav answer answer_reply.wav
audio_to_wav repeat repeat_reply.wav
check "repeat reply_audio sha256" "$(shasum -a 256 < "$WP42_EVIDENCE/repeat_reply.wav" | awk '{print $1}')" \
    "$(shasum -a 256 < "$WP42_EVIDENCE/answer_reply.wav" | awk '{print $1}')"
check "debug intent" "$(field debug_repeat .intent)" "repeat_previous"
check "debug previous_turn_id" "$(field debug_repeat .previous_turn_id)" "$ANSWER_TURN_ID"
check "debug action_outcome" "$(field debug_repeat .action_outcome)" "resolved"
for stage in retrieval_ms llm_ms tts_ms; do
    check "debug $stage" "$(field debug_repeat ".timings_ms.$stage")" "null"
done
check "debug best_dense_score" "$(field debug_repeat .best_dense_score)" "null"
check "debug stt_ms > 0" "$(field debug_repeat '.timings_ms.stt_ms > 0')" "true"
check "stored previous_turn_id" "$(sql "select previous_turn_id from turns where turn_id='$REPEAT_REPLAY_TURN_ID';")" "$ANSWER_TURN_ID"
source_rows "$ANSWER_TURN_ID" > "$WP42_EVIDENCE/answer_source_rows.txt"
source_rows "$REPEAT_REPLAY_TURN_ID" > "$WP42_EVIDENCE/repeat_source_rows.txt"
check "repeat turn_sources rows equal the answer's" \
    "$(cat "$WP42_EVIDENCE/repeat_source_rows.txt")" "$(cat "$WP42_EVIDENCE/answer_source_rows.txt")"
observe "test2_llm_log_before" "$llm_before"
observe "test2_llm_log_after" "$llm_after"
check "cross-check: llm.log completions unchanged across the repeat" "$llm_after" "$llm_before"

printf 'Playing the answer reply, then the repeat reply.\n'
afplay "$WP42_EVIDENCE/answer_reply.wav"
afplay "$WP42_EVIDENCE/repeat_reply.wav"
judge "test2-audio" "Did the repeat sound the same as the answer, and was the answer clear?"

# ---------------------------------------------------------------------------
# Test 3: print_previous (WP4-AT-05).
# ---------------------------------------------------------------------------

section "Test 3: print_previous (WP4-AT-05)"
# Test 4 replays this print on purpose; the id is set once, here.
PRINT_REPLAY_TURN_ID="$(new_turn_id wp42-print)"
SECOND_REPEAT_TURN_ID="$(new_turn_id wp42-repeat2)"
readonly PRINT_REPLAY_TURN_ID SECOND_REPEAT_TURN_ID
printf 'PRINT_REPLAY_TURN_ID=%s\nSECOND_REPEAT_TURN_ID=%s\n' "$PRINT_REPLAY_TURN_ID" "$SECOND_REPEAT_TURN_ID"

llm_before="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
post_turn print "$ACTION_SESSION_ID" "$PRINT_REPLAY_TURN_ID" "$FIXTURE_DIR/$PRINT_FIXTURE"
post_turn repeat2 "$ACTION_SESSION_ID" "$SECOND_REPEAT_TURN_ID" "$FIXTURE_DIR/$REPEAT_FIXTURE"
llm_after="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
observe "test3_print_transcript" "$(field debug_print .transcript)"

check "print state" "$(field print .state)" "acted"
check "print slip_text equals stored answer slip" "$(field print .slip_text)" \
    "$(sql "select slip_text from turns where turn_id='$ANSWER_TURN_ID';")"
check "print slip_text non-empty" "$(field print '.slip_text | length > 0')" "true"
check "print reply_text" "$(field print .reply_text)" "$PRINT_CONFIRMATION"
check "print sources unchanged" "$(field print '.sources | tojson')" "$(field answer '.sources | tojson')"
check "debug intent" "$(field debug_print .intent)" "print_previous"
check "debug previous_turn_id is the answer, not the repeat" "$(field debug_print .previous_turn_id)" "$ANSWER_TURN_ID"
check "debug retrieval_ms" "$(field debug_print .timings_ms.retrieval_ms)" "null"
check "debug llm_ms" "$(field debug_print .timings_ms.llm_ms)" "null"
check "second repeat intent" "$(field debug_repeat2 .intent)" "repeat_previous"
check "second repeat previous_turn_id" "$(field debug_repeat2 .previous_turn_id)" "$ANSWER_TURN_ID"
observe "test3_llm_log_before" "$llm_before"
observe "test3_llm_log_after" "$llm_after"
check "cross-check: llm.log completions unchanged across print and repeat" "$llm_after" "$llm_before"

printf '\nPrinted slip at %s characters:\n' "$RECEIPT_WIDTH"
field print .slip_text | fold -s -w "$RECEIPT_WIDTH" | tee "$WP42_EVIDENCE/print_slip_wrapped.txt"
judge "test3-slip" "Does this read as a sensible printed slip for the CDC voucher answer?"

# ---------------------------------------------------------------------------
# Test 4: action idempotency and restart.
# ---------------------------------------------------------------------------

section "Test 4: action idempotency and restart"
turn_rows_before="$(sql 'select count(*) from turns;')"
# Different audio on purpose: re-execution would swap print and repeat, so an
# identical response proves STT and the pipeline did not run.
post_turn print_replay "$ACTION_SESSION_ID" "$PRINT_REPLAY_TURN_ID" "$FIXTURE_DIR/$REPEAT_FIXTURE"
post_turn repeat_replay "$ACTION_SESSION_ID" "$REPEAT_REPLAY_TURN_ID" "$FIXTURE_DIR/$PRINT_FIXTURE"
for replayed in print repeat; do
    if diff <(jq -S . "$WP42_EVIDENCE/$replayed.json") <(jq -S . "$WP42_EVIDENCE/${replayed}_replay.json") \
        > "$WP42_EVIDENCE/${replayed}_replay_diff.txt"; then
        printf 'check ok: %s replay identical (diff empty)\n' "$replayed"
    else
        cat "$WP42_EVIDENCE/${replayed}_replay_diff.txt"
        fail "$replayed replay differs from the original; see ${replayed}_replay_diff.txt"
    fi
done
check "stored print replay_count" "$(sql "select replay_count from turns where turn_id='$PRINT_REPLAY_TURN_ID';")" "1"
check "stored repeat replay_count" "$(sql "select replay_count from turns where turn_id='$REPEAT_REPLAY_TURN_ID';")" "1"
# The debug view shows the newest executed turn; replays write no row, so it stays on the second repeat.
check "debug turn_id after both replays" "$(field debug_repeat_replay .turn_id)" "$SECOND_REPEAT_TURN_ID"
check "debug replay_count after both replays" "$(field debug_repeat_replay .replay_count)" "0"
check "total turns unchanged by the replays" "$(sql 'select count(*) from turns;')" "$turn_rows_before"

python scripts/dev_stack.py down --only backend || fail "dev_stack.py down --only backend failed"
python scripts/dev_stack.py up --only backend \
    || fail "dev_stack.py up --only backend failed; see $KAKI_DATA_ROOT/logs/backend.log"
curl --fail --silent "$BACKEND_URL/api/health" -o "$WP42_EVIDENCE/health_after_restart.json" \
    || fail "GET /api/health after restart failed"
check "storage_ready after restart" "$(jq -r .storage_ready "$WP42_EVIDENCE/health_after_restart.json")" "true"
post_turn repeat_after_restart "$ACTION_SESSION_ID" "$(new_turn_id wp42-repeat3)" "$FIXTURE_DIR/$REPEAT_FIXTURE"
check "repeat after restart state" "$(field repeat_after_restart .state)" "acted"
check "repeat after restart previous_turn_id" "$(field debug_repeat_after_restart .previous_turn_id)" "$ANSWER_TURN_ID"
check "repeat after restart reply_text" "$(field repeat_after_restart .reply_text)" "$(field answer .reply_text)"

# ---------------------------------------------------------------------------
# Test 5: nothing to act on and session isolation.
# ---------------------------------------------------------------------------

section "Test 5: nothing to act on and session isolation"
LONELY_TURN_ID="$(new_turn_id wp42-lonely)"
readonly LONELY_TURN_ID
llm_before="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
post_turn lonely "wp42-empty-session-$(new_uuid)" "$LONELY_TURN_ID" "$FIXTURE_DIR/$REPEAT_FIXTURE"
llm_after="$(log_count "$LLM_LOG" "$LLM_LOG_PATTERN")"
check "state" "$(field lonely .state)" "acted"
check "reply_text" "$(field lonely .reply_text)" "$NOTHING_TO_ACT_ON"
check "slip_text" "$(field lonely .slip_text)" ""
check "sources" "$(field lonely '.sources | length')" "0"
check "debug intent" "$(field debug_lonely .intent)" "repeat_previous"
check "debug previous_turn_id" "$(field debug_lonely .previous_turn_id)" "null"
check "debug action_outcome" "$(field debug_lonely .action_outcome)" "nothing_to_act_on"
check "turn_sources rows" "$(sql "select count(*) from turn_sources where turn_id='$LONELY_TURN_ID';")" "0"
check "stored action_outcome" "$(sql "select action_outcome from turns where turn_id='$LONELY_TURN_ID';")" "nothing_to_act_on"
observe "test5_llm_log_before" "$llm_before"
observe "test5_llm_log_after" "$llm_after"
check "cross-check: llm.log completions unchanged" "$llm_after" "$llm_before"

# ---------------------------------------------------------------------------
# Test 6: devset regression.
# ---------------------------------------------------------------------------

section "Test 6: devset regression"
regression_rc=0
python scripts/run_regression.py --devset agent/data/devset.jsonl \
    > "$WP42_EVIDENCE/regression_devset.json" 2> "$WP42_EVIDENCE/regression_devset.stderr.txt" \
    || regression_rc=$?
cat "$WP42_EVIDENCE/regression_devset.stderr.txt"
printf 'run_regression.py exit code: %s (as reported by the runner)\n' "$regression_rc"
[ "$regression_rc" -eq 0 ] || fail "run_regression.py exited $regression_rc"
report="$WP42_EVIDENCE/regression_devset.json"
observe "test6_items" "$(jq -r .items "$report")"
observe "test6_items_passed" "$(jq -r .items_passed "$report")"
observe "test6_intent_accuracy" "$(jq -r .intent_accuracy "$report")"
observe "test6_golden_paths" "$(jq -r '"\(.golden_paths_passed) of \(.golden_paths_total)"' "$report")"
jq -r '.results[] | select(.expected_intent == "repeat_previous" or .expected_intent == "print_previous" or .id == "cdc-print-procedural")
    | "\(.id) intent=\(.actual_intent) state=\(.actual_state) previous=\(.previous_turn_id) outcome=\(.action_outcome) passed=\(.passed)"' "$report"
check "runner verdict: action items and the guard item all passed" \
    "$(jq -r '[.results[] | select(.expected_intent == "repeat_previous" or .expected_intent == "print_previous" or .id == "cdc-print-procedural") | .passed] | all' "$report")" "true"

# ---------------------------------------------------------------------------
# Test 7: print policy in the browser (WP4-AT-06).
# ---------------------------------------------------------------------------

section "Test 7: print policy in the browser (WP4-AT-06)"
printf 'Use Chrome at %s (or the protected simulator). Do not reload the page during this test.\n' "$SIMULATOR_URL"

previous_browser_turn=""
browser_step() {
    local step="$1" instruction="$2" intent="$3" state="$4" tag="browser_step$1" turn_id
    wait_for_owner "$instruction"
    curl --fail --silent "$BACKEND_URL/api/device/debug/last-turn" -o "$WP42_EVIDENCE/$tag.json" \
        || fail "GET /api/device/debug/last-turn after browser step $step failed"
    jq -c '{turn_id, intent, state, transcript, previous_turn_id, action_outcome}' "$WP42_EVIDENCE/$tag.json"
    turn_id="$(jq -r .turn_id "$WP42_EVIDENCE/$tag.json")"
    if [ "$turn_id" = "$previous_browser_turn" ]; then
        fail "browser step $step: no new turn reached the backend"
    fi
    check "step $step intent" "$(jq -r .intent "$WP42_EVIDENCE/$tag.json")" "$intent"
    check "step $step state" "$(jq -r .state "$WP42_EVIDENCE/$tag.json")" "$state"
    previous_browser_turn="$turn_id"
    eval "BROWSER_TURN_$step=\$turn_id"
}

browser_step 1 "Select print policy on_request. Hold talk and ask: How do I use my CDC vouchers?" answer answered
judge "test7-step1" "Did you hear the answer, and is the receipt area still empty?"
browser_step 2 "Hold talk and say: Can you repeat that?" repeat_previous acted
check "step 2 previous_turn_id" "$(jq -r .previous_turn_id "$WP42_EVIDENCE/browser_step2.json")" "$BROWSER_TURN_1"
judge "test7-step2" "Did you hear the same answer again, and is the receipt still empty?"
browser_step 3 "Hold talk and say: Please print that for me." print_previous acted
check "step 3 previous_turn_id" "$(jq -r .previous_turn_id "$WP42_EVIDENCE/browser_step3.json")" "$BROWSER_TURN_1"
judge "test7-step3" "Does the receipt now show the slip for the step 1 answer?"
browser_step 4 "Select print policy auto. Hold talk and ask: What is the weather tomorrow?" refuse refused
judge "test7-step4" "Did you hear the refusal, and did the referral slip render at once?"
browser_step 5 "Hold talk and say: Can you repeat that?" repeat_previous acted
check "step 5 previous_turn_id" "$(jq -r .previous_turn_id "$WP42_EVIDENCE/browser_step5.json")" "$BROWSER_TURN_4"
judge "test7-step5" "Did you hear the refusal again, with the receipt unchanged and not reprinted?"
browser_sessions="$(sql "select count(distinct session_id) from turns where turn_id in ('$BROWSER_TURN_1', '$BROWSER_TURN_2', '$BROWSER_TURN_3', '$BROWSER_TURN_4', '$BROWSER_TURN_5');")"
check "cross-check: all five browser turns share one session in SQLite" "$browser_sessions" "1"

# ---------------------------------------------------------------------------
# Test 8: deterministic and tier B regression.
# ---------------------------------------------------------------------------

section "Test 8: tier B reruns"
for unit in WP2.3 WP2.4 WP3.3 WP3.4 WP4.1; do
    run_wp_check "$unit"
done

section "Test 8: deterministic suites"
turn_rows_before_suites="$(sql 'select count(*) from turns;')"
run_suite ruff "$KAKI_APP_ROOT" python -m ruff check --config backend/pyproject.toml backend scripts services rag
run_suite rag "$KAKI_APP_ROOT" python -m unittest discover -s rag/tests -v
run_suite contract "$KAKI_APP_ROOT" python -m unittest discover -s backend/tests/contract -v
run_suite unit "$KAKI_APP_ROOT" python -m unittest discover -s backend/tests/unit -v
run_suite scripts "$KAKI_APP_ROOT" python -m unittest discover -s scripts/tests -v
run_suite web_lint "$KAKI_APP_ROOT/apps/web" npm run lint
run_suite web_test "$KAKI_APP_ROOT/apps/web" npm test
run_suite web_build "$KAKI_APP_ROOT/apps/web" npm run build
observe "test8_contract_tests_ran" "$(ran_count contract)"
observe "test8_unit_tests_ran" "$(ran_count unit)"
observe "test8_rag_tests_ran" "$(ran_count rag)"
observe "test8_scripts_tests_ran" "$(ran_count scripts)"
observe "test8_web_tests" "$(grep -Eo 'Tests +[0-9]+ passed' "$WP42_EVIDENCE/tier_a_web_test.txt" | tail -1)"
check "live database turn rows unchanged by the deterministic suites" \
    "$(sql 'select count(*) from turns;')" "$turn_rows_before_suites"

# ---------------------------------------------------------------------------
# Teardown: printed, not run.
# ---------------------------------------------------------------------------

section "Teardown"
printf 'The stack is still running. Stop it when you are done:\n'
printf '  python scripts/dev_stack.py down\n'
printf 'The web build replaced apps/web/.next; restart npm start before further browser use.\n'
printf 'Keep the database; WP4.5 backs it up.\n\n'
printf 'Harness finished with no failed assertion and no "no" verdict. This is evidence,\n'
printf 'not the WP4.2 gate: review it, then mark runbook 9.2 WP4.2 yourself.\n'
printf 'Evidence: %s\n' "$WP42_EVIDENCE"
