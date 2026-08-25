# Host controls — `juval-server` (192.168.0.26)

Measured evidence for the Linux node that holds a working copy of the JUVAl
repository. Every row was produced by running the stated command on
2026-08-24, not by reading configuration intent.

**Scope.** This host's permanent role is formalized in
[`ADR-027`](../adr/ADR-027-juval-server-role.md): development / CI-like
validation / backend-worker (when needed) / automation / operational
tooling — never production primary database, Supabase self-host, identity
server, or a Vercel/Railway replacement. It runs **no persistent** JUVAl
service (`systemctl list-units | grep -i juval` returns only login
sessions; see H-3 for a note on *transient* dev-server processes), holds
**no** production database, and is **not** the deployment target —
production is Railway (backend, ADR-018) and Vercel (PWA). Nothing here
should be read as evidence about the production environment; for that see
[`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) §3.

**States.** `VERIFIED` (measured, reproducible), `PARTIAL` (measured but
incomplete), `IMPLEMENTED_NOT_VERIFIED`, `NOT_IMPLEMENTED`,
`BLOCKED_EXTERNAL` (needs an action only the user can take),
`NOT_APPLICABLE`.

## 1. Matrix

| # | Requirement | Source | Implementation | Verification command | Evidence (2026-08-24) | Gap | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| H-1 | Host firewall enabled | RF-02 | UFW | `systemctl is-active ufw`; `/etc/default/ufw`, `/etc/ufw/ufw.conf` (world-readable) | `active`; **default policy read directly 2026-08-24**: `DEFAULT_INPUT_POLICY="DROP"`, `DEFAULT_OUTPUT_POLICY="ACCEPT"`, `DEFAULT_FORWARD_POLICY="DROP"`, `IPV6=yes`, `ENABLED=yes` (start on boot) | The specific allow-list (`/etc/ufw/user.rules`, `640 root:root`) still needs sudo to enumerate — default-deny-inbound is now confirmed, but *which* ports are explicitly allowed beyond that is not | User (for the rule enumeration only) | **PARTIAL** (upgraded from the prior pass — default policy is now directly verified, not merely "active") |
| H-2 | Brute-force protection | RF-02 | fail2ban | `systemctl is-active fail2ban`; `/etc/fail2ban/jail.conf`, `/etc/fail2ban/jail.d/*.conf` (world-readable) | `active`; **effective `sshd` jail policy read directly 2026-08-24**: `jail.d/defaults-debian.conf` enables `[sshd]` with `banaction = nftables`/`backend = systemd`; no local override of the upstream defaults in `jail.conf` `[DEFAULT]` — effective policy is `bantime=10m`, `findtime=10m`, `maxretry=5` (ban after 5 failed attempts within a 10-minute window, for 10 minutes) | Live ban counts and currently-banned IPs (`fail2ban-client status sshd`) still need sudo — the socket at `/var/run/fail2ban/fail2ban.sock` is root-only | User (for live ban state only) | **PARTIAL** (upgraded — jail enablement and policy are now directly verified from config, not inferred from `active` alone) |
| H-3 | Network exposure minimised | RF-02 | Default install | `ss -tulnp \| grep LISTEN` | **Re-measured 2026-08-24 22:34**: `:22` (SSH, all interfaces) and DNS `:53` (loopback only) as before, **plus `:5173` (Vite dev server) and `:8000` (FastAPI/uvicorn) now bound to `0.0.0.0`** — two user-started foreground processes (`pts/3`/`pts/4`, started 22:31/22:32, same session as this audit), LAN-exposed rather than localhost-only | Transient, not a persistent service (§6, ADR-027 forbids this host opening app ports as part of its *permanent* role) — but while running, any LAN host can reach them unauthenticated. Recommendation: bind dev servers to `127.0.0.1` unless LAN access from another device is actually needed for the task at hand | User | **PARTIAL** (was `VERIFIED` when no app port was listening; degraded on re-measurement, not a regression this session introduced) |
| H-4 | SSH key authentication works | RF-04 | `~/.ssh/authorized_keys` | `ssh -o BatchMode=yes juval@…` | Historical verification (2026-08-24, from the Windows workstation): non-interactive key auth succeeds. **Could not be re-tested from `juval-server` itself this session** — this host holds only the public key in `authorized_keys` (`stat`: `600 juval:juval`), no private key material, by design (a server does not need to SSH into itself) | Re-verification must happen from the client side, as it did originally — do not treat the absence of a private key on this host as a finding | Agent | **VERIFIED** (2026-08-24, workstation-side; not independently re-testable from this host) |
| H-5 | SSH password authentication disabled | RF-04 | — | `ssh -o PubkeyAuthentication=no -v …` | **Re-verified 2026-08-24 22:34**, unchanged: server answers `Authentications that can continue: publickey,password` — **password auth is still ENABLED** | Password login is accepted on a host holding the repository. See §2 | User | **NOT_IMPLEMENTED** |
| H-6 | OS security patches current | RF-02 (F-01) | `unattended-upgrades` | `apt list --upgradable`; `systemctl is-enabled unattended-upgrades` | 1 upgradable package, **0 security**; unattended-upgrades `enabled`; apt metadata refreshed 2026-08-24 21:22; no `/var/run/reboot-required`; kernel 6.8.0-138 | None currently | Agent | **VERIFIED** |
| H-7 | Persistent audit logging | RF-05 | systemd-journald + rsyslog | `ls -d /var/log/journal`; `ls -l /var/log/auth.log` | `/var/log/journal` present (persistent, survives reboot); `auth.log` present, mode `0640 syslog:adm` | Retention period not configured explicitly | Agent | **PARTIAL** |
| H-8 | Log rotation | RF-05 | logrotate.timer | `systemctl is-enabled logrotate.timer` | `enabled` | None | Agent | **VERIFIED** |
| H-9 | Repository file permissions | RF-04 | Filesystem | `stat -c "%A %U:%G"` | `/home/juval` is `drwxr-x---` (no world access); repo dirs `drwxrwxr-x juval:juval` | Repo dirs are group-writable; single-user host so no second account exists to abuse it | Agent | **PARTIAL** |
| H-10 | Secrets absent from the working copy | RF-02 | `.gitignore` + scanner | `python tools/compliance_check.py` | `secret_scan`: no secret-shaped strings in 312 files; `.env` and `frontend/.env.local` present but git-ignored and never staged | None | Agent | **VERIFIED** |
| H-11 | Capacity headroom | Ops | — | `df -h /`; `free -h` | 98 G volume, 10% used (84 G free); 13 GiB RAM, 4 GiB swap, 12 GiB available | No alerting on thresholds | Agent | **PARTIAL** |
| H-12 | Backup and restore of source code | Ops / RF-05 | GitHub (`origin`) | fresh `git clone` + `diff -r` against the working tree | **Restore-tested 2026-08-24**: cloned `origin/master` into a scratch directory; `diff -r` against the working tree showed zero differences beyond this session's own not-yet-committed edits and known git-ignored artifacts (`.env.local`, `frontend/dist`, `juval_runs.db`, `*.egg-info`) | None for source code specifically. **Secrets and local-only config remain `NOT_IMPLEMENTED` by design** — no destination exists that is both off-host and as secure as this host, and copying a secret to an insecure destination is explicitly worse than no backup (ADR-027 §"Expectativas de backup") | Agent | **VERIFIED** (source code only) |
| H-13 | Browser E2E dependencies | Gate 8 | Playwright | `ldd chrome-headless-shell \| grep "not found"` | **Re-verified 2026-08-24**: nine libraries still missing (`libatk-1.0.so.0`, `libatk-bridge-2.0.so.0`, `libXcomposite.so.1`, `libXdamage.so.1`, `libXfixes.so.3`, `libXrandr.so.2`, `libgbm.so.1`, `libasound.so.2`, `libatspi.so.0`); `apt` history (`/var/log/apt/history.log`) shows no chromium-dependency package was ever installed — the `DEPENDENCIES_VALIDATED` marker Playwright writes under `~/.cache/ms-playwright/` does **not** mean the system libraries are present, it is misleading here; `sudo -n true` → `a password is required` | E2E cannot run on this host until `sudo npx playwright install-deps chromium` actually completes | User | **BLOCKED_EXTERNAL** (unchanged; the mission brief's premise that this was already run is not supported by any evidence found) |
| H-14 | Production service hardening | ADR-018 | — | — | Host runs no JUVAl service by design | — | — | **NOT_APPLICABLE** |
| H-15 | Host monitoring (disk/RAM/load/temp/failed units/log growth/backup status) | Ops, Gate 6 | `tools/host_monitor.sh` + `systemd --user` timer | `systemctl --user status juval-host-monitor.timer`; `journalctl --user -u juval-host-monitor.service` | **Implemented and verified 2026-08-24**: script checks disk, memory, 1-min load vs. core count, CPU temperature (`thermal_zone0`), failed systemd units (system+user), git-based backup status (uncommitted/unpushed), and journal disk usage; runs every 30 min via `juval-host-monitor.timer`, output captured in the user journal. First real run: `PASS WITH WARNINGS` (uncommitted changes correctly flagged) | Only this host's own state; no alert delivery channel configured (no email/webhook) — a human must check `journalctl --user` or the timer status, there is no push notification | Agent | **VERIFIED** |
| H-16 | Reboot persistence for user-level automation | Ops, Gate 7 | `loginctl enable-linger juval` | `loginctl show-user juval \| grep Linger` | **Enabled 2026-08-24 without sudo** (`Linger=yes`) — this is the standard systemd mechanism that starts `user@1000.service` at boot without an interactive login, so `systemd --user` timers (H-15) survive a reboot | Not reboot-tested — this host has active interactive sessions this audit deliberately did not disrupt (STOP conditions: real risk of losing work). Linger is a well-documented systemd behavior, but "the mechanism is enabled" is reported here, not "reboot was tested and the timer fired" | Agent | **IMPLEMENTED_NOT_VERIFIED** (mechanism enabled; reboot itself not exercised) |

## 2. H-5 — SSH password authentication is enabled

Measured, not inferred:

```
$ ssh -o BatchMode=yes -o PubkeyAuthentication=no -v juval@192.168.0.26 true
debug1: Authentications that can continue: publickey,password
```

`/etc/ssh/sshd_config` leaves `PasswordAuthentication` commented (upstream
default `yes`), and `/etc/ssh/sshd_config.d/50-cloud-init.conf` is a 27-byte
root-only drop-in — the size of the standard cloud-init
`PasswordAuthentication yes` line. Its contents could not be read without
sudo, so the *file* is inference; the **server's own answer above is the
verification**, and it is authoritative.

Risk is real but bounded: the host is LAN-only (H-3), fail2ban is running
(H-2), and UFW is active (H-1). Key auth already works (H-4), so disabling
passwords costs no access.

**EXTERNAL USER ACTION REQUIRED** — confirm a key-based session stays open
before applying, so a mistake cannot lock the host out:

```bash
printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\n' \
  | sudo tee /etc/ssh/sshd_config.d/99-juval-hardening.conf
sudo sshd -t && sudo systemctl reload ssh
# verify from the workstation, in a NEW terminal, keeping the old one open:
ssh -o PubkeyAuthentication=no -v juval@192.168.0.26 true   # must now offer publickey only
```

## 3. H-12 — source code backup is restore-tested; secrets are deliberately not backed up

**Source code**: restore-tested 2026-08-24. A fresh `git clone` of `origin`
into a scratch directory, diffed against the working tree, showed zero
unexplained differences — only this session's own not-yet-committed edits
and known git-ignored artifacts. GitHub is a real, verified recovery path
for everything tracked by git, not merely an assumption.

**What is still not backed up, and why that is the correct answer today**:

- `.env` / `frontend/.env.local` and any other local secret material.
  ADR-027 is explicit: a backup destination must be at least as secure as
  this host, and none is currently configured (no encrypted off-host
  storage, no secret manager reachable from here). Copying a secret to an
  insecure destination — a second local directory, an unencrypted USB
  drive, a personal cloud folder — would be a worse security posture than
  the current gap, not an improvement. This is a decision for the user
  (which destination, if any), not one the agent makes unilaterally.
- The nvm/Python toolchain state and any local-only shell configuration.
  These are reconstructable in minutes from
  `docs/DEVELOPMENT_ENVIRONMENT.md` and are not treated as backup-worthy
  data — losing them costs time, not information.
- Any uncommitted work in the working tree. `tools/host_monitor.sh` (H-15)
  now makes this visible on every run (`git.backup` check: flags
  uncommitted changes and unpushed commits) instead of it being an
  undetected risk — this is the "failure visibility" the backup strategy
  needed, without inventing a new backup mechanism for something that
  should simply be committed and pushed promptly.

Retention for the source-code backup is GitHub's own (unlimited, full
history). No separate retention policy is defined here because no separate
copy exists to expire.

## 4. Reboot recovery

Nothing JUVAl-specific needs a *service* to survive a reboot: no persistent
JUVAl service exists on this host by design (ADR-027). What now does need
to survive a reboot is the H-15 monitoring timer, and that is handled by
`loginctl enable-linger juval` (enabled 2026-08-24, no sudo required) —
the standard systemd mechanism that starts the user's systemd instance at
boot without an interactive login. **Not reboot-tested**: this host had
active interactive sessions throughout this audit that were deliberately
not disrupted. If the user reboots for another reason, checking
`systemctl --user status juval-host-monitor.timer` afterward would close
this verification gap.

After a reboot the host is otherwise usable once the operator logs in;
`nvm` loads from `.bashrc` for interactive shells, and automation must
source it explicitly (`docs/DEVELOPMENT_ENVIRONMENT.md` §3).
`unattended-upgrades` and `logrotate.timer` are `enabled`, so they restart
on their own.

This host's permanent role is now formalized by
[`ADR-027`](../adr/ADR-027-juval-server-role.md) — any future persistent
JUVAl service here would be a change of architecture requiring a new ADR,
not an extension of this one.

## 5. Related

[`ADR-027`](../adr/ADR-027-juval-server-role.md) (host role, security/
network/data boundaries, backup/recovery/observability expectations),
[`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) (RF-02, workstation + cloud),
[`ACCESS_CONTROL.md`](ACCESS_CONTROL.md) (RF-04),
[`SP_API_REGISTRATION_REMEDIATION.md`](SP_API_REGISTRATION_REMEDIATION.md) §20,
`docs/DEVELOPMENT_ENVIRONMENT.md` §4, `tools/host_monitor.sh` (H-15).
