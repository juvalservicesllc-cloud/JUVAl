# Juval

Amazon Sourcing Decision Engine: transforma listas de proveedores y datos
de producto en decisiones de sourcing (BUY / REVIEW / PASS), con foco en
trazabilidad de datos sensibles (ASIN, peso, HazMat, bulky, y en general
todo lo que alimenta el Profitability y Decision Engine).

## Estado

**Fase 2 y Fase 3: COMPLETE** — Excel Input → Import → Validation →
SourcingRecord → Processing Core (Data Quality → Profitability → Risk →
Decision) → Excel Output, determinístico y reproducible, con
`ExecutionRun` persistido opcionalmente vía SQLite (ADR-013) y un CLI
real (`interfaces/cli/main.py`, ver más abajo). Sin scraping, sin APIs
externas, sin IA, sin Supabase/Clerk, sin dashboard todavía — ver
`docs/architecture/DATA_MODEL.md` §5 y `docs/PROJECT_STATUS.md`.

- [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) — arquitectura general (Fase 0).
- [`docs/architecture/DATA_DICTIONARY.md`](docs/architecture/DATA_DICTIONARY.md) — diccionario de datos.
- [`docs/architecture/DATA_MODEL.md`](docs/architecture/DATA_MODEL.md) — entidades y relaciones.
- [`docs/architecture/DATA_SOURCES.md`](docs/architecture/DATA_SOURCES.md) — clasificación de fuentes.
- [`docs/architecture/DATA_PROVENANCE.md`](docs/architecture/DATA_PROVENANCE.md) — estructura de provenance.
- [`docs/architecture/DECISION_ENGINE.md`](docs/architecture/DECISION_ENGINE.md) — motor de decisión BUY/REVIEW/PASS.
- [`docs/architecture/EXCEL_PROCESSING.md`](docs/architecture/EXCEL_PROCESSING.md) — import/export, column mapping, fixture.
- [`docs/architecture/AI_ANALYST.md`](docs/architecture/AI_ANALYST.md) — contrato de la futura capa de IA.
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — fotografía oficial actual del proyecto (fase, tests, deuda técnica, pendientes).
- [`docs/adr/`](docs/adr/) — decisiones arquitectónicas registradas (ADR-001 a ADR-013; ADR-009 en estado Propuesta, el resto Aceptada).

## Desarrollo

```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]   # o: .venv/Scripts/pip install pytest openpyxl
.venv/Scripts/python -m pytest
```

`pyproject.toml` apunta `pythonpath` a `src/`, así que los tests importan
`juval.*` sin instalar el paquete.

## Estructura

```
src/juval/
├── domain/           entidades puras: provenance, product, costs, risk, decision,
│                      sourcing_record, execution_run
├── processing/        Processing Core: profitability, decision_engine, decision_score,
│                      data_quality, pipeline (process_record/process_batch)
├── application/       run_pipeline: único módulo que conecta infrastructure + processing
├── infrastructure/
│   └── excel/          column_mapping, importer, exporter
└── interfaces/
    └── cli/             main.py -- CLI real (argparse); api/ y desktop/ siguen vacíos (bloqueados, ver ADR-005)
```

## CLI

```bash
PYTHONPATH=src .venv/Scripts/python -m juval.interfaces.cli.main \
    tests/fixtures/sample_sourcing_TEST_DATA.xlsx out.xlsx \
    --target-profit 5 --target-roi 0.3 --max-risk-severity LOW \
    --referral-fee 3 --referral-fee-rate 0.15 --fulfillment-fee 2
```

Thresholds y fees son siempre obligatorios por flag (ADR-007, sin
default comercial embebido). Agregar `--persist-db runs.db` para guardar
el `ExecutionRun` explícitamente (opt-in, ADR-013 Opción B). Ver
`src/juval/interfaces/cli/README.md` para el detalle completo de flags.

## Probar el pipeline manualmente

```python
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import juval
from juval.domain.decision import Thresholds
from juval.domain.costs import FeeInputs
from juval.domain.risk import Severity
from juval.application.run_pipeline import run_pipeline

run, records = run_pipeline(
    Path("tests/fixtures/sample_sourcing_TEST_DATA.xlsx"),
    Thresholds(target_profit=Decimal("5"), target_roi=Decimal("0.3"),
               minimum_estimated_monthly_sales=0, maximum_risk_severity=Severity.LOW),
    fees=FeeInputs(referral_fee=Decimal("3"), referral_fee_rate=Decimal("0.15"), fulfillment_fee=Decimal("2")),
    application_version=juval.__version__, execution_id="manual-run",
    now=datetime.now(timezone.utc),
)
```
