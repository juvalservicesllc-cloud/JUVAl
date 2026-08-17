# Juval — Development Loop (Completion Loop)

Normativo. Define el proceso obligatorio para ejecutar **cualquier tarea
de fase** del `PROJECT_PLAN.md`. Formalizado en ADR-009
(`docs/adr/ADR-009-phase-completion-loop.md`, estado Propuesta).

Relación con `CLAUDE.md`: `CLAUDE.md` §23 ("Workflow obligatorio"), §24
("Self-review obligatorio") y §27 ("Reporte final obligatorio") son el
resumen operativo de este documento. Ante cualquier diferencia de
detalle entre ambos, este documento gana — `CLAUDE.md` debería
actualizarse para no quedar desalineado (no se hizo en esta tarea por
estar fuera del alcance pedido; ver reporte final).

Este loop aplica a trabajo de tamaño "fase" o "tarea importante". No es
obligatorio repetirlo completo para una corrección trivial de una línea
sin impacto arquitectónico — pero ante la duda, aplicarlo completo es
más seguro que omitirlo.

```
INSPECT
   ↓
PLAN
   ↓
IMPLEMENT
   ↓
TEST
   ↓
PONYTAIL REVIEW
   ↓
SELF-REVIEW
   ↓
ARCHITECTURAL REVIEW
   ↓
FIX LOOP (si hay fallo)
   ↓
COMPLETION GATE
   ↓
REPORT
   ↓
STOP
```

---

## STEP 1 — INSPECT

Inspeccionar el estado real del repositorio antes de escribir una sola
línea. Leer:

- `CLAUDE.md`;
- documentación relevante en `docs/architecture/`;
- ADRs relevantes en `docs/adr/`;
- código existente relacionado;
- tests existentes relacionados;
- `git status` (si hay `.git` inicializado).

**Nunca asumir el estado.** Un documento puede estar desactualizado
respecto al código y viceversa — inspeccionar ambos, no solo uno.
Ejemplo real de este repositorio (histórico, ya corregido — ver
`docs/RECONCILIATION_REPORT.md`): en un momento de esta misma tarea,
`README.md` raíz y `DATA_MODEL.md` §1/§5 fueron descritos aquí como si
siguieran afirmando que Excel Importer/Exporter y `SourcingRecord` no
estaban implementados; verificado directamente contra el contenido
actual de ambos archivos, esa afirmación ya no era cierta en ese momento
tampoco — ambos ya describían correctamente el código real. Se deja este
ejemplo como ilustración de por qué este paso importa: sin inspeccionar
directamente cada documento contra el código, una afirmación
desactualizada (o una afirmación sobre otro documento que en realidad ya
estaba actualizado) puede propagarse de tarea en tarea sin que nadie la
verifique.

## STEP 2 — PLAN

Crear un plan concreto para el scope de la tarea.

Si durante el plan aparece una decisión arquitectónica no definida
(modelo de datos, arquitectura, seguridad, persistencia, fuentes
externas, lógica comercial, IA, autenticación, deployment — la misma
lista de `CLAUDE.md` §3):

**STOP.**

Reportar, sin implementar nada que dependa de esa decisión:

- **Problema** — qué decisión falta y por qué bloquea el trabajo.
- **Opciones** — alternativas concretas consideradas.
- **Recomendación** — cuál se sugiere y por qué, si aplica.
- **Impacto** — qué se ve afectado (fases, módulos, ADRs existentes).

**No inventar la decisión.** Marcarla PENDING y esperar aprobación
explícita. Ejemplo real encontrado en este repositorio de lo que este
paso debería haber prevenido: `infrastructure/excel/importer.py`
implementa `DEFAULT_RISK_SEVERITY` (severidad por defecto de HazMat/
Bulky) con un comentario propio admitiendo que "NOT reviewed/approved
by the business" — la decisión se implementó de todas formas en vez de
quedar en STOP. Se documenta como riesgo abierto en `PROJECT_PLAN.md`
§Fase 2, no se corrige en esta tarea.

## STEP 3 — IMPLEMENT

Implementar únicamente el scope aprobado del plan. Evitar funcionalidad
de fases futuras solo porque sea fácil de añadir. Si aparece una mejora
fuera de alcance, se registra como **FUTURE / PENDING** en el reporte
final (Step Report), no se implementa de paso.

## STEP 4 — TEST

Ejecutar todas las validaciones relevantes al cambio:

- unit tests;
- integration tests;
- E2E (cuando exista UI);
- lint;
- type checking;
- build;
- validación de fixtures (Excel u otros).

No marcar una validación como "no aplica" sin justificarlo en el reporte
final — omitirla silenciosamente no es válido.

## STEP 5 — PONYTAIL REVIEW

Ejecutar Ponytail (modo FULL en este proyecto) cuando corresponda al
tamaño del cambio (`/ponytail-review` para diffs grandes,
`/ponytail-audit` para auditoría de repositorio, `/ponytail-debt` para
deuda marcada con comentarios `ponytail:`). Buscar:

- over-engineering;
- duplicación;
- abstracciones innecesarias;
- dependencias innecesarias;
- boilerplate;
- código especulativo.

**Ponytail NO puede eliminar**:

- provenance;
- validation;
- security;
- tests;
- reproducibility;
- auditability;
- decisiones arquitectónicas aprobadas.

Regla: **minimalismo de implementación ≠ minimalismo de arquitectura**
(`CLAUDE.md` §5). Un hallazgo de Ponytail que choque con una decisión de
ADR aceptada se reporta como conflicto en Step 7 (Architectural Review),
no se aplica automáticamente.

## STEP 6 — SELF-REVIEW

Revisar contra la misma checklist de `CLAUDE.md` §24:

- **Correctness** — ¿el comportamiento es correcto?
- **Traceability** — ¿se puede saber de dónde salió cada dato relevante?
- **Reproducibility** — ¿se puede repetir la ejecución?
- **Security** — ¿hay secretos o vulnerabilidades?
- **Architecture** — ¿se respetan las capas?
- **Scalability** — ¿el diseño bloquea crecimiento razonable?
- **Simplicity** — ¿hay código innecesario?
- **Documentation** — ¿la documentación refleja el estado real?

## STEP 7 — ARCHITECTURAL REVIEW

Comparar explícitamente el cambio contra:

- `CLAUDE.md`;
- ADRs relevantes (`docs/adr/`);
- `docs/architecture/DATA_MODEL.md` y demás docs de arquitectura;
- la fase actual del `PROJECT_PLAN.md` (¿el cambio respeta alcance/
  fuera de alcance de la fase?);
- decisiones ya aprobadas (APPROVED, no PENDING).

Buscar contradicciones explícitamente — no asumir que "pasa los tests"
implica "no contradice la arquitectura". Este tipo de referencia colgante
(código citando un ADR que no documenta la decisión que dice documentar,
o que no existe) es exactamente lo que este paso debe atrapar. Ejemplo
histórico de este repositorio (ya resuelto, ver
`docs/RECONCILIATION_REPORT.md` §6): en un momento de esta tarea,
`domain/sourcing_record.py` referenciaba "ADR-009" (que en realidad
documenta este mismo Development Loop, no la composición de
`SourcingRecord`) y `infrastructure/excel/importer.py` referenciaba un
"ADR-010" que todavía no existía. Ambas referencias se resolvieron
creando ADR-010 y ADR-011 y actualizando el código para citarlos
correctamente — verificado: el código actual dice "See ADR-011" y "See
ADR-010" respectivamente, y ambos ADRs existen con `Estado: Aceptada` y
el contenido correcto.

## STEP 8 — FIX LOOP

Si cualquier paso anterior encuentra un fallo:

```
FIX → TEST → PONYTAIL REVIEW → SELF-REVIEW → ARCHITECTURAL REVIEW
```

Repetir este ciclo hasta resolver el fallo. No saltar directamente a
"declarar completo" con un fallo conocido sin resolver — eso convierte
el Completion Gate en una formalidad vacía.

## STEP 9 — COMPLETION GATE

Ver `docs/PHASE_GATES.md` para la checklist normativa completa. La fase
o tarea solo puede declararse **COMPLETE** si:

- criterios de aceptación de la fase (`PROJECT_PLAN.md`) pasan;
- tests pasan;
- build pasa;
- no hay conflictos arquitectónicos críticos sin resolver;
- no hay hallazgos de seguridad críticos sin resolver;
- documentación actualizada (`docs/` refleja el código real);
- provenance preservada;
- no hay dependencias externas no autorizadas introducidas;
- revisión Ponytail completada donde corresponda.

Si algo de esto no se cumple:

```
status = PARTIALLY IMPLEMENTED  |  BLOCKED
```

**No declarar COMPLETE** con un criterio pendiente, aunque sea menor.

## STEP 10 — REPORT

Reportar siempre, incluso si el resultado es BLOCKED o PARTIALLY
IMPLEMENTED:

- **Implementation** — qué se hizo.
- **Files** — archivos creados/modificados.
- **Tests** — resultados.
- **Ponytail** — hallazgos (o "no aplica" con motivo).
- **Architecture** — decisiones tomadas (APPROVED/PENDING).
- **Risks** — riesgos restantes.
- **Pending** — decisiones pendientes.
- **Completion Gate** — lista de criterios de `PHASE_GATES.md` con
  estado individual: PASS / FAIL / BLOCKED.
- **Next Phase** — proponer solamente. **No ejecutar automáticamente.**

## STOP

Una vez emitido el reporte, el loop se detiene. No se inicia
automáticamente la siguiente fase ni la siguiente tarea.

---

## Condición de parada — el loop no es optimización infinita

Una vez que todos los criterios del Completion Gate de la tarea/fase en
curso están satisfechos:

**STOP.**

No continuar refactorizando, "mejorando" o buscando más hallazgos de
Ponytail sin una razón concreta y nueva (un bug real, un requisito nuevo
del usuario, una regresión). Cerrar el Completion Gate es el criterio de
salida — no "hasta que ya no se me ocurra nada más que mejorar".
