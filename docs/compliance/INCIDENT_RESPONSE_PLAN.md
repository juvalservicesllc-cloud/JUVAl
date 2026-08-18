# JUVAl — Security Incident Response Plan

| Field | Value |
|---|---|
| Document ID | `JUVAL-IRP` |
| Version | `0.1.0-DRAFT` |
| Status | **APPROVED** (2026-08-18, §12 A-3). Not yet fully evidenced as an Amazon control — the first tabletop exercise (§12 A-4) has not been run. |
| Effective date | `2026-08-18` |
| Last reviewed | `2026-08-18` |
| Next review due | `2027-02-18` (six months — DPP §1.6, RF-05) |
| Owner | Daniel E. Liendo (Security Owner) |
| Applies to | Every system that processes, stores, transmits or grants access to Amazon Information (see `AMAZON_SP_API_COMPLIANCE.md` §5) |

This plan exists to satisfy Amazon findings **RF-01** (notify
`security@amazon.com` within 24 hours of detecting an incident involving
Amazon Information) and **RF-05** (an incident-response plan with defined
roles, periodic review and a 24-hour notification procedure), traceable to
Data Protection Policy §1.6 (control `AC-12`).

> **This document is not yet complete evidence of a working control.** Two of
> the three prerequisites are met: the roles in §2 name real people
> (2026-08-18) and §12 is approved and dated (2026-08-18). The third — at
> least one tabletop exercise (§10) — has not been recorded; see
> `TABLETOP_001_PREPARED_SCENARIO.md` (prepared, not executed). Until it is,
> the state is `IMPLEMENTED (documented) + ROLES NAMED + APPROVED / NOT YET
> FULLY EVIDENCED`.

---

## 1. What counts as a Security Incident

A **Security Incident** is any actual or reasonably suspected event that
compromises the confidentiality, integrity or availability of Amazon
Information, or of the credentials that grant access to it.

Non-exhaustive triggers — if any of these is true, open an incident:

| # | Trigger |
|---|---|
| T-01 | SP-API credentials (LWA client ID/secret, refresh token) are exposed, leaked, committed to Git, pasted into a chat/ticket, or suspected of being known to anyone outside the Approved Users list. |
| T-02 | Database credentials, service-role keys, or deployment credentials are exposed by any of the same routes. |
| T-03 | Unauthorized access — or unexplained successful authentication — to the backend API, database, hosting provider, source repository or IdP. |
| T-04 | Amazon Information is disclosed to, or accessible by, any party not authorized under the Acceptable Use Policy. |
| T-05 | Malware, ransomware or unauthorized software is detected on a workstation or server within the boundary. |
| T-06 | A dependency vulnerability is being actively exploited, or a Critical/High vulnerability is found in a component that handles Amazon Information. |
| T-07 | Loss or theft of a device with access to Amazon Information or to any credential in §1 of `SECRETS.md`. |
| T-08 | An Approved User's account is compromised, or offboarding failed to revoke access within 24 hours. |
| T-09 | Amazon, a provider, or a third party notifies JUVAl of a suspected incident affecting JUVAl. |
| T-10 | Integrity failure: Amazon Information is altered, corrupted or destroyed without authorization. |

**When in doubt, open the incident.** Closing an incident later as
`NO_AMAZON_INFORMATION_INVOLVED` is cheap and is itself useful evidence.
Failing to open one is not recoverable, because the 24-hour clock (§5) runs
from *detection*, not from confirmation.

### 1.1 Explicitly not incidents

Ordinary application errors, failed imports of a supplier workbook, a 4xx/5xx
from a provider, or a failed deployment are **operational events**, not
security incidents — unless they meet a trigger above. Do not dilute the
incident record with routine faults.

---

## 2. Roles

Amazon requires defined roles (RF-05). JUVAl is a small organization, so one
person may hold several roles — but each role must be **named**, and the
Security Owner and IMPOC must be reachable outside business hours.

| Role | Responsibility | Assigned to |
|---|---|---|
| **Incident Commander (IC)** | Owns the incident end to end: declares it, sets severity, drives containment, decides recovery, closes it. Has authority to revoke credentials and take systems offline without further approval. | Daniel E. Liendo |
| **Security Owner** | Accountable for this plan, its six-month review, the tabletop exercise, and the accuracy of security evidence given to Amazon. May be the same person as the IC. | Daniel E. Liendo |
| **IMPOC** (Incident Management Point of Contact, per DPP §1.6) | The single contact Amazon can reach about a JUVAl incident, and the person who sends the §5 notification. Must be a monitored address. | Daniel E. Liendo |
| **Technical Responder** | Executes containment, revocation and recovery steps; preserves evidence. | Daniel E. Liendo |
| **Deputy** | Acts when the IC is unreachable within 1 hour. A plan with a single unreachable owner is not a plan. | Jocsimar C. Gonzalez |

Roles assigned 2026-08-18, by explicit user decision: one principal
responsible person (IC, Security Owner, IMPOC, Technical Responder) plus a
separate Deputy — combining roles is permitted by this section, and this is
the user's chosen combination, not a default. Out-of-hours availability for
the IC/Security Owner/IMPOC was confirmed by the user the same date; per the
rule below, the actual contact mechanism is not recorded here (§12 A-2, A-5).

> **Never enter a personal email, phone number or home address into this
> repository.** Record the role assignment in the approved copy of this plan
> held outside Git (§12), and keep only role names here.

---

## 3. Severity classification

Severity drives the clock and the escalation, so classify before acting.

| Severity | Definition | Amazon Information involved? | Notification |
|---|---|---|---|
| **SEV-1 — Critical** | Confirmed unauthorized access to, disclosure of, or loss of Amazon Information; or confirmed compromise of SP-API credentials. | Yes, confirmed | **`security@amazon.com` within 24 h of detection** (§5) — mandatory |
| **SEV-2 — High** | Credible suspicion of the above, not yet confirmed; or compromise of a credential that could reach Amazon Information. | Suspected | **Notify within 24 h of detection** — suspicion is sufficient; do not wait for confirmation |
| **SEV-3 — Moderate** | Security control failure with no evidence Amazon Information was reachable (e.g. workstation malware on a device with no Amazon access, expired TLS, failed offboarding caught in review). | No, after assessment | Internal record; notify only if §4.4 reclassifies it upward |
| **SEV-4 — Low** | Policy/hygiene deviation with no exposure (e.g. a secret found in a local file that was never pushed). | No | Internal record and corrective action |

**Rule:** if the assessment in §4.4 cannot conclusively rule Amazon
Information *out* within the first 12 hours, treat the incident as SEV-2 and
notify. Ambiguity resolves toward notification, never away from it.

---

## 4. Response procedure

The clock starts at **detection** — the first moment any JUVAl person or
system became aware of the facts, not when the investigation concluded.
Record that timestamp before anything else; it is the single most
consequential field in the whole record.

### 4.1 Detect and record (target: within minutes)

1. Record `detected_at` in UTC, ISO-8601, with timezone. Use the incident
   record template (`templates/INCIDENT_RECORD_TEMPLATE.md`).
2. Assign an incident ID: `JUVAL-IR-YYYYMMDD-NN`.
3. Name the IC. If the person who detected it is not the IC, they hold IC
   until formally handed over — the role is never vacant.

Detection sources currently available: application security logs
(`SECURITY.md`), provider dashboards and alerts (Railway, Supabase, Vercel,
GitHub), IdP authentication/admin events (ADR-022), GitHub secret scanning,
dependency vulnerability scanning (`tools/compliance_check.py`), and human
report.

### 4.2 Contain (target: within 1 hour of detection)

Containment precedes root-cause analysis. Do not preserve an active
compromise for the sake of investigation.

1. **Revoke first.** Rotate or revoke any credential in scope — see §4.3.
2. Disable the affected user account(s) at the IdP and terminate their live
   sessions (disabling alone does not always invalidate an issued token).
3. Restrict network exposure: take the affected service offline or block the
   ingress path if the exposure is ongoing.
4. Isolate an affected workstation from the network; do not wipe it (§4.5).

### 4.3 Credential revocation matrix

| Credential | Revocation action | Owner |
|---|---|---|
| SP-API LWA client secret / refresh token | Rotate in Solution Provider Portal; invalidate the old refresh token; update the backend secret store | IC |
| Database (Supabase) credentials / service-role key | Rotate in the Supabase dashboard; redeploy the backend with the new value | Technical Responder |
| Hosting/deploy credentials (Railway, Vercel) | Rotate provider token; review recent deployments for unauthorized changes | Technical Responder |
| Source control (GitHub) | Revoke personal access tokens and deploy keys; review recent pushes and Actions runs | Technical Responder |
| Human IdP account | Suspend account, force password reset, terminate sessions, re-enroll MFA | IC |

A credential that *may* have been exposed is treated as exposed. Rotation is
cheap; a lingering valid secret is not.

### 4.4 Determine whether Amazon Information is involved

This determination decides whether RF-01's 24-hour obligation applies, so it
must be explicit and recorded, not assumed.

Ask, and record the answer with its evidence:

1. Did the affected system store, process, transmit or grant access to Amazon
   Information (per the classification table in `AMAZON_SP_API_COMPLIANCE.md`
   §5)?
2. Were SP-API credentials, or anything that could obtain them, in scope?
3. Do logs show actual access to Amazon-derived records, or only the
   *possibility* of access?
4. Is Amazon PII involved? If yes, additional DPP §2 obligations apply.

Outcome is one of: `AMAZON_INFORMATION_CONFIRMED`,
`AMAZON_INFORMATION_SUSPECTED`, `AMAZON_INFORMATION_RULED_OUT`. The first two
require notification under §5. A `RULED_OUT` conclusion must cite the evidence
that ruled it out — "we think not" is not a determination.

> As of this version JUVAl holds **no** Amazon Information and **no** SP-API
> credentials (registration is `REJECTED_REMEDIATION_REQUIRED`). Any incident
> today would almost certainly resolve to `AMAZON_INFORMATION_RULED_OUT`.
> That will change the moment a reapplication is approved, and this plan is
> written for that state, not only for today's.

### 4.5 Preserve evidence

Before remediating, preserve — remediation destroys evidence.

- Export the relevant logs (application security log, IdP events, provider
  audit logs) to the incident folder with their retrieval timestamp.
- Capture the state: affected versions, commit SHA, deployment ID, config
  snapshot **with secrets redacted**.
- Do not wipe or reimage an affected device until the IC approves.
- Never copy a secret value into the incident record. Record the credential's
  *identity* ("Supabase service-role key") and its rotation timestamp, never
  the value.
- Retain incident evidence for at least 12 months (aligns with the log
  retention expectation in DPP §2.6.1).

### 4.6 Recover

1. Restore service from a known-good state; verify integrity of any data
   restored.
2. Confirm the vulnerability that permitted the incident is actually closed —
   re-test it, do not assume the fix worked.
3. Verify all rotated credentials work and all old ones are dead.
4. Monitor for recurrence for at least 7 days; record what was monitored.
5. The IC formally closes the incident and records `closed_at`.

---

## 5. Amazon notification — the 24-hour obligation (RF-01)

**Address:** `security@amazon.com`
**Deadline:** within **24 hours of detection** (`detected_at`), not of
confirmation, and not of containment.
**Sender:** IMPOC (§2).

Send the notification as soon as §4.4 returns `CONFIRMED` or `SUSPECTED`.
**Do not delay to complete the investigation.** An incomplete but timely
notification satisfies the obligation; a complete but late one does not.

Include:

1. JUVAl developer/organization identity and the IMPOC's contact details.
2. `detected_at` (UTC) and how it was detected.
3. What is known so far, and what is still unknown — state uncertainty plainly.
4. Which Amazon Information is or may be affected, and its scale if known.
5. Containment already performed (credential rotation, account suspension).
6. Immediate next steps and when the next update will be sent.

Then: log the notification's sent timestamp in the incident record, keep the
sent message and any Amazon reply as evidence, and send follow-up updates as
material facts change until Amazon closes it out.

> **Do not send a test or drill notification to `security@amazon.com`.**
> Tabletop exercises (§10) stop at drafting the message; the draft is the
> evidence. Sending a fake incident report to Amazon would itself be a
> reportable failure of judgement.

---

## 6. Communication

| Audience | Who | When |
|---|---|---|
| Amazon | IMPOC | Per §5 |
| Affected provider (Supabase/Railway/Vercel/GitHub/IdP) | Technical Responder | When the provider is implicated or needed for containment |
| Internal | IC | At declaration, at containment, at closure |
| Regulators / data subjects | Security Owner | Only if Amazon PII is confirmed involved and law requires it — take legal advice first |

Use a communication channel that is not the compromised system. If the
compromise involves email or the source repository, coordinate elsewhere.

---

## 7. Postmortem

Within **5 business days** of closure, for every SEV-1 and SEV-2:

1. Timeline: detection → containment → notification → recovery → closure,
   with the actual elapsed time at each step.
2. Root cause — the control that failed, not the person who was on duty.
3. Was the 24-hour notification met? If not, why, and what changes so it is
   met next time.
4. Corrective actions, each with an owner and a due date.
5. Whether this plan needs to change; if so, amend it and bump the version.

Blameless. A plan people are afraid to invoke is worse than no plan, because
it produces the illusion of a control while suppressing detection.

---

## 8. Plan review (RF-05)

- **Cadence: every six months**, and additionally after any SEV-1/SEV-2, any
  material architecture change, and any change to Amazon's policies.
- Reviewer: Security Owner.
- Each review records: date, reviewer, changes made (or an explicit "no change
  required"), and the next due date.
- `tools/compliance_check.py` verifies mechanically that the review is not
  overdue — see §11.

### Review log

| Date | Reviewer | Version | Outcome |
|---|---|---|---|
| 2026-08-18 | `ROLE PLACEHOLDER — Security Owner` | 0.1.0-DRAFT | Initial draft created in response to Amazon findings RF-01/RF-05. **Not yet approved.** |
| 2026-08-18 | Daniel E. Liendo (Security Owner) | 0.1.0-DRAFT | Roles assigned (§2) and plan approved (§12 A-1, A-3, A-5). No content change to this plan; version unchanged. Not a six-month periodic review — logged here for traceability alongside it. |

---

## 9. Contact and escalation

| Need | Contact |
|---|---|
| Declare an incident | Incident Commander (§2) |
| IC unreachable > 1 hour | Deputy (§2) |
| Amazon notification | IMPOC (§2) → `security@amazon.com` |
| Provider support | Each provider's support channel; account owner listed in the third-party register |

Actual names, addresses and phone numbers live in the approved out-of-band
copy (§12), never in this repository.

---

## 10. Tabletop exercise

At least **once every six months**, alongside the §8 review.

Procedure:

1. Pick a scenario. Rotate; do not rehearse the same one twice in a row.
   Suggested: (a) SP-API refresh token committed to a public repository;
   (b) Supabase service-role key found in a frontend bundle; (c) an Approved
   User's IdP account compromised, with MFA fatigue; (d) provider notifies
   JUVAl of unauthorized access to the backend host.
2. Walk the real procedure — §4.1 through §4.6 and §5 — against the wall
   clock. Actually open the templates and fill them in.
3. **Draft** the Amazon notification. Do not send it (§5).
4. Record the result in `templates/TABLETOP_RECORD_TEMPLATE.md`, including
   the elapsed time to a drafted notification and every gap found.
5. File each gap as a corrective action with an owner and due date.

An exercise that finds no gaps was not a real exercise; record what was tested
and why nothing was found.

---

## 11. Automated verification

`tools/compliance_check.py` mechanically verifies what a document cannot
assert about itself:

- every required section of this plan is present;
- `security@amazon.com` and the 24-hour obligation are stated;
- the six-month review is not overdue as of the run date;
- any remaining unfilled role markers are counted, so an unapproved plan can
  never be quietly presented as complete;
- no secret-shaped string has entered this document or the templates.

Run it: `python tools/compliance_check.py`. It exits non-zero when the plan is
structurally incomplete or the review is overdue. It is exercised by
`tests/compliance/test_incident_response_plan.py`, so a regression is caught
by the normal test run.

---

## 12. Approval (EXTERNAL USER ACTION REQUIRED)

This plan is now approved (A-3), but is **not yet fully evidenced** until
every row below is `DONE`. Each row is a user action the agent cannot
perform on the user's behalf — the `DONE` rows below record that the user
performed it, not that the agent inferred or assumed it:

| # | Action | Status |
|---|---|---|
| A-1 | Name a real Incident Commander, Security Owner, IMPOC and Deputy (§2) | `DONE 2026-08-18` — explicit user decision (this session): IC/Security Owner/IMPOC/Technical Responder = Daniel E. Liendo; Deputy = Jocsimar C. Gonzalez. Recorded in §2 |
| A-2 | Record their contact details in an approved copy held **outside** this repository | `PENDING` — no email or phone was provided to, or recorded by, the agent (by design — see the rule above §2); the user still needs to independently confirm this custody exists |
| A-3 | Management approval and signature, with a date; set `Effective date` and change `Status` to APPROVED | `DONE 2026-08-18` — user explicitly approved: *"Yo, [nombre y cargo], apruebo INCIDENT_RESPONSE_PLAN.md versión 0.1.0-DRAFT (document ID JUVAL-IRP, última revisión 2026-08-18) como el procedimiento vigente de respuesta a incidentes de JUVAl, con fecha efectiva 2026-08-18."* Approver: Daniel E. Liendo. `Status`/`Effective date` above updated accordingly |
| A-4 | Run the first tabletop exercise (§10) and file its record | `PENDING` — `TABLETOP_001_PREPARED_SCENARIO.md` is prepared; execution has not occurred |
| A-5 | Confirm the IMPOC address is monitored outside business hours | `DONE 2026-08-18` — user confirmed an out-of-hours availability mechanism exists for the IC/Security Owner/IMPOC (one person); the mechanism itself is deliberately not recorded here, per the rule above §2 |

Until A-2 and A-4 are also complete:

`RF-01 = PARTIAL (roles named and plan approved 2026-08-18; contact-detail custody outside this repository unconfirmed, and no tabletop exercise run)`
`RF-05 = PARTIAL (plan approved, roles named, review cadence documented; still no exercise record — an approved plan is not yet an exercised control)`
