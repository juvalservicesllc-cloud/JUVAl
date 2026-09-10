# ADR-041 — Hosted MFA enrollment public-surface candidate

**Estado: Propuesta**
**Fecha: 2026-09-10**

## Context

An explicitly authorized single disposable JUVAl user, with Required MFA and no
pre-attached authenticator, completed the real hosted TOTP enrollment path and
reached the approved loopback callback. This contradicts the universal conclusion
in the earlier onboarding design; isolated API failure is not hosted-flow failure.
The current inactive nginx template denied three routes actually traversed.

## Proposed production direction; authorized laboratory implementation

Retain exact GET/POST /oauth2/two-factor-enable and
/oauth2/two-factor-enable-complete, plus exact GET /oauth2/consent. No consent POST
was observed. Keep all existing private-surface exclusions; no fonts or /assets/
expansion. Password recovery and forced password change remain excluded by
ADR-035. WebAuthn stays disabled. This does not approve self-service production
onboarding or replace operator responsibilities yet.

The user authorized minimal evidence-supported nginx changes for this experiment.
The candidate was tested in a disposable proxy only. Public activation remains
blocked until actual enrollment/challenge/callback/logout behavior through nginx
and compatible headers are demonstrated. Do not infer production readiness from
the syntax/echo lab or from generic provider GETs.

## Evidence and limits

See docs/research/MFA_DISPOSABLE_DISCOVERY_20260910.md. Direct-runtime enrollment
and callback observed; a subsequent proxy login did not pass credentials, so
an existing-factor challenge was not verified. The human-authorized password
change could not complete under provider policy. No policy was relaxed. The one
user and temporary redirect were removed with readback. RF03/Control 6 status
unchanged. This ADR stays Proposed pending the remaining end-to-end evidence
and explicit production onboarding policy acceptance.
