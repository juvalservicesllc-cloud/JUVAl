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

import csv
import json
import logging
import os
import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import ValidationError

import juval
import openpyxl
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.domain.execution_run import ExecutionStatus
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, aggregate_batch_status
from juval.domain.execution_run import ExecutionRun, hash_file
from juval.application.execution_run_store import ExecutionRunStore
from juval.application.record_snapshot_store import RecordSnapshotQuery
from juval.infrastructure.excel.exporter import export_excel
from juval.infrastructure.excel.importer import SUPPORTED_INPUT_SUFFIXES, UnsupportedInputFormat
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

from . import service
from .auth import RUNS_CREATE, RUNS_EXPORT, RUNS_READ, auth_mode, require
from .models import (
    FeesIn,
    RecordOut,
    RunFailedResponse,
    RecordPaginationOut,
    RunAnalyticsOut,
    BatchFileOut,
    BatchResponse,
    RunRecordsResponse,
    RunResponse,
    RunsListResponse,
    RunSummaryOut,
    ThresholdsIn,
)

_RUNS_LIST_DEFAULT_LIMIT = 20
_RUNS_LIST_MAX_LIMIT = 100
_RECORDS_LIST_DEFAULT_LIMIT = 50
_RECORDS_LIST_MAX_LIMIT = 100
_EXPORT_MAX_RECORDS = 100_000

logger = logging.getLogger("juval.interfaces.api")

app = FastAPI(title="Juval API", version=juval.__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=service.cors_origins(),  # never "*"; empty by default (JUVAL_CORS_ORIGINS unset)
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if auth_mode() == "disabled":
    # Loud on purpose: an unauthenticated deployment cannot satisfy Amazon
    # RF-03/RF-04. Production must set JUVAL_AUTH_MODE=oidc (ADR-022).
    logger.warning(
        "JUVAL_AUTH_MODE=disabled -- every endpoint is UNAUTHENTICATED. "
        "This is acceptable only for local development; production must set "
        "JUVAL_AUTH_MODE=oidc (see docs/adr/ADR-022, SECURITY.md)."
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


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9 ._-]")

# Every way a submitted file can turn out to be unreadable as the tabular
# format its extension claims: a corrupt/non-OOXML workbook, or bytes that are
# not decodable text in a .csv. All are the caller's input problem (422),
# never a server fault.
_UNREADABLE_INPUT = (zipfile.BadZipFile, InvalidFileException, UnicodeDecodeError, csv.Error, UnsupportedInputFormat)


def _unreadable_input_detail(filename: str, exc: Exception) -> str:
    kind = "CSV file" if filename.lower().endswith(".csv") else ".xlsx workbook"
    return f"uploaded file is not a valid {kind}: {exc}"


def safe_input_filename(raw: Optional[str]) -> str:
    """Reduce an uploaded filename to a safe basename, or reject it.

    `Path(...).name` drops every directory component, so no traversal
    (`../`, absolute paths, Windows drive-relative paths) survives. Remaining
    characters are restricted to a set every filesystem accepts, and the
    suffix must be one JUVAl actually imports -- the extension is not trusted
    as proof of content, it only selects the reader, which then validates the
    bytes and raises on anything it cannot parse.
    """

    name = Path(raw or "").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_INPUT_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"unsupported file type {suffix or '(none)'}; JUVAl imports {', '.join(sorted(SUPPORTED_INPUT_SUFFIXES))}",
        )
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", Path(name).stem).strip() or "input"
    return f"{cleaned}{suffix}"


def _parse_json_form(raw: str, model: type, field_name: str):
    try:
        return model.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"invalid {field_name}: {exc}") from exc


def _failed_run(*, execution_id: str, input_path, application_version: str, now: datetime) -> ExecutionRun:
    return ExecutionRun(
        execution_id=execution_id,
        started_at=now,
        finished_at=now,
        status=ExecutionStatus.FAILED,
        input_filename=input_path.name,
        input_hash=hash_file(input_path),
        application_version=application_version,
        records_total=0,
        records_processed=0,
        records_successful=0,
        records_with_errors=0,
        warnings=0,
    )


@app.post("/api/v1/runs", response_model=RunResponse, responses={422: {"model": RunFailedResponse}})
async def create_run(
    file: UploadFile = File(...),
    thresholds: str = Form(...),
    fees: str = Form(...),
    persist: bool = Form(False),
    _principal=Depends(require(RUNS_CREATE)),
) -> JSONResponse:
    thresholds_in = _parse_json_form(thresholds, ThresholdsIn, "thresholds")
    fees_in = _parse_json_form(fees, FeesIn, "fees")

    try:
        domain_thresholds = service.thresholds_from_in(thresholds_in)
        domain_fees = service.fees_from_in(fees_in)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    filename = safe_input_filename(file.filename)
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
    # The submitted filename (sanitized) is kept so ExecutionRun.input_filename
    # records which supplier file produced the run, not a generic placeholder.
    input_path = run_directory / filename
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
    except _UNREADABLE_INPUT as exc:
        raise HTTPException(status_code=422, detail=_unreadable_input_detail(filename, exc)) from exc
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


@app.post("/api/v1/batches", response_model=BatchResponse)
async def create_batch(
    files: list[UploadFile] = File(...),
    thresholds: str = Form(...),
    fees: str = Form(...),
    persist: bool = Form(False),
    _principal=Depends(require(RUNS_CREATE)),
) -> JSONResponse:
    """Process up to ten independent child runs as one auditable batch.

    Each file is XLSX or CSV -- one tabular contract, two encodings
    (ADR-026); the importer dispatches on suffix and rejects anything else.

    ExecutionRun remains one file/one deterministic execution. Batch only
    groups child outcomes; it does not merge snapshots or alter Catalog scope.
    """
    if not files:
        raise HTTPException(status_code=422, detail="at least one file is required")
    if len(files) > 10:
        raise HTTPException(status_code=422, detail="a batch may contain at most 10 files")
    thresholds_in = _parse_json_form(thresholds, ThresholdsIn, "thresholds")
    fees_in = _parse_json_form(fees, FeesIn, "fees")
    try:
        domain_thresholds = service.thresholds_from_in(thresholds_in)
        domain_fees = service.fees_from_in(fees_in)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    batch_id = service.new_execution_id()
    created_at = service.now_utc()
    results: list[BatchFile] = []
    max_bytes = service.max_upload_bytes()
    store = _execution_run_store() if persist else None
    if persist and store is None:
        raise HTTPException(status_code=500, detail="persist=true was requested but the execution store is not configured")

    for ordinal, upload in enumerate(files):
        raw_name = Path(upload.filename or "").name
        body = await upload.read()

        def rejected(reason: str) -> BatchFile:
            """One file's rejection never aborts the batch -- the remaining
            files keep processing and this one is reported by name."""
            return BatchFile(ordinal, raw_name or "(unnamed)", upload.content_type, len(body), BatchFileStatus.REJECTED, None, errors=(reason,))

        if max_bytes is not None and len(body) > max_bytes:
            results.append(rejected(f"uploaded file exceeds the configured limit of {max_bytes} bytes"))
            continue
        try:
            filename = safe_input_filename(raw_name)
        except HTTPException as exc:
            results.append(rejected(str(exc.detail)))
            continue

        execution_id = service.new_execution_id()
        run_directory = service.run_dir(execution_id)
        run_directory.mkdir(parents=True, exist_ok=True)
        input_path = run_directory / filename
        input_path.write_bytes(body)
        now = service.now_utc()
        try:
            try:
                run, records = run_pipeline(input_path, domain_thresholds, fees=domain_fees, application_version=juval.__version__, execution_id=execution_id, now=now)
            except _UNREADABLE_INPUT as exc:
                run, records = _failed_run(execution_id=execution_id, input_path=input_path, application_version=juval.__version__, now=now), ()
                if persist and store is not None:
                    store.save_execution_run(run, ())
                results.append(BatchFile(ordinal, filename, upload.content_type, len(body), BatchFileStatus.FAILED, execution_id, errors=(_unreadable_input_detail(filename, exc),)))
                continue
            snapshots = [record_to_snapshot(record) for record in records]
            if persist and store is not None:
                store.save_execution_run(run, snapshots)
            if run.status != ExecutionStatus.FAILED:
                export_excel(records, service.output_path(execution_id))
            file_status = BatchFileStatus.PARTIAL_SUCCESS if run.status == ExecutionStatus.PARTIAL_SUCCESS else BatchFileStatus.SUCCESS if run.status == ExecutionStatus.SUCCESS else BatchFileStatus.FAILED
            results.append(
                BatchFile(
                    ordinal, filename, upload.content_type, len(body), file_status, execution_id,
                    warnings=(f"{run.warnings} warning(s) reported by processing",) if run.warnings else (),
                    errors=("import produced no usable records",) if run.status == ExecutionStatus.FAILED else (),
                    records_total=run.records_total, records_processed=run.records_processed,
                    records_with_errors=run.records_with_errors, warning_count=run.warnings,
                )
            )
        finally:
            input_path.unlink(missing_ok=True)

    batch = Batch(batch_id=batch_id, created_at=created_at, status=aggregate_batch_status(tuple(results)), files=tuple(results))
    if persist and store is not None:
        if not hasattr(store, "save_batch"):
            raise HTTPException(status_code=500, detail="configured execution store does not support batch persistence")
        store.save_batch(batch)
    return JSONResponse(status_code=200, content=_batch_response(batch, persisted=persist).model_dump(mode="json"))


def _batch_response(batch: Batch, *, persisted: bool) -> BatchResponse:
    return BatchResponse(
        batch_id=batch.batch_id,
        created_at=batch.created_at.isoformat(),
        status=batch.status.value,
        total_files=len(batch.files),
        succeeded_files=batch.succeeded_files,
        failed_files=batch.failed_files,
        persisted=persisted,
        records_total=batch.records_total,
        records_processed=batch.records_processed,
        records_with_errors=batch.records_with_errors,
        warning_count=batch.warning_count,
        files=[
            BatchFileOut(
                ordinal=f.ordinal, filename=f.filename, content_type=f.content_type, size_bytes=f.size_bytes,
                status=f.status.value, execution_id=f.execution_id,
                warnings=list(filter(None, f.warnings)), errors=list(f.errors),
                records_total=f.records_total, records_processed=f.records_processed,
                records_with_errors=f.records_with_errors, warning_count=f.warning_count,
            )
            for f in batch.files
        ],
    )


def _load_batch_or_404(loader: str, key: str, *, not_found: str) -> Batch:
    store = _require_execution_run_store()
    if not hasattr(store, loader):
        raise HTTPException(status_code=500, detail="configured execution store does not support batches")
    batch = getattr(store, loader)(key)
    if batch is None:
        raise HTTPException(status_code=404, detail=not_found)
    return batch


@app.get("/api/v1/batches/{batch_id}", response_model=BatchResponse)
async def get_batch(batch_id: str, _principal=Depends(require(RUNS_READ))) -> JSONResponse:
    batch = _load_batch_or_404("load_batch", batch_id, not_found="unknown batch_id")
    return JSONResponse(status_code=200, content=_batch_response(batch, persisted=True).model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/batch", response_model=BatchResponse)
async def get_run_batch(execution_id: str, _principal=Depends(require(RUNS_READ))) -> JSONResponse:
    """The batch this run belongs to, or 404 when it was submitted on its own.

    A run is never *inside* a batch: it stays a complete, independent
    execution. This only answers "was it submitted alongside others", which is
    what Run Detail needs to show sibling-file context.
    """

    batch = _load_batch_or_404("load_batch_for_run", execution_id, not_found="this run is not part of a batch")
    return JSONResponse(status_code=200, content=_batch_response(batch, persisted=True).model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/download")
async def download_run(execution_id: str, _principal=Depends(require(RUNS_EXPORT))) -> FileResponse:
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
async def list_runs(
    limit: int = Query(_RUNS_LIST_DEFAULT_LIMIT, ge=1, le=_RUNS_LIST_MAX_LIMIT),
    _principal=Depends(require(RUNS_READ)),
) -> JSONResponse:
    store = _require_execution_run_store()
    runs = store.list_execution_runs(limit=limit)
    response = RunsListResponse(items=[service.run_to_summary(r) for r in runs])
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}", response_model=RunSummaryOut)
async def get_run(execution_id: str, _principal=Depends(require(RUNS_READ))) -> JSONResponse:
    store = _require_execution_run_store()
    run = store.load_execution_run(execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    response = service.run_to_summary(run)
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/records", response_model=RunRecordsResponse)
async def get_run_records(
    execution_id: str,
    limit: int = Query(_RECORDS_LIST_DEFAULT_LIMIT, ge=1, le=_RECORDS_LIST_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, max_length=200),
    decision: Optional[Literal["BUY", "REVIEW", "PASS"]] = None,
    sort: Literal["record_ref", "sku", "asin", "title", "price", "cog", "decision", "profit", "roi", "margin", "hazmat", "bulky"] = "record_ref",
    direction: Literal["asc", "desc"] = "asc",
    min_roi: Optional[Decimal] = Query(None, ge=Decimal("-1000000")),
    min_profit: Optional[Decimal] = Query(None, ge=Decimal("-1000000")),
    min_margin: Optional[Decimal] = Query(None, ge=Decimal("-1000000")),
    confidence: Literal["VERIFIED_ONLY", "INCLUDE_INFERRED"] = "VERIFIED_ONLY",
    hazmat: Optional[Literal["PRESENT", "ABSENT", "UNKNOWN"]] = None,
    bulky: Optional[Literal["PRESENT", "ABSENT", "UNKNOWN"]] = None,
    provenance_field: Optional[Literal["asin", "selling_price", "profit", "roi", "margin"]] = None,
    provenance_status: Optional[Literal["VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"]] = None,
    _principal=Depends(require(RUNS_READ)),
) -> JSONResponse:
    store = _require_execution_run_store()
    run = store.load_execution_run(execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")

    page = store.list_records(
        execution_id,
        RecordSnapshotQuery(limit=limit, offset=offset, search=search, decision=decision, sort=sort, direction=direction, min_roi=min_roi, min_profit=min_profit, min_margin=min_margin, confidence=confidence, hazmat=hazmat, bulky=bulky, provenance_field=provenance_field, provenance_status=provenance_status),
    )
    response = RunRecordsResponse(
        execution_id=execution_id,
        records=[RecordOut(**snapshot) for snapshot in page.items],
        pagination=RecordPaginationOut(limit=limit, offset=offset, total=page.total, has_more=offset + len(page.items) < page.total),
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _query_from_params(*, search, decision, sort, direction, min_roi, min_profit, min_margin, confidence, hazmat, bulky, provenance_field, provenance_status, limit):
    return RecordSnapshotQuery(limit=limit, offset=0, search=search, decision=decision, sort=sort, direction=direction, min_roi=min_roi, min_profit=min_profit, min_margin=min_margin, confidence=confidence, hazmat=hazmat, bulky=bulky, provenance_field=provenance_field, provenance_status=provenance_status)


@app.get("/api/v1/runs/{execution_id}/records/export")
async def export_filtered_records(
    execution_id: str,
    search: Optional[str] = Query(None, max_length=200),
    decision: Optional[Literal["BUY", "REVIEW", "PASS"]] = None,
    sort: Literal["record_ref", "sku", "asin", "title", "price", "cog", "decision", "profit", "roi", "margin", "hazmat", "bulky"] = "record_ref",
    direction: Literal["asc", "desc"] = "asc",
    min_roi: Optional[Decimal] = Query(None, ge=Decimal("-1000000")),
    min_profit: Optional[Decimal] = Query(None, ge=Decimal("-1000000")),
    min_margin: Optional[Decimal] = Query(None, ge=Decimal("-1000000")),
    confidence: Literal["VERIFIED_ONLY", "INCLUDE_INFERRED"] = "VERIFIED_ONLY",
    hazmat: Optional[Literal["PRESENT", "ABSENT", "UNKNOWN"]] = None,
    bulky: Optional[Literal["PRESENT", "ABSENT", "UNKNOWN"]] = None,
    provenance_field: Optional[Literal["asin", "selling_price", "profit", "roi", "margin"]] = None,
    provenance_status: Optional[Literal["VERIFIED", "INFERRED", "NOT_FOUND", "INVALID"]] = None,
    _principal=Depends(require(RUNS_EXPORT)),
) -> FileResponse:
    store = _require_execution_run_store()
    if store.load_execution_run(execution_id) is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    query = _query_from_params(search=search, decision=decision, sort=sort, direction=direction, min_roi=min_roi, min_profit=min_profit, min_margin=min_margin, confidence=confidence, hazmat=hazmat, bulky=bulky, provenance_field=provenance_field, provenance_status=provenance_status, limit=_EXPORT_MAX_RECORDS)
    page = store.list_records(execution_id, query)
    path = service.run_dir(execution_id) / "filtered-export.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "catalog_export"
    headers = ("record_ref", "supplier_sku", "asin", "asin_status", "title", "brand", "selling_price", "selling_price_status", "cog", "profit", "profit_status", "roi", "roi_status", "margin", "margin_status", "hazmat_status", "hazmat_severity", "bulky_status", "bulky_severity", "decision", "issue_count", "issues")
    sheet.append(list(headers))
    for record in page.items:
        def value(field): return record.get(field, {}).get("value") if isinstance(record.get(field), dict) else record.get(field)
        def status(field): return record.get(field, {}).get("status") if isinstance(record.get(field), dict) else None
        sheet.append([record.get("record_ref"), record.get("supplier_sku"), value("asin"), status("asin"), value("title"), value("brand"), value("selling_price"), status("selling_price"), record.get("cog"), value("profit"), status("profit"), value("roi"), status("roi"), value("margin"), status("margin"), record.get("hazmat_status"), record.get("hazmat_severity"), record.get("bulky_status"), record.get("bulky_severity"), record.get("decision"), record.get("issue_count", 0), " ; ".join(record.get("issues", []))])
    metadata = workbook.create_sheet("query_metadata")
    metadata.append(["execution_id", execution_id])
    metadata.append(["generated_at", datetime.now(timezone.utc).isoformat()])
    metadata.append(["filters", json.dumps({"search": search, "decision": decision, "min_roi": str(min_roi) if min_roi is not None else None, "min_profit": str(min_profit) if min_profit is not None else None, "min_margin": str(min_margin) if min_margin is not None else None, "confidence": confidence, "hazmat": hazmat, "bulky": bulky, "provenance_field": provenance_field, "provenance_status": provenance_status}, sort_keys=True)])
    metadata.append(["sort", sort])
    metadata.append(["direction", direction])
    # State the unit explicitly: min_roi/min_margin are canonical ratios, so
    # 0.3 in this sheet is the 30% the operator typed. Without this line a
    # reader could take 0.3 for 0.3% and misjudge a sourcing threshold.
    metadata.append(["units", "min_roi and min_margin are ratios (0.30 = 30%); min_profit and prices are absolute currency amounts"])
    workbook.save(path)
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"{execution_id}-filtered.xlsx")


@app.get("/api/v1/runs/{execution_id}/records/{record_ref}", response_model=RecordOut)
async def get_run_record(
    execution_id: str,
    record_ref: str,
    _principal=Depends(require(RUNS_READ)),
) -> JSONResponse:
    """Return one immutable snapshot by ``(execution_id, record_ref)``.

    The store performs the composite-key lookup. This endpoint never loads a
    page or recalculates a record, so refresh/deep-link behavior is independent
    of ordinal position and run size. It is declared after the literal export
    route so ``export`` cannot be interpreted as a record reference.
    """
    store = _require_execution_run_store()
    if store.load_execution_run(execution_id) is None:
        raise HTTPException(status_code=404, detail="unknown record for execution")
    snapshot = store.load_record(execution_id, record_ref)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="unknown record for execution")
    return JSONResponse(status_code=200, content=RecordOut(**snapshot).model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/analytics", response_model=RunAnalyticsOut)
async def get_run_analytics(execution_id: str, _principal=Depends(require(RUNS_READ))) -> JSONResponse:
    store = _require_execution_run_store()
    if store.load_execution_run(execution_id) is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    response = RunAnalyticsOut(execution_id=execution_id, **store.get_run_analytics(execution_id))
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
