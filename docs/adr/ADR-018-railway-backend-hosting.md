# ADR-018: Railway como hosting del backend FastAPI

- Estado: Aceptada — aprobada explícitamente por el usuario 2026-08-17
  ("El usuario APRUEBA Railway como proveedor de hosting del backend"),
  tras una comparación previa de Render/Railway/Fly.io/VPS (ver
  `docs/PROJECT_STATUS.md` §Sesión 2026-08-17, bloque 7).
- Fecha: 2026-08-17

## Contexto

ADR-014 eligió PWA como interfaz principal; ADR-016 eligió FastAPI para
el backend, ya implementado y probado (`interfaces/api/`, 19 tests). La
sesión de deployment previa (bloque 5) aprobó explícitamente **Opción
A**: Vercel solo para el frontend estático; el backend necesita un
proveedor de proceso Python de larga duración, distinto de Vercel
Functions, porque el contrato actual (`POST /api/v1/runs` escribe
`output.xlsx`; `GET .../download` lo lee en un request posterior)
depende de que el mismo proceso/filesystem persista entre ambos
requests — algo que Vercel Functions no garantiza (`/tmp` efímero entre
invocaciones, ver `docs/architecture/API_CONTRACT.md` §8.4).

Se comparó Render, Railway, Fly.io y un VPS genérico (bloque 7). Además
del hallazgo de que los cuatro son técnicamente compatibles con el
contrato actual sin cambios, se encontró un diferenciador operativo
concreto y relevante ahora mismo: GitHub está temporalmente
indisponible para el usuario, y **Render depende de un repositorio
Git conectado** (GitHub/GitLab/Bitbucket) para su flujo de deploy
estándar — no ofrece un `git push`/CLI-only equivalente sin repositorio
remoto. Railway y Fly.io sí permiten desplegar directamente desde el
directorio local vía su propio CLI, sin ningún repositorio Git.

## Decisión

Juval usa **Railway** para alojar el backend FastAPI
(`interfaces/api/`). Configuración mínima en `railway.toml`
(raíz del repositorio):

```toml
[build]
builder = "RAILPACK"
buildCommand = "pip install .[postgres]"

[deploy]
startCommand = "uvicorn juval.interfaces.api.main:app --host 0.0.0.0 --port $PORT"
```

**Hallazgo técnico verificado durante esta sesión, no asumido**:
`pip install -e .` (y equivalentemente `pip install .`) ya funciona
correctamente hoy sin necesidad de una tabla `[build-system]` explícita
en `pyproject.toml` — el backend de build por defecto de `pip`
descubre `src/juval/` automáticamente. Verificado con
`import juval; from juval.interfaces.api.main import app` funcionando
**sin** la variable `PYTHONPATH=src` que `tests/`/desarrollo local
usan por convención de `pytest` (`pyproject.toml::[tool.pytest.ini_options]`).
Esto significa que el `buildCommand` de Railway (`pip install .`)
produce un entorno donde `uvicorn juval.interfaces.api.main:app` corre
de forma nativa, sin ningún hack de `PYTHONPATH` en producción — más
correcto que replicar la convención de testing en producción.

`--host 0.0.0.0` es obligatorio (Railway enruta tráfico al contenedor,
no a `localhost`/`127.0.0.1`); `$PORT` es la variable dinámica que
Railway inyecta en cada deploy — nunca un puerto fijo hardcodeado.

## Qué NO resuelve esta decisión

- **No se ejecutó ningún `railway up`** — esta ADR y `railway.toml`
  dejan el proyecto *preparado*, no desplegado. El comando exacto que
  el usuario debe ejecutar (tras `railway login`) queda documentado en
  `docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloque 8).
- **No se implementó `GET /health`**. Railway soporta un
  `healthcheckPath` opcional en `railway.toml`; sin él, usa una
  comprobación TCP por defecto sobre el puerto vinculado, suficiente
  para detectar un proceso caído. Un endpoint de salud dedicado es una
  mejora razonable (`[RECOMENDACIÓN]`, no aplicada) — no se agregó
  porque cambiar `interfaces/api/main.py` sin que el usuario lo pida
  explícitamente habría sido exactamente el tipo de decisión que este
  ADR debe documentar antes de ejecutar, no ejecutar de paso.
- **No se fijó `JUVAL_CORS_ORIGINS`** a ningún valor real — depende de
  la URL que Vercel asigne al frontend, que todavía no existe (Vercel
  sigue sin desplegar, bloqueado por login). No se inventó ninguna URL.
- **No se verificó Railway contra una cuenta real** — `railway whoami`
  confirma que no hay sesión iniciada; el CLI está instalado y
  funcional, pero nunca se autenticó.
- ~~No cablea `SupabaseExecutionRunStore` en `main.py`~~ — **RESUELTO
  2026-08-17**: `main.py::_execution_run_store` selecciona por
  `JUVAL_EXECUTION_STORE` (`sqlite`|`supabase`), ver
  `docs/architecture/API_CONTRACT.md` §5. El extra `postgres` del
  `buildCommand` (`pip install .[postgres]`) ya instala `psycopg` en el
  build de Railway, que es exactamente lo que este cableado necesita en
  runtime — no requiere cambios adicionales en `railway.toml`.
- **Sigue sin verificarse Railway contra una cuenta real** —
  `[REVERIFICADO 2026-08-17]`: `railway --version` → `5.41.2` (CLI
  instalada globalmente), `railway whoami` → `Unauthorized`. `railway
  login` requiere OAuth interactivo (navegador o `--browserless` con
  device-code) — no completable por el agente, comando exacto queda
  documentado en `docs/PROJECT_STATUS.md`.

## Alternativas descartadas (ver comparación completa, bloque 7)

- **Render**: bloqueado hoy por depender de un repositorio Git
  conectado, indisponible mientras GitHub siga caído para el usuario.
  No descartado permanentemente — viable cuando GitHub regrese.
- **Fly.io**: técnicamente equivalente a Railway (tampoco requiere
  GitHub, vía `flyctl deploy`), pero requiere un `Dockerfile` explícito
  y tiene una curva de configuración algo mayor. Alternativa razonable
  si más adelante importa control multi-región.
- **VPS genérico**: descartado para este MVP de un solo operador por la
  carga operativa (SO, TLS, systemd, actualizaciones de seguridad) sin
  necesidad demostrada (Ponytail).

## Consecuencias

- Positivas: cero cambio en `domain/`, `processing/`,
  `application/run_pipeline.py`; el hallazgo de que `pip install .`
  funciona sin `PYTHONPATH` es una mejora de higiene de deployment
  independiente de Railway en sí (aplicaría igual a cualquier otro
  proveedor); `railway.toml` es autocontenido y versionado, reproducible.
- Negativas: dependencia nueva de configuración (`railway.toml`), un
  archivo más que mantener sincronizado si el comando de arranque
  cambia.
- Reversibilidad: alta — `railway.toml` es solo configuración de
  deployment; cambiar de proveedor más adelante no afecta ningún
  código de aplicación.

## Relacionado

ADR-001 (interfaces como clientes delgados, respetado — Railway no
introduce ninguna regla de negocio), ADR-016 (FastAPI), ADR-017
(Supabase, extra `postgres` preinstalado para cuando se cablee),
`docs/architecture/API_CONTRACT.md` §8.4 (por qué no Vercel Functions),
`docs/PROJECT_STATUS.md` §Sesión 2026-08-17 (bloques 5, 7, 8).
