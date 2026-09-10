# JUVAl — Job-Function Access Control (RF-04)

| Field | Value |
|---|---|
| Status | **PARTIAL.** Technical enforcement is IMPLEMENTED and TESTED; the organizational half (named users, quarterly review, offboarding record) is PENDING. |
| Last verified | `2026-09-10` (endpoint inventory, cookie path and provider citation corrected) |
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
| `runs:read` | View runs, run detail, per-record results, batches and analytics | `GET /api/v1/runs`, `/runs/{id}`, `/runs/{id}/records`, `/runs/{id}/records/{ref}`, `/runs/{id}/analytics`, `/runs/{id}/batch`, `/batches/{id}` |
| `runs:create` | Upload a supplier workbook (or a batch) and start an analysis | `POST /api/v1/runs`, `POST /api/v1/batches` |
| `runs:export` | Download the generated workbook or a record export | `GET /api/v1/runs/{id}/download`, `GET /api/v1/runs/{id}/records/export` |

**Corrected 2026-09-10**: this table listed five endpoints; the API enforces a
permission on **eleven**. The omission understated the control rather than
overstating it, but an access-control document that does not match the routes
is not evidence of anything. Counted from the `Depends(require(...))`
declarations in `interfaces/api/main.py`.

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
| Session cookie is a first-class credential | The BFF's `HttpOnly` cookie resolves to the same `Principal` and the same RBAC, with the same negative tests | `test_api_bff.py::test_session_cookie_authenticates_a_protected_read`, `::test_role_without_permission_is_403_not_401`, `::test_unknown_role_grants_nothing` |
| CSRF on state-changing cookie calls | Double-submit cookie/header, `hmac.compare_digest`; bearer callers exempt (not browsers, cannot be CSRF'd) | `test_state_changing_request_without_csrf_header_is_rejected`, `::_with_wrong_csrf_header_is_rejected`, `::test_logout_requires_csrf` |
| Session store cannot degrade | An invalid production session-store configuration stops startup; no silent fallback to in-memory | `test_api_bff.py` startup section, `test_bff_refresh_and_store_selection.py` |

### 1.1 Two credential shapes, one authorization decision (ADR-034)

Added 2026-09-09, corrected 2026-09-10. Since the BFF, a caller may present
**either** a bearer token **or** an opaque `HttpOnly` session cookie. Both
resolve through `auth.py::current_principal` to the same `Principal` and the
same permission check — there is deliberately no second authorization path.

Order is cookie first, bearer second: the browser never holds a bearer token,
so for it the cookie is the only credential, and a stale `Authorization` header
on a browser request cannot shadow a valid session. Roles come from the ID
token at login and are then held server-side; JUVAl does not call the IdP per
request, which is why a session survives an unreachable IdP but not a *rejected*
refresh (that revokes it).

**Neither shape is active in production**: `JUVAL_AUTH_MODE` is unset.

Verify: `.venv/bin/python -m pytest tests/integration/test_api_auth.py
tests/integration/test_api_bff.py -q` (37 + 34 tests as of 2026-09-10) and
`python tools/compliance_check.py` (asserts every route enforces a
permission).

> **Not yet active in production.** The backend is deployed
> (`https://juval-backend-production.up.railway.app`, since 2026-08-18), so
> deployment is no longer the blocker. Enforcement runs only when
> `JUVAL_AUTH_MODE=oidc`, and that variable is deliberately unset in
> production. The provider decision is **ADR-028** (FusionAuth) with **ADR-031**
> (self-hosted on `juval-server`) — the ADR-022/Okta citation that stood here
> was stale, that ADR is `RECHAZADA`. Turning the variable on requires, and
> does not yet have: a tenant with real users, the migration of ADR-036 applied,
> the public nginx surface measured and deployed, and the frontend integrated
> with the BFF contract. Setting it without those would reject every request.
> Today the control is `IMPLEMENTED + TESTED`, **not `OPERATING`**, and it
> cannot be cited to Amazon as satisfied.

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
| Supabase RLS | **ENABLED, FAIL-CLOSED, VERIFIED LIVE 2026-08-18** (zero policies, by design) | `NETWORK_SECURITY.md` §3.1 |
| Backend deployed | **DONE 2026-08-18** — `https://juval-backend-production.up.railway.app` | `PROJECT_PLAN.md` |
| Production operation (auth enforcement) | **BLOCKED** — backend is deployed, but `JUVAL_AUTH_MODE` is deliberately unset (auth stays disabled until an IdP is approved) | Needs IdP tenant, not deployment — deployment is done |

`RF-04 = PARTIAL` — technical control implemented and tested; organizational
control documented but not operating, because there are no users to govern.

## 6. EXTERNAL USER ACTION REQUIRED

| # | Action |
|---|---|
| R-1 | Create the tenant on the approved IdP (ADR-028 FusionAuth, ADR-031 self-hosted; ADR-022 is `RECHAZADA`) |
| R-2 | Create individual accounts; enroll MFA; assign the lowest sufficient role |
| R-3 | Populate the §2 register with real users and justifications |
| R-4 | Run the first quarterly access review and file the record |
| R-5 | Exercise the ≤24-hour removal procedure once and record the timings |
