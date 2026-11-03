# Recuperación G1–G12 — 2026-11-03

Baseline: `9eb461a`, master limpio. Alcance APPROVED por instrucción explícita
del propietario: frontend/PWA, sin backend, dependencias, push, deploy o cutover.
Los resultados 38/38 y 8/8 pertenecen al baseline; no certifican este diff.
Referencia de brechas: [aceptación visual](FRONTEND_NEXT_VISUAL_ACCEPTANCE.md).

## Matriz previa a implementación

| Gate | Estado inicial | Evidencia y contrato / trabajo autorizado |
|---|---|---|
| G1 | PARCIAL | `frontend/src/pages/DashboardPage.tsx` Donut/Bars y Recent Runs; candidato solo Bars. `GET /runs`, `/analytics` existentes; recuperar presentación sin recalcular decisiones |
| G2 | PARCIAL | `frontend/src/pages/ProductsPage.tsx` record/SKU/identity/issues; `frontend-next/src/catalogColumns.ts` no los incluye. `RecordOut` y sorts record_ref/sku/asin existentes |
| G3 | PARCIAL | Legacy expone provenance field/status; candidato limita a ASIN bajo “Amazon”. Query/export ya soportan asin/selling_price/profit/roi/margin y los cuatro estados |
| G4 | PARCIAL | Legacy `sortRuns`; candidato cards sin ordenación. Ordenar solo los hasta 100 metadatos cargados; no nueva consulta ni clasificación comercial |
| G5 | PARCIAL | Legacy batch + primera página. `getRunBatch` y `getRunRecords` existen. Consultas independientes con error/retry y preview acotado |
| G6 | PARCIAL | Legacy ThemeSettings tiene ocho colores, fit/position/overlay; candidato accent/logo/background. Recuperar preferencias validadas en la configuración actual, conservar protección opaca de C1 |
| G7 | PARCIAL | Legacy sidebar colapsable y activo en detalles; candidato ocho destinos y sin collapse. Preservar destinos/landmark, recuperar collapse desktop y contexto; móvil mantiene barra sticky |
| G8 | PENDIENTE | Legacy VitePWA; candidato sin manifest/SW. ADR-014 acepta PWA. Implementación sin dependencias: manifest/iconos, SW limitado a fallback público offline; sin cache de datos/API/auth ni actualización forzada |
| G9 | PENDIENTE | Legacy /upload, /products, /batches/:id, /runs/:id/records/:ref tienen correspondencias exactas. Aliases cliente, mismos IDs y query; sin hosting |
| G10 | PARCIAL | Input dentro de label con display:none no recibe Tab. Recuperar input nativo enfocable y foco visible; no cambiar cola/upload |
| G11 | PENDIENTE | Claves/esquemas legacy descritos en aceptación. Migración explícita por grupo, solo si destino ausente; originales intactos, validación y previsualización; sin migración entre orígenes ni datos comerciales |
| G12 | BLOQUEADO → autorización específica | ADR-030 prohíbe fixtures en candidato. Instrucción actual autoriza recuperar serie DEMO 90 días/Line/Bar: excepción APPROVED de presentación aislada, etiquetada DEMO_FIXTURE / NOT VERIFIED; jamás ligada a precio real ni inputs de decisión |

No se modifican ADR aprobados. La excepción G12 deriva de la instrucción del
propietario de esta sesión, no de una reinterpretación silenciosa del ADR-030.
Compare, fuentes de mercado reales, imágenes/URLs de proveedor, scoring comercial
y thresholds históricos siguen fuera de alcance cuando falten contratos/ADR.

## Evidencia de validación y revisión

**Estado global: PARTIALLY IMPLEMENTED.** Implementación local terminada;
aceptación de navegador/PWA/propietario pendiente. IMPLEMENTED significa código
y tests locales; VERIFIED requiere ejecución externa sobre el tree resultante.
Ningún gate se declara cerrado con los 38/38 históricos del baseline.

| Gate | Estado de implementación | Evidencia local actual / pendiente externo |
|---|---|---|
| G1 | IMPLEMENTED | Dashboard: Donut/Bars con conteos textuales, barras de provenance/issues/spread y tablas conservadas; seis Recent Runs, enlaces misma pestaña. `DashboardPage.test.tsx`: 15 PASS |
| G2 | IMPLEMENTED | SKU, ASIN/UPC con estado, record_ref e issues desplegables; sorts server-side. Columnas nuevas respetan preferencias guardadas. Incluido en Catalog (22), columns (9), query (11): 42 PASS; disposición histórica seguida por las cuatro columnas nuevas visibles |
| G3 | IMPLEMENTED | Field/status generales, cinco campos, cuatro estados; sin claims de Amazon integrado. Query y export idénticos, offset reseteado; reset probado en los cinco campos |
| G4 | IMPLEMENTED | Nueve claves metadata, controles accesibles de campo/dirección, números y fechas con offsets temporales; alcance hasta 100 runs explícito. `RunsFlow`: 19 PASS |
| G5 | IMPLEMENTED | Carga explícita batch/primera página 25 registros; links run-scoped, estados independientes/error/retry, sin ocultar resumen ni tocar descarga completa. `RunContext`: 2 PASS |
| G6 | IMPLEMENTED | Ocho colores HEX/nativos, fit/position/overlay, persistencia/reset/preview. Tokens protectores por superficie para texto/semántica/foco; preferencias elegidas conservadas. appearance (14) + page (4) + cascade (8): 26 PASS; especificidad localizada independiente del orden de las hojas |
| G7 | IMPLEMENTED | Collapse desktop persistido al elegirlo, ocho destinos preservados, activos en Run/Batch/Product Detail; Settings/docs sin badge LIVE engañoso. App: 9 PASS. Jerarquía visual no rediseñada; firma del propietario pendiente |
| G8 | IMPLEMENTED, aceptación PWA PENDING | Manifest + SVG y PNG 192/512 reproducibles; registro solo build producción. SW cachea únicamente aviso offline público, fetch sin credentials, sin cache de API/auth/runtime ni takeover. Worker real en VM (2) + registro (1): 3 PASS. Instalación/update/offline real pendientes |
| G9 | IMPLEMENTED | Cuatro aliases inequívocos; IDs codificados/query/hash preservados, replaceState sin entrada extra, navegación posterior canónica. routes: 7 PASS. Hosting/deep links de producción quedan para la validación externa, sin modificar infraestructura |
| G10 | IMPLEMENTED, navegador PENDING | Input nativo visible/enfocable y foco de región, cola/procesamiento intactos. UploadKeyboard: 1 PASS. Tab y diálogo nativo deben verificarse en Chromium, no se certifican desde jsdom |
| G11 | IMPLEMENTED | Importación manual por grupo en Appearance; preview sin writes, relectura en acción, destino ausente, originals intactos y rollback de writes propios ante quota. Sin run/brand/offset/records/credenciales ni cross-origin. 3 PASS; probar perfil sintético externo con otras pestañas cerradas |
| G12 | IMPLEMENTED por autorización explícita | Componente sin props de record/precio, 90 días sintéticos fijos, Line/Bar y tabla accesible, DEMO_FIXTURE / NOT VERIFIED / no datos Amazon/Keepa. ProductDetail (18) + MarketDemo (1): 19 PASS; no altera las dos peticiones del detalle ni economía/export |

**Mediciones de la recuperación inicial, anteriores al ajuste G2/G4/G6**
(Node 24.19.0, entorno aislado, sin installs):

- Suite unitaria: **249 PASS / 10 SKIP / 0 FAIL**, 29 archivos PASS, 2 SKIP;
  80.75 s. Los 9 skips de live contract necesitan `JUVAL_LIVE_API` desechable;
  1 necesita `JUVAL_FINANCIAL_JSON`. No equivalen a pruebas aprobadas.
- Typecheck y lint: PASS; lint 0 warnings / 0 errors.
- Revisión focalizada posterior: **51 PASS** en 8 archivos, 0 FAIL (14.25 s),
  después de los ajustes de foco/custom colors y textos; sin repetir auditorías.
- Comprobaciones finales de contratos: Catalog **22 PASS** (incluye aviso de
  provenance incompleta); migración **3 PASS** (incluye preset legacy custom
  sin appearanceMode normalizado igual que el frontend anterior).
- Appearance **4 PASS** después de comprobar reset de borradores HEX inválidos
  y su descripción accesible; el reset también remonta esos borradores locales.
- Build: PASS, salida y logs privados en `/tmp/juval-parity-rHncKG/`.
- Sintaxis del nuevo E2E vía TypeScript: PASS; `node --check public/sw.js`: PASS.
- Manifest/PNG 192×192 y 512×512/SW/offline/registro en bundle: comprobados.
- Los once specs retenidos (38 casos), `package.json`, lockfile, `frontend/`,
  `demo/`, backend y AGENTS sin modificaciones, comprobado con Git.
- Playwright NO ejecutado aquí. Se conserva la limitación conocida del sandbox;
  no se diagnostica de nuevo ni se solicita relajar AppArmor.
- La revisión CSS con jsdom confirma margin/picker, pero no resuelve los colores
  `var(--text)` a RGB. Ese intento no es evidencia de contraste de navegador.
  Las comprobaciones de tokens/contraste unitarias pasan y el CSS real requiere
  los escenarios externos. Sin claims de geometría o responsive desde jsdom.

**Self-review acotado:** cálculos/decisiones/provenance de servidor intactos;
charts son presentación de agregados, spread indica magnitud y conserva signo;
ninguna fuente ni endpoint inventado. Consultas bounded, sin N+1 por producto,
sin registros en storage. Imágenes mantienen PNG/JPEG/WebP/512 KiB y validación
de firma; no SVG/URLs externas. Sin dependencias nuevas ni archivos de datos demo
alterados. Picker nativo/labels/aria-pressed/navegación conservados; tablas con
scroll local y SVG fluidos, sin ocultar overflow de página. Revisar extremos de
color y foco en navegador. Ponytail no disponible en tools/skills; revisión
manual de simplicidad, sin auditoría integral.

**Riesgos restantes:** aceptación de la paridad en Chromium aún pendiente; migración de preferencias no
es una transacción multi-tab (cerrar otras pestañas; originales nunca se borran);
storage que impida también rollback puede dejar preferencias parciales válidas.
No se ofrece migración entre orígenes. Un worker legacy en un origen compartido
requiere plan de cutover independiente; el worker nuevo no borra sus caches.
No se autoriza ni ejecuta ese cutover.

## Validación externa Chromium — 2026-11-03 (Claude Code)

Ejecutada fuera del sandbox de Codex con el lab del README (API/SQLite
desechables, loopback, Chromium snap, TMPDIR corto, salida y log de servidor
separados por invocación). Tree validado: `bf10d43` (código idéntico al de
`56db50a`).

**Primera pasada (tree anterior a las correcciones): no aceptada.** 38 retenidos
29/2 fail/7 sin ejecutar; 4 nuevos 0/4; 42 completos 29/6/7. Causas: G2
desplazaba columnas históricas (g17, severity-provenance), localizadores
`getByLabel` exactos en el spec nuevo, y `.dark` sobrescribía colores
personalizados (G6). Codex corrigió las tres; no se debilitó ningún spec retenido.

**Pasada definitiva:**

| Ejecución | Resultado |
|---|---|
| 38 retenidos (`--grep-invert 'parity gates:'`) | **38 PASS**, 0 skip, 2.6 min |
| 4 nuevos (`zz-parity-gates.spec.ts`) | **4 PASS** (360/1440 × claro/oscuro) |
| Suite completa | **42 PASS**, 0 skip, 0 flaky, 2.9 min; 109 capturas |

`LocalProtocolError`: 0 en los tres logs reales de servidor. Los specs fallan
ante cualquier error de consola o HTTP ≥ 400 no declarado.

**Comprobaciones dirigidas (spec de diagnóstico fuera del repo, 4 PASS):**

- G2: 15 columnas históricas en sus posiciones y SKU, ASIN/UPC, Record, Issues
  al final; un orden/visibilidad guardado prevalece tras recargar.
- G4: con dos runs (3 y 1 registros) `records_total` ordena asc/desc
  correctamente; los dos combobox tienen nombre y orden de tabulación.
- G6: texto `#eeeeee` aplicado al h1 en oscuro y claro (`getComputedStyle`),
  tinta protectora negra sobre superficie blanca, persistencia tras recarga y
  reset a los valores por defecto (sin `has-custom-colors`). C1: con imagen de
  fondo, `main` conserva fondo opaco.

**PWA (build de producción con `vite preview`, API desechable):** manifest sin
errores de instalabilidad de Chromium; iconos 192/512/SVG 200; SW con scope `/`
controla tras recargar; CacheStorage solo `juval-next-offline-v1` →
`/offline.html` tras 8 GET de API (200); offline, rutas frontend muestran el
aviso y la API da error de red; una versión nueva queda en espera con la pestaña
abierta (sin `skipWaiting`). **Límites no aprobados:** instalación real
(headless) y convivencia con workers del frontend anterior en un origen
compartido (pertenece al plan de cutover).

**Migración G11 (perfil sintético, primera pasada):** 14 claves importadas,
originales intactos, columnas actuales no sobrescritas, filtros sin
offset/run/brand, segundo intento bloqueado, segunda pestaña ve los valores al
recargar. No probados en navegador: almacenamiento bloqueado/corrupto ni
concurrencia real entre pestañas (no transaccional, documentado).

**G12:** etiqueta DEMO_FIXTURE · NOT VERIFIED y 90 barras en navegador;
`MarketDemo` no recibe props. Las comparaciones export/descarga/API de los specs
retenidos pasan. La excepción a ADR-030 consta en esta documentación por
instrucción del propietario; el ADR no se modificó y su formalización queda
PENDING del propietario.

**Pruebas unitarias:** 259 PASS / 1 FAIL / 10 SKIP en tres ejecuciones
completas. El fallo es `CatalogBrandFilter.test.tsx` («offers only the brand
labels…»): `findByRole` espera 1 s y el render del Catalog tarda ~1,2 s con la
suite en paralelo. Aislado pasa (8/8). Ya fallaba en el baseline `9eb461a`
(1 de 2 ejecuciones, 220/1/10), así que es inestabilidad previa, no una
regresión; la nueva carga del Catalog la hace más frecuente. Typecheck y lint
PASS en cada commit intermedio.

**Commits locales (sin push):** `e84028c` G2/G3, `083ff54` G1, `c3966b9`
G4/G5, `b2140e1` G6/G11, `4dc9c59` G7/G9/G10, `364ef07` G8, `56db50a` G12,
`fe33140` E2E, `bf10d43` documentación. La sección «Unidades propuestas» de
abajo queda como histórico.

Pendiente: estabilizar `CatalogBrandFilter`, firma del propietario, instalación PWA real, plan de workers previos
y cutover (no autorizado).

## Unidades propuestas para commits locales

Sin stage/commit desde el sandbox protegido. Tras validación externa, el operador
puede dividir mediante selección de hunks compartidos de App/style (sin rebase):

1. G1 Dashboard, gráficos, tests y sus reglas CSS.
2. G2/G3 Catalog/columns y pruebas de query/export.
3. G4/G5 Runs/Run Detail/RunContext y pruebas.
4. G6/G11 Appearance, validación/migración y tests (UI/configuración compartida).
5. G7 shell, G9 routes y G10 picker, por hunks y sus pruebas independientes.
6. G8 manifest/assets/generador/SW/registro/tests.
7. G12 MarketDemo, integración y pruebas; conservar autorización en docs.
8. Escenarios E2E/checklist/documentación actualizada.

Cada unidad debe compilar/pasar sus pruebas sobre las anteriores. No son commits
ya creados; App y CSS requieren selección explícita de los hunks por dependencia.

## Checklist del propietario / ejecución externa

- [ ] Reejecutar los 38 E2E existentes sin debilitarlos, con entorno del README.
- [ ] Revisar 360/390/768/1440, claro/oscuro, con/sin imágenes de apariencia.
- [ ] Probar Donut/Bars y Recent Runs; mismos conteos del API, misma pestaña.
- [ ] Identidad/issues/sorts/provenance/columnas; export conserva query filtrada.
- [ ] Runs ordenación, Run Detail batch/preview y estados parciales de error.
- [ ] Nuevos colores/fit/position/overlay, contraste y reset/persistencia.
- [ ] Shell activo/colapsado, teclado del picker, rutas antiguas y Back/Forward.
- [ ] PWA en build de producción: instalación, actualización, offline honesto;
      inspeccionar CacheStorage: ninguna respuesta API/autenticada ni dataset.
- [ ] Migración en perfil sintético: destino ausente/presente, corrupto/storage
      bloqueado; no borrar preferencias reales ni prometer continuidad cross-origin.
- [ ] Serie DEMO separada de los precios reales, 90 puntos, Line/Bar, sin claims
      Amazon/Keepa; no cambios en decisiones, cálculos o exportaciones.
- [ ] Registrar commit/tree y artefactos, firma humana. Cutover requiere otra
      autorización explícita y permanece NO EJECUTADO.

## Archivos creados/modificados en esta intervención

Inventario del working tree (sin stage ni commit):

- [docs/PROJECT_STATUS.md](../../docs/PROJECT_STATUS.md)
- [docs/architecture/FRONTEND_NEXT_MIGRATION.md](../../docs/architecture/FRONTEND_NEXT_MIGRATION.md)
- [docs/architecture/FRONTEND_NEXT_VISUAL_ACCEPTANCE.md](../../docs/architecture/FRONTEND_NEXT_VISUAL_ACCEPTANCE.md)
- [frontend-next/README.md](../../frontend-next/README.md)
- [frontend-next/e2e/README.md](../../frontend-next/e2e/README.md)
- [frontend-next/index.html](../../frontend-next/index.html)
- [frontend-next/src/app/App.test.tsx](../../frontend-next/src/app/App.test.tsx)
- [frontend-next/src/app/App.tsx](../../frontend-next/src/app/App.tsx)
- [frontend-next/src/appearance.test.ts](../../frontend-next/src/appearance.test.ts)
- [frontend-next/src/appearance.ts](../../frontend-next/src/appearance.ts)
- [frontend-next/src/catalogColumns.test.ts](../../frontend-next/src/catalogColumns.test.ts)
- [frontend-next/src/catalogColumns.ts](../../frontend-next/src/catalogColumns.ts)
- [frontend-next/src/main.tsx](../../frontend-next/src/main.tsx)
- [frontend-next/src/pages/AppearancePage.test.tsx](../../frontend-next/src/pages/AppearancePage.test.tsx)
- [frontend-next/src/pages/AppearancePage.tsx](../../frontend-next/src/pages/AppearancePage.tsx)
- [frontend-next/src/pages/CatalogPage.test.tsx](../../frontend-next/src/pages/CatalogPage.test.tsx)
- [frontend-next/src/pages/CatalogPage.tsx](../../frontend-next/src/pages/CatalogPage.tsx)
- [frontend-next/src/pages/DashboardPage.test.tsx](../../frontend-next/src/pages/DashboardPage.test.tsx)
- [frontend-next/src/pages/DashboardPage.tsx](../../frontend-next/src/pages/DashboardPage.tsx)
- [frontend-next/src/pages/MethodologyPage.tsx](../../frontend-next/src/pages/MethodologyPage.tsx)
- [frontend-next/src/pages/ProductDetailPage.test.tsx](../../frontend-next/src/pages/ProductDetailPage.test.tsx)
- [frontend-next/src/pages/ProductDetailPage.tsx](../../frontend-next/src/pages/ProductDetailPage.tsx)
- [frontend-next/src/pages/RunDetailPage.tsx](../../frontend-next/src/pages/RunDetailPage.tsx)
- [frontend-next/src/pages/RunsFlow.test.tsx](../../frontend-next/src/pages/RunsFlow.test.tsx)
- [frontend-next/src/pages/RunsPage.tsx](../../frontend-next/src/pages/RunsPage.tsx)
- [frontend-next/src/pages/appearance.css](../../frontend-next/src/pages/appearance.css)
- [frontend-next/src/pages/appearanceCascade.test.js](../../frontend-next/src/pages/appearanceCascade.test.js)
- [frontend-next/src/style.css](../../frontend-next/src/style.css)
- [docs/architecture/FRONTEND_NEXT_PARITY_RECOVERY.md](../../docs/architecture/FRONTEND_NEXT_PARITY_RECOVERY.md)
- [frontend-next/e2e/zz-parity-gates.spec.ts](../../frontend-next/e2e/zz-parity-gates.spec.ts)
- [frontend-next/public/icon-192.png](../../frontend-next/public/icon-192.png)
- [frontend-next/public/icon-512.png](../../frontend-next/public/icon-512.png)
- [frontend-next/public/manifest.webmanifest](../../frontend-next/public/manifest.webmanifest)
- [frontend-next/public/offline.html](../../frontend-next/public/offline.html)
- [frontend-next/public/sw.js](../../frontend-next/public/sw.js)
- [frontend-next/src/legacyPreferences.test.ts](../../frontend-next/src/legacyPreferences.test.ts)
- [frontend-next/src/legacyPreferences.ts](../../frontend-next/src/legacyPreferences.ts)
- [frontend-next/src/pages/LegacyPreferences.tsx](../../frontend-next/src/pages/LegacyPreferences.tsx)
- [frontend-next/src/pages/MarketDemo.test.tsx](../../frontend-next/src/pages/MarketDemo.test.tsx)
- [frontend-next/src/pages/MarketDemo.tsx](../../frontend-next/src/pages/MarketDemo.tsx)
- [frontend-next/src/pages/RunContext.test.tsx](../../frontend-next/src/pages/RunContext.test.tsx)
- [frontend-next/src/pages/RunContext.tsx](../../frontend-next/src/pages/RunContext.tsx)
- [frontend-next/src/pages/UploadKeyboard.test.tsx](../../frontend-next/src/pages/UploadKeyboard.test.tsx)
- [frontend-next/src/pwa.test.ts](../../frontend-next/src/pwa.test.ts)
- [frontend-next/src/pwa.ts](../../frontend-next/src/pwa.ts)
- [frontend-next/src/pwaWorker.test.js](../../frontend-next/src/pwaWorker.test.js)
- [frontend-next/src/routes.test.ts](../../frontend-next/src/routes.test.ts)
- [frontend-next/src/routes.ts](../../frontend-next/src/routes.ts)
- [frontend-next/tools/generate-pwa-icons.py](../../frontend-next/tools/generate-pwa-icons.py)


## Corrección quirúrgica G2/G4/G6 — 2026-11-03

Al recibir esta intervención había 47 archivos pendientes, sin commit. Claude
Code informó 29 PASS / 2 FAIL / 7 no ejecutados en los 38 retenidos; 0 PASS /
4 FAIL en los cuatro nuevos; 29 PASS / 6 FAIL / 7 no ejecutados en los 42,
con 0 LocalProtocolError. Es evidencia externa del tree anterior a este ajuste,
no del resultado actual. Alcance APPROVED por instrucción explícita del usuario.

- **G2:** las cuatro columnas nuevas intercaladas después de Title desplazaban
  los índices históricos. Se mantienen las 15 anteriores en su orden y se añaden
  SKU, ASIN/UPC, Record e Issues al final, todas visibles por defecto. No se
  oculta capacidad ni se fuerza una migración: las preferencias guardadas
  conservan orden/visibilidad, incluso cuando incluyen columnas nuevas en otro
  lugar. Clave, tipos, carga y guardado sin cambios. Tres tests nuevos cubren
  inicio, preferencias antiguas y configuración explícita de las columnas nuevas;
  la lectura no escribe ni sustituye la copia persistida.
- **G4:** solo el spec nuevo usa ahora `getByRole("combobox", { name, exact:
  true })` para Sort runs, Background fit y Background position. Se corrige
  también Run sort direction, contiguo y afectado por el mismo label anidado.
  Los cuatro nombres accesibles y la unicidad del control se comprueban en los
  tests de Runs/Appearance. Todas las aserciones E2E permanecen intactas.
- **G6:** `.has-custom-colors` empataba con `.dark`; al cargarse después la hoja
  base ganaba el tema oscuro. Se acotan cinco selectores a
  `.app.has-custom-colors`, superando la especificidad de `.dark` y del estilo
  base del estado del header, sin `!important`. No se cambian tokens, contraste,
  superficies opacas C1, persistencia, reset ni reglas responsive. Ocho tests
  nuevos cargan las hojas reales y comprueban claro/oscuro, paleta predeterminada
  y personalizada, ambos órdenes de carga y lectura del color persistido. jsdom
  verifica la declaración ganadora; RGB/contraste final requieren Chromium.

Validaciones locales del ajuste (Node 24.19.0, sin instalaciones):

- Focalizadas: **62 PASS / 0 FAIL**, cinco archivos, 25.36 s.
- Suite completa: **260 PASS / 10 SKIP / 0 FAIL**, 30 archivos PASS y dos SKIP,
  80.66 s. Nueve requieren `JUVAL_LIVE_API` desechable y uno
  `JUVAL_FINANCIAL_JSON`; no se cuentan como aprobados.
- Typecheck, lint (0 warnings / 0 errors), build y `git diff --check`: PASS.
- Sintaxis TypeScript del spec nuevo: PASS. Comparación con su copia inicial:
  exactamente cuatro sustituciones de localizador, ninguna aserción modificada.
- Logs y build privados: `/tmp/juval-g246-sHc1sc/`. El primer intento de la
  prueba CSS falló al leer una URL HTTP de jsdom mediante node:fs; se corrigió
  la ruta del test y se repitieron las focalizadas y la suite completa con éxito.

El inventario anterior se amplía con `frontend-next/src/catalogColumns.test.ts`
(archivo existente que estaba limpio) y
`frontend-next/src/pages/appearanceCascade.test.js` (nuevo). Los otros cambios
incrementales son catalogColumns.ts, pages/appearance.css, los tests
AppearancePage/RunsFlow, el spec zz-parity-gates y este documento: ocho archivos
respecto al contenido inicial, 49 paths totales pendientes. Comparación SHA-256
contra la copia privada inicial: los demás archivos permanecen idénticos. Los
once specs retenidos son idénticos también a HEAD. style.css, App.tsx, ADR-030,
backend, dependencias y datos demo no se modifican en este ajuste.

Ponytail no disponible en herramientas/skills; revisión manual acotada de
simplicidad, accesibilidad, preferencias, cascade, provenance y regresiones.
Sin commits, stage, push, deploy o cutover. Los doce gates conservan su
implementación; aceptación externa sigue PENDING. Claude Code debe repetir
**38 → 4 → 42** con el entorno aislado, TMPDIR corto y salidas privadas separadas
indicados en `frontend-next/e2e/README.md`, y revisar claro/oscuro, persistencia,
reset y las capturas. No se afirma ningún PASS Chromium para este diff.
