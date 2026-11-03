# frontend-next — Plan de PWA, cutover y rollback

**Estado: PLAN. Cutover NO AUTORIZADO y NO EJECUTADO.** Este documento no
autoriza push, deploy ni cambios de hosting. Cada paso marcado como
*autorización* necesita una instrucción explícita del propietario en el momento
de ejecutarlo.

- Código evaluado: `523aa47` (G1–G12 + estabilización de pruebas).
- Decisión vigente: ADR-030 §8–9 (cutover solo tras aprobación y paridad; sin
  reemplazo destructivo). Topología: ADR-038 (app/api/id same-site).
- Aceptación humana: [FRONTEND_NEXT_OWNER_ACCEPTANCE](FRONTEND_NEXT_OWNER_ACCEPTANCE.md).
- G12: [ADR-054](../adr/ADR-054-demo-presentation-charts-adr-030-amendment.md), Propuesta.

## 1. Qué es el cutover

Sustituir, en el origen público de la app, el build de `frontend/` por el de
`frontend-next/`. Es un cambio **solo de frontend estático**: mismo backend,
misma API, misma base de datos, sin migraciones. `frontend/` y `demo/` no se
borran (ADR-030 §9); el build anterior queda disponible para rollback.

Estrategia recomendada: **mismo origen**. Conserva `localStorage` (preferencias
de apariencia/columnas, importables de forma explícita con G11) y deja que el
navegador sustituya el service worker anterior de forma ordenada (§3). Un origen
nuevo pierde esa continuidad (G11 no migra entre orígenes) y deja el worker
antiguo vivo en el origen viejo.

## 2. Precondiciones (todas obligatorias)

| # | Precondición | Estado al 2026-11-03 | Responsable |
|---|---|---|---|
| C1 | Aceptación visual firmada (owner acceptance §5) | **PENDIENTE** | Propietario |
| C2 | Decisión sobre ADR-054: aceptar, o retirar G12 antes del cutover | **PENDIENTE** | Propietario |
| C3 | Origen de producción confirmado (dominio, proyecto de hosting, TLS) | **BLOQUEADO**: dominio concreto y TLS pendientes (CLAUDE.md §14, ADR-038). No verificado por agentes | Propietario |
| C4 | Configuración de hosting para `frontend-next/` equivalente a `frontend/vercel.json` (reescritura SPA) más `Cache-Control: no-cache` para `/sw.js`, `/` y rutas HTML, y `application/manifest+json` para el manifest | **FALTA**: `frontend-next/` no tiene `vercel.json` | Codex, con aprobación |
| C5 | `VITE_API_BASE_URL` del build apunta al origen API de producción; el bundle no contiene `localhost:8000` | Pendiente de build | Operador |
| C6 | Autenticación: modo de auth de producción y flujo BFF (login, `/auth/session`, CSRF, 401 sin redirección automática) probados en navegador con `frontend-next/` | **PENDIENTE**: cliente BFF implementado; E2E solo con `JUVAL_AUTH_MODE=disabled`. Identidad sigue PARTIAL (`IDENTITY_SECURITY_READINESS.md`) | Propietario / identidad |
| C7 | CORS del backend incluye exactamente el origen de la app (sin comodines, ADR-038) | Sin cambio si el origen se mantiene | Operador |
| C8 | 42/42 E2E y suite unitaria sobre el commit exacto a desplegar | PASS en `38f88ac` (E2E) y `523aa47` (unit). Repetir si cambia el commit | Claude Code |
| C9 | Prueba PWA del propietario en build de producción (owner acceptance §4) | **PENDIENTE** | Propietario |
| C10 | Autorización de push del commit a desplegar | **NO CONCEDIDA** | Propietario |
| C11 | Rollback ensayado en preview o laboratorio (§6) | Lab PASS (§3); ensayo en hosting pendiente | Operador |

Si alguna precondición no está en verde, no hay cutover.

## 3. PWA: instalación, actualización y convivencia

### Diseño actual (`frontend-next/public/sw.js`, `src/pwa.ts`)

- Registro solo en build de producción, `scope: /`, `updateViaCache: "none"`.
- Instalación: precachea **solo** `/offline.html` (sin credenciales) en
  `juval-next-offline-v1`; si no se puede descargar, la instalación falla.
- `fetch`: solo navegaciones GET de rutas del frontend en el mismo origen; red
  primero y, sin red, el aviso offline. Nunca escribe respuestas en caché. La
  API (otro origen, ADR-038) no pasa por el worker.
- Sin `skipWaiting`: una versión nueva espera a que se cierren las pestañas.
- `activate`: borra solo cachés propias antiguas (`juval-next-offline-*`).

### Worker anterior (`frontend/`, vite-plugin-pwa `autoUpdate`)

`/sw.js` de Workbox con `skipWaiting` + `clientsClaim`, precache de todo el build
(17 entradas en el lab) en `workbox-precache-v2-<scope>` y respuesta a **toda**
navegación con su `index.html` precacheado. Usa la misma URL `/sw.js`, por lo
que en el mismo origen el navegador trata el nuevo worker como actualización
del registro existente.

### Evidencia de laboratorio (2026-11-03)

Builds de producción de ambos frontends servidos alternativamente en el mismo
origen loopback, Chromium 156 headless (Xvfb para instalación), perfiles
desechables. Scripts y resultados fuera del repo.

| # | Escenario | Resultado |
|---|---|---|
| A1 | Usuario con el frontend anterior | Worker anterior activo; precache Workbox 17 entradas |
| A2 | Se despliega frontend-next; la pestaña abierta recarga | **Sigue viendo la app anterior** (index precacheado); el nuevo worker queda en espera |
| A3 | Segunda pestaña en `/catalog` | App anterior |
| A4 | Se cierran todas las pestañas y se abre una nueva | **frontend-next** activo y controlando |
| A5 | Sin red, `/catalog` | Aviso «JUVAl is offline», sin datos |
| A6 | Variante propuesta de limpieza | Borra solo `workbox-precache-v2-<scope>` del origen; una caché ajena de prueba y la propia se conservan |
| A7 | **Rollback** al frontend anterior | Primera visita: app anterior y su worker toman el control inmediatamente (`skipWaiting`) |
| A8 | Volver a desplegar frontend-next tras el rollback | Mismo comportamiento que A2/A4 |
| B | Actualización cuyo `offline.html` falta | La instalación falla; el worker previo sigue activo y la app funciona |
| C | Desactivación de emergencia (worker que se desregistra) | Sin worker ni cachés propias tras recargar; la app sigue online |
| I | Instalación real (CDP `PWA.install`, Chromium 156 con Xvfb) | Instala, abre ventana de app y desinstala sin errores; HOME temporal, sin accesos directos en el perfil real |
| — | En todos los escenarios | 0 respuestas `/api/` en CacheStorage |

Evidencia previa sobre el build (sin convivencia): manifest sin errores de
instalabilidad, iconos 192/512/SVG, solo `/offline.html` en caché tras 8 GET de
API, versión nueva en espera con la pestaña abierta.

### Consecuencias y recomendaciones

1. **Transición diferida, no instantánea.** Tras el cutover, cada usuario sigue
   en la app anterior hasta cerrar **todas** sus pestañas de JUVAl. Es seguro
   (misma API), pero hay que comunicarlo: «cierre todas las pestañas de JUVAl y
   vuelva a abrir». No se recomienda forzar `skipWaiting` en la primera versión:
   recargaría pestañas con trabajo en curso.
2. **Caché antigua.** El precache de Workbox queda en el navegador (solo
   recursos estáticos de la app anterior, sin datos de API). Opción propuesta,
   **PENDIENTE de aprobación**: añadir al `activate` de frontend-next el borrado
   exacto de `workbox-precache-v2-` + scope (variante A6). Cambio de código para
   Codex; no aplicado.
3. **Rollback del frontend es rápido** porque el worker anterior hace
   `skipWaiting`. La caché `juval-next-offline-v1` (1 entrada) queda inofensiva.
4. **Desactivación de emergencia:** un `sw.js` que se desregistra y borra
   `juval-next-offline-*` funciona, pero mientras el bundle siga llamando a
   `registerPwa()` el navegador lo reinstala en cada carga. Preparar, **antes**
   del cutover y con aprobación, un artefacto de emergencia que además omita el
   registro. PENDIENTE.
5. **Instalación en dispositivos reales** (Android/escritorio) la verifica el
   propietario (owner acceptance §4); el lab prueba el mecanismo en Chromium, no
   cada plataforma.
6. **API autenticada:** el worker no intercepta peticiones a la API ni guarda
   respuestas. Con auth activa, revisar en C6 que ninguna respuesta autenticada
   aparezca en CacheStorage ni en la caché HTTP por cabeceras de la API.

### Procedimiento de verificación PWA en el hosting (preview)

1. Desplegar el build en una URL de preview (no producción). *Autorización.*
2. Comprobar `/sw.js` con `Cache-Control: no-cache`, manifest 200 con su tipo,
   iconos 200, una ruta profunda (`/runs/x`) devuelve el `index.html`.
3. En Chromium: Application → Manifest sin errores; instalar; Service Workers
   activo tras recargar; Cache Storage solo `juval-next-offline-v1`.
4. Offline: ruta del frontend muestra el aviso; nunca datos.
5. Nota: ADR-038 prohíbe CORS con comodín para orígenes de preview. Una preview
   solo puede hablar con la API si su origen exacto se autoriza de forma
   temporal; si no, limitar la preview a las comprobaciones estáticas y PWA.

## 4. Procedimiento de cutover (para cuando exista autorización)

**T-1 (preparación, sin efecto en producción)**

1. Fijar el commit a desplegar; repetir C8 sobre él; registrar commit y tree.
2. Registrar el identificador del despliegue de producción actual y el commit de
   `frontend/` que sirve (punto de rollback). Conservar su artefacto de build.
3. Build de `frontend-next/` con `VITE_API_BASE_URL` de producción; guardar
   digest SHA-256 de `dist/`; comprobar que no contiene `localhost:8000`.
4. Preview (§3) y ensayo de rollback en preview. *Autorización.*
5. Avisar a los usuarios de la ventana y del cierre de pestañas.

**T0 (ventana)** — *autorización explícita del propietario para este paso.*

1. Confirmar que no hay procesamiento de lotes en curso (Runs) que se quiera
   observar durante la ventana.
2. Promover el build de `frontend-next/` al origen de producción.
3. Health checks (§5). Si alguno falla: abortar y ejecutar rollback (§6).
4. Ventana de observación de 30 min con el propietario revisando P1–P8 en
   producción en modo **solo lectura** (sin subir archivos salvo un archivo de
   prueba aprobado explícitamente).

**T+1**

1. Registrar resultado, digest, commit y hora en `PROJECT_STATUS.md`.
2. Decidir la limpieza de cachés antiguas (§3.2) y la retirada del artefacto de
   emergencia. `frontend/` no se borra.

## 5. Health checks

| Comprobación | Esperado |
|---|---|
| `GET /` y una ruta profunda | 200, `index.html` de frontend-next (`id="root"`, sin `registerSW.js`) |
| `GET /sw.js` | 200, `Cache-Control: no-cache`, contenido = commit desplegado |
| `GET /manifest.webmanifest`, `/icon-192.png`, `/icon-512.png`, `/offline.html` | 200 con tipos correctos |
| Bundle | Origen API correcto; sin `localhost:8000` |
| Dashboard con sesión válida | Lista de runs carga; sin errores de consola; CORS correcto |
| Sin sesión | Mensaje «Sign in», sin redirección automática ni bucles |
| Mutación (solo si se autoriza una subida de prueba) | Cabecera CSRF enviada; respuesta 2xx |
| CacheStorage | Solo `juval-next-offline-v1` (+ el precache anterior hasta su limpieza) |
| API | Sin cambios de backend; logs sin aumento de 4xx/5xx respecto a la línea base |

## 6. Rollback

- **Disparadores:** cualquier criterio de §7 o decisión del propietario.
- **Acción:** volver a promover el despliegue anterior registrado en T-1 (el
  hosting permite promover un despliegue previo; confirmar el procedimiento
  exacto del proveedor antes de la ventana). Sin cambios de base de datos que
  revertir.
- **Efecto en navegadores:** el worker anterior toma el control en la primera
  visita (lab A7). Pestañas de frontend-next abiertas siguen funcionando contra
  la misma API hasta recargarse.
- **Verificación:** health checks de §5 con los valores de la app anterior
  (`registerSW.js` presente) y P1/P3 en modo lectura.
- **Objetivo:** decisión de rollback en ≤ 15 min desde el primer fallo.

## 7. Criterios de abortar

- Cualquier health check de §5 falla.
- Errores de autenticación, CSRF o CORS en flujos que funcionaban antes.
- Una decisión, cifra económica o estado de provenance difiere entre la API y lo
  mostrado.
- Respuestas de API en CacheStorage o datos visibles sin red.
- Regresión visual bloqueante reportada por el propietario.
- Cualquier necesidad de tocar backend, base de datos o infraestructura de
  identidad durante la ventana: se aborta y se trata como cambio separado.

## 8. Backup

El cutover no modifica datos. Se conserva: despliegue anterior (identificador),
commit y artefacto de `frontend/`, commit y digest del build nuevo. Las
preferencias del navegador no se borran (G11 nunca elimina originales). Si
algún paso requiriera tocar datos, no forma parte de este runbook.

## 9. Autorización necesaria

Ejecutar este plan requiere, por escrito y por separado:

1. Firma de aceptación visual (C1) y decisión sobre ADR-054 (C2).
2. Aprobación de los cambios pendientes de código/configuración: C4, y si se
   desea, §3.2 (limpieza) y §3.4 (artefacto de emergencia).
3. Autorización de push del commit concreto (C10).
4. Autorización de preview en hosting (§3).
5. Autorización del cutover de producción con fecha/ventana (§4 T0).

## 10. Matriz de riesgos y bloqueos

| Riesgo / bloqueo | Prob. | Impacto | Mitigación | Estado |
|---|---|---|---|---|
| Origen/dominio/TLS sin definir | — | Bloquea | Decisión de topología ADR-038 | BLOQUEADO |
| Auth real no probada con frontend-next | Media | Alto | C6 antes del cutover | PENDIENTE |
| Falta config de hosting (`vercel.json`) | Alta | Alto (rutas profundas 404, `sw.js` cacheado) | C4 | PENDIENTE |
| Usuarios ven la app anterior tras el cutover | Alta | Bajo | Comunicar cierre de pestañas (§3.1) | Aceptado si se comunica |
| Precache Workbox antiguo ocupa almacenamiento | Alta | Bajo | Limpieza A6 | Decisión PENDIENTE |
| Worker defectuoso en producción | Baja | Medio | Instalación falla segura (B); rollback A7; artefacto de emergencia | Artefacto PENDIENTE |
| Build con API por defecto `localhost:8000` | Media | Alto | Comprobación de bundle (C5) | Control definido |
| G12 contradice ADR-030 si ADR-054 no se acepta | — | Medio (documental) | Aceptar ADR-054 o retirar G12 | PENDIENTE |
| Preferencias no migradas automáticamente | Media | Bajo | Importación explícita G11 en Appearance | Diseño aceptado |
| Concurrencia de importación entre pestañas | Baja | Bajo | Aviso en UI; originales intactos | Documentado |
| Prueba unitaria sensible a carga (3 s) | Baja | Bajo | Falla visible, sin reintentos | Aceptado |
| Instalación en móviles reales no verificada | Media | Bajo | Owner acceptance §4 | PENDIENTE |
