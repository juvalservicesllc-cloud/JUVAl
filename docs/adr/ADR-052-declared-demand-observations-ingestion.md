# ADR-052 — Enmienda acotada a ADR-046: ingestión de demanda declarada (D7-B)

- Estado: **Aceptada con condiciones** (2026-10-26) por decisión explícita del
  usuario. E1–E5, E7, E8, E12 y E13 se aprueban tal cual; E6, E9, E10, E11 y E14
  se aprueban con las correcciones que incorpora este texto.
- **Alcance de la aceptación:** solo ingestión **informativa**, es decir captura,
  persistencia, API, export, preview y visualización. **No autoriza** proyectar
  la demanda declarada hacia `Product.demand`, `DecisionInputs` ni el Decision
  Engine. Una observación INFERRED no puede habilitar BUY.
- ADR-046 conserva su estado *Accepted*. Esta enmienda se lee como su §20.
- Relacionados: ADR-003, ADR-004, ADR-011, ADR-012, ADR-019, ADR-045, ADR-046,
  ADR-047, ADR-050, ADR-051 (Propuesta), D7-D.

## 1. Contexto

- El importer no alimenta `Demand.estimated_monthly_sales`, y `DEMAND_UNKNOWN`
  deja en REVIEW cualquier registro importado (D7, medido 2026-10-26).
- El motor trata INFERRED como utilizable. Escribir demanda declarada en
  `Demand.estimated_monthly_sales` podría producir BUY, y eso no está autorizado.
- ADR-046 §9 define `DemandObservation(ESTIMATED_SALES)` con estas condiciones:
  - entero ≥ 0 en `units`, INFERRED cuando es utilizable;
  - ventana `[start, end)` con `end ≤ observed_at ≤ retrieved_at`;
  - población no vacía.

  También prohíbe:
  - presumir la duración de "mensual" (§8);
  - sustituir `observed_at` por `retrieved_at` (§7).

## 2. Enmienda 1 a ADR-046 (§20)

> **20.1 Preservación.** §1–§19 permanecen vigentes. Esta enmienda solo
> autoriza las excepciones de 20.2–20.6 y únicamente para la métrica
> `ESTIMATED_SALES` declarada en archivos de entrada. Las demás métricas, los
> conteos de competencia, la presencia de Amazon, los precios y las series
> siguen sin ingestión ni persistencia.
>
> **20.2 Ingestión autorizada.** El importer puede construir como máximo una
> `DemandObservation(metric=ESTIMATED_SALES)` por registro a partir de columnas
> explícitas del archivo (contrato D7-B). Solo es utilizable cuando el archivo
> declara todos los elementos que §9 exige; nunca se completa contexto con
> defaults, con la fecha de importación ni con el nombre de una columna.
>
> **20.3 Prohibición de promoción.** Una observación ingerida nunca escribe en
> `Product`, `Demand` ni ningún otro campo legacy, y ningún camino de código la
> proyecta a `DecisionInputs`. Para usarla en una decisión hace falta un ADR
> propio de proyección aprobado, con una versión de política registrada
> (ADR-051 o su sucesor). Hasta entonces la demanda elegible del motor sigue
> siendo exclusivamente `Demand.estimated_monthly_sales`, que el importer no
> rellena.
>
> **20.4 Frontera con el motor.** Las observaciones y sus diagnósticos viajan en
> un componente propio de `SourcingRecord` (`market_evidence`), por composición
> (ADR-011), fuera de `Product`. `processing/` no las importa ni las lee. Data
> quality, profitability, risk y decision no cambian.
>
> **20.5 Persistencia y consulta.** Se serializan como documento versionado
> `juval.adr046.demand-evidence` v1 dentro del snapshot de registro, con la
> identidad `(execution_id, record_ref)` de ADR-012, y se guardan en la misma
> escritura que el snapshot (transacción de ADR-019 y ADR-050). La API, los
> exports y la UI las exponen en solo lectura. Esta enmienda no autoriza
> filtrar, ordenar, agregar ni puntuar por demanda declarada.
>
> **20.6 Compatibilidad histórica.** Hay tres situaciones distintas y no
> intercambiables:
> - snapshot sin el documento: la captura no existía (`NOT_CAPTURED`);
> - documento `null`: el archivo no tenía columnas de demanda (`NOT_DECLARED`);
> - observación `NOT_FOUND`.
>
> Ninguna de ellas se reconstruye ni se rellena.
>
> **20.7 Estados.** Un valor solo es utilizable como INFERRED; NOT_FOUND e
> INVALID se representan según §6–§7, y la ausencia de contexto exigido nunca
> produce una observación utilizable, solo un diagnóstico que conserva los
> valores crudos. Una celda de valor vacía en una columna de demanda declarada
> es una *evaluación declarada sin evidencia* (§6). Se registra como NOT_FOUND
> con evidence "declared demand column present; value cell empty" solo cuando
> el contexto temporal declarado es válido (§7). Si no, se registra únicamente
> como diagnóstico.
>
> **20.8 §16–§19 ampliados para este alcance.**
> - De §16, "persistencia o serialización" e "integración con importador,
>   snapshots, API" quedan resueltos solo para 20.2–20.6.
> - §17 (alcance limitado a `market_evidence.py` y sus tests), §18 criterio 15
>   ("no modificar persistencia, importación o scoring") y §19 ("no se modifican
>   frontend-next/") quedan ampliados únicamente para el plan de implementación
>   de ADR-052 §4.
> - Scoring y proyección siguen excluidos.
>
> **20.9 Instante de captura y reproducción.** La validez de `observed_at` se
> evalúa contra el instante efectivo de la importación, que se guarda como
> `retrieved_at` en cada valor y como `captured_at` en el documento. Una lectura
> posterior reproduce el documento guardado tal cual y nunca lo vuelve a
> validar contra el reloj actual. Importar el mismo archivo otra vez es una
> **nueva** captura con su propio `captured_at`; su resultado puede diferir, por
> ejemplo cuando una fila tenía `observed_at` futuro, y no reemplaza al
> histórico.

## 3. Contrato D7-B

### 3.1 Columnas (encabezado normalizado por `normalize_header`)

| Columna canónica | Alias | Contenido |
|---|---|---|
| `demand_estimated_sales` | `estimated_monthly_sales`, `estimated_sales` | entero ≥ 0 (el valor) |
| `demand_window_start` | — | instante de inicio de la ventana |
| `demand_window_end` | — | instante de fin (excluido) |
| `demand_month` | — | `AAAA-MM`, un mes natural declarado (texto) |
| `demand_observed_at` | — | instante al que corresponde la observación |
| `demand_timezone` | — | zona IANA (`America/New_York`), `UTC` o desfase fijo `±HH:MM` |
| `demand_population` | — | texto no vacío, ≤ 500 caracteres |
| `demand_method` | — | texto no vacío, ≤ 500 caracteres |

- **`monthly_sales` no es alias en v1 (E10).** Ese encabezado sigue siendo
  `UNKNOWN`, igual que hoy.
- El alias `estimated_monthly_sales` nombra la columna valor, pero "monthly" no
  define ninguna ventana.
- Un archivo activa la captura si contiene al menos una columna del grupo. Sin
  ninguna, el registro queda `NOT_DECLARED` y la importación es idéntica a la de
  hoy.

### 3.2 Ventana temporal

Hay dos formas excluyentes de declararla:

1. **Explícita:** `demand_window_start` y `demand_window_end`, ventana semiabierta
   `[start, end)`.
2. **Mes natural (E11):** `demand_month` + `demand_timezone` obligatoria. Equivale
   a `[día 1 00:00, día 1 del mes siguiente 00:00)` en esa zona.

Si una fila declara a la vez `demand_month` y algún extremo explícito, se marca
`DEMAND_WINDOW_CONFLICT` y no hay observación utilizable. `demand_observed_at`
es siempre obligatorio y nunca se deduce de la ventana. Se exige
`start < end ≤ observed_at ≤ captured_at`.

### 3.3 Instantes y zona horaria (E9)

- **Valor con desfase** (texto ISO 8601 con `±HH:MM` o `Z`): se usa tal cual.
  Si además hay `demand_timezone` y su desfase en ese instante difiere,
  `DEMAND_TIMEZONE_CONFLICT`.
- **Valor sin zona** (celda de fecha de Excel o texto sin desfase): exige
  `demand_timezone`. Sin ella, `DEMAND_TIME_NAIVE`.
- **Hora local que no existe** (salto de horario de verano):
  `DEMAND_TIME_NONEXISTENT`.
- **Hora local ambigua** (repetida al volver al horario estándar):
  `DEMAND_TIME_AMBIGUOUS`. Nunca se elige un `fold` en silencio.
- **Zona desconocida:** `DEMAND_TIMEZONE_INVALID`.
- **Texto no interpretable:** `DEMAND_CONTEXT_INVALID`.

Los instantes se guardan en ISO 8601 con el desfase efectivo, y la zona
declarada se guarda aparte (`declared_timezone`).

### 3.4 Valor

- Entero ≥ 0:
  - `int` que no sea `bool`;
  - número de celda con valor entero exacto;
  - texto de solo dígitos.
- Se rechazan decimales (`"1.5"`, `420.5`), negativos, booleanos y texto:
  `INVALID`, con `raw_value`.
- No se trunca ni se redondea. Un `0` válido es una declaración de cero, no
  ausencia.

### 3.5 Resultado por fila

| Valor | Contexto válido | Contexto no válido o incompleto |
|---|---|---|
| Válido | observación INFERRED, `units` | sin observación; `DEMAND_VALUE_NOT_USABLE` con el crudo + diagnósticos de contexto |
| Vacío | observación NOT_FOUND (valor `None`) | `DEMAND_VALUE_EMPTY` + diagnósticos de los contextos presentes pero inválidos |
| No válido | observación INVALID con crudo + `DEMAND_VALUE_INVALID` | `DEMAND_VALUE_INVALID` con crudo + diagnósticos de contexto |

- **Diagnósticos de contexto:** `DEMAND_CONTEXT_MISSING` (falta ventana,
  `observed_at`, población o método), `DEMAND_CONTEXT_INVALID`,
  `DEMAND_WINDOW_CONFLICT` y los de §3.3.
- **Efecto en la fila:** la fila se procesa con normalidad para el resto de sus
  campos. Cada diagnóstico se añade también como `ProcessingIssue` WARNING;
  ninguno afecta a la decisión.
- **Filas descartadas:** una fila que el importer descarta (sin `record_ref`) no
  tiene captura.

### 3.6 Procedencia (E6 corregida)

El archivo lo entrega quien llama a la API o a la CLI. Quién elaboró la
estimación **no está acreditado**, así que no se usa `SUPPLIER_FILE`.

- `source` = nombre del archivo; `source_type` = `USER_INPUT`.
- `source_reference` = `row=N;column=<encabezado original>`.
- `method` = el `demand_method` declarado.
- `evidence` = "declared in uploaded file; author not accredited; not verified".
- `retrieved_at` = `captured_at`.

Nunca se pone VERIFIED. Un futuro `demand_declared_by` necesitaría un medio de
acreditación propio; no forma parte de v1.

### 3.7 Identidad, orden y duplicados

- **Identidad:** `observation_id` = `<record_ref>#ESTIMATED_SALES#1`, único
  dentro del run; junto con `execution_id` da la identidad global.
- **Orden determinista:**
  - observaciones por `observation_id`;
  - diagnósticos en el orden fijo de evaluación: valor, ventana o mes,
    `observed_at`, zona, población, método.
- **Encabezados duplicados:** si dos columnas resuelven al mismo canónico (por
  ejemplo `demand_estimated_sales` y `estimated_monthly_sales`), se usa la
  primera y la segunda se informa con `DUPLICATE_COLUMN`, regla ya existente en
  el importer.
- **Población:** se guarda tal como se declaró, sin espacios sobrantes en los
  extremos. No se compara entre filas ni entre archivos, ni se infiere su
  equivalencia.

### 3.8 Snapshot

```json
"demand_evidence": {
  "format": "juval.adr046.demand-evidence", "version": 1,
  "captured_at": "2026-10-26T15:00:00+00:00",
  "observations": [{
    "observation_id": "row_7:SKU-1#ESTIMATED_SALES#1", "metric": "ESTIMATED_SALES",
    "value": {"value": 420, "status": "INFERRED", "unit": "units", "raw_value": null,
              "provenance": {"source": "...", "source_type": "USER_INPUT", "verification_status": "INFERRED",
                             "retrieved_at": "...", "method": "...", "evidence": "...", "source_reference": "row=7;column=..."}},
    "observed_at": "...", "window": {"start": "...", "end": "..."},
    "window_source": "EXPLICIT", "declared_month": null, "declared_timezone": null,
    "population_definition": "..."
  }],
  "diagnostics": [{"code": "...", "column": "...", "row": 7, "raw_value": "...", "message": "..."}]
}
```

- `window_source` vale `EXPLICIT` o `DECLARED_MONTH`.
- `demand_evidence: null` indica `NOT_DECLARED`; la clave ausente, `NOT_CAPTURED`.
- No hace falta migración: es una clave JSON del snapshot.

### 3.9 API, export e interfaz

- **API:** `RecordOut` añade dos campos:
  - `demand_evidence`, el documento tal cual;
  - `demand_evidence_state`: `DECLARED` | `NOT_DECLARED` | `NOT_CAPTURED`.

  Ningún filtro, orden ni agregado nuevo; `/analytics` no cambia.
- **Export:**
  - el filtrado y el download del run añaden `demand_declared_units`,
    `demand_status`, `demand_window_start`, `demand_window_end`,
    `demand_observed_at`, `demand_population`, `demand_method`,
    `demand_source_reference`, `demand_diagnostics` y `demand_evidence_state`;
  - un valor ausente sale vacío, nunca 0;
  - los diagnósticos se exportan por código, y el valor crudo de un INVALID se
    exporta.
- **Interfaz (frontend-next):**
  - Product Detail: panel "Declared demand — not used for this decision";
  - Catálogo: columna informativa sin orden ni filtro;
  - Preview: grupo `declared_demand`.

  La decisión del motor no cambia en ningún sitio.

## 4. Plan de implementación (autorizado por esta aceptación)

| # | Archivo | Cambio |
|---|---|---|
| 1 | `domain/declared_demand.py` (nuevo) | `DeclaredDemandCapture` y `DemandDiagnostic` |
| 2 | `domain/sourcing_record.py` | `market_evidence: Optional[DeclaredDemandCapture] = None` |
| 3 | `infrastructure/excel/column_mapping.py` | `DEMAND_EVIDENCE_COLUMN_SPECS` |
| 4 | `infrastructure/excel/demand_capture.py` (nuevo) + `importer.py` | captura por fila |
| 5 | `application/demand_evidence.py` (nuevo) | serialización v1 y estado |
| 6 | `application/record_snapshot.py`, `application/import_preview.py` | clave del snapshot y grupo de preview |
| 7 | `interfaces/api/models.py`, `interfaces/api/service.py`, `interfaces/api/main.py`, `infrastructure/excel/exporter.py` | API y exports |
| 8 | frontend-next | tipos, Product Detail, Catálogo, Preview |
| 9 | documentación | `EXCEL_PROCESSING.md`, `API_CONTRACT.md` |

**No se tocan** `domain/product.py`, `domain/decision.py`,
`domain/market_evidence.py`, `processing/` ni ningún umbral.

## 5. Tests requeridos

Valor válido; cero; vacío; inválido; negativo; decimal; contexto incompleto;
ventana inválida; fecha sin zona; hora ambigua y hora inexistente por horario
de verano; mes natural declarado y en conflicto; población ausente; método
ausente; procedencia (`USER_INPUT`, `row/column`, `retrieved_at`); duplicados;
`monthly_sales` sigue `UNKNOWN`; snapshot histórico; API y export; paridad
SQLite/PostgreSQL desechable; preview; frontend-next; y el obligatorio: un
archivo con 1.000.000 unidades declaradas sigue en REVIEW con
`["DEMAND_UNKNOWN"]` bajo umbrales permisivos, idéntico al mismo archivo sin
columnas de demanda.

## 6. Condiciones para una futura política que use demanda en BUY

Ninguna está autorizada por este ADR:

- ADR de proyección aprobado;
- fuentes aceptables y su acreditación;
- duración máxima de la ventana y antigüedad máxima de `observed_at`;
- población a nivel de listing completo;
- equivalencia con `minimum_estimated_monthly_sales` sin suponer días;
- versión de política registrada (ADR-051);
- etiqueta visible del BUY resultante.

## 7. Riesgos

- **Contexto obligatorio:** exigirlo produce muchos diagnósticos.
- **Datos de zonas horarias:** `zoneinfo` depende de la base IANA del sistema.
- **Declaraciones no verificables:** la población y el método son declaraciones
  y no se verifican.
- **Validez dependiente del reloj:** queda explicitada en 20.9.
