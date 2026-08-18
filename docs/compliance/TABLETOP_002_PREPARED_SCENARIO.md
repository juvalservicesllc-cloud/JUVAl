# TABLETOP-002 — Prepared Scenario (NOT YET EXECUTED)

| Field | Value |
|---|---|
| Status | **PREPARED — not run.** This document contains facilitator material, injects and a blank acceptance matrix only; it contains **no actual results**. Not to be executed by this pass — preparation only. |
| Prepared | 2026-08-18 |
| Scenario source | `INCIDENT_RESPONSE_PLAN.md` §10, candidate (b) — "Supabase service-role key found in a frontend bundle" (rotated from TABLETOP-001's candidate (a), per §10's own "do not rehearse the same one twice" rule) |
| Plan version to exercise | `0.1.1-DRAFT` (§4.2/§4.5 amended 2026-08-18 — see `INCIDENT_RESPONSE_PLAN.md` §8 review log) |
| Purpose | Test `CA-01` and `CA-02` (`SP_API_REGISTRATION_REMEDIATION.md` §28), and reach the §5 notification-drafting branch that `JUVAL-TT-20260818` never exercised |
| To be recorded in | `templates/TABLETOP_RECORD_TEMPLATE.md`, as `JUVAL-TT-YYYYMMDD` on the day it is actually run, plus a filled `templates/EVIDENCE_MANIFEST_TEMPLATE.md` |
| Unblocks | Nothing on its own — `CA-01`/`CA-02` stay `OPEN` until this (or a real incident) actually produces the evidence described below |

Required timing: on or before the plan's next review, `2027-02-18`
(`INCIDENT_RESPONSE_PLAN.md` §8/§10) — that date is not moved earlier by
this preparation. Running it sooner is an **option**, not a requirement;
see `SP_API_REGISTRATION_REMEDIATION.md` §28.6.

---

## Why this scenario

Unlike TABLETOP-001's SP-API token (which JUVAl could never actually have,
since no credential has ever been issued — guaranteeing a
`RULED_OUT` outcome), a Supabase service-role key is a **real credential
JUVAl genuinely holds today** in production (`SECRETS.md` §1, class 3).
An exposure of it is not hypothetical in the same way — which is exactly
why this scenario can plausibly reach `CONFIRMED`/`SUSPECTED` rather than
resolving to `RULED_OUT` before containment is even tested.

One fact in this scenario is explicitly simulated, not real, and is
labeled as such throughout: **for this exercise only**, assume Amazon has
approved JUVAl's SP-API reapplication and the Supabase database now holds
live Amazon-derived records. This is necessary to reach the §5 branch at
all — JUVAl holds no real Amazon Information today (`INCIDENT_RESPONSE_
PLAN.md` §4.4's own note), so every honestly-evaluated scenario using
today's actual state resolves to `RULED_OUT`, same as TABLETOP-001. The
plan itself says it "is written for that state, not only for today's" —
this exercise takes it at its word. Nothing about this simulated
assumption is written back into any compliance document as if it were
true today.

## Objectives

1. Test `CA-01`: given a confirmed *real*, live credential exposure, does
   the responder initiate rotation immediately, per the clarified §4.2
   rule — not waiting to fully scope the exposure first?
2. Test `CA-02`: does the responder actually produce a filled evidence
   manifest (`templates/EVIDENCE_MANIFEST_TEMPLATE.md`), not just assert
   "evidence was preserved"?
3. Reach and exercise §5: draft (never send) an Amazon notification,
   against the 24-hour clock from `detected_at`.

## Participants required

Per `INCIDENT_RESPONSE_PLAN.md` §2, as assigned in
`templates/IRP_ROLE_ASSIGNMENT_AND_APPROVAL_FORM.md`: Daniel E. Liendo
(IC/Security Owner/IMPOC/Technical Responder), Jocsimar C. Gonzalez
(Deputy — participation optional but recommended, since TABLETOP-001 ran
without the Deputy present).

## Starting conditions

During a routine review, a JS bundle downloaded from JUVAl's live Vercel
frontend (`https://juval-frontend.vercel.app` or current production URL)
is found to contain a string matching the pattern of a Supabase
service-role key.

**SIMULATED FOR THIS EXERCISE ONLY:** assume Amazon has approved JUVAl's
SP-API reapplication, and the Supabase database referenced by that key now
contains live Amazon-derived product records (ASINs, sales figures).

---

## Inject 1 — Detection (T+0)

**Facilitator reads:** "You find the string. It matches the shape of a
Supabase service-role key exactly."

**Expected decisions (facilitator reference, per §4.1 and the amended
§4.2):**
- Record `detected_at`, assign an incident ID, IC assumes the role
  immediately (§4.1).
- Per the amended §4.2: this is a §1 trigger (T-02, database credential
  exposure) — containment begins now, not after confirming the key is
  live.

**Actual recorded decision:** *(blank — fill when run)*

## Inject 2 — CA-01 test point (T+5 min, simulated)

**Facilitator reads:** "Do you rotate the key now, or first check Supabase
logs to see whether it's actually been used by anyone else?"

**Expected decisions (facilitator reference, per the amended §4.2):**
- Rotate first. Checking usage logs is legitimate, valuable work — but it
  runs *in parallel* with rotation, performed by the Technical Responder
  while the IC (or the same person, here) initiates the key rotation in
  the Supabase dashroom, per §4.3's credential revocation matrix.
- **This is the actual CA-01 test.** Record the wall-clock time between
  `detected_at` and the moment rotation was *initiated* (not completed) —
  that gap is the evidence, not a verbal confirmation that "we'd rotate
  first."

**Actual recorded decision:** *(blank — fill when run)*
**CA-01 result:** *(blank — PASS/FAIL per `SP_API_REGISTRATION_
REMEDIATION.md` §28.2's pass condition, fill when run)*

## Inject 3 — CA-02 test point (T+15 min, simulated)

**Facilitator reads:** "Before you finish rotating, what evidence do you
capture, from where, and where does it go?"

**Expected decisions (facilitator reference, per the amended §4.5):**
- Do not accept a verbal "I'd export the logs" as sufficient. The
  participant must actually open `templates/EVIDENCE_MANIFEST_TEMPLATE.md`
  and fill at least 2–3 rows using **real** source systems from that
  template's table (e.g. Supabase project logs, Vercel deployment/build
  logs, GitHub commit history for when the key was introduced).
- **This is the actual CA-02 test.** A completed (simulated) manifest is
  the evidence, not a description of intent.

**Actual recorded decision:** *(blank — fill when run)*
**CA-02 result:** *(blank — PASS/FAIL per `SP_API_REGISTRATION_
REMEDIATION.md` §28.3's pass condition, fill when run)*

## Inject 4 — Amazon Information determination and §5 (T+25 min, simulated)

**Facilitator reads:** "Recall the simulated assumption: this Supabase
database holds live Amazon-derived records. Work through §4.4."

**Expected decisions (facilitator reference, per §4.4 and §5):**
- §4.4 questions: did the affected system hold Amazon Information? (Yes,
  per the simulated assumption.) Were credentials that could reach it in
  scope? (Yes — the service-role key.) Determination:
  `AMAZON_INFORMATION_CONFIRMED` or `SUSPECTED`, either is defensible
  depending on whether unauthorized *access* (not just exposure) can be
  ruled out from the logs gathered in Inject 3.
- This **triggers §5**: draft — never send — a notification to
  `security@amazon.com` containing all six required elements (identity/
  IMPOC contact, `detected_at` and detection method, known/unknown facts,
  affected Amazon Information and scale, containment already performed,
  next steps and update timing).
- Record the elapsed time from `detected_at` to the completed draft —
  this is the number that matters against the 24-hour obligation.

**Actual recorded decision:** *(blank — fill when run)*
**Drafted notification (never sent):** *(blank — fill when run)*

## Inject 5 — Recovery and lessons learned (T+35 min, simulated)

**Facilitator reads:** "The key is rotated, confirmed dead. What's left?"

**Expected decisions (facilitator reference, per §4.6 and §7):**
- Confirm the new key works and the old one is rejected.
- Since this scenario is SEV-1/SEV-2 (Amazon Information involved),
  §7's postmortem applies within 5 business days of a real occurrence —
  note this as a follow-up expectation, not something to do in the
  tabletop itself.
- Monitor for recurrence for 7 days (§4.6.4) — note as a follow-up.

**Actual recorded decision:** *(blank — fill when run)*

---

## Containment questions to walk explicitly

- Which row of the §4.3 matrix applies (database credentials)? Who owns
  it (Technical Responder, per that matrix)?
- Does rotating a Supabase service-role key require a backend redeploy
  (per `SECRETS.md` — yes, the value is read from environment at
  startup)? If so, was that redeploy actually initiated during the
  exercise, or only described?

## Recovery

- Confirm the rotated key is live in the backend's environment and the
  old value is rejected.
- Confirm the frontend bundle no longer contains the string (re-run the
  same bundle check `NETWORK_SECURITY.md`/`SECRETS.md` already used to
  verify this is *not* currently the case).

---

## Acceptance matrix (leave RESULT blank until actually run)

| Control | Scenario event | Expected action | Pass criterion | Evidence artifact | Result |
|---|---|---|---|---|---|
| `CA-01` | Confirmed live Supabase service-role key found exposed (Inject 2) | Initiate rotation immediately; usage-confirmation runs in parallel, not first | Rotation *initiated* before or in parallel with usage-log investigation, within §4.2's 1-hour target from `detected_at` | Tabletop record timeline: timestamp rotation initiated vs. `detected_at` | `NOT_EXECUTED` |
| `CA-02` | Evidence must be captured before/alongside remediation (Inject 3) | Produce a filled evidence manifest using real source systems only | A completed `EVIDENCE_MANIFEST_TEMPLATE.md` copy with ≥2 rows correctly filled (category, real source system, both timestamps, custody reference) | Filled manifest attached to the `JUVAL-TT-YYYYMMDD` record | `NOT_EXECUTED` |
| §5 notification drafting | Simulated Amazon Information determination reaches `CONFIRMED`/`SUSPECTED` (Inject 4) | Draft (never send) a §5 notification with all 6 required elements | A drafted notification text containing all 6 elements, explicitly marked never sent, with elapsed time from `detected_at` recorded | Draft text + elapsed-time figure in the `JUVAL-TT-YYYYMMDD` record | `NOT_EXECUTED` |

## What this preparation does and does not prove

Preparing this scenario, its injects, and the acceptance matrix is
**documentation work** — it makes `CA-01` and `CA-02` objectively testable
and gives the next exercise a specific target, including the one branch
(§5) TABLETOP-001 never reached. It does **not**, by itself:

- close `CA-01` or `CA-02` — both remain `OPEN`;
- count as `CONTROL_EXERCISED` — nothing has been walked yet;
- count as `RECURRING_OPERATIONAL_EVIDENCE` — preparing a second exercise
  is not the same as having run one, let alone having run two several
  months apart;
- change RF-01 or RF-05's classification — both remain `PARTIAL`.

See `SP_API_REGISTRATION_REMEDIATION.md` §28 for the full reconciliation.
