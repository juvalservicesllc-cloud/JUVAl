# Juval — Data Sources (Fase 1)

## 1. Taxonomía de fuentes (`SourceType`, `domain/provenance.py`)

| SourceType | Significado | Ejemplos de uso en Juval |
|---|---|---|
| `USER_INPUT` | El usuario lo escribió directamente (formulario, config) | marketplace, costos configurados |
| `SUPPLIER_FILE` | Vino en el Excel/archivo del proveedor | SKU, UPC, título tal como lo declara el proveedor |
| `OFFICIAL_API` | API oficial/autorizada de Amazon o del proveedor (ej. SP-API) | título, categoría, dimensiones cuando la API lo expone |
| `AUTHORIZED_EXTERNAL_SOURCE` | Fuente externa con acceso autorizado explícitamente (API de terceros con licencia/ToS aceptados) | BSR, Buy Box histórico, conteo de ofertas |
| `DATABASE` | Ya estaba persistido en la base de datos de Juval de una corrida previa | reutilización de un valor verificado recientemente |
| `CALCULATED` | Derivado determinísticamente por código de Juval | profit, ROI, margin, break-even, volumen |
| `INFERRED` | Derivado por una regla/heurística, no un cálculo exacto | hazmat por categoría+keyword, estimación de ventas |
| `AI_ANALYSIS` | Producido por la capa de IA | resúmenes, explicaciones — **nunca** un valor numérico de negocio (ver ADR-008) |
| `NOT_FOUND` | No se encontró un dato útil después de una consulta o validación aplicable | resultado explícito de una fuente consultada; no representa un fallo operacional |

`SourceType` responde "¿dónde se buscó?"; `VerificationStatus` responde
"¿qué se obtuvo?". Son ejes independientes — ver `domain/provenance.py`
docstring de `SourceType` para el ejemplo canónico
(`OFFICIAL_API` + `NOT_FOUND` = "se consultó la API, no había match").

## 1b. Política transversal de adquisición

Prioridad de fuentes, en orden: (1) API/fuente oficial, (2) fuente pública
estructurada y legítima, (3) proveedor comercial con licencia, (4) dato
derivado internamente de inputs trazables. `docs/DATA_ACQUISITION_MATRIX.md`
es la fuente de verdad campo por campo y de los hechos de cada proveedor.

Un dato de proveedor y un dato Amazon no son sinónimos. Por ejemplo, peso
de paquete declarado por proveedor y peso de paquete de catálogo Amazon se
retienen como hechos distintos, con su propia provenance; no se sobrescribe
uno con el otro. La misma regla aplica a dimensiones, título, marca,
categoría, precio y HazMat. Una divergencia se registra y se resuelve por
contexto aprobado posteriormente, nunca por una precedencia universal oculta.

Fallos operacionales no son resultados de negocio: 429 es throttling, 5xx y
timeout son fallos de fuente/retry, auth es fallo de configuración/autorización
y una respuesta malformada es fallo de esquema. Ninguno debe producir
`NOT_FOUND`. La política por proveedor+operación, batch, rate header, retry y
coste vive en `DATA_ACQUISITION_MATRIX.md`.

## 2. Regla dura del proyecto: sin scraping ni evasión

Explícitamente prohibido en esta fase y en las siguientes salvo aprobación
explícita y documentada:

- Scraping no autorizado de Amazon o de terceros.
- Bypass o evasión de autenticación, CAPTCHAs, rate limits o cualquier
  control de acceso de un servicio externo.
- Extracción de datos privados o de acceso restringido sin autorización.

Fuentes de datos externos aceptables: APIs oficiales/autorizadas (ej.
Amazon SP-API, proveedores de datos con licencia como Keepa si se aprueba
explícitamente), archivos proporcionados por el usuario/proveedor, datos
públicos permitidos por los términos de servicio correspondientes. Ninguna
integración externa concreta se implementó en esta fase (ver §5).

## 3. Excel como fuente (`SUPPLIER_FILE` / `USER_INPUT`)

El Excel de entrada es la fuente primaria de identificación y, con
frecuencia, de costos. **IMPLEMENTED** desde Fase 2:
`infrastructure/excel/importer.py::import_excel` produce `FieldValue`s
con `source_type=SUPPLIER_FILE` directamente desde las celdas del
archivo del usuario, con columnas identificadas por nombre (nunca por
posición) vía `column_mapping.py`. Ver
`docs/architecture/EXCEL_PROCESSING.md` para el contrato columna por
columna, y ADR-002 para la decisión de Excel como formato de
intercambio (no como modelo de dominio).

## 4. APIs y fuentes autorizadas (`OFFICIAL_API` / `AUTHORIZED_EXTERNAL_SOURCE`)

Ningún adapter concreto existe todavía (`infrastructure/enrichment/`
contiene solo el `README.md` de propósito, sin código — ver decisión
pendiente #2). Cuando se apruebe una fuente concreta, su adapter deberá:

1. Vivir en `infrastructure/enrichment/`, implementando un puerto definido
   por `processing/` (nunca al revés).
2. Producir `FieldValue`s con `source_type` correcto y `verification_status`
   honesto — una API que da un estimado no debe marcarse `VERIFIED`.
3. Registrar `retrieved_at` real (no la hora de inicio del batch) y, cuando
   la fuente lo permita, `source_reference` (ID de consulta/URL) para
   auditoría.
4. Nunca traducir un "no encontrado" de la fuente en un valor por defecto.
5. No resolver silenciosamente matches ambiguos: `AMBIGUOUS` es una decisión
   pendiente de modelo separada de `VerificationStatus`.

## 5. Estado de integraciones

| Fuente | Estado |
|---|---|
| Excel (proveedor) | **IMPLEMENTED** — `infrastructure/excel/importer.py`, única fuente de datos real hoy; 17 tests de integración |
| Amazon SP-API Catalog Items | **DOC VERIFIED / AUTH BLOCKED / LIVE VALIDATION BLOCKED** — requirements, Product Listing role y POC están documentados; no hay adapter ni credenciales configuradas |
| Fuente de datos de mercado (BSR/Buy Box histórico, tipo Keepa) | **NOT IMPLEMENTED** — pendiente de aprobación explícita, no asumida |
| Base de datos de persistencia de Juval | **IMPLEMENTED para ExecutionRun/records** (SQLite/Supabase según configuración); no es una fuente externa de Product Intelligence |

## 6. Requisitos de ejecución futura

El enriquecimiento externo debe ejecutarse en backend como trabajo asíncrono,
persistente, reanudable e idempotente por record/etapa. Debe ofrecer resultados
parciales, retry/backoff, prioridad, etapas condicionales, batch, monitor de
throughput y monitor de coste/uso. Esto no selecciona queue, worker ni
tecnología. La PWA observa/controla/prioriza/muestra progreso: no hace llamadas
al proveedor, no conserva la cola y no depende de permanecer abierta.
