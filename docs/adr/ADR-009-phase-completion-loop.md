# ADR-009: Loop de ejecución y cierre de fase (Development Loop + Completion Gates)

- Estado: **Propuesta (PROPOSED)** — pendiente de revisión arquitectónica
  adicional antes de aprobar. No tratar como aceptada hasta que el
  usuario la confirme explícitamente.
- Fecha: 2026-08-16

## Contexto

`PROJECT_PLAN.md` define 11 fases (Fase 0 a Fase 10), varias de ellas
bloqueadas hoy por decisiones pendientes (ADR-005, stack frontend,
Supabase, Clerk, fuente externa concreta, proveedor de IA, fórmulas de
Decision Score — ver `PROJECT_PLAN.md` §4). Sin un proceso explícito y
uniforme para ejecutar y cerrar cada fase, existe riesgo real de que:

- una fase se declare "completa" porque existe código, sin que pase
  tests, revisión arquitectónica o revisión de Ponytail;
- una decisión arquitectónica pendiente se resuelva implícitamente
  durante la implementación, en vez de quedar marcada PENDING y esperar
  aprobación (violación directa de `CLAUDE.md` §3, la regla de oro §4);
- Ponytail elimine arquitectura aprobada (provenance, validación, capas,
  tests) en nombre de la simplicidad, sin que quede registrado como
  conflicto;
- el trabajo de "revisión" se vuelva un loop de optimización sin fin,
  sin una condición de parada clara.

Esto no es un riesgo hipotético: al inspeccionar el repositorio para
esta ADR se confirmó que ya ocurrió una vez. Ver "Evidencia" abajo.

## Decisión

Se adopta un **Development Loop** de 10 pasos, obligatorio para toda
tarea de fase, documentado en detalle en `docs/DEVELOPMENT_LOOP.md`:

```
INSPECT → PLAN → IMPLEMENT → TEST → PONYTAIL REVIEW
   → SELF-REVIEW → ARCHITECTURAL REVIEW → FIX LOOP
   → COMPLETION GATE → REPORT → STOP
```

Reglas duras del loop:

1. **STOP en Step 2 (Plan)** si aparece una decisión arquitectónica no
   definida — se reporta problema/opciones/recomendación/impacto, nunca
   se inventa la decisión.
2. **Step 5 (Ponytail Review)** no puede eliminar arquitectura ya
   aprobada (provenance, validación, capas, tests, auditabilidad,
   decisiones de ADR aceptadas); un conflicto entre Ponytail y un ADR
   aceptado se reporta, no se aplica automáticamente. Regla:
   minimalismo de implementación ≠ minimalismo de arquitectura.
3. **Step 8 (Fix Loop)** exige repetir
   `FIX → TEST → PONYTAIL REVIEW → SELF-REVIEW → ARCHITECTURAL REVIEW`
   hasta resolver cualquier fallo detectado — no se permite saltar al
   cierre con un fallo conocido sin resolver.
4. **Step 9 (Completion Gate)** usa la checklist normativa de
   `docs/PHASE_GATES.md` (Universal Gate + gate específico por fase).
   Una fase solo se declara `COMPLETE` si **todos** los criterios están
   en `PASS`; de lo contrario `PARTIALLY IMPLEMENTED` o `BLOCKED`, nunca
   `COMPLETE`.
5. **Step 10 (Report)** es obligatorio incluso cuando el resultado es
   `BLOCKED` — el reporte incluye el estado individual de cada criterio
   del Completion Gate, no un veredicto agregado.
6. **Condición de parada explícita**: una vez que el Completion Gate de
   la tarea/fase en curso está satisfecho, el loop se detiene (`STOP`).
   No se continúa refactorizando o buscando más hallazgos de Ponytail
   sin una razón nueva y concreta — el loop no es una optimización
   infinita.

## Evidencia — por qué esta ADR no es preventiva sino correctiva

Al revisar el estado real del repositorio para escribir esta ADR se
encontró que Fase 2 (`SourcingRecord` + Excel vertical slice) y parte de
Fase 3 (`ExecutionRun`) ya tienen código implementado y 165 tests
pasando — sin que exista un registro de que pasaron por un Completion
Gate, y con documentación (`README.md` raíz, `DATA_MODEL.md` §1/§5) que
sigue describiendo esas fases como no iniciadas. Además:

- `infrastructure/excel/importer.py` implementa `DEFAULT_RISK_SEVERITY`
  con un comentario propio admitiendo que es una decisión de negocio
  "NOT reviewed/approved" — exactamente el caso que el Step 2 (STOP ante
  decisión no definida) de este loop existe para prevenir, y que no se
  previno.
- `domain/sourcing_record.py` y `infrastructure/excel/importer.py`
  referencian "ADR-009" y "ADR-010" respectivamente para documentar
  decisiones de diseño — ninguno de los dos ADRs existe con ese
  contenido (ADR-009 queda tomado por esta misma ADR; ADR-010 no existe
  en absoluto). Detalle completo en `docs/PHASE_GATES.md` §3.

Esto confirma el problema que motiva la ADR, no lo contradice: se
documenta aquí, no se corrige (fuera de alcance de esta tarea), y queda
como pendiente explícito para la próxima tarea que cierre el gate de
Fase 2.

## Rationale

- El loop hace explícito lo que `CLAUDE.md` §23/§24/§27 ya resumía en
  forma corta, pero sin un mecanismo de verificación por criterio
  (`PASS`/`FAIL`/`BLOCKED`) ni un lugar único donde consultar qué hace
  falta para cerrar cada fase concreta — de ahí que se separe en
  `DEVELOPMENT_LOOP.md` (proceso) y `PHASE_GATES.md` (checklist por
  fase), en vez de expandir `CLAUDE.md` indefinidamente (regla de
  `CLAUDE.md` §18: reglas operativas cortas aquí, especificación
  detallada en `docs/`).
- Separar `BLOCKED` de `FAIL` importa porque son causas distintas: `FAIL`
  es trabajo mal hecho o proceso no cerrado (se corrige con Step 8);
  `BLOCKED` es una decisión externa pendiente (se corrige pidiendo esa
  decisión, nunca inventándola).
- La condición de parada explícita existe porque un loop de revisión sin
  límite es, en sí mismo, una forma de sobreingeniería de proceso — el
  mismo principio de minimalismo que Ponytail aplica al código
  (`CLAUDE.md` §5) aplica aquí al proceso.

## Consecuencias

- Positivas: cada fase tiene un criterio de cierre verificable y
  auditable, no una impresión subjetiva de "ya está"; las decisiones
  pendientes quedan visibles en vez de resolverse silenciosamente;
  Ponytail tiene un límite claro (no puede tocar arquitectura aprobada).
- Negativas: más proceso que simplemente "escribir código y hacer merge"
  — deliberado, dado que la prioridad del proyecto es correctitud y
  trazabilidad por encima de velocidad (`CLAUDE.md` §2).
- Reversibilidad: alta — el loop y los gates son proceso, no código ni
  esquema de datos; pueden ajustarse fase a fase sin migrar nada, y esta
  ADR puede reemplazarse por otra si la experiencia de cerrar
  formalmente el gate de Fase 2/3 muestra que algún paso es innecesario
  o insuficiente.

## Por qué queda como Propuesta y no Aceptada

A diferencia de ADR-001 a ADR-008, que documentaban decisiones ya
tomadas y verificadas contra código existente en el momento de su
redacción, esta ADR introduce un proceso que — según la evidencia
encontrada — ya se saltó una vez antes de existir formalmente. Se
mantiene en estado **Propuesta** hasta que el usuario la revise y
confirme explícitamente, y hasta que exista al menos un cierre de fase
real que la haya seguido de punta a punta — no se marca Aceptada por
conveniencia ni porque los documentos ya estén escritos (`CLAUDE.md`
§3: no convertir PENDING en APPROVED silenciosamente).

## Relacionado

`docs/PROJECT_PLAN.md` (fases, dependencias y estado real de Fase 2/3),
`docs/DEVELOPMENT_LOOP.md` (especificación completa del loop),
`docs/PHASE_GATES.md` (checklist de cierre por fase y contradicción de
numeración de ADR detectada), `CLAUDE.md` §3/§5/§23/§24/§27 (resumen
operativo).
