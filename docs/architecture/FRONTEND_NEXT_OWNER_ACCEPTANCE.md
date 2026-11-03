# frontend-next — Aceptación del propietario (post G1–G12)

**Estado: PENDIENTE de revisión humana.** Ninguna casilla de este documento
está marcada por un agente. Solo el propietario marca casillas y firma.

- Código a revisar: `master` en `523aa47` o posterior (anotar el hash exacto).
- Evidencia automática previa (no sustituye esta revisión): 42/42 E2E Chromium,
  260 PASS / 10 SKIP unitarias, typecheck/lint/build PASS
  ([PARITY_RECOVERY](FRONTEND_NEXT_PARITY_RECOVERY.md), [PROJECT_STATUS](../PROJECT_STATUS.md)).
- Lista detallada por pantalla y defectos históricos (V1–V8, D1–D5):
  [FRONTEND_NEXT_VISUAL_ACCEPTANCE](FRONTEND_NEXT_VISUAL_ACCEPTANCE.md). Este
  documento es la pasada final y corta sobre el código con G1–G12.
- Fuera de alcance: la decisión sobre [ADR-054](../adr/ADR-054-demo-presentation-charts-adr-030-amendment.md)
  (G12) y la autorización de cutover ([runbook](FRONTEND_NEXT_CUTOVER_RUNBOOK.md)).

## 1. Abrir el frontend en local (datos sintéticos, sin servicios reales)

Comandos comprobados el 2026-11-03 desde `/home/juval/JUVAl/APP`, en dos
terminales. Todo escucha solo en `127.0.0.1`; la base es SQLite temporal y se
elimina la variable de Supabase.

```bash
# Terminal 1 — API desechable
export LAB=$(mktemp -d /tmp/juval-owner.XXXXXX); mkdir -p "$LAB/runs"
.venv/bin/python frontend-next/e2e/fixtures.py build "$LAB/files"   # 17 XLSX sintéticos
echo "$LAB"                                                         # anotar para la terminal 2 y la limpieza
env -u JUVAL_SUPABASE_DB_URL JUVAL_AUTH_MODE=disabled JUVAL_EXECUTION_STORE=sqlite \
  JUVAL_EXECUTION_DB_PATH="$LAB/juval.db" JUVAL_RUN_STORAGE_DIR="$LAB/runs" \
  JUVAL_CORS_ORIGINS=http://127.0.0.1:18772 \
  .venv/bin/python -m uvicorn juval.interfaces.api.main:app --host 127.0.0.1 --port 18771

# Terminal 2 — frontend-next
cd frontend-next
VITE_API_BASE_URL=http://127.0.0.1:18771 npx vite --host 127.0.0.1 --port 18772 --strictPort
```

Abrir `http://127.0.0.1:18772/` en Chromium/Chrome con un **perfil nuevo** (sin
preferencias previas). Al terminar: `Ctrl+C` en ambas terminales y
`rm -rf "$LAB"`. La API avisa de que `JUVAL_AUTH_MODE=disabled` deja todo sin
autenticar: es esperado y solo aceptable en loopback.

**Desde otro equipo (sin exponer servicios).** Los dos servidores escuchan
solo en `127.0.0.1` del servidor (`juval-server`). Desde el equipo del
propietario, abrir un túnel SSH con ambos puertos, porque el navegador llama a
la API directamente en `127.0.0.1:18771`:

```bash
ssh -N -L 18772:127.0.0.1:18772 -L 18771:127.0.0.1:18771 juval@juval-server
```

(usar la IP o el nombre por el que ese equipo llega al servidor). Con el túnel
abierto, navegar a `http://127.0.0.1:18772/` en el equipo propio. Usar
`127.0.0.1`, no `localhost`: CORS solo admite ese origen exacto. Si esos puertos
están ocupados en el equipo propio, cerrar lo que los use; cambiar el puerto
local rompería el origen permitido. No abrir puertos en el firewall ni usar
`--host 0.0.0.0`.

Para cargar datos: Import → elegir `no-demand.xlsx` (y después
`suggested-price.xlsx`, `severity-provenance.xlsx`, varios `batch-NN.xlsx`)
desde `$LAB/files`. Configuración usada por los E2E: Target profit 5, Target ROI
0, Minimum estimated monthly sales 0, Maximum accepted risk severity CRITICAL,
Referral fee 1, Referral fee rate 0.15, Allow unknown risk marcado. Son valores
de laboratorio, no thresholds comerciales.

La PWA (service worker, instalación, offline) **no** se activa en este modo de
desarrollo; se revisa aparte con el build de producción (§4).

## 2. Revisión por pantalla

Para cada pantalla: 1440 px y 360 px, claro y oscuro (interruptor Dark del
encabezado). Marcar solo lo comprobado personalmente.

| # | Pantalla (ruta) | Qué comprobar | OK |
|---|---|---|---|
| P1 | Dashboard (`/`) | Elegir run; KPIs coherentes con Runs; Donut/Bars con conteos en texto; provenance, issues y spread; Recent Runs abre el run en la misma pestaña | [ ] |
| P2 | Import (`/import`) | Tab llega al selector de archivos con foco visible; Enter abre el diálogo; cola, procesar 1 y 2+ archivos; 11 archivos avisa del límite sin enviar | [ ] |
| P3 | Catalog (`/catalog?run=…`) | Columnas históricas en su orden y SKU/ASIN-UPC/Record/Issues al final; ocultar/reordenar y recargar; filtro de provenance campo+estado; aviso si falta uno; Export descarga solo lo filtrado | [ ] |
| P4 | Runs (`/runs`) | Ordenar por cada campo, ascendente/descendente; el texto describe el orden; límite de 100 explícito | [ ] |
| P5 | Run Detail (`/runs/<id>`) | Hash completo legible; descarga completa .xlsx; «Load batch context and record preview» muestra batch y 25 registros; errores con Retry | [ ] |
| P6 | Batch (`/batch/<id>`) | Archivos del lote, estados y analítica por archivo; enlace a cada run | [ ] |
| P7 | Product Detail (`/run/<id>/product/<ref>`) | Evidencia por campo con su estado; valores INVALID con su valor crudo; sin imagen ni enlace de proveedor; Back vuelve al Catalog | [ ] |
| P8 | Appearance (`/appearance`) | Ocho colores, fit/position/overlay, logo/fondo PNG/JPEG/WebP ≤ 512 KiB; el texto personalizado se ve en claro y oscuro; Reset restaura; importación de preferencias antiguas solo si no hay actuales | [ ] |
| P9 | Methodology (`/about`) | Texto de fuentes y límites; menciona el gráfico DEMO como no usado en cálculos | [ ] |
| P10 | Compare / Favorites | Estado honesto de «no conectado»/local; ningún dato inventado | [ ] |

## 3. Transversal

- [ ] **Responsive:** a 360/390/768/1440 no hay scroll horizontal de página; en
      móvil la barra de navegación queda fija arriba y opaca.
- [ ] **Navegación:** los ocho destinos funcionan; en detalles se marca la
      sección padre; colapsar la barra lateral (escritorio) persiste al recargar;
      Back/Forward y enlaces en la misma pestaña.
- [ ] **Rutas antiguas:** `/upload`, `/products?run=…`, `/batches/<id>`,
      `/runs/<id>/records/<ref>` llevan a la ruta nueva conservando IDs y query.
- [ ] **Teclado y accesibilidad:** Tab/Shift+Tab recorre todo con foco visible;
      los controles tienen nombre; los gráficos tienen alternativa en texto.
- [ ] **Provenance:** VERIFIED/INFERRED/NOT_FOUND/INVALID se distinguen; nada se
      muestra como verificado sin evidencia; INFERRED nunca aparece como VERIFIED.
- [ ] **Gráfico DEMO (Product Detail):** etiqueta `DEMO_FIXTURE · NOT VERIFIED`
      visible; Line/Bar; no se confunde con datos del producto; ninguna cifra
      DEMO aparece en Catalog, exports ni decisiones.
- [ ] **Decisiones:** BUY/REVIEW/PASS y sus razones coinciden con lo esperado
      para los archivos de prueba; ningún filtro cambia una decisión registrada.

## 4. PWA (build de producción)

Ver procedimiento y evidencia de laboratorio en el
[runbook §3](FRONTEND_NEXT_CUTOVER_RUNBOOK.md#3-pwa-instalación-actualización-y-convivencia).

- [ ] Instalar desde el navegador (icono de instalación) y abrir como app.
- [ ] Sin red, una ruta muestra «JUVAl is offline» y no muestra datos.
- [ ] DevTools → Application → Cache Storage: solo `juval-next-offline-v1` con
      `/offline.html`.

## 5. Resultado y firma

| Campo | Valor |
|---|---|
| Commit / tree revisado | |
| Navegador y versión / SO | |
| Fecha | |
| Pantallas aceptadas | |
| Defectos encontrados (con captura) | |
| Decisión sobre ADR-054 (G12) | Aceptar / Rechazar / Pendiente |
| **Aceptación visual de frontend-next** | Aceptado / Aceptado con defectos / Rechazado |
| Firma del propietario | |

La aceptación visual **no autoriza el cutover**; esa autorización se da aparte
(runbook §5).
