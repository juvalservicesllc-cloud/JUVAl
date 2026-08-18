# Access Review Record — `JUVAL-AR-YYYY-QN`

> Quarterly evidence for Amazon finding RF-04 / DPP §1.2.2.
> Never record a password, token or key in this file.

## Metadata

| Field | Value |
|---|---|
| Review ID | `JUVAL-AR-YYYY-QN` |
| Review date (UTC) | |
| Reviewer | |
| Period covered | |
| IdP export retrieved at | |
| Permission mapping reviewed (commit SHA) | |

## Human accounts

| User | IdP role/group | JUVAl role | Last login | Still justified? | MFA enrolled? | Action |
|---|---|---|---|---|---|---|
| | | | | YES / NO | YES / NO | none / downgrade / remove |

## Service credentials (`SECRETS.md` §1)

| Credential (name only) | Purpose | Still required? | Age | Action |
|---|---|---|---|---|
| | | YES / NO | | none / rotate / revoke |

## Checks

- [ ] Every account maps to exactly one identifiable person (no shared or generic logins).
- [ ] Every role matches current job function; no unnecessary elevation.
- [ ] MFA is enrolled on every account.
- [ ] Every departed person's access was removed within 24 hours (`ACCESS_CONTROL.md` §4).
- [ ] Service credentials within their rotation window.
- [ ] `admin` is held by the minimum number of people.

## Changes made

| # | User / credential | Change | Performed at (UTC) | By |
|---|---|---|---|---|
| 1 | | | | |

## Outcome

**Result:** NO FINDINGS / FINDINGS ADDRESSED / FINDINGS OUTSTANDING

*If NO FINDINGS, state what was examined — an empty review is not evidence.*

**Next review due:** `YYYY-MM-DD`
