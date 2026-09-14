# v1.5 | 13-Sep-2026 | Add WP5.1: KAKI_DB, WP51_EVIDENCE at wp5.1/evidence.XXXXXX, WP51_AUDIO.
# v1.4 | 13-Sep-2026 | Add WP4.5: KAKI_DB and WP45_EVIDENCE at wp4.5/evidence.XXXXXX.
# v1.3 | 13-Sep-2026 | Export KAKI_DB for WP4.2 validation too.
# v1.2 | 13-Sep-2026 | Export KAKI_DB for WP4.1 validation.
# v1.1 | 11-Sep-2026 | Add env-only mode: source kaki_env.sh env
# v1.0 | 09-Sep-2026 | Initial parameterised validation environment loader
#
# Usage: source scripts/kaki_env.sh WPn.m   # full unit setup
#        source scripts/kaki_env.sh env      # venv + exports only
#
# Must be sourced, not executed: it exports variables and
# activates the venv in the current shell.

# Guard: detect execution instead of sourcing.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "Error: source this script, do not execute it." >&2
    echo "Usage: source scripts/kaki_env.sh WPn.m" >&2
    exit 2
fi

# Common setup: project root, venv, data root, service config.
cd "$HOME/projects/kaki-talkie" || return 1
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate" || return 1

export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"

export KAKI_STT_MODE=whisper
export KAKI_WHISPER_URL=http://127.0.0.1:8081
export KAKI_STT_TIMEOUT_SECONDS=30
export KAKI_LLM_MODE=qwen
export KAKI_LLM_URL=http://127.0.0.1:8082
export KAKI_LLM_TIMEOUT_SECONDS=120
export KAKI_TTS_MODE=say
export KAKI_TTS_TIMEOUT_SECONDS=30
export KAKI_RETRIEVAL_MODE=rag
export HF_HOME=/Users/websvc/models/huggingface

# env-only mode: export variables and stop.                     #v1.1
if [ "$1" = "env" ]; then                                       #v1.1
    printf 'App root: %s\n' "$KAKI_APP_ROOT"                    #v1.1
    printf 'Mode:     env-only (no unit, no evidence dir)\n'     #v1.1
    return 0                                                     #v1.1
fi                                                               #v1.1

# Full unit mode: validate, create evidence directory.
if ! printf '%s' "$1" | grep -Eq '^WP[0-9]+\.[0-9]+$'; then
    echo "Error: expected a unit like WP2.4 or 'env', got: '$1'" >&2
    return 2
fi

KAKI_UNIT="$1"
_unit_dir="$(printf '%s' "$KAKI_UNIT" | tr 'A-Z' 'a-z')"
_unit_tag="$(printf '%s' "$KAKI_UNIT" | tr -d '.')"

umask 077
mkdir -p "$KAKI_DATA_ROOT/$_unit_dir" || return 1

export KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/$_unit_dir/smoke.XXXXXX")" || return 1
export "${_unit_tag}_EVIDENCE=$KAKI_EVIDENCE"

export KAKI_UNIT
unset _unit_dir _unit_tag

# Unit-specific exports.                                         #v1.2
case "$KAKI_UNIT" in                                             #v1.2
    WP4.1|WP4.2)                                                 #v1.3
        # The backend's SQLite database (runbook 9.1 WP4.1, WP4.2).
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"
        ;;                                                       #v1.2
    WP4.5)                                                       #v1.4
        # The harness takes an empty evidence.XXXXXX directory (runbook 9.2 WP4.5).
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"  #v1.4
        rmdir "$KAKI_EVIDENCE" || return 1                       #v1.4
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp4.5/evidence.XXXXXX")" || return 1  #v1.4
        export KAKI_EVIDENCE WP45_EVIDENCE="$KAKI_EVIDENCE"      #v1.4
        ;;                                                       #v1.4
    WP5.1)                                                       #v1.5
        # The harness takes an empty evidence.XXXXXX directory and reads the
        # owner-voice demo sample from WP51_AUDIO (runbook 10.1 and 10.2 WP5.1).
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"  #v1.5
        rmdir "$KAKI_EVIDENCE" || return 1                       #v1.5
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp5.1/evidence.XXXXXX")" || return 1  #v1.5
        export KAKI_EVIDENCE WP51_EVIDENCE="$KAKI_EVIDENCE"      #v1.5
        export WP51_AUDIO="$KAKI_DATA_ROOT/wp5.1/audio"          #v1.5
        ;;                                                       #v1.5
esac                                                             #v1.2

printf 'Unit:     %s\n' "$KAKI_UNIT"
printf 'App root: %s\n' "$KAKI_APP_ROOT"
printf 'Evidence: %s\n' "$KAKI_EVIDENCE"
if [ -n "$KAKI_DB" ]; then                                       #v1.2
    printf 'Database: %s\n' "$KAKI_DB"                          #v1.2
fi                                                               #v1.2
