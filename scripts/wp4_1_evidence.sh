#!/usr/bin/env bash
# v1.0 | 13-Sep-2026 | Owner evidence harness for runbook 9.2 WP4.1 Tests 1-5.
#
# Capture WP4.1 validation evidence on the Mac by running the runbook 9.2
# WP4.1 test block in order: the automated runner, then Tests 1-5.
#
# This is the owner's evidence harness, not the gate. It runs every
# machine-decided step, asserts the runbook's expected observations, and stops
# with a non-zero exit at the first failed assertion. It prints no unit-level
# verdict: scripts/wp_check.py stays the automated gate, and the harness only
# records what each wp_check run reported, with its exit code. The WP4.1 block
# contains no judgement steps, so the harness asks for no verdicts. The owner
# marks the runbook block VERIFIED.
#
# Prerequisites: the grounded stack is running (python scripts/dev_stack.py up)
# and the shell has the WP4.1 session environment, either from the runbook
# "Session setup" block or from: source scripts/kaki_env.sh WP4.1
#
# Side effects:
#   - Creates $WP41_EVIDENCE (a new directory under $KAKI_DATA_ROOT/wp4.1
#     unless an empty one is already exported) and writes evidence files there,
#     starting with run-header.txt. transcript.txt receives the whole run.
#   - Posts four turns to the live backend (Test 2, the Test 3 replay and two
#     Test 4 turns). The wp_check runs post their own turns. All of them are
#     stored in $KAKI_DB, which is intended; the database stays for WP4.2.
#   - Restarts the backend only, through dev_stack.py (Test 3).
#   - Runs the deterministic suites (Test 5).
#   - Does not stop the stack. It prints the teardown command instead.
#
# Usage: scripts/wp4_1_evidence.sh [-h|--help]
# Exit status: 0 when every step ran and every assertion held; 1 on a failed
# assertion or command; 2 on a usage or precondition error.

set -Eeuo pipefail

BACKEND_URL="http://127.0.0.1:8000"
SMOKE_ID="wp41-smoke"
EXPECTED_TABLES="devices sessions turn_sources turns"
CDC_HOST="vouchers.cdc.gov.sg"

usage() {
    sed -n '4,33p' "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") ;;
    *) printf 'Unknown argument: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac

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

# ---------------------------------------------------------------------------
# Preconditions, checked before any evidence is written.
# ---------------------------------------------------------------------------

KAKI_APP_ROOT="${KAKI_APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$KAKI_APP_ROOT"

if [ -z "${KAKI_DATA_ROOT:-}" ]; then
    precondition "KAKI_DATA_ROOT is unset." \
        "source scripts/kaki_env.sh WP4.1  (or run the runbook 9.2 WP4.1 Session setup block)"
fi
case "$KAKI_DATA_ROOT" in
    /*) ;;
    *) precondition "KAKI_DATA_ROOT is not absolute: $KAKI_DATA_ROOT" \
           "export KAKI_DATA_ROOT=/Users/websvc/kaki-talkie-data" ;;
esac

KAKI_DB="${KAKI_DB:-${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}}"
if [ ! -f "$KAKI_DB" ]; then
    precondition "the database is missing: $KAKI_DB" \
        "python scripts/dev_stack.py up  (the backend creates the database at start)"
fi

if ! curl --fail --silent --max-time 10 "$BACKEND_URL/api/health" >/dev/null; then
    precondition "the backend is not answering on 127.0.0.1:8000." \
        "python scripts/dev_stack.py up  then  python scripts/dev_stack.py status"
fi

for tool in jq sqlite3 uuidgen curl; do
    command -v "$tool" >/dev/null || precondition "$tool is not on PATH." "install $tool (setup.md 5.2)"
done

if ! python -c "import kaki_backend" 2>/dev/null; then
    precondition "python cannot import kaki_backend." \
        "source \"$KAKI_APP_ROOT/.venv/bin/activate\""
fi

# The wp_check tier B runners this block invokes read these modes.
for setting in KAKI_RETRIEVAL_MODE=rag KAKI_LLM_MODE=qwen KAKI_TTS_MODE=say; do
    name="${setting%%=*}"
    wanted="${setting#*=}"
    actual="${!name:-}"
    if [ "$actual" != "$wanted" ]; then
        precondition "$name is '${actual:-unset}', expected '$wanted'." \
            "source scripts/kaki_env.sh WP4.1"
    fi
done

# ---------------------------------------------------------------------------
# Evidence directory, run header, transcript.
# ---------------------------------------------------------------------------

umask 077
if [ -n "${WP41_EVIDENCE:-}" ]; then
    if [ ! -d "$WP41_EVIDENCE" ]; then
        precondition "WP41_EVIDENCE does not exist: $WP41_EVIDENCE" \
            "unset WP41_EVIDENCE to let the harness create a new directory"
    fi
    if [ -n "$(ls -A "$WP41_EVIDENCE")" ]; then
        precondition "WP41_EVIDENCE already holds evidence: $WP41_EVIDENCE" \
            "unset WP41_EVIDENCE to let the harness create a new directory"
    fi
else
    mkdir -p "$KAKI_DATA_ROOT/wp4.1"
    WP41_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp4.1/evidence.XXXXXX")"
fi
export WP41_EVIDENCE KAKI_DB KAKI_APP_ROOT

# Record one identity item; an unavailable item is recorded, not fatal.
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
        HF_HOME; do
        printf '%s=%s\n' "$name" "${!name:-unset}"
    done
}

HF_HOME_DIR="${HF_HOME:-$HOME/models/huggingface}"
WHISPER_MODEL="${KAKI_WHISPER_MODEL:-$HOME/models/whisper/ggml-large-v3-turbo.bin}"
LLM_PYTHON="${KAKI_LLM_PYTHON:-$HOME/.venvs/kaki-llm/bin/python}"

{
    printf 'KaKi-Talkie WP4.1 evidence run header\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    header_item "git uncommitted changes" git -C "$KAKI_APP_ROOT" status --short
    printf 'KAKI_APP_ROOT: %s\nKAKI_DATA_ROOT: %s\nKAKI_DB: %s\nKAKI_SQLITE_PATH: %s\nWP41_EVIDENCE: %s\n\n' \
        "$KAKI_APP_ROOT" "$KAKI_DATA_ROOT" "$KAKI_DB" "${KAKI_SQLITE_PATH:-unset}" "$WP41_EVIDENCE"
    header_item "adapter settings" env_settings_dump
    header_item "macOS version (identifies the say engine)" sw_vers -productVersion
    header_item "sqlite3 CLI" sqlite3 --version
    header_item "backend Python packages and approved models" python_identity
    header_item "backend health" curl --fail --silent --max-time 30 "$BACKEND_URL/api/health"
    header_item "mlx-lm" "$LLM_PYTHON" -c "import mlx_lm; print('mlx-lm', mlx_lm.__version__)"
    header_item "MLX-LM served models" curl --fail --silent --max-time 10 http://127.0.0.1:8082/v1/models
    header_item "Qwen snapshot" ls "$HF_HOME_DIR/hub/models--mlx-community--Qwen3-8B-4bit/snapshots"
    header_item "embedding snapshot" ls "$HF_HOME_DIR/hub/models--Qwen--Qwen3-Embedding-0.6B/snapshots"
    header_item "whisper.cpp describe" git -C "$HOME/src/whisper.cpp" describe --tags --always
    header_item "whisper.cpp commit" git -C "$HOME/src/whisper.cpp" rev-parse HEAD
    header_item "whisper model sha256" shasum -a 256 "$WHISPER_MODEL"
} > "$WP41_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP41_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP41_EVIDENCE"
printf 'Database: %s\n' "$KAKI_DB"
printf 'Run header written: %s/run-header.txt\n' "$WP41_EVIDENCE"

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
    printf '%s = %s\n' "$1" "$2" >> "$WP41_EVIDENCE/observations.txt"
}

sql() {
    sqlite3 "$KAKI_DB" "$1"
}

new_turn_id() {
    printf '%s-%s' "$1" "$(uuidgen | tr '[:upper:]' '[:lower:]')"
}

# Run one wp_check tier B unit; record stdout, stderr and exit code as reported.
run_wp_check() {
    local unit="$1" tag rc=0
    tag="$(printf '%s' "$unit" | tr -d '.' | tr '[:upper:]' '[:lower:]')"
    local stdout_file="$WP41_EVIDENCE/wp_check_${tag}_tierB.json"
    local stderr_file="$WP41_EVIDENCE/wp_check_${tag}_tierB.stderr.txt"
    local exit_file="$WP41_EVIDENCE/wp_check_${tag}_tierB.exit.txt"
    python scripts/wp_check.py --unit "$unit" --tier B >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$exit_file"
    cat "$stdout_file"
    cat "$stderr_file"
    printf 'wp_check %s tier B exit code: %s (as reported by wp_check; files %s, %s)\n' \
        "$unit" "$rc" "$(basename "$stdout_file")" "$(basename "$stderr_file")"
    if [ "$rc" -ne 0 ]; then
        fail "wp_check $unit tier B exited $rc; see $stderr_file"
    fi
}

# Run one Tier A command into its evidence file; fail on a non-zero exit.
run_suite() {
    local name="$1" rc=0
    shift
    local output_file="$WP41_EVIDENCE/tier_a_${name}.txt"
    "$@" >"$output_file" 2>&1 || rc=$?
    cat "$output_file"
    printf 'tier A %s exit code: %s (file %s)\n' "$name" "$rc" "$(basename "$output_file")"
    if [ "$rc" -ne 0 ]; then
        fail "tier A $name exited $rc; see $output_file"
    fi
}

ran_count() {
    grep -Eo '^Ran [0-9]+ tests?' "$WP41_EVIDENCE/tier_a_$1.txt" | awk '{print $2}' | tail -1
}

# ---------------------------------------------------------------------------
# Automated runner.
# ---------------------------------------------------------------------------

section "Automated runner: wp_check WP4.1 tier B"
run_wp_check WP4.1

# ---------------------------------------------------------------------------
# Test 1: schema and storage readiness.
# ---------------------------------------------------------------------------

section "Test 1: schema and storage readiness"

status_rc=0
python scripts/dev_stack.py status || status_rc=$?
printf 'dev_stack.py status exit code: %s\n' "$status_rc"
if [ "$status_rc" -ne 0 ]; then
    fail "dev_stack.py status reports the stack is not fully healthy; the block needs the grounded stack running"
fi

if ! curl --fail --silent "$BACKEND_URL/api/health" -o "$WP41_EVIDENCE/health.json"; then
    fail "GET /api/health failed"
fi
jq '{storage_ready, retrieval_ready}' "$WP41_EVIDENCE/health.json"
check "health storage_ready" "$(jq -r '.storage_ready' "$WP41_EVIDENCE/health.json")" "true"

ls -l "$KAKI_DB"
check "database file mode" "$(stat -f '%Sp' "$KAKI_DB")" "-rw-------"

sqlite3 "$KAKI_DB" ".tables" "pragma user_version;" > "$WP41_EVIDENCE/schema.txt"
cat "$WP41_EVIDENCE/schema.txt"
schema_tokens="$(tr -s ' \n' '\n' < "$WP41_EVIDENCE/schema.txt" | sed '/^$/d')"
check "tables" "$(printf '%s\n' "$schema_tokens" | sed '$d' | sort | tr '\n' ' ' | sed 's/ $//')" \
    "$EXPECTED_TABLES"
check "user_version" "$(printf '%s\n' "$schema_tokens" | tail -1)" "1"

backend_log="$KAKI_DATA_ROOT/logs/backend.log"
if ! grep -i 'sqlite' "$backend_log" | tail -2 > "$WP41_EVIDENCE/backend_log_sqlite.txt"; then
    fail "no SQLite line in $backend_log; compare \$KAKI_DB with the backend's startup line"
fi
cat "$WP41_EVIDENCE/backend_log_sqlite.txt"
last_log_line="$(tail -1 "$WP41_EVIDENCE/backend_log_sqlite.txt")"
case "$last_log_line" in
    *"$KAKI_DB"*"schema version 1"*) printf 'check ok: backend log names %s and schema version 1\n' "$KAKI_DB" ;;
    *) fail "backend log line does not name $KAKI_DB at schema version 1: $last_log_line" ;;
esac

# ---------------------------------------------------------------------------
# Test 2: durable grounded turn (WP4-AT-01, 02).
# ---------------------------------------------------------------------------

section "Test 2: durable grounded turn (WP4-AT-01, 02)"

# Test 3 replays this exact turn_id after the restart; it is set once, here.
REPLAY_TURN_ID="$(new_turn_id wp41-cdc)"
readonly REPLAY_TURN_ID
printf 'REPLAY_TURN_ID=%s\n' "$REPLAY_TURN_ID"

if ! first_seconds="$(curl --fail --silent --show-error --max-time 300 "$BACKEND_URL/api/device/turn" \
    -F "device_id=$SMOKE_ID" -F "session_id=$SMOKE_ID" -F "turn_id=$REPLAY_TURN_ID" \
    -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/cdc_question.wav" \
    -o "$WP41_EVIDENCE/turn_first.json" -w '%{time_total}')"; then
    fail "POST /api/device/turn (Test 2) failed"
fi
jq '{state, case_id, source_count: (.sources | length), first_source: .sources[0].source_url}' \
    "$WP41_EVIDENCE/turn_first.json"
observe "test2_first_turn_elapsed_seconds" "$first_seconds"

check "state" "$(jq -r '.state' "$WP41_EVIDENCE/turn_first.json")" "answered"
check "case_id" "$(jq -r '.case_id' "$WP41_EVIDENCE/turn_first.json")" "null"
source_count="$(jq -r '.sources | length' "$WP41_EVIDENCE/turn_first.json")"
if [ "$source_count" -lt 1 ] || [ "$source_count" -gt 3 ]; then
    fail "source_count: expected 1-3, got $source_count"
fi
printf 'check ok: source_count = %s (1-3)\n' "$source_count"
first_source="$(jq -r '.sources[0].source_url' "$WP41_EVIDENCE/turn_first.json")"
check "first_source host" "$(printf '%s' "$first_source" | sed -E 's#^https?://([^/:]+).*#\1#')" "$CDC_HOST"

sqlite3 -header "$KAKI_DB" \
    "select turn_id, state, intent, replay_count, completed_at from turns where turn_id='$REPLAY_TURN_ID';" \
    > "$WP41_EVIDENCE/turns_row.txt"
cat "$WP41_EVIDENCE/turns_row.txt"
sqlite3 -header "$KAKI_DB" \
    "select position, source_id, source_url, cited, retrieval_rank, dense_score
     from turn_sources where turn_id='$REPLAY_TURN_ID' order by position;" \
    > "$WP41_EVIDENCE/turn_sources_rows.txt"
cat "$WP41_EVIDENCE/turn_sources_rows.txt"
sqlite3 -header "$KAKI_DB" \
    "select device_id, last_seen_at from devices where device_id='$SMOKE_ID';
     select session_id, last_turn_id from sessions where session_id='$SMOKE_ID';" \
    > "$WP41_EVIDENCE/devices_sessions_rows.txt"
cat "$WP41_EVIDENCE/devices_sessions_rows.txt"

check "turns rows for turn_id" "$(sql "select count(*) from turns where turn_id='$REPLAY_TURN_ID';")" "1"
check "replay_count" "$(sql "select replay_count from turns where turn_id='$REPLAY_TURN_ID';")" "0"
test2_source_rows="$(sql "select count(*) from turn_sources where turn_id='$REPLAY_TURN_ID';")"
check "turn_sources rows = source_count" "$test2_source_rows" "$source_count"
check "position 0 cited" \
    "$(sql "select cited from turn_sources where turn_id='$REPLAY_TURN_ID' and position=0;")" "1"
check "position 0 source_url = first_source" \
    "$(sql "select source_url from turn_sources where turn_id='$REPLAY_TURN_ID' and position=0;")" \
    "$first_source"
check "devices rows" "$(sql "select count(*) from devices where device_id='$SMOKE_ID';")" "1"
check "sessions rows" "$(sql "select count(*) from sessions where session_id='$SMOKE_ID';")" "1"
check "sessions last_turn_id" \
    "$(sql "select last_turn_id from sessions where session_id='$SMOKE_ID';")" "$REPLAY_TURN_ID"
observe "test2_total_turn_rows" "$(sql "select count(*) from turns;")"

# ---------------------------------------------------------------------------
# Test 3: restart and replay (WP4-AT-03).
# ---------------------------------------------------------------------------

section "Test 3: restart and replay (WP4-AT-03)"

if ! python scripts/dev_stack.py down --only backend; then
    fail "dev_stack.py down --only backend failed"
fi
if ! python scripts/dev_stack.py up --only backend; then
    fail "dev_stack.py up --only backend failed; see $KAKI_DATA_ROOT/logs/backend.log"
fi

if ! health_after_restart="$(curl --fail --silent "$BACKEND_URL/api/health")"; then
    fail "GET /api/health after restart failed"
fi
printf '%s' "$health_after_restart" | jq '{storage_ready, retrieval_ready}'
check "storage_ready after restart" "$(printf '%s' "$health_after_restart" | jq -r '.storage_ready')" "true"

if ! curl --fail --silent "$BACKEND_URL/api/device/debug/last-turn" -o "$WP41_EVIDENCE/debug_after_restart.json"; then
    fail "GET /api/device/debug/last-turn after restart failed"
fi
jq '{turn_id, replay_count, completed_at}' "$WP41_EVIDENCE/debug_after_restart.json"
check "debug turn_id before replay" "$(jq -r '.turn_id' "$WP41_EVIDENCE/debug_after_restart.json")" "$REPLAY_TURN_ID"
check "debug replay_count before replay" "$(jq -r '.replay_count' "$WP41_EVIDENCE/debug_after_restart.json")" "0"

llm_log="$KAKI_DATA_ROOT/logs/llm.log"
[ -f "$llm_log" ] || fail "LLM log not found: $llm_log"
llm_calls_before="$(grep -c 'chat/completions' "$llm_log" || true)"
turn_rows_before="$(sql "select count(*) from turns;")"
turn_id_rows_before="$(sql "select count(*) from turns where turn_id='$REPLAY_TURN_ID';")"
source_rows_before="$(sql "select count(*) from turn_sources where turn_id='$REPLAY_TURN_ID';")"

# Different audio on purpose: re-execution would return a refusal, not the CDC answer.
if ! replay_seconds="$(curl --fail --silent --show-error --max-time 60 "$BACKEND_URL/api/device/turn" \
    -F "device_id=$SMOKE_ID" -F "session_id=$SMOKE_ID" -F "turn_id=$REPLAY_TURN_ID" \
    -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/unsupported_question.wav" \
    -o "$WP41_EVIDENCE/turn_replay.json" -w '%{time_total}')"; then
    fail "POST /api/device/turn (Test 3 replay) failed"
fi
llm_calls_after="$(grep -c 'chat/completions' "$llm_log" || true)"
observe "test3_replay_elapsed_seconds" "$replay_seconds"

if diff <(jq -S . "$WP41_EVIDENCE/turn_first.json") <(jq -S . "$WP41_EVIDENCE/turn_replay.json") \
    > "$WP41_EVIDENCE/replay_diff.txt"; then
    echo IDENTICAL | tee "$WP41_EVIDENCE/replay_diff.txt"
else
    cat "$WP41_EVIDENCE/replay_diff.txt"
    fail "replay response differs from the Test 2 response; diff in replay_diff.txt"
fi

sqlite3 -header "$KAKI_DB" \
    "select turn_id, replay_count from turns where turn_id='$REPLAY_TURN_ID';
     select count(*) as turn_rows from turns;
     select count(*) as source_rows from turn_sources where turn_id='$REPLAY_TURN_ID';" \
    > "$WP41_EVIDENCE/replay_rows.txt"
cat "$WP41_EVIDENCE/replay_rows.txt"

if ! curl --fail --silent "$BACKEND_URL/api/device/debug/last-turn" -o "$WP41_EVIDENCE/debug_after_replay.json"; then
    fail "GET /api/device/debug/last-turn after replay failed"
fi
jq '{turn_id, replay_count}' "$WP41_EVIDENCE/debug_after_replay.json"

printf 'replay elapsed: %s s (recorded, no threshold)\n' "$replay_seconds"
check "stored replay_count" "$(sql "select replay_count from turns where turn_id='$REPLAY_TURN_ID';")" "1"
check "debug replay_count after replay" "$(jq -r '.replay_count' "$WP41_EVIDENCE/debug_after_replay.json")" "1"
check "debug turn_id after replay" "$(jq -r '.turn_id' "$WP41_EVIDENCE/debug_after_replay.json")" "$REPLAY_TURN_ID"
check "debug completed_at unchanged" \
    "$(jq -r '.completed_at' "$WP41_EVIDENCE/debug_after_replay.json")" \
    "$(jq -r '.completed_at' "$WP41_EVIDENCE/debug_after_restart.json")"
stage_filter='.timings_ms | {stt_ms, retrieval_ms, llm_ms, tts_ms} | tojson'
check "STT/retrieval/LLM/TTS stage timings unchanged by replay" \
    "$(jq -r "$stage_filter" "$WP41_EVIDENCE/debug_after_replay.json")" \
    "$(jq -r "$stage_filter" "$WP41_EVIDENCE/debug_after_restart.json")"
check "total turn rows unchanged by replay" "$(sql "select count(*) from turns;")" "$turn_rows_before"
check "rows for replayed turn_id unchanged" \
    "$(sql "select count(*) from turns where turn_id='$REPLAY_TURN_ID';")" "$turn_id_rows_before"
check "source rows unchanged by replay" \
    "$(sql "select count(*) from turn_sources where turn_id='$REPLAY_TURN_ID';")" "$source_rows_before"
check "source rows unchanged from Test 2" "$source_rows_before" "$test2_source_rows"
observe "test3_llm_log_chat_completions_before" "$llm_calls_before"
observe "test3_llm_log_chat_completions_after" "$llm_calls_after"
check "LLM log chat/completions count unchanged by replay" "$llm_calls_after" "$llm_calls_before"

# ---------------------------------------------------------------------------
# Test 4: failed and refused turns are stored.
# ---------------------------------------------------------------------------

section "Test 4: failed and refused turns are stored"

: > "$WP41_EVIDENCE/empty.wav"
EMPTY_TURN_ID="$(new_turn_id wp41-empty)"
REFUSED_TURN_ID="$(new_turn_id wp41-refused)"
printf 'EMPTY_TURN_ID=%s\nREFUSED_TURN_ID=%s\n' "$EMPTY_TURN_ID" "$REFUSED_TURN_ID"

if ! empty_response="$(curl --fail --silent --show-error "$BACKEND_URL/api/device/turn" \
    -F "device_id=$SMOKE_ID" -F "session_id=$SMOKE_ID" -F "turn_id=$EMPTY_TURN_ID" \
    -F "audio=@$WP41_EVIDENCE/empty.wav")"; then
    fail "POST /api/device/turn (Test 4 empty audio) failed"
fi
printf '%s' "$empty_response" | jq '{state}'
if ! refused_response="$(curl --fail --silent --show-error --max-time 300 "$BACKEND_URL/api/device/turn" \
    -F "device_id=$SMOKE_ID" -F "session_id=$SMOKE_ID" -F "turn_id=$REFUSED_TURN_ID" \
    -F "audio=@$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/unsupported_question.wav")"; then
    fail "POST /api/device/turn (Test 4 unsupported question) failed"
fi
printf '%s' "$refused_response" | jq '{state}'

sqlite3 -header "$KAKI_DB" \
    "select turn_id, state, intent, refusal_reason,
            (select count(*) from turn_sources s where s.turn_id = t.turn_id) as source_rows
     from turns t where turn_id in ('$EMPTY_TURN_ID', '$REFUSED_TURN_ID');" \
    > "$WP41_EVIDENCE/non_answered_rows.txt"
cat "$WP41_EVIDENCE/non_answered_rows.txt"

check "empty audio response state" "$(printf '%s' "$empty_response" | jq -r '.state')" "failed"
check "unsupported question response state" "$(printf '%s' "$refused_response" | jq -r '.state')" "refused"
check "stored rows" \
    "$(sql "select count(*) from turns where turn_id in ('$EMPTY_TURN_ID', '$REFUSED_TURN_ID');")" "2"
check "empty turn stored state" "$(sql "select state from turns where turn_id='$EMPTY_TURN_ID';")" "failed"
check "refused turn stored state" "$(sql "select state from turns where turn_id='$REFUSED_TURN_ID';")" "refused"
check "refused turn intent" "$(sql "select intent from turns where turn_id='$REFUSED_TURN_ID';")" "refuse"
check "refused turn refusal_reason" \
    "$(sql "select refusal_reason from turns where turn_id='$REFUSED_TURN_ID';")" "no_coverage"
check "empty turn source rows" "$(sql "select count(*) from turn_sources where turn_id='$EMPTY_TURN_ID';")" "0"
check "refused turn source rows" "$(sql "select count(*) from turn_sources where turn_id='$REFUSED_TURN_ID';")" "0"

# ---------------------------------------------------------------------------
# Test 5: deterministic and tier B regression.
# ---------------------------------------------------------------------------

section "Test 5: tier B reruns"
for unit in WP2.3 WP2.4 WP3.3 WP3.4; do
    run_wp_check "$unit"
done

section "Test 5: deterministic suites"
turn_rows_before_suites="$(sql "select count(*) from turns;")"
run_suite ruff python -m ruff check --config backend/pyproject.toml backend scripts services rag
run_suite rag python -m unittest discover -s rag/tests -v
run_suite contract python -m unittest discover -s backend/tests/contract -v
run_suite unit python -m unittest discover -s backend/tests/unit -v
run_suite scripts python -m unittest discover -s scripts/tests -v
observe "test5_contract_tests_ran" "$(ran_count contract)"
observe "test5_unit_tests_ran" "$(ran_count unit)"
observe "test5_rag_tests_ran" "$(ran_count rag)"
check "live database turn rows unchanged by the deterministic suites" \
    "$(sql "select count(*) from turns;")" "$turn_rows_before_suites"

# ---------------------------------------------------------------------------
# Teardown: printed, not run.
# ---------------------------------------------------------------------------

section "Teardown"
printf 'The stack is still running. Stop it when you are done:\n'
printf '  python scripts/dev_stack.py down\n'
printf 'Keep the database; WP4.2 builds on it.\n\n'
printf 'Harness finished with no failed assertion. This is evidence, not the WP4.1 gate:\n'
printf 'review it, then mark runbook 9.2 WP4.1 yourself.\n'
printf 'Evidence: %s\n' "$WP41_EVIDENCE"
