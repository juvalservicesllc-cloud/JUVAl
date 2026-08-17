# JUVAl — SP-API Registration Remediation Plan

**Status:** DRAFT / NOT COMMITTED / NOT PUSHED. Documentation and audit only.
No control, integration, credential, queue or infrastructure change is made
by this plan.

## 1. Decision and operating boundary

| Item | State | Evidence |
|---|---|---|
| Developer registration | `REJECTED_REMEDIATION_REQUIRED` / **NOT ELIGIBLE FOR SP-API ACCESS** | Amazon reviewer decision communicated 2026-08-17 |
| Decision date | `2026-08-17` | Same decision; no personal email, case ID or unnecessary identifier retained |
| Next Amazon action | Update Developer Profile truthfully and submit a **new case**; never reopen the prior case | Reviewer instruction |
| Production client / self-authorization / credentials / live calls | NOT CREATED / NOT PERFORMED / NOT AVAILABLE / NOT PERFORMED | Repository and onboarding baseline |

The five findings below are reviewer findings. Their mapping to public policy
is explicit; a more specific reviewer statement remains a
`REVIEWER_REQUIREMENT / POLICY TRACEABILITY NEEDS VERIFICATION` until the
public source proves the same scope.

## 2. Finding-to-control reconciliation

| FINDING_ID | AMAZON_FINDING | RELATED_AC_CONTROLS | OFFICIAL_POLICY_SOURCE | SOURCE_SECTION | AUTHORITY_TYPE | SCOPE | CURRENT_JUVAL_STATE | CURRENT_EVIDENCE | GAP | REMEDIATION_REQUIRED | EVIDENCE_REQUIRED | BLOCKS_REAPPLICATION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RF-01 | Notify `security@amazon.com` within 24 hours of detecting an incident involving Amazon Information. | AC-12 | Data Protection Policy | §1.6 | NORMATIVE_POLICY + reviewer address trace pending | Security Incident / Information | NOT_IMPLEMENTED | No plan, IMPOC, notification runbook or drill | No accountable 24-hour procedure | Incident plan, escalation clock, evidence preservation and notification workflow | Approved plan, drill/test record, dated review | YES |
| RF-02 | Firewall, IDS/IPS, anti-malware and segmentation. | AC-06 | Data Protection Policy | §1.1 | NORMATIVE_POLICY | Systems handling Information | NOT_IMPLEMENTED | No real deployment/topology/control evidence | Network controls unverified and absent from repo | Define and implement controls only after approval; document boundary | Network diagram, provider configuration, control test | YES |
| RF-03 | 12-character passwords, special characters, MFA, 365-day expiry, annual rotation. | AC-07, AC-08 | Data Protection Policy | §§1.2–1.4.2 | NORMATIVE_POLICY; exact reviewer scope pending | User and programmatic credentials | NOT_IMPLEMENTED | No app auth/MFA/password lifecycle; no SP-API secret | Identity and credential controls absent | Identity policy/configuration, rotation/revocation and review process | Configuration evidence, MFA test, rotation/access records | YES |
| RF-04 | Restrict Amazon Information access by job duty/business function. | AC-07, AC-14A | Data Protection Policy; Acceptable Use Policy | §§1.2–1.3; §§4.6–4.9 | NORMATIVE_POLICY | Personnel, service accounts and processors | NOT_IMPLEMENTED | No access matrix, RLS policy evidence or production lifecycle | Least-privilege boundary not evidenced | Role matrix, grants, quarterly review and revocation | Access review record, authorization tests, provider review | YES |
| RF-05 | Defined incident roles, six-month plan review, 24-hour notification procedure. | AC-12 | Data Protection Policy | §1.6 | NORMATIVE_POLICY | Security incidents involving Information | NOT_IMPLEMENTED | No plan, roles, six-month review or exercise | Response governance absent | Approved plan, ownership, review cadence and exercise | Plan, review record, exercise/evidence-preservation record | YES |

Official source URLs and verification date: Agreement, DPP and AUP were
verified 2026-08-17 in
[`AMAZON_SP_API_COMPLIANCE.md`](AMAZON_SP_API_COMPLIANCE.md) §§2–3a.
Amazon implementation guidance is secondary and cannot amend those policies.

## 3. Current JUVAl evidence audit

| Area | Classification | Evidence / gap |
|---|---|---|
| `.env`, Git and secret handling | PARTIALLY_IMPLEMENTED | `.gitignore` excludes real `.env`; templates contain placeholders; no SP-API secret exists; no production secret-store evidence. |
| Authentication, MFA and authorization | NOT_IMPLEMENTED | Current API has no user authentication, MFA or role lifecycle; do not infer compliance from documentation. |
| Network controls | EXTERNAL_CONFIGURATION_NEEDS_VERIFICATION | Railway/Vercel/Supabase topology and firewall/IDS/IPS/anti-malware/segmentation evidence are absent. |
| Logging and monitoring | PARTIALLY_IMPLEMENTED | API exception method/path logging exists; no secure central audit logs, alerts, retention or bi-weekly review evidence. |
| Incident response | NOT_IMPLEMENTED | No approved plan, roles, IMPOC, six-month review or 24-hour drill. |
| Vulnerability management | NOT_IMPLEMENTED | No recurring scan, SLA, pen-test or assessment evidence. |
| Access lifecycle | NOT_IMPLEMENTED | No production access inventory, quarterly review or 24-hour revocation record. |

## 4. Infrastructure boundary (not a provider compliance determination)

| Component | Process | Store | Transmit | Access | Controls/evidence required | Status |
|---|---|---|---|---|---|---|
| Frontend/PWA | Could display derived results | Must not store SP-API secrets or raw Amazon Information by default | HTTPS to backend only | End-user view, never SP-API | Auth, TLS, no `VITE_*` secrets, redaction | NEEDS_VERIFICATION |
| Backend API | Would call SP-API and process Amazon Information | Would store only approved minimum and provenance | SP-API/TLS and database TLS | Service account and authorized operators | AuthZ, least privilege, logs, retention, secrets | NEEDS_VERIFICATION |
| Railway | Hosts backend if deployed | May hold runtime config/logs | Public ingress/egress | Provider operators/service | Contract, topology, firewall, logs, incident terms | NEEDS_VERIFICATION |
| Supabase | Database service | Could store Amazon Information | Backend/database TLS | Service role/admin and app role | RLS, encryption, backup/deletion, access review | NEEDS_VERIFICATION |
| Vercel | Frontend hosting target | Build artifacts only; no secrets | Browser/backend HTTPS | Provider/build actors | Environment separation and secret exclusion | NEEDS_VERIFICATION |
| GitHub | Source/CI hosting | Source and history; no Amazon secrets | Git/CI network | Developers/automation | Secret scan, branch/access review, retention | NEEDS_VERIFICATION |
| Developer workstation | Develop/audit only | Local files could contain test data | Uploads/dependency traffic | Developers | Disk/account/MFA, no secrets in repo, revocation | NEEDS_VERIFICATION |
| Future worker/queue | Would enrich/retry Amazon calls | Retry/audit metadata only | SP-API/provider traffic | Service account | Throttling, idempotency, no credentials in payloads/logs | FUTURE / NEEDS_VERIFICATION |
| Future historical-data provider | Could provide non-Amazon comparison data | Provider-defined | Provider API | Backend | Contractual/data-sharing and classification review | NEEDS_VERIFICATION |

## 5. Remediation matrix

| CONTROL | AMAZON_FINDING | CURRENT_STATE | TARGET_STATE | IMPLEMENTATION_REQUIRED | INFRA_COMPONENT | EVIDENCE_TO_PRODUCE | VALIDATION | DEPENDENCIES | PRIORITY | ESTIMATED_COMPLEXITY | BLOCKS_SP_API_REAPPLICATION |
|---|---|---|---|---|---|---|---|---|---|---|---|
| IR notification | RF-01/RF-05 | NOT_IMPLEMENTED | Tested 24-hour notification | Plan, role, clock, evidence chain | Backend/ops | Plan, drill, review record | Tabletop exercise | Owner, contact, logging | P0 | Medium | YES |
| Network defense | RF-02 | NOT_IMPLEMENTED | Verified layered controls | Firewall, IDS/IPS, anti-malware, segmentation | Railway/Supabase/Vercel/backend | Topology/config/test | Independent control review | Provider facts/contracts | P0 | High | YES |
| Credential/access security | RF-03 | NOT_IMPLEMENTED | Enforced identity/MFA/password/rotation | Auth, MFA, password and programmatic credential lifecycle | Backend/provider/workstation | Config, tests, rotation records | Access and compromise drills | Identity decision, secret store | P0 | High | YES |
| Least privilege | RF-04 | NOT_IMPLEMENTED | Job-function access with revocation | Role matrix, grants, quarterly review, 24-hour removal | Backend/Supabase/providers | Access review and authorization tests | Negative/positive access tests | Auth and data classification | P0 | High | YES |
| Reviewer reconciliation | RF-01–RF-05 | REJECTED | All findings remediated and evidenced | Update profile truthfully; new case only | Developer Profile | Evidence index and submitted answers | Independent pre-submit review | All P0 controls | P0 | Medium | YES |

## 6. Evidence model and profile gates

Acceptable evidence is dated and reproducible: `CONFIGURATION_EVIDENCE`,
`POLICY_DOCUMENT`, `TEST_RESULT`, `ACCESS_REVIEW_RECORD`,
`INCIDENT_RESPONSE_DOCUMENT`, `NETWORK_CONFIGURATION`,
`LOGGING_CONFIGURATION`, `SECURITY_SCAN_RESULT`, and
`PROVIDER_CONFIGURATION`. Evidence must never contain passwords, client
secrets, refresh/access tokens or other secret values.

### DEVELOPER_PROFILE_REAPPLICATION_GATE

JUVAl will not answer **YES** to a Developer Profile control until the
requirement is identified, real implementation exists, evidence exists and
has been validated, and the answer does not contradict deployed reality.
`DECLARED YES — EVIDENCE INCOMPLETE` remains an open remediation state.

### AMAZON SP-API REAPPLICATION GATE

Do not submit a new case until RF-01 through RF-05 are
`REMEDIATED_AND_EVIDENCED` (or have a documented, evidence-backed
`NOT_APPLICABLE` determination), applicable `AMAZON_MANDATORY` MUST controls
are evidenced, and the Developer Profile is updated truthfully. Submit a new
case; never reopen the prior case.

## 7. Future-only queue implications

If Amazon access is later approved, architecture must document per-provider
and per-operation throttling, observed rate-limit handling, 429 backoff,
persistent retry state, idempotency, resumability, incremental results,
audit metadata, and the rule that operational errors are never `NOT_FOUND`.
Credentials are forbidden in job payloads and logs. No queue is implemented
by this plan.

## 8. Recommended order and approvals

1. Approve scope/ownership and classify intended Amazon operations and data.
2. Design and implement P0 controls in the real target infrastructure.
3. Produce independent evidence and run the gates above.
4. Update the Developer Profile truthfully and submit a new case.
5. Only after approval, create the minimum-privilege client and proceed with
   the existing SP-API authorization gates.

Estimated planning/implementation effort: **P0 controls are a multi-week
security workstream**, with network/provider evidence and identity lifecycle
the highest uncertainty. No estimate is a claim of completion.

## 9. Security remediation architecture (design only)

### 9.1 Real security boundary audit

| Component | Owner | Amazon Information / secrets | AuthN / AuthZ | Network / encryption / backup | Logging / incident responsibility | Evidence now |
|---|---|---|---|---|---|---|
| Developer workstation | JUVAl operator | Supplier files today; no Amazon data or SP-API secret | Local OS identity; no MFA evidence | Windows/provider defaults not verified; disk/backup unknown | Local logs and response owner not defined | `.env` policy and source scan only |
| GitHub | JUVAl repository owner | Source/history; no Amazon data or secrets permitted | Account controls unknown; no security settings evidence | Provider controls available but current configuration unknown | Repository audit responsibility not assigned | Git repository and `.gitignore` |
| Vercel / PWA | JUVAl deployment owner | Intended presentation of derived results only; never SP-API secrets | No deployed frontend/auth evidence | HTTPS capability available; deployment/config unverified; backup unknown | No production logs or owner evidence | ADR-014/PROJECT_STATUS only |
| Backend API | JUVAl application owner | Would process Amazon Information after approval | FastAPI has no user AuthN/AuthZ/MFA | TLS/deployment/provider topology unverified; local temp upload is deleted | Exception method/path logging only; no security audit stream | `src/juval/interfaces/api/main.py` |
| Railway | JUVAl deployment owner / Railway provider boundary | Would run backend and runtime configuration | Account/configuration unknown | `railway.toml` exists; no account, firewall, IDS/IPS or backup evidence | Provider responsibility and alerting unverified | `railway.toml`, ADR-018 |
| Supabase | JUVAl database owner / Supabase provider boundary | Could store runs/derived data; Amazon scope unverified | Service-role path exists in template; RLS/auth not operationally verified | TLS/provider encryption and backups available only as capability; project not verified | Database audit/incident ownership unknown | ADR-017, migrations, `.env.example` |
| Future worker/queue | JUVAl application owner | Would process Amazon Information and retry metadata | Service identity required; not implemented | Provider topology, TLS, backups and limits TBD | Must emit auditable retry/security events | None; future only |
| Future historical provider | JUVAl sourcing owner / provider boundary | Could transmit/store comparison data; classification unknown | Contract and service identity TBD | Provider security/retention unknown | Provider incident terms and due diligence required | None; candidate only |
| SP-API | Amazon / JUVAl integration owner | Would be source of Amazon Information | No client, authorization or credentials | Amazon TLS and rate limits apply; JUVAl controls still required | Incident contact and evidence obligations apply | Rejected registration only |

`AVAILABLE_PROVIDER_CAPABILITY` is not evidence of `VERIFIED_CURRENT_CONFIGURATION`.
Railway, Vercel, Supabase, GitHub and Windows must each supply dated
configuration evidence before any control can move to verified.

### 9.2 Identity architecture recommendation (not approved)

The repository has no application authentication, MFA, RBAC or account
lifecycle. A custom password system is rejected as an architectural option.
Clerk remains `PENDING` in the project contract; it is a candidate Identity
Provider, not a decision. Before implementation, compare Clerk with an
equivalent managed IdP against MFA, RBAC, session security, revocation,
auditability and password-policy enforcement.

The design must keep four identities separate:

1. **Human JUVAl users:** IdP-managed accounts, MFA, password policy and
   job-function role assignment.
2. **Infrastructure accounts:** Railway/Vercel/Supabase/GitHub operator
   accounts with provider MFA and separate ownership.
3. **Service credentials:** backend/database/deployment identities, non-human,
   scoped, rotated and revoked independently of human passwords.
4. **SP-API credentials:** not available; backend-only after approval, never
   browser or `VITE_*` configuration.

Password requirements must be applied to human accounts only where Amazon's
scope requires them. Programmatic credentials require encryption, access
restriction, rotation and revocation; they are not human passwords.

### 9.3 RF-02 network architecture

| Control | Provider capability | Default/optional | Currently verified? | Configuration required | Evidence |
|---|---|---|---|---|---|
| Firewall / ACL | Railway, Supabase, Vercel and Windows may expose platform/network controls | Unknown per product/configuration | NO | Select and configure exact boundary; deny unnecessary ingress | Export/configuration and external probe |
| IDS/IPS | Platform or managed security service may provide it; no repo evidence | Optional/unknown | NO | Confirm coverage for every Amazon-data path | Provider statement plus enabled setting/test |
| Anti-malware | Windows endpoint and provider runtime controls may exist | Optional/unknown | NO | Enable/maintain endpoint and server protection | Version/status and monthly update record |
| Segmentation | Separate frontend, backend, database and operator access paths | Design required | NO | Restrict backend/database ingress and admin paths | Network diagram, rules and negative tests |

No provider is declared compliant based on marketing claims. RF-02 remains
`NOT_IMPLEMENTED` until real configuration and evidence exist.

### 9.4 Credential-management architecture

| Credential class | Storage | Rotation/revocation | Access/audit |
|---|---|---|---|
| Human passwords | Managed IdP only; never repository or frontend | IdP policy, MFA and termination workflow | Per-user identity, access review, audit events |
| Infrastructure accounts | Provider secret store/password manager | Annual minimum where applicable and on compromise | Named operators, MFA, provider audit logs |
| Service credentials | Backend-only secret store; separate environments | Scoped rotation and immediate compromise revocation | Service identity, access log, no payload/log values |
| SP-API credentials | Not present; future backend-only secret store | Annual/programmatic policy and immediate compromise revocation | Restricted operators, rotation record, redaction test |
| GitHub/deployment credentials | Provider-managed secret store or approved vault | Rotation and revocation on role change | Repository/environment audit evidence |

No secret value is evidence. Evidence is configuration metadata, redacted
test output, rotation timestamp and access review record.

### 9.5 Minimum RBAC model (proposal)

Role names remain pending approval. Derive the smallest set from actual
functions:

| Capability | Required role boundary |
|---|---|
| Upload supplier catalog / view supplier results | Operator-like product role |
| View Amazon-enriched data / start enrichment | Explicitly authorized enrichment role; not every viewer |
| Export results | Separate export permission if exports contain Amazon Information |
| Modify thresholds/configuration | Configuration administrator only |
| Manage integrations and SP-API credentials | Integration administrator; never ordinary analyst |
| Manage users/access reviews | Identity administrator |
| Read secrets | No human default; break-glass/audited operator only |

Least privilege, quarterly access review and removal within 24 hours remain
requirements to evidence. Do not create a broad Administrator role merely for
convenience.

### 9.6 Incident-response architecture

The future plan must define: incident and Amazon Information classification,
severity, incident owner, IMPOC/security contact, detection, containment,
credential revocation, evidence preservation, Amazon-data determination,
24-hour decision/notification clock, internal timeline, postmortem,
six-month review, version history and tabletop validation. It must contain a
specific procedure for `security@amazon.com`; no email is sent by this plan.

## 10. Evidence matrix

| Control | Required evidence | Current classification |
|---|---|---|
| RF-01/RF-05 | Approved incident plan, owner/IMPOC, notification drill, six-month review timestamp | PROCEDURAL_REQUIRED / NOT_IMPLEMENTED |
| RF-02 | Topology, firewall/ACL, IDS/IPS, anti-malware status, segmentation tests | AVAILABLE_NOT_CONFIGURED / NEEDS_EXTERNAL_ACTION |
| RF-03 | IdP password/MFA settings, service-secret inventory, rotation/revocation records | NOT_IMPLEMENTED |
| RF-04 | Role matrix, authorization tests, quarterly access review, termination drill | NOT_IMPLEMENTED |
| Profile answers | Versioned evidence index and independent pre-submit review | NEEDS_EXTERNAL_ACTION |

## 11. Gap matrix and implementation plan

| Priority | Task | WHY | Files/system | Dependencies | Manual action | Test/evidence | Rollback | Done when |
|---|---|---|---|---|---|---|---|---|
| P0 | Select and configure managed IdP | RF-03/RF-04 | Identity provider + backend boundary | ADR approval | User configures tenant/MFA | MFA/RBAC/revocation tests | Disable integration/config revert | Dated config and tests pass |
| P0 | Establish network controls | RF-02 | Railway/Supabase/Vercel/Windows | Provider capability verification | Configure provider controls | Network evidence and negative probes | Revert rules safely | All four controls evidenced |
| P0 | Approve incident plan | RF-01/RF-05 | Compliance documentation/operations | Named owner/contact | Approve plan and run tabletop | Tabletop and six-month review record | Supersede versioned plan | Notification path proven |
| P0 | Establish credential lifecycle | RF-03 | IdP/provider secret stores | IdP and vault choice | Configure rotation/revocation | Redaction and rotation tests | Revoke/restore documented | No secret reaches frontend/logs |
| P0 | Validate least privilege | RF-04 | Backend/database/provider roles | Identity + data classification | Review grants quarterly | Positive/negative authorization tests | Remove grants | Job-function matrix evidenced |
| P1 | Central logging, alerting and vulnerability program | Production readiness | Backend/provider/CI | P0 boundary | Enable scans/reviews | Scan, log-retention and alert evidence | Disable only by documented change | Recurring evidence established |
| P1 | Backup/recovery and deletion lifecycle | Data protection | Supabase/provider | Data classification | Configure backups/TTL/deletion | Recovery and deletion tests | Restore/versioned config | Retention and recovery evidenced |
| P2 | Hardening and automation | Reduce operational error | CI/providers | P0/P1 stable | Automate evidence collection | Scheduled checks | Disable automation | Review cadence sustainable |

### Actions requiring user/operator authority

Provider account configuration, IdP selection, MFA enrollment, network rules,
secret-store provisioning, incident-owner approval, tabletop exercise,
access reviews, provider contracts and any future Amazon Developer Profile
answer remain manual actions. Claude must not perform them implicitly.

### Actions Claude may implement after approval

Documentation, ADRs, redaction tests, authorization tests, configuration
validation and non-secret evidence checkers may be implemented only after the
identity/provider decisions are approved. No such implementation is made in
this session.

## 12. ADR candidates (not approved)

- Identity Provider and authentication boundary (managed IdP alternatives).
- Minimum RBAC and data-access model.
- Secret-management boundary and rotation ownership.
- Production security boundary across Railway/Supabase/Vercel.
- Incident-response ownership and escalation authority.

An ADR is warranted only after alternatives, scope and owner are decided;
this plan approves none of them.
