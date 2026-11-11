# Integración frontend-next / BFF — 2026-11-10 UTC

Estado global: **PARTIALLY IMPLEMENTED** hasta verificar navegador y backend
real fuera del sandbox. Implementación frontend terminada; aceptación integral
**BLOCKED**. HEAD de partida y de cierre: `bb9ed35`. Sin commits, push o deploy.

## Alcance y decisiones

- **APPROVED**: instrucción explícita del usuario para trabajar en
  `frontend-next/`, contrato SEC-01E/F y ADR-034/038. Esta instrucción autoriza
  la excepción a la congelación general de frontend indicada en AGENTS.md.
- Se leyeron completos `CODEX_BFF_INTEGRATION_PROMPT.md`,
  `BFF_FRONTEND_CONTRACT.md`, `LOCAL_INTEGRATION_ENVIRONMENT.md` y ADR-038.
  Se contrastaron las rutas de sesión/logout y la validación de `return_to`
  con el código del BFF, sin modificarlo.
- Solo se editaron archivos dentro de `frontend-next/`. Backend,
  infraestructura, migraciones, otros frontends y documentación exterior no
  fueron modificados por este trabajo. No se añadieron dependencias.
- Producción, dominio real, TLS, migraciones live y activación pública siguen
  **PENDING** y fuera del alcance autorizado.

## Comportamiento implementado

- Login mediante navegación superior al BFF con `return_to` codificado por
  `URLSearchParams`: pathname, query y fragmento actuales. Se descartan URLs
  absolutas, rutas relativas, `//host`, backslashes y controles.
- `getSession()` expone authenticated, subject, roles, permissions y
  expires_at. Comparte una única consulta en memoria con CSRF; no expone CSRF
  al shell. Los fallos de servicio/red no quedan cacheados como sesión cerrada.
- Consulta de sesión al cargar y después del retorno de login (documento
  nuevo), ante CSRF desactualizado o por reintento manual de un error de
  sesión. Sin temporizadores, sondeo, keep-alive o caducidad decidida en JS.
- Falta de CSRF en una sesión autenticada: otra lectura de `/session`.
  Rechazo CSRF de una mutación: nueva lectura y un único reintento.
- `Sign out` solo aparece cuando la sesión dice authenticated=true. Envía
  POST con CSRF y cookies, resetea la memoria tras éxito y navega a
  `end_session_url` o `/`. Evita clics duplicados durante el logout. Un fallo
  conserva la cuenta salvo que el servidor responda 401.
- 401 borra la sesión en memoria y ofrece login sin navegación automática.
  Una respuesta de inicio tardía no restaura el control de logout tras 401.
- 403 por organización ausente explica que hay que contactar al administrador
  y no muestra controles de reintento. Permisos y CSRF mantienen mensajes
  distintos. 503 conserva la sesión y muestra indisponibilidad temporal.
  Otros errores 5xx muestran un mensaje genérico, como exige el contrato.
  Se mantiene el tratamiento de 404 sin sugerir la existencia de recursos ajenos.
- Se reutilizaron header, botones y notice existentes. Sin CSS, layout, tema,
  componentes de diseño o fórmulas comerciales nuevos.

## Archivos de este trabajo

- `src/api/client.ts`: login, sesión compartida, logout y clasificación de errores.
- `src/app/App.tsx`: estado de cuenta, retorno, logout y errores recuperables.
- `src/pages/{BatchPage,CatalogPage,DashboardPage,FavoritesPage,ProductDetailPage,RunContext,RunDetailPage,RunsPage,UploadPage}.tsx`:
  no ofrecer reintento ante organización ausente; consultas, formularios y
  cálculos existentes conservados.
- `src/api/client.test.ts`, nuevo `src/app/Auth.test.tsx`,
  `src/pages/RunContext.test.tsx`, `src/pages/UploadPage.test.tsx`: cobertura
  de autenticación y errores, incluida ausencia de sondeo durante ocho horas.
- `src/pages/{AppearancePage,MethodologyPage}.test.tsx`: fixtures estrictos
  que permiten solo la lectura de sesión del shell y conservan la cobertura
  de preferencias/imágenes locales. `src/pages/RunsFlow.test.tsx`: mensaje
  genérico de error 500 conforme al contrato.
- `README.md` y este informe: comportamiento y comandos reproducibles.

Durante la ejecución aparecieron dos archivos ajenos, conservados intactos:
`docs/adr/ADR-057-integration-lab-reverse-api-engineer.md` y
`docs/research/REVERSE_API_ENGINEER_EVALUATION_20261110.md`.

## Resultados medidos

| Verificación | Resultado | Evidencia / límite |
|---|---|---|
| Línea base Vitest, antes de editar | PASS | 260 passed, 10 skipped; 30 archivos pass, 2 omitidos |
| Vitest final | PASS | 314 passed, 10 skipped; 31 archivos pass, 2 omitidos; 54.05 s. Log local: `test-results/bff-vitest.log` |
| `npm run typecheck` | PASS | Sin errores |
| `npm run lint` | PASS | Sin avisos finales |
| `npm run build` | PASS | Build Vite generado localmente, sin publicación |
| `git diff --check` | PASS | Sin errores de whitespace |
| Escáner existente `scan_for_secrets`, limitado a frontend-next | PASS | Sin coincidencias; no certifica ausencia de todos los secretos posibles |
| Playwright existente, Chromium indicado por el usuario | BLOCKED | `spawnSync .venv/bin/python EPERM` al generar fixtures; ningún escenario ejecutado |
| `tools/integration_lab.py --check` | BLOCKED | No puede abrir loopback; diagnóstico independiente: crear socket falla con `PermissionError: [Errno 1] Operation not permitted` |
| Validación real en navegador, siete pasos SEC-01F | BLOCKED | Requiere levantar API/IdP/Vite fuera del sandbox |
| Ponytail FULL | BLOCKED | No hay herramienta ni skill Ponytail disponible; revisión manual de simplicidad realizada |

Los diez tests omitidos son anteriores a esta tarea: nueve en
`src/live.contract.test.tsx` requieren `JUVAL_LIVE_API` y un backend desechable;
uno en `src/financial.real.test.tsx` requiere `JUVAL_FINANCIAL_JSON` con una
respuesta real guardada de datos sintéticos. No se introdujeron skips ni se
contabilizan estas omisiones como PASS.

**FAIL encontrados y corregidos:** typecheck detectó tres opciones `exact`
inválidas en consultas por rol de los tests nuevos. La primera suite completa
detectó tres fallos en tests de Appearance/Methodology que asumían cero
consultas de cuenta; se corrigieron sus fixtures y aserciones para exigir
solo GET de sesión, sin permitir uploads o consultas comerciales. También se
eliminó un aviso de lint sobre controles en regex. No se eliminaron tests.

## Comandos exactos para Claude Code, fuera del sandbox

Ejecutar en este mismo checkout, sin instalar dependencias ni usar servicios
compartidos. Cada bloque usa un entorno limpio, conservando HOME y PATH del
operador. Los logs pueden incluir tokens/cookies sintéticos: mantenerlos
locales; no adjuntar trazas de autenticación a servicios externos.

### 1. Gates frontend y E2E comercial existente

```bash
cd /home/juval/JUVAl/APP/frontend-next
npm test
npm run typecheck
npm run lint
npm run build

JUVAL_BFF_CHECK_DIR=$(mktemp -d /tmp/jbff.XXXXXX)
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TMPDIR=/tmp \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/juval/JUVAl/APP/src \
  JUVAL_PYTHON=/home/juval/JUVAl/APP/.venv/bin/python \
  JUVAL_CHROME_BIN=/snap/chromium/current/usr/lib/chromium-browser/chrome \
  JUVAL_E2E_OUTPUT="$JUVAL_BFF_CHECK_DIR/e2e" \
  JUVAL_E2E_SERVER_LOG="$JUVAL_BFF_CHECK_DIR/server.log" \
  DEBUG=pw:webserver npm run e2e >"$JUVAL_BFF_CHECK_DIR/server.log" 2>&1
```

El último comando conserva su exit code. Revisar `server.log` y
`e2e/report.json` dentro de `$JUVAL_BFF_CHECK_DIR`. No reutilizar un backend
ya arrancado: el harness crea SQLite y fixtures sintéticos desechables y usa
solo puertos loopback 18771/18772. `TMPDIR=/tmp` evita sockets Unix demasiado
largos de Chromium. No cambiar el harness para ocultar fallos.

### 2. Smoke BFF real, PostgreSQL e IdP sintéticos

```bash
cd /home/juval/JUVAl/APP
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TMPDIR=/tmp \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/juval/JUVAl/APP/src \
  JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin \
  .venv/bin/python tools/integration_lab.py --check
```

El laboratorio construye su propio clúster y aplica migraciones solo a ese
clúster desechable; no ejecuta migraciones live ni cambia archivos de
migración. Su validación automática de backend no sustituye al navegador.

### 3. Navegador: dos terminales

Terminal 1:

```bash
cd /home/juval/JUVAl/APP
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TMPDIR=/tmp \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/juval/JUVAl/APP/src \
  JUVAL_POSTGRES_BIN=/usr/lib/postgresql/16/bin \
  .venv/bin/python tools/integration_lab.py
```

Terminal 2:

```bash
cd /home/juval/JUVAl/APP/frontend-next
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TMPDIR=/tmp \
  VITE_API_BASE_URL=http://localhost:18781 \
  npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

En Chromium, abrir `http://localhost:5173/runs?tab=history#recent`, usando
localhost en todo el flujo. Sin contraseñas ni identidades reales:

1. Sin sesión: aviso de 401 y `Sign in`, sin redirección automática.
2. Pulsar `Sign in`, elegir alice. Volver al origen de la app con ruta,
   query y fragmento; comprobar que aparece `Sign out`.
3. Ir a Import, elegir `tests/fixtures/sample_sourcing_TEST_DATA.xlsx`.
   Declarar explícitamente configuración sintética: Target profit=5,
   Target ROI=0.3, Minimum monthly sales=0, Maximum risk severity=CRITICAL,
   Referral fee=1, Referral fee rate=0.15, Allow unknown risk activado y
   Persist activado. Procesar. Comprobar en DevTools que el POST lleva
   `X-JUVAL-CSRF`, sin copiar su valor; abrir el run y guardar solo su URL.
4. Pulsar `Sign out`: POST correcto, navegación al end-session del IdP y
   regreso a la app. Recargar: no hay logout y los datos requieren login.
5. Entrar como bob: el run de alice no figura. Su URL directa produce
   «Run not found», igual que un id inexistente. Cerrar sesión.
6. Entrar como carol: mensaje de cuenta sin organización, sin Retry ni
   nuevo login automático. Conservar abierta la app para el último paso.
7. Cerrar sesión de carol y volver a entrar como alice. Ir a Runs, detener
   Terminal 1 con Ctrl-C (limpia el laboratorio) y recargar o provocar una
   nueva petición: error de red/servicio, nunca aviso de sesión expirada.
   Detener Vite al terminar. La base desaparece; no se espera conservar runs.

No exportar HAR, cookies, headers CSRF, códigos OAuth ni trazas completas de
login como evidencia pública. Registrar solo pasos, códigos, mensajes y
resultados; redactar cualquier valor sensible de capturas locales.

### 4. Los nueve tests Vitest opt-in del contrato comercial

En otra ejecución, con el laboratorio anterior detenido, Terminal 1:

```bash
cd /home/juval/JUVAl/APP
JUVAL_BFF_LIVE_DIR=$(mktemp -d /tmp/jbff-live.XXXXXX)
mkdir -p "$JUVAL_BFF_LIVE_DIR/runs"
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TMPDIR=/tmp \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/home/juval/JUVAl/APP/src \
  JUVAL_AUTH_MODE=disabled JUVAL_AUTH_DISABLED_CONFIRM=yes-loopback-lab-only \
  JUVAL_EXECUTION_STORE=sqlite \
  JUVAL_EXECUTION_DB_PATH="$JUVAL_BFF_LIVE_DIR/juval.db" \
  JUVAL_RUN_STORAGE_DIR="$JUVAL_BFF_LIVE_DIR/runs" \
  JUVAL_CORS_ORIGINS=http://127.0.0.1:5173 \
  .venv/bin/python -m uvicorn juval.interfaces.api.main:app \
    --host 127.0.0.1 --port 8765
```

Terminal 2:

```bash
cd /home/juval/JUVAl/APP/frontend-next
env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TMPDIR=/tmp \
  JUVAL_LIVE_API=http://127.0.0.1:8765 \
  VITE_API_BASE_URL=http://127.0.0.1:8765 \
  npx vitest run src/live.contract.test.tsx
```

Terminar uvicorn con Ctrl-C al finalizar. Solo usa SQLite sintético bajo el
directorio temporal generado. Este gate no verifica autenticación BFF.
El décimo test opt-in de evidencia financiera necesita además una respuesta
guardada real con documentos financieros sintéticos (`JUVAL_FINANCIAL_JSON`);
no se fabricó una respuesta vacía para forzar su ejecución o un PASS.

## Self-review y pendientes

- Correctitud: retorno seguro, logout CSRF y reintento acotado; errores de
  servicio distintos de sesión cerrada. Servidor siempre autoriza realmente.
- Trazabilidad/reproducibilidad: contrato explícito, pruebas deterministas,
  comandos de entorno sintético y bloqueos documentados. No se inventó
  evidencia de navegador ni se tomaron counts históricos como resultado actual.
- Arquitectura: solo cliente y UI; sin cálculos, persistencia o lógica de
  identidad trasladada al navegador. No se alteró el modelo comercial.
- Seguridad: cookies host-only manejadas por el navegador, credentials include,
  sin Authorization, lectura de cookies o persistencia de CSRF/OAuth.
  Escaneo de secretos existente sin coincidencias en el alcance.
- Simplicidad: reutiliza apiFetch/requestJson, una caché de sesión y estilos
  existentes. El único helper nuevo de errores evita reintentos que no pueden
  asignar organización. Sin servicios, abstracciones o dependencias nuevas.
- Tests/documentación: gates locales y README actualizados; validación real
  pendiente por EPERM. Ponytail no ejecutado; revisión manual efectuada.

No se observó una contradicción entre el código del backend leído y el
contrato. El comportamiento real de la integración no se pudo contrastar
desde este sandbox. La ausencia de regresiones en navegador y el flujo
completo BFF siguen **BLOCKED**, no certificados por mocks de Vitest.

Próximo paso: Claude Code ejecuta los bloques anteriores fuera del sandbox,
registra PASS/FAIL de E2E, smoke y los siete pasos y devuelve únicamente los
fallos o evidencia saneada. No hacer commit/push/deploy ni modificar backend
como parte de esa validación.
