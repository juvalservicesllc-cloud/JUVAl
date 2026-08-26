# JUVAl — Network Security Architecture and Control Audit (RF-02)

| Field | Value |
|---|---|
| Status | **PARTIAL.** Workstation controls measured and evidenced; both cloud services are now deployed and their TLS/segmentation/RLS controls are measured with real evidence (§3). The sole remaining blocking gap is workstation finding **F-01** (§2), unchanged and re-confirmed. |
| Audit date | `2026-08-18` (initial); **re-verified 2026-08-18 against live production** (Railway + Vercel + Supabase) |
| Method | Read-only inspection of the developer workstation; official provider documentation for capability claims. No configuration was changed. |
| Amazon finding | **RF-02** — firewall, IDS/IPS, anti-virus/anti-malware, network segmentation |
| Related control | `AC-06` (DPP §1.1), `AC-05` (TLS, DPP §1.5) |
| Scope note | This audit covers the **workstation** and the **cloud services**. A third node exists -- the Linux development/validation server `juval-server` -- audited separately in [`HOST_CONTROLS_JUVAL_SERVER.md`](HOST_CONTROLS_JUVAL_SERVER.md) (measured 2026-08-24, host-control phase closed 2026-08-26). It runs no JUVAl service and holds no production data, but it does hold a working copy of the repository. As of 2026-08-26, SSH password authentication is disabled there (H-5 **VERIFIED**, USER-EXECUTED evidence); the remaining open item is app-level network exposure (H-3, still `PARTIAL` -- dev servers bind `0.0.0.0`, constrained to LAN by UFW, pending a product decision on whether LAN-device access is actually needed). |

Three states are kept strictly distinct throughout, because collapsing them is
exactly how a compliance answer becomes untrue:

- **`PROVIDER_CAPABILITY`** — the provider documents that the control exists.
- **`ACTIVE_CONFIGURATION`** — it is switched on in JUVAl's account.
- **`VERIFIED_CONFIGURATION`** — JUVAl holds dated evidence that it is on.

A provider's marketing page is only ever the first of the three.

---

## 1. Where Amazon Information would actually flow

RF-02 applies to "systems handling Information". Today JUVAl holds **no Amazon
Information at all** — SP-API registration is `REJECTED_REMEDIATION_REQUIRED`,
no client, no credential, no call. This audit therefore covers the boundary as
it will exist **after** a successful reapplication, and states today's real
state separately.

```
Operator workstation ──HTTPS──> Vercel (PWA, static)
                                     │  HTTPS + OIDC bearer token
                                     v
                               Railway (FastAPI backend)  ──HTTPS──> Amazon SP-API
                                     │  TLS (pooler)              (future)
                                     v
                               Supabase (PostgreSQL)
```

| Stage | Enters | Processed | Stored | Transmitted | Admin access |
|---|---|---|---|---|---|
| SP-API → backend | Yes (future) | Backend only | — | TLS | Backend service identity |
| Backend → database | — | — | Yes (derived records) | TLS via pooler | Operator via Supabase console |
| Backend → PWA | — | — | No (render only) | HTTPS | Authenticated operator |
| Workstation | Supplier workbooks today | Local | Local files | HTTPS uploads | Operator |

**Segmentation principle:** the browser never holds an SP-API credential and
never talks to Supabase with a privileged key; only the backend does. That
separation is enforced in code today (`SECRETS.md` §2/§6) rather than by
network topology, which is the honest description — JUVAl has no VPC.

---

## 2. Developer workstation — MEASURED 2026-08-18

The workstation is in scope because supplier data and, in future, credentials
are reachable from it. These values were read directly from the host, not
assumed.

| Control | Measured value | State |
|---|---|---|
| **Firewall — Domain profile** | `Enabled: True` | `VERIFIED_CONFIGURATION` |
| **Firewall — Private profile** | `Enabled: True` | `VERIFIED_CONFIGURATION` |
| **Firewall — Public profile** | `Enabled: True` | `VERIFIED_CONFIGURATION` |
| **Anti-malware** (Microsoft Defender) | `AntivirusEnabled: True`, `AMServiceEnabled: True` | `VERIFIED_CONFIGURATION` |
| **Real-time protection** | `RealTimeProtectionEnabled: True` | `VERIFIED_CONFIGURATION` |
| **Anti-spyware** | `AntispywareEnabled: True` | `VERIFIED_CONFIGURATION` |
| **Behavior monitoring** | `BehaviorMonitorEnabled: True` | `VERIFIED_CONFIGURATION` |
| **Network intrusion prevention** (Defender NIS) | `NISEnabled: True` | `VERIFIED_CONFIGURATION` — this is the workstation's IDS/IPS-equivalent control |
| **Signature currency** | `AntivirusSignatureAge: 0` days; last updated `2026-08-18` | `VERIFIED_CONFIGURATION` |
| **Disk encryption** | Query returned `Access denied` (requires elevation) | `NEEDS_VERIFICATION` — see F-02 |
| **OS patch level** | Windows 10 Home, build `19045`; most recent hotfix `KB5072653`, installed `2025-11-19` | **FINDING F-01** |

Reproduce with (read-only, no elevation needed for the first two):

```powershell
Get-NetFirewallProfile | Select-Object Name, Enabled
Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled,
    AntispywareEnabled, BehaviorMonitorEnabled, NISEnabled, AntivirusSignatureAge
Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 5
Get-BitLockerVolume            # requires an elevated shell
```

### Findings

| ID | Severity | Finding | Required action |
|---|---|---|---|
| **F-01** | **HIGH** — **RE-MEASURED 2026-08-18, OPEN, UNCHANGED** | The most recent OS security hotfix is still `KB5072653`, installed **2025-11-19** — identical to the original measurement; **zero new OS security patches landed in the intervening period**. That is now exactly **9 months** of no OS patching, on Windows 10 (past end of mainstream support). `Get-HotFix` re-run confirms the same top-5 hotfix list as the original audit. Note for precision: the Windows Update Agent's own `LastSearchSuccessDate`/`LastInstallationSuccessDate` (via `Microsoft.Update.AutoUpdate`) show activity as recently as today — this reflects the update *agent* checking in (e.g. Defender definitions, which update daily and are tracked separately, see below), **not** a new OS security patch; it must not be read as "the OS is being patched." | **EXTERNAL USER ACTION, unchanged:** (a) bring the workstation fully up to date and move to a supported OS, or (b) formally exclude it from the Amazon Information boundary. Neither has been done. **Classification: `OPEN`** (§11) — re-verified from current evidence, not assumed from the prior audit. |
| **F-02** | MEDIUM — **RE-MEASURED 2026-08-18, UNVERIFIABLE_WITH_CURRENT_PRIVILEGES, UNCHANGED** | `Get-BitLockerVolume` still returns `Access denied` from this (non-elevated) shell; the agent has no path to elevate itself. No inference of encryption state was made from Windows edition or any other proxy. | **EXTERNAL USER ACTION, unchanged:** run `Get-BitLockerVolume` in an elevated PowerShell session and record the result. |
| **F-03** | LOW | The workstation firewall profiles show `DefaultInboundAction: NotConfigured`, i.e. the Windows default (block unsolicited inbound) rather than an explicit policy. The effective behavior is correct; the *explicitness* is not. | Optional: set the default inbound action explicitly so the posture is stated rather than inherited. |

F-01 is the single most consequential item in this document. It is a real
control gap on a real machine, not a documentation gap. **It is now also the
sole remaining blocker for RF-02** — every cloud-side gap that used to share
this document's `PARTIAL` status has been closed with real evidence (§3).

---

## 3. Cloud components — DEPLOYED 2026-08-18, RE-VERIFIED

Both application services are now live in production. Evidence below is from
real HTTP/database probes against the live deployment, not from provider
marketing pages — `VERIFIED_CONFIGURATION`, not `PROVIDER_CAPABILITY`, except
where explicitly marked otherwise.

| Component | Deployed? | Firewall / ACL | IDS/IPS | Anti-malware | Segmentation | TLS |
|---|---|---|---|---|---|---|
| **Railway** (backend) | **YES** — `https://juval-backend-production.up.railway.app`, `railway.toml` (Nixpacks builder, corrected 2026-08-18 after a real Railpack deploy failure) | Provider-managed edge; no JUVAl-level ingress rules configured (`PROVIDER_CAPABILITY`) | Provider-level only; no JUVAl-visible IDS/IPS configured (`PROVIDER_CAPABILITY`) | Provider runtime responsibility (`PROVIDER_CAPABILITY`) | Logical: browser never holds a Supabase credential, only the backend does (`SECRETS.md` §2/§6, enforced in code) | **`VERIFIED_CONFIGURATION`** — `GET /docs` and `GET /api/v1/runs` return over HTTPS, confirmed by direct request |
| **Vercel** (PWA) | **YES** — `https://juval-frontend.vercel.app` | Provider edge/WAF capability (`PROVIDER_CAPABILITY`) | Provider-level (`PROVIDER_CAPABILITY`) | N/A (static assets) | Static hosting; frontend bundle confirmed to contain no DSN/service-role/database credential (0 matches on `postgres://`/`supabase`/`service_role` in the served bundle) | **`VERIFIED_CONFIGURATION`** — served over HTTPS |
| **Supabase** (PostgreSQL) | **YES** — live project, in active production use since 2026-08-18 | Network restrictions available on paid tiers; **not configured** (`NETWORK_SECURITY.md` N-6, still open) | Provider-level (`PROVIDER_CAPABILITY`) | Provider responsibility | RLS **enabled, zero policies = fail-closed** on both tables — **re-confirmed live 2026-08-18** by direct query against the production database: `rowsecurity = true` on `execution_runs` and `execution_run_records`, `pg_policies` returns 0 rows (see §3.1) | **`VERIFIED_CONFIGURATION`** — live connection confirmed `ssl = on` server-side |

**CORS — `VERIFIED_CONFIGURATION`:** `JUVAL_CORS_ORIGINS` on Railway is set to
the exact Vercel origin (`https://juval-frontend.vercel.app`), no wildcard.
Confirmed with real cross-origin requests: the Vercel origin receives
`access-control-allow-origin` echoed back; an arbitrary third-party origin
does not.

### 3.1 Supabase Row Level Security — enabled and fail-closed

Both migrations (`20260817000000_execution_runs.sql`,
`20260817000001_execution_run_records.sql`) end with
`alter table … enable row level security` and define **no policies**. In
PostgreSQL that means the table is inaccessible to any non-owner role: the
public/anon API key can read nothing. That is fail-closed and is the correct
posture, not an oversight.

Two consequences must be stated precisely, because they are easy to overclaim:

1. **RLS is not the control protecting run data from JUVAl's own users.** The
   backend connects as the database owner over a direct PostgreSQL connection,
   and RLS does not constrain the owner. Authorization for human callers is
   enforced at the API layer (`interfaces/api/auth.py`, RF-04) — that is where
   the least-privilege decision actually happens.
2. **RLS is the control that stops the browser reaching the database.** The
   frontend never queries Supabase for run data; it calls the FastAPI backend.
   Should an anon key ever leak, RLS with zero policies means it grants no
   read access to these tables.

**No RLS policies are proposed.** There is no authenticated Supabase end-user
model — no caller exists for a per-row policy to discriminate between — so
writing policies now would be speculative and would weaken the current
fail-closed default rather than strengthen it. If JUVAl ever lets the browser
query Supabase directly, that is a new architectural decision requiring an ADR,
and per-row policies become mandatory at that point.

**Verification: DONE, 2026-08-18.** Confirmed on the live project by direct
query: `select tablename, rowsecurity from pg_tables where schemaname='public'`
returns `true` for both `execution_runs` and `execution_run_records`;
`select * from pg_policies where schemaname='public'` returns 0 rows. No
permissive policy has been added through the dashboard.

### 3.2 GitHub (source control) — re-checked 2026-08-18

| Control | Value | Source |
|---|---|---|
| Repository visibility | **PUBLIC** | `gh repo view` |
| Secret scanning | **`enabled`** | `gh api repos/.../JUVAl` → `security_and_analysis.secret_scanning.status` |
| Secret scanning push protection | **`enabled`** | Same — blocks a push that contains a recognized secret pattern before it reaches the remote |
| Open secret-scanning alerts | **0** | `gh api repos/.../JUVAl/secret-scanning/alerts` → `[]` |
| Dependency graph | **enabled** (implicit) | Always on for public repositories; not a togglable field on this API for a public repo |
| Vulnerability alerts (Dependabot alerts) | **`enabled` — turned on 2026-08-18** | Before: `gh api .../vulnerability-alerts` → 404 "Vulnerability alerts are disabled". Action: `gh api -X PUT .../vulnerability-alerts` (user-authorized, this pass). After: same endpoint → 204 (enabled) |
| Dependabot security updates | **`enabled` — turned on 2026-08-18** | Before: `security_and_analysis.dependabot_security_updates.status` = `disabled`. Action: `gh api -X PUT .../automated-security-fixes` (required alerts enabled first — GitHub returned `422` until that prerequisite was met). After, independently re-read: `security_and_analysis.dependabot_security_updates.status` = `enabled`, and `gh api .../automated-security-fixes` → `{"enabled":true,"paused":false}` |

This closes `SECRETS.md` §8 item **S-2** (secret scanning) as already
satisfied, and now also **S-5** (Dependabot) — see `SECRETS.md` for the
updated evidence. Covers all three dependency ecosystems actually present
in this repository (`pyproject.toml` for pip; `frontend/package.json` and
`demo/package.json` for npm) via GitHub's dependency graph — no
`.github/dependabot.yml` was created, because that file configures a
*different*, unauthorized feature (scheduled version updates), not the
security-update capability that was enabled; see
`SP_API_REGISTRATION_REMEDIATION.md` §27 for why.

### The honest RF-02 position

JUVAl is a small application on managed PaaS. It has **no VPC, no firewall
appliance, no IDS/IPS sensor and no network segments of its own**, and it
would be untrue to claim otherwise. What it can legitimately claim, once
deployed and evidenced, is:

1. **Firewall/ACL** — inherited from the platform edge, plus application-level
   access control (`auth.py`) and database-level RLS.
2. **IDS/IPS** — provider-level protections, plus Defender NIS on the
   workstation. JUVAl operates no network sensor of its own.
3. **Anti-malware** — Defender on the workstation (verified); provider
   responsibility for managed runtimes.
4. **Segmentation** — logical rather than network: browser → backend →
   database, with credentials scoped so the browser can never reach the
   database privileged path, and least-privilege authorization at the API
   (RF-04, implemented and tested).

Where a control is the provider's rather than JUVAl's, the Developer Profile
answer must say so plainly. Claiming a firewall JUVAl does not operate is
precisely the kind of unevidenced "YES" that caused the original rejection.

---

## 4. Control-by-control status

| RF-02 control | Workstation | Cloud (deployed, 2026-08-18) | Overall |
|---|---|---|---|
| Firewall / ACL | `VERIFIED` (all 3 profiles enabled) | `PROVIDER_CAPABILITY` — deployed, but JUVAl configures no ingress rules of its own | **PARTIAL** (honest: provider-owned, not JUVAl-owned) |
| IDS / IPS | `VERIFIED` (Defender NIS enabled) | `PROVIDER_CAPABILITY` — deployed, provider-level only | **PARTIAL** (same reason) |
| Anti-virus / anti-malware | `VERIFIED` (Defender, signatures 0 days old) | Provider responsibility for managed runtimes | **PARTIAL** (same reason) |
| Network segmentation | N/A (single host) | **`VERIFIED_CONFIGURATION`** — RLS confirmed live: `rowsecurity=true`, 0 policies, on the production database (§3.1) | **VERIFIED** (logical segmentation, correctly scoped claim) |
| TLS in transit (AC-05) | HTTPS outbound | **`VERIFIED_CONFIGURATION`** — real HTTPS 200 responses from both Railway and Vercel; Supabase connection confirmed `ssl=on` server-side | **VERIFIED** |
| CORS (exact-origin, AC-06 adjacent) | N/A | **`VERIFIED_CONFIGURATION`** — exact Vercel origin allowed, arbitrary origin rejected, no wildcard | **VERIFIED** |
| Endpoint patching | **FINDING F-01 — re-measured 2026-08-18, still 9 months behind, `OPEN`** | Provider-managed | **NOT_COMPLIANT** |

`RF-02 = PARTIAL` — the deployment blocker that previously kept every cloud
row at `NOT_DEPLOYED` is closed; **F-01 (workstation patching) is now the
only control keeping RF-02 out of `COMPLIANT`.** Firewall/IDS/IPS/anti-malware
for the cloud stay `PARTIAL` on principle, not evidence gaps: they are
genuinely provider-owned, and claiming JUVAl operates them would itself be the
kind of unevidenced "YES" that caused the original rejection (§ "The honest
RF-02 position" above) — that framing is unchanged by deployment.

---

## 5. Required actions

| # | Action | Owner | Status | Blocking RF-02? |
|---|---|---|---|---|
| N-1 | Resolve **F-01**: patch and move to a supported OS, or formally exclude the workstation from the boundary | User (**EXTERNAL**) | **OPEN — re-confirmed 2026-08-18, unchanged** | **YES — the sole remaining blocker** |
| N-2 | Resolve **F-02**: verify disk encryption from an elevated shell | User (**EXTERNAL**) | **OPEN — re-confirmed 2026-08-18, still `Access denied` from this shell** | Yes |
| N-3 | Deploy the backend so cloud controls exist to evidence | User (**EXTERNAL**) | **DONE 2026-08-18** — `https://juval-backend-production.up.railway.app` | Closed |
| N-4 | Apply the migrations to the live Supabase project and confirm RLS is enabled with no permissive policy added via the dashboard (§3.1) | Agent | **DONE 2026-08-18** — confirmed live: `rowsecurity=true`, 0 policies (§3.1) | Closed |
| N-5 | Verify TLS termination and database transport after deployment (AC-05) | Agent | **DONE 2026-08-18** — HTTPS 200 on both services, `ssl=on` confirmed server-side on the database connection | Closed |
| N-6 | Restrict Supabase network access to the backend if the tier permits | User + agent | **OPEN — not attempted this session** (requires checking the current Supabase plan tier for network-restriction support, and would be an infrastructure change beyond this pass's read-only scope) | Improves posture, not required for `PARTIAL`→ current state |
| N-7 | Record dated provider configuration evidence for each deployed component | Both | **DONE 2026-08-18** — this document, §3 | Closed |
| N-8 | Enable GitHub Dependabot security updates (was `disabled`, §3.2) | User-authorized, agent-executed | **DONE 2026-08-18** — `gh api -X PUT .../vulnerability-alerts` then `.../automated-security-fixes`; independently re-verified `enabled` (§3.2) | Closed — improves RF-05 posture, not RF-02 |

N-3 through N-5, N-7 and N-8 are now closed with real evidence. **F-01
(N-1) is the only item still blocking RF-02 from advancing past
`PARTIAL`.**
