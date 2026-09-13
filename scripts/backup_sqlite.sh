#!/usr/bin/env bash
# v1.0 | 13-Sep-2026 | WP4.5 backup set: SQLite .backup, corpus and index copies, manifest.
#
# Write one KaKi-Talkie backup set (runbook 9.1 WP4.5 "Backup set").
#
# Usage:
#   scripts/backup_sqlite.sh            write a new backup set
#   scripts/backup_sqlite.sh -h|--help  show this text
#
# Reads KAKI_DATA_ROOT (required, absolute) and KAKI_SQLITE_PATH (optional,
# absolute; default $KAKI_DATA_ROOT/sqlite/kaki.db). Run it by hand; nothing
# schedules it (ADR-0008 decision 2). It is safe while the backend runs.
#
# The set is $KAKI_DATA_ROOT/backups/<UTC timestamp>/, directory mode 0700,
# file mode 0600, holding:
#   kaki.db       sqlite3 ".backup" of the database (WAL-safe)
#   corpus/       copy of $KAKI_DATA_ROOT/corpus
#   chroma/       copy of $KAKI_DATA_ROOT/chroma (restore source of truth)
#   manifest.txt  created_utc, git commit, user_version, turns count,
#                 ingest_running, and sha256:<path>=<hash> for every file
#
# Models, caches, virtual environments, build output, .env, logs and the wp*/
# evidence directories are never copied.
#
# ingest_running is true when pgrep -f finds index_corpus.py or
# ingest_corpus.py. A copy taken during either may be inconsistent; the script
# records it and warns, and the restore test proves the index is readable.
# If pgrep cannot list processes, the value is "unknown".
#
# Side effects: creates the new set and nothing else. The set is built as
# <timestamp>.partial and renamed on success; a failed run leaves the
# .partial directory for inspection. The script never deletes or overwrites a
# set, and refuses when a set with the same timestamp already exists.
#
# Backup files are read only through immutable URIs, because an ordinary
# open of a WAL-mode backup leaves -wal/-shm files beside it.
#
# Exit status: 0 on success; 1 when a copy or verification fails; 2 on a usage
# or configuration error.

set -Eeuo pipefail

usage() {
    awk 'NR > 3 && /^#/ { sub(/^# ?/, ""); print; next } NR > 3 { exit }' "$0"
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") ;;
    *) printf 'Unknown argument: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac

config_error() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 2
}

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

for tool in sqlite3 shasum find; do
    command -v "$tool" >/dev/null || config_error "$tool is not on PATH."
done

DATA_ROOT="${KAKI_DATA_ROOT:-}"
case "$DATA_ROOT" in
    /*) ;;
    *) config_error "export an absolute KAKI_DATA_ROOT first (runbook 9.1 WP4.1)." ;;
esac
DATABASE="${KAKI_SQLITE_PATH:-$DATA_ROOT/sqlite/kaki.db}"
case "$DATABASE" in
    /*) ;;
    *) config_error "KAKI_SQLITE_PATH must be absolute when set." ;;
esac
[ -s "$DATABASE" ] || config_error "the database is missing or empty: $DATABASE"
for directory in corpus chroma; do
    [ -d "$DATA_ROOT/$directory" ] || config_error "$DATA_ROOT/$directory does not exist."
done

REPOSITORY="$(cd "$(dirname "$0")/.." && pwd)"
BACKUPS="$DATA_ROOT/backups"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CREATED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SET_DIR="$BACKUPS/$TIMESTAMP"
PARTIAL_DIR="$SET_DIR.partial"

umask 077
mkdir -p "$BACKUPS"
if [ -e "$SET_DIR" ] || [ -e "$PARTIAL_DIR" ]; then
    fail "a backup set named $TIMESTAMP already exists; wait a second and retry."
fi
mkdir "$PARTIAL_DIR"

ingest_state() {
    local pids="" status=0 pattern found
    for pattern in index_corpus.py ingest_corpus.py; do
        found="$(pgrep -f "$pattern" 2>/dev/null)" || status=$?
        if [ "$status" -gt 1 ]; then
            printf 'unknown\n'
            return
        fi
        status=0
        found="$(printf '%s' "$found" | tr '\n' ' ')"
        pids="$pids${found:+ $found}"
    done
    if [ -n "$pids" ]; then
        printf 'true%s\n' "$pids"
    else
        printf 'false\n'
    fi
}

# Record the ingest state before copying, so it describes the copy window.
INGEST="$(ingest_state)"
INGEST_RUNNING="${INGEST%% *}"
INGEST_PIDS=""
[ "$INGEST_RUNNING" = "$INGEST" ] || INGEST_PIDS="${INGEST#* }"
if [ "$INGEST_RUNNING" != "false" ]; then
    printf 'WARN: ingest_running=%s; the corpus or index copy may be inconsistent.\n' \
        "$INGEST_RUNNING" >&2
fi

printf 'Backing up %s\n' "$DATABASE"
sqlite3 "$DATABASE" ".backup '$PARTIAL_DIR/kaki.db'" || fail "sqlite3 .backup failed."
cp -R "$DATA_ROOT/corpus" "$PARTIAL_DIR/corpus" || fail "copying corpus/ failed."
cp -R "$DATA_ROOT/chroma" "$PARTIAL_DIR/chroma" || fail "copying chroma/ failed."
find "$PARTIAL_DIR" -type d -exec chmod 700 {} +
find "$PARTIAL_DIR" -type f -exec chmod 600 {} +

backup_query() {
    sqlite3 "file:$PARTIAL_DIR/kaki.db?immutable=1" "$1"
}

INTEGRITY="$(backup_query 'pragma integrity_check;')" || fail "cannot open the backup database."
[ "$INTEGRITY" = "ok" ] || fail "integrity_check on the backup reported: $INTEGRITY"
FOREIGN_KEYS="$(backup_query 'pragma foreign_key_check;')"
[ -z "$FOREIGN_KEYS" ] || fail "foreign_key_check on the backup reported: $FOREIGN_KEYS"
USER_VERSION="$(backup_query 'pragma user_version;')"
TURNS="$(backup_query 'select count(*) from turns;')"
GIT_COMMIT="$(git -C "$REPOSITORY" rev-parse HEAD 2>/dev/null || printf 'unknown')"

{
    printf 'format=kaki-backup-manifest/1\n'
    printf 'created_utc=%s\n' "$CREATED_UTC"
    printf 'git_commit=%s\n' "$GIT_COMMIT"
    printf 'source_database=%s\n' "$DATABASE"
    printf 'user_version=%s\n' "$USER_VERSION"
    printf 'turns=%s\n' "$TURNS"
    printf 'integrity_check=%s\n' "$INTEGRITY"
    printf 'ingest_running=%s\n' "$INGEST_RUNNING"
    printf 'ingest_pids=%s\n' "$INGEST_PIDS"
    (cd "$PARTIAL_DIR" && find . -type f ! -name manifest.txt | LC_ALL=C sort) \
        | while IFS= read -r path; do
            relative="${path#./}"
            hash="$(shasum -a 256 "$PARTIAL_DIR/$relative" | awk '{print $1}')"
            printf 'sha256:%s=%s\n' "$relative" "$hash"
        done
} > "$PARTIAL_DIR/manifest.txt"
chmod 600 "$PARTIAL_DIR/manifest.txt"

[ ! -e "$SET_DIR" ] || fail "$SET_DIR appeared during the run; left $PARTIAL_DIR in place."
mv "$PARTIAL_DIR" "$SET_DIR"

printf 'Backup set: %s\n' "$SET_DIR"
printf 'user_version=%s turns=%s ingest_running=%s\n' "$USER_VERSION" "$TURNS" "$INGEST_RUNNING"
printf 'PASS: backup set written and verified.\n'
