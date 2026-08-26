# ADR-029: `demo/` como Golden Product Experience Baseline

- Estado: **Aceptada** — 2026-08-26. Decisión explícita del usuario tras
  inspección visual directa.
- Alcance: **referencia de UX/UI únicamente.** No aprueba la lógica de
  negocio, los datos, el motor de decisión, la persistencia ni el router del
  demo como arquitectura de producción.
- Relacionada con: ADR-023 (gobernanza del Design System del frontend),
  ADR-024 (IA de producto y contrato de Catalog), ADR-011/ADR-012
  (identidad run-scoped), ADR-003/ADR-004 (provenance y estados de
  verificación), ADR-006/ADR-007 (cálculo y thresholds),
  `docs/architecture/DEMO_PRODUCTION_PARITY_MATRIX.md`,
  `docs/architecture/CATALOG_GOLDEN_UX_PARITY.md`.

## Contexto

El 2026-08-26 se ejecutó una investigación forense en la estación Windows
para localizar una interfaz «avanzada» que el usuario recordaba y que no
correspondía al `frontend/` actual. Evidencia recogida:

- El repositorio no perdió trabajo: `git fsck` no encontró **ningún commit
  inalcanzable** (solo blobs/trees sueltos, correspondientes al frontend del
  2026-08-17, *más simple* que el actual), y el reflog (172 entradas) es
  **lineal**, sin `reset`, `rebase`, `checkout` ni `clean`.
- Los transcripts locales de sesión muestran que **nunca** se escribieron
  `ComparePage`, `FavoritesPage`, `PriceHistory` ni `CatalogPage` bajo
  `frontend/`.
- Sí existen —y siguen íntegros y versionados— bajo `demo/`
  (`juval-west-marine-demo`, commit `549019c`, 62 archivos versionados,
  React 19 + Recharts, construido entre 2026-08-18 y 2026-08-19).
- `docs/architecture/DEMO_PRODUCTION_PARITY_MATRIX.md` (2026-08-19) ya
  describía `demo/` como *«evidence of the previous product experience and
  its intended interaction model»*.

El usuario ejecutó `demo/` en `http://127.0.0.1:5181/catalog` y confirmó
explícitamente que esa es la experiencia que recordaba.

## Decisión

1. **`demo/` es la referencia canónica de UX/UI** («Golden Product
   Experience Baseline») de JUVAl.
2. **`frontend/` sigue siendo el objetivo de integración de producción.**
   La convergencia se hace llevando la experiencia visual de `demo/` a
   `frontend/`, **nunca** sustituyendo `frontend/` por `demo/`.
3. **La lógica de negocio y los datos de `demo/` no son verdad de
   producción.** Su motor, sus fixtures, su historial de precios simulado,
   sus imágenes de proveedor, sus decisiones y sus thresholds locales son
   material de demostración.
4. **`DEMO_FIXTURE` nunca se convierte silenciosamente en `VERIFIED`.** La
   separación `VERIFIED` / `INFERRED` / `DEMO_FIXTURE` / `NOT_FOUND` /
   `INVALID` se mantiene explícita (ADR-003, ADR-004). Ningún elemento
   visual migrado puede presentar un dato inferido o de fixture como
   verificado.
5. **La migración es selectiva e incremental**, por olas independientes,
   testeables y reversibles. Los contratos del backend, la provenance y la
   semántica de riesgo tienen precedencia sobre la paridad visual.
6. **`demo/` permanece intacto** hasta que la convergencia esté completa y
   aceptada. No se borra, no se renombra y no se modifica.
7. **La paridad visual la valida el usuario.** Ninguna ola se declara
   completa por que pasen los tests.

Huella de origen preservada (árbol `demo/src`, SHA-256 del conjunto):
`a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`.

## Consecuencias

- Existen dos implementaciones vivas simultáneamente, con roles distintos y
  declarados. Esto es deliberado, no duplicación accidental.
- `frontend/` gana la dirección visual de `demo/` sin heredar su modelo de
  datos. Donde `demo/` obtiene una capacidad de un fixture y producción no
  tiene fuente autorizada, la capacidad **no** se migra como si existiera:
  se documenta como bloqueada.
- Capacidades del demo que requieren decisiones arquitectónicas previas
  —Favorites y Compare (propiedad, persistencia, identidad comparable),
  editor de thresholds de decisión, imágenes canónicas de producto,
  historial de mercado real— quedan **fuera de esta ADR** y siguen
  `DEFER_BLOCKED` hasta que exista un ADR propio.
- Las tres capacidades visuales migradas en la primera ola (Catalog) están
  cubiertas por tests de regresión sobre el contrato, no sobre el estilo.

## Alternativas descartadas

- **Sustituir `frontend/` por `demo/`**: perdería autenticación/RBAC,
  persistencia real, consultas server-side, paginación, export filtrado,
  provenance por campo y el contrato de API. Rechazada.
- **Declarar `frontend/` como la experiencia correcta**: contradice la
  identificación visual explícita del usuario, que es el oráculo de
  aceptación. Rechazada.
- **Reconstruir la UI «de memoria»**: no reproducible ni trazable, y
  además innecesario: la referencia existe y está versionada. Rechazada.
