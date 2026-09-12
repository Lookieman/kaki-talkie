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

printf 'Unit:     %s\n' "$KAKI_UNIT"
printf 'App root: %s\n' "$KAKI_APP_ROOT"
printf 'Evidence: %s\n' "$KAKI_EVIDENCE"
