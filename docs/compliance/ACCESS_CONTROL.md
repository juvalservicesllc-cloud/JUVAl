# JUVAl — Job-Function Access Control (RF-04)

| Field | Value |
|---|---|
| Status | **PARTIAL.** Technical enforcement is IMPLEMENTED and TESTED; the organizational half (named users, quarterly review, offboarding record) is PENDING. |
| Last verified | `2026-08-18` |
| Owner | `ROLE PLACEHOLDER — Security Owner` |
| Amazon finding | **RF-04** — restrict access to Amazon Information by job duties / business function |
| Related controls | `AC-07` (DPP §§1.2–1.4), `AC-14A` (AUP §§4.6–4.9) |

RF-04 has two halves and both must hold. A role matrix nobody enforces is
paperwork; enforcement with no review is drift. This document owns the
organizational half and points at the code that owns the technical half.

---

## 1. Technical enforcement — IMPLEMENTED and TESTED

Implemented in `src/juval/interfaces/api/auth.py`, enforced on every endpoint
in `src/juval/interfaces/api/main.py`.

### Capabilities

Derived from what the API actually exposes — not a speculative hierarchy.

| Permission | Grants | Endpoints |
|---|---|---|
| `runs:read` | View runs, run detail and per-record results | `GET /api/v1/runs`, `GET /api/v1/runs/{id}`, `GET /api/v1/runs/{id}/records` |
| `runs:create` | Upload a supplier workbook and start an analysis | `POST /api/v1/runs` |
| `runs:export` | Download the generated workbook | `GET /api/v1/runs/{id}/download` |

### Roles

| Role | Permissions | Job function |
|---|---|---|
| `viewer` | `runs:read` | Reviews results; cannot start work or extract data |
| `operator` | `runs:read`, `runs:create`, `runs:export` | Performs sourcing analysis day to day |
| `admin` | all | Manages the deployment and the integration |

Least privilege is the default: `viewer` deliberately cannot export, because
export is the data-egress path. An unrecognized role grants **nothing** — it
never falls back to permissive.

### Enforcement properties

| Property | How | Evidence |
|---|---|---|
| Server-side only | FastAPI dependency runs before any handler logic | `test_api_auth.py` |
| Frontend is not a control | Direct API calls bypassing the PWA are rejected | `test_direct_api_call_bypassing_frontend_is_rejected` |
| Token integrity | RS256 signature vs. IdP JWKS; `alg=none` and wrong-key tokens rejected | `test_unsigned_alg_none_token_is_rejected`, `test_token_signed_by_a_different_key_is_rejected` |
| Token scope | Issuer, audience, expiry and required claims all enforced | `test_wrong_issuer_*`, `test_wrong_audience_*`, `test_expired_*`, `test_token_missing_a_required_claim_*` |
| Least privilege | `viewer` refused create and export | `test_viewer_cannot_create_a_run`, `test_viewer_cannot_download_an_export` |
| Fail-closed config | Missing OIDC config raises at startup, never serves unauthenticated | `test_oidc_mode_without_issuer_fails_fast` |
| No credential in logs | Rejected tokens never logged | `test_token_value_never_appears_in_logs` |

Verify: `.venv/Scripts/python -m pytest tests/integration/test_api_auth.py -q`
(33 tests) and `python tools/compliance_check.py` (asserts every route
enforces a permission).

> **Not yet active in production.** Enforcement runs only when
> `JUVAL_AUTH_MODE=oidc`, which requires an IdP tenant (ADR-022, pending
> commercial approval) and a deployment. Today the control is
> `IMPLEMENTED + TESTED`, not `OPERATING`.

---

## 2. Identity register

Amazon requires unique IDs, no shared accounts, and access matched to job
function.

| Principle | Rule |
|---|---|
| Unique identity | One human, one IdP account. The IdP `sub` claim is the only identity key the backend accepts; JUVAl mints no parallel identity |
| No shared accounts | No generic/team/service login for humans. Shared credentials make the access review meaningless and break attribution during an incident |
| Service identities | Tracked separately in `SECRETS.md` §1 — never in the human register |
| Least privilege | Grant the lowest role that lets the person do their job; `admin` is the exception, not the default |

### Approved Users register

| User (role placeholder) | JUVAl role | Business justification | Granted | Last reviewed |
|---|---|---|---|---|
| `ROLE PLACEHOLDER — Operator 1` | | | | |

**Empty by design.** No IdP tenant exists, so no account exists. Populating
this is an EXTERNAL USER ACTION that follows provider selection.

---

## 3. Quarterly access review (DPP §1.2.2)

**Cadence: every quarter**, and additionally after any role change,
offboarding, or security incident.

Procedure:

1. Export the current user/role/last-login list from the IdP.
2. Export the current permission mapping (`auth.py::ROLE_PERMISSIONS`) — it is
   version-controlled, so the reviewed state is reproducible from the commit.
3. For each user confirm: still employed/engaged; role still matches job
   function; no unnecessary elevation; MFA still enrolled.
4. Remove or downgrade anything not justified. Record the change.
5. Review service credentials on the same cadence (`SECRETS.md` §1).
6. File the record; keep it at least 12 months.

Record with `templates/ACCESS_REVIEW_TEMPLATE.md`.

### Review log

| Date | Reviewer | Users reviewed | Changes | Next due |
|---|---|---|---|---|
| — | *No review yet — no accounts exist.* | 0 | — | First review is due one quarter after the first account is created |

---

## 4. Access removal within 24 hours (DPP §1.2.3)

On termination, role change, or suspected compromise:

| # | Step | Deadline |
|---|---|---|
| 1 | Suspend the IdP account | Immediately |
| 2 | Terminate live sessions — suspension alone does not invalidate an already-issued token | Immediately |
| 3 | Revoke provider access (Railway, Vercel, Supabase, GitHub) | ≤24 h |
| 4 | Rotate any shared/provider credential the person could reach (`SECRETS.md` §5) | ≤24 h |
| 5 | Record the completion timestamp as evidence | ≤24 h |

Step 2 is the one most often missed: a disabled account whose refresh token
still works is not revoked access. The backend uses short-lived access tokens
so revocation converges quickly, but session termination at the IdP remains
the authoritative action.

Evidence is the timestamp pair — notification received and access removed —
proving the gap was under 24 hours.

---

## 5. Status and gaps

| Requirement | State | Evidence |
|---|---|---|
| Role/permission model defined | **IMPLEMENTED** | `auth.py`, §1 |
| Backend enforcement | **IMPLEMENTED + TESTED** | 33 tests |
| Negative authorization tested | **IMPLEMENTED + TESTED** | `test_viewer_cannot_*` |
| Frontend not treated as a control | **IMPLEMENTED + TESTED** | direct-call bypass test |
| Unique IDs / no shared accounts | **DOCUMENTED** | §2 — no accounts exist |
| Quarterly review | **DOCUMENTED, NEVER RUN** | §3 |
| ≤24-hour removal | **DOCUMENTED, NEVER EXERCISED** | §4 |
| Supabase RLS policies | **NOT IMPLEMENTED** | `NETWORK_SECURITY.md` N-4 |
| Production operation | **BLOCKED** | Needs IdP tenant + deployment |

`RF-04 = PARTIAL` — technical control implemented and tested; organizational
control documented but not operating, because there are no users to govern.

## 6. EXTERNAL USER ACTION REQUIRED

| # | Action |
|---|---|
| R-1 | Approve the IdP (ADR-022) and create the tenant |
| R-2 | Create individual accounts; enroll MFA; assign the lowest sufficient role |
| R-3 | Populate the §2 register with real users and justifications |
| R-4 | Run the first quarterly access review and file the record |
| R-5 | Exercise the ≤24-hour removal procedure once and record the timings |
