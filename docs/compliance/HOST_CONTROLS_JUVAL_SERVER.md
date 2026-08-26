# Host controls — `juval-server` (192.168.0.26)

Measured evidence for the Linux node that holds a working copy of the JUVAl
repository. Every row was produced by running the stated command on
2026-08-24, not by reading configuration intent. H-1, H-2, H-3 and H-13
were re-measured on 2026-08-26 — see §5. H-5 and H-11 were closed, and
H-3/H-7/H-9 were reinvestigated, later the same day — see §6. The user
then resolved the three pending decisions (H-3, H-7, H-9) and approved a
final reboot as the H-16 verification gate — see §7. The user then
applied the H-7 journald policy and executed the real reboot; H-7 and
H-16 were verified against direct post-reboot evidence, closing the
host-hardening phase — see §9.

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
`NOT_APPLICABLE`, `DEFERRED / ACCEPTED_RISK` (added 2026-08-26 — the user
made an explicit, scoped risk-acceptance decision *not* to close the
control; distinct from `PARTIAL`, which means "not yet closed," and never
to be read as `VERIFIED`), `READY_FOR_USER_SUDO` / `READY_FOR_USER_REBOOT`
(added 2026-08-26 — the agent has designed the exact change and cannot
apply it itself; execution and the resulting evidence are the user's
step, after which the row can be upgraded).

## 1. Matrix

| # | Requirement | Source | Implementation | Verification command | Evidence (2026-08-24) | Gap | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| H-1 | Host firewall enabled | RF-02 | UFW | `systemctl is-active ufw`; `/etc/default/ufw`, `/etc/ufw/ufw.conf` (world-readable); `sudo ufw status verbose` | `active`; default policy read directly 2026-08-24: `DEFAULT_INPUT_POLICY="DROP"`, `DEFAULT_OUTPUT_POLICY="ACCEPT"`, `DEFAULT_FORWARD_POLICY="DROP"`, `IPV6=yes`; **rule allow-list reported by the user 2026-08-26 (`sudo ufw status verbose`)**: logging low, default deny incoming, default allow outgoing, routed disabled, `22/tcp` (OpenSSH) allowed, `5173/tcp` allowed **only from `192.168.0.0/24`**, `8000/tcp` allowed **only from `192.168.0.0/24`**, OpenSSH IPv6 allowed | None — allow-list now enumerated, closing the prior sudo gap. The agent independently re-confirmed 2026-08-26 it still has no sudo (`sudo -n true` → `a password is required`), so this row's evidence is user-reported, not agent-executed | User (ran the sudo command and reported output) | **VERIFIED** (2026-08-26 — upgraded from `PARTIAL`; allow-list matches the intended LAN-only exposure for 5173/8000, see H-3; user-reported unchanged post-reboot 2026-08-26 session 4, see §9) |
| H-2 | Brute-force protection | RF-02 | fail2ban | `systemctl is-active fail2ban`; `/etc/fail2ban/jail.conf`, `/etc/fail2ban/jail.d/*.conf` (world-readable); `sudo fail2ban-client status sshd` | `active`; effective `sshd` jail policy read directly 2026-08-24: `bantime=10m`, `findtime=10m`, `maxretry=5`; **live state reported by the user 2026-08-26 (`sudo fail2ban-client status sshd`)**: jail active, currently failed 0, total failed 0, currently banned 0, total banned 0, journal filter active | None — live ban state now confirmed, closing the prior sudo gap. Agent-side sudo access independently re-checked 2026-08-26 (still unavailable), so this row's evidence is user-reported | User (ran the sudo command and reported output) | **VERIFIED** (2026-08-26 — upgraded from `PARTIAL`; jail is live and the host has no ongoing brute-force activity; user-reported unchanged post-reboot 2026-08-26 session 4, see §9) |
| H-3 | Network exposure minimised | RF-02 | Default install | `ss -tulnp \| grep LISTEN` | **Re-measured 2026-08-24 22:34**: `:22` (SSH, all interfaces) and DNS `:53` (loopback only) as before, **plus `:5173` (Vite dev server) and `:8000` (FastAPI/uvicorn) bound to `0.0.0.0`** — two user-started foreground processes, LAN-exposed rather than localhost-only. **2026-08-26**: same two processes still listening on `0.0.0.0:5173`/`0.0.0.0:8000` (`ps -o lstart` confirms unchanged since 2026-08-24 22:31/22:32) — the *application* bind is still all-interfaces and unauthenticated at the app layer. What is new is the perimeter control: H-1's user-reported UFW rule enumeration confirms `5173/tcp` and `8000/tcp` are allowed **only from `192.168.0.0/24`**, so reachability is firewall-constrained to the LAN subnet, not open to the internet | The app itself still binds `0.0.0.0` with no application-layer auth (`JUVAL_AUTH_MODE=disabled`). **USER DECISION recorded 2026-08-26 (§7)**: keep `0.0.0.0` — cross-device LAN development/testing is a real current need — with UFW's LAN-only allow-list (`5173/tcp`, `8000/tcp` restricted to `192.168.0.0/24`, default-deny incoming) as the compensating control. This is a scoped, time-boxed acceptance for the **current development/server phase**, explicitly to be revisited before any public/production exposure — it does not satisfy the control's own definition (loopback binding or application-layer auth), so it is **not** `VERIFIED` | The app itself still has no application-layer authentication and binds all interfaces; the LAN-only firewall constraint (H-1) is the entire compensating control. Nothing left for the agent to do here — the decision is made and recorded, not a technical gap | User (decision made 2026-08-26) | **PARTIAL — ACCEPTED DEVELOPMENT-LAN RISK / COMPENSATING CONTROL** (2026-08-26; not `VERIFIED` by design — see §7) |
| H-4 | SSH key authentication works | RF-04 | `~/.ssh/authorized_keys` | `ssh -o BatchMode=yes juval@…` | Historical verification (2026-08-24, from the Windows workstation): non-interactive key auth succeeds. **Could not be re-tested from `juval-server` itself this session** — this host holds only the public key in `authorized_keys` (`stat`: `600 juval:juval`), no private key material, by design (a server does not need to SSH into itself) | Re-verification must happen from the client side, as it did originally — do not treat the absence of a private key on this host as a finding | Agent | **VERIFIED** (2026-08-24, workstation-side; not independently re-testable from this host) |
| H-5 | SSH password authentication disabled | RF-04 | `/etc/ssh/sshd_config.d/50-cloud-init.conf` (`PasswordAuthentication no`) | `sudo sshd -T \| grep -E 'passwordauthentication\|pubkeyauthentication\|permitrootlogin'`; external client test forcing each auth method in turn | **USER-EXECUTED, 2026-08-26**: user edited the cloud-init drop-in (backing up the original first, see §2), `sudo sshd -t` passed, `sudo sshd -T` shows `permitrootlogin without-password`, `pubkeyauthentication yes`, `passwordauthentication no`; `sudo systemctl reload ssh` → `is-active` = `active`. **External Windows client tests (USER-EXECUTED)**: (1) `ssh -o PasswordAuthentication=no juval@192.168.0.26` → succeeded, normal shell — key-only auth works; (2) `ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 juval@192.168.0.26` → `Permission denied (publickey)` — password-only auth is rejected by the server. Test (2) is the direct external proof of the H-5 requirement, mirroring how H-4 was verified client-side. **AGENT-EXECUTED, same session**: confirmed via `sshd`'s actual `Include /etc/ssh/sshd_config.d/*.conf` glob semantics (read from `/etc/ssh/sshd_config` and tested against real glob/`fnmatch` behavior) that the backup file `50-cloud-init.conf.backup-20260826` does **not** match `*.conf` and is therefore never read by `sshd` — see §2 | None. The evidence chain (local sudo config check + reload + two independent external auth-method tests) is sufficient and self-consistent | User (change + validation + external tests), Agent (backup-file glob safety check) | **VERIFIED** (2026-08-26 — upgraded from `NOT_IMPLEMENTED`; USER-EXECUTED evidence, agent-verified backup-file safety; persisted through the real reboot in session 4, `sshd -T` reported unchanged and `ssh -o PasswordAuthentication=no` reconnect succeeded externally, see §9) |
| H-6 | OS security patches current | RF-02 (F-01) | `unattended-upgrades` | `apt list --upgradable`; `systemctl is-enabled unattended-upgrades` | 1 upgradable package, **0 security**; unattended-upgrades `enabled`; apt metadata refreshed 2026-08-24 21:22; no `/var/run/reboot-required`; kernel 6.8.0-138 | None currently | Agent | **VERIFIED** |
| H-7 | Persistent audit logging | RF-05 | systemd-journald + rsyslog | `ls -d /var/log/journal`; `ls -l /var/log/auth.log`; `cat /etc/logrotate.d/rsyslog`; `cat /etc/systemd/journald.conf`; `systemd-analyze cat-config systemd/journald.conf` | **Applied (USER-EXECUTED) and verified post-reboot (AGENT-EXECUTED), 2026-08-26 — see §9**: `/etc/systemd/journald.conf.d/99-juval-retention.conf` created (`[Journal]\nMaxRetentionSec=30day`), `systemd-analyze cat-config` showed it merged pre-reboot, `systemctl restart systemd-journald` → `active`, `journalctl --disk-usage` 44.2M pre-reboot. After the real reboot the agent independently re-read the drop-in directly (world-readable, content unchanged), re-ran `systemd-analyze cat-config systemd/journald.conf \| grep -B2 -A1 MaxRetentionSec` (no sudo needed) and confirmed the effective, merged value is still `MaxRetentionSec=30day` sourced from `99-juval-retention.conf`; `systemctl is-active systemd-journald` → `active`; `journalctl --disk-usage` → 60.4M. The host monitor's own `log.growth` check (H-11/H-15) independently reported `60.4M` in its first post-reboot run, a third confirming source | None — effective configuration is confirmed post-reboot by direct agent read of the drop-in and by `systemd-analyze`'s own merge resolution, not only by user report. As noted at design time, no log on this host is yet 30 days old, so *actual pruning* still cannot be demonstrated — "effective configuration persisted across reboot" is what is verified here, matching the standard used at design time | User (applied pre-reboot), Agent (post-reboot re-verification) | **VERIFIED** (2026-08-26, session 4 — upgraded from `READY_FOR_USER_SUDO`; effective config confirmed both pre- and post-reboot) |
| H-8 | Log rotation | RF-05 | logrotate.timer | `systemctl is-enabled logrotate.timer` | `enabled` | None | Agent | **VERIFIED** |
| H-9 | Repository file permissions | RF-04 | Filesystem | `stat -c "%A %U:%G"`; `umask`; `git config core.sharedRepository` | **Re-checked 2026-08-26**: `/home/juval` is `drwxr-x---` (no world access); `~/JUVAl` and `~/JUVAl/APP` are `drwxrwxr-x juval:juval` (group-writable); default `umask 0002` explains the group-write bit — it is not a one-off misconfiguration, every new file/dir inherits it; `core.sharedRepository` unset (git's own default, not a shared-repo setup) | **USER DECISION recorded 2026-08-26 (§7)**: explicitly **do not** perform a repository-wide recursive `chmod` — single-user host, current measured risk is low (no second local account exists to abuse group-write access), and the blast radius (`.venv/`, `node_modules/`, tens of thousands of files, some possibly open in an active dev session) exceeds the security benefit. This closes the investigation, not the control: the underlying permissions are unchanged and group-write access remains technically present | Repo dirs remain group-writable (`umask 0002`, applied consistently, not a one-off). Accepted by explicit user decision, not by agent default. If future hardening is warranted (e.g. before this host stops being single-user), the targeted alternative is tightening specific sensitive paths only (e.g. `.env`, any local secret material) rather than the whole tree — not attempted here, no such path currently holds anything sensitive beyond what H-10 already confirms is git-ignored | User (decision made 2026-08-26) | **DEFERRED / ACCEPTED_RISK** (2026-08-26 — reclassified from `PARTIAL` to record that this is now a deliberate, explicit user decision rather than an unresolved gap; never `VERIFIED`) |
| H-10 | Secrets absent from the working copy | RF-02 | `.gitignore` + scanner | `python tools/compliance_check.py` | `secret_scan`: no secret-shaped strings in 312 files; `.env` and `frontend/.env.local` present but git-ignored and never staged | None | Agent | **VERIFIED** |
| H-11 | Capacity headroom | Ops | `tools/host_monitor.sh` (H-15) | `df -h /`; `free -h`; read `tools/host_monitor.sh` disk/memory threshold logic; `journalctl --user -u juval-host-monitor.service` | **Re-checked 2026-08-26**: 98 G volume, 11% used (83 G free); 13 GiB RAM, 4 GiB swap, 11 GiB available. `tools/host_monitor.sh` (verified by reading the script, lines 20-38) has real coded thresholds, not just informational output: disk WARN at ≥80%, FAIL at ≥90%; memory WARN at <10% available, FAIL at <5% available. This runs automatically every ~30 min via the H-15 timer (confirmed live in Gate 4: consecutive journal entries 12:49/13:20/13:51/14:22/14:53/15:23 UTC, all with real PASS/WARN results) | None for disk/RAM — thresholds exist, are coded (not just displayed), and run unattended on a verified cadence. The `log.growth` check in the same script is informational-only (no threshold, always PASS) — that gap belongs to H-7's retention question, not to this capacity control | Agent | **VERIFIED** (2026-08-26 — upgraded from `PARTIAL`; the "no alerting on thresholds" gap was already closed by H-15's `host_monitor.sh`, just not previously cross-referenced here; reboot persistence confirmed agent-side in session 4 — timer active immediately post-boot and its first unattended run at 16:21:41 UTC returned `ALL CHECKS PASS`, see §9) |
| H-12 | Backup and restore of source code | Ops / RF-05 | GitHub (`origin`) | fresh `git clone` + `diff -r` against the working tree | **Restore-tested 2026-08-24**: cloned `origin/master` into a scratch directory; `diff -r` against the working tree showed zero differences beyond this session's own not-yet-committed edits and known git-ignored artifacts (`.env.local`, `frontend/dist`, `juval_runs.db`, `*.egg-info`) | None for source code specifically. **Secrets and local-only config remain `NOT_IMPLEMENTED` by design** — no destination exists that is both off-host and as secure as this host, and copying a secret to an insecure destination is explicitly worse than no backup (ADR-027 §"Expectativas de backup") | Agent | **VERIFIED** (source code only) |
| H-13 | Browser E2E dependencies | Gate 8 | Playwright | `ldd chrome-headless-shell \| grep "not found"`; `E2E_BASE_URL=... npx playwright test` | **Resolved 2026-08-26**: `/var/log/apt/history.log` shows `Start-Date: 2026-08-26 13:12:37`, `Commandline: apt-get install -y --no-install-recommends libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 ... xvfb ...`, `Requested-By: juval (1000)` (sudo, with the user-scoped nvm `npx` exposed on `PATH`); all 9 previously-missing libraries confirmed present by direct `find` (`libatk-1.0.so.0`, `libatk-bridge-2.0.so.0`, `libXcomposite.so.1`, `libXdamage.so.1`, `libXfixes.so.3`, `libXrandr.so.2`, `libgbm.so.1`, `libasound.so.2`, `libatspi.so.0` all under `/usr/lib/x86_64-linux-gnu/`); `ldd` on both `chrome-headless-shell` and `chrome` (`~/.cache/ms-playwright/chromium{,_headless_shell}-1234/...`) shows **zero** `not found` lines, both binaries answer `--version` (`Google Chrome for Testing 151.0.7922.34`); **full E2E suite executed for real** on isolated ports (backend `127.0.0.1:8001`, fresh SQLite db; frontend `vite build` + `npm run preview --host 127.0.0.1 --port 5180`, avoiding the pre-existing LAN-bound 5173/8000 dev servers) — **27/27 passing**, same count as the historical Windows baseline | None | Agent (deps install by User via sudo; E2E execution and verification by Agent) | **VERIFIED** (2026-08-26 — upgraded from `BLOCKED_EXTERNAL`; the Linux E2E blocker is closed) |
| H-14 | Production service hardening | ADR-018 | — | — | Host runs no JUVAl service by design | — | — | **NOT_APPLICABLE** |
| H-15 | Host monitoring (disk/RAM/load/temp/failed units/log growth/backup status) | Ops, Gate 6 | `tools/host_monitor.sh` + `systemd --user` timer | `systemctl --user status juval-host-monitor.timer`; `journalctl --user -u juval-host-monitor.service` | **Implemented and verified 2026-08-24**; **re-verified live 2026-08-26**: `systemctl --user show` reports `ActiveState=active`, `Result=success`, `LastTriggerUSec` = 2026-08-26 15:23:39 UTC; six consecutive real runs inspected in the journal (12:49→15:23 UTC, ~30 min apart), all `PASS`/`PASS WITH WARNINGS` with correct per-check reasoning (e.g. flagged 1 unpushed commit mid-session, cleared once pushed). Disk/memory checks are real coded thresholds (80/90%, 10/5%) — see H-11. **2026-08-26**: the two systemd unit files (`juval-host-monitor.timer`/`.service`) were copied byte-for-byte from `~/.config/systemd/user/` into `tools/systemd/` (git-tracked, `diff` confirmed identical) with an install `README.md` — closing the prior "not reproducible from Git" gap; the live host's copy in `~/.config/systemd/user/` was not modified | Only this host's own state; no alert delivery channel configured (no email/webhook) — a human must check `journalctl --user` or the timer status, there is no push notification. `log.growth` check is informational only (no threshold) | Agent | **VERIFIED** (re-confirmed 2026-08-26; unit files now git-tracked under `tools/systemd/`) |
| H-16 | Reboot persistence for user-level automation | Ops, Gate 7 | `loginctl enable-linger juval` | `loginctl show-user juval \| grep Linger`; full PRECHECK/POSTCHECK procedure in §7; post-reboot re-verification in §9 | **Real reboot executed (USER-EXECUTED) and postchecked (AGENT-EXECUTED + USER-EXECUTED external), 2026-08-26 — see §9**: new boot ID `a97e9f80ac1c47ec940e46b152b48606` (agent-confirmed via `journalctl --list-boots`, prior boot ended 16:16:00 UTC, new boot started 16:16:12 UTC); external Windows key-only SSH reconnect succeeded (USER-EXECUTED); `Linger=yes` persisted (agent-confirmed); `juval-host-monitor.timer` `enabled`/`active (waiting)` immediately after boot (agent-confirmed), and its first post-reboot run at 16:21:41 UTC executed unattended with `RESULT: ALL CHECKS PASS` (agent-captured live from the journal, not user-reported); toolchain (Node v24.19.0, npm 11.17.0, system + venv Python 3.12.3) confirmed post-reboot (agent-executed); repository clean at `ddb7a66`, matching the pre-reboot hash (agent-executed); UFW and fail2ban reported by the user as active with unchanged rules/jail state (agent has no sudo to re-verify, consistent with every prior session); expected absence of `:5173`/`:8000` listeners confirmed (agent-executed, `ss -lntp`) | None against the acceptance criteria enumerated for this gate. Sudo-gated checks (`ufw status`, `fail2ban-client status`, `sshd -T`) remain user-reported rather than agent-re-executed post-reboot — an unchanged limitation carried from every earlier session, not new to this pass | User (reboot, external SSH test, UFW/fail2ban reporting), Agent (boot-ID/timer/monitor-run/toolchain/repo/listener verification) | **VERIFIED** (2026-08-26, session 4 — upgraded from `READY_FOR_USER_REBOOT`; all enumerated H-16 acceptance criteria satisfied) |

## 2. H-5 — SSH password authentication is disabled (closed 2026-08-26)

**Status: `VERIFIED`, USER-EXECUTED evidence, agent-verified backup-file
safety.**

Prior state (superseded, kept for history): `/etc/ssh/sshd_config` leaves
`PasswordAuthentication` commented (upstream default `yes`), and
`/etc/ssh/sshd_config.d/50-cloud-init.conf` carried the cloud-init
`PasswordAuthentication yes` line. The server's own answer to a probe
confirmed this: `Authentications that can continue: publickey,password`.

**What the user did (USER-EXECUTED, 2026-08-26)**: backed up the original
drop-in to `/etc/ssh/sshd_config.d/50-cloud-init.conf.backup-20260826`
*before* changing anything, then edited the active file to
`PasswordAuthentication no`. Validated locally:

```
$ sudo sshd -t
(no output = pass)
$ sudo sshd -T | grep -E 'passwordauthentication|pubkeyauthentication|permitrootlogin'
permitrootlogin without-password
pubkeyauthentication yes
passwordauthentication no
$ sudo systemctl reload ssh && sudo systemctl is-active ssh
active
```

Then confirmed externally from the Windows workstation, in two directions:

```
# (1) password disabled, pubkey allowed — must succeed
$ ssh -o PasswordAuthentication=no juval@192.168.0.26
→ SUCCESS, normal shell

# (2) pubkey disabled, password forced — must fail
$ ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password \
      -o NumberOfPasswordPrompts=1 juval@192.168.0.26
→ juval@192.168.0.26: Permission denied (publickey).
```

Test (2) is the direct, external, client-side proof that password
authentication is rejected — the same evidentiary standard already applied
to H-4 (SSH key auth verified from the workstation, not from the host
itself).

**What the agent verified (AGENT-EXECUTED, same session, read-only, no
sudo)**: whether the backup file left in `sshd_config.d/` could
accidentally be read by `sshd` and reintroduce the old setting.
`/etc/ssh/sshd_config` line 12 reads:

```
Include /etc/ssh/sshd_config.d/*.conf
```

The backup filename is `50-cloud-init.conf.backup-20260826` — it does
**not** end in `.conf` (it ends in `.backup-20260826`), so it cannot match
the `*.conf` glob. This was checked two ways, not assumed: a real bash
glob expansion against the live directory, and a `case`/`fnmatch`-style
pattern test — both confirm only `50-cloud-init.conf` (the active file)
matches. `ls -la` also confirms both files are `0600 root:root`, unreadable
by the `juval` account, consistent with the backup being untouched since
its creation (mtime 2026-08-24, before this change — see below).

**Backup file safety verdict**: keeping
`50-cloud-init.conf.backup-20260826` inside `sshd_config.d/` is **safe, not
ambiguous** — it is provably excluded from `Include` by OpenSSH's own glob
semantics, independent of file content or permissions. No file needs to be
moved to close H-5. As an optional hygiene improvement (not required for
correctness), it can be relocated outside the include directory so a future
`.conf`-suffixed rename can't reintroduce risk:

```bash
sudo mkdir -p /etc/ssh/backups
sudo mv /etc/ssh/sshd_config.d/50-cloud-init.conf.backup-20260826 \
        /etc/ssh/backups/50-cloud-init.conf.backup-20260826
```

This command is **not required** and was **not run** — offered only if the
user wants it. Do not delete the backup.

Residual risk is unchanged from the prior analysis: the host is LAN-only
(H-1/H-3), fail2ban is active (H-2), and key auth was already proven to
work (H-4) before passwords were disabled, so this change costs no
legitimate access.

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

## 5. 2026-08-26 update — H-1, H-2, H-13 closed; H-3 evidence strengthened

**H-13 (Linux E2E dependency blocker): closed.** The prior session's
blocker was genuine — `sudo` had no cached credential and the mission
brief's premise that dependencies were already installed was unsupported
by evidence. This session the user ran the actual install using the
existing user-scoped nvm Node (not a second Node distribution — none was
installed), exposing its `PATH` to `sudo` so `sudo npx playwright
install-deps chromium` (or an equivalent explicit `apt-get install` of
the same package set, per the apt history line quoted in the H-13 row)
could resolve `npx`. The agent independently verified the result: all 9
libraries present on disk, `ldd` clean on both Chromium binaries, and —
the only verification that actually matters — **the real E2E suite run
end-to-end and passing 27/27**, matching the historical Windows count.

**Method note**: the agent ran E2E against isolated ports (backend
`127.0.0.1:8001` with a scratch SQLite db, frontend production build
served via `npm run preview` on `127.0.0.1:5180`), not the pre-existing
dev servers already listening on `0.0.0.0:5173`/`0.0.0.0:8000` (running
since 2026-08-24 22:31/22:32, unrelated to this task). This follows
`frontend/e2e/README.md`'s own documented rationale — an isolated port
means a stale/concurrent server can't be mistaken for the result. Those
pre-existing dev-server processes were left running untouched; the
agent's own backend/frontend processes on 8001/5180 were torn down after
the run, and `frontend/.env.local` was restored to its original content
(`VITE_API_BASE_URL=http://192.168.0.26:8000`). `git status` was clean
before and after — no untracked artifacts (`dist/`, `.env.local`) were
staged, both are already `.gitignore`d.

**H-1 / H-2 (UFW allow-list, fail2ban live state): closed, but by
user-reported evidence, not agent-executed evidence.** The agent still
has no sudo on this host (`sudo -n true` → `a password is required`,
re-confirmed 2026-08-26) and cannot run `ufw status` or
`fail2ban-client status` itself (`ERROR: You need to be root to run
this script`; `Permission denied to socket`). The user ran both commands
with sudo and reported the output, which is treated here the same way
H-4's workstation-side SSH verification is treated: real evidence,
sourced from the user rather than re-executed by the agent this session.
The reported UFW allow-list (`22/tcp` open, `5173/tcp` and `8000/tcp`
restricted to `192.168.0.0/24`) is consistent with — and explains — the
H-3 measurement that those two ports are listening on `0.0.0.0`: the
application binds all interfaces, but the firewall is what actually
constrains reachability to the LAN subnet. Per the mission brief, these
ports must not be described as internet-exposed; the UFW evidence is
exactly why that description would be wrong.

**H-3: still `PARTIAL`, not upgraded.** The firewall constraint is now
directly confirmed rather than inferred, which is real progress, but the
underlying finding — the app processes bind `0.0.0.0` and have no
application-layer authentication — is unchanged. UFW is a compensating
network control, not a fix at the layer H-3 measures.

**Not touched that session, by mission constraint**: UFW rules,
fail2ban configuration, SSH authentication (H-5 was `NOT_IMPLEMENTED` at
the time — **superseded, see §6**), FusionAuth deployment, AI Analyst,
enrichment. No second Node/npm distribution was installed; the existing
nvm-scoped one was reused for both the dependency install and the E2E
run.

## 6. 2026-08-26 (continued) — H-5 closed, H-11 closed, H-3/H-7/H-9
investigated, monitoring re-verified and made reproducible from Git

This is a second pass on the same day, after the user hardened SSH
directly on the host (§2) and asked for a full host-control-phase
closure sweep. Baseline for this pass: `cf030c6`, clean tree, 0/0
divergence from `origin/master` (re-verified before starting).

- **H-5**: closed — see §2 for the full evidence chain. Status matrix
  above updated `NOT_IMPLEMENTED → VERIFIED`.
- **H-11**: closed by cross-reference, not new work — `tools/host_monitor.sh`
  (implemented for H-15 on 2026-08-24) already has coded disk (80/90%)
  and memory (10/5%) thresholds, running automatically every ~30 min.
  The H-11 row's "no alerting on thresholds" gap was stale; it predated
  or wasn't cross-checked against H-15. Status matrix updated
  `PARTIAL → VERIFIED`.
- **H-15 (monitor)**: re-verified live — `systemctl --user show` and six
  consecutive journal entries (12:49→15:23 UTC) confirm the timer fires
  on its own every ~30 min with correct PASS/WARN output, not merely
  that the script exists. The systemd unit files were **not** previously
  tracked in Git (`~/.config/systemd/user/*.timer|*.service` is
  host-local state) — copied byte-for-byte into `tools/systemd/` this
  session (`diff` confirmed identical) with an install `README.md`, so
  the monitoring setup can now be reconstructed from a fresh clone
  instead of only living on this one host. The live host's own copy
  under `~/.config/systemd/user/` was left untouched (no reload/restart
  needed — nothing there changed).
- **H-7 (audit log retention)**: re-investigated, still `PARTIAL`.
  New evidence: `auth.log` (via rsyslog/logrotate) *does* have an
  explicit, bounded retention — `rotate 4` + `weekly` in
  `/etc/logrotate.d/rsyslog`, world-readable, ≈4 weeks. What remains
  open is `journald`'s own retention: `/etc/systemd/journald.conf` has
  `SystemMaxUse`/`MaxRetentionSec`/`MaxFileSec` all commented out, so it
  relies on upstream auto-vacuum defaults rather than an explicit,
  recorded value. Closing this needs two things this agent will not
  decide unilaterally: **(1) a retention-period decision** — how many
  days of journal/audit history this host is required to keep (no
  number is specified anywhere in `docs/compliance/`, so there is no
  existing decision to read off), and **(2) `sudo`** to write a
  `journald.conf.d/` drop-in. **STOPPED per Gate 3** — reporting the
  decision needed rather than picking a number. If/when the user
  decides a retention period (e.g. 90 days is a common baseline, offered
  as a suggestion, not a decision made here), the closing command would
  be:

  ```bash
  printf '[Journal]\nMaxRetentionSec=90day\nSystemMaxUse=2G\n' \
    | sudo tee /etc/systemd/journald.conf.d/99-juval-retention.conf
  sudo systemctl restart systemd-journald
  ```

  Not run this session.
- **H-9 (repo group-writable dirs)**: re-investigated, still `PARTIAL`.
  Root cause identified precisely this session: `umask 0002` on this
  account, applied consistently (not a one-off `chmod`), and
  `core.sharedRepository` is unset (git's own default). Real-world risk
  stays low — single-user host, no second local account. **Not closed**:
  the mechanical fix (`chmod -R g-w` across `~/JUVAl/APP`, or changing
  `umask` in `.bashrc`) touches the entire working tree including
  `.venv/` and `node_modules/` — tens of thousands of files, non-trivial
  blast radius for a risk this host's own threat model already treats as
  low. This is a judgment call about acceptable risk vs. disruption, not
  a technical blocker, so it is reported rather than auto-applied. If the
  user wants it closed:

  ```bash
  find ~/JUVAl/APP -path ~/JUVAl/APP/.git -prune -o -exec chmod g-w {} +
  echo 'umask 0027' >> ~/.bashrc   # future files/dirs default to non-group-writable
  ```

  Not run this session.
- **H-3 (network exposure)**: re-investigated, still `PARTIAL`, unchanged
  from earlier 2026-08-26 evidence. Confirmed again this pass that this
  is a **product/workflow decision** (bind dev servers to `127.0.0.1` and
  lose LAN-device testing, vs. keep `0.0.0.0` and rely on UFW as the
  compensating control) rather than a technical gap — see the H-3 matrix
  row above for the exact tradeoff. **STOPPED per Gate 3**, not touched.
- **Reboot readiness**: no reboot performed (mission brief forbids it).
  See §7 below for the exact user-executed procedure that would close
  the remaining `IMPLEMENTED_NOT_VERIFIED` on H-16 and the "not
  reboot-tested" note in §4.
- **Backup/recovery (H-12)**: re-read, no change needed — the 2026-08-24
  analysis (source code restore-tested via GitHub, secrets deliberately
  excluded pending a destination decision, local SQLite treated as
  disposable runtime state) still holds and was not contradicted by
  anything measured this session.

## 7. 2026-08-26 (session 3) — user decisions recorded; H-7 sudo block staged; H-16 reboot procedure finalized

Baseline for this pass: `9dfc5fc`, clean tree. `HEAD...origin/master` read
`1 0` (ahead 1, behind 0), not `0 0` as the mission brief expected — this
is the known, already-reported state from the prior session (Linux has no
GitHub credentials to push `9dfc5fc`; see §"Push status" in that session's
report), not a new or unexplained divergence. Treated as expected, not a
STOP condition.

### 7.1 H-3 — decision recorded: keep `0.0.0.0`, accept LAN-only risk

**Decision (user, 2026-08-26)**: keep the frontend/backend dev servers
bound to `0.0.0.0` rather than `127.0.0.1`. Reason given: JUVAl currently
requires cross-device LAN development/testing. Compensating control:
UFW (H-1, `VERIFIED`) restricts `5173/tcp` and `8000/tcp` to
`192.168.0.0/24` with a default-deny-incoming policy.

This does **not** satisfy H-3's own control definition (loopback binding
or application-layer auth), so per explicit instruction the row stays
`PARTIAL`, now qualified `ACCEPTED DEVELOPMENT-LAN RISK / COMPENSATING
CONTROL` rather than left as an unexplained gap. **Scope**: this decision
applies to the current development/server phase only and must be
revisited before any public/production exposure — recorded here as the
condition under which it was made, not as a standing exemption.

**ADR question**: is this a material architecture/security decision
requiring a new ADR under this repo's governance (CLAUDE.md §18)? No —
it does not select or change a technology, a data model, a persistence
choice, an auth provider, or any layer boundary (§6/ADR-001); it is a
scoped, reversible, time-boxed operational risk acceptance about how two
*existing* dev processes bind a socket during the *current* development
phase, explicitly flagged for revisit before production. The repo's own
ADR criteria (see the list of what *does* get an ADR: PWA vs. `.exe`,
FastAPI, Supabase, Railway, identity provider) are all standing
technology/architecture selections, not this. It belongs exactly where
it already lives — this host-control document — not in `docs/adr/`. No
ADR created.

### 7.2 H-7 — explicit 30-day journald retention: designed, staged, not applied

**Decision (user, 2026-08-26)**: replace journald's implicit/default
retention with an explicit `MaxRetentionSec=30day` policy, for
determinism and reproducibility rather than relying on unstated system
defaults.

**Design basis (AGENT-EXECUTED, read-only, no sudo, 2026-08-26)**:
- `/etc/systemd/journald.conf.d/` does not currently exist — no existing
  drop-in to conflict with or overwrite.
- `/etc/systemd/journald.conf` itself has every retention-relevant
  directive commented out (`SystemMaxUse`, `RuntimeMaxUse`,
  `MaxRetentionSec`, `MaxFileSec` all inactive) — confirming there is
  nothing already pinning retention today, consistent with §6's H-7
  finding.
- `systemd 255` (`systemd --version`) supports `MaxRetentionSec` natively
  — no compatibility concern.
- Current journal usage is 44.2M on an 83G-free volume — this change is
  about *determinism*, not urgency; nothing is at risk of being deleted
  prematurely or of overflowing disk.
- Smallest configuration that satisfies the decision: a single-directive
  `[Journal]` drop-in. No `SystemMaxUse` size cap was added — the user's
  decision was time-based determinism, not a size policy, and adding one
  would be scope beyond what was decided.

**The agent has no sudo on this host** (`sudo -n true` → `a password is
required`, re-confirmed this session) and cannot write
`/etc/systemd/journald.conf.d/` or restart `systemd-journald`. Per Gate 3,
this STOPS here with one consolidated block for the user to run:

```bash
# === H-7: explicit 30-day journald retention — ONE block, run as-is ===

# 1) precheck — confirm no existing drop-in would be clobbered, capture
#    the "before" merged config for comparison
sudo test -f /etc/systemd/journald.conf.d/99-juval-retention.conf \
  && echo "STOP: file already exists, inspect before overwriting" \
  || echo "OK: no existing drop-in, safe to create"
sudo systemd-analyze cat-config systemd/journald.conf

# 2) create the explicit retention drop-in
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nMaxRetentionSec=30day\n' \
  | sudo tee /etc/systemd/journald.conf.d/99-juval-retention.conf

# 3) validate: journald has no "-t" syntax check like sshd; the real
#    equivalent is systemd-analyze cat-config, which shows the merged
#    config and which file/line is effective for each directive
sudo systemd-analyze cat-config systemd/journald.conf | grep -B2 -A1 MaxRetentionSec

# 4) apply — journald has no reload verb for config changes; restart is
#    the documented way, and it does not lose persisted logs on disk
sudo systemctl restart systemd-journald
sudo systemctl is-active systemd-journald

# 5) prove the effective configuration (post-change)
sudo systemd-analyze cat-config systemd/journald.conf | grep -E "MaxRetentionSec|99-juval-retention"
journalctl --disk-usage
```

**Not run this session.** Once the user runs this and reports the output
of step 5, H-7 can be upgraded to `VERIFIED` — note that no log entries
on this host are anywhere near 30 days old yet, so *actual pruning*
cannot be demonstrated today; "effective configuration" here means the
merged config shows `MaxRetentionSec=30day` as the active value from
`99-juval-retention.conf`, which is what `systemd-analyze cat-config`
proves.

### 7.3 H-9 — decision recorded: no repository-wide `chmod`

**Decision (user, 2026-08-26)**: explicitly do **not** perform a
recursive `chmod` across the repo, `.venv/`, `node_modules/`, or any
other generated dependency tree merely to turn the control green. Reason
given: single-user host, current measured risk is low, blast radius
exceeds the security benefit.

Classified `DEFERRED / ACCEPTED_RISK` (added to the taxonomy this
session — see the States legend above) rather than force-fit into
`PARTIAL` (understates that this was a deliberate decision) or
`VERIFIED` (explicitly forbidden by the decision itself). If targeted
future hardening is ever warranted, the recommended approach is
permissions on specific sensitive paths only (e.g. `.env` if it ever
existed group-writable — it currently doesn't, per H-10) rather than a
tree-wide change.

**ADR question**: same analysis as H-3 — this is an operational
risk-acceptance about filesystem permissions on one single-user
development host, not a data-model, persistence, auth, or layer-boundary
decision. No ADR created.

### 7.4 H-16 — final reboot: user procedure (not executed by the agent)

All non-reboot host-control work is now closed or explicitly decided
(H-1, H-2, H-5, H-11, H-13 `VERIFIED`; H-3, H-9 decided and recorded;
H-7 designed and staged; H-15 re-verified and made git-reproducible).
The user approved a real controlled reboot as the final H-16
verification gate. **The agent will not execute it** — `sudo reboot`
must be run by the user. Baseline values below were captured
2026-08-26 ~15:39 UTC; **re-run the PRECHECK block immediately before
rebooting** to get a fresh baseline, since time will have passed.

**Known before rebooting**: the frontend (`vite`, PID 16589) and backend
(`uvicorn`, PID 15923) dev servers are currently running in interactive
terminal sessions (`pts/3`, `pts/4`), listening on `0.0.0.0:5173`/`:8000`
since 2026-08-24. **These are not systemd-managed and will not
auto-restart after reboot** — this is correct and expected (ADR-027: no
persistent JUVAl service on this host), not a fault to fix, but the user
will need to manually restart them post-reboot if LAN dev/testing access
is needed again. Current boot ID `d4e7004164f345c29cc33c467fae1e3b`
(booted 2026-08-24 19:54:30 UTC); no other JUVAl-critical job was found
running (no batch pipeline run, no in-progress Excel processing, no open
DB transaction — `juval-server` holds no production data or persistent
service by design).

**PRECHECK** — run immediately before rebooting, save the output:
```bash
# repo state
git -C ~/JUVAl/APP status --porcelain      # must be empty
git -C ~/JUVAl/APP rev-parse HEAD          # record this exact hash

# SSH key-only, effective config
sudo sshd -T | grep -E 'passwordauthentication|pubkeyauthentication|permitrootlogin'
# expect: passwordauthentication no / pubkeyauthentication yes / permitrootlogin without-password

# firewall / brute-force protection
sudo ufw status verbose
sudo fail2ban-client status sshd

# monitoring
systemctl --user is-active juval-host-monitor.timer
loginctl show-user juval | grep Linger     # expect Linger=yes

# capacity sanity
df -h /
free -h

# no critical active JUVAl job (dev servers are expected here, not a "job")
ps aux | grep -iE "vite|uvicorn" | grep -v grep
ss -tulnp | grep LISTEN                    # record current listeners for comparison

# identity of this boot, for comparison after
journalctl --list-boots --no-pager | tail -1
uptime
```

**REBOOT**:
```bash
sudo reboot
```
Expect the current SSH session to drop within seconds.

**RECONNECT** — from the Windows workstation, wait ~1-2 minutes, then:
```
ssh juval@192.168.0.26
```
Must connect with **no password prompt** (key-only). If it prompts for a
password, do not enter one — that would indicate H-5 did not persist
across reboot; stop and report instead.

**POSTCHECK** — run after reconnecting, compare against PRECHECK:
```bash
# new boot, confirm it actually rebooted
journalctl --list-boots --no-pager | tail -1   # boot ID must differ from PRECHECK
uptime                                          # must show a fresh uptime (minutes, not days)

# SSH key-only persisted
sudo sshd -T | grep -E 'passwordauthentication|pubkeyauthentication|permitrootlogin'
# must still read: passwordauthentication no / pubkeyauthentication yes

# password-only login still rejected (run from the Windows workstation)
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password \
    -o NumberOfPasswordPrompts=1 juval@192.168.0.26
# must fail: "Permission denied (publickey)"

# firewall / fail2ban persisted and active
sudo ufw status verbose        # active, same rules as PRECHECK
sudo fail2ban-client status sshd   # sshd jail active

# monitoring timer survived reboot without a manual re-enable
systemctl --user is-active juval-host-monitor.timer   # active
journalctl --user -u juval-host-monitor.service -n 5  # a run should land within ~35 min (OnBootSec=5min + OnUnitActiveSec=30min)

# toolchain still usable
bash -lc 'node --version'      # nvm loads via .bashrc for interactive shells
.venv/bin/python --version     # from ~/JUVAl/APP — confirms the venv survived

# repo intact and at the expected commit
git -C ~/JUVAl/APP status --porcelain   # empty
git -C ~/JUVAl/APP rev-parse HEAD       # must match the PRECHECK hash exactly

# no unexpected listeners (dev servers will be GONE — that's expected, not a fault; nothing else should be new)
ss -tulnp | grep LISTEN

# capacity still sane
df -h / ; free -h
```

**ROLLBACK/RECOVERY considerations**: if SSH does not come back on
reconnect, the hosting provider's/hypervisor's console access
(out-of-band, not SSH) is the only recovery path — this is exactly why
H-5's key-only change was validated with a second open session before
the original reload (§2), and why this reboot procedure is user-executed
end-to-end, not agent-automated. If the monitoring timer does not resume,
`loginctl show-user juval | grep Linger` should still read `yes` (H-16);
if it does not, `loginctl enable-linger juval` restores it without sudo.
If `git rev-parse HEAD` does not match, stop and report — do not run any
`git reset`/`checkout` to "fix" it.

Once POSTCHECK passes in full, H-16 can be upgraded
`READY_FOR_USER_REBOOT → VERIFIED`, and the reboot itself becomes the
closing evidence for H-1/H-2/H-5/H-15's persistence claims as well
(currently `VERIFIED` on pre-reboot evidence; a clean POSTCHECK is
confirmation, not a prerequisite for their current status).

## 9. 2026-08-26 (session 4) — real reboot executed; H-7 and H-16 verified; host hardening closed

Baseline for this pass: `ddb7a66`, clean tree. `git fetch origin` then
`git rev-list --left-right --count HEAD...origin/master` read `0 0` —
`origin/master` already carries `ddb7a66` (the prior session's commit
that could not be pushed from this host for lack of Linux-side GitHub
credentials has since reached GitHub via the established Linux →
Windows → GitHub bridge). This is reported plainly because the mission
brief anticipated origin possibly lagging for that exact reason — it did
not, this pass.

### 9.1 H-7 — journald 30-day retention applied and verified across reboot

**USER-EXECUTED, pre-reboot**: created
`/etc/systemd/journald.conf.d/99-juval-retention.conf`
(`[Journal]\nMaxRetentionSec=30day`), confirmed with
`systemd-analyze cat-config systemd/journald.conf` that it merged
correctly, `systemctl restart systemd-journald` → `active`,
`journalctl --disk-usage` → 44.2M.

**Real reboot executed (USER-EXECUTED)**, then reconnected externally via
key-only SSH from Windows.

**AGENT-EXECUTED, post-reboot, this session**: independently re-read
`/etc/systemd/journald.conf.d/99-juval-retention.conf` directly
(world-readable, content unchanged: `[Journal]` / `MaxRetentionSec=30day`);
re-ran `systemd-analyze cat-config systemd/journald.conf` (no sudo
required — this command merges and displays config, it does not need
root) and confirmed the effective value is still sourced from
`99-juval-retention.conf`; confirmed `systemctl is-active
systemd-journald` → `active`; confirmed `journalctl --disk-usage` →
60.4M. A third, independent confirmation of the same 60.4M figure came
from the host monitor's own `log.growth` check in its first post-reboot
run (§9.3) — three separately-derived reads of the same effective state
agree. This is stronger evidence than the design-time report (which was
necessarily pre-application) and closes the gap the prior session left
open. **Matrix row upgraded `READY_FOR_USER_SUDO → VERIFIED`.**

As at design time: no journal entry on this host is yet 30 days old, so
actual pruning cannot be demonstrated today. What is verified is that the
explicit policy is the effective, active configuration, and that it
survived a real reboot — not that pruning has fired.

### 9.2 Real reboot — evidence

- New boot ID `a97e9f80ac1c47ec940e46b152b48606`, confirmed AGENT-EXECUTED
  via `journalctl --list-boots`: previous boot
  (`d4e7004164f345c29cc33c467fae1e3b`) ended 2026-08-26 16:16:00 UTC, new
  boot started 16:16:12 UTC. `uptime` at first agent check showed ~2
  minutes — a genuinely fresh boot, not a stale/cached value.
- External reconnect from the Windows workstation via
  `ssh -o PasswordAuthentication=no juval@192.168.0.26` succeeded
  (USER-EXECUTED, external evidence, same evidentiary standard as H-4/H-5).
- `sudo sshd -T` reported `permitrootlogin without-password` /
  `pubkeyauthentication yes` / `passwordauthentication no`
  (USER-EXECUTED — the agent still has no sudo on this host,
  `sudo -n true` → `a password is required`, re-confirmed this session;
  `systemctl is-active ssh` → `active` is the one piece the agent could
  confirm directly). Values are unchanged from the pre-reboot baseline.
  **H-5 remains `VERIFIED`**, now with reboot persistence confirmed.

### 9.3 H-16 — final decision: VERIFIED

All acceptance criteria enumerated for this gate were checked, mixing
AGENT-EXECUTED and USER-EXECUTED evidence honestly rather than treating
either alone as sufficient:

- New boot ID and fresh uptime — **AGENT-EXECUTED** (§9.2).
- External key-only SSH reconnect succeeded — **USER-EXECUTED**.
- `PasswordAuthentication no` persisted — **USER-EXECUTED** (`sshd -T`
  needs sudo the agent doesn't have).
- UFW active, same allow-list (LAN-only `5173`/`8000`, open `22`,
  default-deny incoming) — **USER-EXECUTED** (`ufw status` also needs
  sudo; agent re-confirmed it still cannot run it: `ERROR: You need to
  be root to run this script`).
- fail2ban active, `sshd` jail live, 0/0/0/0 — **USER-EXECUTED**
  (`fail2ban-client status` also needs sudo; agent re-confirmed:
  `Permission denied to socket`).
- journald 30-day policy persisted, effective config confirmed —
  **AGENT-EXECUTED** (§9.1).
- `juval-host-monitor.timer` survived reboot without a manual
  re-enable — **AGENT-EXECUTED**: `systemctl --user is-enabled` →
  `enabled`, `is-active` → `active (waiting)` since 16:16:21 UTC, next
  trigger 16:21:09 UTC, all read directly, no sudo needed (user-level
  systemd instance kept alive by linger).
- `loginctl show-user juval -p Linger` → `Linger=yes` — **AGENT-EXECUTED**.
- The monitor's first unattended post-reboot run actually fired and
  passed — **AGENT-EXECUTED, captured live**: the agent set up a
  bounded background watch on
  `journalctl --user -u juval-host-monitor.service` before the
  scheduled 16:21:09 UTC trigger and captured the real run at
  16:21:41 UTC:

  ```
  [PASS] disk./                 11% used
  [PASS] memory                 93% available
  [PASS] load                   1-min load 0.21 / 4 cores = 0.05x
  [PASS] temperature             46C
  [PASS] systemd.failed          0 failed units (system + user)
  [PASS] git.backup              working tree clean, in sync with upstream (behind: 0)
  [PASS] log.growth              journal disk usage: 60.4M
  RESULT: ALL CHECKS PASS
  ```

  This is a real, unattended, unscripted-by-the-agent execution — not a
  fabrication and not user-reported. It also independently corroborates
  the repository state (§9.4) and the journald figure (§9.1) from a
  third source.
- Node/npm and Python/venv usable post-reboot — **AGENT-EXECUTED**:
  `node --version` → `v24.19.0`, `npm --version` → `11.17.0`,
  `python3 --version` → `Python 3.12.3`, `.venv/bin/python --version` →
  `Python 3.12.3` — all unchanged from pre-reboot.
- Repository intact at the expected commit — **AGENT-EXECUTED**:
  `git status --short` empty, `git rev-parse --short HEAD` → `ddb7a66`,
  matching the pre-reboot hash exactly (§9.4).
- Expected absence of dev-server listeners — **AGENT-EXECUTED**:
  `ss -lntp` shows only `0.0.0.0:22` / `[::]:22`; no `:5173`/`:8000`
  listener. This is the expected outcome per ADR-027 (no persistent
  JUVAl service on this host) — **not** treated as a failure.
- Host resources healthy — **AGENT-EXECUTED**: `df -h /` → 98G volume,
  10G used, 83G available, 11% used; `free -h` → 13Gi total, ~838Mi
  used, ~12Gi available, swap unused.

Every enumerated acceptance criterion is satisfied by real evidence.
**Matrix row upgraded `READY_FOR_USER_REBOOT → VERIFIED`.** The one
honest limitation, unchanged from every earlier session, is that the
three sudo-gated checks (UFW, fail2ban, `sshd -T`) remain user-reported
rather than agent-re-executed — the agent has never had sudo on this
host at any point in this project, and that has not changed this
session.

### 9.4 Repository state, this session

`git status --short` was empty and `git rev-parse --short HEAD` read
`ddb7a66` both before and after the reboot-evidence review in this
session — no functional or product code was touched, only this
documentation file. `git fetch origin` plus `git rev-list --left-right
--count HEAD...origin/master` → `0 0`: this repository is not behind
origin, and is not blocked on the Linux-credential caveat the mission
brief anticipated.

### 9.5 Not touched this session, by mission constraint

FusionAuth, enrichment, AI Analyst, product code, tests were not
started or modified — this was a documentation/evidence-closure pass
only. H-3 and H-9 were **not** reinterpreted: H-3 remains `PARTIAL —
ACCEPTED DEVELOPMENT-LAN RISK / COMPENSATING CONTROL`, H-9 remains
`DEFERRED / ACCEPTED_RISK`, per explicit instruction. No repository-wide
`chmod` was performed. No persistent frontend/backend systemd services
were created — the absence of `:5173`/`:8000` listeners is expected,
not a gap to close.

### 9.6 Architectural closure

With H-7 and H-16 both verified against real post-reboot evidence, and
no new material blocker discovered, the host-hardening phase for
`juval-server` is declared **`HOST_HARDENING_COMPLETE`**. This closes a
phase of work, not the project: FusionAuth deployment, AI Analyst,
enrichment, and production deployment (Railway/Vercel/Supabase
verification) remain separate, future workstreams, entirely unaffected
by this closure and not started here.

## 10. Related

[`ADR-027`](../adr/ADR-027-juval-server-role.md) (host role, security/
network/data boundaries, backup/recovery/observability expectations),
[`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) (RF-02, workstation + cloud),
[`ACCESS_CONTROL.md`](ACCESS_CONTROL.md) (RF-04),
[`SP_API_REGISTRATION_REMEDIATION.md`](SP_API_REGISTRATION_REMEDIATION.md) §20,
`docs/DEVELOPMENT_ENVIRONMENT.md` §4, `tools/host_monitor.sh` (H-15),
`tools/systemd/` (git-tracked copies of the `juval-host-monitor` timer/
service units, added 2026-08-26).
