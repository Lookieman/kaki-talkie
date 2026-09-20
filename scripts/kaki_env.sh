# v2.0 | 20-Sep-2026 | WP6.4: load KAKI_DEVICE_TOKEN from .env; add the WP6.4 branch.
# v1.9 | 20-Sep-2026 | Add WP6.2: Mac-side evidence directory for tier A and the reruns.
# v1.8 | 19-Sep-2026 | Load KAKI_ADMIN_TOKEN in common setup, so env-only mode
#                      gets it too. It sat in the WP6.6 branch, which runs
#                      after the env-only return, so `source kaki_env.sh env`
#                      left the admin surface disabled.
# v1.7 | 18-Sep-2026 | Add WP6.6: evidence directory, KAKI_DB and the admin token from .env.
# v1.6 | 16-Sep-2026 | Add WP6.1: device evidence directory and mock fixture path.
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

# The admin surface fails closed without its token. Read it from the      #v1.8
# untracked project-root .env when the shell has none, so every mode -    #v1.8
# env-only included - can drive the admin endpoints.                      #v1.8
if [ -z "${KAKI_ADMIN_TOKEN:-}" ] && [ -f "$KAKI_APP_ROOT/.env" ]; then    #v1.8
    KAKI_ADMIN_TOKEN="$(sed -n 's/^KAKI_ADMIN_TOKEN=//p' "$KAKI_APP_ROOT/.env" | tail -1)"  #v1.8
fi                                                                        #v1.8
[ -z "${KAKI_ADMIN_TOKEN:-}" ] || export KAKI_ADMIN_TOKEN                 #v1.8

# The device path fails closed without its token too (WP6.4). Same        #v2.0
# pattern: the untracked project-root .env feeds the shell when it has    #v2.0
# none. It is a different secret from the admin token.                    #v2.0
if [ -z "${KAKI_DEVICE_TOKEN:-}" ] && [ -f "$KAKI_APP_ROOT/.env" ]; then   #v2.0
    KAKI_DEVICE_TOKEN="$(sed -n 's/^KAKI_DEVICE_TOKEN=//p' "$KAKI_APP_ROOT/.env" | tail -1)"  #v2.0
fi                                                                        #v2.0
[ -z "${KAKI_DEVICE_TOKEN:-}" ] || export KAKI_DEVICE_TOKEN               #v2.0

# env-only mode: export variables and stop.                     #v1.1
if [ "$1" = "env" ]; then                                       #v1.1
    printf 'App root: %s\n' "$KAKI_APP_ROOT"                    #v1.1
    printf 'Mode:     env-only (no unit, no evidence dir)\n'     #v1.1
    if [ -n "${KAKI_ADMIN_TOKEN:-}" ]; then                      #v1.8
        printf 'Admin:    KAKI_ADMIN_TOKEN set\n'                #v1.8
    else                                                         #v1.8
        printf 'Admin:    KAKI_ADMIN_TOKEN unset (admin surface disabled)\n'  #v1.8
    fi                                                           #v1.8
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
    WP6.1)                                                       #v1.6
        # The device harness writes evidence and a slip log; the mock
        # microphone replays a committed spoken fixture (runbook 11.1 WP6.1).
        rmdir "$KAKI_EVIDENCE" || return 1                       #v1.6
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp6.1/evidence.XXXXXX")" || return 1  #v1.6
        export KAKI_EVIDENCE WP61_EVIDENCE="$KAKI_EVIDENCE"      #v1.6
        export KAKI_DEVICE_MOCK__AUDIO_PATH="$KAKI_APP_ROOT/backend/src/kaki_backend/fixtures/cdc_question.wav"  #v1.6
        ;;                                                       #v1.6
    WP5.1)                                                       #v1.5
        # The harness takes an empty evidence.XXXXXX directory and reads the
        # owner-voice demo sample from WP51_AUDIO (runbook 10.1 and 10.2 WP5.1).
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"  #v1.5
        rmdir "$KAKI_EVIDENCE" || return 1                       #v1.5
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp5.1/evidence.XXXXXX")" || return 1  #v1.5
        export KAKI_EVIDENCE WP51_EVIDENCE="$KAKI_EVIDENCE"      #v1.5
        export WP51_AUDIO="$KAKI_DATA_ROOT/wp5.1/audio"          #v1.5
        ;;                                                       #v1.5
    WP6.2)                                                       #v1.9
        # Mac-side WP6.2 work is the tier A gate and the WP6.1 regression
        # reruns; the physical validation runs on the Pi (runbook 11.2 WP6.2)
        # and its evidence is copied into this directory afterwards.
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"  #v1.9
        rmdir "$KAKI_EVIDENCE" || return 1                       #v1.9
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp6.2/evidence.XXXXXX")" || return 1  #v1.9
        export KAKI_EVIDENCE WP62_EVIDENCE="$KAKI_EVIDENCE"      #v1.9
        ;;                                                       #v1.9
    WP6.4)                                                       #v2.0
        # Tier A and B run on the Mac; KAKI_DEVICE_TOKEN loads in common
        # setup above. Tier C is the owner at the Pi (runbook 11.2 WP6.4).
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"  #v2.0
        rmdir "$KAKI_EVIDENCE" || return 1                       #v2.0
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp6.4/evidence.XXXXXX")" || return 1  #v2.0
        export KAKI_EVIDENCE WP64_EVIDENCE="$KAKI_EVIDENCE"      #v2.0
        ;;                                                       #v2.0
    WP6.6)                                                       #v1.7
        # KAKI_ADMIN_TOKEN now loads in common setup above (runbook 11.1 WP6.6).
        export KAKI_DB="${KAKI_SQLITE_PATH:-$KAKI_DATA_ROOT/sqlite/kaki.db}"  #v1.7
        rmdir "$KAKI_EVIDENCE" || return 1                       #v1.7
        KAKI_EVIDENCE="$(mktemp -d "$KAKI_DATA_ROOT/wp6.6/evidence.XXXXXX")" || return 1  #v1.7
        export KAKI_EVIDENCE WP66_EVIDENCE="$KAKI_EVIDENCE"      #v1.7
        ;;                                                       #v1.7
esac                                                             #v1.2

printf 'Unit:     %s\n' "$KAKI_UNIT"
printf 'App root: %s\n' "$KAKI_APP_ROOT"
printf 'Evidence: %s\n' "$KAKI_EVIDENCE"
if [ -n "$KAKI_DB" ]; then                                       #v1.2
    printf 'Database: %s\n' "$KAKI_DB"                          #v1.2
fi                                                               #v1.2
