# ADR-053 — Precio sugerido del proveedor, declarado en el archivo (GOLDEN 17)

- Estado: **Aceptada con condiciones** (2026-10-27). La implementación de la
  captura informativa se apoya en instrucción explícita del usuario (unidad
  "GOLDEN 17: precio sugerido declarado"): S1–S4 y S7–S9 vienen de esa
  instrucción o se derivan de ella. Hay tres elementos que **no** tienen todavía
  ratificación del usuario y siguen PENDING:
  - la enmienda a ADR-046 §20.1 (abajo);
  - **S5** (el cero es inválido);
  - **S6** (no se convierten mayúsculas en la moneda).
- **Auditoría del 2026-10-27 (§7):** S2 se corrigió a `USER_INPUT`, y los valores
  crudos se conservan tal como llegaron.
- **Alcance:** solo evidencia **informativa**, es decir captura, snapshot, API,
  exports, preview y visualización. No autoriza usar el precio sugerido en
  `selling_price`, `cog`, cálculos financieros, `DecisionInputs`, umbrales ni
  scoring.
- **Enmienda acotada a ADR-046** (se lee como su §21). ADR-052 §20.1 dejó "los
  precios" sin ingestión ni persistencia. Esta enmienda autoriza una única
  excepción, el campo de §2, y nada más. `PriceObservation`, `PriceSeries` y las
  demás métricas siguen igual.
- Relacionados: ADR-002, ADR-003, ADR-004, ADR-011, ADR-019, ADR-026, ADR-029
  (GOLDEN 17), ADR-046, ADR-047, ADR-052.

## 1. Contexto

- **Qué hace Golden.** Muestra un "Suggested price" en Catalog y en Product
  Detail, importado del campo de precio sugerido del proveedor y etiquetado como
  `VERIFIED_SOURCE`. Producción no tiene ese campo (GOLDEN §18, ítem 17,
  `REQUIRES_BACKEND_CONTRACT`).
- **Por qué no es otro concepto existente.** Hay cinco conceptos y ninguno es
  equivalente:
  - `selling_price`: el precio que el motor usa para vender en Amazon (legacy).
  - `fin_selling_price_*`: el precio de venta declarado del flujo ADR-047.
  - `cost` / `cog`: lo que el comprador paga al proveedor.
  - `PriceKind.SUPPLIER_QUOTE` (ADR-046 §12): una cotización del proveedor, es
    decir, un coste.
  - **El precio sugerido del proveedor**: el precio de reventa que el proveedor
    recomienda. No es una oferta de Amazon, no es un coste y no garantiza nada.
  - Además, MSRP (del *fabricante*), `list_price` (el precio de lista de Amazon)
    y MAP (precio mínimo anunciado) son conceptos distintos.
- **Por qué no se modela como `PriceObservation`.** `PriceObservation` exige un
  `PriceKind` que signifique esto (no existe ninguno), además de `observed_at` y
  `price_basis`, que el archivo no declara. Representarlo así inventaría una
  equivalencia o un contexto. Por eso es un **atributo declarado** del registro,
  no una observación de mercado.

## 2. Decisión

Un componente propio de `SourcingRecord`, por composición (ADR-011) y fuera de
`Product`:

```
SourcingRecord.supplier_suggested_price: Optional[SupplierSuggestedPrice]
SupplierSuggestedPrice(amount: FieldValue[Decimal], currency_raw: str | None,
                       diagnostics: tuple[PriceDiagnostic, ...])
```

`processing/` no lo importa ni lo lee. Data quality, profitability, risk y
decision no cambian.

### Columnas (encabezado normalizado por `normalize_header`)

| Columna canónica | Alias | Contenido |
|---|---|---|
| `supplier_suggested_price` | — | importe decimal > 0, sin símbolo |
| `supplier_suggested_price_currency` | — | código de tres letras ASCII mayúsculas (`USD`) |

La captura se activa si el archivo contiene al menos una de las dos columnas. Si
no contiene ninguna, el registro queda `NOT_DECLARED` y la importación es
idéntica a la anterior.

## 3. Decisiones

- **S1 — Sin alias.** `suggested_price`, `msrp`, `list_price`, `rrp`, `srp`,
  `map` y `retail_price` siguen siendo `UNKNOWN_COLUMN`. Cada uno nombra un
  concepto distinto o deja ambiguo quién sugiere el precio.
- **S2 — Nunca VERIFIED.** Que el dato aparezca en el archivo no lo verifica. Un
  importe utilizable es **INFERRED**, con estos datos:
  - `source_type=USER_INPUT`, no `SUPPLIER_FILE`. El archivo lo entrega quien
    llama a la API o a la CLI, y nadie acredita quién escribió el precio
    (mismo criterio que ADR-052 §3.6). El nombre de la columna dice lo que el
    archivo *afirma*; no atribuye el dato al proveedor;
  - `method="declared_in_uploaded_file"`;
  - `evidence` que dice que el autor no está acreditado, que no está verificado
    y que no es precio de venta ni coste.

  El dominio rechaza VERIFIED en `__post_init__`.
- **S3 — Moneda explícita y nunca inferida.** `unit` del importe es la moneda
  declarada (convención de ADR-046 §12). Si falta o no tiene forma válida, el
  importe queda **INVALID** con su texto crudo, y la moneda cruda se conserva en
  `currency_raw`. Diagnósticos: `SUGGESTED_PRICE_CURRENCY_MISSING` o
  `SUGGESTED_PRICE_CURRENCY_INVALID`.
  - No se toma la moneda del marketplace ni de `fin_currency`, y no se convierte.
  - Igual que en ADR-046, se valida la forma del código, no su pertenencia a
    ISO 4217.
- **S4 — Decimal exacto.** Solo se acepta un decimal simple (signo opcional,
  dígitos y punto). El importe se guarda como `Decimal` de ese texto, sin
  redondear ni truncar.
  - Lo hacen INVALID (`SUGGESTED_PRICE_INVALID`), sin interpretarlos: un símbolo
    (`$24.99`), un separador de miles, `_`, un exponente, `NaN` o `Infinity`.
  - El único ajuste de lectura es ignorar los espacios de alrededor, igual que en
    el resto de columnas.
  - `raw_value`, `currency_raw` y los diagnósticos conservan la celda **tal como
    llegó**, con espacios incluidos.
- **S5 — Cero y negativos son INVALID** (`SUGGESTED_PRICE_NOT_POSITIVE`), con el
  texto crudo. Un precio sugerido de 0 casi siempre es un marcador de "sin
  precio", y mostrarlo como 0,00 induciría a error. ADR-046 §12 admite `>= 0`
  para observaciones de precio, pero aquí es más estricto porque es otro
  concepto. *Sujeto a revisión.*
- **S6 — Sin normalizar la moneda.** `usd` es INVALID, igual que en ADR-046. Así
  no hay reparación silenciosa. *Sujeto a revisión.*
- **S7 — Celda de importe vacía = NOT_FOUND**, sin diagnóstico, haya o no moneda.
  Nunca se convierte en 0.
- **S8 — Diagnósticos como WARNING.** Cada diagnóstico se registra también como
  `ProcessingIssue` WARNING del registro, con la columna original. Un precio
  sugerido inválido no convierte la fila en error ni cambia la decisión.
- **S9 — Provenance de fila y columna.** El registro guarda estos datos:
  - `source` = nombre del archivo;
  - `source_reference` = `row=<n>;column=<encabezado original>`;
  - `retrieved_at` = instante de la importación (no es un instante de
    observación, que el archivo no declara).

## 4. Persistencia, API y exports

- **Snapshot.** Clave `supplier_suggested_price`, que puede contener `null`
  (`NOT_DECLARED`) o el documento versionado
  `{format: "juval.supplier-suggested-price", version: 1, amount, currency_raw, diagnostics}`.
  `amount` tiene la forma `FieldValue` de todo snapshot. Si la clave no existe,
  el snapshot es anterior a este ADR (`NOT_CAPTURED`). Nada se reconstruye.
- **Almacenamiento.** El snapshot ya es JSON en SQLite y en Supabase (JSONB),
  así que no hace falta migración.
- **API.** `RecordOut.supplier_suggested_price` (el documento tal cual) y
  `supplier_suggested_price_state` (`DECLARED | NOT_DECLARED | NOT_CAPTURED`).
  No hay filtros, orden, agregación ni analítica. Ordenar mezclaría monedas, lo
  que sería una equivalencia inventada.
- **Exports.** El export filtrado del Catalog y la descarga del run añaden las
  mismas ocho columnas `supplier_suggested_price_*`:
  - estado, importe, moneda, estado de verificación, importe crudo, moneda cruda,
    referencia de origen y códigos de diagnóstico;
  - el importe va como **texto exacto**, nunca como float;
  - un valor ausente es una celda vacía.
- **Preview.** Las dos columnas aparecen en su propio grupo,
  `supplier_suggested_price`.

## 5. Consecuencias

- **Diferencias con Golden.**
  - Golden etiquetaba el precio `VERIFIED_SOURCE` y lo ordenaba. Aquí es
    INFERRED, siempre lleva la moneda declarada y no se ordena.
  - Golden lo leía de un adapter de West Marine. Aquí solo se lee de las dos
    columnas de §2, en `.xlsx` o `.csv` (ADR-026). No se añade ningún formato.
- **Uso en decisiones.** Usarlo en cualquier cálculo o decisión requiere un ADR
  propio.

## 6. Pruebas exigidas

- **Valores:** decimal válido, cero, negativo, texto, vacío, moneda explícita,
  moneda ausente y moneda inválida.
- **Provenance:** de fila y columna.
- **Compatibilidad:** snapshot histórico y que no haya alias.
- **Paridad:** entre API y los dos exports.
- **Invariante:** decisiones, motivos, profit y ROI idénticos con y sin las
  columnas, y `processing/` nunca lo importa.
- **Navegador:** E2E en Chromium sobre Catalog y Product Detail.

## 7. Auditoría del 2026-10-27

- **Origen del dato (corregido).** La versión inicial marcaba el importe como
  `SUPPLIER_FILE`, que atribuía al proveedor un dato cuya autoría no consta. Ahora
  es `USER_INPUT`, con evidencia "author not accredited". La UI ya no dice
  "declared by the supplier".
- **Crudo (corregido).** La versión inicial recortaba los espacios de
  `raw_value` y `currency_raw`. Ahora se conservan tal como llegaron.
- **Moneda contradictoria.** No se comparan monedas ni se elige entre ellas.
  - Un símbolo en el importe vuelve INVALID el importe.
  - Si la columna de moneda aparece dos veces, se usa la primera y la segunda
    produce un aviso `DUPLICATE_COLUMN` (regla general del importer).
  - Que la moneda no coincida con el marketplace o con `fin_currency` no es un
    error: son conceptos distintos y no se comparan.
- **Sin cambios:** S1, S3 y S5–S9, la frontera con el motor y la compatibilidad
  histórica.
