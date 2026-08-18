# TABLETOP-001 — Prepared Scenario (NOT YET EXECUTED)

| Field | Value |
|---|---|
| Status | **PREPARED — not run.** No exercise has occurred. This document contains facilitator material and expected/reference answers only; it contains **no actual results**. |
| Prepared | 2026-08-18 |
| Scenario source | `INCIDENT_RESPONSE_PLAN.md` §10, candidate (a) — "SP-API refresh token committed to a public repository" |
| Plan version to exercise | `0.1.0-DRAFT` |
| To be recorded in | `templates/TABLETOP_RECORD_TEMPLATE.md`, as `JUVAL-TT-YYYYMMDD` on the day it is actually run |
| Unblocks | `INCIDENT_RESPONSE_PLAN.md` §12 A-4, once actually run and filed |

This exercises `INCIDENT_RESPONSE_PLAN.md` §4.1–§4.6 and §5 end to end,
using facts already true of JUVAl today — not invented ones: the GitHub
repository is genuinely public (`NETWORK_SECURITY.md` §3.2), and JUVAl
genuinely holds no live SP-API credential today (registration
`REJECTED_REMEDIATION_REQUIRED`). No new Amazon obligation is introduced
beyond what the plan already documents.

---

## Objectives

1. Walk the full response procedure against a realistic credential-exposure
   trigger (`INCIDENT_RESPONSE_PLAN.md` §1, trigger T-01) under time
   pressure, and measure how long it actually takes to reach a drafted
   Amazon notification.
2. Specifically test the §4.4 Amazon Information determination — this
   scenario is deliberately built so the *initial* facts look like SEV-1,
   and a mid-exercise fact changes that. A tabletop that only ever confirms
   the obvious case is not testing judgment.
3. Surface any role, tooling, or template gap before a real incident does.

## Participants required

Per `INCIDENT_RESPONSE_PLAN.md` §2 — whoever is named IC, Security Owner,
IMPOC, Technical Responder and Deputy in the completed
`IRP_ROLE_ASSIGNMENT_AND_APPROVAL_FORM.md`. One person may hold multiple
roles; run the exercise with however many humans are actually assigned. A
facilitator (may be the Security Owner) reads the injects and does not
participate in the response decisions.

**This exercise cannot run before `INCIDENT_RESPONSE_PLAN.md` §12 A-1 is
complete** — there is no one to play IC/IMPOC/Deputy otherwise.

## Starting conditions

A GitHub secret-scanning alert (a control JUVAl already has enabled and
verified — `NETWORK_SECURITY.md` §3.2) fires for the `JUVAl` repository:
*"Possible Amazon LWA refresh token detected in commit `<sha>`, pushed 40
minutes ago."* The repository is public.

---

## Inject 1 — Detection (T+0)

**Facilitator reads:** "You receive the GitHub secret-scanning alert above.
Nothing else is known yet."

**Expected decisions (facilitator reference, per §4.1 and §3):**
- Record `detected_at` = the alert's timestamp, in UTC.
- Open an incident, assign an ID (`JUVAL-IR-YYYYMMDD-NN`).
- Whoever received the alert holds IC until formally handed over (§4.1.3)
  — the role is never vacant, even mid-exercise.
- Initial severity classification: the alert *describes* a possible
  compromise of an SP-API credential, which per §3 is SEV-1 — classify it
  SEV-1 provisionally and start the clock. (§3's rule that ambiguity
  resolves toward notification, not away from it, applies from the first
  minute, not only after confirmation.)

**Actual recorded decision:** *(blank — fill when run)*

## Inject 2 — Complication (T+15 min, simulated)

**Facilitator reads:** "You open the commit. The string matching the
secret-scanning pattern is present. You also notice: JUVAl's SP-API
registration status is `REJECTED_REMEDIATION_REQUIRED` — no SP-API
credential has ever actually been issued to JUVAl (`SP_API_REGISTRATION_
REMEDIATION.md` §20). The committer says it's leftover text from a draft
`.env.example` line, not a real value pasted from a provider console."

**Expected decisions (facilitator reference, per §4.3 and §4.4):**
- Containment does not wait for the determination in §4.4 to be finished
  — rotate/invalidate first regardless of whether the string turns out to
  be real (§4.2: "revoke first"). Since no live SP-API credential exists,
  "rotation" here means: confirm no such credential exists anywhere that
  could be invalidated, and remove/history-scrub the exposed string as a
  hygiene action.
- Work the §4.4 questions explicitly rather than accepting the committer's
  claim at face value: did the system ever hold Amazon Information? (No —
  documented and independently true.) Were SP-API credentials in scope?
  (No — none exist.) Do logs show access, or only the possibility of
  access? (N/A — nothing to access.) Is Amazon PII involved? (No.)
- Reference determination: `AMAZON_INFORMATION_RULED_OUT`, **citing the
  evidence** (the registration status, and confirmation no credential of
  that kind has ever been issued) — not "we think not" (§4.4 explicitly
  forbids that shortcut).

**Actual recorded decision:** *(blank — fill when run)*

## Inject 3 — Decision point (T+45 min, simulated)

**Facilitator reads:** "A participant asks: given the string turned out
not to be a live credential, do we still need to notify
`security@amazon.com`? A second participant points out the repository was
public for 40 minutes before detection — could someone else have already
tried to use it?"

**Expected decisions (facilitator reference, per §3 and §5):**
- With a cited `AMAZON_INFORMATION_RULED_OUT` determination, §5's
  mandatory-notification trigger (`CONFIRMED` or `SUSPECTED`) is not met —
  do **not** send to `security@amazon.com` for *this* fact pattern. The
  exercise should reach this conclusion **because of the evidence
  gathered in Inject 2**, not by default — a group that skips straight to
  "no need to notify" without doing the §4.4 work has failed the exercise
  even if the final answer matches.
  Contrast: if Inject 2 had instead confirmed the string *was* a real,
  live credential, this same question would resolve to SEV-1 → mandatory
  notification within 24 hours of Inject 1's `detected_at` — the exercise
  should have participants say this out loud, since it is the actual
  control being tested (§5's 24-hour clock), even though this run's
  specific facts don't trigger it.
- The "someone already used it" question is a real §4.6 recovery/
  monitoring question regardless of the notification answer: even a fake
  credential's public exposure for 40 minutes is a hygiene finding —
  scrub the string from history, and treat it as a SEV-4 policy/hygiene
  deviation per §3, logged with a corrective action (§7 applies only to
  SEV-1/SEV-2, but nothing stops recording a lighter note for SEV-4).

**Actual recorded decision:** *(blank — fill when run)*

---

## Containment questions to walk explicitly

Per the §4.3 credential revocation matrix, even though nothing here is a
live credential:

- Which row of the matrix would apply if the string *had* been real (SP-API
  LWA client secret / refresh token row — owner: IC)?
- Who actually has the access needed to purge the string from Git history
  today, and is that a Technical Responder action or does it need GitHub
  support?
- Is the exposed-string cleanup itself logged as a corrective action, with
  an owner and a due date (§7's postmortem structure, applied even though
  this is SEV-4)?

## Notification decision — record explicitly

- Determination reached: `AMAZON_INFORMATION_RULED_OUT` /
  `AMAZON_INFORMATION_SUSPECTED` / `AMAZON_INFORMATION_CONFIRMED`
  *(blank — fill when run; reference answer above is RULED_OUT)*
- If not RULED_OUT: drafted notification text, **not sent** (§5's hard
  rule — the draft is the evidence, sending it is a reportable failure of
  judgement in a drill).

## Amazon 24-hour notification consideration

- `detected_at` (from Inject 1): *(blank — fill when run)*
- Notification deadline if SEV-1/SEV-2 confirmed: `detected_at` + 24h.
- Elapsed time from `detected_at` to the group's determination in Inject 3:
  *(blank — fill when run)* — compare against the 24-hour budget even
  though this run doesn't require sending, so the group has a felt sense of
  the clock for the run where it does.

## Recovery

- Confirm the exposed string is removed from the current tree and, if
  feasible, from history (or documented as a residual exposure if history
  rewrite is not performed — rewriting public repository history has its
  own risk and is itself a decision worth surfacing, not a given).
- Confirm GitHub secret scanning correctly flagged this class of string
  (it did, by construction of the scenario) — this is itself evidence the
  control works, worth noting in the record.

## Evidence preservation

- Screenshot/export of the secret-scanning alert, with retrieval
  timestamp.
- The commit SHA and the exact matched pattern (never the string's full
  value, if it were ever real) recorded per §4.5.

## Lessons learned

*(blank — fill when run)*

## Corrective actions

| # | Action | Owner | Due |
|---|---|---|---|
| *(blank — fill when run)* | | | |

---

## What this exercise does and does not prove

Running this closes `INCIDENT_RESPONSE_PLAN.md` §12 A-4 and provides the
first genuine operational evidence for RF-05 (`SP_API_REGISTRATION_
REMEDIATION.md` §22.1). It does **not**, by itself, make RF-01 or RF-05
`COMPLIANT` — a single exercise is one data point, not a demonstrated
ongoing control, and A-1/A-2/A-3/A-5 are independent gates that must also
close. See `SP_API_REGISTRATION_REMEDIATION.md` §20.5 E-4 and §22 for the
exact classification impact.
