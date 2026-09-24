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
- Con el flag, el run, sus snapshots y un documento financiero v1 por registro con
  escenario completo (`fin_*`, ver `docs/architecture/EXCEL_PROCESSING.md` §9) se
  guardan en una sola transacción SQLite. Si esa escritura falla, el comando
  devuelve 3 y no se persiste nada del run.
- Los problemas de captura se imprimen, porque el formato v1 no los guarda.
- Registros, Excel de salida, profitability y decisiones son idénticos a la ruta
  legacy.
- Los `--financial-target-*` son opcionales y no reutilizan los `--target-*`
  comerciales:
  - `--financial-target-profit` necesita su moneda explícita.
  - `--financial-target-roi` es un ratio.
  - Sin ellos, los resultados max-COG quedan bloqueados.
- No hay input de peso por registro, así que los resultados que dependen de un
  `shipping_per_pound` aplicable quedan bloqueados.

Fuera de alcance de este entrypoint (todavía `PENDING`/`BLOCKED`, ver
`CLAUDE.md` §14 y `docs/PROJECT_PLAN.md` Fase 4+): API HTTP, PWA,
`.exe`, autenticación, listar corridas históricas.
