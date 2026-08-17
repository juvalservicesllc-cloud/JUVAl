# Juval — Security

Documenta el estado real de seguridad del repositorio hoy y las reglas
que aplican a trabajo futuro (`CLAUDE.md` §16). Este documento no
implementa controles nuevos — es un inventario y una referencia. Ningún
control descrito aquí como PENDING/NOT IMPLEMENTED debe tratarse como si
ya existiera.

## 1. Estado actual del repositorio

| Área | Estado | Evidencia |
|---|---|---|
| Secrets / API keys en el código | **Ninguno encontrado** | No hay ningún adapter de fuente externa implementado (`infrastructure/enrichment/` vacío) que requeriría credenciales; no hay archivos `.env` en el repo |
| Control de versiones | **NOT INITIALIZED** | No existe `.git` en el repositorio (`git status` falla con "not a git repository"). Decisión explícitamente pendiente del usuario (`ARCHITECTURE.md` §14.7) — no se ejecuta `git init` sin autorización. |
| `.gitignore` | **IMPLEMENTED** (para cuando se inicialice git) | Excluye `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.egg-info/`. No incluye todavía una entrada para `.env` — no hace falta hoy porque no existe ningún `.env`, pero debe agregarse en el mismo cambio que introduzca el primer secreto real. |
| Autenticación de usuarios | **NOT IMPLEMENTED** | Sin interfaz alguna (CLI/API/desktop no implementadas), no hay superficie de autenticación que asegurar todavía. Ver Fase 9 en `PROJECT_PLAN.md` (bloqueada, Clerk PENDING). |
| Autorización / aislamiento de datos por usuario | **NOT IMPLEMENTED** | No aplica sin autenticación ni persistencia multiusuario. |
| Persistencia de datos | **NOT IMPLEMENTED** | Todo el procesamiento es in-memory por corrida (ver `EXECUTION_MODEL.md`); no hay base de datos que asegurar. |
| Validación de input (Excel) | **IMPLEMENTED (parcial)** | `infrastructure/excel/importer.py` valida tipo y formato celda a celda (número/booleano/ASIN/UPC), y columnas requeridas ausentes abortan el import (`FATAL`). No se ha evaluado explícitamente contra amenazas específicas de `openpyxl` (ver §3). |
| Ejecución de contenido del usuario como código | **No aplica / no ocurre** | El importer solo lee valores de celda como datos (texto/número/booleano); no evalúa fórmulas de Excel como código ni ejecuta macros. `openpyxl.load_workbook(..., data_only=True)` lee el último valor calculado de una fórmula, no la fórmula misma, y no ejecuta macros VBA. |
| Logging de datos sensibles | **No aplica todavía** | No existe logging operacional implementado (`infrastructure/logging/` vacío, solo `README.md`); no hay riesgo actual de que un log exponga PII/tokens porque no hay logs. Ver §4 para la regla que debe aplicarse cuando se implemente. |
| PII | **Mínima exposición hoy** | El dominio no modela datos de personas (clientes, empleados) — modela productos. `top_seller_fba`/`top_seller_fbm` (`Competition`) podrían contener nombres de vendedores de terceros si una fuente externa los provee; hoy no hay ninguna fuente que los llene. |

## 2. Reglas duras (`CLAUDE.md` §16) — aplican a todo trabajo futuro

- Nunca hardcodear secrets en código.
- Nunca guardar API keys en Git.
- Nunca imprimir tokens en logs.
- Nunca incluir credenciales en código fuente.
- Nunca confiar ciegamente en archivos Excel del usuario — validar todo
  upload (parcialmente implementado hoy, ver §1; falta cobertura contra
  amenazas específicas de formato, ver §3).
- Nunca ejecutar contenido del usuario como código.
- Usar variables de entorno y mecanismos apropiados de gestión de
  secrets cuando exista el primer secreto real (ninguno existe hoy).

## 3. Riesgos identificados, sin mitigación implementada todavía

Estos son observaciones de este documento, no hallazgos de un security
review formal ni tareas aprobadas para ejecutar:

1. **Tamaño de archivo Excel no acotado.** `import_excel` no impone un
   límite de tamaño o de filas antes de cargar el workbook completo en
   memoria (`read_only=True` mitiga parcialmente el uso de memoria, pero
   no hay un límite explícito ni un manejo de `MemoryError`). Relevante
   si Juval llega a aceptar archivos de fuentes no confiables.
2. **Sin límite de tasa ni cuota** en `import_excel`/`run_pipeline` — no
   aplica hoy porque no hay interfaz expuesta a usuarios externos, pero
   es una consideración pendiente para cuando exista una API (Fase 4).
3. **`openpyxl` como dependencia externa** — cualquier vulnerabilidad en
   la librería de parseo de `.xlsx` afecta directamente la superficie de
   ataque del Excel Importer. No se ha hecho un audit de la versión
   fijada en `pyproject.toml` (`openpyxl>=3.1`, sin límite superior).
4. **Ningún control de contenido en campos de texto libre** (`title`,
   `brand`, `description`, `evidence`, mensajes de `ProcessingIssue`)
   antes de que estos datos lleguen eventualmente a una futura interfaz
   web (Fase 4) — riesgo de XSS si esos valores se renderizan sin escape
   en una UI HTML. No aplica hoy (no hay UI), pero debe evaluarse
   explícitamente antes de construir Fase 4.

Ninguno de estos puntos se resuelve en esta tarea (documentación
únicamente); quedan como entradas para un futuro `/security-review` o
para el Completion Gate de la fase que corresponda.

## 4. Reglas para trabajo futuro (por área, cuando se implemente)

| Área futura | Regla a aplicar quando se implemente |
|---|---|
| `infrastructure/enrichment/` (Fase 6) | Credenciales de cualquier fuente externa vía variables de entorno, nunca en código ni en `docs/`; nunca loggear la API key completa (redactar o truncar en cualquier log/error) |
| `infrastructure/logging/` (persistencia de `ExecutionRun`) | No loggear el contenido completo de un `FieldValue` sensible en texto plano si el destino del log no es confiable; el `ExecutionRun` en sí (conteos, hash, timestamps) no es sensible |
| `interfaces/api/` (Fase 4) | Validar/sanitizar cualquier input antes de procesarlo; escapar cualquier texto libre del dominio (`title`, `evidence`, mensajes de `ProcessingIssue`) al renderizar en HTML |
| Persistencia (Fase 8, Supabase PENDING) | Ningún secreto de conexión en código; principio de menor privilegio en credenciales de base de datos |
| Autenticación (Fase 9, Clerk PENDING) | Aislamiento de datos por usuario/organización verificado por test explícito antes de declarar la fase completa (ver `PHASE_GATES.md` §Fase 9) |

## 5. Relacionado

`CLAUDE.md` §16 (fuente normativa de estas reglas), `DATA_SOURCES.md` §2
(regla dura de "sin scraping ni evasión", relevante para cualquier futura
fuente externa), `PROJECT_PLAN.md` Fase 8/Fase 9 (persistencia y auth,
ambas bloqueadas por decisiones PENDING).
