# Incident Record — `JUVAL-IR-YYYYMMDD-NN`

> Copy this file to start an incident. Fill fields as you go; do not wait for
> certainty. **Never paste a secret value into this record** — name the
> credential and record its rotation time instead.

## Identification

| Field | Value |
|---|---|
| Incident ID | `JUVAL-IR-YYYYMMDD-NN` |
| `detected_at` (UTC, ISO-8601) | |
| Detected by | |
| Detection source | log / provider alert / IdP event / secret scan / human report / third party |
| Incident Commander | |
| Severity (§3) | SEV-1 / SEV-2 / SEV-3 / SEV-4 |
| Current status | OPEN / CONTAINED / RECOVERING / CLOSED |
| `closed_at` (UTC) | |

## Summary

*What happened, in three sentences or fewer. Write this first, revise it last.*

## Amazon Information determination (§4.4)

| Question | Answer | Evidence |
|---|---|---|
| Did the affected system hold/process/transmit Amazon Information? | | |
| Were SP-API credentials in scope? | | |
| Do logs show actual access, or only possible access? | | |
| Is Amazon PII involved? | | |

**Determination:** `AMAZON_INFORMATION_CONFIRMED` / `AMAZON_INFORMATION_SUSPECTED` / `AMAZON_INFORMATION_RULED_OUT`

*If RULED_OUT, state the evidence that ruled it out. "We think not" is not a determination.*

## Amazon notification (§5) — required for CONFIRMED and SUSPECTED

| Field | Value |
|---|---|
| Required by (`detected_at` + 24 h) | |
| Sent at (UTC) | |
| Sent by (IMPOC) | |
| Sent to | `security@amazon.com` |
| Within 24 hours? | YES / NO |
| If NO — why, and corrective action | |
| Amazon reply / reference | |

## Timeline

| UTC timestamp | Actor | Action | Evidence reference |
|---|---|---|---|
| | | Detection | |
| | | Incident declared, IC assigned | |
| | | Containment begun | |
| | | Credentials revoked | |
| | | Amazon notified | |
| | | Recovery complete | |
| | | Closed | |

## Credentials revoked (§4.3)

| Credential (name only — never the value) | Rotated at (UTC) | By | Old credential confirmed dead? |
|---|---|---|---|
| | | | |

## Evidence preserved (§4.5)

| Item | Location | Retrieved at (UTC) | Secrets redacted? |
|---|---|---|---|
| | | | |

## Root cause

*Which control failed. Not who was on duty.*

## Corrective actions

| # | Action | Owner | Due | Status |
|---|---|---|---|---|
| 1 | | | | |

## Postmortem (§7 — required for SEV-1/SEV-2 within 5 business days)

- Time to containment:
- Time to notification:
- Was the 24-hour obligation met?
- Does the incident response plan need to change? If yes, version bumped to:
