# Juval — Arquitectura del sistema (Fase 0)

Estado del contenido de este documento hasta §15: **propuesta de diseño
original de Fase 0**, escrita cuando el repositorio estaba vacío — se
conserva tal cual como registro histórico (incluye nombres conceptuales
como `CatalogRecord`/`RawRecord`/`ResultModel` que **no existen** en el
código actual; el nombre real implementado es `SourcingRecord`, ver
`docs/architecture/DATA_MODEL.md`). **§16 (al final de este documento)
es la fotografía del estado real de implementación, actualizada en cada
reconciliación** — ante cualquier lectura de este documento, §16 y
`docs/PROJECT_STATUS.md` tienen prioridad sobre §1-§15 para saber qué
existe hoy. Fecha de la propuesta original: 2026-08-16.

## 1. Estado actual del repositorio

Inspección realizada antes de escribir este documento:

- El directorio `APP` estaba **completamente vacío**: sin `.git`, sin código, sin
  `README`, sin dependencias, sin tests, sin configuración.
- No existía ninguna decisión arquitectónica previa que respetar.
- No hay control de versiones inicializado (`git init` no se ha ejecutado; se
  deja como decisión pendiente para el usuario, ver §11).

Conclusión: este es un proyecto **greenfield**. No hay riesgo de romper nada
existente, pero tampoco hay nada de qué partir — todo lo que sigue es
propuesta, no hecho consumado.

## 2. Principios rectores

Orden de prioridad explícito para cualquier decisión de diseño futura:

1. **Correctitud** — un resultado incorrecto es peor que ningún resultado.
2. **Trazabilidad** — todo dato debe poder explicarse: de dónde salió, cómo,
   cuándo.
3. **Reproducibilidad** — la misma entrada + misma versión del sistema debe
   producir el mismo resultado (o un resultado explicablemente distinto si
   una fuente externa cambió).
4. **Escalabilidad** — el diseño no debe bloquear crecimiento en volumen o en
   número de fuentes de enriquecimiento.
5. **Automatización** — preparar el camino a ejecución desatendida (lotes,
   cron, CI), sin necesitarla desde el día uno.
6. **Velocidad** — deliberadamente el último criterio. No se sacrifica
   correctitud o trazabilidad por rendimiento.

Regla dura que se deriva de esto: **ninguna capa puede "inventar" ni
"asumir" un valor**. Si no hay evidencia suficiente, el dato se marca
`NOT_FOUND` y se propaga así hasta el resultado final.

## 3. Arquitectura de componentes

```mermaid
flowchart TB
    subgraph UI["Interfaces (intercambiables)"]
        CLI[CLI]
        API[API / futura PWA]
        DESK[Wrapper Windows .exe]
    end

    subgraph APP["Application Layer"]
        UC[Casos de uso / orquestación\nej: ProcessCatalogBatch]
    end

    subgraph CORE["Processing Core (independiente, sin I/O)"]
        VAL[Validation]
        ENR[Enrichment]
        CLA[Classification]
    end

    subgraph INFRA["Infrastructure"]
        IMP[Excel Importer]
        EXP[Excel Exporter]
        SRC[Fuentes externas\n(adapters, futuras)]
        LOG[Logging / Run Registry]
    end

    CLI --> UC
    API --> UC
    DESK --> UC
    UC --> VAL --> ENR --> CLA
    UC --> IMP
    UC --> EXP
    ENR --> SRC
    UC --> LOG
    IMP -. "filas crudas" .-> UC
    UC -. "Result Model" .-> EXP
```

### 3.1 Capas y responsabilidades

| Capa | Responsabilidad | No debe hacer |
|---|---|---|
| **Interfaces** (CLI / API / desktop) | Recibir input del usuario, mostrar resultados, disparar casos de uso | Contener reglas de negocio, validar datos de dominio, tocar Excel directamente |
| **Application Layer** | Orquestar un caso de uso completo (`ProcessCatalogBatch`, `ExportResults`, ...); decide *qué* pasos ocurren y en qué orden | Conocer detalles de Excel (columnas, celdas) ni de la interfaz que la invoca |
| **Processing Core** | Validación, enriquecimiento, clasificación sobre el **Modelo Interno**; reglas puras, testeables sin I/O | Leer/escribir archivos, llamar APIs externas directamente (usa puertos/interfaces), saber que existe Excel |
| **Infrastructure** | Importador/Exportador Excel, adapters de fuentes externas, logging, persistencia de runs | Contener reglas de negocio o decidir estados de verificación |

### 3.2 Regla de dependencia

Las flechas de dependencia de código van **hacia adentro**: Interfaces →
Application → Processing Core. Infrastructure implementa **puertos**
(interfaces/protocolos) que Application y Processing Core definen pero no
implementan — inversión de dependencias. Así, el Core nunca importa
`openpyxl`, `pandas`, un cliente HTTP, o un framework web.

Esto es lo que permite que la misma lógica de negocio sirva detrás de una
PWA o de un `.exe` sin duplicarse (ver ADR-001).

## 4. Modelo interno de dominio (conceptual)

El Excel es **formato de intercambio**, nunca el modelo de dominio (ver
ADR-002). Al importar, cada fila se convierte en una entidad de dominio;
al exportar, el modelo de dominio se convierte de vuelta a filas.

### 4.1 Entidades principales

- **`CatalogRecord`** (producto/registro de catálogo)
  - `record_ref`: identificador lógico y estable de la fila de origen (no la
    posición física — ver §6). Ej: SKU si existe, o un id sintético
    `row_hash`.
  - `sku`: opcional, tal como viene del Excel.
  - `title`: opcional, descriptivo.
  - `asin`: `FieldValue[str]`
  - `weight`: `FieldValue[Decimal]` (con `unit`, ej. `lb`/`kg`)
  - `dimensions`: `FieldValue[Dimensions]` opcional (`length`, `width`,
    `height`, `unit`)
  - `hazmat`: `FieldValue[bool]`
  - `bulky`: `FieldValue[bool]`
  - `issues`: lista de `ProcessingIssue` (errores y warnings del registro)
  - `status`: `RecordStatus` (`OK` / `PARTIAL` / `FAILED`)

- **`FieldValue[T]`** — envoltorio de **provenance** para todo campo
  sensible (ver §5 y ADR-003/ADR-004). Nunca se guarda un `str`/`float`
  "pelado" para ASIN, peso, hazmat o bulky.

- **`ProcessingIssue`**
  - `level`: `FATAL` / `RECORD_ERROR` / `WARNING`
  - `code`: identificador estable (ej. `MISSING_COLUMN`, `INVALID_WEIGHT_UNIT`)
  - `message`: texto legible
  - `field`: campo afectado, si aplica
  - `record_ref`: a qué registro pertenece (si no es a nivel de lote)

- **`ExecutionRun`** (una corrida del sistema, para reproducibilidad)
  - `run_id`, `started_at`, `finished_at`
  - `system_version` (versión de Juval, no solo del archivo)
  - `input_file` (nombre + hash del contenido)
  - `record_count`, `error_count`, `warning_count`
  - `sources_used`: qué fuentes externas se consultaron en esta corrida
  - `status`: `SUCCESS` / `PARTIAL_SUCCESS` / `FAILED`

No se modelan campos adicionales especulativos (ej. precio, categoría,
proveedor) hasta que haya un requisito concreto que los necesite.

### 4.2 Relaciones

```
ExecutionRun 1---N CatalogRecord
CatalogRecord 1---N ProcessingIssue
CatalogRecord 1---1 FieldValue<asin>
CatalogRecord 1---1 FieldValue<weight>
CatalogRecord 1---1 FieldValue<hazmat>
CatalogRecord 1---1 FieldValue<bulky>
CatalogRecord 0---1 FieldValue<dimensions>
```

## 5. Estrategia de provenance

Ver ADR-003 y ADR-004 para el detalle normativo. Estructura de
`FieldValue[T]`:

| Campo | Descripción |
|---|---|
| `value` | El valor tipado, o `None` si `status == NOT_FOUND` |
| `unit` | Unidad cuando aplica (peso, dimensiones); `None` si no aplica |
| `status` | `VERIFIED` \| `INFERRED` \| `NOT_FOUND` \| `INVALID` |
| `source` | Identificador de la fuente (`"excel_input"`, `"rule:hazmat_by_keyword"`, `"amazon_catalog_api"`, ...) |
| `method` | Cómo se obtuvo (`"direct_read"`, `"lookup"`, `"manual_override"`, nombre de regla) |
| `retrieved_at` | Timestamp de obtención (no de creación del registro) |
| `evidence` | Opcional: texto/URL/snapshot que soporta el valor |
| `confidence` | Opcional, solo informativo — **nunca** sustituye a `status` |

Reglas duras (verificadas en self-review, §12):

- Un valor `INFERRED` **nunca** se presenta ni se serializa como `VERIFIED`.
  Son variantes distintas del enum `VerificationStatus`, no un booleano
  adicional que se pueda perder.
- `NOT_FOUND` implica `value = None`. No existe una ruta de código que
  convierta `NOT_FOUND` en un valor por defecto silencioso (ej. peso = 0,
  hazmat = false). Si el negocio necesita un valor por defecto explícito
  algún día, eso es una decisión de negocio documentada, no un fallback
  técnico oculto.
- `INVALID` conserva el valor original (crudo) en un campo separado
  (`raw_value`, ver Excel Importer) para poder diagnosticar *por qué* es
  inválido, en vez de simplemente descartarlo.

## 6. Estrategia de importación / exportación Excel

Capa aislada en `infrastructure/excel/` (ver ADR-002). Responsabilidades:

**Importador**
1. Leer el archivo (`.xlsx`).
2. Validar la presencia de columnas requeridas **por nombre de encabezado**,
   nunca por posición/índice — un usuario puede reordenar columnas sin
   romper el sistema.
3. Reportar columnas faltantes como error fatal (aborta el batch) o
   columnas opcionales faltantes como warning, según configuración de
   esquema esperado.
4. Normalizar valores crudos a tipos primitivos (strings a `Decimal`,
   texto de hazmat/bulky a booleano) — esta normalización es sintáctica
   (parseo), **no** de negocio; no decide si un dato es válido según reglas
   de dominio, solo si es parseable.
5. Producir un `RawRecord` por fila con `record_ref` estable (fila +
   hash de contenido, o SKU si es único) y pasarlo a Application Layer,
   que lo convierte en `CatalogRecord` a través del Processing Core.

**Exportador**
1. Recibe el `ResultModel` (lista de `CatalogRecord` procesados + resumen
   del `ExecutionRun`).
2. Aplana cada `FieldValue` a columnas explícitas: valor, unidad, status,
   fuente — nunca colapsa un `FieldValue` a una sola celda con el valor
   pelado, porque eso destruiría la trazabilidad en el artefacto que el
   usuario realmente mira.
3. Incluye una hoja/sección de resumen de la corrida (errores, warnings,
   conteos) además del detalle por fila.

El procesamiento de negocio (Processing Core) nunca importa el módulo de
Excel ni conoce nombres de columnas — solo trabaja sobre `CatalogRecord`.

## 7. Estrategia de validación

Taxonomía de severidad (usada de forma consistente en todo el sistema):

| Nivel | Efecto | Ejemplo |
|---|---|---|
| `FATAL` | Aborta el batch completo, no se genera resultado parcial | Archivo ilegible, falta columna obligatoria, versión de esquema no soportada |
| `RECORD_ERROR` | El registro específico no se puede procesar; se excluye del resultado "exitoso" pero se reporta explícitamente | Fila sin ningún identificador de producto |
| `WARNING` | El registro se procesa igual, pero se marca | Peso fuera de un rango razonable, columna opcional ausente |
| Dato faltante | No es un error de validación por sí solo — es un `FieldValue` con `status=NOT_FOUND` | ASIN no encontrado tras enriquecimiento |
| Dato inválido | `FieldValue` con `status=INVALID` + `raw_value` conservado | Peso no numérico, ASIN con formato incorrecto |
| Dato inferido | `FieldValue` con `status=INFERRED` — no es error, es una clasificación de confianza que se debe poder auditar | hazmat derivado de una regla por palabra clave |

El sistema **procesa lotes completos y reporta todos los errores
encontrados**, no se detiene en el primer `RECORD_ERROR` (solo se detiene
ante `FATAL`). Ocultar errores para "hacer pasar" un batch está
explícitamente prohibido por los requisitos del proyecto.

## 8. Estrategia de logging y reproducibilidad

**Diseño original (Fase 0, conceptual)**: cada ejecución genera un
`ExecutionRun` persistido (inicialmente como archivo estructurado, ej.
JSON, junto al resultado exportado; una base de datos es una evolución
posible, no un requisito de MVP), con contenido mínimo: `run_id`,
`system_version`, timestamp de inicio/fin, archivo de entrada (nombre +
hash), conteo de registros/errores/warnings, fuentes externas
efectivamente usadas en esa corrida, referencia al archivo de resultado
exportado. Logging operacional (texto/estructurado a stdout o archivo)
se mantiene separado del `ExecutionRun` (que es el registro de
auditoría/negocio); el primero es para debugging técnico, el segundo es
un documento de trazabilidad que puede mostrarse a alguien de negocio.

**Estado real (actualizado 2026-08-16, ver ADR-013)**: `ExecutionRun`
(`domain/execution_run.py`) implementa un subconjunto de ese diseño
original — `execution_id` (no `run_id`), `started_at`/`finished_at`,
`status`, `input_filename`+`input_hash`, `application_version`, y
contadores de registros/warnings. **No** incluye `sources_used` ni
`thresholds` (gap de diseño conocido, ver
`docs/architecture/EXECUTION_MODEL.md` §3) ni una referencia al archivo
de resultado exportado.

**Persistencia: IMPLEMENTADA con SQLite local** (ADR-013, `Estado:
Aceptada`, aprobada explícitamente por el usuario 2026-08-16) —
`infrastructure/logging/sqlite_execution_run_store.py::SqliteExecutionRunStore`
implementa el puerto `application/execution_run_store.py::ExecutionRunStore`
(`save_execution_run(run)` / `load_execution_run(execution_id)`),
probado con round-trip a través de conexiones/instancias de store
distintas (`tests/integration/test_execution_run_store.py`, 12 tests).
No es un archivo JSON como sugería el diseño original — SQLite se eligió
en su lugar (ver ADR-013 §"Por qué SQLite").

**Limitaciones explícitas de este estado**: (1) alcance single-user,
local — no resuelve acceso concurrente multiusuario/remoto (eso sigue
correspondiendo a Fase 8, `Supabase`, `BLOCKED`); (2)
`application/run_pipeline.py` **no invoca** el store — persistir una
corrida es una acción explícita del llamador
(`store.save_execution_run(run)`), no un efecto automático de ejecutar
el pipeline; (3) no existe `list_execution_runs()` ni ninguna forma de
consultar el historial más allá de `load_execution_run(execution_id)`
conociendo el id exacto. Detalle completo en ADR-013 §"Qué NO resuelve
esta decisión".

Reproducibilidad realista: dado el mismo archivo de entrada y la misma
versión del sistema, sin fuentes externas, el resultado debe ser idéntico.
Con fuentes externas, se documenta la fuente y momento de consulta para que
una diferencia sea explicable, no misteriosa.

## 9. Estrategia de tests

| Tipo | Objetivo | Ejemplos |
|---|---|---|
| Unit | Processing Core en aislamiento (sin I/O) | Reglas de clasificación hazmat/bulky, transición de estados de `FieldValue`, validación de un `CatalogRecord` |
| Integración — importación | Excel real → `RawRecord`/`CatalogRecord` | Archivo con columnas correctas, columnas faltantes, columnas fuera de orden, tipos inválidos |
| Integración — exportación | `ResultModel` → Excel real, y round-trip básico | Verificar que provenance se refleja en columnas separadas, no colapsada |
| Integración — pipeline completo | Excel de entrada → Excel de salida, sin mocks del Core | Casos con mezcla de `VERIFIED`/`INFERRED`/`NOT_FOUND`/`INVALID` |
| Reglas de clasificación | Cada regla de inferencia probada con casos borde | Palabra clave ambigua, unidad de peso no reconocida |

Regla dura: los tests **no deben ocultar errores para pasar** — un test que
verifica manejo de errores debe afirmar que el error fue *reportado*
correctamente, no que desapareció.

## 10. PWA vs. `.exe` — análisis sin decisión irreversible

| Necesidad futura | Favorece navegador/PWA | Favorece `.exe` local |
|---|---|---|
| Acceso a archivos locales sin fricción | — | Sí (filesystem nativo) |
| Multiusuario / acceso concurrente | Sí | — |
| Distribución sin instalación | Sí | — |
| Procesamiento pesado offline | — | Sí, o backend compartido |
| Ejecución remota / automatización desatendida | Sí (servidor) | Limitado |
| Persistencia centralizada de runs históricos | Sí (servidor) | Requiere sincronización aparte |

Esta tabla documenta el análisis original de Fase 0, todavía válido como
comparación de tradeoffs — se conserva sin reescribir. La arquitectura
propuesta evitó que esta decisión fuera costosa: el Processing Core y la
Application Layer no saben si quien los invoca es un proceso CLI local,
un backend detrás de una PWA, o un `.exe` empaquetado — ver ADR-005.

**Actualizado 2026-08-17**: la elección ya se tomó — **PWA**, aprobada
explícitamente por el usuario vía ADR-014 (`Estado: Aceptada`). `.exe`
no se construirá como interfaz principal. Framework de backend/frontend
concreto y deployment siguen sin aprobar (ver ADR-014 §"Límites
explícitos de esta decisión" y `docs/PROJECT_PLAN.md` §Fase 4).

## 11. Propuesta de estructura de directorios

Se creó el siguiente esqueleto (carpetas + `README.md` de propósito en cada
una; **sin código de negocio todavía**):

```
APP/
├── docs/
│   ├── architecture/
│   │   └── ARCHITECTURE.md        (este documento)
│   └── adr/
│       ├── ADR-001-separacion-ui-processing-core.md
│       ├── ADR-002-excel-formato-intercambio.md
│       ├── ADR-003-provenance-datos.md
│       ├── ADR-004-estados-verificacion.md
│       └── ADR-005-independencia-pwa-exe.md
├── src/
│   └── juval/
│       ├── domain/                 (entidades: CatalogRecord, FieldValue, etc.)
│       ├── processing/             (validation, enrichment, classification — puro)
│       ├── application/            (casos de uso / orquestación)
│       ├── infrastructure/
│       │   ├── excel/              (importer/exporter)
│       │   ├── enrichment/         (adapters a fuentes externas, futuro)
│       │   └── logging/            (ExecutionRun, logging técnico)
│       └── interfaces/
│           ├── cli/                (punto de entrada por línea de comandos)
│           ├── api/                (futuro backend para PWA)
│           └── desktop/            (futuro wrapper .exe)
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/                   (archivos Excel de prueba)
```

Nota: la existencia de `interfaces/api` e `interfaces/desktop` **no**
implica que ambas se implementen — son ranuras que la arquitectura deja
abiertas hasta que ADR-005 se resuelva con datos reales de uso.

## 12. Self-review (checklist de cierre de fase)

- [x] ¿Hay acoplamientos innecesarios? No — Core no depende de Excel ni de
      interfaz; Infrastructure implementa puertos definidos hacia adentro.
- [x] ¿Hay duplicación? No aplica todavía (no hay código); el diseño evita
      duplicar lógica de negocio entre CLI/API/desktop al centralizarla en
      Application + Core.
- [x] ¿Hay decisiones prematuras? Se evitó fijar PWA vs. `.exe` (ADR-005
      documenta el análisis, no una elección forzada); se evitó modelar
      campos no solicitados (precio, categoría, proveedor, etc.).
- [x] ¿Riesgos de escalabilidad? Ver §13.
- [x] ¿Excel se convirtió en el modelo de dominio? No — `RawRecord` /
      Excel Importer producen datos crudos; `CatalogRecord` es el modelo
      interno y es lo único que ve Processing Core.
- [x] ¿`VERIFIED` e `INFERRED` pueden confundirse? No — son valores
      distintos y mutuamente excluyentes de un mismo enum `VerificationStatus`,
      no flags independientes que puedan desincronizarse.
- [x] ¿`NOT_FOUND` puede volverse un valor silenciosamente? No — por diseño
      `NOT_FOUND` implica `value=None`; no existe ruta de "valor por
      defecto" en el Core.
- [x] ¿Sirve tanto detrás de PWA como de `.exe`? Sí — ambas serían
      "Interfaces" delgadas que llaman a la misma Application Layer.
- [x] ¿Los tests propuestos detectan regresiones? Sí — cubren Core en
      aislamiento (reglas), import/export Excel, y pipeline completo con
      los cuatro estados de verificación representados.

## 13. Riesgos identificados

- **Ambigüedad de `record_ref`**: si el Excel de origen no tiene un
  identificador único confiable (SKU vacío/duplicado), hay que decidir la
  estrategia de hash de fila. Pendiente de definir con datos reales.
- **Unidades de peso/dimensiones**: si el Excel mezcla `lb`/`kg` sin
  columna de unidad explícita, la normalización puede ser ambigua —
  requiere regla de negocio explícita, no un default silencioso.
- **Fuentes de enriquecimiento aún no definidas**: no se sabe todavía qué
  fuente(s) externas se usarán para verificar ASIN/peso/hazmat/bulky, lo
  que afecta el diseño concreto de los adapters (rate limits, costos,
  formato de evidencia). Se deja como puerto abierto, no bloquea el diseño
  actual.
- **Volumen esperado**: no se conoce el tamaño típico de un Excel de
  entrada (cientos vs. cientos de miles de filas), lo que afecta si el
  pipeline puede ser síncrono en memoria o necesita streaming/paralelismo.

## 14. Decisiones pendientes explícitas

1. Lenguaje/framework de implementación concreto (hay una recomendación
   técnica en §15, pero no se ha fijado como ADR).
2. Fuente(s) externas de verificación para ASIN/peso/hazmat/bulky.
3. Estrategia definitiva de `record_ref` cuando no hay SKU confiable.
4. Unidad canónica interna para peso y dimensiones (¿todo se normaliza a
   `lb`/`in`, o se conserva la unidad original siempre?).
5. Persistencia de `ExecutionRun`: ¿archivo plano por corrida, o base de
   datos desde el inicio?
6. PWA vs. `.exe` vs. ambos (ADR-005 deja el análisis, no la decisión).
7. ¿Se inicializa control de versiones (`git init`) ahora o lo hace el
   usuario?
8. Política de reglas de inferencia: ¿quién define/aprueba las reglas que
   producen `INFERRED` (ej. hazmat por palabra clave)? Esto es una decisión
   de negocio con impacto legal/comercial, no solo técnica.

## 15. Recomendación técnica para la siguiente fase

**Lenguaje: Python 3.11+** para Domain / Processing Core / Application /
Infrastructure, por:

- Ecosistema maduro de Excel (`openpyxl`) sin depender de Excel instalado.
- `pydantic` (o `dataclasses` + validación explícita) encaja bien con el
  modelo `FieldValue`/`CatalogRecord` tipado y con validación en los
  bordes.
- Un mismo Core puede exponerse por CLI (`typer`/`argparse`), por API
  (`FastAPI`, para una futura PWA) y empaquetarse a `.exe` (`PyInstaller`),
  sin reescribir lógica de negocio — soporta directamente ADR-005.
- Buen soporte de testing (`pytest`) para la estrategia de §9.

Esto es una recomendación, no un ADR, porque no es estrictamente
irreversible: Processing Core queda aislado detrás de la Application Layer,
así que si más adelante hay una razón de peso para migrar, el radio de
impacto es acotado. Si el usuario prefiere otro stack (TypeScript/Node,
por ejemplo, si la PWA es prioridad #1), la arquitectura no cambia, solo
la implementación.

**Siguiente vertical slice concreto propuesto (Fase 1):**

> Importar un Excel real de ejemplo → mapear a `CatalogRecord` con
> `FieldValue` para `asin`, `weight`, `hazmat`, `bulky` (todos con
> `status=VERIFIED` si vienen directos del Excel, o `NOT_FOUND` si la
> columna está vacía) → validar (fatal si faltan columnas requeridas) →
> exportar de vuelta a Excel con columnas de provenance visibles → un test
> de integración de extremo a extremo con un archivo de ejemplo pequeño.

Deliberadamente **sin enriquecimiento externo ni reglas de inferencia
todavía** — eso demuestra el esqueleto completo (Excel → Domain →
Processing → Excel) con datos 100% verificables (lo que ya viene en el
Excel), antes de introducir la complejidad de fuentes externas e
inferencia.

## 16. Estado de implementación (actualizado 2026-08-17)

Este documento describió, en su versión original, un repositorio
**vacío** (§1). Ya no lo está. Esta sección es la fotografía de qué
capas tienen código real hoy, para que el resto del documento (diseño
conceptual, en gran parte todavía vigente) no se lea como si nada se
hubiera construido. Ver `docs/PROJECT_STATUS.md` para el detalle
completo y actualizado con más frecuencia que este archivo.

| Capa | Estado | Evidencia |
|---|---|---|
| Domain | **IMPLEMENTED** | `src/juval/domain/{provenance,product,costs,risk,decision,identifiers,units,issues,sourcing_record,execution_run}.py` |
| Processing Core | **IMPLEMENTED** | `src/juval/processing/{profitability,decision_engine,decision_score,data_quality,pipeline}.py` |
| Application Layer | **IMPLEMENTED** (un caso de uso) | `src/juval/application/run_pipeline.py` |
| Infrastructure — Excel | **IMPLEMENTED** | `src/juval/infrastructure/excel/{importer,exporter,column_mapping}.py`, ver `docs/architecture/EXCEL_PROCESSING.md` |
| Infrastructure — enrichment (fuentes externas) | **NOT IMPLEMENTED** | solo `README.md` |
| Infrastructure — logging (persistencia de `ExecutionRun`) | **IMPLEMENTED** (SQLite local, ADR-013 `Aceptada`) | `SqliteExecutionRunStore` implementa el puerto `ExecutionRunStore`; probado con round-trip entre conexiones. No invocado automáticamente por `run_pipeline()` (Opción B) — ver §8 arriba y ADR-013 |
| Interfaces — CLI | **IMPLEMENTED** (2026-08-17) | `src/juval/interfaces/cli/main.py` — `argparse` (stdlib, sin dependencia nueva) sobre `run_pipeline()` + `export_excel()`; thresholds/fees siempre explícitos por flag (ADR-007); persistencia opt-in vía `--persist-db` (ADR-013, Opción B). Ver `docs/architecture/EXECUTION_MODEL.md` |
| Interfaces — API (backend PWA) | **NOT IMPLEMENTED** | solo `README.md`; interfaz elegida (ADR-014, PWA), bloqueada por framework backend/frontend/deployment sin aprobar |
| Interfaces — desktop | **NOT IMPLEMENTED** | solo `README.md`; `.exe` no se construirá como interfaz principal (ADR-014); sin trabajo planeado |
| AI Analyst | **NOT IMPLEMENTED** (diseño only) | `AI_ANALYST.md`, ADR-008 |
| Persistencia (Supabase) / Auth (Clerk) / Framework frontend+backend de la PWA (Next.js, FastAPI u otros) | **PENDING** (decisión no aprobada) | `CLAUDE.md` §14, ADR-014 §"Límites explícitos" |

`SourcingRecord`, mencionado en §4.1/§14 como pendiente de Fase 1, está
**implementado** desde Fase 2 como composición pura de los tipos ya
descritos aquí (ADR-011) — ver `docs/architecture/DATA_MODEL.md` y
`docs/architecture/PROCESSING_PIPELINE.md`.

### 16.1 Flujo de datos real (implementado hoy)

```
Excel Input (.xlsx)
   ↓  Ingestion + Normalize   (infrastructure/excel/importer.py)
   ↓  Validate (formato de celda: número/booleano/ASIN/UPC)
   ↓  Domain Model            (SourcingRecord, domain/*.py)
   ↓  Processing              (processing/pipeline.py::process_record)
   │     ├─ Data Quality (re-validación estructural)
   │     ├─ Profitability (processing/profitability.py)
   │     ├─ Risk (leído del SourcingRecord, ya construido en import)
   │     └─ Decision (processing/decision_engine.py) → BUY/REVIEW/PASS
   ↓  Output                  (infrastructure/excel/exporter.py)
Excel Output (.xlsx)
```

`AI Explanation` **no** es parte de este flujo todavía — es la capa
conceptual final, diseñada pero sin código
(`docs/architecture/AI_ANALYST.md`, ADR-008). Cuando exista, se conecta
estrictamente **después** de `Output`, nunca entre `Domain` y
`Decision`: la IA lee resultados ya calculados, nunca sustituye
`Processing`/`Risk`/`Decision`. Ver `docs/architecture/AI_ANALYST.md` y
`docs/architecture/PROCESSING_PIPELINE.md`.

### 16.2 Límites entre componentes verificados en código (no solo en diseño)

- `processing/pipeline.py` no importa `openpyxl` ni ningún símbolo de
  `infrastructure/` — verificado por inspección de imports.
- `infrastructure/excel/importer.py` y `exporter.py` no contienen
  ninguna regla de negocio (fees, profit, decisión) — solo parseo,
  normalización de unidades/formatos y mapeo de columnas.
- `application/run_pipeline.py` es el único módulo que importa tanto
  `infrastructure/` (`import_excel`) como `processing/` (`process_batch`)
  — consistente con la regla de dependencia de §3.2.
