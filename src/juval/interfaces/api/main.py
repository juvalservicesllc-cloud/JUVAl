"""FastAPI backend for the Juval PWA (Fase 4A).

Thin client over `application.run_pipeline` -- same architectural role
as `interfaces/cli/main.py` (ADR-001, ADR-014). This module contains no
business logic: no profit/ROI/margin/score/decision/severity/fee
calculation lives here. It only:

  1. receives an HTTP request;
  2. validates the *shape* of the request (Pydantic, models.py);
  3. translates it into Thresholds/FeeInputs (service.py);
  4. calls run_pipeline() (application/, unmodified, still pure);
  5. persists the ExecutionRun explicitly, only when the caller asks for
     it via `persist=true` (ADR-013 "Option B" -- run_pipeline() itself
     never persists; this endpoint is simply a second explicit caller
     of the store, exactly like the CLI's `--persist-db` flag);
  6. translates the result back into a response (service.py);
  7. serves the generated Excel for download, reusing export_excel()
     unmodified.

See docs/architecture/API_CONTRACT.md for the full contract.
"""

from __future__ import annotations

import json
import logging
import os
import zipfile
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import ValidationError

import juval
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.domain.execution_run import ExecutionStatus
from juval.application.execution_run_store import ExecutionRunStore
from juval.infrastructure.excel.exporter import export_excel
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

from . import service
from .models import (
    FeesIn,
    RecordOut,
    RunFailedResponse,
    RunRecordsResponse,
    RunResponse,
    RunsListResponse,
    ThresholdsIn,
)

_RUNS_LIST_DEFAULT_LIMIT = 20
_RUNS_LIST_MAX_LIMIT = 100

logger = logging.getLogger("juval.interfaces.api")

app = FastAPI(title="Juval API", version=juval.__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=service.cors_origins(),  # never "*"; empty by default (JUVAL_CORS_ORIGINS unset)
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _execution_run_store() -> Optional[ExecutionRunStore]:
    """Composition root for ExecutionRunStore (ADR-013/ADR-017).

    JUVAL_EXECUTION_STORE ("sqlite"|"supabase"), when set, is the sole
    source of truth -- it always wins over which connection variable
    happens to be present, so a stray JUVAL_SUPABASE_DB_URL left over in
    a local .env can never silently redirect a "sqlite" selection (or
    vice versa). Unset JUVAL_EXECUTION_STORE keeps the pre-existing
    legacy behavior: SqliteExecutionRunStore if JUVAL_EXECUTION_DB_PATH
    is set, else no store configured. Missing the variable a selected
    mode requires is a fail-fast error, never a fallback to the other
    mode or to None.
    """
    mode = os.environ.get("JUVAL_EXECUTION_STORE")

    if mode is None:
        db_path = os.environ.get("JUVAL_EXECUTION_DB_PATH")
        return SqliteExecutionRunStore(db_path) if db_path else None

    if mode == "sqlite":
        db_path = os.environ.get("JUVAL_EXECUTION_DB_PATH")
        if not db_path:
            raise RuntimeError("JUVAL_EXECUTION_STORE=sqlite requires JUVAL_EXECUTION_DB_PATH to be set")
        return SqliteExecutionRunStore(db_path)

    if mode == "supabase":
        db_url = os.environ.get("JUVAL_SUPABASE_DB_URL")
        if not db_url:
            raise RuntimeError("JUVAL_EXECUTION_STORE=supabase requires JUVAL_SUPABASE_DB_URL to be set")
        return SupabaseExecutionRunStore(db_url)

    raise RuntimeError(f"JUVAL_EXECUTION_STORE has an unrecognized value: {mode!r} (expected 'sqlite' or 'supabase')")


def _parse_json_form(raw: str, model: type, field_name: str):
    try:
        return model.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid {field_name}: {exc}") from exc


@app.post("/api/v1/runs", response_model=RunResponse, responses={422: {"model": RunFailedResponse}})
async def create_run(
    file: UploadFile = File(...),
    thresholds: str = Form(...),
    fees: str = Form(...),
    persist: bool = Form(False),
) -> JSONResponse:
    thresholds_in = _parse_json_form(thresholds, ThresholdsIn, "thresholds")
    fees_in = _parse_json_form(fees, FeesIn, "fees")

    try:
        domain_thresholds = service.thresholds_from_in(thresholds_in)
        domain_fees = service.fees_from_in(fees_in)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    max_bytes = service.max_upload_bytes()
    body = await file.read()
    if max_bytes is not None and len(body) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"uploaded file exceeds the configured limit of {max_bytes} bytes "
                "(JUVAL_MAX_UPLOAD_BYTES) -- the definitive business value for this "
                "limit is still PENDING, see API_CONTRACT.md"
            ),
        )

    execution_id = service.new_execution_id()
    run_directory = service.run_dir(execution_id)
    run_directory.mkdir(parents=True, exist_ok=True)
    input_path = run_directory / "input.xlsx"
    input_path.write_bytes(body)

    try:
        run, records = run_pipeline(
            input_path,
            domain_thresholds,
            fees=domain_fees,
            application_version=juval.__version__,
            execution_id=execution_id,
            now=service.now_utc(),
        )
    except (zipfile.BadZipFile, InvalidFileException) as exc:
        raise HTTPException(status_code=422, detail=f"uploaded file is not a valid .xlsx workbook: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)  # never keep the uploaded input around (Sec. 12)

    if run.status == ExecutionStatus.FAILED:
        body_out = RunFailedResponse(
            execution_id=run.execution_id,
            status=run.status.value,
            input_filename=run.input_filename,
            input_hash=run.input_hash,
            message="import produced no usable records",
        )
        return JSONResponse(status_code=422, content=body_out.model_dump(mode="json"))

    record_snapshots = [record_to_snapshot(r) for r in records]

    persisted = False
    if persist:
        store = _execution_run_store()
        if store is None:
            raise HTTPException(
                status_code=500,
                detail="persist=true was requested but JUVAL_EXECUTION_DB_PATH is not configured",
            )
        store.save_execution_run(run, record_snapshots)
        persisted = True

    export_excel(records, service.output_path(execution_id))

    response = RunResponse(
        execution_id=run.execution_id,
        status=run.status.value,
        input_filename=run.input_filename,
        input_hash=run.input_hash,
        records_total=run.records_total,
        records_processed=run.records_processed,
        records_successful=run.records_successful,
        records_with_errors=run.records_with_errors,
        warnings=run.warnings,
        persisted=persisted,
        records=[RecordOut(**s) for s in record_snapshots],
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/download")
async def download_run(execution_id: str) -> FileResponse:
    path = service.output_path(execution_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="unknown or expired execution_id")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{execution_id}.xlsx",
    )


def _require_execution_run_store() -> ExecutionRunStore:
    store = _execution_run_store()
    if store is None:
        raise HTTPException(
            status_code=500,
            detail="this endpoint requires JUVAL_EXECUTION_STORE/JUVAL_EXECUTION_DB_PATH to be configured",
        )
    return store


@app.get("/api/v1/runs", response_model=RunsListResponse)
async def list_runs(limit: int = Query(_RUNS_LIST_DEFAULT_LIMIT, ge=1, le=_RUNS_LIST_MAX_LIMIT)) -> JSONResponse:
    store = _require_execution_run_store()
    runs = store.list_execution_runs(limit=limit)
    response = RunsListResponse(items=[service.run_to_summary(r) for r in runs])
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/records", response_model=RunRecordsResponse)
async def get_run_records(execution_id: str) -> JSONResponse:
    store = _require_execution_run_store()
    run = store.load_execution_run(execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")

    snapshots = store.load_records(execution_id)
    response = RunRecordsResponse(execution_id=execution_id, records=[RecordOut(**s) for s in snapshots])
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
