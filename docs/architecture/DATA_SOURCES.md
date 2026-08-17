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
| `NOT_FOUND` | No se intentó ninguna fuente, o ninguna tuvo el dato | valor por defecto cuando no hay nada que declarar |

`SourceType` responde "¿dónde se buscó?"; `VerificationStatus` responde
"¿qué se obtuvo?". Son ejes independientes — ver `domain/provenance.py`
docstring de `SourceType` para el ejemplo canónico
(`OFFICIAL_API` + `NOT_FOUND` = "se consultó la API, no había match").

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

## 5. Estado de integraciones

| Fuente | Estado |
|---|---|
| Excel (proveedor) | **IMPLEMENTED** — `infrastructure/excel/importer.py`, única fuente de datos real hoy; 17 tests de integración |
| Amazon SP-API u otra API oficial | **NOT IMPLEMENTED** — pendiente de aprobación y credenciales |
| Fuente de datos de mercado (BSR/Buy Box histórico, tipo Keepa) | **NOT IMPLEMENTED** — pendiente de aprobación explícita, no asumida |
| Base de datos de persistencia de Juval | **NOT IMPLEMENTED** — pendiente decisión (Supabase `PENDING`, `CLAUDE.md` §14; ver `docs/architecture/TECHNOLOGY_DECISIONS.md`) |
