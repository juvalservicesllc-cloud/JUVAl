# FusionAuth 1.69.0 identity lab — specification and blocking status

**Date: 2026-09-09.** Status: **EXECUTED AND TORN DOWN.** Option B was
authorised by the operator, the lab was built, L-1…L-4 and Control 6 were
answered, and every lab artifact was destroyed. **No production identity state
was touched at any point.**

Sections 1-7 are the design as written before execution and are preserved
unchanged. **Section 9 onward records what actually happened**, including two
design assumptions that execution falsified.

Governing decision: ADR-033 (`Propuesta`, approved in principle for this
phase) — documentation/source evidence first, runtime reproduction only where
uncertainty remains, production identity state is never the experiment
environment, reproduction is isolated and disposable.

---

## 1. Production baseline (read-only, captured before any lab work)

| Property | Value at start | Value after this pass | Verdict |
|---|---|---|---|
| Host | `juval-server` | — | **The lab host *is* the production host.** This raises the isolation bar; see §3 |
| `fusionauth-app` `MainPID` | `369334` | `369334` | unchanged |
| `fusionauth-app` `NRestarts` | `0` | `0` | unchanged |
| `fusionauth-app` `SubState` | `running` | `running` | unchanged |
| `ActiveEnterTimestamp` | `Mon 2026-09-07 18:46:43 UTC` | identical | unchanged — **not restarted** |
| Listening | `*:9011`, `*:9012` | identical | unchanged |
| `git HEAD` | `26b4f9d` | `26b4f9d` | unchanged |
| `frontend/`, `frontend-next/`, `demo/` | clean | clean | **unchanged** |

Pre-existing condition, observed and **not acted upon**: `systemctl status`
reports *"The unit file, source configuration file or drop-ins of
fusionauth-app.service changed on disk. Run 'systemctl daemon-reload'"*. This
predates this session. Running `daemon-reload` is a production action and was
not performed.

---

## 2. Incident — unintended LXD snap installation during capability probing

**This must be read before anything else in this document.**

While inventorying container runtimes, the probe `lxc --version` was executed.
On Ubuntu 24.04, `/usr/sbin/lxc` is not the LXD client: it is a **shim from the
`lxd-installer` package** which installs the LXD snap on first invocation. The
probe therefore triggered an installation:

```
snap changes ->  ID 6   Done   today at 14:50 UTC ... 14:51 UTC
                 Install "lxd" snap from "5.21/stable/ubuntu-24.04" channel
snap list    ->  lxd  5.21.7-1018661  rev 40585  5.21/stable/ubuntu-24.04
```

**This was not intended, was not approved, and violates the standing rule that
nothing is installed silently.** It is recorded here rather than resolved
quietly.

**Measured blast radius** (all read-only checks, this pass):

| Check | Result |
|---|---|
| `snap.lxd.daemon` | `inactive` |
| `snap.lxd.activate` | `inactive` |
| `lxdbr0` bridge | **does not exist** |
| Network interfaces | `lo`, `wlo1` only — unchanged |
| `lxd init` | never run |
| Production `fusionauth-app` MainPID / NRestarts | `369334` / `0` — unchanged |
| Disk | 79 G available; snap adds ~150 MB |

LXD was installed but **never initialised**, so it created no bridge, no NAT,
and no container. The firewall could **not** be inspected — `nft list ruleset`
and `iptables -S` both require root — so "no firewall rule was added" is
**stated as unverified**, not claimed. `lxd init` is the step that would add
rules, and it was not run.

**Remediation requires the operator** (`snap remove lxd`, and optionally
`apt purge lxd-installer` so the shim cannot fire again). The agent cannot
remove it: no passwordless sudo. **Recommended: remove it.** The lab design
below does not use LXD, and an idle, uninitialised container manager on the
host that holds JUVAl's only repository copy is pure surface with no benefit.

**Process correction adopted for the rest of this phase:** capability probing
uses `command -v` / `ls -l` / `dpkg -S` only. No binary is invoked — not even
with `--version` — until its provenance is known, because on this distribution
an invocation can *be* an installation.

---

## 3. Capability inventory (measured, 2026-09-09)

| Capability | State | Consequence for the lab |
|---|---|---|
| `docker` | **ABSENT** | Not available, and out of scope by standing rule (no Docker in JUVAl architecture without an ADR) |
| `podman`, `nerdctl`, `systemd-nspawn` | **ABSENT** | — |
| `lxd` | present only by the accident in §2; uninitialised | **Rejected** — initialising it means bridges/NAT on the production host, against ADR-031's zero-new-network-rule posture |
| `/usr/local/fusionauth` | `drwxr-x--- fusionauth:root` — **unreadable by `juval`** | The installed 1.69.0 binaries **cannot be reused without sudo** |
| Bundled JRE (`/usr/local/fusionauth/java/current`) | unreadable | same |
| System Java | **none installed** (`/usr/bin/java` does not exist) | A JRE must be obtained for any non-sudo path. FusionAuth 1.69 requires **Java 21** |
| PostgreSQL server | 16.15, cluster `16-main` running on `127.0.0.1:5432` | Production cluster. **Not to be used for the lab** |
| `initdb`, `pg_ctl`, `postgres` binaries | `-rwxr-xr-x root:root` — **world-executable** | **An isolated PostgreSQL cluster can be created entirely in user space, no sudo.** The database half of the lab is solved |
| `psql` client | 16.15 present | Available |
| Passwordless sudo | **NO** (`sudo: a password is required`) | Any root action needs the operator, interactively |
| Postgres access as `juval` | password required, none held | Cannot use the production cluster even if it were desirable |
| Free RAM / disk / CPU | 11.1 GB available / 79 GB / 4 cores | Ample for a second 768 MB JVM + a second PG cluster |

**Conclusion: the lab cannot be built with what is currently reachable.** Every
mechanism needs either sudo or a download. Per the phase rules, work stops here
and the decision goes to the operator.

---

## 4. Isolation analysis — mechanisms evaluated

| Option | Isolation quality | Needs | Verdict |
|---|---|---|---|
| **A. Docker/Podman** | Excellent | Install a container runtime (sudo, apt) | **Rejected** — standing no-Docker rule; would need its own ADR to introduce even as tooling, and the cheaper options below do not require it |
| **B. User-space bundle + private PG cluster** | **Sufficient** — separate JVM, separate ports, separate PG *cluster* (own postmaster, own data dir, own socket), separate filesystem tree, unprivileged UID | Download `fusionauth-app-1.69.0.zip` + a Java 21 runtime into the scratchpad | **RECOMMENDED** — the only option needing no root at all |
| **B′. Same as B, reusing installed binaries** | Same as B | `sudo cp -a /usr/local/fusionauth/{fusionauth-app,java}` to a scratch dir | **Acceptable alternative** — no download, but needs one sudo command and reads the production install tree |
| **C. LXD container** | Excellent | sudo, `lxd init`, bridge + NAT on the production host, user added to `lxd` group | **Rejected** — network changes on the host holding the only repository copy; disproportionate |
| **D. Second tenant in the production instance** | **Insufficient** | none | **Rejected** — L-1/L-3 are instance- and process-level behaviours; a tenant boundary shares the JVM, the caches and the configuration. This is precisely what ADR-033 forbids |
| **E. Second FusionAuth against the production PG cluster** | **Insufficient** | postgres superuser | **Rejected** — shares the database process with production FusionAuth data |

**Docker is not required.** That question resolves itself: the recommended
mechanism introduces no container runtime, so no ADR-033 authorisation question
about Docker arises.

---

## 5. Recommended design — Option B in detail

Everything lives under one disposable root, `$LAB` (session scratchpad, outside
the repository). Nothing is written to the repository except the results
document.

```
$LAB/
  pgdata/            isolated PostgreSQL 16 cluster (initdb, unprivileged)
  pgsock/            private unix socket dir (cluster is NOT on a TCP port)
  fusionauth/        extracted fusionauth-app-1.69.0.zip
  jre21/             extracted Java 21 runtime
  config/            fusionauth.properties + kickstart.json
  logs/
```

| Dimension | Design | Why production cannot be affected |
|---|---|---|
| **Ports** | FusionAuth HTTP `127.0.0.1:9411`, management `127.0.0.1:9412` | Production holds `9011`/`9012`; the lab binds explicitly to loopback on unused ports. Verified free in the port map |
| **Database** | Own cluster via `initdb -D $LAB/pgdata`, started with `pg_ctl` listening **only on a private unix socket** in `$LAB/pgsock`, `-h ''` (no TCP at all) | A different postmaster, different data directory, different socket. It cannot see, and is not reachable from, the production cluster on `:5432`. No TCP port is opened at all |
| **Filesystem** | Everything under `$LAB`, owned by `juval` | `/usr/local/fusionauth` is never written, and is not even readable |
| **Process** | Own JVM, `-Xmx512M`, started in the foreground under this session; no systemd unit, never enabled | No unit file is created, so nothing survives a reboot and `systemctl` is never invoked |
| **Network exposure** | Loopback only; no nginx change; no `ufw` rule; no tunnel | ADR-031's zero-new-network-rule posture is preserved literally |
| **Secrets** | Lab-only, process-local, generated per run; no production tenant/application id, no production issuer, no production API key, no production user, no SMTP | Nothing production-derived enters the lab, so nothing lab-derived can leak back |
| **Config isolation** | `-Dfusionauth.config.directory=$LAB/config` etc. | The production config directory is never referenced |
| **Teardown** | `pg_ctl -D $LAB/pgdata stop -m immediate`; kill the lab JVM by its own PID; `rm -rf $LAB` | Nothing outside `$LAB` is removed. No shared package, no production file |

**Determinism.** Setup is one script and one Kickstart file. Kickstart runs only
against an empty instance (*"Kickstart expects an untouched FusionAuth instance.
The Kickstart process will only run if no API keys, users or tenants exist"*),
which is itself a safety property: it is structurally incapable of running
against the production instance's populated database.

### 5.1 Command sequence (reviewed by the operator before it is ever run)

Marked **UNVERIFIED-UNTIL-RUN**: written from official documentation, not yet
executed, because execution is exactly what is being requested.

```
# 1. isolated PostgreSQL cluster - no sudo, no TCP port
/usr/lib/postgresql/16/bin/initdb -D "$LAB/pgdata" -U labadmin --auth=trust
/usr/lib/postgresql/16/bin/pg_ctl -D "$LAB/pgdata" -l "$LAB/logs/pg.log" \
    -o "-h '' -k $LAB/pgsock" start
psql -h "$LAB/pgsock" -U labadmin -d postgres -c 'CREATE DATABASE fusionauth_lab'

# 2. runtime + app  (THE STEP NEEDING APPROVAL - see section 6)
#    https://files.fusionauth.io/products/fusionauth/1.69.0/fusionauth-app-1.69.0.zip
#    plus a Java 21 runtime (FusionAuth 1.69 requires Java 21)

# 3. configuration - $LAB/config/fusionauth.properties
#    database.url=jdbc:postgresql://<unix-socket>/fusionauth_lab
#    fusionauth-app.http.port=9411
#    fusionauth-app.management.port=9412
#    fusionauth-app.kickstart.file=$LAB/config/kickstart.json
#    fusionauth-app.url=http://127.0.0.1:9411
#    search engine: database (no Elasticsearch)

# 4. start in the foreground, loopback only
"$LAB/fusionauth/fusionauth-app/bin/start.sh"

# 5. run the matrix in section 7, then tear down (section 5)
```

### 5.2 Kickstart design

One tenant, one application, mirroring
`deploy/fusionauth/tenant-password-policy.template.json` — `minLength 12`,
`requireMixedCase`, `requireNumber`, `requireNonAlpha`, history 10, lockout
10 attempts / 30 minutes, `multiFactorConfiguration.loginPolicy = Required`,
TOTP enabled (HmacSHA1 / 6 digits / 30 s). Kickstart `requests` can PATCH the
tenant, so every one of these is expressible declaratively.

Synthetic identities only. No real names. Passwords are generated per run into
process-local variables, are never echoed, never passed as CLI arguments,
never written to a file, and never appear in output — only symbolic case ids
and outcomes are recorded.

---

## 6. What the operator must approve

Exactly one decision, with two acceptable answers. **Nothing proceeds without
it.**

| | **Option B (recommended)** | **Option B′** |
|---|---|---|
| Action | Download `fusionauth-app-1.69.0.zip` (~250 MB) and a Java 21 runtime (~200 MB) from official sources into the session scratchpad | One command: `sudo cp -a /usr/local/fusionauth/fusionauth-app /usr/local/fusionauth/java <scratch>/` then `sudo chown -R juval <scratch>` |
| Root needed | **None** | One `cp` + one `chown`, entered by the operator |
| apt / snap / systemd | **None** | **None** |
| Touches the production install | No | Reads it (copy only) |
| Network egress | Yes, two official downloads | None |
| Version fidelity | 1.69.0 by URL | **Byte-identical to production** |
| Risk | Third-party binaries land on the production host, in a disposable directory | Momentary root; the copy is read-only with respect to the source |

Secondary, independent of the above: **remove the accidentally installed LXD
snap** (`snap remove lxd`, and consider `apt purge lxd-installer`). Recommended.

Neither option installs Docker, changes any systemd unit, opens any port beyond
loopback, adds any firewall rule, touches nginx, or writes to
`/usr/local/fusionauth`.

---

## 7. Test matrix — all cases NOT_TESTED

FusionAuth version under test: **1.69.0** (to be asserted from
`GET /api/status` on the lab instance before any case runs; a version mismatch
aborts the run).

| test_id | Preconditions | Action | Expected (official docs) | Observed | Result | Evidence class |
|---|---|---|---|---|---|---|
| L1-01 | `loginPolicy=Required`, TOTP enabled, user with **no** MFA method | Hosted login with correct password | Login blocked; hosted pages do not enrol | — | **NOT_TESTED** | — |
| L1-02 | same | Inspect the exact page/state reached | Undocumented at page level | — | **NOT_TESTED** | — |
| L1-03 | same, via `POST /api/login` (lab key) | Compare API status to hosted behaviour | `242` or a block | — | **NOT_TESTED** | — |
| L2-01 | policy active | Set password via **admin console** — too short / no number / no non-alpha / no mixed case | Rejected by tenant rules | — | **NOT_TESTED** | — |
| L2-02 | policy active | Set password via **admin API** (lab key) — same four classes | Rejected | — | **NOT_TESTED** | — |
| L2-03 | `passwordChangeRequired=true` | **Forced change** — same four classes | Rejected | — | **NOT_TESTED** | — |
| L2-04 | Community edition | Determine whether a **self-service** change surface exists at all | Self-service account portal is a **paid** feature; `/password/forgot` is the only Community self-service path | — | **NOT_TESTED** | — |
| L2-05 | history enabled (10) | Re-use of a previous password on each available surface | Rejected | — | **NOT_TESTED** | — |
| L3-01 | `passwordChangeRequired=true` **and** `loginPolicy=Required`, user **with** TOTP | Hosted login | MFA first, then change (issue #1591, shipped 1.33.0) | — | **NOT_TESTED** | — |
| L3-02 | same but user **without** TOTP | Hosted login | Predicted deadlock: cannot pass MFA, therefore cannot reach the change | — | **NOT_TESTED** | — |
| L4-01 | no SMTP configured | Request `/password/forgot` | Route exists; request likely accepted; delivery impossible | — | **NOT_TESTED** | — |
| L4-02 | same | Attempt completion without the emailed id | Not completable | — | **NOT_TESTED** | — |
| C6-01 | synthetic `firstName`, conforming password **containing firstName** | Set on every surface L-2 found | **Accepted** — no native rule exists | — | **NOT_TESTED** | — |
| C6-02 | synthetic `lastName`, conforming password **containing lastName** | same | **Accepted** | — | **NOT_TESTED** | — |
| C6-03 | control: conforming password containing neither | same | Accepted | — | **NOT_TESTED** | — |
| C6-04 | `disallowUserLoginId = true`, password containing the loginId | same | **Rejected** — the one native rule that does fire | — | **NOT_TESTED** | — |

C6-01…C6-03 are not there to rediscover the documentation. C6-01/C6-02 are
expected to be **accepted**; their purpose is to measure *which surfaces* the
absence of the rule spans, which is the coverage input ADR-035 needs. C6-04
exists so a green Control-6 run cannot be manufactured by conflating the
loginId rule with the name rule.

**Excluded by decision: L-6 / any API-key timing reproduction.** The API-key
investigation is closed (`ROOT_CAUSE = NOT_PROVEN`, permanent) and is not on
the product critical path.

---

## 8. Status (superseded by section 9 - preserved as the pre-execution state)

```
LAB_MECHANISM        = SELECTED (Option B, user-space bundle + private PG cluster)
LAB_BUILT            = NO
L-1 / L-2 / L-3 / L-4 = NOT_TESTED (blocked)
CONTROL_6            = B - PARTIALLY_SATISFIED (unchanged, not probed)
BLOCKER              = one operator decision (section 6)
PRODUCTION_IMPACT    = NONE to FusionAuth; one unintended snap install (section 2)
```

---

# 9. EXECUTION RESULTS (2026-09-09)

## 9.1 What was actually built

| Property | Value | Class |
|---|---|---|
| FusionAuth | **1.69.0** — asserted from `fusionauth-app-1.69.0.jar` in the running install, not from the download name | `VERIFIED_LAB` |
| Source | `https://files.fusionauth.io/products/fusionauth/1.69.0/fusionauth-app-1.69.0.zip`, vendor-controlled, `content-length: 86570373`, `last-modified: Tue, 18 Aug 2026 17:14:20 GMT`; SHA-256 `89b5c914…65e3d59f` recorded at download. **The vendor publishes no checksum next to the artifact**, so this hash is a custody record of what *this* run used, not a vendor attestation | `VERIFIED_LAB` |
| Java | Eclipse Temurin **21.0.12.1+1-LTS** (JRE), from the Adoptium API; vendor-published SHA-256 `24131497…2c5b500` **verified before extraction — MATCH** | `VERIFIED_LAB` |
| Database | Private PostgreSQL 16.15 cluster, own `PGDATA`, own postmaster (pid distinct from production's), `127.0.0.1:55432`, private socket dir | `VERIFIED_LAB` |
| Listeners | Lab `:9411` only. Production `:9011`/`:9012` untouched throughout | `VERIFIED_LAB` |
| Setup | Kickstart (one API key + one admin registration), then declarative tenant/application configuration over the API | `VERIFIED_LAB` |
| Teardown | JVM stopped, `pg_ctl stop -m immediate`, `rm -rf` of the 809 MB lab root, parent directory removed | `VERIFIED_LAB` |

**Two design assumptions were falsified by execution, and both are recorded
rather than quietly fixed:**

1. **The ZIP bundles its own Java runtime** (`fa/java/current/bin/java`), which
   `start.sh` prefers. The separately downloaded Temurin JRE was therefore
   **not** what ran FusionAuth. Section 3's premise ("no system Java, so a JRE
   must be obtained") was true of the host but wrong about the bundle. A future
   lab needs the app ZIP only.
2. **`fusionauth-app.management-port` is not a recognised 1.69.0 property.**
   Neither `fusionauth-app.management.port` nor `fusionauth-app.management-port`
   changed the second listener, which kept trying its default — **9012, the port
   production owns** — and failed every start with
   `java.net.BindException: Address already in use`. The lab ran correctly on
   `:9411` regardless, because that bind failure is non-fatal.

   This is a **real isolation defect in the design**, not a curiosity. It was
   fail-safe only because production already held `9012`: the operating system
   refused the lab's bind. Had production been stopped while the lab was
   running, the lab could have taken production's port. **A future lab on this
   host must not run while production is stopped**, or must run in a network
   namespace. Recorded as `LAB-DEFECT-1`.

**Incidental finding that closes an open question.** The second listener is
FusionAuth's own default management port. `SP_API_REGISTRATION_REMEDIATION.md`
§33 recorded "two listeners (`:9011` and `:9012`) observed, unexplained", and
the research document carried it as unknown **U-2**. A clean 1.69.0 instance
with no management port configured attempts exactly this second listener.
**U-2 is answered: two listeners is stock 1.69.0 behaviour, not a
misconfiguration of `juval-server`.** `VERIFIED_LAB`.

## 9.2 L-1 — MFA `Required` with no enrolled method

**`MFA_REQUIRED_WITHOUT_METHOD = 242_WITH_EMPTY_METHODS_AND_NO_ENROLMENT_PATH`**

| test_id | Preconditions | Action | Expected (doc) | Observed | Result |
|---|---|---|---|---|---|
| L1-01 | `loginPolicy=Required`, user with **no** method | `POST /api/login` | "will not be able to log in" | **242**, `methods: []`, `configurableMethods: ["authenticator"]` | **OBSERVED_UNDOCUMENTED** |
| L1-02 | same | `POST /api/two-factor/login` with the returned `twoFactorId` | — | **421** | OBSERVED_UNDOCUMENTED |
| L1-03 | same | `POST /api/user/two-factor/{id}` (enrol), incl. variants with tenant header, `applicationId`, and the `twoFactorId` | enrolment succeeds | **421** in all 4 variants | OBSERVED_UNDOCUMENTED |
| L1-04 | `loginPolicy=Disabled`, same user | `POST /api/login` | success | **200** + token | PASS_EXPECTED |
| L1-05 | `loginPolicy=Required`, method **pre-seeded at user creation** | `POST /api/user` with `twoFactor.methods[]` | — | **200**, method present on the user | PASS_EXPECTED |

**Observed flow:**

```
password accepted
      |
      v
loginPolicy = Required
      |
      +-- user HAS a method  --> 242  methods:["authenticator"]  --> challengeable
      |
      +-- user has NO method --> 242  methods:[]                 --> DEAD END
                                      configurableMethods:["authenticator"]
                                      |
                       POST /api/two-factor/login  -> 421
                       POST /api/user/two-factor/{id} -> 421
```

The vendor's prose ("they will not be able to log in") is directionally right
but imprecise: FusionAuth does not refuse the login, it **issues a two-factor
challenge that cannot be satisfied**, while simultaneously refusing the
enrolment call that would make it satisfiable. The `configurableMethods` array
is the signal an integrating client is expected to act on — which is exactly
the "build your own MFA page" the vendor recommends, and which the hosted pages
do not provide.

**The only enrolment paths observed to work:** pre-seed `twoFactor.methods[]`
at `POST /api/user`, or set the policy to something other than `Required`
first. **`POST /api/user/two-factor/{userId}` returned 421 in every
configuration attempted here** — reported as an observation, **not** as a
defect: no vendor issue was matched and the possibility of an unmet
precondition in this lab's use of the endpoint is not excluded.

## 9.3 L-2 — password rule enforcement by surface

Policy under test: `minLength 12`, mixed case, number, non-alpha, history 10.
Invalid inputs are symbolic classes only; no value is recorded anywhere.

| SURFACE | AVAILABLE? | RULE ENGINE ENFORCED? | SAME RULES? | BYPASS? | Evidence (error codes returned) |
|---|---|---|---|---|---|
| `POST /api/user` (admin API create) | Yes | **Yes** | **Yes** — 4/4 classes | No | `tooShort`, `requireNumber`, `onlyAlpha`, `singleCase` |
| `PATCH /api/user/{id}` (admin API change) | Yes | **Yes** | **Yes** — 4/4 | No | same four codes |
| Forced change (`POST /api/user/change-password/{changePasswordId}`) | Yes | **Yes** | **Yes** — 4/4 | No | same four codes |
| `POST /api/user/change-password` with `loginId`+`currentPassword` | Yes, **API-key protected** (401 without a key) | **Yes** | **Yes** — 4/4 | No | same four codes |
| Forgot-password-minted `changePasswordId` | Yes | **Yes** | **Yes** — 4/4 | No | same four codes |
| Password history (reuse of the immediately previous password) | Yes | **Yes** | — | No | `previouslyUsed` |
| **FusionAuth admin console (browser)** | Yes | **NOT_TESTED** | — | — | see below |

**`PASSWORD_RULE_SURFACE_MATRIX` = five API surfaces tested, five enforce the
identical rule set with identical error codes. Equivalence is measured, not
assumed.**

**The admin console was deliberately not tested, and this is a real gap.**
Driving it requires typing a live administrator credential into this session's
transcript, which this phase's secret-handling rules forbid. It is marked
`NOT_TESTED`, not inferred from the API results. It is the one surface ADR-035
still needs measured, and §11 proposes how.

## 9.4 L-3 — ordering of password change vs MFA

**`PASSWORD_CHANGE_VS_MFA_ORDER = MFA_FIRST, PASSWORD_CHANGE_SECOND`**

Established by controlled comparison, not by a single observation:

| test_id | `loginPolicy` | `passwordChangeRequired` | Method? | `POST /api/login` | Interpretation |
|---|---|---|---|---|---|
| L3-01 | Disabled | true | no | **203** + `changePasswordId` | change-password reached directly |
| L3-02 | **Required** | true | no | **242** | **the MFA gate preempts the 203** |
| L3-03 | Required | true | yes | **242** | same |
| L3-04 | Required | **true** | yes | 242 → second factor → **203** + `changePasswordId` → change → **200** | full ordering |
| L3-05 | Required | **false** | yes | 242 → second factor → **200** + token + `trustToken` | control: no 203 when not required |

The single-variable flip between L3-01 and L3-02 — only `loginPolicy` changes —
is what makes this an ordering result rather than a coincidence.

**Observed state diagram (measured):**

```
START
  |
  v
CREDENTIALS  (loginId + password)
  |
  +-- invalid ------------------------------> 404  (retry; lockout after 10)
  |
  v
MFA GATE     (tenant loginPolicy = Required)
  |
  +-- no method enrolled --> 242 methods:[] --> DEAD END  (421 on challenge
  |                                                        and on enrolment)
  v
SECOND FACTOR  (POST /api/two-factor/login)
  |
  v
PASSWORD CHANGE GATE  (passwordChangeRequired)
  |
  +-- false --> 200  TOKEN (+ trustToken)
  |
  +-- true  --> 203  changePasswordId + changePasswordReason
                  |
                  v
        POST /api/user/change-password/{id}   [full tenant rules enforced]
                  |
                  v
                200 -> re-login -> 242 (MFA still enforced)
```

Consistent with vendor issue #1591 (2FA moved before change-password, shipped
1.33.0), now **measured on 1.69.0** rather than inferred from a 1.33.0 issue.

## 9.5 L-4 — forgot password without SMTP

**`PASSWORD_FORGOT_WITHOUT_SMTP = ROUTE_AVAILABLE; EMAIL_PATH_FAILS_403;
API_PATH_COMPLETES_WITHOUT_EMAIL`**

| Question | Observed |
|---|---|
| Route exists? | **Yes** — `GET /password/forgot` → 200 and `GET /password/change` → 200 on Community, unauthenticated |
| Request accepted? | `POST /api/user/forgot-password` → **403** with no usable SMTP configured (tenant carried the stock `localhost:25` / `change-me@example.com` placeholder) |
| SMTP required? | **For the email path, yes.** |
| Completable without SMTP? | **Yes, and this is the finding.** `POST /api/user/forgot-password` with `sendForgotPasswordEmail: false` returns **200 and a `changePasswordId` in the response body**. That id is then accepted by `POST /api/user/change-password/{id}` **with no API key**, and the tenant password rules are fully enforced on it |
| Paid feature dependency? | **None observed** — all of the above on unlicensed Community |
| Security implication | An API-key holder can mint a password-reset token for any user **without any email delivery and without knowing the current password**. It is not a rule bypass — the rules still apply — it is an **authentication bypass of the "prove you own the mailbox" step**. It matters for ADR-035 because it is a password-**setting** path that no JUVAl-side validator sits in front of |

## 9.6 Control 6

**Positive control first**, so a negative result cannot be confused with a
non-firing rule:

| test_id | `disallowUserLoginId` | Password contains | Observed | Classification |
|---|---|---|---|---|
| C6-04a | **true** | the **full** loginId (email) | **400** `containsEmail` | rule **fires** |
| C6-04b | **true** | the email **local part** only | **200** accepted | rule matches the full loginId, not fragments |
| C6-04c | **true** | the **username** (username-based account) | **400** `containsUsername` | rule **fires** |
| C6-01 | false | **firstName** | **200 accepted** | — |
| C6-02 | false | **lastName** | **200 accepted** | — |
| C6-03 | false | neither (control) | **200 accepted** | control behaves |
| C6-05 | **true** | **firstName** | **200 accepted** | the loginId rule does **not** extend to names |
| C6-06 | **true** | **lastName** | **200 accepted** | same |

```
NATIVE_FIRSTNAME_REJECTION = NOT SATISFIED
NATIVE_LASTNAME_REJECTION  = NOT SATISFIED
CONTROL_CASE               = accepted, as expected
LOGINID_CONTROL            = SATISFIED (containsEmail / containsUsername)
CONTROL_6_CLASSIFICATION   = B - PARTIALLY_SATISFIED  (unchanged)
```

The classification does not move. What changes is its **basis**: it was
documentary (the field list contains no such rule); it is now **behavioural**,
with a working positive control proving the mechanism that *does* exist fires,
and that it does not extend to `firstName`/`lastName` even when enabled.

**This is not a FusionAuth defect.** FusionAuth implements the rule it
documents. Amazon requires a different, stricter rule.

## 10. Bypass matrix for ADR-035

`ADR-035 OPTION C (JUVAl-side pre-validation) = ONLY_WITH_CONDITIONS`

| Path | AVAILABLE? | BYPASSES A JUVAl VALIDATOR? | CAN BE DISABLED? | GOVERNABLE OPERATIONALLY? | AUDITABLE? | RESIDUAL RISK |
|---|---|---|---|---|---|---|
| Admin API create/change (`/api/user`) | Yes | **Yes** — unless every call goes through the JUVAl tool | Not as an endpoint; **yes** by not issuing an API key with those grants (ADR-032) | **Yes** — this is exactly ADR-032's lifecycle scoping | Yes — FusionAuth audit log | **Low** if no standing key carries `POST /api/user` |
| Forced change (`/api/user/change-password/{id}`) | Yes | **Yes** — no API key needed once an id exists | No | Only by never minting a `changePasswordId` | Yes | **Medium** — depends entirely on who can mint ids |
| Forgot/reset (`/api/user/forgot-password`) | Yes | **Yes** — `sendForgotPasswordEmail:false` mints an id with no email at all | Hosted route can be blocked at nginx; **the API cannot** without an API-key grant policy | Yes, via key scoping | Yes | **Medium-High** — the sharpest edge found in this lab |
| Hosted `/password/forgot`, `/password/change` | Yes (Community) | **Yes** | **Yes** — nginx allow-list already defaults to 404 | Yes | Partially | **Low**, given the existing default-deny |
| Self-service account portal (`/account/?client_id=…`) | **Yes — 200 on unlicensed Community** | **Yes** | Not natively; blockable at nginx | Yes | Partially | **Medium** — see correction below |
| Self-service registration | Disabled (`registration_enabled=false`) | Would | **Yes** — already off | Yes | Yes | **Low** |
| **FusionAuth admin console** | Yes | **Presumed yes** | No | Yes — single named operator | Yes — audit log | **NOT_MEASURED** |

**Correction to the prior research pass.** `IDENTITY_AMAZON_DEEP_RESEARCH.md`
§5.2 recorded, from the vendor pricing page, that the self-service account
portal is a paid Starter feature, and §5.5 leaned on that to argue Option C's
bypass surface was unusually small. **The lab contradicts it**:
`GET /account/?client_id=<app>` returned **200** on an unlicensed Community
instance and rendered a login page whose text includes a "Forgot your password?"
affordance. The earlier claim is **withdrawn**. Option C's surface is larger
than the research pass estimated, which is precisely why this lab existed.

## 11. What is still not measured

| # | Item | Why it matters | Proposed method |
|---|---|---|---|
| 1 | Admin console password set | The last unmeasured L-2 surface, and the one ADR-035 names as the residual | Operator drives it manually on a future lab instance and reports the four symbolic outcomes; or a lab run seeds a browser profile from a file so no credential enters a transcript |
| 2 | Whether `/account/` on Community exposes a *working* password change (not just a login page) | Determines whether it is a real bypass or only a login shell | Same lab, authenticated session |
| 3 | `POST /api/user/two-factor/{userId}` → 421 | Blocks the natural enrolment path; affects onboarding design | Vendor question, or a lab run with `/api/two-factor/start`-derived trust token |
| 4 | Lockout behaviour (10 attempts / 30 min) | RF-03 evidence, not an L-question this phase asked | Next lab run |

## 12. Final status

```
LAB_BUILT              = YES (FusionAuth 1.69.0, Temurin 21 available but unused - bundle ships its own JRE)
LAB_DESTROYED          = YES (JVM stopped, cluster stopped, 809 MB root removed)
L-1                    = ANSWERED  (242 + empty methods + no enrolment path)
L-2                    = ANSWERED for 5 API surfaces; admin console NOT_TESTED
L-3                    = ANSWERED  (MFA before password change, with controls)
L-4                    = ANSWERED  (403 with SMTP absent; completable without email via API)
CONTROL_6              = B - PARTIALLY_SATISFIED (unchanged; now behaviourally grounded)
ADR-035 OPTION C       = ONLY_WITH_CONDITIONS
PRODUCTION_IMPACT      = NONE (MainPID, NRestarts, ActiveEnterTimestamp, listeners all identical)
RF-03 / RF-04          = NOT_VERIFIED (unchanged - this lab is not production evidence)
```
