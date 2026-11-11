# ADR-058 — Registro de fuentes y resultados de adquisición por ExecutionRun

- Estado: **Aceptada** (2026-11-11). El propietario aprobó la revisión 2
  como contrato arquitectónico.
  - PD-1 a PD-7 quedan aprobadas.
  - **PD-8 sigue pendiente** (§9) y no autoriza ningún cambio en
    `ExecutionRun.status`.
- Implementación: **IMPLEMENTED en el código local (2026-11-11)** por
  instrucción expresa del propietario, que adelantó PD-3. No existe ningún
  conector de proveedor, transporte HTTP real ni credencial. La migración
  PostgreSQL está redactada y **no aplicada** a ninguna base real. API y UI
  sin cambios (PD-4). Detalle en §16.
- Origen: ADR-057 D5 (diferida a este ADR). Auditoría de persistencia y
  provenance del 2026-11-11.
- Relacionados, sin modificarlos: ADR-003, ADR-004, ADR-012, ADR-013,
  ADR-017, ADR-019, ADR-046, ADR-047, ADR-048, ADR-050, ADR-051 (Propuesta),
  ADR-052, ADR-056, ADR-057; `DATA_SOURCES.md` §1b y §4;
  `DATA_ACQUISITION_MATRIX.md` §18; CLAUDE.md §15.

## 1. Contexto

`ExecutionRun` guarda identidad, `input_filename`, `input_hash`,
`application_version` y contadores. No guarda qué fuentes externas
intervinieron (CLAUDE.md §15). Hoy no hace falta, porque la única fuente es
el archivo de entrada, ya identificado por `input_hash`. Hará falta en cuanto
exista un conector externo (ADR-057).

Hechos medidos en el código (2026-11-11):

- Una corrida se persiste con **un único INSERT al final**, en la misma
  transacción que sus snapshots (`application/execution_run_store.py`). No
  existe una fila `RUNNING` persistida ni un estado de cancelación.
- Con `persist=false` no se persiste nada.
- El rol `juval_backend` solo tiene `SELECT` e `INSERT` sobre
  `execution_runs`, y por tanto ninguna política de `UPDATE` ni `DELETE`
  (ADR-048, migración `…000007`; ADR-056, migración `…000009`). Los permisos
  se conceden por tabla.
- Los listados de runs seleccionan columnas explícitas. SQLite añade columnas
  con `_add_missing_columns`.
- Cada `FieldValue` persistido conserva su provenance en dos lugares:
  - los snapshots de registro (`application/record_snapshot.py`, incluida
    `demand_evidence` de ADR-052);
  - los documentos financieros de ADR-047 (`execution_run_financial_records`).
- `processing/` solo lee `Provenance.source` en `validate_source`, para
  detectar marcadores de relleno (`data_quality.py`). Nunca lee `method`.
  El motor de decisión no lee `ProcessingIssue`.

## 2. Alcance

**Incluye:** fuentes de **adquisición externa**, es decir conectores
autorizados según ADR-057 con `source_type` ∈ {`OFFICIAL_API`,
`AUTHORIZED_EXTERNAL_SOURCE`}.

**Excluye:**

| Excluido | Por qué |
|---|---|
| `SUPPLIER_FILE` y `USER_INPUT` del archivo de entrada | Ya los identifica `input_hash` en `ExecutionRun` |
| `USER_INPUT` de la petición (p. ej. `source="juval-api"`, objetivos ADR-047) | Es configuración de la petición, no adquisición (ámbito de ADR-051) |
| `CALCULATED`, `INFERRED` | Valores derivados por JUVAl |
| `AI_ANALYSIS` | ADR-008 |
| `DATABASE` | Exige una política de caché no aprobada |
| `NOT_FOUND` como `source_type` | No hubo consulta a ninguna fuente |
| Políticas no aprobadas | Freshness/TTL, ambigüedad de match, precedencia o conflicto entre fuentes, presupuestos, prioridades, estado de la corrida ante fallos de adquisición (PD-8) |

## 3. Identidad y enlace con la provenance (PD-6)

- **`source_id`** = `<proveedor>/<operación>`, registrado en la ficha de
  `DATA_SOURCES.md` §4.
  - Contiene `/`, así que es disjunto de cualquier `input_filename`
    (`path.name` nunca contiene `/`).
  - Es único.
  - Nunca coincide con un marcador de `_PLACEHOLDER_SOURCES`.
- **Enlace de un valor con su fuente.** Todo `FieldValue` producido por un
  conector lleva `Provenance.source = source_id` y `source_type` ∈
  {`OFFICIAL_API`, `AUTHORIZED_EXTERNAL_SOURCE`}.
- **`Provenance.method` conserva su significado actual:** cómo se obtuvo,
  estimó, agregó o detectó el valor (ADR-046 §9; ADR-052 §3.6). No lleva
  identificadores de fuente ni hashes de contrato.
- **Versión del contrato.** Se resuelve por
  `(execution_id, source_id)` → entrada de `acquisition_configuration`
  (`contract_id`, `contract_sha256`, ADR-057 D3.2). Cada fuente usa un único
  contrato por corrida (P9).
- `Provenance` no se modifica.

## 4. Almacenamiento (PD-5)

Dos columnas opcionales nuevas en `execution_runs`. No se crea ninguna tabla.

| Columna | Tipo (SQLite / PostgreSQL) | Contenido |
|---|---|---|
| `acquisition_configuration` | `TEXT` nulo / `text` nulo | Documento `juval.adr058.acquisition-configuration` |
| `acquisition_execution` | `TEXT` nulo / `text` nulo | Documento `juval.adr058.acquisition-execution` |

**Reglas de almacenamiento:**

- **Ambas nulas o ambas presentes**, con un `CHECK` en las dos bases (P3).
- **Atomicidad.** Ambas se escriben en **el mismo INSERT** que la fila del
  run (P1). Nunca después, ni en otra sentencia, ni con un UPDATE.
- **Inmutabilidad.** La base de datos ya no concede UPDATE a `juval_backend`.
  El puerto `ExecutionRunStore` no ofrece rutas de actualización (P2).
- **Aislamiento por organización (ADR-056).** Las columnas heredan la
  política `juval_tenant_select`/`juval_tenant_insert` de su fila. No hace
  falta ninguna política ni permiso nuevo, y las 12 políticas que exige la
  migración `…000009` no cambian.
- **Listados.** No seleccionan estas columnas (P5). Se leen solo en la carga
  individual de un run.
- **Dominio.** `ExecutionRun` no cambia. Los documentos viajan junto al run
  como argumento del puerto, igual que los snapshots (`RunWrite` en batches).
- **Migraciones (cuando se implemente).**
  - PostgreSQL: un `ALTER TABLE … ADD COLUMN` nulo más el `CHECK`, con su
    `.down.sql`; se redacta y **no se aplica** a ninguna base real.
  - SQLite: `_add_missing_columns`.
  - Se actualiza el comentario de tabla que dice "mirrors ADR-013 exactly".

## 5. Documentos y serialización canónica

**Serialización común de ambos documentos:**

- JSON UTF-8 canónico, definido por este ADR:
  `json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False)`.
  Es más estricto que el texto de ADR-047, que usa `sort_keys=True` con los
  separadores por defecto; ADR-047 no se modifica. Leer y volver a serializar
  produce los mismos bytes.
- Instantes en ISO 8601 con desfase.
- Contadores como enteros ≥ 0.
- Cada documento declara `format` y `version`. Al leer:
  - un formato o una versión desconocidos son un error, nunca una
    reinterpretación (P4);
  - una versión nueva exige un ADR o una enmienda.
- **Lista blanca de campos.** Solo identificadores, hashes, enums, contadores
  e instantes. Nunca payloads, cuerpos, cabeceras, URLs con parámetros,
  valores de producto, valores de entorno, credenciales, identificadores de
  petición del proveedor (PD-2) ni mensajes de error crudos.

### 5.1 `juval.adr058.acquisition-configuration` v1

Se fija al iniciar la corrida, antes de la primera consulta.

```json
{"format": "juval.adr058.acquisition-configuration", "version": 1,
 "captured_at": "2026-11-11T10:00:00+00:00",
 "sources": [{"source_id": "<proveedor>/<operación>",
              "source_type": "OFFICIAL_API",
              "contract_id": "<ADR-057 D3.2>",
              "contract_sha256": "<64 hex>",
              "enabled_by": "ENV_FLAG"}]}
```

`sources` vacío es un estado válido y distinto de `NOT_RECORDED`: significa
que la corrida se registró sin fuentes externas configuradas.

### 5.2 `juval.adr058.acquisition-execution` v1

Se cierra al terminar la corrida y se escribe en el INSERT final.

```json
{"format": "juval.adr058.acquisition-execution", "version": 1,
 "sources": [{"source_id": "<proveedor>/<operación>",
              "first_request_at": "...", "last_request_at": "...",
              "requests_sent": 0, "retries": 0,
              "items": {"requested": 0, "with_evidence": 0, "no_evidence": 0, "rejected": 0,
                        "failed": {"THROTTLED": 0, "SOURCE_FAILURE": 0,
                                   "AUTH_OR_CONFIGURATION": 0, "SCHEMA_FAILURE": 0}},
              "values": {"used": 0, "not_found": 0, "invalid": 0},
              "observation_contract_rejected": 0,
              "not_consulted_reason": null}]}
```

- Hay **una entrada por cada fuente configurada**, se haya consultado o no.
- `not_consulted_reason` es un enum cerrado v1:
  - `RUN_FAILED_BEFORE_ACQUISITION`;
  - `NO_ELIGIBLE_RECORDS`: ningún registro tenía el identificador que la
    operación exige según su contrato;
  - `null` si la fuente se consultó.
- Un motivo nuevo exige el ADR de la política que lo justifique.

## 6. Categorías

| Categoría | Definición | Origen del dato |
|---|---|---|
| Configurada | Aparece en `acquisition_configuration` | Configuración al iniciar |
| Consultada | `items.requested` > 0 | Contado por el adapter |
| Utilizada | `values.used` > 0: valores persistidos `VERIFIED`/`INFERRED` atribuidos a la fuente | **Derivado** (§7) |
| Resultado rechazado | Respuesta estructuralmente válida con un valor no aceptado: `values.invalid` (ADR-004; ADR-046 §6), derivado, más `observation_contract_rejected` (observación ADR-046 imposible por contexto obligatorio ausente), contado por el adapter | Mixto |
| Fallo operacional | 429, 5xx/timeout, auth/configuración y esquema (`DATA_SOURCES.md` §1b; ADR-057 D4). **Nunca produce `NOT_FOUND`**: el campo queda en ausencia estructural (ADR-046 §6) | Contado por el adapter |
| Ausencia legítima | Consulta con éxito sin dato: `FieldValue` `NOT_FOUND` con provenance de la fuente, en `values.not_found` | Derivado |

**Resultado por ítem consultado.** Cada ítem tiene exactamente uno, por esta
precedencia:

1. `FAILED:<categoría>` si no hubo respuesta utilizable;
2. si no, `WITH_EVIDENCE` si produjo al menos un valor `VERIFIED`/`INFERRED`;
3. si no, `REJECTED` si produjo al menos un rechazo;
4. si no, `NO_EVIDENCE`.

Los contadores de ítems (`items.*`) y los de valores (`values.*`) son ejes
distintos y no se suman entre sí.

## 7. Derivación desde la provenance persistida

- **Ámbito.** Todos los `FieldValue` persistidos de la corrida:
  - los campos de cada snapshot de registro;
  - `demand_evidence` (ADR-052);
  - los documentos financieros de ADR-047 de esa corrida.
- **Atribución.** Un valor se atribuye a la fuente S si
  `provenance.source == S.source_id` y su `source_type` es externo (§2).
  Cualquier otro valor queda fuera del registro.
- **Cálculo.** Los contadores derivados (`values.*`) se calculan al cerrar la
  corrida, sobre exactamente los snapshots y documentos que se van a escribir
  en esa misma transacción. Se guardan en `acquisition_execution`.
- **Consistencia.** El recálculo sobre lo persistido debe coincidir con lo
  guardado (P7). El adapter nunca declara la utilización por su cuenta.

## 8. Comportamiento ante fallos, reintentos y batches

Principio: **el registro v1 solo documenta corridas persistidas. No es un
registro de intentos.** Una transacción final no puede conservar eventos de
una ejecución que no llega a persistirse.

Límites conocidos de v1:

- **`SUCCESS` y `PARTIAL_SUCCESS` se refieren al procesamiento de los
  registros, no a la adquisición externa.** Una corrida `SUCCESS` puede haber
  tenido fallos de adquisición, incluso que fallaran todas las peticiones a
  una fuente. Esos fallos solo constan en los contadores de
  `acquisition_execution`. Mientras PD-8 siga pendiente, `ExecutionRun.status`
  no cambia de semántica.
- **Una corrida que aborta antes del INSERT final no deja registro.** No
  quedan ni el run ni los documentos, ni constancia auditable de las
  consultas ya enviadas al proveedor.
- **Con el endpoint actual, los batches pueden quedar persistidos
  parcialmente.** `POST /api/v1/batches` guarda hijo por hijo. La ruta
  atómica de ADR-050 existe, pero no está conectada.
- **Reintentos e idempotencia.**
  - Los reintentos dentro de una corrida solo se cuentan (`retries`).
  - Un reenvío del cliente crea otra corrida, que puede volver a consumir el
    proveedor.
  - La idempotencia de ADR-050 D5 sigue diferida. Las corridas solo se
    relacionan por `input_hash`.

| Caso | Comportamiento actual de JUVAl | Registro ADR-058 |
|---|---|---|
| `SUCCESS` | Run y snapshots en un INSERT final | Ambos documentos en el mismo INSERT: `RECORDED` |
| `PARTIAL_SUCCESS` | Igual; el estado refleja registros con `RECORD_ERROR` | Igual que `SUCCESS`. Los fallos de adquisición **no** cambian el estado (PD-8 pendiente) |
| `FAILED` persistido (import fatal o 0 registros procesados) | Se persiste el run sin registros | `RECORDED`. Las fuentes no consultadas llevan `RUN_FAILED_BEFORE_ACQUISITION`; las consultadas antes del fallo conservan sus contadores |
| Aborto antes de persistir (excepción, proceso terminado, desconexión) | No se persiste nada | **Nada.** No hay run ni registro. Las llamadas al proveedor ya hechas **no quedan en ningún registro auditable** (§11) |
| Error de base de datos en el INSERT final | Rollback completo; la API responde 500 genérico | Nada; equivale a un aborto. Nunca hay un run sin documentos ni documentos sin run (P1, P8) |
| `persist=false` | No se persiste nada | **PD-7:** los conectores externos no se ejecutan. Una corrida `persist=false` nunca consulta fuentes externas |
| Reintentos dentro de la corrida | — | Se cuentan en `retries`; cada ítem tiene un único resultado final |
| Reenvío del cliente | Corrida nueva con `execution_id` nuevo; la idempotencia de ADR-050 D5 sigue diferida | Registro nuevo e independiente. Las corridas solo se relacionan por `input_hash`. El consumo del proveedor puede duplicarse |
| Fallo de red de un ítem o petición | — | `FAILED:SOURCE_FAILURE` o `AUTH_OR_CONFIGURATION`; el campo queda en ausencia estructural y la corrida continúa. Si el fallo aborta la corrida, se aplica la fila "Aborto" |
| Batches | `save_batch_with_runs` (ADR-050) es atómico, **pero `POST /api/v1/batches` todavía guarda hijo por hijo** | Cada hijo sigue su propio INSERT. Con el endpoint actual, un fallo intermedio deja persistidos los hijos anteriores con su registro y ninguno de los posteriores. Si se conecta la ruta atómica, todo o nada |
| Cancelación | El estado **no existe** | No se introduce. Una cancelación se comporta como un aborto. `CANCELLED` o cualquier estado nuevo exige un ADR propio |

## 9. PD-8 — Estado ante fallos de adquisición (PENDIENTE)

Este ADR **no elige** una política. Hasta que se decida, `ExecutionRun.status`
mantiene su semántica actual y los fallos de adquisición constan solo en los
contadores de `acquisition_execution`.

Hechos que condicionan la elección:

- `status` hoy se deriva de los registros: `RECORD_ERROR` da
  `PARTIAL_SUCCESS`, y 0 registros o import fatal da `FAILED`
  (`run_pipeline.py`).
- La CLI trata `FAILED` como "import produced no usable records": sale con
  código 1 y no exporta.
- Los batches mapean `status` a `BatchFileStatus`, con ese mismo mensaje para
  `FAILED`.
- El motor de decisión no lee `ProcessingIssue`. Las observaciones externas
  no llegan a `DecisionInputs` sin un ADR de proyección (ADR-052 §20.3; I6).
  En v1, un fallo de adquisición no puede alterar BUY/REVIEW/PASS bajo
  ninguna de las alternativas. Lo que cambia entre ellas es la visibilidad,
  no la decisión.

| Criterio | A. `status` sin cambios + estado de adquisición independiente | B. Fallos de adquisición dentro de `status` | C1. Solo contadores, sin estado agregado | C2. `ProcessingIssue` WARNING por registro afectado |
|---|---|---|---|---|
| Qué cambia | Un campo enum (p. ej. `COMPLETE`/`DEGRADED`) en `acquisition_execution`, derivado de los contadores con un umbral a definir | `PARTIAL_SUCCESS` o `FAILED` también por adquisición | Nada más que §5.2 | Un código de issue nuevo por registro con algún ítem fallido |
| Compatibilidad | Total con `ExecutionRun`, CLI, batch y API | Cambia el significado de `PARTIAL_SUCCESS`/`FAILED`. Rompe el mensaje y el código de salida de la CLI y de los batches. Las corridas históricas dejan de ser comparables | Total | Usa un mecanismo existente. Aumenta `warnings` (contador aditivo); no toca `status` |
| Fallo parcial | Se distingue (`DEGRADED`), pero el umbral es una política nueva | `PARTIAL_SUCCESS` mezcla dos causas distintas; un `FAILED` por adquisición ocultaría resultados válidos | Solo visible para quien lea los contadores | Visible por registro, sin agregado de corrida |
| Experiencia del usuario | Invisible hasta que se decida la API/UI (PD-4) | Visible de inmediato, pero ambiguo | Invisible hasta PD-4 | Visible hoy en las issues existentes de cada registro |
| Decisiones económicas | Intactas | Intactas por registro, pero `FAILED` bloquearía el export en la CLI | Intactas | Intactas (el motor no lee issues) |
| Nueva política | Sí: umbral de degradación | Sí: redefinir estados | No | Sí, mínima: un código de issue |

Mientras PD-8 siga pendiente:

- no existe un estado agregado de adquisición;
- `ExecutionRun.status` conserva su semántica actual;
- los fallos solo constan en los contadores de §5.2.

Esto no constituye una elección entre A, B, C1 o C2.

## 10. Decisiones

| ID | Decisión | Estado |
|---|---|---|
| PD-1 | Solo agregados por corrida en v1 | **APROBADA** |
| PD-2 | Sin identificadores externos de petición | **APROBADA** |
| PD-3 | Implementación junto al primer conector autorizado | **APROBADA** |
| PD-4 | API y UI fuera del alcance | **APROBADA** |
| PD-5 | Dos columnas opcionales en `execution_runs`, sin tabla nueva (§4) | **APROBADA** |
| PD-6 | Enlace por `Provenance.source` y configuración de la corrida, sin modificar `Provenance.method` (§3) | **APROBADA** |
| PD-7 | Prohibir conectores externos en corridas `persist=false` (§8) | **APROBADA** |
| PD-8 | Política de estado ante fallos de adquisición (§9) | **PENDIENTE** |

## 11. Invariantes

### Persistencia

| # | Invariante |
|---|---|
| P1 | Ambos documentos se escriben en el mismo INSERT que la fila del run; nunca en otra sentencia ni transacción |
| P2 | Ninguna ruta del puerto actualiza los documentos ni la fila; la base de datos no concede UPDATE |
| P3 | Ambas columnas nulas ⇔ `NOT_RECORDED`; una sola nula es inválido (`CHECK`) |
| P4 | `format` y `version` se validan al leer; una versión desconocida es un error, no se reinterpreta |
| P5 | Los listados nunca seleccionan las columnas de documentos |
| P6 | Todo valor persistido con `source_type` externo se atribuye a una fuente de `acquisition_configuration`; uno no atribuible es un error de integridad |
| P7 | Los contadores derivados (`values.*`) coinciden con su recálculo sobre los snapshots y documentos ADR-047 persistidos de la misma corrida |
| P8 | Una corrida no persistida (abortada, revertida o `persist=false`) no genera ningún registro, y el sistema no afirma nada sobre ella |
| P9 | Cada `source_id` usa un único contrato (`contract_sha256`) por corrida |
| P10 | `source_id` contiene `/`, es único y no coincide con ningún marcador de `_PLACEHOLDER_SOURCES` |

### Contenido

| # | Invariante |
|---|---|
| I1 | Fuentes en `acquisition_execution` = fuentes en `acquisition_configuration` (una entrada por fuente configurada) |
| I2 | `items.requested` = `with_evidence` + `no_evidence` + `rejected` + Σ`failed` |
| I3 | `requests_sent` ≥ 1 ⇔ `items.requested` > 0; `retries` no se suman a `requests_sent`; `not_consulted_reason` ≠ `null` ⇔ `items.requested` = 0 |
| I4 | `items.with_evidence` > 0 ⇔ `values.used` > 0; `items.no_evidence` > 0 ⇒ `values.not_found` > 0 |
| I5 | Ningún `FieldValue` atribuido a una fuente es `NOT_FOUND` para un ítem contado como fallo |
| I6 | Las observaciones nunca se proyectan a `Product` ni a `DecisionInputs`; `processing/` no lee estos documentos (ADR-052 §20.3–20.4) |
| I7 | Ninguna corrida `persist=false` tiene fuentes consultadas (PD-7) |

## 12. Volumen y escalabilidad

- **Tamaño de los documentos:** O(fuentes × categorías). Con 8 operaciones
  configuradas son unos pocos KB por run, con independencia del número de
  registros.
- **Coste del cálculo derivado:** O(registros × campos), una sola vez al
  cerrar la corrida y en memoria.
- **Lecturas:** solo en la carga individual de un run, nunca en listados.
- **Límite de v1 (PD-1):** sin detalle por registro, el registro no explica la
  causa de una ausencia concreta. Si en una versión futura hace falta ese
  detalle, la decisión de almacenamiento se revisa (probablemente con una
  tabla) mediante un ADR nuevo.

## 13. Pruebas previstas (al implementar, PD-3)

- **Corrida sin conectores tras la activación:** `sources` vacío y `RECORDED`.
  **Corrida histórica:** `NOT_RECORDED`.
- **P1, P3, P8:**
  - un INSERT con una sola columna rellena se rechaza en SQLite y en
    PostgreSQL desechable;
  - un rollback no deja ni run ni documentos.
- **P2:** el puerto no tiene método de actualización; `juval_backend` no
  puede hacer UPDATE (lab PostgreSQL de ADR-048/056).
- **Aislamiento:** otra organización no puede leer las columnas.
- **P4:** un formato o una versión desconocidos fallan al leer.
- **P5:** los listados no devuelven las columnas.
- **P6, P7:** recálculo sobre los snapshots y documentos ADR-047 persistidos;
  un valor externo con un `source` desconocido falla.
- **I1–I5:**
  - con dobles de transporte en `tests/` (ADR-057 §3.1), cada categoría de
    fallo incrementa su contador;
  - no aparece ningún `NOT_FOUND`;
  - los ítems con mezcla de resultados siguen la precedencia de §6.
- **I6:** el mismo archivo con y sin registro produce decisiones y razones
  idénticas.
- **I7:** una corrida `persist=false` no invoca ningún adapter.
- **Sin secretos:** test de lista blanca, más `tools/compliance_check.py`. Un
  valor de entorno plantado no aparece en ningún documento.
- **Batch:** con el endpoint actual hijo por hijo y con la ruta atómica de
  ADR-050.

## 14. Compatibilidad

| ADR | Relación |
|---|---|
| ADR-046 | Sin cambios en las observaciones; distingue ausencia estructural y `NOT_FOUND` (§6); `method` conserva su significado (§9); sin adapters ficticios (§15) |
| ADR-047 | Sus documentos son ámbito de la derivación, solo lectura; no cambian formato ni tabla |
| ADR-048 | Sin permisos nuevos: las columnas quedan cubiertas por los permisos de tabla existentes; sigue sin UPDATE |
| ADR-050 | Los documentos viajan en `RunWrite` dentro de la transacción única. Se documenta que el endpoint actual no es atómico |
| ADR-051 (Propuesta) | Independiente: no mezcla configuración de decisión y de adquisición. Si ADR-051 se aprueba con una tabla propia, la diferencia de almacenamiento se revisa entonces |
| ADR-052 | La demanda declarada (`USER_INPUT` del archivo) queda fuera del registro; nada se proyecta al motor |
| ADR-056 | Aislamiento heredado de la fila del run; las 12 políticas no cambian |
| ADR-057 | Cumple D5; usa `contract_id`/`sha256` de D3.2; las pruebas siguen D2 y §3.1 |

## 15. Riesgos

- **Abortos sin traza.** Una corrida que consulta un proveedor y aborta antes
  del INSERT no deja registro del consumo. Resolverlo exige un registro de
  intentos previo al commit (`DATA_ACQUISITION_MATRIX.md` §18), es decir otra
  arquitectura que no está aprobada.
- **Batch no atómico** en el endpoint actual: registros completos de algunos
  hijos y de otros no.
- **PD-8 pendiente:** una caída total de un proveedor puede acabar en
  `SUCCESS`.
- **Convención de `source` incumplida por un adapter:** rompería la
  atribución. La mitigan P6 y P7.
- **Tiempos de la corrida:** `run_pipeline` usa un mismo `now` para
  `started_at` y `finished_at`. Solo `first/last_request_at` aportan tiempos
  reales.
- **Migración no aplicada a bases reales:** requiere la acción del operador.

## 16. Notas de implementación (2026-11-11)

| Pieza | Archivo |
|---|---|
| Value objects e invariantes I1–I4, P9, P10 | `src/juval/domain/acquisition.py` |
| Documentos canónicos v1, `NOT_RECORDED`, derivación §7, P3, P4, P6, P7 | `src/juval/application/acquisition_documents.py` |
| Orquestación: pipeline sin cambios, adquisición posterior, INSERT único, PD-7 | `src/juval/application/acquisition_run.py` |
| Puerto `AuthorizedConnector` (definido en `processing/`, nunca invocado allí) | `src/juval/processing/acquisition_port.py` |
| Maquinaria reutilizable de ADR-057 (contrato D3.2/D3.3, validación, errores, reintentos) | `src/juval/infrastructure/enrichment/connector.py` |
| Columnas, `CHECK`, escritura y `load_acquisition` | stores SQLite y PostgreSQL, puerto `ExecutionRunStore`, `RunWrite`, `BatchChild` |
| Migración y rollback, **no aplicados** | `supabase/migrations/20261111000010_execution_run_acquisition{,.down}.sql` |
| Pruebas (sintéticas, dobles de transporte solo en `tests/`) | `tests/unit/test_acquisition_{documents,connector,boundaries}.py`, `tests/integration/test_acquisition_run.py`, `tests/integration/test_postgres_acquisition.py` |

Decisiones tomadas al implementar, que requieren ratificación del propietario:

- **Clave de snapshot `acquired_evidence`.** Documento
  `juval.adr058.acquired-evidence` v1 por registro, con los `FieldValue`
  adquiridos y su provenance. Es la única forma de que §7 derive la
  utilización desde lo persistido. Es informativa, igual que `demand_evidence`
  (ADR-052): no se proyecta a `Product` ni a `DecisionInputs`, y la API la
  ignora (PD-4). No requiere migración.
- **`load_acquisition`.** Distingue los tres casos: `None` es `NOT_RECORDED`,
  un run inexistente lanza `LookupError` y uno fuera de alcance,
  `OutOfScopeError`. En PostgreSQL sin la migración lanza
  `AcquisitionStorageUnavailable`, nunca `NOT_RECORDED`.
- **Escritura en PostgreSQL.** Las columnas solo se nombran en el INSERT
  cuando hay registro, así que una base sin la migración sigue aceptando
  corridas sin adquisición.
- **Clasificación de estados HTTP.** Cualquier estado no 2xx distinto de
  401/403/429/5xx es `SCHEMA_FAILURE`, salvo los que el contrato declare como
  respuesta válida (`handled_statuses`).
- **Reintentos.** Solo para `THROTTLED` y `SOURCE_FAILURE`, acotados por
  `RetryPolicy`. La espera es `Retry-After` en segundos si existe, y si no un
  backoff exponencial con tope, mediante un `sleep` inyectado.

**Ratificación del propietario (2026-11-11).** Se ratifican:

1. `acquired_evidence` como campo informativo de los snapshots, sin efecto en
   BUY/REVIEW/PASS. Lo verifican
   `test_decisions_and_existing_snapshot_fields_are_identical_with_or_without_connectors`
   y `test_processing_and_the_decision_engine_never_read_acquisition`.
2. La implementación anticipada respecto de PD-3.
3. El contrato sintético, exclusivamente dentro de `tests/` (ADR-057 §3.1).

Las demás decisiones de este ADR no cambian. PD-8 sigue pendiente.

Fuera de esta implementación, por falta de autorización externa: adapter de
proveedor, transporte HTTP de producción, credenciales, habilitación por
entorno y el cableado en la API.
