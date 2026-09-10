# ADR-040 — Independent readiness evidence measurements

**Estado: Aceptada. Fecha: 2026-09-10.** Authority: second-wave progress
measurement instruction. Applies to Project Intelligence reporting, not business
scoring or Amazon compliance decisions. ADR-037 is nginx hardening, not a model.

## Decision

Retain portal implementation and verification weights, with explicit model 1.2
scope in project-config.json. Implementation credits COMPLETE=1, PARTIAL or
IN_PROGRESS=.5, other active statuses=0; DEFERRED excluded. Verification uses
the existing test/behavior evidence levels independently of implementation.
These measure curated roadmap criteria, not all product capabilities or code coverage.

Add three separately enumerated scopes in config.measurements, evaluated by
scripts/measure.mjs and model.mjs::readiness. Each earns its criterion weight
only when status is COMPLETE AND its verificationLevel belongs to the scope's
explicit accepted levels. Divide by all specified weights and round to nearest
integer percent. Missing/duplicate IDs or invalid levels fail instead of yielding
zero. DEFERRED blockers remain in readiness denominators.

Production and Amazon scopes require PRODUCTION_VERIFIED. Security scope credits
closed test/behavior/lab controls, explicitly including no claim of public readiness.
An unverified criterion earns zero evidence credit; that does NOT mean the actual
system has zero implementation or actual protection. Zero here is a measured
absence of qualifying evidence in a known denominator, not an invented runtime
measurement. Global production coverage remains NOT_MEASURED. Amazon approval
remains an independent human/external gate even if an evidence score reaches 100.

## Reproduction and consequences

`JUVAL_EVIDENCE_REF=<full-tested-commit> npm run sync`, then
`node scripts/measure.mjs` from project-portal. Output includes indexed commit,
model version, numerator/denominator/count and readiness IDs. Config/rules must
come from the same committed checkout as evidence for a release report. The tool
supports local review but cannot attest operator-supplied runtime documents.
Keep all five dimensions separate. Do not combine or infer one from another.

Tests prove lab evidence earns no production credit, deferred blockers retain
weight and incomplete scopes fail. New requirements need a versioned scope
update; historical percentages cannot be compared blindly after denominator changes.
