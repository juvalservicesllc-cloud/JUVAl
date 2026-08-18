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

## 13. Identity-provider research checkpoint (2026-08-17)

Clerk documentation was reviewed as a candidate only. It documents MFA,
session lifetime/inactivity controls, organization roles/permissions and
secret-key rotation, but the following Amazon-specific items are not yet
evidenced for a JUVAl production instance:

| Requirement | Clerk candidate result | Classification |
|---|---|---|
| MFA | TOTP/SMS/backup codes and forced MFA session task documented | SUPPORTED WITH CONFIGURATION |
| 12-character minimum | Current password guidance documents NIST-style minimums, not a verified JUVAl 12-character enforcement setting | NEEDS_VERIFICATION |
| Special characters | No verified tenant setting proving this exact rule | NEEDS_VERIFICATION |
| 365-day expiration | Session lifetime is documented; password expiration policy is not verified | NEEDS_VERIFICATION |
| Annual password rotation | No verified automatic annual human-password rotation policy | NOT_SUPPORTED / NEEDS_VERIFICATION |
| Sessions and forced revocation | Session lifetime/inactivity and user/session controls are documented | SUPPORTED WITH CONFIGURATION |
| Organizations, roles, permissions, RBAC | Organization custom roles and permissions documented; server-side custom permission checks are required | SUPPORTED WITH CUSTOM IMPLEMENTATION |
| Disable/delete users | Platform user-management capability exists; operational evidence is absent | SUPPORTED WITH CONFIGURATION |
| Audit/access-review evidence | Provider/API audit capability and exports require plan/tenant verification; quarterly review remains JUVAl responsibility | NEEDS_VERIFICATION |
| Administrative MFA | MFA is available; administrator enforcement and plan constraints require tenant verification | NEEDS_VERIFICATION |
| API/service separation | Publishable vs secret keys and backend verification are documented | SUPPORTED WITH CONFIGURATION |

Sources: [Clerk password rules](https://clerk.com/docs/guides/secure/password-protection-and-rules),
[MFA/session tasks](https://clerk.com/docs/guides/configure/session-tasks),
[session security](https://clerk.com/docs/guides/secure/session-options),
[roles and permissions](https://clerk.com/docs/guides/organizations/control-access/roles-and-permissions),
and [secret-key rotation](https://clerk.com/docs/guides/secure/rotate-api-keys),
verified 2026-08-17. These sources do not constitute Amazon compliance
evidence. RF-03 and RF-04 therefore remain blocked pending provider-plan
verification and an approved identity architecture.

### RF-03 identity-scope status

Official Amazon guidance says MFA applies to “all accounts” and separately
defines credentials broadly (including passwords, API keys, encryption keys
and SP-API client credentials/tokens). It distinguishes API-key rotation and
credential protection from the human password lifecycle, but does not clearly
state whether password composition/expiration applies to JUVAl application
end users, personnel with Amazon Information access, provider administrators,
or every category. Therefore:

`RF-03 IDENTITY SCOPE = NEEDS AMAZON CLARIFICATION`

This is not a favorable reinterpretation and does not reduce any reviewer
requirement. A proposed clarification is recorded in ADR-021; it must not be
sent until reviewed by the user.

`AMAZON_RF03_SCOPE_CLARIFICATION = PENDING_EXTERNAL_ACTION`
`IDENTITY SECURITY GATE = BLOCKED`
`REAPPLICATION GATE = BLOCKED`

## 14. SP-API Guard decision (official documentation, 2026-08-17)

`SP_API_GUARD = DEFERRED`

Rationale: Guard is an optional self-assessment oriented primarily to AWS;
JUVAl's current target production boundary is Railway/Vercel/Supabase; it does
not resolve RF-03/RF-04/RF-05; introducing AWS solely for Guard would add
infrastructure and security surface. It may be reconsidered if JUVAl later
operates material AWS infrastructure or Amazon specifically requests the
additional evidence. No Guard deployment or further Guard research is
authorized without new evidence.

### Purpose and status

Amazon describes SP-API Guard as an optional, serverless AWS application for
automated self-service Data Security Assessments against AWS data in the
context of the Data Protection Policy. It produces findings, policy
references and remediation recommendations; it does not implement JUVAl
controls and is not itself a compliance approval. The official guide states
that the assessment is independent, may be shared with Amazon by user choice,
and that Amazon makes no contractual assurance through the documentation.

Sources: [Implementation Guide](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-implementation-guide),
[Guide History](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-document-history),
verified 2026-08-17.

### Applicability and boundary

| Question | Official finding |
|---|---|
| Mandatory? | No evidence that Guard is mandatory; documentation presents it as self-service assessment. |
| Private developers? | Access requires the Solution Provider Portal/Developer credentials and a Seller Central merchant token; specific private-developer eligibility is not stated. `NEEDS_VERIFICATION`. |
| AWS hosting required? | Yes for Guard itself: CloudFormation deploys AWS resources and scans AWS infrastructure. JUVAl does not need to migrate its application to AWS, but Guard cannot directly assess Railway/Vercel/Supabase/Windows controls from the documented scan model. |
| External/non-AWS systems? | Not demonstrated. Treat Railway, Vercel, Supabase and workstation findings as outside Guard scope. |
| Share with Amazon? | Yes, an explicit `report_to_amazon` path exists; sharing is voluntary and is not evidence that Amazon will approve a reapplication. |

### Components, permissions and lifecycle

The reference CloudFormation architecture creates S3, SNS, Lambda,
EventBridge, IAM roles, VPC, subnets, security groups and an Amazon Linux 2
EC2 CLI instance. It enables Macie, GuardDuty, Inspector, IAM Access
Analyzer, Security Hub and AWS Config for the scan. Guard uses IAM roles and
temporary AWS resources; it does not require or request JUVAl SP-API secrets
according to the security guide. It collects account/IAM/operational scan
information, not proprietary data or the specific tools themselves.

Services activated for scans are automatically disabled after 24 hours. The
EC2 instance and VPC are automatically deleted after 30 days, with immediate
cleanup available via `cleanup_guard_interface` or the documented uninstall
procedure. The S3 report bucket and stack artifacts still require explicit
cleanup verification.

Sources: [Architecture Overview](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-architecture-overview),
[Components](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-components),
[Guard and Security](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-security),
[Automated Deployment](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-automated-deployment),
verified 2026-08-17.

### Controls assessed versus controls not demonstrated

| JUVAl control area | Guard relevance | Limitation |
|---|---|---|
| AWS network exposure / some IDS/GuardDuty signals | Assessment of AWS VPC/flow/log domains | Does not prove Railway/Vercel/Supabase/Wi-Fi/workstation controls or complete segmentation design |
| AWS malware signals | GuardDuty/endpoint domains for AWS workloads | Not a universal antivirus/anti-malware implementation or proof for non-AWS endpoints |
| AWS IAM external sharing | IAM Access Analyzer | Does not establish JUVAl job-function RBAC in FastAPI or human access reviews |
| AWS vulnerabilities | Inspector for EC2/ECR | Does not replace application SAST/DAST, annual pen test or provider scans |
| S3 PII/encryption/public exposure | Macie | Only AWS S3 sample/data domain; not Supabase or all Amazon Information |
| AWS configuration/log aggregation | Config/Security Hub/GuardDuty domains | Does not create JUVAl incident-response plan, 24-hour procedure or six-month review |
| Password policy, MFA, 365-day expiry, annual human rotation | No documented Guard scan rule | RF-03 remains unresolved; Guard is not an IdP evidence substitute |
| Secrets/API tokens | Guard protects its own AWS roles but is not a JUVAl secret inventory | It does not validate absence of JUVAl secrets in frontend/provider systems |
| Incident response, ownership and notification | Findings can inform remediation | No evidence that Guard tests JUVAl roles, IMPOC, tabletop or Amazon notification workflow |

Guard evidence is therefore **assessment evidence for selected AWS domains**,
not implementation evidence or a replacement for policy, access reviews,
provider configuration, incident exercises or IdP evidence.

### Cost and support

Amazon's published example estimates a total below **$500 per scan** in
US East (N. Virginia), with first-use trials potentially making the first
scan close to $0; actual cost varies by account, region and service usage.
Regional availability matters: Guard is supported across AWS Regions, but
Macie and Inspector are not available in every Region. Amazon documents
Solution Architect support for remediation and Developer Support for
troubleshooting.

Source: [Guard Cost](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-cost)
and [Regional Deployments](https://developer-docs.amazon.com/sp-api/docs/sp-api-guard-regional-deployments),
verified 2026-08-17.

### RF-03 update

The official Guard guidance reinforces the previously recorded RF-03 facts:
12-character minimum, mixed case/numbers/special characters, no name/user
identifier, password history of 10, minimum age one day, maximum expiration
365 days, MFA for all accounts, and annual API-key/associated-credential
rotation. It does not resolve which JUVAl identity categories the reviewer
intended. `RF-03 IDENTITY SCOPE = NEEDS AMAZON CLARIFICATION` remains active.

### Support channel and sandbox

Amazon's Guard documentation directs technical Guard questions and feature
requests to a **Developer Support case**. RF-03 identity-scope clarification
should remain a concise Developer Support/security-compliance question, not a
Guard deployment request. SP-API sandbox testing is documented as a separate
development tool, but JUVAl has no client, authorization or credentials; no
sandbox access is evidenced here. Production rejection therefore remains a
blocker for live calls, while sandbox eligibility is `NEEDS_VERIFICATION` and
must not be attempted in this plan.

### Recommendation

**DEFERRED.** Guard must not be treated as a prerequisite, approval, or
substitute for RF-03–RF-05 remediation.

## 15. RF-03 human/programmatic boundary reconciliation

### Historical state

`PREVIOUS STATE: RF-03 IDENTITY SCOPE = NEEDS AMAZON CLARIFICATION`

### Subsequent official-documentation finding

Amazon's [Safeguarding Sensitive Credentials](https://developer-docs.amazon.com/sp-api/docs/safeguarding-sensitive-credentials)
and [Key Security Control Guidance](https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration)
separate human/user password controls from API/programmatic credential
controls. The former covers password composition/lifecycle and MFA for user
accounts; the latter covers encryption, restricted access and annual rotation
of API keys and associated credentials. This resolves the architectural
boundary, not implementation or evidence.

`RF-03 HUMAN VS PROGRAMMATIC CONTROL BOUNDARY = DOCUMENTATION RESOLVED / IMPLEMENTATION PENDING`
`AMAZON_RF03_SCOPE_CLARIFICATION = NOT REQUIRED FOR ARCHITECTURAL PROGRESS`

This does not mean COMPLIANT, IMPLEMENTED, EVIDENCED or REAPPLICATION READY.
`IDENTITY SECURITY GATE = BLOCKED` and `REAPPLICATION GATE = BLOCKED` remain.

## 16. Managed IdP reevaluation against the Amazon human-account baseline

Statuses: `NATIVE_VERIFIED`, `CONFIGURABLE_VERIFIED`,
`EXTERNAL_CONTROL_REQUIRED`, `NOT_SUPPORTED`, `NEEDS_VERIFICATION`.

| Control | Clerk | Amazon Cognito | Microsoft Entra External ID |
|---|---|---|---|
| Unique user IDs / no shared accounts | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED |
| ≥12 characters | NEEDS_VERIFICATION | CONFIGURABLE_VERIFIED | NOT_SUPPORTED |
| Upper/lower/numbers/special | NEEDS_VERIFICATION | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED (3 of 4) |
| Exclude username/name | NEEDS_VERIFICATION | NEEDS_VERIFICATION | NEEDS_VERIFICATION |
| Password history 10 | NEEDS_VERIFICATION | CONFIGURABLE_VERIFIED (tier dependent) | NOT_SUPPORTED (only last-password controls documented) |
| Minimum password age 1 day | NEEDS_VERIFICATION | NEEDS_VERIFICATION | NEEDS_VERIFICATION |
| Maximum password age 365 days | NEEDS_VERIFICATION | NOT_SUPPORTED for local passwords | CONFIGURABLE_VERIFIED, tenant policy required |
| Mandatory MFA | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED |
| Lockout ≤10 failed attempts | CONFIGURABLE_VERIFIED (default 10 on new instances) | NATIVE_VERIFIED (lockout begins after 5) | NATIVE_VERIFIED (default 10) |
| Session/token revocation | CONFIGURABLE_VERIFIED | NATIVE_VERIFIED on disable/revoke | EXTERNAL_CONTROL_REQUIRED (token revocation limitations) |
| User disablement/deletion | CONFIGURABLE_VERIFIED | NATIVE_VERIFIED | CONFIGURABLE_VERIFIED |
| Quarterly access-review evidence | EXTERNAL_CONTROL_REQUIRED | EXTERNAL_CONTROL_REQUIRED | EXTERNAL_CONTROL_REQUIRED |
| Backend roles/permissions/claims | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED | CONFIGURABLE_VERIFIED |

Sources verified 2026-08-17: [Clerk lockout](https://clerk.com/docs/guides/secure/user-lockout),
[Cognito password policy](https://docs.aws.amazon.com/cognito/latest/developerguide/managing-users-passwords.html),
[Cognito account disablement/revocation](https://docs.aws.amazon.com/cognito/latest/developerguide/how-to-manage-user-accounts.html),
[Entra password policy](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-sspr-policy),
and [Entra MFA](https://learn.microsoft.com/en-us/entra/identity/authentication/concept-mfa-howitworks).

No candidate satisfies the complete human-account baseline without unresolved
gaps or external controls. No IdP is selected and no password store or custom
authentication is proposed.

## 17. Control-ownership reevaluation and candidate recommendation (2026-08-17)

Section 16 above used a "does the IdP have a native feature for every item"
methodology, which the user directed not to repeat: Amazon requires controls
over the security system, not necessarily IdP-native features for each one.
The full ownership-based reevaluation — a 25-control ownership matrix
(`IDP_NATIVE_REQUIRED` / `IDP_OR_MANAGED_AUTH_REQUIRED` / `BACKEND_ENFORCED` /
`ORGANIZATIONAL_PROCEDURAL` / `INFRASTRUCTURE_CONTROL` /
`SERVICE_CREDENTIAL_CONTROL` / `MULTI_LAYER`), the derived 11-item HARD IdP
requirement set, the passwordless/federated-identity finding, and the final
per-provider re-evaluation — is maintained in
[`ADR-021`](../adr/ADR-021-identity-provider-authentication-boundary.md)
§"Control ownership reevaluation (2026-08-17)" so the analysis is not
duplicated across two documents.

Outcome summary (full detail in ADR-021):

- Only 11 of 25 controls are `IDP_NATIVE_REQUIRED`/HARD (the complete
  password-composition set, MFA, and lockout). The other 14 are legitimately
  owned by FastAPI, organizational procedure, infrastructure, or
  service-credential lifecycle — none of them require an IdP feature.
- Microsoft Entra External ID is **eliminated**: two HARD requirements
  (12-character minimum, password history 10) have a confirmed native
  ceiling, and its passkey flow does not remove the underlying weak-password
  floor (it still requires a password account to bootstrap).
- Clerk remains **unresolved**: no confirmed ceiling, but six of eleven HARD
  requirements lack a published, tenant-specific setting; closing this
  requires a real test-tenant configuration export, not performed here.
- Amazon Cognito is the **best-positioned candidate**: ten of eleven HARD
  requirements are `CONFIGURABLE_VERIFIED`/`NATIVE_VERIFIED` against official
  AWS documentation; the remaining gap (no native automatic expiration for a
  user's own permanent password) has an officially-documented, provider-native
  closing mechanism (a scheduled call to Cognito's `AdminResetUserPassword`
  admin API) rather than a custom-built password engine, though whether that
  repurposed use satisfies Amazon's 365-day intent is itself
  `NEEDS_VERIFICATION`.
- Passwordless/federated identity does **not** eliminate Amazon's password
  controls on current evidence — Amazon's official guidance states them as
  flat requirements for "all accounts" with no passwordless exemption found
  in either official page checked. `NEEDS_VERIFICATION`, not assumed.

`RECOMMENDED IdP (candidate, not selected): Amazon Cognito.`

This is a recommendation, not a decision: ADR-021 stays `Estado: Propuesta`
and its `Decision` line reads "candidate, not accepted." No account, tenant,
credential, or code was created by this reevaluation.

`IDENTITY SECURITY GATE = BLOCKED` (implementation and evidence — including
closing the remaining `NEEDS_VERIFICATION` items and confirming the scheduled
Cognito reset satisfies Amazon's intent — are still required).
`REAPPLICATION GATE = BLOCKED` (unchanged; RF-01–RF-05 remain
`NOT_IMPLEMENTED` per §§1–2 above regardless of the identity-provider
recommendation).

## 18. Cognito maximum-password-age gap — focused verification (2026-08-17)

Scope: only the single previously-flagged Cognito gap (maximum password age
/ expiration ≤365 days). Full detail, including the `PASSWORD_MAX_AGE_CONTROL`
design and the verbatim `AdminResetUserPassword` behavior analysis, is
maintained in [`ADR-021`](../adr/ADR-021-identity-provider-authentication-boundary.md)
§"PASSWORD_MAX_AGE_CONTROL design" so it is not duplicated here.

**Outcome**: Cognito does **not** natively expire a local user's own
permanent password ("Passwords for local users in Amazon Cognito user pools
don't automatically expire" — official AWS documentation, verified
2026-08-17). AWS's own documentation names the closing pattern: log password
age externally, then use a scheduled trigger calling `AdminResetUserPassword`
(paired with `AdminUserGlobalSignOut`, since the reset alone does not revoke
already-issued sessions — confirmed via official `AdminUserGlobalSignOut`
documentation) to force a reset before the 365-day boundary. This is an
AWS-documented pattern, not a JUVAl-invented workaround, does not store or
know any password, and keeps Cognito as the sole authentication source of
truth. Classified **B — MANAGED_CONTROL_VERIFIED**.

**This does not close ADR-021.** The same focused reread of Cognito's
complete official password-policy page (necessary to confirm the max-age
finding) showed the page is exhaustive about every configurable
password-policy control — which means two other HARD requirements previously
marked `NEEDS_VERIFICATION` for Cognito (minimum password age of 1 day;
username/name exclusion from the password) have no documented setting
anywhere on that page. They are reclassified `NOT_SUPPORTED` in ADR-021 as of
this session. Neither was in scope for this task and neither has a proposed
resolution yet.

`RECOMMENDED IdP (candidate, still best-positioned, not selected): Amazon Cognito.`
`ADR-021 = NOT YET READY FOR USER APPROVAL` — two newly-identified native
gaps (minimum password age, name/username exclusion) require the same kind
of focused investigation just completed for maximum age.
`IDENTITY SECURITY GATE = BLOCKED.`
`REAPPLICATION GATE = BLOCKED.`
No Amazon clarification question was identified or sent — the maximum-age
wording states an outcome, not a mandated mechanism, and no normative
ambiguity blocks determining whether Cognito's mechanism satisfies it.

## 19. Cognito minimum-age and name-exclusion gaps — resolved, Cognito rejected (2026-08-17)

Scope, as directed: only the two gaps named §18 left open (minimum password
age 1 day; password must not contain username/name). Full detail — the exact
Amazon wording per gap, the AWS Lambda-trigger flow-coverage table, the
bypass analysis across every password-setting API, and the classification
rationale — is maintained in
[`ADR-021`](../adr/ADR-021-identity-provider-authentication-boundary.md)
§"Final two-gap investigation and Cognito rejection (2026-08-17)".

**Outcome, decisive for both gaps**: AWS's own exhaustive official
documentation — the complete API-operation-to-Lambda-trigger mapping table —
proves that Cognito's `ChangePassword` operation (the standard,
always-available, self-service "I know my current password, here is my new
one" call) has **no Lambda trigger of any kind**, and that the one trigger
positioned early enough to inspect a new password before it is stored
(`PreSignUp`) is proven, by AWS's own worked before/after example, to
**never receive the plaintext password** in its event payload. Neither gap
has a native, managed, or safely-designed procedural control that covers
every applicable flow without either exposing a password outside Cognito's
boundary (explicitly ruled out) or being trivially bypassable by a direct
API call to `ChangePassword` (explicitly ruled out).

- **GAP A (minimum age 1 day)**: `E — NOT_SUPPORTED`. Only a post-hoc,
  detect-and-remediate design is technically possible, and it does not
  prevent the violation — it can only react after the too-early change has
  already succeeded, which does not meet the "must not be evadable by
  calling the API directly" bar.
- **GAP B (name/username exclusion)**: `E — NOT_SUPPORTED`. No mechanism, of
  any kind, ever sees the plaintext password — this is the clearer of the
  two gaps and admits no compensating design at all without building
  forbidden custom authentication or exposing passwords outside the IdP
  boundary.

Per the decision rule set for this investigation, either gap landing on `E`
disqualifies Cognito. Both did.

`COGNITO HARD REQUIREMENTS = NOT SATISFIED`
`AMAZON COGNITO = REJECTED FOR CURRENT AMAZON BASELINE`
`ADR-021 = PENDING NEW ARCHITECTURAL DECISION`

Combined with the already-standing conclusions on the other two candidates
(Entra External ID eliminated on two confirmed native ceilings; Clerk
unresolved with zero confirmed passes on any HARD requirement in a real
tenant), **no candidate currently has a verified, evidence-backed path to
satisfying the full HARD IdP requirement set.** This is a decision point for
the user, not a further research task to run unprompted: possible paths
include a scoped Amazon clarification on whether GAP A's outcome-based
wording tolerates a detect-and-remedy model (identified in ADR-021, not
sent), accepting documented residual risk with compensating organizational
controls for GAP A while treating GAP B as an unmitigated blocker, or
directing research into providers not yet evaluated. None is chosen here.

`RECOMMENDED IdP: NONE — no candidate currently satisfies the full HARD IdP
requirement set under verified evidence.`
`IDENTITY SECURITY GATE = BLOCKED.`
`REAPPLICATION GATE = BLOCKED.`

## 20. Remediation execution status (2026-08-18)

This section supersedes the per-finding `CURRENT_JUVAL_STATE` column of §2 for
every item it names. §§1–19 are preserved as the historical record.

Compliance states used: `COMPLIANT` (identified + implemented + validated +
evidenced), `PARTIAL`, `NOT_IMPLEMENTED`, `BLOCKED`, `NEEDS_VERIFICATION`.
Documentation alone is never `COMPLIANT`.

### 20.1 Finding status

| Finding | Was | Now | Implemented | Tested | Evidenced | Blocking gap |
|---|---|---|---|---|---|---|
| **RF-01** | `NOT_IMPLEMENTED` | **PARTIAL** | Yes — [`INCIDENT_RESPONSE_PLAN.md`](INCIDENT_RESPONSE_PLAN.md) §5 defines the 24-hour `security@amazon.com` procedure, the detection clock, the Amazon Information determination and evidence preservation | Structure verified mechanically by `tools/compliance_check.py` (15 tests) | **NO** | Roles unnamed; plan unapproved; no tabletop exercise run (§12 A-1…A-5) |
| **RF-02** | `NOT_IMPLEMENTED` | **PARTIAL** | Workstation controls verified; cloud controls not deployed — [`NETWORK_SECURITY.md`](NETWORK_SECURITY.md) | Workstation measured 2026-08-18 | Partially — workstation only | **Backend is not deployed**, so there is no system to evidence. Plus finding F-01 (host ~9 months unpatched, OS past end-of-support) |
| **RF-03** | `NOT_IMPLEMENTED` | **PARTIAL** | Backend half implemented (OIDC validation, `interfaces/api/auth.py`); IdP half designed and provider identified (ADR-022) | Yes — 33 negative security tests | Backend only | No IdP tenant. Okta requires a $1,500/year contract (**commercial approval**) |
| **RF-04** | `NOT_IMPLEMENTED` | **PARTIAL** | Yes — least-privilege RBAC enforced server-side on every endpoint; [`ACCESS_CONTROL.md`](ACCESS_CONTROL.md) | Yes — positive, negative, and direct-API-bypass tests | Technical half only | No users exist to govern; quarterly review never run; Supabase RLS policies absent |
| **RF-05** | `NOT_IMPLEMENTED` | **PARTIAL** | Yes — roles, six-month review cadence, tabletop process and templates | Review currency checked mechanically | **NO** | Same as RF-01: unapproved, unexercised |

**No finding is `COMPLIANT`.** Every one advanced from `NOT_IMPLEMENTED` to
`PARTIAL`; none can close on documentation and code alone.

### 20.2 What was actually built

| Artifact | Purpose | Validation |
|---|---|---|
| `src/juval/interfaces/api/auth.py` | Provider-agnostic OIDC/JWT verification and capability-based RBAC | 33 tests |
| `interfaces/api/main.py` | Permission enforced on all five routes, server-side | `compliance_check.py::check_auth_posture` |
| `docs/adr/ADR-022` | Okta selected as the only candidate satisfying all 11 HARD IdP requirements | Verbatim primary-source citations |
| `docs/compliance/INCIDENT_RESPONSE_PLAN.md` | RF-01/RF-05 operational runbook | 15 tests |
| `docs/compliance/SECRETS.md` | Credential classes, rotation, redaction, access boundaries | Secret scan + redaction tests |
| `docs/compliance/NETWORK_SECURITY.md` | RF-02 audit with measured workstation values | Reproducible PowerShell commands |
| `docs/compliance/ACCESS_CONTROL.md` | RF-04 organizational half | Cross-referenced to the test suite |
| `tools/compliance_check.py` | Mechanical verification: plan completeness, review currency, auth posture, dependency CVEs, secret scan | Self-tested (proves it detects failure) |
| `docs/compliance/templates/` | Incident, tabletop and access-review records | — |

Test suite: **303 passed, 3 skipped** (`SKIPPED_EXPECTED` — Supabase tests
requiring a live database). `pip-audit`: no known vulnerabilities.

### 20.3 The identity blocker is resolved, technically

ADR-021 concluded `RECOMMENDED IdP = NONE`. That conclusion stood on a survey
of three **CIAM** products (Cognito, Entra External ID, Clerk), none of which
offers minimum password age or name-exclusion — controls that are standard in
**workforce** IAM. Re-framing the search resolved it:

`GAP A (minimum password age 1 day)` — Okta: "Minimum password age is N units
… up to 9,999 minutes" → 1,440 minutes. **`A — NATIVE_VERIFIED`.**

`GAP B (password must not contain username/name)` — Okta: "Does not contain
part of username" / "Does not contain first name" / "Does not contain last
name". **`A — NATIVE_VERIFIED`.**

All 11 HARD requirements are natively configurable. No managed control,
scheduled job, or plaintext-password inspection is required — unlike the
`PASSWORD_MAX_AGE_CONTROL` design Cognito would have needed.

`AMAZON COGNITO = REJECTED` (unchanged)
`RECOMMENDED IdP = OKTA WORKFORCE IDENTITY`
`ADR-022 = PROPOSED / PENDING COMMERCIAL APPROVAL`

### 20.4 Gates

`IDENTITY SECURITY GATE = BLOCKED`
— technical design complete and the backend half implemented and tested, but
no tenant exists, no policy is applied, and no configuration evidence has been
exported. Opens when: ADR-022 is approved and paid for, the tenant is
configured to Amazon's exact values, MFA is enforced, and the password-policy
export is filed.

`REAPPLICATION GATE = BLOCKED`
— RF-01 through RF-05 are all `PARTIAL`. Reapplying now would require
answering the Developer Profile with the same unevidenced "YES" that produced
the original rejection.

`AMAZON_COMPLIANCE_READINESS = NOT_READY`

### 20.5 Ordered external actions

Everything technically executable without an external account has been done.
The remaining path is gated on user actions, in dependency order:

| # | Action | Unblocks | Cost |
|---|---|---|---|
| **E-1** | Approve ADR-022 and purchase Okta Workforce Identity | RF-03, RF-04 | $1,500/yr minimum |
| **E-2** | Configure the tenant to Amazon's values (12 chars, all four character classes, name exclusion, history 10, min age 1 day, max age 365 days, MFA all accounts, lockout ≤10) and export the policy as evidence | RF-03 | — |
| **E-3** | Name the Incident Commander, Security Owner, IMPOC and Deputy; approve the incident response plan | RF-01, RF-05 | — |
| **E-4** | Run the first tabletop exercise and file the record (**never send a test mail to `security@amazon.com`**) | RF-05 | — |
| **E-5** | Resolve `NETWORK_SECURITY.md` F-01: patch the workstation and move to a supported OS, or formally exclude it from the boundary | RF-02 | — |
| **E-6** | `railway login` and deploy the backend with `JUVAL_AUTH_MODE=oidc` and `JUVAL_EXECUTION_STORE=supabase` | RF-02, RF-03, RF-04 | Hosting |
| **E-7** | After E-6: apply and negatively test Supabase RLS policies; verify TLS; capture provider configuration evidence | RF-02, RF-04 | — |
| **E-8** | Run the first quarterly access review and one ≤24-hour removal drill | RF-04 | — |
| **E-9** | Only then: update the Developer Profile truthfully and open a **new** case (never reopen the prior one) | Reapplication | — |

E-1, E-3 and E-5 are independent and can proceed in parallel. E-6 gates E-7.
E-9 gates on everything above reaching `COMPLIANT`.
