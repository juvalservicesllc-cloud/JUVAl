# RF remediation recovery — 2026-09-18

Status: **PARTIALLY IMPLEMENTED** overall; all independently actionable work in
this recovery completed. Remaining RF closure is human/external blocked.
Authority: operator's reboot-recovery instruction, with MFA and frontend frozen.
This is a repository recovery and scoped verification record, not a production
or Amazon certification. No new incident or organizational action is claimed.

## Recovered state

- KNOWN_PRE_REBOOT_CHECKPOINT and initial CURRENT_HEAD:
  `59bc3a1cf932c89f65ba4d263cd622b30857b7e1`.
- `git status --short` and `git status --short --untracked-files=all`: empty.
- `git log --oneline --decorate -15` and `git log 59bc3a1..HEAD`: no commits
  after the checkpoint. No legitimate interrupted tracked/untracked work found.
  Ignored runtime artifacts are not discarded, inspected for secrets or treated
  as evidence of a completed remediation loop.
- The checkpoint prepared a real MFA runner, not an RF-01/02/04/05 closure.
  Prior commits already verified callback containment; this recovery did not
  rerun it. Git evidence cannot establish whether an unrecorded process ran.
- No reset, checkout, clean, fetch or push. Remote synchronization NOT_VERIFIED.

## RF classification and continuation, in priority order

| RF | Recovery classification | Completed evidence reused / correction in this recovery | Remaining closure |
|---|---|---|---|
| RF-01 | HUMAN_BLOCKED; control PARTIAL | IRP §§1–10 define detection triggers, containment, named roles/deputy, escalation, Amazon determination, notification within 24 hours of detection, six-month review and corrective actions. §12 records approval and contact custody; first human tabletop exists. No missing procedure requiring another implementation found. | TABLETOP-002 needs real participant decisions/timing, a notification draft never sent, CA-01 containment decision and CA-02 completed evidence manifest. No fabricated exercise/notification. |
| RF-02 | EXTERNAL_BLOCKED; control PARTIAL | Existing perimeter/loopback/nginx evidence reused with its dates. Fresh read-only host observations below. Added a current reconciliation above stale historical network audit claims. | Effective firewall rule enumeration and external-denial evidence after reboot, attribution/need for port 631, workstation F-01 closure/exclusion, selected public ingress/TLS/logging evidence and production authorization. Service-active is insufficient. |
| RF-04 | HUMAN_BLOCKED; backend IMPLEMENTED / BEHAVIORALLY_VERIFIED in synthetic tests; control PARTIAL | Existing bearer/cookie tests and source reviewed. Viewer read only; operator/admin share three current API capabilities; missing/unknown roles deny in OIDC mode. Eleven main.py routes bind permissions. Corrected docs and module docstring that overstated full RF closure; reused named Security Owner. | Human approved-user duties/register, access review, timed removal drill including BFF sessions, infrastructure admin grants and production activation evidence. Development auth remains disabled by default and permissive; no silent policy change. |
| RF-05 | HUMAN_BLOCKED; external alert reconciliation also pending; control PARTIAL | Approved IRP, assigned owners, first tabletop, CA-01/02 procedural fixes and review deadline reused. Corrected stale Dependabot-disabled/no-remediation-ever assertions against later durable evidence. | Actual TABLETOP-002 and recurring review/exercise evidence; contact availability is not freshly verified. CA-01/02 remain open. Review due 2027-02-18 was not reset. Current GitHub alerts require authorized account evidence. |

No item is NOT_STARTED or IN_PROGRESS_INTERRUPTED on available Git evidence.
Existing technical/documentation portions are adequately complete for the current
scope; the RFs as a whole are not VERIFIED or TECHNICALLY_COMPLETE. Preparing a
form does not satisfy the remaining human gates. Existing approval/role assignment
is retained: no repeated signature request and no invented new personnel decision.

## RF-02 post-reboot observations

Read-only measurement started `2026-09-18T21:43:27Z`:

- `ss -H -ltn`: SSH 22 and 631 on IPv4/IPv6 all interfaces; 9011/9012 wildcard;
  PostgreSQL 5432 on 127.0.0.1; viewer 6080 on 127.0.0.1, 5900 on loopback
  IPv4/IPv6; DNS 53 on loopback. No 9222, 5173 or 8000 TCP listener observed.
- `ss -H -lun`: loopback DNS and interface-scoped DHCP 68/546. Observation is
  listener binding only, not packet reachability or proof that a service is safe.
- `systemctl is-active ufw fail2ban ssh systemd-journald`: all active.
  `systemctl is-enabled unattended-upgrades logrotate.timer`: both enabled.
- World-readable `/etc/default/ufw`: INPUT/FORWARD DROP, OUTPUT ACCEPT,
  IPv6 yes; `/etc/ufw/ufw.conf`: ENABLED=yes. These files do not enumerate live
  rules, prove rule loading, or replace a privileged/external check.
- 631 attribution NOT_VERIFIED: `ss -H -ltnp 'sport = :631'` exposes no owner;
  `systemctl is-active cups` returned inactive, `/etc/cups/cupsd.conf` absent,
  socket inventory returned no matching cups/631 entry. Do not infer CUPS or
  malware from a port number. No process stopped and no packet probe performed.

Next operator network evidence: obtain effective `sudo ufw status verbose`
locally (never provide passwords), identify the 631 listener through privileged
local inspection, and corroborate denied reachability from the applicable network
boundary. The historical 2026-08-27 denial of 9011/9012 is not refreshed by these
checks. Remediation, if needed, requires a separate authorized network action.
No UFW/SSH/host configuration change, public exposure or sudo was attempted.

## Validation and metrics

Relevant regression executed once on recovered runtime code:

```
.venv/bin/python -m pytest -q tests/compliance/test_compliance_check.py tests/integration/test_api_auth.py tests/integration/test_api_bff.py tests/unit/test_auth_hardening.py
127 passed, 1 warning in 11.51s
```

Warning: Starlette/httpx TestClient deprecation. No skips. Tests use synthetic
credentials and in-process test clients, not real authentication or MFA. Runtime
code was not changed; auth.py's only edit is its module description. Existing
nginx/callback/frontend tests were not repeated for documentation corrections.

Offline compliance (existing `check_incident_response_plan`,
`check_auth_posture`, `scan_for_secrets`): **8 PASS / 1 WARN / 0 FAIL**.
The warning is the preserved historical IRP role-placeholder log entry, not
missing current role approval. Current-tree pattern scan: **526 files, no
findings**; ignored secrets and Git history are outside that scan's scope.
Dependency network audit and GitHub alerts were not queried. `git diff --check`
and `git diff --exit-code 59bc3a1 -- frontend/ frontend-next/ demo/` passed.

ADR-040 model 1.2 was regenerated from exact committed ref
`59bc3a1cf932c89f65ba4d263cd622b30857b7e1` with `JUVAL_EVIDENCE_REF` and
`project-portal/scripts/sync.mjs`, then measured with `scripts/measure.mjs`.
The initially available generated snapshot indexed 32f0ee9 and was not passed
off as current. Generated output is ignored, not a frontend source change.

| Dimension | Before | After recovery (no qualifying evidence promotion) |
|---|---|---|
| Implementation | 44/68 = 65% | 44/68 = 65% |
| Verification | 17/68 = 25% | 17/68 = 25% |
| Production | 0/12 = 0% | 0/12 = 0% |
| Security | 5/16 = 31% | 5/16 = 31% |
| Amazon | 0/18 = 0% | 0/18 = 0% |

No ADR or measurement rule changed. No aggregate percentage. Recovery edits
supply no production evidence and do not close roadmap criteria.

## Freeze, decisions and self-review

MFA_FREEZE_STATUS = ACTIVE. REAL_MFA_EXECUTED = NO; historical preflight PASS
and callback synthetic boundary remain unchanged. Marcus ABSENT / tenant 0
are prior HUMAN_REPORTED/HUMAN_ADMIN_READBACK, not new machine verification.
No identities, secrets, provider policy/redirect mutations, real login, API-key
experiment, production auth, deployment, live DB installer or Amazon reapplication.

APPROVED: read-only recovery, existing-policy documentation corrections, scoped
synthetic regression and local commit under the operator instruction. PENDING:
public boundary/production activation, personnel decisions and external evidence.
No business/domain/architecture/security policy decision was silently introduced.

Ponytail is unavailable in this environment (no listed skill/callable tool).
Manual simplicity and self-review: no dependency, abstraction, permission,
redundant test or speculative feature added; history preserved; docs distinguish
implementation, synthetic behavior, historical human reports and fresh observation.
No frontend change. No claim that a policy document proves operational compliance.

Stop condition 2: every remaining RF closure needs human/external/security
participation. Next human checkpoint: resolve current network evidence (including
631) and schedule TABLETOP-002; retain MFA freeze. No further independently
justified RF implementation identified. Next autonomous work becomes useful when
non-secret network/tabletop evidence arrives: reconcile it without changing the
perimeter or fabricating results. COMMITS_PUBLISHED = 0.
