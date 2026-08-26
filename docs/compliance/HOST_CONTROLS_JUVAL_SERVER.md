# Host controls — `juval-server` (192.168.0.26)

Measured evidence for the Linux node that holds a working copy of the JUVAl
repository. Every row was produced by running the stated command on
2026-08-24, not by reading configuration intent. H-1, H-2, H-3 and H-13
were re-measured on 2026-08-26 — see §5. H-5 and H-11 were closed, and
H-3/H-7/H-9 were reinvestigated, later the same day — see §6.

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
| H-1 | Host firewall enabled | RF-02 | UFW | `systemctl is-active ufw`; `/etc/default/ufw`, `/etc/ufw/ufw.conf` (world-readable); `sudo ufw status verbose` | `active`; default policy read directly 2026-08-24: `DEFAULT_INPUT_POLICY="DROP"`, `DEFAULT_OUTPUT_POLICY="ACCEPT"`, `DEFAULT_FORWARD_POLICY="DROP"`, `IPV6=yes`; **rule allow-list reported by the user 2026-08-26 (`sudo ufw status verbose`)**: logging low, default deny incoming, default allow outgoing, routed disabled, `22/tcp` (OpenSSH) allowed, `5173/tcp` allowed **only from `192.168.0.0/24`**, `8000/tcp` allowed **only from `192.168.0.0/24`**, OpenSSH IPv6 allowed | None — allow-list now enumerated, closing the prior sudo gap. The agent independently re-confirmed 2026-08-26 it still has no sudo (`sudo -n true` → `a password is required`), so this row's evidence is user-reported, not agent-executed | User (ran the sudo command and reported output) | **VERIFIED** (2026-08-26 — upgraded from `PARTIAL`; allow-list matches the intended LAN-only exposure for 5173/8000, see H-3) |
| H-2 | Brute-force protection | RF-02 | fail2ban | `systemctl is-active fail2ban`; `/etc/fail2ban/jail.conf`, `/etc/fail2ban/jail.d/*.conf` (world-readable); `sudo fail2ban-client status sshd` | `active`; effective `sshd` jail policy read directly 2026-08-24: `bantime=10m`, `findtime=10m`, `maxretry=5`; **live state reported by the user 2026-08-26 (`sudo fail2ban-client status sshd`)**: jail active, currently failed 0, total failed 0, currently banned 0, total banned 0, journal filter active | None — live ban state now confirmed, closing the prior sudo gap. Agent-side sudo access independently re-checked 2026-08-26 (still unavailable), so this row's evidence is user-reported | User (ran the sudo command and reported output) | **VERIFIED** (2026-08-26 — upgraded from `PARTIAL`; jail is live and the host has no ongoing brute-force activity) |
| H-3 | Network exposure minimised | RF-02 | Default install | `ss -tulnp \| grep LISTEN` | **Re-measured 2026-08-24 22:34**: `:22` (SSH, all interfaces) and DNS `:53` (loopback only) as before, **plus `:5173` (Vite dev server) and `:8000` (FastAPI/uvicorn) bound to `0.0.0.0`** — two user-started foreground processes, LAN-exposed rather than localhost-only. **2026-08-26**: same two processes still listening on `0.0.0.0:5173`/`0.0.0.0:8000` (`ps -o lstart` confirms unchanged since 2026-08-24 22:31/22:32) — the *application* bind is still all-interfaces and unauthenticated at the app layer. What is new is the perimeter control: H-1's user-reported UFW rule enumeration confirms `5173/tcp` and `8000/tcp` are allowed **only from `192.168.0.0/24`**, so reachability is firewall-constrained to the LAN subnet, not open to the internet | The app itself still binds `0.0.0.0` with no application-layer auth (`JUVAL_AUTH_MODE=disabled`) — UFW is a compensating control, not a substitute for binding to `127.0.0.1` when LAN access isn't actually needed. **This is a product/workflow decision, not a technical blocker**: closing it means choosing between (a) rebind both dev servers to `127.0.0.1`, losing the ability to reach them from another LAN device (e.g. a phone, a second workstation) for manual testing, or (b) keep `0.0.0.0` and accept UFW's LAN-only allow-list as the compensating control, which is already measured and holding (H-1). The agent is not choosing this silently — flagged `PENDING DECISION` per CLAUDE.md §3, not touched this session | User (decision required) | **PARTIAL** (app-level exposure unchanged; the LAN-only firewall constraint is now directly confirmed rather than inferred — see H-1; closure requires a product decision, see Gate 3 note below) |
| H-4 | SSH key authentication works | RF-04 | `~/.ssh/authorized_keys` | `ssh -o BatchMode=yes juval@…` | Historical verification (2026-08-24, from the Windows workstation): non-interactive key auth succeeds. **Could not be re-tested from `juval-server` itself this session** — this host holds only the public key in `authorized_keys` (`stat`: `600 juval:juval`), no private key material, by design (a server does not need to SSH into itself) | Re-verification must happen from the client side, as it did originally — do not treat the absence of a private key on this host as a finding | Agent | **VERIFIED** (2026-08-24, workstation-side; not independently re-testable from this host) |
| H-5 | SSH password authentication disabled | RF-04 | `/etc/ssh/sshd_config.d/50-cloud-init.conf` (`PasswordAuthentication no`) | `sudo sshd -T \| grep -E 'passwordauthentication\|pubkeyauthentication\|permitrootlogin'`; external client test forcing each auth method in turn | **USER-EXECUTED, 2026-08-26**: user edited the cloud-init drop-in (backing up the original first, see §2), `sudo sshd -t` passed, `sudo sshd -T` shows `permitrootlogin without-password`, `pubkeyauthentication yes`, `passwordauthentication no`; `sudo systemctl reload ssh` → `is-active` = `active`. **External Windows client tests (USER-EXECUTED)**: (1) `ssh -o PasswordAuthentication=no juval@192.168.0.26` → succeeded, normal shell — key-only auth works; (2) `ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 juval@192.168.0.26` → `Permission denied (publickey)` — password-only auth is rejected by the server. Test (2) is the direct external proof of the H-5 requirement, mirroring how H-4 was verified client-side. **AGENT-EXECUTED, same session**: confirmed via `sshd`'s actual `Include /etc/ssh/sshd_config.d/*.conf` glob semantics (read from `/etc/ssh/sshd_config` and tested against real glob/`fnmatch` behavior) that the backup file `50-cloud-init.conf.backup-20260826` does **not** match `*.conf` and is therefore never read by `sshd` — see §2 | None. The evidence chain (local sudo config check + reload + two independent external auth-method tests) is sufficient and self-consistent | User (change + validation + external tests), Agent (backup-file glob safety check) | **VERIFIED** (2026-08-26 — upgraded from `NOT_IMPLEMENTED`; USER-EXECUTED evidence, agent-verified backup-file safety) |
| H-6 | OS security patches current | RF-02 (F-01) | `unattended-upgrades` | `apt list --upgradable`; `systemctl is-enabled unattended-upgrades` | 1 upgradable package, **0 security**; unattended-upgrades `enabled`; apt metadata refreshed 2026-08-24 21:22; no `/var/run/reboot-required`; kernel 6.8.0-138 | None currently | Agent | **VERIFIED** |
| H-7 | Persistent audit logging | RF-05 | systemd-journald + rsyslog | `ls -d /var/log/journal`; `ls -l /var/log/auth.log`; `cat /etc/logrotate.d/rsyslog`; `cat /etc/systemd/journald.conf` | **Re-checked 2026-08-26**: `/var/log/journal` present (persistent, survives reboot), 44.2M current usage; `auth.log` present, mode `0640 syslog:adm`, 242 KB. `/etc/logrotate.d/rsyslog` (world-readable) shows `auth.log` **is** on an explicit bounded retention: `rotate 4` + `weekly` + `compress` ≈ 4 weeks of syslog/auth history. `/etc/systemd/journald.conf` has `SystemMaxUse`/`MaxRetentionSec`/`MaxFileSec` all commented out — journald retention relies on upstream defaults (auto-vacuum, not an explicit pinned policy) rather than a value chosen and recorded for this host | auth.log retention is real and bounded (~4 weeks); journald retention is still implicit/default rather than explicit — closing this needs (a) a retention-period decision (how many days of journal audit history this host must keep) and (b) `sudo` to write `/etc/systemd/journald.conf.d/`. Not closed this session — see Gate 3 note below | Agent | **PARTIAL** (evidence improved 2026-08-26; auth.log retention confirmed bounded, journald explicit retention still open — decision + sudo required) |
| H-8 | Log rotation | RF-05 | logrotate.timer | `systemctl is-enabled logrotate.timer` | `enabled` | None | Agent | **VERIFIED** |
| H-9 | Repository file permissions | RF-04 | Filesystem | `stat -c "%A %U:%G"`; `umask`; `git config core.sharedRepository` | **Re-checked 2026-08-26**: `/home/juval` is `drwxr-x---` (no world access); `~/JUVAl` and `~/JUVAl/APP` are `drwxrwxr-x juval:juval` (group-writable); default `umask 0002` explains the group-write bit — it is not a one-off misconfiguration, every new file/dir inherits it; `core.sharedRepository` unset (git's own default, not a shared-repo setup) | Repo dirs are group-writable. Real-world risk is low (single-user host, `juval`'s own primary group, no second local account exists to abuse group access), but "closing" this by recursively `chmod`-ing the whole working tree (which includes `.venv/` and `node_modules/`, tens of thousands of files, some possibly open in an active dev session) is a broad, blast-radius action for a theoretical risk on a single-user host — not something to run silently. Left to the user to decide: accept as documented low-severity residual risk, or explicitly request the recursive `chmod`/`umask` change | Agent | **PARTIAL** (unchanged; root cause identified as `umask 0002`, closure deliberately not auto-applied — see Gate 3 note below) |
| H-10 | Secrets absent from the working copy | RF-02 | `.gitignore` + scanner | `python tools/compliance_check.py` | `secret_scan`: no secret-shaped strings in 312 files; `.env` and `frontend/.env.local` present but git-ignored and never staged | None | Agent | **VERIFIED** |
| H-11 | Capacity headroom | Ops | `tools/host_monitor.sh` (H-15) | `df -h /`; `free -h`; read `tools/host_monitor.sh` disk/memory threshold logic; `journalctl --user -u juval-host-monitor.service` | **Re-checked 2026-08-26**: 98 G volume, 11% used (83 G free); 13 GiB RAM, 4 GiB swap, 11 GiB available. `tools/host_monitor.sh` (verified by reading the script, lines 20-38) has real coded thresholds, not just informational output: disk WARN at ≥80%, FAIL at ≥90%; memory WARN at <10% available, FAIL at <5% available. This runs automatically every ~30 min via the H-15 timer (confirmed live in Gate 4: consecutive journal entries 12:49/13:20/13:51/14:22/14:53/15:23 UTC, all with real PASS/WARN results) | None for disk/RAM — thresholds exist, are coded (not just displayed), and run unattended on a verified cadence. The `log.growth` check in the same script is informational-only (no threshold, always PASS) — that gap belongs to H-7's retention question, not to this capacity control | Agent | **VERIFIED** (2026-08-26 — upgraded from `PARTIAL`; the "no alerting on thresholds" gap was already closed by H-15's `host_monitor.sh`, just not previously cross-referenced here) |
| H-12 | Backup and restore of source code | Ops / RF-05 | GitHub (`origin`) | fresh `git clone` + `diff -r` against the working tree | **Restore-tested 2026-08-24**: cloned `origin/master` into a scratch directory; `diff -r` against the working tree showed zero differences beyond this session's own not-yet-committed edits and known git-ignored artifacts (`.env.local`, `frontend/dist`, `juval_runs.db`, `*.egg-info`) | None for source code specifically. **Secrets and local-only config remain `NOT_IMPLEMENTED` by design** — no destination exists that is both off-host and as secure as this host, and copying a secret to an insecure destination is explicitly worse than no backup (ADR-027 §"Expectativas de backup") | Agent | **VERIFIED** (source code only) |
| H-13 | Browser E2E dependencies | Gate 8 | Playwright | `ldd chrome-headless-shell \| grep "not found"`; `E2E_BASE_URL=... npx playwright test` | **Resolved 2026-08-26**: `/var/log/apt/history.log` shows `Start-Date: 2026-08-26 13:12:37`, `Commandline: apt-get install -y --no-install-recommends libasound2t64 libatk-bridge2.0-0t64 libatk1.0-0t64 libatspi2.0-0t64 ... xvfb ...`, `Requested-By: juval (1000)` (sudo, with the user-scoped nvm `npx` exposed on `PATH`); all 9 previously-missing libraries confirmed present by direct `find` (`libatk-1.0.so.0`, `libatk-bridge-2.0.so.0`, `libXcomposite.so.1`, `libXdamage.so.1`, `libXfixes.so.3`, `libXrandr.so.2`, `libgbm.so.1`, `libasound.so.2`, `libatspi.so.0` all under `/usr/lib/x86_64-linux-gnu/`); `ldd` on both `chrome-headless-shell` and `chrome` (`~/.cache/ms-playwright/chromium{,_headless_shell}-1234/...`) shows **zero** `not found` lines, both binaries answer `--version` (`Google Chrome for Testing 151.0.7922.34`); **full E2E suite executed for real** on isolated ports (backend `127.0.0.1:8001`, fresh SQLite db; frontend `vite build` + `npm run preview --host 127.0.0.1 --port 5180`, avoiding the pre-existing LAN-bound 5173/8000 dev servers) — **27/27 passing**, same count as the historical Windows baseline | None | Agent (deps install by User via sudo; E2E execution and verification by Agent) | **VERIFIED** (2026-08-26 — upgraded from `BLOCKED_EXTERNAL`; the Linux E2E blocker is closed) |
| H-14 | Production service hardening | ADR-018 | — | — | Host runs no JUVAl service by design | — | — | **NOT_APPLICABLE** |
| H-15 | Host monitoring (disk/RAM/load/temp/failed units/log growth/backup status) | Ops, Gate 6 | `tools/host_monitor.sh` + `systemd --user` timer | `systemctl --user status juval-host-monitor.timer`; `journalctl --user -u juval-host-monitor.service` | **Implemented and verified 2026-08-24**; **re-verified live 2026-08-26**: `systemctl --user show` reports `ActiveState=active`, `Result=success`, `LastTriggerUSec` = 2026-08-26 15:23:39 UTC; six consecutive real runs inspected in the journal (12:49→15:23 UTC, ~30 min apart), all `PASS`/`PASS WITH WARNINGS` with correct per-check reasoning (e.g. flagged 1 unpushed commit mid-session, cleared once pushed). Disk/memory checks are real coded thresholds (80/90%, 10/5%) — see H-11. **2026-08-26**: the two systemd unit files (`juval-host-monitor.timer`/`.service`) were copied byte-for-byte from `~/.config/systemd/user/` into `tools/systemd/` (git-tracked, `diff` confirmed identical) with an install `README.md` — closing the prior "not reproducible from Git" gap; the live host's copy in `~/.config/systemd/user/` was not modified | Only this host's own state; no alert delivery channel configured (no email/webhook) — a human must check `journalctl --user` or the timer status, there is no push notification. `log.growth` check is informational only (no threshold) | Agent | **VERIFIED** (re-confirmed 2026-08-26; unit files now git-tracked under `tools/systemd/`) |
| H-16 | Reboot persistence for user-level automation | Ops, Gate 7 | `loginctl enable-linger juval` | `loginctl show-user juval \| grep Linger` | **Enabled 2026-08-24 without sudo** (`Linger=yes`) — this is the standard systemd mechanism that starts `user@1000.service` at boot without an interactive login, so `systemd --user` timers (H-15) survive a reboot | Not reboot-tested — this host has active interactive sessions this audit deliberately did not disrupt (STOP conditions: real risk of losing work). Linger is a well-documented systemd behavior, but "the mechanism is enabled" is reported here, not "reboot was tested and the timer fired" | Agent | **IMPLEMENTED_NOT_VERIFIED** (mechanism enabled; reboot itself not exercised) |

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

## 7. Reboot readiness — user action procedure (not executed)

Not performed this session (mission brief: "DO NOT reboot automatically").
Warranted to close H-16 (`IMPLEMENTED_NOT_VERIFIED` → `VERIFIED`) and to
confirm SSH/UFW/fail2ban/monitoring persistence end-to-end rather than by
mechanism inspection alone. Exact procedure if/when the user chooses to
run it:

**PRECHECK** (run and note output before rebooting):
```bash
systemctl is-active ssh ufw fail2ban
systemctl --user is-active juval-host-monitor.timer
loginctl show-user juval | grep Linger
git -C ~/JUVAl/APP status --porcelain   # must be empty — do not reboot with uncommitted work
git -C ~/JUVAl/APP rev-parse HEAD
```

**REBOOT**: `sudo reboot`. Expect the SSH session to drop.

**RECONNECT** (from the Windows workstation, after ~1-2 min):
```
ssh juval@192.168.0.26      # must succeed key-only, no password prompt
```

**POSTCHECK** (same commands as PRECHECK, plus):
```bash
systemctl is-active ssh ufw fail2ban          # all must be 'active' with no manual start
systemctl --user is-active juval-host-monitor.timer   # must be 'active' without re-enabling
journalctl --user -u juval-host-monitor.service -n 5  # a run should appear within ~35 min (OnBootSec=5min + OnUnitActiveSec=30min)
git -C ~/JUVAl/APP rev-parse HEAD             # must match the PRECHECK hash — repo integrity
node --version   # after `source ~/.nvm/nvm.sh` or a fresh interactive shell — nvm loads via .bashrc, not automation
.venv/bin/python --version   # from ~/JUVAl/APP
```

**ROLLBACK/RECOVERY considerations**: if SSH does not come back, the
hosting provider's/hypervisor's console access (out-of-band, not SSH) is
the only recovery path — this is exactly why H-5's key-only change was
validated with a second open session before reload, and why this
procedure is user-executed, not agent-automated. If the monitoring timer
does not resume, `loginctl show-user juval | grep Linger` should still say
`yes` (H-16); if not, `loginctl enable-linger juval` restores it, no sudo
required.

## 8. Related

[`ADR-027`](../adr/ADR-027-juval-server-role.md) (host role, security/
network/data boundaries, backup/recovery/observability expectations),
[`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) (RF-02, workstation + cloud),
[`ACCESS_CONTROL.md`](ACCESS_CONTROL.md) (RF-04),
[`SP_API_REGISTRATION_REMEDIATION.md`](SP_API_REGISTRATION_REMEDIATION.md) §20,
`docs/DEVELOPMENT_ENVIRONMENT.md` §4, `tools/host_monitor.sh` (H-15),
`tools/systemd/` (git-tracked copies of the `juval-host-monitor` timer/
service units, added 2026-08-26).
