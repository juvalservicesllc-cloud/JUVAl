# Incident Response — Role Assignment and Approval Form

> Prepared 2026-08-18 to unblock `INCIDENT_RESPONSE_PLAN.md` §12 (A-1…A-5).
> **Updated 2026-08-18: role names (A-1) and approval (A-3, A-5) were
> provided by the user and are recorded below and in
> `INCIDENT_RESPONSE_PLAN.md` §2/§12.** This closes the naming/approval part
> of E-3 (`SP_API_REGISTRATION_REMEDIATION.md` §20.5). A-2 (contact-detail
> custody outside this repository) and A-4 (the tabletop) remain open — see
> Part C.

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
| Name | Daniel E. Liendo |
| Email | Not recorded in this repository (§2 rule) — held by the user outside Git |
| Phone (for off-hours reachability) | Not recorded in this repository (§2 rule) — user confirmed 2026-08-18 that an out-of-hours mechanism exists (A-5); the mechanism itself is not recorded here |

### Security Owner
*Accountable for the plan itself, its six-month review, the tabletop, and
the accuracy of security evidence given to Amazon. May be the same person
as the IC. Must be reachable outside business hours (§2).*

| Field | Value |
|---|---|
| Name | Daniel E. Liendo (same person as IC — user's chosen combination) |
| Email | Not recorded in this repository (§2 rule) |
| Phone (for off-hours reachability) | Not recorded in this repository (§2 rule) — see A-5 note above |

### IMPOC (Incident Management Point of Contact)
*The single contact Amazon can reach about a JUVAl incident; sends the §5
notification. Must be a monitored address, reachable outside business
hours (§2).*

| Field | Value |
|---|---|
| Name | Daniel E. Liendo (same person as IC/Security Owner — user's chosen combination) |
| Email (must be actively monitored) | Not recorded in this repository (§2 rule) |
| Phone (for off-hours reachability) | Not recorded in this repository (§2 rule) — see A-5 note above |

### Technical Responder
*Executes containment, revocation and recovery steps; preserves evidence
(§4.3).*

| Field | Value |
|---|---|
| Name | Daniel E. Liendo |
| Email | Not recorded in this repository (§2 rule) |

### Deputy
*Acts when the IC is unreachable within 1 hour. Must be a different person
from the IC — a deputy who is the IC is not a deputy.*

| Field | Value |
|---|---|
| Name | Jocsimar C. Gonzalez |
| Email | Not recorded in this repository (§2 rule) |
| Phone (for off-hours reachability) | Not recorded in this repository (§2 rule) |

No sixth role is requested. `INCIDENT_RESPONSE_PLAN.md` §2 defines exactly
these five; nothing here adds a role the plan doesn't already call for.

**A-2 is still open**: no email or phone address was provided by the user
in any message, so none could be recorded anywhere, in or out of this
repository. This form only tracks *that* names were assigned — it is not
itself the "approved copy held outside Git" that A-2 requires; the user
still needs to establish and confirm that custody independently.

---

## Part B — Plan approval statement

Derived from `INCIDENT_RESPONSE_PLAN.md` §12 (A-3). **Made 2026-08-18**, by
explicit user instruction (this session), verbatim:

> "Yo, Daniel E. Liendo, apruebo `INCIDENT_RESPONSE_PLAN.md` versión
> `0.1.0-DRAFT` (document ID `JUVAL-IRP`, última revisión 2026-08-18) como el
> procedimiento vigente de respuesta a incidentes de JUVAl, con fecha
> efectiva `2026-08-18`."

Recorded in `INCIDENT_RESPONSE_PLAN.md`'s header (`Status: APPROVED`,
`Effective date: 2026-08-18`) and §12 (A-3: `DONE`).

---

## Part C — A-1…A-5 checklist

| # | Action | Status |
|---|---|---|
| A-1 | Name IC, Security Owner, IMPOC, Deputy | `DONE 2026-08-18` — Part A, and `INCIDENT_RESPONSE_PLAN.md` §2 |
| A-2 | Contact details recorded outside this repository | `PENDING` — no email or phone was ever provided to the agent; nothing to store, and the user still needs to independently confirm this custody exists |
| A-3 | Management approval, signed and dated | `DONE 2026-08-18` — Part B above |
| A-4 | First tabletop exercise run and filed | `PENDING` — `TABLETOP_001_PREPARED_SCENARIO.md` is prepared, not yet run |
| A-5 | IMPOC address confirmed monitored outside business hours | `DONE 2026-08-18` — user confirmed the mechanism exists; the mechanism itself is not recorded here (§2 rule) |

`RF-01` and `RF-05` stay `PARTIAL` until A-2 and A-4 also close — see
`SP_API_REGISTRATION_REMEDIATION.md` §24 for how this changed (and did not
change) the classification.
