# ADR-054 — Gráficos DEMO de presentación en `frontend-next/` (enmienda propuesta a ADR-030)

- Estado: **Propuesta** (2026-11-03). **No aprobada.** Requiere aceptación
  explícita del propietario; hasta entonces ADR-030 rige sin cambios.
  El propietario indicó el 2026-11-03 una **aprobación arquitectónica
  preliminar**; el estado sigue siendo Propuesta hasta su confirmación formal.
- Origen: la recuperación G12 se implementó por instrucción explícita del
  propietario en la sesión del 2026-11-03 (commit `56db50a`), registrada en
  [FRONTEND_NEXT_PARITY_RECOVERY](../architecture/FRONTEND_NEXT_PARITY_RECOVERY.md).
  Esa autorización de sesión no modifica el texto de ADR-030. Este ADR propone
  formalizarla de forma acotada.
- Enmienda a: **ADR-030** §Decisión punto 6 y §Consecuencias («Nunca muestra
  datos de demostración»).
- Relacionado: ADR-003/ADR-004 (provenance), ADR-006 (cálculo determinístico),
  ADR-029 (Golden), ADR-046 (contratos de observaciones de mercado).

## Contexto

ADR-030 prohíbe que `frontend-next/` muestre datos de demostración, para que un
candidato de producción nunca presente fixtures como si fueran reales. El
Product Detail de Golden (`demo/`) y del frontend anterior incluía una serie de
mercado ilustrativa con Line/Bar (gate G12). El propietario autorizó recuperarla
como presentación aislada. No existe fuente de mercado aprobada (ADR-046,
`DATA_SOURCES.md`), así que no hay serie real que mostrar.

## Decisión propuesta

1. Se permite **una única categoría** de excepción: gráficos de presentación
   **explícitamente DEMO**, con datos sintéticos fijos, en `frontend-next/`.
2. Requisitos obligatorios de cada gráfico DEMO:
   - etiqueta visible `DEMO_FIXTURE · NOT VERIFIED` y texto que niegue ser
     Amazon/Keepa o la historia del producto mostrado;
   - serie constante en el código: sin red, sin aleatoriedad en ejecución, sin
     fechas reales ni afirmaciones de frescura;
   - el componente **no recibe** record, ASIN, precio, run ni ningún dato del
     backend como entrada;
   - alternativa accesible (tabla de valores) con el mismo etiquetado.
3. Prohibido, sin excepción:
   - usar valores DEMO en ROI, profit, margin, break-even, max COG, score,
     thresholds, decisiones (BUY/REVIEW/PASS), filtros, ordenaciones o exports;
   - asignarles `VerificationStatus` (VERIFIED, INFERRED, NOT_FOUND, INVALID) o
     `Provenance`; no son `FieldValue` y no entran en el modelo de dominio;
   - persistirlos, enviarlos al backend o mezclarlos con una serie real;
   - presentar una serie DEMO junto a datos reales sin separación visual y
     textual inequívoca.
4. Cuando exista una fuente de mercado aprobada (ADR-046), la serie real
   sustituye al gráfico DEMO; no conviven en el mismo control.
5. Corrección editorial a aplicar con la aceptación: ADR-030 §Decisión punto 8
   dice «El cutover a `frontend/`»; por el contexto (punto 5 y §Consecuencias)
   el destino del cutover es `frontend-next/`.

## Trazabilidad actual (estado del código en `523aa47`)

| Requisito | Evidencia |
|---|---|
| Serie fija de 90 puntos, sin entradas | `frontend-next/src/pages/MarketDemo.tsx`: `DEMO_MARKET` constante; `MarketDemo()` sin props |
| Aislamiento | `DEMO_MARKET` y `MarketDemo` solo se importan desde `ProductDetailPage.tsx` (búsqueda en `src/`, 2026-11-03) |
| Etiquetado visible | Texto `DEMO_FIXTURE · NOT VERIFIED · NOT INFERRED FROM PRODUCTION DATA` |
| Pruebas unitarias | `MarketDemo.test.tsx` (90 puntos, inmutabilidad, Line/Bar, tabla de 91 filas); `ProductDetailPage.test.tsx` (etiqueta y separación) |
| Navegador | `e2e/zz-parity-gates.spec.ts`: etiqueta y 90 barras a 360/1440, claro/oscuro; 42/42 E2E PASS |
| Sin impacto económico | Specs retenidos comparan export de Catalog, descarga de run y API en `d7`/`g17`; pasan sin cambios |

## Pruebas exigidas si se acepta

- Mantener las pruebas anteriores.
- Añadir una comprobación estática que falle si `DEMO_MARKET` se importa fuera
  de `MarketDemo.tsx`/`ProductDetailPage.tsx` o si `MarketDemo` recibe props.
- Cualquier nuevo gráfico DEMO necesita su propia prueba de etiqueta y de
  ausencia de entradas.

## Consecuencias

- Positiva: paridad visual con Golden sin inventar datos de mercado.
- Riesgo: un usuario puede ignorar la etiqueta. Mitigación: etiqueta en el
  título del panel y en el nombre accesible; ningún valor DEMO aparece fuera
  del panel.
- Si se **rechaza**: G12 debe retirarse de `frontend-next/` antes del cutover
  (revertir `56db50a` y su documentación), porque contradice ADR-030.

## Alternativas

- **Mantener G12 solo como autorización de sesión:** deja una contradicción
  documental con un ADR aceptado. No recomendado.
- **Retirar G12:** cumple ADR-030 sin enmienda; pierde la paridad visual.
- **Serie real:** bloqueada por falta de fuente aprobada.
