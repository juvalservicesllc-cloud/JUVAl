# FusionAuth self-hosted on `juval-server` — runbook

**Authority:** ADR-031 (`Aceptada`, Opción A) and ADR-027 §"Enmienda
2026-08-26". **Control evidence plan:**
`docs/compliance/IDENTITY_DEPLOYMENT_FUSIONAUTH.md`.

**State: nothing is installed.** Every fact below about the package, its
service account, its Java bootstrap and its configuration keys was read from
the real `fusionauth-app_1.69.0-1_all.deb` with `dpkg-deb` on 2026-08-26,
without installing it. Facts about a *running* instance do not exist yet and
are not claimed anywhere in this file.

---

## 1. Network architecture

Two phases. **Phase 1 changes nothing outside the host** and produces most of
the Amazon evidence. Phase 2 is the only part that needs a decision from the
user, and it is isolated here so it blocks nothing else.

### Phase 1 — install, configure, evidence (no external network change)

```
  juval-server 192.168.0.26 ── Ubuntu 24.04.4, UFW default-deny incoming
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  :22    sshd            ── LAN     ufw allow 22/tcp   (existing) │
  │  :5173  vite            ── LAN     ufw allow from 192.168.0.0/24 │
  │  :8000  uvicorn         ── LAN     ufw allow from 192.168.0.0/24 │
  │                                                                  │
  │  :9011  fusionauth-app  ── binds 0.0.0.0, NO ufw rule            │
  │  :5432  postgresql      ── binds 127.0.0.1, NO ufw rule          │
  │                              │                                   │
  │            fusionauth-app ───┘ jdbc:postgresql://localhost:5432  │
  └──────────────────────────────────────────────────────────────────┘
        ▲
        │ ssh -L 9011:127.0.0.1:9011   ← the ONLY path to the admin UI
   operator workstation
```

New UFW rules required: **none**. FusionAuth has no bind-address property (its
`fusionauth.properties` template exposes `fusionauth-app.http.port` and
nothing else — the only `bind` mention in the file concerns node-to-node
clustering), so `:9011` listens on all interfaces. `DEFAULT_INPUT_POLICY="DROP"`
with no matching `allow` rule is what makes it unreachable, and that policy is
already `VERIFIED` (H-1). The admin UI is therefore not reachable even from the
LAN; the operator forwards it over the existing key-only SSH channel (H-5).

### Phase 2 — public issuer (needs one user decision, see §6)

```
  Railway (JUVAl backend)                Vercel (PWA)
        │  GET /.well-known/jwks.json
        ▼
  ┌───────────── managed HTTPS endpoint ──────────────┐   TLS terminates here
  └───────────────────────┬───────────────────────────┘
                          │  outbound tunnel — established FROM juval-server
                          ▼
  juval-server:  tunnel client ──► nginx 127.0.0.1:8080 ──► fusionauth :9011
                                   allow-list, default 404
```

The tunnel is **outbound**. No inbound port is opened, no port-forwarding is
configured on the router, no public IP is required, and no UFW rule is added —
which is precisely why ADR-031 could accept Option A without breaking ADR-027's
network boundary.

### Trust boundaries, stated as a table

| Zone | Members | What keeps it there |
|---|---|---|
| **PUBLIC** | `GET /.well-known/openid-configuration`, `GET /.well-known/jwks.json` | `nginx-fusionauth-public.conf` allow-list; every other path returns 404 |
| **LAN-ONLY** | `:22` SSH, `:5173` vite, `:8000` uvicorn | Existing UFW rules, unchanged (H-1/H-3) |
| **LOCALHOST / INTERNAL** | PostgreSQL `:5432`, nginx `:8080`, FusionAuth `:9011`, FusionAuth `/admin` and `/api` | Loopback binds where the software allows one; UFW default-deny where it does not |

**Why only two public paths.** `interfaces/api/auth.py` fetches
`<issuer>/.well-known/jwks.json` and validates issuer, audience, signature and
expiry locally. It makes no other call to the IdP. The discovery document is
published alongside it because `tools/verify_oidc.py` checks it and because
OIDC clients expect it. If and when the PWA gains a browser login flow — which
does not exist today — `/oauth2/*` and the hosted-login assets must be added
deliberately, with that reason recorded. Do not add them pre-emptively.

---

## 2. What gets installed

| Component | Version | Source | Notes |
|---|---|---|---|
| FusionAuth App | **1.69.0** (pinned) | `files.fusionauth.io`, `.deb` + published `.sha256` | Latest stable, released 2026-08-18 |
| PostgreSQL | 16.15 | Ubuntu `noble-updates/main` | Security-supported by the distro; FusionAuth requires ≥ 14 |
| Temurin JDK | whatever `start.sh` pins (25.0.3+9 in 1.69.0) | Adoptium GitHub release + published `.sha256.txt` | Pre-staged, see below |
| Search | `search.type=database` | — | No Elasticsearch. It would want another 1–2 GiB on a 2-core host |
| nginx | 1.24.0 | Ubuntu `noble-updates/main` | **Phase 2 only** |

### Version floor

`MINIMUM_FUSIONAUTH_VERSION = 1.63.0` (ADR-021) is unchanged and is not
lowered. 1.63.0 is where password-vs-login-identifier validation appeared; below
it the tenant template's fields are silently dropped. 1.69.0 satisfies the floor
with margin.

1.69.0 carries a breaking change tightening which keys may verify JWTs and SAML
payloads. It affects installations that have rotated signing keys or that
federate to an external SAML/OIDC identity provider. A fresh install with no
external identity provider is not affected — but that is a statement about the
documented scope of the change, not a verified observation, and it must be
re-read as such if federation is ever added.

### The Java bootstrap — the one real trap found

FusionAuth's `start.sh` resolves `JAVA_HOME` to
`/usr/local/fusionauth/java/current` and, if that path is missing, **downloads a
Temurin JDK from GitHub at service-start time**, as the service user, with no
checksum or signature check. The `.deb` ships no JVM.

Left alone that means: the service silently depends on GitHub being reachable
every time the JDK directory is absent, and the JVM arrives unverified.

`install.sh` therefore stages the JDK itself — reading the expected version out
of `start.sh` so it cannot drift from the package, downloading the tarball with
its published `.sha256.txt`, verifying it, and extracting it to the exact path
`start.sh` looks for. The vendor's download branch then never runs.

Stated precisely: the checksum is published by the same origin as the tarball,
so this proves integrity of the transfer, not provenance independent of
Adoptium. What it does buy is real — a deterministic, verifiable JVM version and
no network dependency at service start.

A second consequence, and the reason `FUSIONAUTH_USE_GLOBAL_JAVA=1` with a
distro JDK is *not* used: `start.sh` runs `sed -i` against
`$JAVA_HOME/conf/security/java.security` on every start. Against a root-owned
system JDK, that write fails as the unprivileged `fusionauth` user. Staging the
JDK inside `/usr/local/fusionauth` (owned by `fusionauth:root`) keeps that
vendor behaviour working as designed.

### Resource estimate

~1.0–1.5 GiB for the JVM (heap pinned to 768M plus JVM overhead), ~250–500 MiB
for PostgreSQL, ~3–5 GB of disk. Measured headroom on 2026-08-26: 13 GiB RAM
with 11 GiB available, 98 G volume with 83 G free. It fits.

The honest caveat is CPU, not memory: 2 cores / 4 threads already run `pytest`,
`npm build` and Playwright. A JVM and a database compete with exactly those.
And installation starting is not evidence of adequate steady-state capacity —
H-11 capacity alerting must cover the new services before any of this is called
verified.

---

## 3. Install (Phase 1)

The agent has no `sudo` on `juval-server`; every step below is user-executed,
as in every prior host-control session.

```bash
ssh juval@192.168.0.26
cd ~/JUVAl/APP && git pull
sudo bash deploy/fusionauth/install.sh
```

The script is idempotent — each step checks its end state first — and refuses
to continue rather than guess if it finds a half-configured install. It prints
no secret. The database password is generated inside the script and written
only to `/usr/local/fusionauth/config/fusionauth.properties` (0600,
`fusionauth:root`); it is never typed, echoed, or passed as a command argument.

### Verify the boundary immediately after

```bash
ss -lntp | grep -E ':(9011|5432)'   # 9011 all-interfaces, 5432 loopback
sudo ufw status verbose             # must show NO rule for 9011 or 5432
systemctl is-active fusionauth-app postgresql
curl -fsS http://127.0.0.1:9011/api/status >/dev/null && echo up
```

From the **workstation**, confirm the LAN really cannot reach it:

```bash
curl -m 5 http://192.168.0.26:9011/  # must time out or be refused
```

That last check is the one that matters. A successful response means the
firewall is not doing what H-1 says it does — stop and fix that before going
further.

---

## 4. Configure and evidence

1. **Setup wizard**, through the SSH forward only:
   `ssh -L 9011:127.0.0.1:9011 juval@192.168.0.26`, then
   `http://127.0.0.1:9011`. Creates the first admin account. That password goes
   in the operator's password manager — never in this repository, never in a
   document, never in shell history.
2. **Tenant password policy**: apply
   `deploy/fusionauth/tenant-password-policy.template.json` with
   `PATCH /api/tenant/{tenantId}`, using an API key from the environment.
   Controls 8 and 9 sit outside `passwordValidationRules` in the Tenants API —
   the template's `_controls_not_expressible_here` block says where they go.
3. **Issuer**: set the tenant's `issuer` to the public HTTPS URL from Phase 2.
   Until Phase 2 exists, tokens carry a local issuer and are only good for
   configuration evidence, not for production activation.
4. **Verify**: `python tools/verify_oidc.py --issuer <url>` and, with
   `JUVAL_IDP_API_KEY` in the environment, `--tenant-policy`. Read-only, prints
   no secret, exits non-zero on failure.
5. **Schedule backups** (§5).

Only then does `JUVAL_AUTH_MODE=oidc` get set on Railway. Setting it earlier
breaks every request against an unreachable issuer (`SECRETS.md` §8 S-4).

### What verification cannot prove

`verify_oidc.py` cannot evidence that **every account has MFA enrolled** —
enabling TOTP on the tenant is not the same as every user having enrolled, and
that distinction is exactly the kind Amazon rejected the first application over.
That evidence is a user-by-user enrolment report. Nor does it prove lockout
actually locks; that needs deliberate failed logins against a dedicated
non-sensitive test account. And it reports **control 6 as `NOT_VERIFIED` by
design**, so a fully green run can never be read as closing it.

### Licence boundary — verified 2026-08-26

Community (free, self-hosted) covers what Amazon's controls need: password
validation rules, password history, minimum/maximum password age, account
lockout, TOTP MFA, OIDC/JWT issuance. Confirmed paid, and therefore **not
used**: email and SMS MFA, and *breached password detection*. The tenant
template disables email/SMS MFA and does not enable breach detection — a
template that enabled a licensed feature would fail or be silently ignored on a
Community instance, and would quietly undermine `LICENSE_COST = $0`.

---

## 5. Backup and restore

```bash
sudo bash deploy/fusionauth/backup.sh          # → /var/backups/juval-fusionauth
```

`pg_dump` in custom format, plus a copy of `fusionauth.properties` (which holds
the database password and is written 0600 root-only). The script verifies each
dump with `pg_restore --list` before reporting success — a truncated dump passes
a size check and fails a restore, which is the worst possible moment to find
out. Retention 14 days.

Schedule it with a `systemd` timer under `juval`, following the pattern already
proven for `juval-host-monitor` (`tools/systemd/`, H-15). Do not invent a
second scheduling mechanism.

**Restore** — deliberately not a script. Restoring drops live identity data;
it is rare, high-stakes and belongs under a human's supervision:

```bash
sudo systemctl stop fusionauth-app
sudo runuser -u postgres -- dropdb fusionauth
sudo runuser -u postgres -- createdb -O fusionauth fusionauth
sudo runuser -u postgres -- pg_restore -d fusionauth /var/backups/juval-fusionauth/fusionauth-<STAMP>.dump
sudo systemctl start fusionauth-app
curl -fsS http://127.0.0.1:9011/api/status
```

**Open gap, stated plainly.** These backups are **on-host only**. They protect
against database corruption and bad upgrades; they do **not** survive loss of
the machine. ADR-027 §"Expectativas de backup" forbids copying secrets to a
destination less secure than this host, and no such destination has been chosen.
Choosing one — an encrypted off-host target — is an open user decision, and
until it is made, the disaster-recovery story for identity data is
"reprovision from scratch and re-enrol every user". Say that, do not soften it.

---

## 6. Phase 2 — the one open decision

Railway must reach the issuer over HTTPS. The constraint set is: no assumed
port-forwarding, no assumed public IP, no assumed DNS, no assumed certificate,
and no new inbound firewall rule. That rules out exposing the host directly and
leaves an outbound tunnel. Which tunnel is a user decision — it needs a
third-party account, and one option needs a domain.

| Option | Needs | Issuer hostname | Trade-off |
|---|---|---|---|
| **Cloudflare Tunnel** | a domain on Cloudflare DNS (free tier) | your own, e.g. `idp.example.com` | Stable, self-owned hostname — the `iss` claim is baked into every token, so owning it matters. Costs a domain |
| **Tailscale Funnel** | a Tailscale account only | `<host>.<tailnet>.ts.net` | No domain to buy, fastest path. The hostname is borrowed: renaming the tailnet changes the issuer, and changing an issuer means reconfiguring the tenant and every client |

**Recommendation: Cloudflare Tunnel**, for the issuer-ownership reason alone.
An issuer URL is the one identifier in this architecture that is expensive to
change later.

Whichever is chosen, the shape is identical: the tunnel client runs on
`juval-server` as a systemd service, dials out, and forwards to
`127.0.0.1:8080`, where `nginx-fusionauth-public.conf` allows exactly two
paths. Nothing else about the deployment changes.

**Before enabling it, verify the allow-list actually holds** — from outside:

```bash
curl -fsS https://<issuer>/.well-known/jwks.json | head -c 80   # expect a key set
curl -o /dev/null -w '%{http_code}\n' https://<issuer>/admin    # expect 404
curl -o /dev/null -w '%{http_code}\n' https://<issuer>/api/status # expect 404
```

Two 404s and one key set. Anything else means the surface is wider than
designed — do not proceed to `JUVAL_AUTH_MODE=oidc`.

---

## 7. Update and rollback

**Update.** Pinned, deliberate, never automatic — `unattended-upgrades` does not
know about FusionAuth, which is the correct default here.

```bash
sudo bash deploy/fusionauth/backup.sh                       # always first
sudo FUSIONAUTH_VERSION=<new> bash deploy/fusionauth/install.sh
```

Re-running the script with a new version downloads and checksum-verifies the
new package, installs it, re-stages the JDK if that version expects a different
one, and leaves the existing configuration and database untouched. FusionAuth
migrates its own schema on first start after an upgrade — which is exactly why
the backup comes first and is not optional. Read the release notes for breaking
changes before bumping a minor version.

PostgreSQL and nginx are distro packages and follow the host's existing patch
process (H-6, `unattended-upgrades`).

**Rollback.** Reversible, and the backend needs no change: its OIDC boundary is
provider-agnostic and `JUVAL_AUTH_MODE=disabled` restores the current state.

```bash
# 1. de-activate first, so nothing is validating against a dying issuer
#    (set JUVAL_AUTH_MODE=disabled on Railway, redeploy)
# 2. stop the public surface
sudo systemctl disable --now <tunnel-service>
sudo rm -f /etc/nginx/sites-enabled/juval-fusionauth-public && sudo systemctl reload nginx
# 3. stop and remove the application
sudo systemctl disable --now fusionauth-app
sudo dpkg -r fusionauth-app
# 4. only once the backups are known good and no longer needed
sudo runuser -u postgres -- dropdb fusionauth
sudo runuser -u postgres -- dropuser fusionauth
```

Step 1 before step 2 — reversing them takes the backend down instead of
degrading it. Nothing in `src/` changes at any point.
