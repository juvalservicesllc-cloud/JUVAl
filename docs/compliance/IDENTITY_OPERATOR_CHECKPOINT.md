# Identity operator checkpoint — second wave

Date: 2026-09-10. PREPARED_NOT_EXECUTED. This procedure adds no authorization
for live migration, users, passwords/TOTP, DNS, purchases or Amazon submission.
Current state and asset-only procedure: ../IDENTITY_SECURITY_READINESS.md.

## One-shot session migration approval packet

1. Identify exact environment/project/database/schema, migration Git SHA and
   deployment version. Review `supabase/migrations/20260909000004_identity_sessions.sql`
   and its down migration. Confirm this is the intended production project.
2. Record current tables, owner, RLS/FORCE flags, policies and indexes using
   metadata only. Never read token rows. Backend role must own both tables;
   anonymous/authenticated browser roles must not gain access. Existing tables
   with incompatible definitions are STOP, not an excuse for DROP/repair.
3. Verify protected backup completion AND restore rehearsal, application rollback
   artifact, keyring custody and change-window owner. Schema rollback deletes
   sessions: obtain explicit approval for that consequence separately.
4. Confirm actual connection endpoint/pooler supports transaction advisory locks
   (ADR-039), encrypted connections, bounded connection attempts, and capacity
   for one additional connection per concurrent refresh. Repeat the disposable
   contract against an approved isolated equivalent endpoint first.
5. Present the exact migration, target, owner, backup/restore evidence and rollback
   consequence together for explicit live-migration approval. Approval remains
   PENDING; do not execute the remaining steps on production now.
6. After approval, pause login admission, apply the reviewed SQL transaction as
   the intended owner, read back metadata and run `verify_session_database` with
   the real backend role. No automatic repair or anonymous fallback.
7. Configure secret keyring/DSN privately. Verify startup rejects missing keyring,
   missing table, wrong owner, unsafe RLS/policies and unavailable DB. Confirm
   ordinary DB errors do not expose DSNs in operational logs.
8. With separately approved disposable login, prove cross-worker callback,
   replay refusal, session reload after backend restart, expiry, concurrent
   refresh, CSRF negatives, key rotation compatibility and logout/revocation.
   Verify an unprivileged role cannot select either table. Record counts/status,
   never cookies/tokens/rows. Actual IdP/pooler tests remain NOT_EXECUTED.
9. Schedule existing purge_expired in the chosen backend environment; alert on
   purge failures/row growth/connection saturation. Keep old decryption keys
   until no retained rows require them. No runtime scheduling changed here.
10. Reopen only after gates pass. On failure keep authentication unavailable;
    roll back only within the explicit authorization. Never enable anonymous
    production access. Document restoration and end-of-window owner signoff.

Scratch evidence: session contract 48 PASS / 2 memory-only SKIP, including repeat
migration/down/reapply, sentinel preservation, unsafe ownership/RLS rejection,
cross-instance state, token encryption, exclusion and exception cleanup. The
private-cluster restart probe additionally preserves live/revoked/consumed state. Backend
restart/process persistence and real endpoint behavior are different claims;
current adapter-instance tests do not by themselves prove a deployed restart.
`LIVE_MIGRATION_AUTHORIZED=NO`; `LIVE_MIGRATION_PACKET_READY=YES`.

## RF03 single human session

`RF03_HUMAN_RUNBOOK_READY=YES`; `RF03_EXECUTION_AUTHORIZED=NO`.
Approval must name the isolated/disposable users, tenant/application, allowed
paths, cleanup owner and window. Never use an administrator as lockout subject.
Use only a synthetic disposable email under `.invalid`; do not use a deliverable
mailbox or a real person's identity. If email delivery is required by the effective
flow, mark that case BLOCKED and obtain a separately approved isolated delivery
procedure; do not silently substitute a real address or bypass verification.
Record initial tenant/app user counts and existing disposable identifiers
privately; count zero must be observed, never assumed. Do not change global
policy to shorten the test. If no effective create/change/reset route exists,
mark that case BLOCKED instead of testing an unrelated path as production.

| Case | Action / result required |
|---|---|
| RF03-B0 | Confirm exact IDs, provider version, baseline policy and effective route; record no secret fields |
| RF03-P0 | Valid password positive control succeeds and reaches required MFA |
| RF03-P6 | BLOCKED_BY_ARCHITECTURE under ADR-035: do not set passwordChangeRequired in the current JUVAl tenant. A future isolated disposable test requires explicit authorization covering that exception and its effective change route; only then test mandatory change, old-password bypass refusal and MFA preservation |
| RF03-P1..P5 | One negative each: too short, missing uppercase, lowercase, digit, symbol; verify intended rejection reason; keep all other requirements valid |
| RF03-C6 | First-name, last-name, case-variant and normalized-name negatives on every approved create/change/reset path, with a compliant non-name control on each; no real personal names in report |
| RF03-H1 | Reject password reuse against observed history; include positive new-password control |
| RF03-H2 | Immediate change obeys actual minimum age; maximum-age result needs elapsed-time/provider evidence and may remain pending after this session |
| RF03-M1..M4 | Required enrollment, missing/wrong TOTP rejection, valid TOTP acceptance, consumed challenge/code replay refusal; all input private |
| RF03-L1 | Positive login first; wrong attempts up to observed threshold, then valid-password refusal while locked; record times/counts only |
| RF03-L2 | After actual configured interval, correct login recovers; no clock/policy bypass. Reserve at least the configured lockout interval (historical template 30 minutes) |
| RF03-R1 | When BFF active, role negatives, CSRF negatives and logout invalidate application access; otherwise BLOCKED |
| RF03-Z0 | Revoke test sessions, remove only newly created disposable users, restore temporary settings, read back counts and baseline; pre-existing users preserved |

Batch order: baseline/positive, password and Control 6/history, MFA, lockout,
cleanup planning during the lockout wait, timed recovery, final cleanup/readback.
Do not promise all age/history cases close within one short session.

Sanitized evidence schema: case ID, UTC timestamp, tested Git SHA, provider
version, environment classification, route PATH ONLY, expected result, observed
status/reason category, PASS/FAIL/BLOCKED/NOT_EXECUTED, cleanup status. No raw
HTML/HAR/screenshots of credential fields, bodies, user names, passwords, TOTP,
state/nonce, codes, cookies, tokens or PKCE verifier. Artifact report must be
reviewed and secret-scanned before Git. Do not treat an infrastructure 401/403
as password-policy enforcement. Stop on wrong tenant, unexpected existing user,
real-user impact, unintended privilege or failed cleanup. Retain no test secrets.
`CONTROL_6_AMAZON=PARTIALLY_SATISFIED` until effective-path evidence warrants more.

## Off-host backup/recovery proposal

Existing backup.sh takes daily FusionAuth dumps/config copies with 14-day local
retention and validates dump readability. It does not encrypt or transfer them
off-host. A successful timer exit does not prove restore or host-loss recovery.

| Threat | Required control / residual |
|---|---|
| Disk/host loss | Independent off-host destination and recovery host; same disk/account alone insufficient |
| Ransomware or operator deletion | Versioning/immutable retention, separate restore/delete authority; upload credential cannot delete retained copies |
| Backup theft | Client-side authenticated encryption before upload, TLS transport, restricted destination access; provider encryption alone does not isolate provider access |
| Key loss/compromise | Separately protected recovery key and access-tested escrow; rotate on compromise, retain decryption capability for authorized retained backups |
| Corrupt/incomplete dump | Checksums plus isolated actual restore, not only pg_restore --list; verify schema/application startup privately |
| Session rollback | Restored session backups can resurrect revocations and consumed OAuth exchanges; invalidate session/transaction state before reopening |

Proposed targets, PENDING operator/business acceptance: daily off-host recovery
points, RPO <=24h conditional on successful upload, RTO <=8h target NOT_MEASURED;
14 daily + 8 weekly encrypted copies, no indefinite retention. Final retention
must match data/privacy obligations. Alerts when newest verified off-host copy
exceeds 24h, on failed upload or failed monthly isolated restore. Quarterly
fresh-host recovery rehearsal; measure actual RTO/RPO before claiming achieved.

Destination selection packet: approved region/jurisdiction, owner, cost/capacity,
versioning/immutability, retention deletion policy, TLS, least-privilege upload
and separate restore credentials, audit trail, recovery-key custody and a
reachable replacement host. No destination or paid service selected here.

Operator restore sequence: isolate replacement host and block public auth;
retrieve chosen encrypted copy privately, verify integrity, decrypt only in
protected temporary storage, restore to isolated DB with compatible versions,
verify FusionAuth configuration and issuer without public activation, invalidate
BFF sessions/transactions under approved destructive-recovery authority, validate
roles/policies and non-secret controls, measure elapsed recovery/data age, then
approve cutover and securely remove temporary plaintext. Never test by restoring
over the stable live database. Record backup ID/time/hash and sanitized outcomes,
not dump contents, keys or database credentials.
`OFF_HOST_DESTINATION=HUMAN_SELECTION_PENDING`; no transfer/restore executed.

## Executable read-only preflight — third wave

Run `.venv/bin/python tools/session_migration_preflight.py` offline first. It
prints hashes of the exact up/down SQL, pending target/backup/admission/pooler
checks and explicit absence of migration authorization. It performs no DB call,
including when runtime variables happen to exist.

Only for an intentionally selected, already-migrated DB, use `--check-database`
with JUVAL_SESSION_DB_URL provided privately. There is no product-DB fallback.
This reuses bounded metadata-only readiness checks, reads no session rows and
never applies SQL migrations. Missing/unmigrated/unsafe schema returns failure;
no repair. Success does not attest target identity, backup, pooler behavior or
production approval. For a new unmigrated target, retain the expected failure
and perform the before-migration metadata/backup checklist above with the operator.
