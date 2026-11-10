# Entorno local de integración BFF ↔ frontend-next (SEC-01F)

Un entorno completo, desechable y sintético para desarrollar y verificar el
login real de `frontend-next` contra el backend real, sin FusionAuth, Supabase
ni credenciales reales. Herramienta: `tools/integration_lab.py` (IdP
sintético: `tools/oidc_lab.py`). Contrato: [`BFF_FRONTEND_CONTRACT.md`](BFF_FRONTEND_CONTRACT.md).

## Qué levanta

| Pieza | Detalle |
|---|---|
| PostgreSQL | clúster privado en un directorio temporal, sólo socket unix (sin TCP); roles ADR-048 (`juval_backend` sin privilegios, `anon`…); migraciones 00–09 aplicadas como `postgres` en el orden del runbook; RLS por organización activa |
| Datos | organizaciones sintéticas A y B; membresías: `alice` → A, `bob` → B; `carol` sin organización |
| IdP sintético | `http://localhost:18782`; discovery, JWKS (RS256, clave generada al arrancar), código + PKCE S256, refresh con rotación, logout; página de selección de usuario sin contraseña |
| Backend | uvicorn en `http://localhost:18781`, `JUVAL_AUTH_MODE=oidc`, sesiones en PostgreSQL cifradas, almacén de ejecución en PostgreSQL con RLS, entorno construido desde cero (no hereda variables `JUVAL_*`/`PG*` del operador) |
| Frontend | lo arranca Codex: `frontend-next` en `http://localhost:5173` |

Usuarios sintéticos: `alice` (A, `operator`), `bob` (B, `operator`),
`carol` (sin organización, `viewer`). Todo escucha en loopback. El access
token dura 60 s por defecto (`--token-ttl`), así que cada petición ejercita el
refresh y la re-verificación de roles.

Diferencias deliberadas con producción, sólo para HTTP local:
`JUVAL_BFF_INSECURE_COOKIES=yes-local-http-only` (cookies sin `Secure`) y
emisor `http://localhost:18782`. `localhost` con puertos distintos es el mismo
*site*, así que `SameSite=Lax` y las cookies host-only de la API se comportan
como en la topología ADR-038.

## Arranque

Requisitos: `.venv` del proyecto con el extra `postgres` y binarios de
PostgreSQL (`JUVAL_POSTGRES_BIN`, p. ej. `/usr/lib/postgresql/16/bin`).

```bash
# Terminal 1 (raíz del repo): backend + PostgreSQL + IdP. Ctrl-C lo borra todo.
JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin .venv/bin/python tools/integration_lab.py

# Terminal 2 (frontend-next/, Codex):
VITE_API_BASE_URL=http://localhost:18781 npm run dev -- --port 5173 --strictPort
```

Abrir `http://localhost:5173/` (usar `localhost`, no `127.0.0.1`: debe
coincidir con el origen permitido por CORS y el destino post-login).

## Validación

Automática, sin navegador (la ejecutan los tests si hay binarios de PostgreSQL):

```bash
JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin .venv/bin/python tools/integration_lab.py --check
```

23 comprobaciones: `/healthz`; 401 sin sesión; login con `return_to` que
aterriza en el origen de la app; atributos de cookie; `/session` sin tokens;
CSRF obligatorio; creación por `operator`; BOLA (otra organización = 404
idéntico a inexistente, ausente del listado); 403 sin membresía; sesión
guardada sólo como digest con tokens cifrados; RLS sin GUC = 0 filas; cambio
de rol en el IdP efectivo en la siguiente petición; cuenta desactivada = 401;
`revoke-sessions` inmediato; logout + end-session; cookie capturada inútil
tras logout; eventos de seguridad emitidos y log sin cookies, CSRF ni `sub`.

Manual, en navegador (para Codex, con el frontend arrancado):

1. Sin sesión, la app muestra el aviso de 401 con «Sign in»; no redirige sola.
2. «Sign in» → página del IdP sintético → `alice` → vuelve a la ruta de la
   que salió, en `http://localhost:5173`.
3. Crear un run (envía `X-JUVAL-CSRF`) y verlo en la lista.
4. Logout → vuelve a `http://localhost:5173/`; recargar: sesión cerrada.
5. `bob`: el run de `alice` no aparece; su URL directa da «no encontrado».
6. `carol`: mensaje de «cuenta sin organización asignada».
7. Detener el backend con la app abierta: el error es de red/servicio, nunca
   se muestra como «sesión cerrada».

## Seguridad del entorno

Protecciones comprobadas por `tests/unit/test_integration_lab_safety.py`:

- se niega a arrancar si detecta una plataforma de hosting (`RAILWAY_*`, `VERCEL*`);
- no acepta DSN: los construye sobre su propio socket y rechaza migrar
  cualquier otro destino;
- retira las variables `PG*` del operador mientras se ejecuta (p. ej.
  `PGHOSTADDR` redirigiría libpq a otra base) y las restaura al terminar;
- el backend recibe un entorno construido desde cero: ninguna variable
  `JUVAL_*` del operador (DSN, llaveros) llega a él;
- IdP y backend sólo escuchan en `127.0.0.1`; un puerto ocupado detiene el
  arranque (nunca habla con un servidor ajeno);
- ante cualquier fallo limpia procesos, clúster y directorio temporal sin
  bloquearse.

Ninguna credencial real: el secreto de cliente, la clave de firma y el
llavero de sesiones se generan al arrancar y desaparecen al terminar. El
directorio temporal (datos, logs) se borra salvo con `--keep`. No usar nunca
estos valores, el IdP sintético ni `JUVAL_BFF_INSECURE_COOKIES` fuera de
loopback.
