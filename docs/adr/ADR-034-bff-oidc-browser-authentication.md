# ADR-034 — Topología de autenticación del navegador: BFF

**Estado: Aceptada**, por decisión explícita del usuario (2026-09-09).
**Fecha: 2026-09-09.**
**Relacionada con:** ADR-028 (FusionAuth como proveedor), ADR-031 (alojamiento
self-hosted), ADR-032 (ciclo de vida de credenciales), ADR-033 (estrategia de
verificación), ADR-035 (Control 6), **ADR-036 (Propuesta — almacén de sesiones
duradero, bloquea la activación)**, `docs/research/IDENTITY_AMAZON_DEEP_RESEARCH.md`,
`docs/research/FUSIONAUTH_169_IDENTITY_LAB.md`,
`src/juval/interfaces/api/bff.py`, `deploy/fusionauth/nginx-fusionauth-public.conf`.

## Contexto

La arquitectura de runtime declarada era:

```
navegador → FusionAuth OIDC → Authorization Code → PKCE → JWT → JWKS → FastAPI → RBAC
```

La investigación de 2026-09-09 midió que **no existía**: `frontend/`,
`frontend-next/` y `demo/` no contienen ni una línea de cliente OIDC, y la
superficie pública planificada (`nginx-fusionauth-public.conf`) exponía
exactamente dos rutas — el documento de discovery y el JWKS — devolviendo 404
para `/oauth2/authorize`. Era la mitad de verificación de tokens sin la mitad
de login humano.

Al construir la mitad que falta hay exactamente dos formas defendibles:

| | (i) BFF en el backend | (ii) Cliente público SPA con PKCE |
|---|---|---|
| Custodia de tokens | Servidor | Navegador |
| Superficie ante XSS | Cookie `HttpOnly` ilegible por JS | Access **y refresh** token al alcance de cualquier XSS |
| Complejidad | Endpoints nuevos + almacén de sesión | Menos código de servidor |
| RFC 9700 §4.9.3 | Cumple de forma natural | Cumple sólo con disciplina de almacenamiento |

Una tercera opción, el **Hosted Backend** de FusionAuth (`/app/*`, cookies
`HttpOnly`, PKCE y `state` gestionados por el proveedor), sería ideal y **no es
utilizable**: el fabricante exige que la aplicación y FusionAuth compartan
dominio o sean subdominios de uno. JUVAl es Vercel + Railway + un emisor
tunelizado — tres orígenes sin relación. Queda descartada por hecho técnico
medido, no por preferencia.

El frontend de JUVAl está además en rediseño activo (ADR-023/029/030). Poner
refresh tokens al alcance del JavaScript de una UI que cambia semana a semana
es aceptar un riesgo cuyo control depende de que ningún componente nuevo
introduzca un XSS. No es un riesgo que este proyecto deba aceptar por ahorrar
un endpoint.

## Decisión

**La topología de autenticación del navegador es un Backend-for-Frontend.**

```
navegador/PWA
   │  cookie de sesión opaca, Secure + HttpOnly + SameSite=Lax
   ▼
JUVAl FastAPI (BFF)  ── Authorization Code + PKCE S256 ──▶ FusionAuth
   │                 ◀────────── JWT / JWKS ──────────────┘
   ▼
Principal → RBAC (interfaces/api/auth.py)
```

**Se rechaza explícitamente la custodia de tokens portadores en la SPA.**
Ningún access token, refresh token, ID token, `code_verifier`, `state`,
`nonce`, `twoFactorId` ni `changePasswordId` se entrega al navegador. Revertir
esto exige un ADR que supersede a éste; no es una decisión de implementación.

### Custodia server-side (obligatoria)

| Artefacto | Dónde vive | Por qué no en el navegador |
|---|---|---|
| `state` | `OAuthTransaction` | Es el vínculo CSRF entre la petición de autorización y su callback (RFC 9700 §2.1.3) |
| `code_verifier` (PKCE) | `OAuthTransaction` | Si lo tuviera el navegador, PKCE no protegería nada que la cookie no proteja ya |
| `nonce` | `OAuthTransaction` | Liga el ID token a *esta* petición; impide replay de ID tokens |
| `redirect_uri` | `OAuthTransaction` | Se guarda, no se deriva de `Host`/`X-Forwarded-Host`: una cabecera falsificada no puede cambiar a dónde va el código |
| access / refresh token | `Session` | RFC 9700 §4.9.3: son secretos |
| `twoFactorId`, `changePasswordId` | `Session` / no expuestos | Credenciales de un solo uso |
| Estado de logout | `Session` | El cierre debe ser efectivo en el servidor, no una cookie borrada |

### Detalle del protocolo

- **Grant**: Authorization Code. **PKCE S256 siempre**, incluso siendo cliente
  confidencial: PKCE frena la inyección de código de autorización en el
  redirect, cosa que un client secret no hace. `plain` no se ofrece.
- **`state`**: 32 bytes aleatorios, comparado con `hmac.compare_digest`.
- **`nonce`**: 32 bytes, verificado contra el ID token.
- **Emisor / audiencia / expiración / RS256 / JWKS**: se reutiliza
  `auth.py::TokenVerifier`. **No hay una segunda ruta de verificación** — dos
  implementaciones de la misma comprobación divergen con el tiempo.
- **Redirect URI**: exacto, configurado (`JUVAL_BFF_REDIRECT_URI`), enviado al
  authorization endpoint y repetido al token endpoint.
- **`return_to`**: sólo rutas absolutas del mismo sitio; se rechaza cualquier
  cosa con esquema o autoridad, incluido `//host` protocolo-relativo.

### Modelo de sesión y cookies

| Cookie | `HttpOnly` | `Secure` | `SameSite` | Contenido |
|---|---|---|---|---|
| `juval_session` | **Sí** | Sí | Lax | id opaco de sesión — es *la* credencial |
| `juval_oauth_txn` | **Sí** | Sí | Lax | id de transacción OAuth, TTL 10 min, ruta `/api/v1/auth` |
| `juval_csrf` | **No, a propósito** | Sí | Lax | token CSRF que la SPA debe reenviar en `X-JUVAL-CSRF` |

**Justificación de `SameSite=Lax`** (no es un valor por defecto): FusionAuth
devuelve al usuario mediante una **navegación GET de nivel superior** al
callback. `Lax` envía cookies exactamente en ese caso y las retiene en POST
cross-site y en subrecursos — que es la propiedad CSRF deseada. `Strict` las
retendría también en el callback y rompería el flujo. `None` las enviaría en
todo contexto cross-site, estrictamente peor. `Lax` es el valor más estricto
que funciona.

`Secure` está activo salvo que se fije exactamente
`JUVAL_BFF_INSECURE_COOKIES=yes-local-http-only` (desarrollo local sobre HTTP).
Cualquier otro valor lo deja activo: un error tipográfico no puede degradar la
cookie en producción.

### CSRF

Doble envío: la cookie `juval_csrf` debe coincidir con la cabecera
`X-JUVAL-CSRF`, comparadas con `hmac.compare_digest`. Se exige en toda petición
que cambia estado y está autenticada **por cookie**. Un llamador con bearer
token no es un navegador y no puede sufrir CSRF; exigírselo sería teatro que
rompe clientes de servicio.

`SameSite=Lax` ya bloquea el POST cross-site en navegadores actuales; esto es
la segunda capa, porque `Lax` es un comportamiento del navegador y no un
control del servidor, y porque un subdominio comprometido lo derrota.

### CORS

`allow_credentials=True` pasa a ser necesario (la PWA y la API están en
orígenes distintos y el navegador no adjuntaría la cookie). Es seguro
únicamente porque `service.cors_origins()` es una lista explícita, vacía por
defecto, que **nunca** puede ser `*` — la propia especificación CORS prohíbe
`*` junto con credenciales.

### Refresh, rotación y logout

- El refresh token vive en la sesión del servidor. La renovación es
  server-side; el navegador nunca ve el intercambio.
- **La rotación de la sesión en el refresh no está implementada todavía** y se
  declara como trabajo pendiente, no como propiedad existente.
- `POST /api/v1/auth/logout` borra la sesión server-side y devuelve la URL de
  `end_session` para que el cliente navegue a ella. Sin esa segunda mitad, la
  sesión SSO de FusionAuth sobrevive y el siguiente login reautentica en
  silencio.

### Semántica de errores

Se conserva la ya existente y correcta: **401** sin credencial o con credencial
inválida (con `WWW-Authenticate: Bearer error="invalid_token"`, RFC 6750 §3);
**403** autenticado pero sin permiso, y también fallo de CSRF. El orden de
resolución es **cookie primero, bearer después**: para el navegador la cookie
es la única credencial, y así una cabecera `Authorization` obsoleta no puede
ensombrecer una sesión válida.

### Superficie pública de FusionAuth

`deploy/fusionauth/nginx-fusionauth-public.conf` pasa de dos rutas a las
mínimas que el BFF necesita. **Corregido 2026-09-10** — el texto anterior decía
«cinco rutas exactas» y que dos elementos quedaban «sin medir»; el archivo real
contiene diez reglas, y las dos «sin medir» sí estaban escritas. El inventario
real es:

| Regla | Necesidad ante el proveedor | Despacho del proxy (lab 2026-09-10) |
|---|---|---|
| `/.well-known/openid-configuration`, `/.well-known/jwks.json`, `/oauth2/authorize`, `/oauth2/token`, `/oauth2/logout` (exactas) | Justificadas por el propio protocolo | `LAB_BEHAVIOURALLY_VERIFIED` |
| `/oauth2/two-factor`, `/oauth2/two-factor-methods` (exactas) | **`NOT_VERIFIED`** | `LAB_BEHAVIOURALLY_VERIFIED` |
| `/css/`, `/js/`, `/images/` (prefijos) | **`NOT_VERIFIED`** | `LAB_BEHAVIOURALLY_VERIFIED` + **hallazgo N-1** |

Todo lo demás sigue en 404, incluidos `/admin`, `/api`, `/account` y
`/password` (ADR-035 Condición 2) — **medido**, y medido además que ninguna
petición denegada alcanza el upstream, que es la propiedad que justifica una
allow-list.

**Las dos columnas no deben colapsarse.** El laboratorio del 2026-09-10
(`docs/research/NGINX_PUBLIC_SURFACE_LAB.md`) ejecutó esta plantilla bajo un
nginx real con un upstream de eco: mide el **proxy**. Las cinco reglas
`NOT_VERIFIED` lo son por una pregunta sobre el **proveedor** — qué sirve
FusionAuth 1.69.0 y qué assets piden sus páginas hospedadas — que necesita una
instancia de FusionAuth. **Siguen `NOT_VERIFIED` y siguen bloqueando la Fase 2.**

**Hallazgo N-1, abierto**: el inventario de la plantilla afirma «Everything
else: 404» y para tres URIs es falso. `/css`, `/js` e `/images` responden 301
hacia la forma con barra, con `Location` construido desde el `Host` del cliente,
en `http://` y filtrando el puerto del listener. `proxy_set_header Host` no lo
afecta porque el redirect precede al proxy. Resolverlo (`absolute_redirect off;`,
estrechar los prefijos a rutas exactas, o eliminarlos) es una decisión previa a
la Fase 2, no una limpieza — y los tres prefijos ya eran las reglas más anchas
y peor justificadas del archivo.

Las cinco últimas llevaban en el archivo la anotación «MEASURED 2026-09-09».
La auditoría de recuperación (2026-09-10) **no pudo correlacionar esa
afirmación con ninguna evidencia registrada**: el documento de laboratorio da
el lab por destruido antes de esa hora y no lista esas rutas. La afirmación
queda **retirada** — no reescrita — y las reglas siguen en la plantilla marcadas
`NOT_VERIFIED`. **Medirlas en un laboratorio nuevo es un prerrequisito de la
Fase 2**, y los tres prefijos son además las reglas más anchas del archivo, así
que no se habilitan sobre una base no verificada.

## Consecuencias

- El backend gana estado de sesión, que hasta ahora no tenía. Eso obligó a
  decidir un almacén duradero: **ADR-036 (`Aceptada`, 2026-09-09)**. El
  adaptador en memoria que se entrega es correcto para un proceso y **falso
  para varios**, y desde 2026-09-10 el proceso no puede arrancar con una
  selección de almacén inválida (`main.py::_lifespan`).
- `JUVAL_AUTH_MODE` **sigue sin definir**. Activarlo exige: (1) ADR-036
  decidido, (2) superficie pública ampliada y verificada, (3) integración del
  frontend, (4) tenant con usuarios reales. Ninguna está completa.
- **El frontend necesitará cambios**: hoy no envía credencial alguna. El
  contrato exacto se reporta antes de tocar `frontend/`, que sigue congelado.
- Se gana una propiedad real: un XSS en la PWA no puede robar un token de
  FusionAuth, porque no hay ninguno que robar en el navegador.

## Estado

**Aceptada.** Implementada en `src/juval/interfaces/api/bff.py` con 34 tests
(28 originales + 6 de arranque/cableado añadidos en la consolidación de
2026-09-10). **No activada.**

Corrección de 2026-09-10, registrada aquí porque afecta a una propiedad que
este ADR daba por cierta: los consumidores de sesión leían un global de módulo
que `build_stores()` podía no haber poblado nunca, así que un worker que no
hubiera servido `/login` respondía desde el marcador de pre-inicialización. Era
fail-closed (401) pero la sesión duradera no se usaba. Ahora hay un único punto
de inicialización (`bff.ensure_configured()`), al que llegan login, callback,
resolución de sesión, refresh, CSRF y logout.

## Session projection correction — 2026-09-10 accelerator

After a rejected refresh, `/api/v1/auth/session` previously fell back to the
pre-refresh record and reported authenticated despite revocation. It now
reloads the store after refresh; absent/revoked state reports unauthenticated
and clears cookies. A transport outage still preserves the session per ADR-036.
HTTP-level tests exercise both outcomes. This corrects presentation of the
existing security state without changing the role or refresh policy.
