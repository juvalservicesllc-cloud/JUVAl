# frontend-next — recorrido del propietario y gates de cutover

Fecha: 2026-11-03. Baseline inspeccionado: `165b37e`, C1 `198aa70`.
Preparación del recorrido: **IMPLEMENTED**. Aceptación del propietario y
validación externa de este diff: **PENDING**. Cutover: **NO AUTORIZADO / NO
EJECUTADO**. La paridad con `frontend/` tiene brechas abiertas; no se certifica
«sin pérdida de funcionalidades». B1–B4/C1–C3 aceptados no equivalen a paridad
completa ni a preparación de producción.

## Evidencia y alcance

- **EXTERNA HISTÓRICA:** PROJECT_STATUS en `165b37e` registra 30/30 Playwright,
  217 unit tests, 10 skips condicionales, typecheck/lint/build y 12 capturas C1
  revisadas. Esa evidencia precede a las correcciones de esta fase.
- **SOURCE:** comparación de las pantallas actuales de `frontend/` con
  `frontend-next/`, el baseline de capacidades y los contratos de paridad.
  Es evidencia de presencia/ausencia de controles, no de comportamiento visual
  observado en un navegador en esta fase.
- **UNIT actual:** los fallos de landmark y color-scheme se reprodujeron con
  pruebas focalizadas antes de corregirlos. También se reprodujo la ausencia
  del enlace de descarga completa. Resultados y logs actuales: nueva entrada
  de [PROJECT_STATUS](../PROJECT_STATUS.md).
- **EXTERNA PENDIENTE:** `e2e/z-visual-acceptance.spec.ts`, ocho escenarios
  nuevos. No ejecutados aquí. El conector de navegador requiere aprobación y
  la política de esta sesión no permite solicitarla; el EPERM de Playwright
  ya está documentado. No se investigó de nuevo ni se cambió el sandbox.
- **HUMANA PENDIENTE:** las casillas siguientes están abiertas deliberadamente.
  Un test verde o una captura existente no constituyen firma del propietario.

Este documento es una revisión limitada de paridad/UX de frontend para preparar
aceptación; no es la auditoría integral del día ni una revisión de seguridad de
producción. No hay cambios de ADR, backend, infraestructura o dependencias.

## Preparación segura de la sesión

- [ ] Operador identifica commit/tree exactos, navegador/versión, SO, fecha,
  viewport, zoom 100 %, origen del candidato y directorio privado de evidencia.
- [ ] Usar el lab E2E existente: API/SQLite desechables, loopback, configuración
  aislada. `auth=disabled` es exclusivo del lab; no demuestra login/MFA/CSRF
  en un despliegue real. No usar bases compartidas o reales para crear fixtures.
- [ ] Abrir un perfil/contexto nuevo para la primera pasada. Después probar
  un perfil con preferencias; registrar las diferencias sin borrar preferencias
  reales del propietario.
- [ ] Generar datos con `frontend-next/e2e/fixtures.py`: `no-demand.xlsx`
  (3 registros, REVIEW/REVIEW/PASS), `demand-valid.xlsx` (declaración sintética
  de demanda, sigue REVIEW), suggested-price/severity para estados adicionales.
  Para BUY, reutilizar solo `seed-buy` sobre el SQLite desechable: snapshot
  sintético INFERRED, nunca resultado de una subida ni verificación de mercado.
- [ ] Configuración de procesamiento del lab: la de `e2e/support.ts` /
  `configureUpload`. Es configuración explícita para fixtures, no defaults
  comerciales recomendados ni una política aprobada para compras.
- [ ] Tener imágenes PNG/JPEG/WebP propias o sintéticas de apariencia, claras,
  oscuras y checker; no imágenes de producto. No cargar secretos en capturas.
- [ ] Guardar evidencia fuera de APP, copiarla a una ubicación durable elegida
  por el operador antes de limpiar `/tmp`; registrar hashes de artefactos. No
  publicar capturas/datasets ni enviar nada a terceros desde esta tarea.

## Recorrido del propietario

Repetir con Light/Dark a 1440 × 900 y 390 × 900. Comprobar también 360 × 900
y 768 × 900, en particular navegación, tablas y textos largos. El C1 previo
añade 390 × 844 y las combinaciones de acento/fondo. Registrar OK/defecto y
nombre de captura por fila; no marcar una capacidad ausente como aprobada.

| ID | Pantalla y acceso actual | Acciones y comprobaciones | Resultado humano |
|---|---|---|---|
| V1 | Dashboard `/` | Seleccionar el run del lab; confirmar filename, conteos y cobertura VERIFIED de promedios. Revisar distribución, HazMat/Bulky separados, provenance, brands, issue types, spread y demanda pendiente. Abrir Catalog manteniendo run. Comparar controles ausentes de G1 | [ ] |
| V2 | Upload: botón **Import**, `/import` | XLSX y CSV son producción. Cola de 2 archivos, quitar/añadir, preview por archivo sin crear run, configuración vacía sin defaults inventados. Procesar, ver estados indeterminados honestos, batch/child runs; comprobar 10/overflow 11 con los B1 existentes | [ ] |
| V3 | Catalog `/catalog?run=…` | Verificar run, buscar, decision/riesgo, 30% → request `min_roi=0.3`, confidence y resultados. Sort asc/desc, 25/50/100, scroll horizontal solo dentro de tabla. Columnas hide/reorder/reset, Title siempre visible; preferencias no cambian query/export. Contrastar G2/G3 | [ ] |
| V4 | Runs `/runs` → Open → `/runs/:id` | Filename/ID/status/fechas/conteos y razones de PARTIAL_SUCCESS sin ceros inventados. Abrir Catalog del run. Descargar **Download complete run (.xlsx)**: todos los registros, sin filtros; distinguir del export filtrado. Ordenación/batch/preview pendientes según G4/G5 | [ ] |
| V5 | Product Detail, enlace Title → `/run/:id/product/:ref` | Decision/reasons arriba; REVIEW por DEMAND_UNKNOWN, BUY solo seeded. Identity/source, economía con estados, fees/COG planos conforme API, riesgo presence/severity, missing/invalid/raw, evidencia histórica explícita. Datos declarados no cambian decisión; volver con Back en la misma pestaña | [ ] |
| V6 | Appearance `/appearance` | Light/Dark, acento normal/blanco/negro, imagen clara/oscura/checker. Título/LIVE/texto/foco/acciones legibles, imagen visible. Logo/background/acento persisten tras reload; límite 512 KiB y rechazo SVG; storage no disponible no rompe app. Reset solo appearance. Revisar brecha G6 | [ ] |
| V7 | Methodology `/about` | Flujo real, PASS antes de REVIEW, demanda declarada solo informativa, estados y DEMO distintos, score experimental, Amazon/Keepa no conectados, IA no implementada. Mismo tema/contraste y navegación | [ ] |
| V8 | Batch `/batch/:id`, Favorites `/favorites`, Compare `/compare` | Batch conserva cada archivo y enlace; favoritos son locales y run-scoped. Compare declara bloqueo, no simula comparaciones. No convertir placeholders/limitaciones en capacidades aceptadas por observar la ruta | [ ] |

Pasos transversales:

- [ ] Tab/Shift+Tab recorren controles con nombre y foco visible. Probar
  explícitamente el selector de archivos **con teclado**; el source mantiene
  `.drop-zone input { display:none }` (G10). Un test de subida con setInputFiles
  no prueba acceso por teclado. No cerrar esta casilla desde jsdom.
- [ ] Cada ruta conserva shell; 404/empty/loading/error/retry son honestos,
  nunca fixtures insertados como fallback. Sign-in en 401 sin redirección en bucle.
- [ ] Back/Forward y enlaces internos permanecen en la misma pestaña. Descargar
  no reemplaza el documento; export filtrado conserva su comportamiento existente.
- [ ] Persistir filtros en la pestaña, cambiar pantalla y volver; no restaurar
  run ni offset desde preferencias. Separar filtros de columnas/appearance.
- [ ] Probar historias legacy sin inventar provenance/valores. VERIFIED leído
  del supplier file no significa verificado por Amazon/Keepa.

## Navegación sticky móvil: prueba en viewport

La observación anterior de una barra superpuesta en una captura full-page
**no basta para declarar un defecto**: Playwright puede dibujar sticky en el
punto donde terminó el scroll/foco. Tampoco basta para declarar que está bien.

- [ ] A 360/390 px, con y sin logo/fondo, verificar `aside` sticky en `top:0`
  tras scroll real. Barra de una fila, fondo opaco, sin desbordamiento de body.
- [ ] Deslizar horizontalmente la barra: los ocho destinos permanecen
  alcanzables; que aparezcan ocho es diferencia de IA frente al legacy (G7).
- [ ] Tab hacia un control fuera de viewport y volver: su punto de interacción
  y su foco quedan visibles, sin quedar tapados por la barra. Revisar select
  Theme, búsqueda y botones al principio/final del contenido.
- [ ] Capturar **viewport con scroll**, posición/foco/bounding boxes y scrollY,
  además de full-page. Solo corregir sticky si estos pasos reproducen un fallo.
  No cambiar `position:sticky` para acomodar una captura de documento completo.
- [ ] A 768 px se mantiene el layout desktop actual (breakpoint 760); verificar
  que el propietario lo acepta, sin asumir que tablet implica barra horizontal.

## Diferencias concretas y gates abiertos

Los enlaces son evidencia SOURCE de este tree. «Gate» significa que no se
puede certificar la paridad/cutover; no autoriza una implementación de mayor
alcance ni una excepción a un ADR aceptado.

| ID | Evidencia anterior → candidato | Impacto / disposición |
|---|---|---|
| G1 | [Dashboard legacy](../../frontend/src/pages/DashboardPage.tsx): `decisionChartType`, Donut/Bars, RECENT RUNS; [candidato](../../frontend-next/src/pages/DashboardPage.tsx): Bars fijas, issue/provenance/spread en tablas, sin Recent Runs | Datos agregados siguen; controles/representaciones protegidos no están completos. **Gate de paridad**, restaurar con trabajo separado; no sustituir la evidencia con «hay Dashboard» |
| G2 | [Catalog legacy](../../frontend/src/pages/ProductsPage.tsx): columnas identity/record/SKU/issues y sort SKU/ASIN/ref; [candidato](../../frontend-next/src/catalogColumns.ts): sin esos ids ni sus controles de sort; Product Detail aún muestra datos/issues | Inspección en la tabla se perdió; datos del backend no desaparecieron. **Gate de paridad**, no borrado autorizado de la capacidad |
| G3 | [Catalog legacy](../../frontend/src/pages/ProductsPage.tsx): Provenance field/status; [candidato](../../frontend-next/src/pages/CatalogPage.tsx): selector Amazon cambia solo campo asin | Client/query soporta más campos, pero UI no permite escoger price/profit/ROI/margin. Además «Amazon» puede sugerir conexión inexistente. **Gate de paridad y claridad**, revisión funcional pendiente |
| G4 | [Runs legacy](../../frontend/src/pages/RunsPage.tsx): tabla con `sortRuns` y botones de ordenación; [candidato](../../frontend-next/src/pages/RunsPage.tsx): cards newest-first sin sort | Metadatos conservados; ordenación interactiva ausente. **Gate de paridad** |
| G5 | [Run Detail legacy](../../frontend/src/pages/RunDetailPage.tsx): download, BatchSummary, primera página ResultsTable; [candidato](../../frontend-next/src/pages/RunDetailPage.tsx): summary/decisions y handoff Catalog | **Descarga restaurada en esta fase** usando GET `/runs/{id}/download`. Batch context/preview siguen ausentes aquí aunque Batch y Catalog existen como pantallas separadas. Gate restante; no confundir acceso indirecto con paridad |
| G6 | [Appearance legacy](../../frontend/src/pages/AppearancePage.tsx): 8 tokens, fit/position/overlay; [candidato](../../frontend-next/src/pages/AppearancePage.tsx): accent/logo/background, cover/center y protección opaca | C1 cumple su alcance aprobado, pero no todos los controles legacy. Assets 400 KiB → 512 KiB (C1 aprobado). **Gate de paridad de personalización**, no ampliar sin trabajo explícito |
| G7 | [Shell legacy](../../frontend/src/components/AppLayout.tsx): 4 destinos principales, settings contextual, sidebar colapsable; [candidato](../../frontend-next/src/app/App.tsx): 8 botones, sin collapse, LIVE también en settings/docs | Diferencia visual/IA confirmada en source; propietario revisa jerarquía. No reescribir ADR-024/030 ni asumir nueva IA comercial aprobada |
| G8 | [Vite legacy](../../frontend/vite.config.ts): VitePWA manifest + SW; [candidato](../../frontend-next/vite.config.ts), [index](../../frontend-next/index.html): React sin manifest/registro SW | **Gate PWA**. Build web válido no demuestra instalación/actualización/offline shell. No añadir dependencias ni implementar cache durante esta fase; respetar ADR-014 |
| G9 | [Router legacy](../../frontend/src/App.tsx) → [router candidato](../../frontend-next/src/app/App.tsx) | `/upload`→`/import`, `/products`→`/catalog`, `/batches/:id`→`/batch/:id`, `/runs/:id/records/:ref`→`/run/:id/product/:ref`. No aliases en candidato: favoritos/bookmarks externos y deep links antiguos requieren plan aprobado, no cambios de hosting aquí |
| G10 | [CSS candidato](../../frontend-next/src/style.css), `.drop-zone input` oculto; tests usan carga programática | Teclado del file picker requiere reproducción externa. **Gate de accesibilidad** pendiente, no se afirmó reproducción visual ni se modificó el picker sin ella |
| G11 | [Theme storage legacy](../../frontend/src/theme/storage.ts), [columns legacy](../../frontend/src/pages/ProductsPage.tsx), [query legacy](../../frontend/src/catalogQuery.ts) → [appearance](../../frontend-next/src/appearance.ts), [columns](../../frontend-next/src/catalogColumns.ts), [query](../../frontend-next/src/catalogQuery.ts) | Esquemas/claves diferentes, ver tabla siguiente. **Gate de compatibilidad de preferencias**, no migración implícita ni borrado de datos |
| G12 | [Product Detail legacy](../../frontend/src/pages/ProductDetailPage.tsx): serie DEMO_FIXTURE con Line/Bar; candidato la omite explícitamente | Diferencia real, ya bloqueada/documentada por ADR-030/handoff. No copiar una serie a producción ni inventar proveedor. Presentación ilustrativa pendiente de decisión; mercado real bloqueado por fuente |

Correcciones pequeñas de esta fase: landmark `Main navigation` válido dentro
de aside (flex-direction/gap heredados conservan filas/columnas), color-scheme
nativo derivado del tema activo y descarga completa en Run Detail. Reproducción
por unit antes/después; la apariencia final y descarga real requieren la
ejecución externa nueva. No se restauraron automáticamente las brechas G1–G12.

| Preferencia | frontend anterior | frontend-next | Antes de cutover |
|---|---|---|---|
| Appearance | `juval-theme-settings-v1`, objeto ThemeSettings | `juval.appearance.*`, claves por campo | Elegir estrategia explícita, preservar/respaldar original; no convertir formatos aquí |
| Columnas | `juval.catalog.columns.v4`, ids legacy | `juval.catalog.columns.v1`, objetos id/visible | Reconciliar ids/orden y columnas nuevas; no reutilizar JSON como si fuera compatible |
| Filtros de pestaña | `juval.catalog.query.v1` | `juval.next.catalog.query.v1` | No prometer continuidad silenciosa de filtros |
| Favoritos locales | `juval.catalog.favorites.v1` | misma clave run-scoped | Validar formato y origen real; mismo nombre no migra datos entre orígenes distintos |
| Sidebar | `juval-sidebar-collapsed` | no control equivalente | Conservar registro de la diferencia G7 |

No se encontró evidencia de desaparición de datos del servidor: estas son
brechas de representación/acceso/UX verificadas en source. Tampoco se certifica
que no existan otros gaps: el gate no se cierra por inventario o conteos de tests.

## Ejecución externa y artefactos

Claude Code/operador reutiliza el comando aislado de
[e2e/README](../../frontend-next/e2e/README.md) con LOG privado fuera de APP,
TMPDIR **corto**, Python auditado, browser local ya instalado y
`JUVAL_E2E_OUTPUT`. No usar `npm install` ni descargar navegadores.

1. Ejecutar `npm run e2e -- e2e/z-visual-acceptance.spec.ts` (8 escenarios).
   El `beforeAll` usa el upload real existente de un XLSX sintético sobre el
   SQLite desechable. No stubs de analytics ni inyección de datos de negocio.
2. Ejecutar la suite retenida junto a la nueva con log real del servidor
   (`JUVAL_E2E_SERVER_LOG`, `DEBUG=pw:webserver`). **38 escenarios previstos**,
   no un resultado medido aquí. El nombre `z-` conserva primero el caso vacío D7.
3. Revisar `report.json`, consola/HTTP, artifacts y los 12 C1 existentes.
   Ocho combinaciones nuevas generan 64 capturas de las 7 pantallas + Run
   Detail, 4 capturas viewport de sticky móvil, 8 XLSX y 8 attachments JSON
   con executionId/mediciones. Patrones: `{screen}-{width}-{theme}.png`,
   `navigation-scrolled-{width}-{theme}.png`, `complete-run.xlsx`.
4. Las aserciones cubren same-tab/document, landmarks, tema nativo, heading
   único, botones con nombre, body sin overflow, dirección del nav, foco Theme
   no tapado, sticky real y destinos accesibles por scroll horizontal. No son
   un test completo de WCAG, no validan los controles ausentes ni reemplazan
   recorrido manual/aceptación del propietario.
5. Documentar captura/viewport/scroll/pasos exactos para cada defecto, aplicar
   únicamente remediaciones frontend autorizadas y volver a ejecutar checks
   afectados. No ocultar fallos de la matriz ni bajar assertions para aprobar.

## Resultado de la ejecución externa (2026-11-03, Claude Code)

Ejecutado fuera del sandbox de Codex: API/SQLite desechables en loopback,
Chromium headless (snap), `TMPDIR` corto privado, sin red externa.

| Ejecución | Resultado |
|---|---|
| `npm run e2e -- e2e/z-visual-acceptance.spec.ts` | **2 passed / 6 failed** (49 s). Pasan 1440 light/dark. Fallan 360, 390 (Dashboard) y 768 (Run Detail) en `pageOverflow <= 0` |
| Suite retenida (`--grep-invert "owner walkthrough"`) con `JUVAL_E2E_SERVER_LOG` | **30 passed / 0 failed**, 0 `LocalProtocolError` |
| Suite completa de 38 | **No ejecutada como aceptación**: los ocho nuevos no pasan |

Capturas: **30 generadas / 64 + 4 previstas**. 24 de pantalla (las 8 de
1440 × 2 temas; Dashboard/Upload/Catalog/Runs a 768 × 2) y 6 de fallo. Cada
escenario se detiene en su primer overflow, así que no se generaron las de
360/390 ni las 4 `navigation-scrolled-*`: **la prueba sticky móvil en viewport
sigue sin ejecutarse**. Se descargó `complete-run.xlsx` real en 1440 × 2.

Medición directa del overflow de cada pantalla (spec diagnóstico fuera de
APP, mismo lab), elemento más externo que excede el viewport:

| ID | Defecto | Pantallas / ancho | Overflow | Criticidad |
|---|---|---|---|---|
| D1 | `<select>` Run crece hasta su opción más larga (`no-demand.xlsx — fecha`) dentro de su `label` | Dashboard y Catalog a 360 / 390 | +65 / +35 px | **Alta** (bloquea móvil; el selector queda cortado) |
| D2 | `Input hash` (SHA-256 de 64 caracteres) en `<small>` sin corte de línea | Run Detail a 360 / 390 / 768 | +216 / +186 / +68 px | **Alta** (rompe layout a 768 y móvil) |
| D3 | Botones `Open in Catalog` / `All runs` sin separación | Run Detail, todos los anchos | — | Baja, preexistente |
| D4 | `main{margin:auto}` centra verticalmente páginas cortas; el header baja respecto de otras pantallas | Run Detail 1440 | — | Baja, preexistente |

Sin overflow a 360/390/768: Upload, Runs, Appearance, Methodology, Product
Detail. A 768: Dashboard y Catalog correctos. Revisión visual 1440 light/dark:
las 8 pantallas legibles, landmark y `color-scheme` correctos, provenance
coherente ("3 of 3 records, verified only"), enlace de descarga completa
visible y funcional. D1/D2 no los introduce esta fase (existen en `165b37e`).

**Reejecución tras D1/D2 (2026-11-03):** `z-visual-acceptance` **4/8**
(768 y 1440 pasan); retenida 30/30, 0 `LocalProtocolError`; 64 capturas de
pantalla generadas y revisadas. D1 y D2 **corregidos** (hash íntegro de 64
caracteres). 360/390 fallan solo en la comprobación sticky: **D5**, margen
por defecto de `body` (8 px, sin `margin:0`), `aside` en y=8 al inicio;
preexistente y visible como marco claro en todas las capturas. D3 sigue
abierto. Faltan las 4 `navigation-scrolled-*`.

**Reejecución tras D5 (2026-11-03):** `z-visual-acceptance` **6/8**; retenida
30/30, 0 `LocalProtocolError`. **D5 corregido**: `aside` móvil en y=0 al inicio
y tras scroll; sin marco de 8 px. 64 capturas de pantalla y las 4
`navigation-scrolled-*` generadas y revisadas. Fallo restante solo a 360 px:
aserción exacta `box.x >= 0` frente a `-0.203125` (redondeo subpíxel de la
barra con scroll horizontal; texto visible). Corrección pendiente en la spec.

### Matriz de paridad con evidencia

| Área | Estado | Criticidad para cutover | Evidencia |
|---|---|---|---|
| Dashboard | **PARCIAL** | Alta | D1 y D5 corregidos; G1 (Donut/Bars, Recent Runs) ausente |
| Catalog | **PARCIAL** | Alta | D1 corregido; G2/G3 (identity/issues, provenance general). B2/C2 verificados |
| Runs | **PARCIAL** | Media | Sin overflow; G4 (ordenación) ausente |
| Run Detail | **PARCIAL** | Media | D2 corregido; D3 abierto; descarga completa verificada; G5 (batch/preview) ausente |
| Appearance | **PARCIAL** | Media | C1 verificado (12 capturas previas, contraste); G6 controles legacy ausentes |
| PWA | **AUSENTE** | Alta | G8: sin manifest ni service worker en `frontend-next/` |
| Compatibilidad | **NO CERTIFICADA** | Alta | G9 rutas sin alias; G11 claves de preferencias distintas; G10 teclado del file picker sin reproducir |

## Gates de aprobación y eventual cutover

- [x] D1 y D2 corregidos (verificado 2026-11-03).
- [x] D5 corregido (verificado 2026-11-03).
- [ ] Tolerancia subpíxel en la spec; `z-visual-acceptance` 8/8 y suite completa 38/38
  fuera del sandbox; capturas 360/390 y `navigation-scrolled-*` revisadas.
- [ ] Propietario firma V1–V8 y móvil, con commit/tree y referencias de evidencia.
- [ ] Resolver brechas de capacidades protegidas G1–G8 y G10; si se propone
  cambiar el alcance, presentar propuesta explícita. Una casilla marcada no
  deroga ADR-030: exige paridad completa **y** aprobación del usuario.
- [ ] Plan de rutas, preferencias/orígenes y ciclo de vida SW/caches (G8/G9/G11)
  revisado con responsables; conservar el frontend anterior y rollback probado
  fuera de esta tarea. No copiar/renombrar árboles ni tocar hosting aquí.
- [ ] Gates de identidad/seguridad y despliegue revisados por sus responsables
  en [IDENTITY_SECURITY_READINESS](../IDENTITY_SECURITY_READINESS.md). Lab sin
  auth y tests live condicionales omitidos no demuestran readiness de producción.
- [ ] Registrar digest del build, configuración aprobada, alcance de entrega,
  compatibilidad BFF y navegación directa, plan de validación y rollback. Esto
  es un requisito de futuro, no autorización para ejecutar operaciones ahora.
- [ ] Aprobación **separada y explícita** del propietario para ejecutar cutover.

**Firma visual:** propietario ____; fecha ____; commit/tree ____;
evidencias ____; observaciones/gaps abiertos ____; resultado ____.

**Decisión de cutover:** PENDING. No push, deploy, migraciones ni cambios de
servicios realizados. Incluso con aceptación visual positiva, los gates de
paridad/PWA/compatibilidad/seguridad anteriores siguen vigentes.
