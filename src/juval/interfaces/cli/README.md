# interfaces/cli

Punto de entrada por línea de comandos. Cliente delgado de
`application/` — sin reglas de negocio. Implementado (ver ADR-005,
`docs/architecture/ARCHITECTURE.md` §15): expone `run_pipeline()` +
`export_excel()` vía `argparse` (stdlib, sin dependencia nueva).

```bash
.venv/Scripts/python -m juval.interfaces.cli.main \
    tests/fixtures/sample_sourcing_TEST_DATA.xlsx out.xlsx \
    --target-profit 5 --target-roi 0.3 --max-risk-severity LOW \
    --referral-fee 3 --referral-fee-rate 0.15 --fulfillment-fee 2
```

Todos los thresholds y fees son obligatorios y se declaran por flag —
no existe un default comercial embebido (ADR-007). La persistencia del
`ExecutionRun` es opt-in vía `--persist-db <path>` (ADR-013, Opción B);
sin ese flag, la corrida no se guarda en ningún lado más allá del
Excel de salida.

### Evidencia financiera nativa (ADR-047, opt-in)

```bash
.venv/bin/python -m juval.interfaces.cli.main input.xlsx out.xlsx \
    --target-profit 5 --target-roi 0.3 --max-risk-severity LOW \
    --referral-fee 3 --referral-fee-rate 0.15 --fulfillment-fee 2 \
    --persist-db runs.db --native-financial-evidence \
    --financial-target-profit 3 --financial-target-profit-currency USD \
    --financial-target-roi 0.30
```

- `--native-financial-evidence` requiere `--persist-db`. Sin este flag, el
  comportamiento es el legacy de siempre.
- Con el flag, el run, sus snapshots y un documento financiero **v2** por registro
  con escenario completo (`fin_*`, ver `docs/architecture/EXCEL_PROCESSING.md` §9) se
  guardan en una sola transacción SQLite. Si esa escritura falla, el comando
  devuelve 3 y no se persiste nada del run.
- El documento v2 guarda, además del núcleo:
  - los inputs que recibió el resolvedor, incluso inutilizables;
  - los problemas de captura del registro, tal cual;
  - la identidad de implementación, con `application_version` del run y
    `code_revision`/`configuration` en `null`, porque no existe una fuente
    verificable.
- Los diagnósticos de captura de **cada** registro capturado, tenga escenario o no,
  se guardan en la misma transacción como un conjunto independiente
  (`juval.adr047.capture-diagnostics` v1). Un conjunto vacío significa "capturado
  sin diagnósticos". Un registro sin escenario tiene diagnósticos pero no
  documento financiero.
- Los documentos v1 guardados antes se siguen leyendo como v1.
- Registros, Excel de salida, profitability y decisiones son idénticos a la ruta
  legacy.
- Los `--financial-target-*` son opcionales y no reutilizan los `--target-*`
  comerciales:
  - `--financial-target-profit` necesita su moneda explícita.
  - `--financial-target-roi` es un ratio.
  - Sin ellos, los resultados max-COG quedan bloqueados.
- No hay input de peso por registro, así que los resultados que dependen de un
  `shipping_per_pound` aplicable quedan bloqueados.

### Consulta financiera de solo lectura

```bash
.venv/bin/python -m juval.interfaces.cli.financial_report \
    --persist-db runs.db --execution-id <execution_id>
```

- Muestra, por registro y en orden de procesamiento:
  - el documento financiero (v1, v2 o ninguno);
  - cada resultado calculado con valor, unidad y estado, o `BLOCKED` con su
    diagnóstico;
  - los resultados no solicitados;
  - el conjunto de diagnósticos (no guardado, vacío o con sus `CaptureCode`, fila,
    columna y valor original).
- Abre SQLite en modo `mode=ro`: no crea la base, no ejecuta DDL y no recalcula
  nada. No hay base de datos por defecto ni "última ejecución".
- Códigos de salida:
  - 0: reporte;
  - 2: la base no existe;
  - 4: el `execution_id` no está guardado;
  - 5: integridad (payload corrupto, versión desconocida, identidad o
    discrepancia v2/diagnósticos);
  - 6: no es una base SQLite legible.

Fuera de alcance de este entrypoint (todavía `PENDING`/`BLOCKED`, ver
`CLAUDE.md` §14 y `docs/PROJECT_PLAN.md` Fase 4+): API HTTP, PWA,
`.exe`, autenticación, listar corridas históricas.
