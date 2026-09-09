# v1.0 | 09-Sep-2026 | Initial parameterised validation environment loader
#
# Usage: source scripts/kaki_env.sh WPn.m
# Example: source scripts/kaki_env.sh WP2.4
#
# Must be sourced, not executed: it exports variables and
# activates the venv in the current shell.

# Guard: detect execution instead of sourcing.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "Error: source this script, do not execute it." >&2
    echo "Usage: source scripts/kaki_env.sh WPn.m" >&2
    exit 2
fi

# Validate the unit argument, e.g. WP2.4
if ! printf '%s' "$1" | grep -Eq '^WP[0-9]+\.[0-9]+$'; then
    echo "Error: expected a unit like WP2.4, got: '$1'" >&2
    return 2
fi

KAKI_UNIT="$1"
# WP2.4 -> wp2.4 (directory name), WP24 (variable prefix)
_unit_dir="$(printf '%s' "$KAKI_UNIT" | tr 'A-Z' 'a-z')"
_unit_tag="$(printf '%s' "$KAKI_UNIT" | tr -d '.')"

cd "$HOME/projects/kaki-talkie" || return 1
export KAKI_APP_ROOT="$PWD"
source "$KAKI_APP_ROOT/.venv/bin/activate" || return 1

export KAKI_DATA_ROOT="/Users/websvc/kaki-talkie-data"
umask 077
mkdir -p "$KAKI_DATA_ROOT/$_unit_dir" || return 1

# Evidence directory: both a generic name and the per-unit
# name the runbooks reference (WP24_EVIDENCE etc.).
export KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/$_unit_dir/smoke.XXXXXX")" || return 1
export "${_unit_tag}_EVIDENCE=$KAKI_EVIDENCE"

# Service configuration: identical across units so far.
export KAKI_STT_MODE=whisper
export KAKI_WHISPER_URL=http://127.0.0.1:8081
export KAKI_STT_TIMEOUT_SECONDS=30
export KAKI_LLM_MODE=qwen
export KAKI_LLM_URL=http://127.0.0.1:8082
export KAKI_LLM_TIMEOUT_SECONDS=120
export KAKI_TTS_MODE=say
export KAKI_TTS_TIMEOUT_SECONDS=30
export HF_HOME=/Users/websvc/models/huggingface

export KAKI_UNIT
unset _unit_dir _unit_tag

printf 'Unit:     %s\n' "$KAKI_UNIT"
printf 'App root: %s\n' "$KAKI_APP_ROOT"
printf 'Evidence: %s\n' "$KAKI_EVIDENCE"
