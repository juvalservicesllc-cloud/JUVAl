# Incident Response — Role Assignment and Approval Form

> Prepared 2026-08-18 to unblock `INCIDENT_RESPONSE_PLAN.md` §12 (A-1…A-5).
> This is a **blank form**, not a record. It closes E-3 in
> `SP_API_REGISTRATION_REMEDIATION.md` §20.5 once the user completes it.

**Do not commit a filled copy of this file with real names, emails or phone
numbers.** `INCIDENT_RESPONSE_PLAN.md` §2 is explicit: personal contact
details are recorded in an approved copy held **outside** this Git
repository, never inside it. Fill this form in a local copy, in the
organization's secret/HR system, or on paper — then transcribe only the
**role names** (not the contact details) back into `INCIDENT_RESPONSE_PLAN.md`
§2 and answer the checklist in Part C here in the repository copy.

Fields requested are limited to what §2/§4/§5 of the plan actually use: who
declares/leads, who Amazon can reach, who takes over if the lead is
unreachable. No other personal information is requested.

---

## Part A — Role assignment

One person may legitimately hold more than one role in a small
organization (`INCIDENT_RESPONSE_PLAN.md` §2). Combining roles is an
**option the user chooses**, not an assignment made here — nothing below
pre-selects a combination.

### Incident Commander (IC)
*Declares incidents, sets severity, drives containment/recovery, can revoke
credentials and take systems offline without further approval. Must be
reachable — a Deputy exists for when they are not (within 1 hour).*

| Field | Value |
|---|---|
| Name | `[USER MUST ASSIGN]` |
| Email | `[USER MUST ASSIGN]` |
| Phone (for off-hours reachability) | `[USER MUST ASSIGN]` |

### Security Owner
*Accountable for the plan itself, its six-month review, the tabletop, and
the accuracy of security evidence given to Amazon. May be the same person
as the IC. Must be reachable outside business hours (§2).*

| Field | Value |
|---|---|
| Name | `[USER MUST ASSIGN]` (may be the same person as IC — user's choice) |
| Email | `[USER MUST ASSIGN]` |
| Phone (for off-hours reachability) | `[USER MUST ASSIGN]` |

### IMPOC (Incident Management Point of Contact)
*The single contact Amazon can reach about a JUVAl incident; sends the §5
notification. Must be a monitored address, reachable outside business
hours (§2).*

| Field | Value |
|---|---|
| Name | `[USER MUST ASSIGN]` (may be the same person as IC/Security Owner — user's choice) |
| Email (must be actively monitored) | `[USER MUST ASSIGN]` |
| Phone (for off-hours reachability) | `[USER MUST ASSIGN]` |

### Technical Responder
*Executes containment, revocation and recovery steps; preserves evidence
(§4.3).*

| Field | Value |
|---|---|
| Name | `[USER MUST ASSIGN]` |
| Email | `[USER MUST ASSIGN]` |

### Deputy
*Acts when the IC is unreachable within 1 hour. Must be a different person
from the IC — a deputy who is the IC is not a deputy.*

| Field | Value |
|---|---|
| Name | `[USER MUST ASSIGN]` (must differ from IC) |
| Email | `[USER MUST ASSIGN]` |
| Phone (for off-hours reachability) | `[USER MUST ASSIGN]` |

No sixth role is requested. `INCIDENT_RESPONSE_PLAN.md` §2 defines exactly
these five; nothing here adds a role the plan doesn't already call for.

---

## Part B — Plan approval statement

Derived from `INCIDENT_RESPONSE_PLAN.md` §12 (A-3). To approve, the user
states the following, filled in and signed/dated outside this repository
(or pasted back to the agent as an explicit instruction to record it):

> "I, **`[USER MUST FILL — name/title]`**, approve
> `INCIDENT_RESPONSE_PLAN.md` version **`0.1.0-DRAFT`** (document ID
> `JUVAL-IRP`, last reviewed 2026-08-18) as JUVAl's current incident-response
> procedure, effective **`[USER MUST FILL — YYYY-MM-DD]`**."

This statement is **not yet made**. No agent may make it on the user's
behalf (`CLAUDE.md` §3 — decisions with this impact require explicit
APPROVED status, never inferred for convenience).

Once made, the plan's own header fields change: `Status: DRAFT — NOT
APPROVED` → `APPROVED`, `Effective date: PENDING_APPROVAL` → the date given
above. That edit is a one-line follow-up the agent can make **after**, and
only after, the user supplies this statement.

---

## Part C — Remaining A-1…A-5 checklist

| # | Action | Satisfied when |
|---|---|---|
| A-1 | Name IC, Security Owner, IMPOC, Deputy | Part A filled (Technical Responder is not in A-1 but the plan lists it — filling it too is recommended, not required by A-1 itself) |
| A-2 | Contact details recorded outside this repository | Part A's filled copy is stored outside Git — confirm here: `[ ] done, stored at: ______` (location only, not the details) |
| A-3 | Management approval, signed and dated | Part B statement made — confirm here: `[ ] done` |
| A-4 | First tabletop exercise run and filed | See `TABLETOP_001_PREPARED_SCENARIO.md` — prepared, not yet run |
| A-5 | IMPOC address confirmed monitored outside business hours | `[ ] confirmed` |

`RF-01` and `RF-05` stay `PARTIAL` until this checklist is complete
**and** A-4 has an actual filed record — see
`SP_API_REGISTRATION_REMEDIATION.md` §22 for how each step changes (or
doesn't change) the classification.
