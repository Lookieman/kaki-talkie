#!/usr/bin/env bash
# v1.0 | 18-Sep-2026 | WP6.6 loopback admin fallback: config, push and state over curl.
#
# Run the demo admin actions against the loopback backend on the Mac Mini.
# This is the WP6-AT-18 fallback: the tunnel is the weakest link in the demo,
# and every admin action must work without it (design.md 5.5). The script
# talks to http://127.0.0.1:8000 only.
#
# Usage:
#   scripts/wp6_6_admin.sh config <en|ms|auto> [--device ID]
#   scripts/wp6_6_admin.sh push [--device ID]
#   scripts/wp6_6_admin.sh state
#   scripts/wp6_6_admin.sh -h|--help
#
# Actions:
#   config LANG   Set the device's reply language (en, ms or auto).
#   push          Mark the seeded CDC-vouchers message queued for the device.
#   state         Print the current config and push queue as JSON.
#
# Options:
#   --device ID   Target device (default: KAKI_ADMIN_DEFAULT_DEVICE, else
#                 kaki-pi-01). Every write names its device explicitly; no
#                 target is ever inferred from recent activity.
#
# Prerequisites: the backend is running on loopback, and KAKI_ADMIN_TOKEN is
# exported (or present in the project-root .env, which this script reads for
# that one value). Admin routes fail closed without it.
#
# Side effects: config and push write admin state in the backend's database,
# exactly as the /admin page would. state writes nothing.
#
# Exit status: 0 on success; 1 when the backend refuses or is unreachable;
# 2 on a usage or precondition error.

set -Eeuo pipefail

BACKEND_URL="${KAKI_ADMIN_URL:-http://127.0.0.1:8000}"

usage() {
    awk 'NR > 2 && /^#/ { sub(/^# ?/, ""); print; next } NR > 2 { exit }' "$0"
}

usage_error() {
    printf '%s\n\n' "$1" >&2
    usage >&2
    exit 2
}

ACTION="${1:-}"
case "$ACTION" in
    -h|--help) usage; exit 0 ;;
    config|push|state) shift ;;
    "") usage_error "An action is required: config, push or state." ;;
    *) usage_error "Unknown action: $ACTION" ;;
esac

LANGUAGE=""
if [ "$ACTION" = "config" ]; then
    LANGUAGE="${1:-}"
    case "$LANGUAGE" in
        en|ms|auto) shift ;;
        *) usage_error "config needs a language: en, ms or auto." ;;
    esac
fi

DEVICE="${KAKI_ADMIN_DEFAULT_DEVICE:-kaki-pi-01}"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --device)
            [ "$#" -ge 2 ] || usage_error "--device needs a device id."
            DEVICE="$2"; shift 2 ;;
        *) usage_error "Unknown argument: $1" ;;
    esac
done
[ -n "$DEVICE" ] || usage_error "The device id must not be blank."

# The token may live in the untracked project-root .env; a real export wins.
if [ -z "${KAKI_ADMIN_TOKEN:-}" ]; then
    ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
    if [ -f "$ENV_FILE" ]; then
        KAKI_ADMIN_TOKEN="$(sed -n 's/^KAKI_ADMIN_TOKEN=//p' "$ENV_FILE" | tail -1)"
    fi
fi
if [ -z "${KAKI_ADMIN_TOKEN:-}" ]; then
    printf 'FAIL: KAKI_ADMIN_TOKEN is not set. Export it, or add it to the project-root .env\n' >&2
    printf '(setup.md 11.4). The admin surface fails closed without it.\n' >&2
    exit 2
fi

request() {
    local method="$1" path="$2" body="${3:-}" http_code response_file
    local body_args=()
    if [ -n "$body" ]; then
        body_args=(-H "Content-Type: application/json" -d "$body")
    fi
    response_file="$(mktemp "${TMPDIR:-/tmp}/kaki-admin.XXXXXX")"
    # ${array[@]+...} is the empty-array expansion that survives set -u on
    # the macOS system bash (3.2).
    http_code="$(curl --silent --show-error --max-time 10 -X "$method" \
        -H "Authorization: Bearer $KAKI_ADMIN_TOKEN" \
        ${body_args[@]+"${body_args[@]}"} \
        -o "$response_file" -w '%{http_code}' \
        "$BACKEND_URL$path")" || {
        rm -f "$response_file"
        printf 'FAIL: the backend is not answering on %s.\n' "$BACKEND_URL" >&2
        exit 1
    }
    cat "$response_file"
    printf '\n'
    rm -f "$response_file"
    if [ "$http_code" != "200" ]; then
        printf 'FAIL: HTTP %s from %s.\n' "$http_code" "$path" >&2
        exit 1
    fi
}

case "$ACTION" in
    config)
        printf 'Setting %s to %s...\n' "$DEVICE" "$LANGUAGE"
        request POST /api/admin/config \
            "{\"device_id\": \"$DEVICE\", \"reply_language\": \"$LANGUAGE\"}"
        ;;
    push)
        printf 'Pushing the CDC-vouchers message to %s...\n' "$DEVICE"
        request POST /api/admin/push "{\"device_id\": \"$DEVICE\"}"
        ;;
    state)
        request GET /api/admin/state
        ;;
esac
