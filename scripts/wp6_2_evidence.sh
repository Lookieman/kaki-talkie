#!/usr/bin/env bash
# v1.0 | 20-Sep-2026 | Owner evidence harness for runbook 11.2 WP6.2 Tests 1-6, run on the Pi.
#
# Capture WP6.2 validation evidence AT THE RASPBERRY PI. Every human step is
# physical - press the dome button, speak, listen, read the panel - and the
# harness only prompts, records verdicts and runs service-level assertions.
# It never simulates an owner action (owner decision, 20-Sep-2026).
#
# Run it on the Pi as kaki, from the cloned checkout, while the kiosk process
# runs in its own terminal or SSH session:
#
#   ~/.venvs/kaki-device/bin/python -m kaki_device.main --config ~/kaki-device.toml
#
# Modes:
#   scripts/wp6_2_evidence.sh                 run Tests 1-6
#   scripts/wp6_2_evidence.sh --from-test N   resume at test N (1-6)
#   scripts/wp6_2_evidence.sh -h|--help       show this text
#
# Prerequisites: setup.md 29 complete on this Pi; the Mac backend stack up
# and reachable at the configured backend_url; KAKI_DEVICE_CONFIG naming the
# device TOML (or KAKI_DEVICE_* exports); an interactive terminal.
#
# Side effects: creates an evidence directory under ~/kaki-evidence/wp6.2 and
# posts real turns to the live backend (the owner's spoken turns), stored in
# the Mac's database as any device turn is. No teardown: the kiosk keeps
# running, and the final message shows how to copy the evidence to the Mac's
# KAKI_DATA_ROOT.
#
# Exit status: 0 when every step ran, every assertion held and every verdict
# was yes; 1 on a failed assertion or a "no" verdict; 2 on a usage or
# precondition error.

set -Eeuo pipefail

DEVICE_PYTHON="${KAKI_DEVICE_PYTHON:-$HOME/.venvs/kaki-device/bin/python}"
EVIDENCE_HOME="${WP62_EVIDENCE_HOME:-$HOME/kaki-evidence/wp6.2}"

usage_error() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 2
}

FROM_TEST=1
case "${1:-}" in
    -h|--help)
        sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    --from-test)
        [ "$#" -ge 2 ] || usage_error "--from-test needs a test number."
        FROM_TEST="$2"
        ;;
    "") ;;
    *) usage_error "unknown option: $1" ;;
esac
case "$FROM_TEST" in
    1|2|3|4|5|6) ;;
    *) usage_error "--from-test must be 1 to 6, got: $FROM_TEST" ;;
esac
readonly FROM_TEST

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

trap 'printf "FAIL: command exited non-zero at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

KAKI_APP_ROOT="${KAKI_APP_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$KAKI_APP_ROOT"

for tool in git arecord aplay pgrep; do
    command -v "$tool" >/dev/null || usage_error "$tool is not installed (setup.md 29.3)."
done
[ -x "$DEVICE_PYTHON" ] || usage_error "device venv python not found at $DEVICE_PYTHON (setup.md 29.3)."

mkdir -p "$EVIDENCE_HOME"
WP62_EVIDENCE="$(mktemp -d "$EVIDENCE_HOME/evidence.XXXXXX")"
readonly WP62_EVIDENCE

# The backend the device is configured to call; also proves the config loads.
BACKEND_URL="$(KAKI_APP_ROOT="$KAKI_APP_ROOT" "$DEVICE_PYTHON" - <<'PY'
import os, sys
sys.path.insert(0, os.path.join(os.environ["KAKI_APP_ROOT"], "device", "src"))
from kaki_device.config import load_config
print(load_config(os.environ.get("KAKI_DEVICE_CONFIG") or None).backend_url)
PY
)" || usage_error "the device configuration does not load; fix it first (runbook 11.1 WP6.2)."
readonly BACKEND_URL

header_item() {
    local label="$1"
    shift
    printf '%s:\n' "$label"
    "$@" 2>&1 || true
    printf '\n'
}

{
    printf 'KaKi-Talkie WP6.2 evidence run header (Raspberry Pi)\n\n'
    header_item "date (local)" date
    header_item "date (UTC)" date -u
    header_item "git commit" git -C "$KAKI_APP_ROOT" rev-parse HEAD
    header_item "git branch" git -C "$KAKI_APP_ROOT" branch --show-current
    printf 'harness start test: %s (tests before it did not run)\n\n' "$FROM_TEST"
    printf 'WP62_EVIDENCE: %s\nbackend_url: %s\n\n' "$WP62_EVIDENCE" "$BACKEND_URL"
    header_item "os" sh -c 'head -2 /etc/os-release'
    header_item "machine" uname -m
    header_item "temperature" vcgencmd measure_temp
    header_item "device python" "$DEVICE_PYTHON" --version
    header_item "alsa capture devices" arecord -L
} > "$WP62_EVIDENCE/run-header.txt" 2>&1

exec > >(tee -a "$WP62_EVIDENCE/transcript.txt") 2>&1

printf 'Evidence: %s\n' "$WP62_EVIDENCE"
printf 'Start test: %s\n' "$FROM_TEST"

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
    printf '%s = %s\n' "$1" "$2" >> "$WP62_EVIDENCE/observations.txt"
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
        >> "$WP62_EVIDENCE/judgements.txt"
    printf 'owner verdict recorded for %s: %s\n' "$step" "$answer"
    [ "$answer" = "yes" ] || fail "owner verdict no for $step: $note"
}

# Wait until the owner has done a physical step; recorded, not asserted.
ready() {
    printf '\nDO NOW: %s\n' "$*"
    read -r -p 'Press Enter when done... ' _ </dev/tty
}

# Record the backend's newest stored turn, as service-level evidence.
snapshot_last_turn() {
    local tag="$1"
    "$DEVICE_PYTHON" - "$tag" <<PY
import sys, httpx
tag = sys.argv[1]
response = httpx.get("$BACKEND_URL/api/device/debug/last-turn", timeout=30)
path = "$WP62_EVIDENCE/last_turn_" + tag + ".json"
open(path, "w").write(response.text)
body = response.json() if response.status_code == 200 else {}
print(f"last turn ({tag}): device_id={body.get('device_id')} "
      f"turn_id={body.get('turn_id')} state={body.get('state')}")
PY
}

run_wp_check_tier_c() {
    local rc=0
    local stdout_file="$WP62_EVIDENCE/wp_check_wp62_tierC.json"
    local stderr_file="$WP62_EVIDENCE/wp_check_wp62_tierC.stderr.txt"
    "$DEVICE_PYTHON" scripts/wp_check.py --unit WP6.2 --tier C \
        --evidence "$WP62_EVIDENCE" >"$stdout_file" 2>"$stderr_file" || rc=$?
    printf '%s\n' "$rc" > "$WP62_EVIDENCE/wp_check_wp62_tierC.exit.txt"
    cat "$stderr_file"
    printf 'wp_check WP6.2 tier C exit code: %s (as reported by wp_check)\n' "$rc"
    [ "$rc" -eq 0 ] || fail "wp_check WP6.2 tier C exited $rc; see $stderr_file"
}

# ---------------------------------------------------------------------------
# Tests. Every owner step is physical; the dispatcher honours --from-test.
# ---------------------------------------------------------------------------

# Test 1: the kiosk is up and resting.
test1_kiosk_idle() {
    section "Test 1: kiosk process and the idle screen"
    check "a kaki_device.main process is running" \
        "$(pgrep -f kaki_device.main >/dev/null && echo yes || echo no)" "yes"
    judge "test1-idle-screen" \
        "Does the panel show the idle prompt (EN/MS press-to-talk wording)?"
}

# Test 2: one press, one spoken turn (the WP6.1 loop on real hardware).
test2_one_turn() {
    section "Test 2: one full turn - press, speak, watch, listen"
    ready "Press and hold the dome button, ask 'How do I use my CDC vouchers?', release."
    snapshot_last_turn "test2"
    judge "test2-states" \
        "Did the panel show listening (with a countdown), then thinking, then the answer?"
    judge "test2-audio" \
        "Was the reply spoken once, at normal speed and pitch, from the Jabra?"
    judge "test2-legibility" \
        "Was every screen readable from about a metre away?"
}

# Test 3: debounce (WP6-AT-01).
test3_debounce() {
    section "Test 3: debounce - a rattled press is one press (WP6-AT-01)"
    ready "Tap the dome button once, deliberately sloppily (a quick rattle), then ask a short question and release."
    snapshot_last_turn "test3"
    judge "test3-one-turn" \
        "Did exactly one recording start (no stutter into a second turn)?"
}

# Test 4: the recording cap and release-stop (WP6-AT-02).
test4_recording_cap() {
    section "Test 4: hold past 15 seconds - the cap ends the recording (WP6-AT-02)"
    ready "Press and hold the button for more than 15 seconds while speaking."
    snapshot_last_turn "test4"
    judge "test4-cap" \
        "Did the countdown run to 0 and recording stop by itself at 15 seconds?"
    ready "Now press, say one short word, and release immediately."
    judge "test4-release" \
        "Did releasing the button end the recording at once (no wait for the cap)?"
}

# Test 5: interruption - the ratified 16-Sep-2026 behaviour.
test5_interruption() {
    section "Test 5: a press during playback interrupts into a new recording"
    ready "Ask a question, and while the answer is being spoken, press the button again and ask another."
    snapshot_last_turn "test5"
    judge "test5-interrupt" \
        "Did the speech stop at the press and a new recording start immediately?"
}

# Test 6: the scripted service-level assertions (the only scripted checks).
test6_service_level() {
    section "Test 6: service-level checks on the Pi (wp_check WP6.2 tier C)"
    run_wp_check_tier_c
}

teardown() {
    section "Done"
    printf 'The kiosk keeps running; stop it with Ctrl-C in its own terminal.\n\n'
    printf 'Copy the evidence to the Mac data root (run ON THE MAC):\n'
    printf '  scp -r kaki@kaki-pi.local:%s \\\n' "$WP62_EVIDENCE"
    printf '      /Users/websvc/kaki-talkie-data/wp6.2/\n\n'
    printf 'Harness finished with no failed assertion and no "no" verdict. This is\n'
    printf 'evidence, not the WP6.2 sign-off: review it, then mark runbook 11.1 WP6.2\n'
    printf 'VERIFIED yourself.\n'
    printf 'Evidence: %s\n' "$WP62_EVIDENCE"
}

[ "$FROM_TEST" -gt 1 ] || test1_kiosk_idle
[ "$FROM_TEST" -gt 2 ] || test2_one_turn
[ "$FROM_TEST" -gt 3 ] || test3_debounce
[ "$FROM_TEST" -gt 4 ] || test4_recording_cap
[ "$FROM_TEST" -gt 5 ] || test5_interruption
test6_service_level
teardown
