# ADR-032 — Credenciales de FusionAuth con alcance por ciclo de vida

**Estado: Aceptada**, por instrucción explícita del usuario, practicada en
dos sesiones consecutivas (2026-09-01) antes de quedar escrita aquí — este
ADR transcribe una decisión ya tomada, no propone una nueva.
**Fecha: 2026-09-01.**
**Relacionada con:** ADR-031 (alojamiento self-hosted de FusionAuth),
ADR-027 (rol de `juval-server`), `docs/compliance/
SP_API_REGISTRATION_REMEDIATION.md` §33/§38/§39/§40, `tools/
configure_fusionauth.py`, `tools/verify_rbac.py`, `tools/
verify_identity_behavior.py`.

## Contexto

El bootstrap de FusionAuth (§33/§38) usó una única API key ("JUVAl
Bootstrap") con una ACL de mínimo privilegio explícita: `GET/POST/PATCH
/api/tenant`, `GET/POST/PATCH /api/application`, `POST /api/application/
role`. Cuando la verificación RBAC (§39/§40) necesitó `POST /api/jwt/vend`,
el usuario **amplió esa misma key** en un paso separado, aprobado
explícitamente, y no antes.

Al preparar la siguiente verificación — comportamiento real de contraseña/
lockout/MFA, que necesita `POST /api/user`, `POST /api/user/registration`,
`POST /api/login`, `POST /api/user/two-factor/{id}`, `POST /api/two-factor/
login`, `GET /api/user/action` — el usuario dio una instrucción distinta:
**no ampliar la key de bootstrap**, sino preparar el diseño para una key
**separada y nueva**, "JUVAl Identity Verification", con su propia ACL
mínima, que el operador crea manualmente después de revisar la matriz
exacta que este ADR/reporte deja documentada.

Este patrón — una key por *propósito de ciclo de vida*, nunca una key
"maestra" que va acumulando permisos a medida que aparecen nuevas
necesidades — ya se practicó dos veces de forma consistente, sin que
mediara una decisión de diseño explícita previa por escrito. Vale la pena
fijarlo antes de que aparezca una tercera necesidad (verificación pública
del emisor, Fase 2; o el propio backend de producción, que ni siquiera
necesita una API key de FusionAuth porque solo consume JWKS de forma
anónima).

## Decisión

FusionAuth se opera en JUVAl con **credenciales de API key separadas por
ciclo de vida**, nunca una key compartida entre etapas:

1. **`JUVAl Bootstrap`** — provisioning de tenant/aplicación/roles/política.
   ACL: `GET/POST/PATCH /api/tenant`, `GET/POST/PATCH /api/application`,
   `POST /api/application/role`. Usada también, tras ampliación explícita
   y puntual del usuario, para `POST /api/jwt/vend` (verificación RBAC
   sintética vía token minteado, no un login real).
2. **`JUVAl Identity Verification`** (próxima, no creada todavía) —
   verificación de comportamiento real (usuarios desechables, login,
   lockout, MFA). ACL propia, exhaustivamente distinta de la de bootstrap:
   `POST /api/user`, `GET /api/application`, `POST /api/user/registration`,
   `POST /api/login`, `POST /api/user/two-factor`, `POST /api/two-factor/
   login`, `GET /api/user/action`. **Sin** `/api/tenant*` — no la necesita,
   y pedirla sería ampliar la superficie sin motivo (ver el reporte de
   sesión 2026-09-01 para la justificación endpoint por endpoint).
3. **Runtime (producción)** — el backend (`src/juval/interfaces/api/
   auth.py::build_verifier`) **no usa ninguna API key de FusionAuth**. Solo
   lee `/.well-known/jwks.json` (público, sin autenticar) para verificar
   firmas. Esto ya era así antes de este ADR; se documenta aquí para dejar
   completo el ciclo de vida: bootstrap (una vez) → verificación (bajo
   demanda, temporal) → runtime (ninguna key).

**Regla operativa, para toda key futura:**

- una key nueva se crea con la ACL mínima que su propósito requiere, nunca
  heredando o ampliando la ACL de una key de otro propósito;
- ampliar la ACL de una key existente es una decisión explícita del
  usuario, nunca automática ni "por conveniencia de implementación"
  (CLAUDE.md §4);
- el agente **nunca** crea, ve o amplía una key por su cuenta — reporta la
  ACL exacta necesaria (método + endpoint + motivo) y el operador decide y
  ejecuta en la UI de FusionAuth;
- `DELETE`, `PUT`, Key Manager, `/api/key*` y `/api/system*` quedan fuera
  de cualquier key operativa de JUVAl salvo necesidad explícita y aprobada
  caso por caso — ninguna key actual los tiene, ni de bootstrap ni de
  verificación;
- una key cuyo propósito ya se cumplió (por ejemplo, bootstrap, una vez
  que tenant/aplicación/roles/política están estables y no se espera
  reconfigurarlos) es candidata a revocación — no auto-eliminada por este
  ADR, pero sí una acción que el operador puede tomar sin que eso rompa
  nada del lado del agente, porque el agente nunca depende de una key
  específica seguir viva más allá de la tarea para la que se le dio.

## Consecuencias

- Cada verificación (bootstrap, RBAC, comportamiento) tiene una superficie
  de fallo y de exposición mínima y auditable independientemente — si una
  key de verificación se filtrara, el daño máximo son operaciones sobre
  usuarios desechables de prueba, nunca gestión de tenant/aplicación.
- Más fricción operativa (el operador crea/revisa más de una key a lo
  largo del proyecto) a cambio de una propiedad de seguridad real, no
  cosmética.
- Este ADR no crea ninguna key nueva ni cambia ninguna ACL — documenta el
  patrón ya seguido y lo deja como referencia para la próxima vez que
  aparezca una necesidad de acceso nueva.

## Estado

**Aceptada.** No bloquea nada pendiente; no introduce trabajo nuevo. La
key `JUVAl Identity Verification` sigue sin crearse — su ACL exacta está
en el reporte de la sesión 2026-09-01 (ver también `docs/compliance/
SP_API_REGISTRATION_REMEDIATION.md` §41 si esta sesión registra evidencia
ahí) y en `tools/verify_identity_behavior.py`, pendiente de creación manual
por el operador antes de cualquier ejecución en vivo.

---

## Enmienda 2026-09-07 — la credencial de verificación behavioral son **siete** grants exactos

**Estado: Aceptada** (aprobación explícita del usuario, 2026-09-07). No
supersede nada de lo anterior; fija con precisión el punto 2 de la Decisión.

### Qué se fija

La credencial del punto 2 se llama **`JUVAL Behavioral Verification 1`** y su
ACL es **exactamente estos siete grants, ni uno más**:

| # | Método | Endpoint | Para qué |
|---|---|---|---|
| 1 | `GET` | `/api/application` | targeting fail-closed (`verify_targeting()`) |
| 2 | `POST` | `/api/user` | crear usuarios desechables (P-01…P-06, C6-01/C6-02) |
| 3 | `GET` | `/api/user/action` | leer el estado de bloqueo (L-02…L-05) |
| 4 | `POST` | `/api/user/registration` | registrar el usuario en la aplicación |
| 5 | `POST` | `/api/user/two-factor` | enrolar TOTP (M-02/M-03) |
| 6 | `POST` | `/api/two-factor/login` | completar el segundo factor (M-05/M-06/M-07) |
| 7 | `POST` | `/api/login` | login real (M-01/M-04, L-01/L-04) |

`GET /api/user/action` y `POST /api/two-factor/login` se envían **sin**
`X-FusionAuth-TenantId` (`scope_tenant=False`); los demás lo llevan.

### Por qué se registra esto

La ACL de siete endpoints ya estaba en el cuerpo de este ADR desde su
redacción. Entre §41 y §46 el trabajo derivó a hablar de "los seis
aprobados", omitiendo `POST /api/two-factor/login`. Esa deriva no fue
inocua: con seis permisos ese endpoint devuelve `401`, y
`tools/verify_identity_behavior.py` puntuaba **M-05** como
`PASS if status not in (200,)` y **L-04** como
`PASS if status not in (200, 242)`. Ambos convertían un rechazo de
autorización en evidencia de política — "código TOTP incorrecto rechazado",
"el bloqueo se mantuvo" — sin que la política se hubiera evaluado nunca.

Corregido en código (`SP_API_REGISTRATION_REMEDIATION.md` §47.5) con seis
tests de regresión. Se deja escrito aquí porque el ADR es el sitio donde se
consulta la ACL, y una ACL mal transcrita fue lo que habilitó el falso
positivo.

**Esto no es un broadening genérico.** El séptimo endpoint es
lifecycle-scoped y estrictamente necesario para la verificación behavioral;
no amplía la superficie a gestión de tenant, aplicación, claves ni sistema.
La regla operativa del cuerpo del ADR sigue intacta: `DELETE`, `PUT`,
`PATCH`, Key Manager, `/api/key*`, `/api/system*` y `/api/tenant*` quedan
fuera.

### Regla de clasificación, obligatoria para toda verificación behavioral

```
401 / 403  -> fallo de autenticación/autorización de la API key
           -> BLOCKED (fallo de evidencia de infraestructura)
           -> NUNCA PASS de un test de política o comportamiento

404 u otro status esperado del endpoint puede ser evidencia behavioral
solo si la semántica del endpoint y el test lo justifican explícitamente.
```

FusionAuth responde `404` a una credencial o a un código TOTP incorrectos;
`401` queda reservado para el fallo de autorización de la API key. Confundir
ambos es exactamente el error que §39–§46 arrastró durante toda la
investigación del 401.

### Ciclo de vida de esta credencial

Creada manualmente por el operador en la GUI (nunca por el agente, nunca vía
Playwright/MCP, que no abre el formulario Add API Key), Not Retrievable, Key
Manager OFF, tenant `JUVAl`, expiración ≤24 h, y **revocada al terminar** la
verificación. La expiración corta es respaldo, no el plan. No reutilizar
`JUVAl Identity Verification` (IV1/IV2/IV3) ni ninguna key de bootstrap.
