# ADR-035 — Control 6 de Amazon: exclusión del nombre en la contraseña

**Estado: Aceptada con riesgo residual**, por decisión explícita del usuario
(2026-09-09).
**Fecha: 2026-09-09.**
**Relacionada con:** ADR-021 (requisito HARD #8), ADR-028, ADR-031, ADR-032
(ciclo de vida de credenciales — **Condición 1 depende de él**), ADR-034 (BFF),
`docs/research/FUSIONAUTH_169_IDENTITY_LAB.md` §9.3/§9.5/§9.6/§10,
`src/juval/domain/password_policy.py`,
`src/juval/application/password_provisioning.py`,
`docs/compliance/SP_API_REGISTRATION_REMEDIATION.md`.

## Contexto

Amazon, en su *Key Security Control Guidance* mapeada a **DPP §1.4 (requisitos
generales, no la §2 específica de PII)**, exige: *"minimum 12 characters with
mixed case letters, numbers, and special characters, and **must not include any
part of the user's name**"*. Evitar PII no evita este control: aplica a todo
desarrollador.

FusionAuth 1.69.0 implementa la mitad de composición de forma nativa. **No
implementa la mitad del nombre.** Medido en laboratorio aislado (2026-09-09):

| Caso | `disallowUserLoginId` | Resultado |
|---|---|---|
| contraseña contiene `firstName` | `false` | **ACEPTADA** |
| contraseña contiene `lastName` | `false` | **ACEPTADA** |
| contraseña contiene `firstName` | **`true`** | **ACEPTADA** |
| contraseña contiene `lastName` | **`true`** | **ACEPTADA** |
| contraseña contiene el email completo | **`true`** | RECHAZADA — `containsEmail` |
| contraseña contiene el username | **`true`** | RECHAZADA — `containsUsername` |
| contraseña contiene sólo la parte local del email | **`true`** | ACEPTADA |

El control positivo dispara, así que el resultado negativo no es un falso
negativo de medición: la regla que existe funciona y **no se extiende a
`firstName`/`lastName`**. **Esto no es un defecto de FusionAuth** — implementa
exactamente la regla que documenta. Amazon pide una regla distinta y más
estricta.

Ningún punto de extensión soportado cierra el hueco: no existe un lambda de
validación de contraseña; el Login Validation lambda no recibe la contraseña;
los webhooks se disparan **después** de persistir; los formularios avanzados de
registro son de pago y no comparan campos entre sí. Ningún plan de pago lo
cambia.

## Decisión

**JUVAl valida la Condición 6 en su propio backend/dominio, antes de que
cualquier contraseña llegue a FusionAuth.**

Es una regla de seguridad del dominio, no una validación de frontend. Vive en
`domain/password_policy.py` (función pura, sin I/O, ADR-001) y su único punto
de paso es `application/password_provisioning.py`.

### Semántica exacta de la regla

**Normalización** (aplicada a la contraseña y a cada nombre):

1. `unicodedata.normalize("NFKD", …)` — descompone acentos en base + marca.
2. Se descartan las marcas combinantes → `Müller` ≡ `Muller`, `José` ≡ `Jose`.
3. `casefold()`, **no** `lower()` → `Straße` ≡ `STRASSE` (la ß pliega a `ss`),
   caso que `lower()` resuelve mal.

**Tokenización del nombre**: se parte por ` \t\r\n-_.,'’/\()[]`, de modo que
`Ana-Maria`, `O'Neill`, `van der Berg` y `Smith, John` se descomponen. Cada
parte es un token, **y además** la forma pegada (`vanderberg`), porque una
contraseña puede contener el nombre corrido sin contener ninguna parte aislada.
Se comprueban también `firstName+lastName` y `lastName+firstName` pegados
(`johnsmith`, `smithjohn`), que ninguna comprobación por campo vería.

**Coincidencia**: subcadena, sobre las formas normalizadas.

**Longitud mínima de token = 3.** Un token de 1–2 caracteres (`Al`, `Ng`, `Li`,
una inicial) aparece dentro de una fracción enorme de cadenas normales: `Ng`
rechazaría `king`, `strong`, `morning`. Aplicarlo empujaría al usuario hacia
contraseñas *peores* rechazando buenas — una pérdida neta de seguridad. **Es un
residual declarado, no silencioso**: un componente de nombre de 1–2 caracteres
no se excluye. `password_policy.SHORT_TOKEN_RESIDUAL` lo nombra en código.

**Deliberadamente fuera de alcance**: plegado *leet* (`4`→`a`, `0`→`o`). No es
lo que Amazon pide, y añadirlo generaría falsos positivos propios. Declarado
como hueco aceptado, no como hueco no visto.

**Sujeto sin nombre**: la regla pasa de forma vacua — no hay nada que excluir.
Por eso `PasswordProvisioningService.validate` **rechaza** provisionar un sujeto
sin `firstName` ni `lastName`: es el único punto donde ese vacío podría
convertirse en un agujero silencioso.

**Clasificación de evidencia**: un `PasswordPolicyResult` en verde es
`VERIFIED_POLICY`, nunca `AMAZON_VERIFIED_COMPLIANCE`. El enum tiene
exactamente dos miembros para que ningún llamador invente un tercero más
fuerte.

**Manejo de secretos**: la contraseña se lee, no se almacena, no se registra,
no aparece en excepciones. Una violación reporta el *token del nombre* (dato
del propio usuario) y jamás una porción de la contraseña.

### Rutas cubiertas

Toda ruta de JUVAl que cree, cambie o provisione una contraseña **debe** pasar
por `PasswordProvisioningService`. Hoy no existe ninguna ruta de producción, y
por eso se define el puerto `IdentityPasswordPort` **sin adaptador concreto**:
tener uno exigiría una API key permanente con `POST /api/user` / `PATCH
/api/user`, que la Condición 1 prohíbe. Cuando se apruebe una tarea de
provisioning, su adaptador implementa el puerto y hereda el control.

### Rutas NO cubiertas — residual declarado

**La consola administrativa de FusionAuth.** Un operador con acceso a consola
fija una contraseña dentro de FusionAuth, donde no corre código de JUVAl.
**No está medido** si la consola aplica siquiera las reglas del tenant: fue
marcado `NOT_TESTED` en el laboratorio porque probarlo exigía escribir una
credencial viva en la transcripción de la sesión. **No se afirma que la consola
esté impedida técnicamente de puentear a JUVAl.**

| Elemento | Valor |
|---|---|
| Operador autorizado | El propietario de seguridad de JUVAl (única persona con acceso a consola) |
| Propósito | Recuperación de emergencia y provisioning inicial, nada más |
| Procedimiento de contraseña | Aplicar la misma regla manualmente: ninguna parte del nombre de ≥3 caracteres, mínimo 12, mixta, número, no alfanumérico |
| Expectativa de auditoría | Cada uso queda en el audit log de FusionAuth; se revisa en la revisión de seguridad periódica (RF-05) |
| Riesgo residual | Un operador puede fijar una contraseña que incumpla la Condición 6. Mitigado por procedimiento y por ser una sola persona identificada, **no** por un control técnico |

## Condiciones (vinculantes)

1. **Ninguna API key permanente de FusionAuth puede llevar `POST /api/user`,
   `PATCH /api/user`, `POST /api/user/forgot-password` ni equivalentes**, salvo
   con alcance de ciclo de vida para una tarea administrativa aprobada y
   temporal. ADR-032 sigue siendo vinculante. Esto es lo que hace exigible a la
   Condición general: sin key, no hay ruta que puentee al validador.
2. **No exponer públicamente** `/api/*`, `/admin/*`, `/account/*` ni
   `/password/*` de FusionAuth salvo ADR futuro que autorice una ruta concreta.
   Medido: `/account/` responde **200 en Community sin licencia**, así que es
   una superficie real y no inerte.
3. **Se mantiene el principio de allow-list de nginx**: sólo la superficie OIDC
   pública mínima que el BFF necesita (ADR-034), con `location =` exactos y
   `return 404` por defecto.
4. **La consola administrativa es un bypass residual con nombre**, documentado
   arriba, no un control.

Corolario operativo derivado de la Condición 2 y de la medición L-3: **JUVAl
nunca fija `passwordChangeRequired`**, porque completar ese estado exigiría
publicar `/password/change`. Está anotado en el propio archivo de nginx.

## Consecuencias

- El control existe, es determinístico, está probado (20 tests unitarios de la
  regla + **10 del chokepoint**, todos con datos ficticios) y no depende del
  proveedor de identidad. Los 10 del chokepoint se añadieron el 2026-09-10: la
  auditoría de recuperación encontró `application/password_provisioning.py`
  **sin un solo test**, que es donde vive la propiedad «no hay camino que
  rodee la regla» — la parte que hace del Control 6 un control y no una
  función de validación.
- La superficie de bypass queda enumerada y gobernada, no negada.
- **`CONTROL_6` no pasa a satisfecho.** Etiqueta unificada el 2026-09-10,
  porque el propio proyecto la escribía de dos formas distintas
  (`IMPLEMENTED_NOT_PRODUCTION_VERIFIED` aquí, `B — PARTIALLY_SATISFIED` en el
  laboratorio y en compliance §52.3). La forma canónica separa tres
  afirmaciones que no son la misma:

  | Afirmación | Clase |
  |---|---|
  | FusionAuth 1.69.0 no excluye `firstName`/`lastName`, con control positivo disparando | **`BEHAVIORALLY_VERIFIED`** — en laboratorio aislado, nunca en producción |
  | JUVAl implementa la regla y el chokepoint la hace inevitable | **`VERIFIED_CODE` + `VERIFIED_TEST`** (20 + 10 tests) |
  | Ante Amazon | **`CONTROL_6_AMAZON = PARTIALLY_SATISFIED`** |

  «Implementado y probado» **no** es evidencia de comportamiento y no puede
  citarse a Amazon. Hoy el chokepoint no protege ninguna contraseña real: no
  tiene adaptador ni ruta de producción, a propósito (Condición 1).
- Queda una medición pendiente antes de poder cerrar el residual: si la consola
  administrativa aplica o no las reglas del tenant.

## Estado

**Aceptada con riesgo residual.** Implementada y probada; **no verificada en
producción**. `CONTROL_6_AMAZON = PARTIALLY_SATISFIED`.
