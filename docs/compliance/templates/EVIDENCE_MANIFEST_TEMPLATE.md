# Evidence Manifest — `JUVAL-IR-YYYYMMDD-NN` / `JUVAL-TT-YYYYMMDD`

> Added 2026-08-18 to make `INCIDENT_RESPONSE_PLAN.md` §4.5 (evidence
> preservation) executable instead of abstract — this closes the
> documentation half of `CA-02`, not `CA-02` itself. `CA-02` only closes
> when a real exercise or incident actually produces a filled copy of
> this file.
>
> One row per artifact. List **only** source systems JUVAl actually has —
> do not invent a capability (SIEM, centralized log aggregator, EDR) this
> project does not operate. Never put a secret value, personal contact
> detail, or credential in any field — record identity and timestamps
> only, per §4.5's existing rule.

## Real source systems available today

Do not add a source system to a row below that isn't one of these, or a
documented successor to one of these:

| Category | Source system | What it can actually provide |
|---|---|---|
| Application security log | `interfaces/api/main.py` exception handler | Method + path of the failing request, exception type name — no stack trace, no secret |
| Provider dashboard/audit log | Railway | Deployment history, build/deploy logs, variable-set history (names only) |
| Provider dashboard/audit log | Vercel | Deployment history, build logs |
| Provider dashboard/audit log | Supabase | Project logs, `pg_stat`/query logs where enabled, RLS policy state |
| Provider dashboard/audit log | GitHub | Secret-scanning alerts, push history, Actions run logs, commit history |
| CI run output | `.github/workflows/ci.yml` | `pytest` and `tools/compliance_check.py` output for the relevant run |
| IdP authentication/admin events | *(not available — no IdP tenant exists yet, ADR-022 pending)* | N/A until an IdP is approved and configured |
| Human report | Whoever detected or investigated | A written account, timestamped |

## Manifest

| Incident/Exercise ID | Artifact ID | Artifact category | Source system | Description | Event timestamp (UTC) | Retrieval timestamp (UTC) | Collected by | Storage/custody reference | Integrity/hash | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| | `EV-01` | | | | | | | | | |
| | `EV-02` | | | | | | | | | |

- **Storage/custody reference**: describe *where* the artifact is kept
  (e.g. "incident folder, see `INCIDENT_RECORD_TEMPLATE.md` §Evidence
  preserved") — never an actual filesystem path, drive identifier, or
  credential.
- **Integrity/hash**: a SHA-256 of an exported file, where one was
  actually computed. Write `N/A` rather than leaving it blank if no hash
  was taken — a blank cell is ambiguous between "not applicable" and
  "forgot to check."
- An empty manifest, or one with placeholder rows only, is not evidence of
  anything. Delete the unused example row(s) above before filing a real
  manifest; do not leave `EV-01`/`EV-02` unfilled and call the exercise
  complete.
