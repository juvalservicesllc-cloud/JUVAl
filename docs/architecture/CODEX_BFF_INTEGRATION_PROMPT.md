# Prompt para Codex CLI — integración de frontend-next con el BFF (SEC-01E)

Copiar el bloque siguiente, completo, en Codex CLI desde `/home/juval/JUVAl/APP`.

```text
# JUVAl — frontend-next: integración de autenticación con el BFF (SEC-01E)

## Rol y alcance
Eres responsable exclusivamente de `frontend-next/`. No modifiques nada fuera
de ese directorio (backend, docs, tools, supabase, otros frontends). Si algo
del backend parece incorrecto, detente y repórtalo; no lo cambies.

## Contrato (fuente de verdad)
Lee primero, completos:
- docs/architecture/BFF_FRONTEND_CONTRACT.md  (contrato exacto: flujos, cookies, códigos y textos `detail`)
- frontend-next/src/api/client.ts y frontend-next/src/app/App.tsx (estado actual)
- docs/adr/ADR-038-browser-site-topology-readiness.md (topología same-site)
Si el contrato y el comportamiento observado del backend difieren, para y repórtalo.

## Estado actual verificado
- client.ts ya envía `credentials: "include"`, obtiene el CSRF de
  GET /api/v1/auth/session, lo guarda sólo en memoria, reintenta una vez ante
  `403 csrf token missing or invalid` y notifica 401 sin redirigir.
- App.tsx muestra un aviso con enlace «Sign in» ante 401.
- No existe logout, no se envía `return_to`, y el 403 de «sin organización» y
  los 503 no tienen mensajes propios.

## Tareas (mínimas, sin rediseño visual)
1. Login con retorno: `loginUrl(returnTo)` añade `?return_to=<ruta actual>`
   (sólo pathname+search+hash de la app, codificado con URLSearchParams; nunca
   una URL absoluta). El aviso de 401 lo usa con la ruta actual.
2. Logout: función `logout()` en client.ts: obtiene el token CSRF, hace
   `POST api/v1/auth/logout` con `X-JUVAL-CSRF`, llama a `resetSession()` y
   navega (window.location.assign) a `end_session_url` si viene, si no a "/".
   Si /session dice `authenticated: false`, no mostrar el control.
   Colocar el control en el lugar existente del shell para acciones de cuenta,
   reutilizando componentes y estilos actuales. Ningún estilo nuevo.
3. Mensajes en `apiErrorMessage` (texto, sin cambios visuales):
   - 403 `no organization access for this identity` → "Your account is not
     assigned to an organization. Contact your JUVAl administrator."
   - 503 (cualquier `detail`) → "The service is temporarily unavailable. Try
     again in a moment." — no tratarlo como sesión cerrada, no notificar 401.
   - 404 → mantener el comportamiento actual (no insinuar que el recurso existe).
4. Estado de sesión: exponer desde client.ts una lectura de
   GET /api/v1/auth/session (authenticated, subject, permissions, expires_at)
   para que el shell sepa si mostrar logout; no duplicar la caché del CSRF.
5. Sesión: inactividad de 30 min y máximo de 8 h los decide el servidor.
   NO consultar /session con un temporizador ni simular actividad (anularía
   la inactividad). Consultarla al cargar, tras un 403 de CSRF y tras el
   login. Un 401 posterior es la señal de sesión terminada.
6. Modo lab (`JUVAL_AUTH_MODE=disabled`): /session da `authenticated: false`
   y /login responde 404. Nada de lo anterior debe romper el lab ni los E2E.

## Prohibido
- Cambios visuales, de layout, de tema o de componentes de diseño.
- Guardar tokens o el CSRF en localStorage/sessionStorage/IndexedDB.
- Cabecera Authorization, lectura de cookies, `document.cookie`.
- Redirección automática ante 401.
- Sondeo periódico de /api/v1/auth/session o "keep-alive".
- Ampliar CORS, dominios o cookies; tocar el backend.
- Dependencias nuevas.
- Commits, push o deploy sin autorización explícita del propietario.

## Pruebas
- Vitest: loginUrl con return_to (rutas válidas; URL absoluta descartada),
  logout (CSRF enviado, resetSession, navegación a end_session_url y a "/"),
  mensajes 403-sin-organización y 503 (incluido `identity provider
  temporarily unavailable`), 503 no dispara onAuthRequired, ningún
  temporizador consulta /session.
- Ejecutar los tests y el typecheck/lint existentes de frontend-next.
- E2E existentes en modo lab sin regresión; usar
  JUVAL_CHROME_BIN=/snap/chromium/current/usr/lib/chromium-browser/chrome.
- No ocultar fallos con skips ni mocks permisivos.

## Informe final
Estado, archivos modificados, tests ejecutados con resultado, desviaciones del
contrato encontradas, riesgos y próximo paso. Sin commits.
```
