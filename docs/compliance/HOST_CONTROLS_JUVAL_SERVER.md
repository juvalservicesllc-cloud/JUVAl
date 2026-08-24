# Host controls — `juval-server` (192.168.0.26)

Measured evidence for the Linux node that holds a working copy of the JUVAl
repository. Every row was produced by running the stated command on
2026-08-24, not by reading configuration intent.

**Scope.** This host is a development/validation node. It runs **no** JUVAl
service (`systemctl list-units | grep -i juval` returns only login
sessions), holds **no** production database, and is **not** the deployment
target — production is Railway (backend, ADR-018) and Vercel (PWA). Nothing
here should be read as evidence about the production environment; for that
see [`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) §3.

**States.** `VERIFIED` (measured, reproducible), `PARTIAL` (measured but
incomplete), `IMPLEMENTED_NOT_VERIFIED`, `NOT_IMPLEMENTED`,
`BLOCKED_EXTERNAL` (needs an action only the user can take),
`NOT_APPLICABLE`.

## 1. Matrix

| # | Requirement | Source | Implementation | Verification command | Evidence (2026-08-24) | Gap | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| H-1 | Host firewall enabled | RF-02 | UFW | `systemctl is-active ufw` | `active` | Rule set not read — `ufw status` needs sudo, so *which* ports are permitted is unconfirmed | User | **PARTIAL** |
| H-2 | Brute-force protection | RF-02 | fail2ban | `systemctl is-active fail2ban` | `active` | Jail list and ban counts need sudo | User | **PARTIAL** |
| H-3 | Network exposure minimised | RF-02 | Default install | `ss -tulnp \| grep LISTEN` | Only `:22` (SSH) on all interfaces; DNS `:53` bound to loopback only. No HTTP/DB/app port listening | None | Agent | **VERIFIED** |
| H-4 | SSH key authentication works | RF-04 | `~/.ssh/authorized_keys` | `ssh -o BatchMode=yes juval@…` | Non-interactive key auth succeeds | None | Agent | **VERIFIED** |
| H-5 | SSH password authentication disabled | RF-04 | — | `ssh -o PubkeyAuthentication=no -v …` | Server answers `Authentications that can continue: publickey,password` — **password auth is ENABLED** | Password login is accepted on a host holding the repository. See §2 | User | **NOT_IMPLEMENTED** |
| H-6 | OS security patches current | RF-02 (F-01) | `unattended-upgrades` | `apt list --upgradable`; `systemctl is-enabled unattended-upgrades` | 1 upgradable package, **0 security**; unattended-upgrades `enabled`; apt metadata refreshed 2026-08-24 21:22; no `/var/run/reboot-required`; kernel 6.8.0-138 | None currently | Agent | **VERIFIED** |
| H-7 | Persistent audit logging | RF-05 | systemd-journald + rsyslog | `ls -d /var/log/journal`; `ls -l /var/log/auth.log` | `/var/log/journal` present (persistent, survives reboot); `auth.log` present, mode `0640 syslog:adm` | Retention period not configured explicitly | Agent | **PARTIAL** |
| H-8 | Log rotation | RF-05 | logrotate.timer | `systemctl is-enabled logrotate.timer` | `enabled` | None | Agent | **VERIFIED** |
| H-9 | Repository file permissions | RF-04 | Filesystem | `stat -c "%A %U:%G"` | `/home/juval` is `drwxr-x---` (no world access); repo dirs `drwxrwxr-x juval:juval` | Repo dirs are group-writable; single-user host so no second account exists to abuse it | Agent | **PARTIAL** |
| H-10 | Secrets absent from the working copy | RF-02 | `.gitignore` + scanner | `python tools/compliance_check.py` | `secret_scan`: no secret-shaped strings in 312 files; `.env` and `frontend/.env.local` present but git-ignored and never staged | None | Agent | **VERIFIED** |
| H-11 | Capacity headroom | Ops | — | `df -h /`; `free -h` | 98 G volume, 10% used (84 G free); 13 GiB RAM, 4 GiB swap, 12 GiB available | No alerting on thresholds | Agent | **PARTIAL** |
| H-12 | Backup and restore of host data | Ops / RF-05 | — | `systemctl list-units \| grep -iE "backup\|restic\|borg"` | Nothing configured (only `dpkg-db-backup`, a package-database dump, not data) | No backup exists. Mitigated, not solved, by the repo being fully pushed to GitHub — see §3 | User | **NOT_IMPLEMENTED** |
| H-13 | Browser E2E dependencies | Gate 8 | Playwright | `ldd chrome-headless-shell \| grep "not found"` | Nine system libraries missing; `sudo -n true` → `a password is required` | E2E cannot run on this host | User | **BLOCKED_EXTERNAL** |
| H-14 | Production service hardening | ADR-018 | — | — | Host runs no JUVAl service by design | — | — | **NOT_APPLICABLE** |

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

## 3. H-12 — no backup exists

Nothing on this host is backed up. What limits the damage today:

- The repository is fully pushed to GitHub (`git status` clean, 0 ahead),
  so the source is recoverable by re-cloning.
- The host stores no production data and no unique JUVAl artifact.

That is a **recovery path for the repository**, not a host backup: local
`.env` files, the nvm/Python toolchain and any unpushed work would be lost.
The honest reading is `NOT_IMPLEMENTED`, mitigated by the source living
elsewhere. Choosing a backup mechanism is a decision for the user, not one
the agent should make unilaterally.

## 4. Reboot recovery

Nothing JUVAl-specific needs to survive a reboot: no service, no timer, no
mount. After a reboot the host is usable once the operator logs in; `nvm`
loads from `.bashrc` for interactive shells, and automation must source it
explicitly (`docs/DEVELOPMENT_ENVIRONMENT.md` §3). `unattended-upgrades`
and `logrotate.timer` are `enabled`, so they restart on their own.

If this host is ever given a persistent JUVAl role, that is a change of
architecture and needs an ADR first (CLAUDE.md §3) — it is deliberately not
assumed here.

## 5. Related

[`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) (RF-02, workstation + cloud),
[`ACCESS_CONTROL.md`](ACCESS_CONTROL.md) (RF-04),
[`SP_API_REGISTRATION_REMEDIATION.md`](SP_API_REGISTRATION_REMEDIATION.md) §20,
`docs/DEVELOPMENT_ENVIRONMENT.md` §4.
