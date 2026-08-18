# JUVAl — Network Security Architecture and Control Audit (RF-02)

| Field | Value |
|---|---|
| Status | **PARTIAL.** Workstation controls measured and evidenced; cloud components are **not deployed**, so their controls cannot be evidenced. |
| Audit date | `2026-08-18` |
| Method | Read-only inspection of the developer workstation; official provider documentation for capability claims. No configuration was changed. |
| Amazon finding | **RF-02** — firewall, IDS/IPS, anti-virus/anti-malware, network segmentation |
| Related control | `AC-06` (DPP §1.1), `AC-05` (TLS, DPP §1.5) |

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
| **F-01** | **HIGH** | The most recent operating-system update was installed **2025-11-19** — roughly nine months before this audit. Windows 10 also reached end of mainstream support in October 2025. A host that is nine months behind on patches, on an OS past end-of-support, cannot credibly be described to Amazon as a maintained endpoint within the security boundary. | **EXTERNAL USER ACTION:** either (a) bring the workstation fully up to date and move to a supported OS (Windows 11 or Windows 10 with an ESU subscription), or (b) formally remove the workstation from the Amazon Information boundary — never handle Amazon Information or credentials on it — and document that exclusion. Option (a) is strongly preferred. |
| **F-02** | MEDIUM | Disk-encryption status could not be read without elevation, and Windows 10 **Home** does not include full BitLocker management (only "Device Encryption" where hardware supports it). An unencrypted disk holding supplier data or, later, cached credentials is a loss/theft exposure (`INCIDENT_RESPONSE_PLAN.md` T-07). | **EXTERNAL USER ACTION:** run `Get-BitLockerVolume` in an elevated PowerShell and record the result; enable device encryption if available, or record the compensating control. |
| **F-03** | LOW | The workstation firewall profiles show `DefaultInboundAction: NotConfigured`, i.e. the Windows default (block unsolicited inbound) rather than an explicit policy. The effective behavior is correct; the *explicitness* is not. | Optional: set the default inbound action explicitly so the posture is stated rather than inherited. |

F-01 is the single most consequential item in this document. It is a real
control gap on a real machine, not a documentation gap.

---

## 3. Cloud components — NOT DEPLOYED

Nothing below is deployed. Every row is therefore `PROVIDER_CAPABILITY` at
best; **none reaches `VERIFIED_CONFIGURATION`**, and none may be presented to
Amazon as an implemented control.

| Component | Deployed? | Firewall / ACL | IDS/IPS | Anti-malware | Segmentation | TLS |
|---|---|---|---|---|---|---|
| **Railway** (backend) | **NO** — `railway.toml` prepared, never deployed (ADR-018) | Provider-managed edge; JUVAl-level ingress rules unconfigured | Provider-level only; no JUVAl-visible IDS/IPS configured | Provider runtime responsibility | Would rely on provider network isolation, not a JUVAl-designed VPC | Provider terminates HTTPS |
| **Vercel** (PWA) | **NO** | Provider edge/WAF capability | Provider-level | N/A (static assets) | Static hosting, no backend reachability | Provider terminates HTTPS |
| **Supabase** (PostgreSQL) | Project exists; **not verified against a live JUVAl deployment** | Network restrictions available on paid tiers; current state unverified | Provider-level | Provider responsibility | **RLS is the primary control and has no policies verified for JUVAl tables** | TLS via connection pooler |
| **GitHub** (source) | Repository exists | N/A | N/A | N/A | Branch/access controls unverified | HTTPS |

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

| RF-02 control | Workstation | Cloud (post-deployment) | Overall |
|---|---|---|---|
| Firewall / ACL | `VERIFIED` (all 3 profiles enabled) | `PROVIDER_CAPABILITY`, not deployed | **PARTIAL** |
| IDS / IPS | `VERIFIED` (Defender NIS enabled) | `PROVIDER_CAPABILITY`, not deployed | **PARTIAL** |
| Anti-virus / anti-malware | `VERIFIED` (Defender, signatures 0 days old) | Provider responsibility | **PARTIAL** |
| Network segmentation | N/A (single host) | **Logical only**; RLS policies unverified | **NOT_IMPLEMENTED** |
| TLS in transit (AC-05) | HTTPS outbound | `PROVIDER_CAPABILITY`, not verified | **NEEDS_VERIFICATION** |
| Endpoint patching | **FINDING F-01 — 9 months behind** | Provider-managed | **NOT_COMPLIANT** |

`RF-02 = PARTIAL` — and it cannot advance beyond PARTIAL until the backend is
actually deployed, because there is no system to evidence.

---

## 5. Required actions

| # | Action | Owner | Blocking RF-02? |
|---|---|---|---|
| N-1 | Resolve **F-01**: patch and move to a supported OS, or formally exclude the workstation from the boundary | User (**EXTERNAL**) | **YES** |
| N-2 | Resolve **F-02**: verify disk encryption from an elevated shell | User (**EXTERNAL**) | Yes |
| N-3 | Deploy the backend so cloud controls exist to evidence | User (**EXTERNAL** — `railway login` is interactive) | **YES** |
| N-4 | Define and apply Supabase RLS policies for JUVAl tables, then test them negatively | Agent, after N-3 | **YES** |
| N-5 | Verify TLS termination and database transport after deployment (AC-05) | Agent, after N-3 | Yes |
| N-6 | Restrict Supabase network access to the backend if the tier permits | User + agent, after N-3 | Improves posture |
| N-7 | Record dated provider configuration evidence for each deployed component | Both, after N-3 | **YES** |

Note that N-3 gates N-4 through N-7: **RF-02 cannot be closed without a
deployment**, and the deployment requires an interactive provider login the
agent cannot perform.
