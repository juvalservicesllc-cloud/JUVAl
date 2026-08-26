#!/usr/bin/env bash
#
# JUVAl — FusionAuth backup.
#
# Identity data is the one category on juval-server that is NOT regenerable
# from Git: users, hashed credentials and the JWT signing keys live only in
# FusionAuth's PostgreSQL database. ADR-027 §"Enmienda 2026-08-26" makes this
# a deployment requirement, not an optional extra.
#
# Scope, deliberately narrow:
#   * pg_dump of the fusionauth database (custom format, compressed);
#   * a copy of fusionauth.properties, which holds the database password and
#     is therefore treated as a secret and written 0600 root-only.
#
# NOT in scope: copying any of this off-host. ADR-027 §"Expectativas de backup"
# is explicit that no destination exists which is as secure as this host, and
# that copying a secret to an insecure destination is worse than no backup.
# Choosing an encrypted off-host destination is an open user decision — see
# README.md §"Backup and restore". Until then this protects against database
# corruption and bad upgrades, NOT against loss of the host.
#
# Usage:  sudo bash deploy/fusionauth/backup.sh [destination-dir]
#
set -euo pipefail

DEST="${1:-/var/backups/juval-fusionauth}"
KEEP=14
DB_NAME=fusionauth
FA_CONFIG=/usr/local/fusionauth/config/fusionauth.properties
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root: sudo bash $0"
command -v pg_dump >/dev/null || fail "pg_dump not found"

install -d -m 0700 "$DEST"

dump="${DEST}/fusionauth-${STAMP}.dump"
runuser -u postgres -- pg_dump --format=custom --compress=9 \
    --file="$dump" "$DB_NAME"
chmod 0600 "$dump"

# Verify the dump is readable as a dump, not merely non-empty. A truncated
# file passes a size check and fails a restore, which is the worst order to
# find out in.
runuser -u postgres -- pg_restore --list "$dump" >/dev/null \
    || fail "pg_restore --list rejected ${dump} — backup is NOT usable"

if [ -f "$FA_CONFIG" ]; then
    cp -p "$FA_CONFIG" "${DEST}/fusionauth.properties-${STAMP}"
    chmod 0600 "${DEST}/fusionauth.properties-${STAMP}"
fi

# Retention. Only files this script created are considered.
find "$DEST" -maxdepth 1 -type f \
    \( -name 'fusionauth-*.dump' -o -name 'fusionauth.properties-*' \) \
    -mtime "+${KEEP}" -delete

printf 'backup OK: %s (%s bytes), retention %d days, destination %s\n' \
    "$(basename "$dump")" "$(stat -c%s "$dump")" "$KEEP" "$DEST"
printf 'reminder: this is on-host only — it does not survive loss of this machine.\n'
