# JUVAl — Amazon SP-API Compliance & Policy Baseline

**Status:** APPROVED BASELINE — documentation only. This baseline approves no
credential, integration, queue, infrastructure, role, client or live call.

**Purpose:** Compliance master for what JUVAl may and must do with Amazon
access and Amazon Information. DATA_ACQUISITION_MATRIX answers where sourcing
data comes from and is not duplicated here.

**Verification date:** 2026-08-17. Normative hierarchy is: (1) Solution
Provider Agreement, (2) Data Protection Policy (DPP), (3) Acceptable Use
Policy (AUP). Official guidance and operational documentation are secondary;
they never modify or override the Agreement, DPP or AUP.

## 1. Evidence-bound onboarding state

| Fact | State | Evidence |
| --- | --- | --- |
| Developer type / intended use | PRIVATE DEVELOPER; INTERNAL / OWN ORGANIZATION / OWN SELLER ACCOUNT | DATA_ACQUISITION_MATRIX §17 |
| Developer registration | REJECTED_REMEDIATION_REQUIRED — NOT ELIGIBLE FOR SP-API ACCESS; reapplication requires an updated Developer Profile and a new case | Amazon decision communicated 2026-08-17; no case ID retained |
| Production application client | NOT CREATED | Same |
| Self-authorization | NOT PERFORMED | Same |
| Credentials | NOT AVAILABLE | No credential was requested, read or used |
| Live SP-API calls | NOT PERFORMED; Catalog validation blocked pending remediation, reapplication and approval | DATA_ACQUISITION_MATRIX §§13, 17; compliance/SP_API_REGISTRATION_REMEDIATION.md |

## 2. Source register

All URLs were opened and verified on 2026-08-17. A displayed update date is
not a contract version. English US policy text prevails where Amazon publishes
translations.

| ID | Official title / URL | Authority type | Version/date exposed | Scope / precedence |
| --- | --- | --- | --- | --- |
| S1 | [Amazon Solution Provider Portal Agreement](https://sellercentral.amazon.com/solution-provider/agreement?locale=en_US) | NORMATIVE_POLICY | Version November 2025 | Binding; Agreement controls a conflict with Policies/underlying terms. |
| S2 | [Data Protection Policy](https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US) | NORMATIVE_POLICY | No fixed version displayed | General requirements concern Information; §2 is headed Additional Security Requirements Specific to PII. |
| S3 | [Acceptable Use Policy](https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US) | NORMATIVE_POLICY | No fixed version displayed | Acceptable API use, data minimization, sharing and throttling. |
| S4 | [Policies and Agreements](https://developer-docs.amazon.com/sp-api/docs/policies-and-agreements) | OPERATIONAL_DOCUMENTATION | Living index | Official policy index; English prevails. |
| S5 | [Prepare for Registration](https://developer-docs.amazon.com/sp-api/docs/onboarding-step-1-prepare-for-registration) | ONBOARDING_REQUIREMENT | Updated 5 days before verification | Developer type and role planning. |
| S6 | [Create a Developer Profile](https://developer-docs.amazon.com/sp-api/docs/onboarding-step-3-create-a-developer-profile) | ONBOARDING_REQUIREMENT | Updated 4 months before verification | Profile review and security questionnaire. |
| S7 | [Role Mappings for SP-API Operations](https://developer-docs.amazon.com/sp-api/docs/role-mappings) | OPERATIONAL_DOCUMENTATION | Living documentation | Operation-to-role mapping; recheck before each request. |
| S8 | [Authorize Private Applications](https://developer-docs.amazon.com/sp-api/docs/self-authorization) | OPERATIONAL_DOCUMENTATION | Updated 2 days before verification | Private self-authorization and token-handling practices. |
| S9 | [Key Security Control Guidance](https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration) | OFFICIAL_IMPLEMENTATION_GUIDANCE | Updated 11 days before verification | Guidance expressly states governing agreements control. |
| S10 | [Vulnerability Management](https://developer-docs.amazon.com/sp-api/docs/vulnerability-management) | OFFICIAL_IMPLEMENTATION_GUIDANCE | Living guidance | Guidance for DPP implementation. |
| S11 | [Changes to the Acceptable Use Policy](https://developer-docs.amazon.com/sp-api/changelog/changes-to-the-acceptable-use-policy) | OPERATIONAL_DOCUMENTATION | 2023-06-20 | Change notice; current S3 controls. |

## 2a. Amazon registration findings (reviewer event, 2026-08-17)

The reviewer decision is recorded separately from policy interpretation.
`AMAZON_REJECTION_FINDING` is not, by itself, a universal normative rule;
where public policy does not expose the same specificity, the traceability
state is `REVIEWER_REQUIREMENT / POLICY TRACEABILITY NEEDS VERIFICATION`.

| Finding ID | AMAZON_REJECTION_FINDING | Related AC | Policy traceability / authority | Scope | JUVAl state and evidence | Gap / required evidence | Blocks reapplication |
|---|---|---|---|---|---|---|---|
| RF-01 | Report incidents involving Amazon Information to `security@amazon.com` within 24 hours of detection. | AC-12 | DPP §1.6; S2; NORMATIVE_POLICY / AMAZON_MANDATORY for Security Incidents. Reviewer-specific address is also an onboarding/reviewer requirement pending exact public-policy trace. | Information / incident-dependent | NOT_IMPLEMENTED; no incident plan, IMPOC, notification runbook or exercise. | Approved plan, named role, clock, evidence preservation and notification procedure. | YES |
| RF-02 | Maintain firewall, IDS/IPS, antivirus/anti-malware and network segmentation. | AC-06 | DPP §1.1; S2; NORMATIVE_POLICY / AMAZON_MANDATORY. | Systems handling Information | NOT_IMPLEMENTED; no deployed topology or provider control evidence. | Network diagram, provider configuration and control-validation records. | YES |
| RF-03 | Password/access controls: 12-character minimum, special characters, MFA, 365-day expiration and annual rotation. | AC-07, AC-08 | DPP §§1.2–1.4.2; S2; NORMATIVE_POLICY / AMAZON_MANDATORY for the stated account/credential scope. | User and programmatic credentials; exact reviewer scope remains to be reconciled. | NOT_IMPLEMENTED; API has no application auth; no MFA/password/access lifecycle evidence; no SP-API credential. | Identity policy/configuration, MFA proof, rotation/revocation records and access review. | YES |
| RF-04 | Restrict access to Amazon Information by job duties/business functions. | AC-07, AC-14A | DPP §§1.2–1.3 and AUP §§4.6–4.9; S2/S3; NORMATIVE_POLICY / AMAZON_MANDATORY. | Personnel and service accounts with Information access | NOT_IMPLEMENTED; no roles, access review, RLS evidence or production identity lifecycle. | Role matrix, least-privilege grants, quarterly review and revocation evidence. | YES |
| RF-05 | Incident-response plan must define roles, be reviewed every six months, and contain 24-hour notification procedures. | AC-12 | DPP §1.6; S2; NORMATIVE_POLICY / AMAZON_MANDATORY for plan/review/notification. | Security incidents involving Information | NOT_IMPLEMENTED; no plan, accountable roles, six-month review record or exercise. | Approved plan, six-month review schedule, notification drill and preserved evidence. | YES |

The complete remediation matrix and reapplication gate are maintained in
[`SP_API_REGISTRATION_REMEDIATION.md`](SP_API_REGISTRATION_REMEDIATION.md).

## 3. Traceability contract and control matrix

Status values: COMPLIANT, PARTIAL, NOT_IMPLEMENTED, NOT_APPLICABLE, BLOCKED,
NEEDS_VERIFICATION, DECLARED_YES_EVIDENCE_INCOMPLETE. No control is COMPLIANT
without operating evidence.

| ID | Requirement | Authority type / origin | Official source title, section, source reference, verified | Scope / level | Current evidence / status | Gap, remediation, validation |
| --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Use API only for acceptable activities, authorized users and data necessary to functionality. | NORMATIVE_POLICY / AMAZON_MANDATORY | Acceptable Use Policy §§1.1, 3.8; S3; 2026-08-17 | All Information / MUST | Own-account intent; no adapter/call. BLOCKED | Amazon approval and operation-purpose/minimum-data inventory. Validate before each scope change. |
| AC-02 | Keep Portal Registration Data accurate/current and notify Amazon immediately if Portal credentials are compromised. | NORMATIVE_POLICY / AMAZON_MANDATORY | Agreement §1; S1; 2026-08-17 | Portal registration / MUST | Registration rejected with remediation required; no accountable owner/runbook. PARTIAL | Assign owner and update/compromise process. Quarterly and event-driven evidence. |
| AC-03 | Request and qualify only roles aligned with intended operations. Do not infer unrestricted scope from Product Listing alone. | ONBOARDING_REQUIREMENT / AMAZON_ONBOARDING | Prepare for Registration, roles; Role Mappings; S5/S7; 2026-08-17 | Roles and returned payload / CONDITIONAL | Product Listing is documented planning target; no role/client/payload. NEEDS_VERIFICATION | GATE 3 current operation/role/payload review, including PII/restricted determination. |
| AC-04A | A private application must be self-authorized before calls for the organization account. | OPERATIONAL_DOCUMENTATION / AMAZON_ONBOARDING | Authorize Private Applications, self-authorization workflow; S8; 2026-08-17 | Private app after client exists / CONDITIONAL | No client or authorization. BLOCKED | Perform only after Amazon approval and client creation. Validate Portal authorization evidence. |
| AC-04B | Store tokens securely; do not put them in client code, logs or URLs; restrict access. | OFFICIAL_IMPLEMENTATION_GUIDANCE / AMAZON_GUIDANCE | Authorize Private Applications, Token storage details; S8; 2026-08-17 | Tokens after issuance / SHOULD | .env is ignored; no SP-API token exists; no secret manager. PARTIAL | Backend-only encrypted store and redaction/access controls. Validate no browser/log exposure. |
| AC-04C | Maintain token rotation and revocation process. | OFFICIAL_IMPLEMENTATION_GUIDANCE / AMAZON_GUIDANCE | Authorize Private Applications, Token storage details; S8; 2026-08-17 | Tokens after issuance / SHOULD | No token/process. NOT_IMPLEMENTED | Document rotation/revocation runbook. Test revocation drill. |
| AC-05 | Encrypt Information in transit with TLS 1.2+ over public/network boundaries. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §1.5; S2; 2026-08-17 | All Information / MUST | Railway deployment/TLS evidence absent. NOT_IMPLEMENTED | Verify HTTPS termination and DB transport before production. Probe/config evidence. |
| AC-06 | Use defense-in-depth network controls, including firewall/ACL, segmentation, IDS/IPS, WAF/equivalent on public endpoints, and document them. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §1.1; S2; 2026-08-17 | All Information / MUST | No deployed topology/control evidence. NOT_IMPLEMENTED | Provider-backed architecture and controls assessment. Review before production and material change. |
| AC-07 | Unique identities, MFA, least privilege, quarterly access review, and access removal within 24 hours after termination/role change. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §§1.2–1.4; S2; 2026-08-17 | All Information / MUST | Current API lacks application auth; RLS no policies. NOT_IMPLEMENTED | Access lifecycle, MFA, service ownership/revocation. Quarterly evidence and termination drill. |
| AC-08 | Encrypt programmatic credentials at rest, limit to authorized personnel, rotate at least each 12 months or on compromise; do not hardcode/publicly expose sensitive credentials. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §§1.4.2, 2.5; S2; 2026-08-17 | Credentials; §2.5 PII context / MUST for §1.4.2 | .env ignored; blank template; worktree scan passed; no SP-API secret. PARTIAL | Implement backend secret storage and rotation/access process. KMS is not claimed as a general mandatory control here. |
| AC-09 | Securely delete Information within 30 days of Amazon notice, authorization/access ending or participation ending; retain only as necessary. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §1.7; S2; 2026-08-17 | All Information / MUST | Temporary upload is deleted; no Amazon-data lifecycle/cache/backup deletion design. PARTIAL | Inventory, deletion propagation/certification process. Validate revocation deletion. |
| AC-10A | Attribute/tag origin of Amazon Information. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §1.8; S2; 2026-08-17 | All Information / MUST | Provenance/source separation exists; no storage-level lifecycle tag. PARTIAL | Data inventory/storage tag and access evidence. |
| AC-10B | Retain PII no longer than 30 days after delivery unless law requires longer. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §2.1; S2; 2026-08-17 | Amazon PII / CONDITIONAL | No intended PII operation; role/payload unverified. NEEDS_VERIFICATION | Classify selected operations; if PII, implement TTL/deletion. |
| AC-10C | Limit non-PII retention to 18 months unless law requires longer. | OFFICIAL_IMPLEMENTATION_GUIDANCE / AMAZON_GUIDANCE | Key Security Control Guidance, Data retention processes; S9; 2026-08-17 | Amazon non-PII / SHOULD | No live Amazon data or retention implementation. NOT_IMPLEMENTED | Adopt only after accountable policy decision; do not describe as DPP MUST. |
| AC-11A | Gather/review/protect security logs; retain them 12 months; the cited requirements are in DPP §2.6. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §2.6.1; S2; 2026-08-17 | DPP §2 PII context; wording also says Information / CONDITIONAL | Only exception method/path logging; no centralized audit logs/redaction/retention. NEEDS_VERIFICATION | Obtain documented applicability decision for non-PII; implement if PII/restricted or otherwise required. |
| AC-11B | Centralize logging, monitor alarms and review logs real-time or bi-weekly. | OFFICIAL_IMPLEMENTATION_GUIDANCE / AMAZON_GUIDANCE | Key Security Control Guidance, Monitoring and incident response; S9; 2026-08-17 | Systems handling Amazon data / SHOULD | No such controls. NOT_IMPLEMENTED | Future logging design; no claim it changes DPP scope. |
| AC-12 | Maintain risk/incident plan, IMPOC and investigation evidence; notify Amazon within 24 hours of detecting a Security Incident. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §1.6; S2; 2026-08-17 | All Information / MUST | No plan, IMPOC, exercise or evidence chain. NOT_IMPLEMENTED | Management-approved plan and six-month/post-change review. Test exercise. |
| AC-13A | Maintain vulnerability plan, scans at least every 30 days and after significant change, pre-release code scans, pen tests every 365 days, critical remediation 7 days/high 30 days. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §§2.7.1–2.7.3; S2; 2026-08-17 | DPP §2 heading is PII; text says systems handling Amazon data including PII / CONDITIONAL | No program/scans/pen test/SLA. NEEDS_VERIFICATION | Resolve DPP §2 applicability before live non-PII use; implement whenever applicable. |
| AC-13B | Test backup/recovery quarterly and maintain geographically separated recovery capability. | OFFICIAL_IMPLEMENTATION_GUIDANCE / AMAZON_GUIDANCE | Key Security Control Guidance, operational requirements; S9; 2026-08-17 | Guidance; PII/recovery context / SHOULD | No evidence. NOT_IMPLEMENTED | Future recovery plan/test; do not present cadence as universal DPP policy. |
| AC-14A | Before sharing Information, perform data-security due diligence and use parties with standards at least as strict as JUVAl. | NORMATIVE_POLICY / AMAZON_MANDATORY | Acceptable Use Policy §§4.6–4.9; S3; 2026-08-17 | Information shared outside authorized activity / MUST | No live sharing; processors unassessed. NEEDS_VERIFICATION | Assess provider only before it receives/accesses Amazon Information. |
| AC-14B | Conduct annual vendor/subcontractor assessment before granting Amazon-data access. | NORMATIVE_POLICY / AMAZON_MANDATORY | Data Protection Policy §2.8; S2; 2026-08-17 | DPP §2 PII context / CONDITIONAL | No third-party assessment. NEEDS_VERIFICATION | Apply if scope determination requires §2; do not call annual universal. |
| AC-15 | Notify SP-API Support within 30 days of organizational changes affecting Information use and maintain a written policy; disclose affiliates when seeking added roles. | NORMATIVE_POLICY / AMAZON_MANDATORY | Acceptable Use Policy §§3.11–3.12; S3; 2026-08-17 | All Information/role request / MUST | No policy or affiliate register. NOT_IMPLEMENTED | Governance register/workflow. Validate event-driven review. |
| AC-16 | Respect per-Authorized-User throttling and never bypass quotas through multiple accounts/apps. | NORMATIVE_POLICY / AMAZON_MANDATORY | Acceptable Use Policy §§2.9, 3.10; S3; 2026-08-17 | Future calls / MUST | Acquisition matrix mandates operation/provider policy; no adapter/queue. PARTIAL | Future design/test per operation/provider and no bypass. |
| AC-17 | Be clear about data/purpose, calculations/AI/freshness, and validate materially impactful analytical processing. | NORMATIVE_POLICY / AMAZON_MANDATORY | Acceptable Use Policy §§2.2–2.4, 2.10; S3; 2026-08-17 | Operator-facing feature / MUST | Provenance/AI limits documented; no Amazon-facing feature. PARTIAL | Disclosure and status-presentation review before feature. |
| AC-18 | Do not improperly disclose/aggregate Information or use it for prohibited customer marketing, Amazon business insights or external data services. | NORMATIVE_POLICY / AMAZON_MANDATORY | Acceptable Use Policy §§4.1–4.9; S3; 2026-08-17 | Information/PII by subsection / MUST | No live Amazon data; no enforced sharing control. PARTIAL | Permitted-use/sharing register and access/export tests. |
| AC-19 | Determine whether selected roles/operations expose restricted data or PII before use. | OPERATIONAL_DOCUMENTATION / AMAZON_ONBOARDING | Prepare for Registration; Role Mappings; S5/S7; 2026-08-17 | Role/payload selection / CONDITIONAL | No role/client/live payload. NEEDS_VERIFICATION | GATE 3 evidence; PII-only controls can be NOT_APPLICABLE only after evidence. |
| AC-20 | API/auth/429/5xx/timeout/schema failure is not NOT_FOUND; preserve ambiguity separately. | JUVAL_ARCHITECTURAL_CONTROL / JUVAL_ARCHITECTURAL | JUVAl DATA_ACQUISITION_MATRIX §§8, 10, 17; AUP §2.9 is rationale only; 2026-08-17 | JUVAl adapter semantics / INTERNAL | Existing documented rule; no adapter. PARTIAL | Future adapter tests for failure classes and ambiguity. This is not stated as an Amazon mandatory rule. |

### 3a. Direct control source URLs

The source reference in every control above resolves to this direct official
source table; this keeps the matrix readable while preserving a per-control
title, section, URL and verification date.

| Control IDs | Official source title / section | Direct source URL | Verified date |
| --- | --- | --- | --- |
| AC-01 | Acceptable Use Policy §§1.1, 3.8 | https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US | 2026-08-17 |
| AC-02 | Amazon Solution Provider Portal Agreement §1 | https://sellercentral.amazon.com/solution-provider/agreement?locale=en_US | 2026-08-17 |
| AC-03 | Prepare for Registration; Role Mappings | https://developer-docs.amazon.com/sp-api/docs/onboarding-step-1-prepare-for-registration ; https://developer-docs.amazon.com/sp-api/docs/role-mappings | 2026-08-17 |
| AC-04A | Authorize Private Applications, self-authorization workflow | https://developer-docs.amazon.com/sp-api/docs/self-authorization | 2026-08-17 |
| AC-04B | Authorize Private Applications, Token storage details | https://developer-docs.amazon.com/sp-api/docs/self-authorization | 2026-08-17 |
| AC-04C | Authorize Private Applications, Token storage details | https://developer-docs.amazon.com/sp-api/docs/self-authorization | 2026-08-17 |
| AC-05 | Data Protection Policy §1.5 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-06 | Data Protection Policy §1.1 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-07 | Data Protection Policy §§1.2–1.4 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-08 | Data Protection Policy §§1.4.2, 2.5 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-09 | Data Protection Policy §1.7 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-10A | Data Protection Policy §1.8 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-10B | Data Protection Policy §2.1 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-10C | Key Security Control Guidance, Data retention processes | https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration | 2026-08-17 |
| AC-11A | Data Protection Policy §2.6.1 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-11B | Key Security Control Guidance, Monitoring and incident response | https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration | 2026-08-17 |
| AC-12 | Data Protection Policy §1.6 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-13A | Data Protection Policy §§2.7.1–2.7.3 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-13B | Key Security Control Guidance, operational requirements | https://developer-docs.amazon.com/sp-api/docs/guidance-to-address-key-security-controls-in-sp-api-integration | 2026-08-17 |
| AC-14A | Acceptable Use Policy §§4.6–4.9 | https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US | 2026-08-17 |
| AC-14B | Data Protection Policy §2.8 | https://sellercentral.amazon.com/solution-provider/policy?policyType=DPP&locale=en_US | 2026-08-17 |
| AC-15 | Acceptable Use Policy §§3.11–3.12 | https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US | 2026-08-17 |
| AC-16 | Acceptable Use Policy §§2.9, 3.10 | https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US | 2026-08-17 |
| AC-17 | Acceptable Use Policy §§2.2–2.4, 2.10 | https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US | 2026-08-17 |
| AC-18 | Acceptable Use Policy §§4.1–4.9 | https://sellercentral.amazon.com/solution-provider/policy?policyType=AUP&locale=en_US | 2026-08-17 |
| AC-19 | Prepare for Registration; Role Mappings | https://developer-docs.amazon.com/sp-api/docs/onboarding-step-1-prepare-for-registration ; https://developer-docs.amazon.com/sp-api/docs/role-mappings | 2026-08-17 |
| AC-20 | JUVAl DATA_ACQUISITION_MATRIX §§8, 10, 17; AUP §2.9 is rationale only | docs/DATA_ACQUISITION_MATRIX.md | 2026-08-17 |

## 4. Quantitative requirements register

| Requirement | Direct source / authority | Scope | Classification |
| --- | --- | --- | --- |
| Incident notification within 24 hours | DPP §1.6.3, S2 | All Information | NORMATIVE_POLICY / AMAZON_MANDATORY |
| Access removal within 24 hours | DPP §1.2.3, S2 | All Information | NORMATIVE_POLICY / AMAZON_MANDATORY |
| Programmatic credential rotation each 12 months | DPP §1.4.2, S2 | Credentials | NORMATIVE_POLICY / AMAZON_MANDATORY |
| Quarterly access review | DPP §1.2.2, S2 | All Information | NORMATIVE_POLICY / AMAZON_MANDATORY |
| Annual Approved User training | DPP §1.2.4, S2 | All Information | NORMATIVE_POLICY / AMAZON_MANDATORY |
| PII 30-day retention after delivery | DPP §2.1, S2 | PII | NORMATIVE_POLICY / AMAZON_MANDATORY / CONDITIONAL |
| Log retention 12 months; review every 2 weeks | DPP §2.6.1, S2 | DPP §2 PII context | NORMATIVE_POLICY / AMAZON_MANDATORY / CONDITIONAL |
| Monthly/change scans; yearly pen test; 7/30 remediation | DPP §§2.7.1–2.7.3, S2 | DPP §2 scope ambiguity | NORMATIVE_POLICY / AMAZON_MANDATORY / CONDITIONAL |
| Non-PII 18 months; quarterly backup/recovery; annual third-party assessment guidance | S9 operational requirements/data retention | Guidance context | OFFICIAL_IMPLEMENTATION_GUIDANCE / AMAZON_GUIDANCE |

## 5. Data classification

| Category | Source / examples | Sensitivity | Storage allowed | Retention rule | Access / logging rule | Current status |
| --- | --- | --- | --- | --- | --- | --- |
| SUPPLIER_DATA | Supplier Excel, SKU, COG, supplier facts | Business data | Existing controlled stores | Business policy; not Amazon-derived | Least privilege; do not conflate with Amazon fact | IMPLEMENTED |
| AMAZON_NON_PII_INFORMATION | Catalog identity, title, dimensions, rank if returned | Amazon Information | Only after approved lifecycle/processor assessment | DPP §1.7 necessity/deletion; 18 months is guidance | Need-to-know; no unnecessary logging | NOT_IMPLEMENTED |
| AMAZON_PII | Customer/address/contact/order data if a selected operation returns it | High | Only after DPP §2 applicability/control evidence | DPP §2.1 30 days unless law | DPP §2 controls; exclude from logs unless legally needed | NEEDS_VERIFICATION |
| CREDENTIALS_SECRETS | Client secret, refresh/access token, DB credentials | Critical | Backend-only encrypted store after approval | Rotate/revoke per applicable source | Never browser, URL or logs | NOT_AVAILABLE |
| SECURITY_LOGS | Auth/access/error/audit metadata | Sensitive | Protected logging system after design | DPP §2.6 conditional; guidance 12 months | Integrity/access/redaction required | NOT_IMPLEMENTED |
| DERIVED_DATA | Calculated score, trend, aggregates based on Amazon Information | Context dependent | No automatic exemption | NEEDS_VERIFICATION: derived form may retain Amazon-policy obligations | Keep provenance; do not disclose beyond authorized use | NEEDS_VERIFICATION |

## 6. Third-party register

No provider below is deemed compliant or non-compliant. The question is whether
it would process, store or access Amazon Information; all unknowns remain
NEEDS_VERIFICATION.

| Provider | Purpose | Process / store / access Amazon Information? | Contractual review required | Security assessment required | Data processing role | Status / evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Railway | Planned backend hosting | UNKNOWN / UNKNOWN / UNKNOWN | YES if Amazon Information enters it | YES if Amazon Information enters it | NEEDS_VERIFICATION | No deployed topology or assessment |
| Supabase | JUVAl PostgreSQL persistence | UNKNOWN / UNKNOWN / UNKNOWN | YES if Amazon Information enters snapshots | YES if Amazon Information enters it | NEEDS_VERIFICATION | Existing JUVAl persistence does not prove Amazon-data scope |
| Vercel | PWA deployment target | UNKNOWN / UNKNOWN / UNKNOWN | YES if Amazon Information enters it | YES if Amazon Information enters it | NEEDS_VERIFICATION | No Amazon-data design/evaluation |
| GitHub | Source control/CI candidate | UNKNOWN / UNKNOWN / UNKNOWN | YES if secrets/Amazon data could enter it | YES if it receives them | NEEDS_VERIFICATION | No secret/history/CI processor assessment |
| Keepa | Candidate market-history source | UNKNOWN / UNKNOWN / UNKNOWN | YES if data is exchanged/shared | YES if it receives Amazon Information | NEEDS_VERIFICATION | Candidate only; no procurement/integration |

## 7. Developer Registration Assertions

The submitted questionnaire is unavailable. Historical declarations are
preserved; absence of evidence never becomes COMPLIANT.

| Assertion | Declared state | Current evidence | Compliance state | Gap / remediation | Evidence required to close |
| --- | --- | --- | --- | --- | --- |
| Private developer, internal organization | DECLARED YES | User state and onboarding record | NEEDS_VERIFICATION | Keep Portal profile current | Amazon registration approval and Portal record |
| Own seller account only | DECLARED YES | User state and onboarding record | NEEDS_VERIFICATION | No other account scope without review | Self-authorization record for own account |
| Security questionnaire accurately reflected controls | DECLARED YES if answered yes | Questionnaire unavailable; AC-05–AC-15 lack operating evidence | DECLARED_YES_EVIDENCE_INCOMPLETE | Obtain redacted answer/control inventory and reconcile | Dated policies, configs, tests and operating records per answer |
| Backend-only/no VITE secrets | No answer recovered | .gitignore, blank .env.example and current scan | PARTIAL | Automate after credential issuance | CI/history scan and secret-store evidence |

## 8. Future queue/enrichment requirements only

No queue, worker or adapter is approved by this baseline. If later approved, its
architecture must use per-provider and per-operation throttling, observed
rate-limit metadata, 429 backoff, persistent retry state/jobs, idempotency,
resumability, incremental results, audit metadata, and no credentials in job
payloads or logs. AC-20 remains the JUVAl rule for operational error and
NOT_FOUND semantics.

## 9. Amazon Compliance Readiness Gate

Production SP-API remains BLOCKED until: (1) Amazon approves registration;
(2) client, minimum roles and authorization are correctly evidenced; (3) every
applicable AMAZON_MANDATORY MUST is COMPLIANT with evidence; (4) every
DECLARED_YES_EVIDENCE_INCOMPLETE is resolved; (5) relevant processors are
assessed; (6) secret handling, incident response, logging/monitoring,
vulnerability management and lifecycle/deletion are implemented; and (7)
PII-only controls are NOT_APPLICABLE only with documented role/payload
evidence.

## 10. Policy-change process and limitations

Review S1–S11 monthly, before role/client/deployment/scope changes, and after
Amazon notices. Record source update/version, verification date, affected
controls, owner, gap and remediation here. A material change requires review
of this baseline, DATA_ACQUISITION_MATRIX, DATA_SOURCES, SECURITY,
API_CONTRACT and applicable ADRs; create an ADR for a changed security
boundary, retention, persistence or external-source scope.

No direct official-policy conflict was found. A scope ambiguity is preserved:
DPP §2 is headed PII-specific while §§2.6–2.7 use broad wording about
Information/Amazon data. This baseline does not extend those controls to
non-PII automatically; AC-11A and AC-13A remain NEEDS_VERIFICATION.

This is repository/documentation evidence only. No .env contents, credentials,
Portal values, cloud accounts, employee devices, backups or live SP-API calls
were inspected. Existing SECURITY documentation contained historical claims
that are corrected separately only where repository evidence directly
contradicts them.
