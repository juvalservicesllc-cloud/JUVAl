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

Fuera de alcance de este entrypoint (todavía `PENDING`/`BLOCKED`, ver
`CLAUDE.md` §14 y `docs/PROJECT_PLAN.md` Fase 4+): API HTTP, PWA,
`.exe`, autenticación, listar corridas históricas.
