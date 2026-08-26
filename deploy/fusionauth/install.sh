#!/usr/bin/env bash
#
# JUVAl — FusionAuth self-hosted install (Phase 1: LAN/localhost only).
#
# Authorised by ADR-031 (Aceptada, Opción A) and ADR-027 §"Enmienda 2026-08-26".
# Read deploy/fusionauth/README.md before running this.
#
# What it does:
#   PostgreSQL 16 (Ubuntu main) + a dedicated database/role for FusionAuth,
#   FusionAuth App (pinned version, checksum-verified), a checksum-verified
#   Temurin JDK pre-staged so the service never downloads a JVM at start time,
#   and a production-mode configuration bound to the loopback database.
#
# What it deliberately does NOT do:
#   * no `ufw` rule is added or changed — the existing DEFAULT_INPUT_POLICY=DROP
#     is what keeps :9011 and :5432 unreachable from the LAN;
#   * no reverse proxy, no TLS, no public exposure — that is Phase 2 (README);
#   * no tenant/application/user is created — that is the operator's step, and
#     it needs an admin credential this script must never hold;
#   * nothing is printed that could be a secret.
#
# Idempotent: safe to re-run. Each step checks its own end state first.
#
# Usage:  sudo bash deploy/fusionauth/install.sh
#
set -euo pipefail

FUSIONAUTH_VERSION="${FUSIONAUTH_VERSION:-1.69.0}"
FA_HOME=/usr/local/fusionauth
FA_CONFIG="${FA_HOME}/config/fusionauth.properties"
FA_JAVA_DIR="${FA_HOME}/java"
DB_NAME=fusionauth
DB_USER=fusionauth
WORK_DIR="${WORK_DIR:-/var/cache/juval-fusionauth}"

log()  { printf '\n=== %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "run as root: sudo bash $0"

# --- 0. preflight -----------------------------------------------------------
log "Preflight"
. /etc/os-release
[ "${ID:-}" = "ubuntu" ] || fail "expected Ubuntu, found ID=${ID:-unknown}"
[ "$(uname -m)" = "x86_64" ] || fail "this script pins the x86_64 JDK build"

free_kb=$(df --output=avail -k / | tail -1)
[ "$free_kb" -gt 8388608 ] || fail "less than 8 GiB free on / — aborting"
mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
[ "$mem_mb" -gt 3000 ] || fail "less than 3 GiB RAM — aborting"
printf 'ubuntu %s, x86_64, %s MiB RAM, %s KiB free on /\n' \
    "${VERSION_ID:-?}" "$mem_mb" "$free_kb"

mkdir -p "$WORK_DIR"
chmod 0700 "$WORK_DIR"

# --- 1. PostgreSQL ----------------------------------------------------------
log "PostgreSQL"
if ! command -v psql >/dev/null 2>&1; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        postgresql postgresql-client
else
    echo "already installed: $(psql --version)"
fi
systemctl enable --now postgresql

# Ubuntu's default is listen_addresses='localhost'. Assert it rather than
# assume it: a Postgres reachable from the LAN would silently widen the
# trust boundary ADR-031 pins to localhost.
listen=$(runuser -u postgres -- psql -tAc 'show listen_addresses')
case "$listen" in
    localhost|127.0.0.1|'') echo "listen_addresses=${listen:-<empty>} — loopback only, OK" ;;
    *) fail "postgresql listen_addresses='${listen}' is not loopback-only; refusing to continue" ;;
esac

# --- 2. database role -------------------------------------------------------
log "FusionAuth database role and database"
role_exists=$(runuser -u postgres -- psql -tAc \
    "select 1 from pg_roles where rolname='${DB_USER}'")
if [ "$role_exists" = "1" ]; then
    echo "role ${DB_USER} already exists — password left untouched"
else
    # Generated here so no password is ever typed, echoed, or kept in shell
    # history. It is written only into $FA_CONFIG (0600, fusionauth:root).
    DB_PASSWORD=$(openssl rand -base64 33 | tr -d '/+=' | cut -c1-32)
    # Fed on stdin, not as an argument: an argument would be visible in `ps`
    # for the lifetime of the call. `printf` is a shell builtin, so the
    # password never becomes an argv of an external process either.
    printf "create role %s with login password '%s';\n" "$DB_USER" "$DB_PASSWORD" \
        | runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 >/dev/null
    echo "role ${DB_USER} created"
fi

db_exists=$(runuser -u postgres -- psql -tAc \
    "select 1 from pg_database where datname='${DB_NAME}'")
if [ "$db_exists" = "1" ]; then
    echo "database ${DB_NAME} already exists"
else
    runuser -u postgres -- createdb -O "${DB_USER}" "${DB_NAME}"
    echo "database ${DB_NAME} created, owned by ${DB_USER}"
fi

# --- 3. FusionAuth package --------------------------------------------------
log "FusionAuth ${FUSIONAUTH_VERSION} package"
DEB="fusionauth-app_${FUSIONAUTH_VERSION}-1_all.deb"
BASE="https://files.fusionauth.io/products/fusionauth/${FUSIONAUTH_VERSION}"
installed=$(dpkg-query -W -f='${Version}' fusionauth-app 2>/dev/null || true)
if [ "$installed" = "${FUSIONAUTH_VERSION}-1" ]; then
    echo "fusionauth-app ${installed} already installed"
else
    cd "$WORK_DIR"
    [ -f "$DEB" ] || curl -fsSL -o "$DEB" "${BASE}/${DEB}"
    curl -fsSL -o "${DEB}.sha256" "${BASE}/${DEB}.sha256"
    sha256sum -c "${DEB}.sha256" || fail "checksum mismatch on ${DEB}"
    echo "checksum verified"
    # postinst creates the system account `fusionauth` (-r, /usr/sbin/nologin)
    # and enables fusionauth-app.service with User=fusionauth. Never root.
    dpkg -i "$DEB"
fi

# --- 4. pre-stage the JVM ---------------------------------------------------
# FusionAuth's own start.sh downloads a Temurin JDK from GitHub on first start,
# unverified, as the service user. Staging it here with a checksum removes both
# the runtime network dependency and the unverified download. The version is
# read out of start.sh so this cannot drift from what the package expects.
log "Java runtime"
START_SH="${FA_HOME}/fusionauth-app/bin/start.sh"
[ -f "$START_SH" ] || fail "missing ${START_SH} — package install did not complete"
JAVA_VERSION=$(sed -n 's/^[[:space:]]*JAVA_VERSION=\(.*\)$/\1/p' "$START_SH" | head -1)
[ -n "$JAVA_VERSION" ] || fail "could not read JAVA_VERSION from start.sh"
JDK_DIR="${FA_JAVA_DIR}/jdk-${JAVA_VERSION}"
echo "package expects JDK ${JAVA_VERSION}"

if [ -d "$JDK_DIR" ] && [ -e "${FA_JAVA_DIR}/current" ]; then
    echo "already staged at ${JDK_DIR}"
else
    JDK_TAG="jdk-${JAVA_VERSION/+/%2B}"
    JDK_FILE="OpenJDK${JAVA_VERSION%%.*}U-jdk_x64_linux_hotspot_${JAVA_VERSION/+/_}.tar.gz"
    JDK_URL="https://github.com/adoptium/temurin${JAVA_VERSION%%.*}-binaries/releases/download/${JDK_TAG}/${JDK_FILE}"
    cd "$WORK_DIR"
    [ -f "$JDK_FILE" ] || curl -fsSL -o "$JDK_FILE" "$JDK_URL"
    curl -fsSL -o "${JDK_FILE}.sha256.txt" "${JDK_URL}.sha256.txt"
    sha256sum -c "${JDK_FILE}.sha256.txt" || fail "checksum mismatch on ${JDK_FILE}"
    echo "checksum verified"
    mkdir -p "$FA_JAVA_DIR"
    tar xzf "$JDK_FILE" -C "$FA_JAVA_DIR"
    [ -d "$JDK_DIR" ] || fail "expected ${JDK_DIR} after extraction"
    ln -sfn "jdk-${JAVA_VERSION}" "${FA_JAVA_DIR}/current"
    echo "staged ${JDK_DIR}"
fi

# --- 5. configuration -------------------------------------------------------
log "Configuration"
if grep -q '^database.password=' "$FA_CONFIG" 2>/dev/null \
   && ! grep -q '^database.password=fusionauth$' "$FA_CONFIG"; then
    # A configured file plus a role created in *this* run means the two now
    # disagree: the config holds an older password the new role does not have.
    # Fail loudly rather than leave an install that only breaks at connect time.
    [ -z "${DB_PASSWORD:-}" ] || fail \
        "the ${DB_USER} role was just created, but ${FA_CONFIG} already holds a
       different password. These now disagree. Resolve by hand: either drop the
       role and re-run, or set the role's password to the one in the config.
       Refusing to overwrite a configuration this script did not write."
    echo "${FA_CONFIG} already configured — not overwriting"
else
    [ -n "${DB_PASSWORD:-}" ] || fail \
        "the ${DB_USER} role pre-existed but ${FA_CONFIG} still holds the template
       password. Set the role's password manually and write it into
       ${FA_CONFIG}, or drop the role and re-run. Refusing to guess."
    mkdir -p "$(dirname "$FA_CONFIG")"
    # runtime-mode=production disables the maintenance-mode auto-configuration
    # and the development-only behaviours. search.type=database avoids adding
    # Elasticsearch to a 2-core host (ADR-031 §Consecuencias).
    cat > "$FA_CONFIG" <<PROPS
# Generated by deploy/fusionauth/install.sh — do not commit this file.
database.url=jdbc:postgresql://localhost:5432/${DB_NAME}
database.username=${DB_USER}
database.password=${DB_PASSWORD}

fusionauth-app.http.port=9011
fusionauth-app.https.enabled=false
fusionauth-app.runtime-mode=production
fusionauth-app.memory=768M
search.type=database
PROPS
    echo "wrote ${FA_CONFIG}"
fi
chown fusionauth:root "$FA_CONFIG"
chmod 0600 "$FA_CONFIG"
chown -R fusionauth:root "$FA_HOME"
chmod -R o-rwx "$FA_HOME"

# --- 6. service -------------------------------------------------------------
log "Service"
systemctl enable fusionauth-app
systemctl restart fusionauth-app

# First start runs the schema migration; it is slow on this hardware.
for i in $(seq 1 60); do
    if curl -fsS -o /dev/null "http://127.0.0.1:9011/api/status" 2>/dev/null; then
        echo "fusionauth-app answered /api/status after ~$((i * 5))s"
        break
    fi
    [ "$i" -lt 60 ] || fail \
        "no answer on 127.0.0.1:9011 after 5 min — check: journalctl -u fusionauth-app"
    sleep 5
done

# --- 7. what the operator does next ----------------------------------------
log "Installed. Nothing is exposed beyond this host."
cat <<'NEXT'
Verify the boundary (all three must be empty or loopback-only):
    ss -lntp | grep -E ':(9011|5432)'      # 9011 binds all interfaces by design
    sudo ufw status verbose                # NO rule for 9011 or 5432 must exist

Reach the admin UI without opening a port:
    ssh -L 9011:127.0.0.1:9011 juval@192.168.0.26
    # then browse http://127.0.0.1:9011 on the workstation

Then, per deploy/fusionauth/README.md:
  1. complete the setup wizard (creates the admin account — password goes in
     the operator's password manager, never in this repository);
  2. apply deploy/fusionauth/tenant-password-policy.template.json;
  3. run tools/verify_oidc.py;
  4. schedule deploy/fusionauth/backup.sh.

JUVAL_AUTH_MODE stays `disabled` until step 3 passes against the real issuer.
NEXT
