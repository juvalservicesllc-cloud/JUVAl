# ADR-030: Golden-first frontend productionization (`frontend-next/`)

- Estado: **Aceptada** — 2026-08-26. Decisión explícita del usuario tras
  inspección visual.
- Alcance: **estrategia de frontend.** No cambia el backend, ni el motor de
  decisión, ni la persistencia, ni la semántica de provenance.
- Relacionada con: **ADR-029** (Golden Product Experience Baseline),
  ADR-011/ADR-012 (identidad run-scoped), ADR-003/ADR-004 (provenance),
  ADR-006/ADR-007 (cálculo determinístico y thresholds), ADR-019
  (persistencia de records), ADR-023 (Design System),
  `docs/architecture/GOLDEN_PRODUCT_EXPERIENCE_PARITY.md`.

## Contexto

ADR-029 estableció `demo/` como referencia de experiencia de producto y
`frontend/` como objetivo de integración. La estrategia derivada fue
**convergencia**: llevar capacidades de Golden al `frontend/` heredado, ola a
ola (Wave B, B2, B3, unidad C1).

El 2026-08-26 el usuario inspeccionó el resultado en
`http://127.0.0.1:5182` y **lo rechazó explícitamente**. La razón es
concreta y verificable: 5182 sigue siendo, en lo esencial, la aplicación
heredada con funciones de Golden trasplantadas dentro. La suma de
capacidades no reprodujo la experiencia de producto aprobada.

La conclusión no es que el trabajo previo fuera incorrecto — el audit y las
capacidades recuperadas siguen siendo válidos — sino que **la dirección de la
migración estaba invertida**.

## Decisión

1. **El usuario rechazó visualmente la convergencia basada en `frontend/`.**
2. **El usuario confirmó visualmente `demo/` como la experiencia de producto
   correcta.**
3. **`demo/` permanece como referencia Golden inmutable.** No se modifica, no
   se renombra y no se borra. Huella preservada del árbol `demo/src`:
   `a09635f4432bdecb2ff22aadf3e4a27d296e86af53d7dd2330038375ed560681`.
4. **`frontend/` permanece como referencia heredada de contratos de
   producción**: comportamiento de API, provenance, tests y semánticas ya
   verificadas. No se borra y no se sigue rediseñando.
5. **`frontend-next/` es el candidato de productionización**: la aplicación
   Golden ejecutándose contra el backend real.
6. **Ninguna lógica ni dato `DEMO_FIXTURE` se convierte en verdad de
   producción.** `frontend-next/` no contiene motor de fixtures, ni
   procesamiento de CSV/XLSX en el navegador, ni enriquecimiento simulado, ni
   política de decisión en cliente, ni ASIN generado.
7. **Los contratos de producción, la provenance y las semánticas del backend
   siguen siendo autoritativos.** Donde Golden y el backend difieren, gana el
   backend; lo que Golden aporta es la experiencia, no los datos.
8. **El cutover a `frontend/` ocurre solo tras aprobación del usuario y
   paridad completa.** Hasta entonces `frontend/` sigue siendo la aplicación
   de producción vigente.
9. **No hay reemplazo destructivo durante la migración.** Las tres
   aplicaciones coexisten y se ejecutan en puertos distintos.
10. **La migración avanza capacidad por capacidad**, con revisión visual del
    usuario en cada hito. Catalog es el primero.

## Consecuencias

- Existen tres árboles de frontend con roles declarados: `demo/` (Golden,
  inmutable), `frontend/` (producción vigente y referencia de contrato),
  `frontend-next/` (candidato). Es deliberado, no duplicación accidental.
- Los commits de convergencia previos (`9497bda`, `9280868`, `d9e4e45`,
  `eeb8e08`) **se conservan intactos**: contienen decisiones de contrato ya
  validadas y tests que `frontend-next/` reutiliza como referencia conceptual.
- Una pantalla de `frontend-next/` o habla con la API real, o declara
  explícitamente que aún no está conectada. **Nunca muestra datos de
  demostración**: presentar fixtures dentro de un candidato de producción es
  exactamente el fallo que este ADR existe para evitar.
- Capacidades de Golden que dependen de contratos inexistentes (imágenes de
  proveedor, URL de proveedor, Compare, bandas de thresholds) conservan su
  hueco en la UI con un estado honesto de "no disponible", y sus bloqueos
  quedan registrados en la matriz de paridad. No se eliminan del roadmap.
- El `index.html` de Golden no declara `<!doctype html>`, lo que ejecuta la
  página en *quirks mode* y provoca que `<table>` no herede el color de texto
  — la causa real del defecto de contraste oscuro-sobre-oscuro observado en
  5181. `frontend-next/` declara el doctype; el defecto no se hereda.

## Alternativas descartadas

- **Seguir la convergencia sobre `frontend/`**: ya fue evaluada por el
  usuario sobre el resultado real y rechazada. Rechazada.
- **Sustituir `frontend/` por `demo/` directamente**: perdería contratos de
  API, provenance por campo, persistencia real, consultas server-side,
  paginación, export filtrado, RBAC y la suite de tests. Rechazada.
- **Rediseñar Golden durante la productionización**: el usuario ha dicho que
  Golden aún necesita trabajo de UI/UX, pero *después*. Primero hay que hacer
  real la aplicación correcta. Rechazada para esta fase.
