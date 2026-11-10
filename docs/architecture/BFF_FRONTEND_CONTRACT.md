# BFF ↔ frontend-next — contrato de autenticación y errores (SEC-01E)

**Estado: contrato del backend implementado localmente (2026-11-10, sin commit).**
Fuente de verdad: `src/juval/interfaces/api/bff.py`, `auth.py`, `main.py` y sus
tests. Si este documento y el código difieren, gana el código y se corrige
este documento. Relacionado: ADR-034 (BFF), ADR-036 (sesiones), ADR-038
(topología), ADR-055 (modo fail-closed), ADR-056 (organizaciones).
Prompt para Codex: [`CODEX_BFF_INTEGRATION_PROMPT.md`](CODEX_BFF_INTEGRATION_PROMPT.md).

## 1. Topología (ADR-038)

```
https://app.<dominio>  (Vercel, frontend-next)  --fetch credentials:"include"-->  https://api.<dominio>  (FastAPI + BFF)
                                                 <--top-level navigation--------  /api/v1/auth/login, /callback
https://id.<dominio>   (FusionAuth)
```

- Misma raíz registrable (same-site). Dominio real: `HUMAN_DOMAIN_SELECTION_PENDING`.
- `VITE_API_BASE_URL=https://api.<dominio>`; `JUVAL_CORS_ORIGINS=https://app.<dominio>`
  (exacto, nunca `*`); `JUVAL_BFF_POST_LOGIN_REDIRECT=https://app.<dominio>/`
  (absoluto: ver §3); `JUVAL_BFF_POST_LOGOUT_REDIRECT=https://app.<dominio>/`.
- En desarrollo: `JUVAL_AUTH_MODE=disabled` (lab loopback). No hay sesión;
  `/api/v1/auth/session` responde `{"authenticated": false}` y `/login` 404.

## 2. Cookies (las fija y lee sólo la API)

| Cookie | Contenido | Atributos | JS de la app |
|---|---|---|---|
| `juval_session` | id opaco de sesión | `HttpOnly`, `Secure`, `SameSite=Lax`, host-only, `Path=/`, 8 h | no la ve |
| `juval_csrf` | token CSRF | `Secure`, `SameSite=Lax`, host-only (API), `Path=/` | no la ve (otro host) |
| `juval_oauth_txn` | transacción OAuth | `HttpOnly`, `Secure`, `Lax`, `Path=/api/v1/auth`, 10 min | no la ve |

La app **nunca** guarda tokens, ni en `localStorage` ni en `sessionStorage`. El token CSRF
se obtiene de `/session` y vive sólo en memoria.

## 3. Flujos

**Login.** Navegación de nivel superior (no `fetch`) a
`GET /api/v1/auth/login?return_to=<ruta>` → 302 a FusionAuth (PKCE S256,
`state`, `nonce`) → `GET /api/v1/auth/callback` → 302 al destino.

- `return_to` debe ser una **ruta** de la app (`/runs/abc?tab=x`). Si
  `JUVAL_BFF_POST_LOGIN_REDIRECT` es absoluto, la API la resuelve contra
  **ese** origen (`https://app.<dominio>/runs/abc?tab=x`).
- Se rechazan en silencio (y se va al destino por defecto) las URL absolutas,
  `//host`, rutas con `\` y con caracteres de control.
- Un login nuevo **revoca** la sesión anterior del navegador.

**Errores del callback** (respuesta JSON en el host de la API, el usuario la
ve tal cual; mejora futura PENDING: redirigir a la app con un código):
`400 invalid authorization response` (state, nonce, transacción caducada o
repetida), `400 authorization code exchange failed`, `401 invalid or expired
token` (ID token), `502 identity provider unreachable`, `502 identity provider
returned no id_token`. La app debe ofrecer «Volver a iniciar sesión».

**Sesión.** `GET /api/v1/auth/session` (con `credentials: "include"`) siempre
responde 200 salvo fallo del almacén (503):

```json
{"authenticated": false}
{"authenticated": true, "subject": "<sub>", "roles": ["operator"],
 "permissions": ["runs:create", "runs:export", "runs:read"],
 "expires_at": "2026-11-10T20:00:00+00:00", "csrf_token": "<token>"}
```

`csrf_token` falta si la cookie CSRF no coincide; tratarlo como «volver a
pedir `/session`». `permissions` sirve para mostrar u ocultar acciones; la
autorización real es del servidor.

**Mutaciones.** `POST` con `credentials: "include"` y cabecera
`X-JUVAL-CSRF: <csrf_token>`. Sin ella o errónea: `403 csrf token missing or
invalid`. Releer `/session` y reintentar **una** vez (ya implementado en
`client.ts`).

**Logout.** `POST /api/v1/auth/logout` con `X-JUVAL-CSRF` → `200
{"logged_out": true, "end_session_url": "<url FusionAuth>"}`. La API revoca
la sesión y borra las cookies. Después la app olvida el token CSRF y navega
(nivel superior) a `end_session_url` si existe, para cerrar también la sesión
SSO de FusionAuth; si no, a su pantalla de inicio. Repetir logout es
inofensivo (200).

**Duración de la sesión (decisiones del propietario, SEC-01E).**

- Inactividad: **30 min** (configurable sólo en el servidor,
  `JUVAL_SESSION_IDLE_TIMEOUT_MINUTES`). Cuenta como actividad toda petición
  que la API resuelve con la cookie; nada que declare el navegador.
- Absoluta: **8 h** desde el login; la actividad no la extiende.
- Roles: válidos mientras lo sea el access token del IdP. Al vencer, la API
  los renueva con el refresh token y los vuelve a verificar; sin refresh
  token la sesión termina (`401`); con el IdP caído, `503 identity provider
  temporarily unavailable` y la sesión se conserva.
- La app **no debe** consultar `/session` con un temporizador: mantendría
  viva una pestaña abandonada y anularía la inactividad. Consultarla al
  cargar, tras un 401/403 de CSRF y tras volver de un login.

**Sesión expirada o revocada.** `/session` → `{"authenticated": false}`; las
rutas de datos → `401`. No hay renovación silenciosa: volver a iniciar sesión.

## 4. Códigos de estado de las rutas de datos (`/api/v1/runs…`, `/api/v1/batches…`)

| Código | `detail` exacto | Significado | UI |
|---|---|---|---|
| 401 | `missing bearer token` (y otros 401) | sin sesión válida (nunca hubo, expiró, revocada) | estado «sesión cerrada» + enlace a login; **sin** redirección automática |
| 403 | `csrf token missing or invalid` | CSRF | reintento único; si persiste, «recarga la página» |
| 403 | `insufficient permissions` | el rol no permite la acción | «sin permiso para esta acción» |
| 403 | `no organization access for this identity` | identidad válida sin organización JUVAl (sin autoaprovisionamiento) | «tu cuenta no tiene organización asignada; contacta al administrador» — no ofrecer reintento |
| 404 | `unknown execution_id`, `unknown record for execution`, `unknown or expired execution_id`, `unknown batch_id`, `this run is not part of a batch` | no existe **o es de otra organización** (indistinguible a propósito) | «no encontrado»; nunca sugerir que existe |
| 503 | `session service unavailable` | almacén de sesiones caído | «servicio no disponible temporalmente», reintento manual; **no** tratar como sesión cerrada |
| 503 | `organization membership is temporarily unavailable` | base de datos caída | igual |
| 503 | `identity provider temporarily unavailable` | el IdP no responde al renovar roles | igual |
| 503 | `authentication is not initialised` | instancia arrancando | igual |
| 422 / 413 | validación / tamaño | — | mensajes existentes |

`GET /healthz` es la única ruta pública: liveness, `{"status":"ok"}`. No es
para la app.

Rutas `/api/v1/auth/*` bajo `JUVAL_AUTH_MODE=disabled`: `404 authentication
is not enabled`; OIDC sin BFF configurado: `404 browser authentication is not
configured`.

## 5. Invariantes que el frontend no debe romper

- Ninguna redirección automática ante 401 (bucles de login).
- `credentials: "include"` en toda llamada a la API; nada de cabecera `Authorization`.
- Nunca leer, escribir ni ampliar cookies de la API (`Domain`).
- El token CSRF sólo en memoria; se olvida tras logout, 401 o login.
- No inferir existencia de recursos ajenos: 404 es 404.
- No sondear `/session` periódicamente (§3, inactividad).
