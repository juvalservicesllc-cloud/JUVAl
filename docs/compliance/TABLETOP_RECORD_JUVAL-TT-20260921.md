# Tabletop Exercise Record — `JUVAL-TT-20260921`

**TABLETOP-002 = COMPLETED_WITH_FINDINGS.** Human exercise completed;
CA-01 is now CLOSED / TABLETOP_VERIFIED following the supplemental action-start
evidence below. This is not technical incident remediation or Amazon compliance.
Uses [the prepared scenario](TABLETOP_002_PREPARED_SCENARIO.md) and existing
`templates/TABLETOP_RECORD_TEMPLATE.md`; notification draft is embedded below.

## Exercise metadata

| Field | Value |
|---|---|
| Exercise ID | `JUVAL-TT-20260921` / TABLETOP-002 |
| Date (UTC) | 2026-09-21 |
| Facilitation | Agent presented the grouped checkpoint; Daniel supplied authoritative answers and recorded times in the conversation |
| Actual human participant | Daniel E. Liendo only; Incident Lead / IC / IMPOC / Security Owner / Technical Responder under existing assignments |
| Deputy | Jocsimar C. Gonzalez; did NOT participate; backup procedure only |
| Plan version exercised | `0.1.1-DRAFT` |
| Start / detection | `2026-09-21T15:12:56Z` |
| End | `2026-09-21T15:28:57Z` |
| Duration | 16m01s, calculated from human-reported timestamps |
| Repository baseline | `750e0723a8eb87b8ff655b76aa4d789b233f924d`; master, clean at integration |

Provenance: Daniel's authoritative checkpoint response. Decisions are real human
decisions; times are HUMAN_REPORTED, not independently clock-observed by the
agent. This filing transcribes the supplied exercise artifacts; Git/file write
time is not their event or collection time. No timestamp assigned to events
for which Daniel supplied none. Existing August exercise/approval remains
historical evidence; it is not re-executed here.

## Scenario

Exclusively SIMULATED: a possible Supabase service-role key appears in a public
Vercel bundle; the database contains Amazon-derived data and registration is
approved. These are exercise assumptions, not JUVAl's actual state. Actual
SP-API remains NOT_APPROVED; case 21652891301 is not resubmitted. No evidence
of effective unauthorized access was supplied. Initial severity: HIGH / ALTA
(corresponds to the plan's SEV-2); Amazon Information classification: SUSPECTED.

## Walkthrough

| Step | Plan section | Performed? | Elapsed from detection | Evidence / limits |
|---|---|---|---|---|
| Detection recorded, IC assigned | §4.1 | Human decision recorded | 0m00s | E-001; Daniel leads; Jocsimar acts/escalates per IRP if Daniel unavailable, not an exercised handoff |
| Containment actions identified | §4.2 | Human decision REAL; response instruction SIMULATED | 8m49s | E-002 at `2026-09-21T15:21:45Z`; not a credential-rotation initiation timestamp |
| Credential revocation walked | §4.3 | Later controlled action described only | Separate time NOT_RECORDED | No actual rotation/revocation/redeploy; sequencing residual CA-01 below |
| Amazon Information determination | §4.4 | Human decision: SUSPECTED | Separate time NOT_RECORDED | Possible privileged credential exposure in simulated Amazon-data system; insufficient evidence to confirm or rule out access |
| Evidence preservation | §4.5 | Two real human exercise artifacts collected and approved | 10m01s | `2026-09-21T15:22:57Z`; attached manifest; no provider logs/exports |
| Amazon notification DRAFTED (never sent) | §5 | Conceptual text approved/finalized by Daniel, transcribed below | 14m31s | `2026-09-21T15:27:27Z`; exercise preparation within 24h, no delivery proof |
| Recovery plan stated | §4.6 | Human procedural decision only | Separate time NOT_RECORDED | Criteria below; technical recovery NOT_EXECUTED |
| Exercise closed | §10 | Human closure confirmations | 16m01s | `2026-09-21T15:28:57Z`; does not close a technical incident |

### CA-01 decision — exact human text

> Ante una posible credencial privilegiada expuesta, ordeno tratarla como potencialmente comprometida y priorizar su contención. Se preservará la evidencia necesaria; después se confirmará la autenticidad de la credencial y se revisarán los logs disponibles para determinar posible uso y alcance. La rotación/revocación y cualquier despliegue serían acciones técnicas controladas posteriores. Durante TABLETOP-002 estas acciones son simuladas y no se ejecutarán.

Decision at `2026-09-21T15:21:45Z`: REAL. Instruction/response: SIMULATED.
Technical action: NOT_EXECUTED. No logs were reported inspected. No independent
confirmation-concluded time or applicable containment-action initiation event
was supplied. Prioritizing containment is not proof of executing its sequence.

### Evidence preservation

[Completed evidence manifest](EVIDENCE_MANIFEST_JUVAL-TT-20260921.md): E-001
and E-002 are real human artifacts from this simulated scenario, not provider
exports. Hashes are N/A as approved; no secret or secret fingerprint collected.
The manifest's Human report source category is expressly allowed by the existing
template. Its historical IdP availability entry is not used as current evidence.

### Amazon determination and procedure

Daniel chose **AMAZON_INFORMATION_SUSPECTED**, because the possible privileged
credential exposure concerns a simulated system containing Amazon-derived data,
and there is insufficient evidence to confirm unauthorized access or rule it out.
He activated the notification procedure FOR THE SCENARIO, with Daniel as IMPOC /
Incident Lead. Preparation starts at detection; investigation continues in
parallel. Exercise clock starts `2026-09-21T15:12:56Z`; calculated 24h deadline
is `2026-09-22T15:12:56Z`. That deadline is arithmetic, not an observed event.
The approved draft finished in 14m31s. No separate determination timestamp is
invented and no actual Amazon notification is implied.

### Approved notification draft — EJERCICIO — NO ENVIAR

Approval/finalization: `2026-09-21T15:27:27Z` (HUMAN_REPORTED).
Procedural recipient: `security@amazon.com`; nothing sent.

**EJERCICIO — NO ENVIAR**

Organización: JUVAl.

IMPOC / Incident Lead: Daniel E. Liendo. Información de contacto custodiada
fuera del repositorio Git.

Detección: `2026-09-21T15:12:56Z`. Durante el escenario TABLETOP-002 se
identificó una posible clave Supabase service-role expuesta en un bundle
público simulado de Vercel.

Clasificación: HIGH. Posible implicación de información Amazon: SUSPECTED.

Hechos conocidos: el escenario supone una posible exposición pública de una
credencial privilegiada y una base que contiene datos derivados de Amazon.

Hechos desconocidos: no se ha confirmado que la credencial sea auténtica o
utilizable, que terceros hayan accedido a ella, que haya sido utilizada
indebidamente ni que información Amazon haya sido accedida o extraída.

Información posiblemente afectada: información derivada de Amazon accesible
mediante los privilegios hipotéticos de la credencial. El alcance exacto
permanece sin determinar.

Contención: a las `2026-09-21T15:21:45Z` el Incident Lead decidió tratar la
credencial como potencialmente comprometida, priorizar contención y preservación
de evidencia y posteriormente confirmar autenticidad y revisar logs.
En este tabletop la actuación es simulada: no se rotaron/revocaron credenciales,
no se realizaron despliegues y no se modificaron sistemas.

Próximos pasos del procedimiento: confirmar autenticidad y alcance; preservar y
revisar evidencia disponible; determinar si existió uso no autorizado; reevaluar
clasificación; ejecutar las acciones técnicas de remediación que correspondan
en un incidente real.

Actualización: se proporcionaría una actualización cuando existan resultados
materiales de la investigación y dentro del plazo aplicable iniciado desde la
detección.

**ESTE DOCUMENTO FORMA PARTE DE UN EJERCICIO. NO ENVIAR.**

Evaluation: all six §5 content categories are represented, with private contact
custody referenced rather than copied into Git. Update timing is conditional
and bounded by the stated deadline, not a specific scheduled update time. This
records approved draft preparation; actual contact availability, delivery,
acknowledgment and update execution remain NOT_VERIFIED.

### Recovery and closure — exact human criteria

> El incidente no podrá declararse recuperado/cerrado hasta determinar razonablemente el alcance, revisar la evidencia disponible, eliminar la exposición, revocar/rotar cualquier credencial confirmada o prudentemente considerada comprometida, comprobar el estado posterior a la remediación y documentar las acciones correctivas. Después se realizará una revisión post-incidente y se hará seguimiento de cualquier gap pendiente.
>
> En TABLETOP-002 estas condiciones se evalúan únicamente como procedimiento. No se ejecutarán rotaciones, cambios de infraestructura, despliegues ni comunicaciones externas.

Recovery procedure walked; technical remediation and incident closure NOT_VERIFIED.
IRP's existing seven-day monitoring and five-business-day postmortem requirements
remain in force; no separate human schedule or new plan approval is inferred.

## Confirmation

Daniel confirmed at `2026-09-21T15:28:57Z`:

- No external communication was sent.
- No credential was rotated/revoked and no technical change resulted from the scenario.
- No real secret was intentionally exposed during TABLETOP-002.

These are HUMAN_REPORTED confirmations. The last statement is not strengthened
into proof that no accidental exposure anywhere occurred. This filing contains
no credential values or private contact details; pattern scan has its own limits.

## Additional CA-01 demonstration — 2026-09-21

Integration baseline: `aaed44e81cca4792683038ae6ea9ac7038a118e5`, clean.
Provenance: HUMAN_REPORTED by Daniel E. Liendo. This additional demonstration
is separate from the original 16m01s exercise; neither its times nor the original
E-001/E-002 manifest collection times are overwritten.

- Start: `2026-09-21T15:47:13Z`.
- Conclusion approved by Daniel: `2026-09-21T15:48:59Z`.
- Duration: **106 seconds / 1m46s**, calculated from those human timestamps.
- Exact REAL human decision: “Apruebo iniciar contención y confirmación en paralelo.”
- Line A, SIMULATED containment: aislar la exposición pública y preparar la
  revocación/rotación controlada de la credencial potencialmente comprometida.
- Line B, SIMULATED confirmation: preservar evidencia y comprobar autenticidad,
  posible utilización y alcance mediante los logs disponibles.

Daniel reported that the two simulated response lines ran in parallel from the
start and approved the procedural conclusion that investigation must not delay
containment. This is **TABLETOP_VERIFIED / HUMAN_REPORTED for the parallel-response
component**, not independently observed provider behavior. The end timestamp is
exercise/procedural conclusion, not completion of actual authenticity checking.
No real incident or credential was used. Isolation, revocation/rotation, log
queries, provider/infrastructure changes, deployment and configuration changes
were NOT_EXECUTED; technical results remain NOT_VERIFIED. Nothing was sent.

Historical evaluation after the 15:47 demonstration, before the 16:00 action-start
supplement below, against remediation §28.1 and IRP §4.3:

| Criterion | Evaluation |
|---|---|
| Start of containment without waiting for confirmation | Supported for the reported simulated containment line from demonstration start, with documented parallelism; original blanket “parallel behavior missing” residual superseded |
| Within one hour | Supported for that simulated line at demonstration start; demonstration duration 106s. These are not credential-action timestamps |
| Initiate the applicable §4.3 action | NOT_ESTABLISHED: the Supabase row requires rotation/revocation initiation; Line A says prepare it. Simulated isolation is containment under §4.2, but does not itself evidence starting the credential action of §4.3 |
| Conclusion / parallelism evidence | Real human start/end timestamps plus reported parallel simulated lines support procedural parallelism. No actual log/authenticity conclusion is inferred; two timestamps alone do not close the whole criterion |

**At that checkpoint CA-01 was OPEN / PARTIALLY_EXERCISED.** Residual was a recorded
start of the applicable credential action **within a simulation**, without
waiting for confirmation; no real credential action is required or authorized.
Do not repeat the already supplied parallelism decision or demand invented
retrospective timestamps. No observed technical failure is asserted.

### CA-01 applicable action started — 2026-09-21

Integration baseline: `6151c958415ff54fee6c115f0039b59d9c4a2ea2`, clean.
At **`2026-09-21T16:00:52Z`**, Daniel E. Liendo approved:
“Apruebo iniciar la revocación/rotación simulada.”

Exact approved semantics:

> A las 2026-09-21T16:00:52Z, ante el escenario simulado de una credencial Supabase service-role potencialmente comprometida, ordeno iniciar inmediatamente la revocación/rotación SIMULADA de esa credencial conforme a la acción aplicable de §4.3, sin esperar a que concluya la confirmación o investigación. Esta es exclusivamente una decisión y acción de tabletop. No se revoca, rota ni modifica ninguna credencial real y no se realiza ningún cambio técnico.

**CA-01 = CLOSED / TABLETOP_VERIFIED / HUMAN_REPORTED**, based on the combined
parallel-response demonstration and this specific action-start event:

- Applicable §4.3 action: initiation of simulated revocation/rotation of the
  potentially compromised Supabase service-role credential is now explicit.
- One-hour target (§28.1/§4.2): 16:00:52Z minus the original detection at
  15:12:56Z is **47m56s / 2876 seconds**, within one hour; the clock is not reset
  to the supplemental demonstration start.
- No waiting for confirmation: explicit in the new action-start instruction,
  complementing the documented parallel-response component. This satisfies the
  existing pass-condition alternative of parallel containment/confirmation;
  no confirmation-completion time or technical conclusion is fabricated.
- The residual was initiation, not completion. No rotation-completion timestamp,
  successful rotation, redeployment or credential verification is inferred.

Human decision REAL / HUMAN_REPORTED; §4.3 action start SIMULATED; real credential
revocation/rotation NOT_EXECUTED; technical result NOT_VERIFIED; technical changes
NONE; external notification NONE. No real secret used. CA-01 tabletop residual
NONE. Earlier observations remain historical; no further CA-01 iteration needed.

### Contact and governance follow-through

Daniel confirmed his private contact mechanism and availability **OPERATIVE /
HUMAN_REPORTED**. No private contact information recorded and no independent
contact test claimed. Jocsimar remains the defined Deputy, did not participate,
and current operational availability is **NOT_VERIFIED**. Daniel approved
retaining **2027-02-18** for the next formal governance review; this is a schedule
confirmation, not a completed formal review. Existing earlier-response duties
for critical findings remain applicable. No distinct timestamps were supplied
for these confirmations; none are invented.

## Gaps found and corrective-action results

| Item | Result / exact evidence | Residual / next evidence |
|---|---|---|
| CA-01 | CLOSED / TABLETOP_VERIFIED / HUMAN_REPORTED; parallel-response evidence plus specific simulated §4.3 start at 16:00:52Z | No tabletop residual. Real credential actions NOT_EXECUTED; technical results NOT_VERIFIED. |
| CA-02 | CLOSED / TABLETOP_VERIFIED in the manifest-production scope of remediation §28.2 | Two completed rows from an allowed real human source, with event/retrieval times, collector, custody and N/A hash. Provider log collection, integrity verification and long-term retention are not verified by this closure. |
| Governance | PARTIALLY_EXERCISED; Daniel contact/availability OPERATIVE / HUMAN_REPORTED; next review 2027-02-18 explicitly retained | Deputy availability and handoff NOT_VERIFIED; formal review not performed. No independent contact test or extra deadline inferred. |

Existing Security Owner: Daniel. Next formal review explicitly retained at
2027-02-18; no additional corrective-action deadline invented.

## Plan changes resulting

No policy or plan version change. This record and its manifest are evidence
updates; they do not amend the containment order to match the exercised answer.

## RF-01 / RF-05 and ADR-040 effect

- RF-01: PARTIAL before and after. The previously unexercised §5 branch now has
  human tabletop evidence: SUSPECTED determination, notification decision and
  an approved six-category draft in 14m31s. CA-01 is closed only in tabletop
  scope; operational notification evidence and Deputy availability remain
  incomplete. No Amazon compliance claim.
- RF-05: PARTIAL before and after. A second dated exercise and real manifest
  production now exist (2026-08-18 and 2026-09-21). This supports repeated exercise
  evidence, not proof of a mature program, formal six-month review or technical
  remediation. CA-01 and CA-02 are closed only in their tabletop scopes; Deputy
  behavior, formal review and external alert reconciliation remain incomplete.
  Daniel contact availability is now
  HUMAN_REPORTED operative. No GitHub queries or provider changes performed.
- ADR-040 model 1.2: `rf-01` (24-hour incident reporting, weight 2) and `rf-05`
  (security program/response roles, weight 2) stay PARTIAL / NOT_VERIFIED at the
  whole roadmap-criterion level. Their scoped tabletop evidence does not satisfy
  COMPLETE plus PRODUCTION_VERIFIED for Amazon readiness. Neither criterion is
  in security or production readiness scopes; no other criterion is completed.
  Config/rules unchanged; no portal regeneration required.

| Dimension | Before | After |
|---|---|---|
| Implementation | 44/68 = 65% | 44/68 = 65% |
| Verification | 17/68 = 25% | 17/68 = 25% |
| Production | 0/12 = 0% | 0/12 = 0% |
| Security | 5/16 = 31% | 5/16 = 31% |
| Amazon | 0/18 = 0% | 0/18 = 0% |

EXACT_CRITERIA_CHANGED = NONE. No aggregate project completion claimed.
RF-02 not reopened; RF-04 unchanged. MFA and frontend frozen. No infrastructure,
provider, auth, network, package or runtime change; no push.
