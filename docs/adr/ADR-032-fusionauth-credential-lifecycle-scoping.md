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
