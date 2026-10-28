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

import contextlib
import csv
import json
import logging
import os
import re
import tempfile
import zipfile
from dataclasses import replace
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
from juval.application.batch_persistence import BatchChild, save_batch_with_runs
from juval.application.import_preview import preview_import
from juval.application.record_snapshot import record_to_snapshot, severity_provenance_cells
from juval.application.run_pipeline import run_pipeline, run_pipeline_with_financial_evidence
from juval.domain.execution_run import ExecutionStatus
from juval.domain.batch import Batch, BatchFile, BatchFileStatus, aggregate_batch_status
from juval.domain.execution_run import ExecutionRun, hash_file
from juval.application.execution_run_store import ExecutionRunStore
from juval.application.financial_persistence import (
    FinancialRecordIntegrityError,
    FinancialStorageUnavailable,
    save_run_with_financial_records,
)
from juval.application.native_financial_documents import (
    build_financial_documents,
    capture_diagnostics_sets,
    declared_financial_target,
)
from juval.application.financial_report import record_financial_reports
from juval.application.financial_serialization import FinancialSerializationError
from juval.application.record_snapshot_store import RecordSnapshotQuery
from juval.application.review_classification import review_classification as classify_review
from juval.application.demand_evidence import demand_export_cells
from juval.application.suggested_price_evidence import suggested_price_export_cells
from juval.infrastructure.excel.exporter import DEMAND_EXPORT_HEADERS, SEVERITY_PROVENANCE_EXPORT_HEADERS, SUGGESTED_PRICE_EXPORT_HEADERS
from juval.infrastructure.excel.exporter import append_literal_row, export_excel
from juval.infrastructure.excel.importer import SUPPORTED_INPUT_SUFFIXES, UnsupportedInputFormat
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.infrastructure.persistence.supabase_execution_run_store import SupabaseExecutionRunStore

from . import bff, service
from .auth import RUNS_CREATE, RUNS_EXPORT, RUNS_READ, auth_mode, require, set_session_resolver
from .models import (
    FeesIn,
    ImportPreviewResponse,
    RecordFinancialOut,
    RunFinancialSummaryOut,
    RecordOut,
    RunFailedResponse,
    RunFinancialResponse,
    StoredPayloadOut,
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

#: ADR-050 D3: the batch was stored, only this file's XLSX download is missing.
EXPORT_FAILED_WARNING = "download unavailable: export failed"


@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Validate the identity configuration before the first request is served.

    ADR-036 promises fail-closed session storage. Validating lazily made that
    promise weaker than it reads: a bad DSN, a missing encryption key or a
    half-configured browser flow would surface as an intermittent 500 on
    whichever request happened to touch the BFF first, on whichever instance
    happened to serve it. Doing it here means an invalid production
    configuration stops the process from starting at all, which is the only
    failure mode an operator cannot miss.

    `ensure_configured()` is idempotent, so a test that installed its own
    stores keeps them; this never overwrites an explicit `bff.configure()`.
    """
    bff.ensure_configured()
    yield


app = FastAPI(title="Juval API", version=juval.__version__, lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=service.cors_origins(),  # never "*"; empty by default (JUVAL_CORS_ORIGINS unset)
    # Cookie-based sessions (ADR-034) require credentialed CORS: the browser
    # will not attach the HttpOnly session cookie to a cross-origin request
    # otherwise. CORS does not override SameSite=Lax: public PWA/API site
    # topology still requires validation (ADR-038). This is only safe because `allow_origins` is an explicit
    # allow-list that is empty by default and can never be "*" -- the CORS spec
    # itself forbids "*" together with credentials, and `cors_origins()` would
    # have to be changed for that combination to arise.
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# The BFF owns the browser's half of OIDC (ADR-034). Mounted unconditionally so
# its routes exist and answer 404 "authentication is not enabled" when
# JUVAL_AUTH_MODE is unset -- a missing route and a disabled feature would
# otherwise be indistinguishable to the frontend.
app.include_router(bff.router)

# Teach auth.py how to turn a session cookie into a Principal, without auth.py
# importing the BFF (see auth.py::set_session_resolver).
set_session_resolver(bff.principal_from_session)

if auth_mode() == "disabled":
    # Loud on purpose: an unauthenticated deployment cannot satisfy Amazon
    # RF-03/RF-04. Production must set JUVAL_AUTH_MODE=oidc (ADR-028 provider,
    # ADR-031 hosting; the ADR-022 citation here was stale -- that ADR is
    # RECHAZADA). See docs/compliance/ACCESS_CONTROL.md.
    logger.warning(
        "JUVAL_AUTH_MODE=disabled -- every endpoint is UNAUTHENTICATED. "
        "This is acceptable only for local development; production must set "
        "JUVAL_AUTH_MODE=oidc once the ADR-034 BFF, the public issuer surface "
        "and a durable session store (ADR-036) are all in place."
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
    native_financial_evidence: bool = Form(False),
    financial_target_profit: Optional[Decimal] = Form(None),
    financial_target_profit_currency: Optional[str] = Form(None),
    financial_target_roi: Optional[Decimal] = Form(None),
    _principal=Depends(require(RUNS_CREATE)),
    _csrf: None = Depends(bff.csrf_guard),
) -> JSONResponse:
    thresholds_in = _parse_json_form(thresholds, ThresholdsIn, "thresholds")
    fees_in = _parse_json_form(fees, FeesIn, "fees")

    try:
        domain_thresholds = service.thresholds_from_in(thresholds_in)
        domain_fees = service.fees_from_in(fees_in)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _check_financial_options(persist, native_financial_evidence, financial_target_profit,
                             financial_target_profit_currency, financial_target_roi)

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

    now = service.now_utc()
    pipeline = run_pipeline_with_financial_evidence if native_financial_evidence else run_pipeline
    try:
        outcome = pipeline(
            input_path,
            domain_thresholds,
            fees=domain_fees,
            application_version=juval.__version__,
            execution_id=execution_id,
            now=now,
        )
    except _UNREADABLE_INPUT as exc:
        raise HTTPException(status_code=422, detail=_unreadable_input_detail(filename, exc)) from exc
    finally:
        input_path.unlink(missing_ok=True)  # never keep the uploaded input around (Sec. 12)
    run, records = (outcome.run, outcome.records) if native_financial_evidence else outcome

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
    financial = None
    if persist:
        store = _execution_run_store()
        if store is None:
            raise HTTPException(
                status_code=500,
                detail="persist=true was requested but JUVAL_EXECUTION_DB_PATH is not configured",
            )
        if native_financial_evidence:
            # One transaction for run, snapshots, documents and diagnostics: a
            # failure raises (generic 500) and nothing of this run is persisted.
            financial = _persist_native_financial(
                store, outcome, record_snapshots, now,
                financial_target_profit, financial_target_profit_currency, financial_target_roi)
        else:
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
        records=[service.record_out(s) for s in record_snapshots],
        financial=financial,
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.post("/api/v1/runs/preview", response_model=ImportPreviewResponse)
async def preview_run_input(
    file: UploadFile = File(...),
    _principal=Depends(require(RUNS_CREATE)),
    _csrf: None = Depends(bff.csrf_guard),
) -> JSONResponse:
    """Validate-only: how the importer reads this file, before any run.

    Same upload rules as POST /api/v1/runs (type, sanitized name, size) and the
    same importer. No processing, decision, ExecutionRun or persistence; the
    upload lives in a temporary directory removed before the response. A file
    whose headers are fatally wrong is a 200 with `fatal: true` -- reporting
    that is the purpose of a preview -- while an unreadable file is a 422.
    """
    filename = safe_input_filename(file.filename)
    body = await file.read()
    max_bytes = service.max_upload_bytes()
    if max_bytes is not None and len(body) > max_bytes:
        raise HTTPException(status_code=413,
                            detail=f"uploaded file exceeds the configured limit of {max_bytes} bytes (JUVAL_MAX_UPLOAD_BYTES)")
    service.storage_dir().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=service.storage_dir(), prefix="preview-") as scratch:
        input_path = Path(scratch) / filename
        input_path.write_bytes(body)
        try:
            preview = preview_import(input_path, now=service.now_utc())
        except _UNREADABLE_INPUT as exc:
            raise HTTPException(status_code=422, detail=_unreadable_input_detail(filename, exc)) from exc
    response = ImportPreviewResponse(
        input_filename=preview.input_filename,
        input_hash=preview.input_hash,
        fatal=preview.fatal,
        rows_scanned=preview.rows_scanned,
        rows_skipped_blank=preview.rows_skipped_blank,
        records_importable=preview.records_importable,
        columns=[vars(column) for column in preview.columns],
        missing_required_columns=[{"canonical": s.canonical, "target": s.target} for s in preview.missing_required_columns],
        issue_counts=[{"level": level, "code": code, "count": n} for level, code, n in preview.issue_counts],
        issues=[{"level": i.level.value, "code": i.code, "message": i.message, "field": i.field, "record_ref": i.record_ref}
                for i in preview.issues],
        issues_total=preview.issues_total,
        issues_truncated=preview.issues_total > len(preview.issues),
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _check_financial_options(persist, native, target_profit, target_profit_currency, target_roi) -> None:
    """Same rules as the CLI's opt-in (ADR-047): nothing is inferred or defaulted."""
    if native and not persist:
        raise HTTPException(status_code=422, detail="native_financial_evidence requires persist=true")
    if not native and any(v is not None for v in (target_profit, target_profit_currency, target_roi)):
        raise HTTPException(status_code=422, detail="financial_target_* fields require native_financial_evidence=true")
    if (target_profit is None) != (target_profit_currency is None):
        raise HTTPException(status_code=422,
                            detail="financial_target_profit and financial_target_profit_currency go together")
    for name, value in (("financial_target_profit", target_profit), ("financial_target_roi", target_roi)):
        if value is not None and not value.is_finite():
            raise HTTPException(status_code=422, detail=f"{name} must be a finite decimal")


def _persist_native_financial(store, outcome, snapshots, now, target_profit, target_profit_currency,
                              target_roi) -> RunFinancialSummaryOut:
    """Build the ADR-047 documents and save them atomically with the run."""
    documents, diagnostics, summary = _native_financial_parts(outcome, now, target_profit, target_profit_currency,
                                                              target_roi)
    save_run_with_financial_records(store, outcome.run, snapshots, documents, diagnostics)
    return summary


def _native_financial_parts(outcome, now, target_profit, target_profit_currency, target_roi):
    """The ADR-047 documents and diagnostics of one run, built with the CLI's own
    application functions; writes nothing and never changes records or decisions."""
    def declared(value, unit, field):
        return declared_financial_target(value, unit, source="juval-api", method=f"request field {field}",
                                         retrieved_at=now)

    profit = declared(target_profit, target_profit_currency, "financial_target_profit") if target_profit is not None else None
    roi = declared(target_roi, "ratio", "financial_target_roi") if target_roi is not None else None
    documents = build_financial_documents(outcome, calculated_at=now, target_profit=profit, target_roi=roi,
                                          application_version=outcome.run.application_version)
    diagnostics = capture_diagnostics_sets(outcome)
    return documents, diagnostics, RunFinancialSummaryOut(
        captures=len(outcome.financial_evidence),
        documents=len(documents),
        without_scenario=sum(1 for item in outcome.financial_evidence if item.evidence is None),
        capture_diagnostics_sets=len(diagnostics),
        capture_problems=sum(len(item.problems) for item in outcome.financial_evidence),
    )


@app.post("/api/v1/batches", response_model=BatchResponse)
async def create_batch(
    files: list[UploadFile] = File(...),
    thresholds: str = Form(...),
    fees: str = Form(...),
    persist: bool = Form(False),
    native_financial_evidence: bool = Form(False),
    financial_target_profit: Optional[Decimal] = Form(None),
    financial_target_profit_currency: Optional[str] = Form(None),
    financial_target_roi: Optional[Decimal] = Form(None),
    _principal=Depends(require(RUNS_CREATE)),
    _csrf: None = Depends(bff.csrf_guard),
) -> JSONResponse:
    """Process up to ten independent child runs as one auditable batch.

    Each file is XLSX or CSV -- one tabular contract, two encodings
    (ADR-026); the importer dispatches on suffix and rejects anything else.

    ExecutionRun remains one file/one deterministic execution. Batch only
    groups child outcomes; it does not merge snapshots or alter Catalog scope.

    The ADR-047 opt-in (`native_financial_evidence` + `financial_target_*`)
    has the single-file endpoint's fields, rules and functions. Each child's
    documents and diagnostics are keyed by its own execution_id, so nothing
    is shared between files. With persist=true the batch, every child run
    and their records, documents and diagnostics are saved in one single
    transaction for the whole batch (ADR-050): all of it or nothing. The
    response is unchanged; documents are read per child execution (§2e).
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
    _check_financial_options(persist, native_financial_evidence, financial_target_profit,
                             financial_target_profit_currency, financial_target_roi)
    pipeline = run_pipeline_with_financial_evidence if native_financial_evidence else run_pipeline

    batch_id = service.new_execution_id()
    created_at = service.now_utc()
    results: list[BatchFile] = []
    children: list[BatchChild] = []
    exports: list[tuple[int, str, tuple]] = []      # (index in results, execution_id, records) to export after commit
    max_bytes = service.max_upload_bytes()
    store = _execution_run_store() if persist else None
    if persist and store is None:
        raise HTTPException(status_code=500, detail="persist=true was requested but the execution store is not configured")

    # 1. Process every file; nothing is written to the store here (ADR-050 D1).
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
                outcome = pipeline(input_path, domain_thresholds, fees=domain_fees, application_version=juval.__version__, execution_id=execution_id, now=now)
            except _UNREADABLE_INPUT as exc:
                children.append(BatchChild(_failed_run(execution_id=execution_id, input_path=input_path, application_version=juval.__version__, now=now)))
                results.append(BatchFile(ordinal, filename, upload.content_type, len(body), BatchFileStatus.FAILED, execution_id, errors=(_unreadable_input_detail(filename, exc),)))
                continue
        finally:
            input_path.unlink(missing_ok=True)
        run, records = (outcome.run, outcome.records) if native_financial_evidence else outcome
        snapshots = [record_to_snapshot(record) for record in records]
        documents, diagnostics = (), ()
        if native_financial_evidence:
            documents, diagnostics, _ = _native_financial_parts(outcome, now, financial_target_profit,
                                                                financial_target_profit_currency, financial_target_roi)
        children.append(BatchChild(run, snapshots, documents, diagnostics))
        if run.status != ExecutionStatus.FAILED:
            exports.append((len(results), execution_id, records))
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

    batch = Batch(batch_id=batch_id, created_at=created_at, status=aggregate_batch_status(tuple(results)), files=tuple(results))

    # 2. One transaction for every child run, its records, documents and
    #    diagnostics, and the batch: all of it or nothing (ADR-050 D2). A
    #    failure is the existing generic 500 (D4 provisional) and leaves no row.
    if persist and store is not None:
        if not hasattr(store, "save_batch_with_runs"):
            raise HTTPException(status_code=500, detail="configured execution store does not support batch persistence")
        save_batch_with_runs(store, batch, children)

    # 3. Exports only after the commit (D3). A failed export never undoes what
    #    was stored; it is reported as a warning on that file in this response.
    response_files = list(results)
    for index, execution_id, records in exports:
        try:
            export_excel(records, service.output_path(execution_id))
        except Exception:
            logger.exception("batch %s: XLSX export failed for %s", batch_id, execution_id)
            item = response_files[index]
            response_files[index] = replace(item, warnings=(*item.warnings, EXPORT_FAILED_WARNING))
    return JSONResponse(status_code=200, content=_batch_response(replace(batch, files=tuple(response_files)), persisted=persist).model_dump(mode="json"))


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
    decisions = store.decision_counts([r.execution_id for r in runs])
    response = RunsListResponse(items=[service.run_to_summary(r, decisions.get(r.execution_id)) for r in runs])
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}", response_model=RunSummaryOut)
async def get_run(execution_id: str, _principal=Depends(require(RUNS_READ))) -> JSONResponse:
    store = _require_execution_run_store()
    run = store.load_execution_run(execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    response = service.run_to_summary(run, store.decision_counts([execution_id]).get(execution_id))
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/records", response_model=RunRecordsResponse)
async def get_run_records(
    execution_id: str,
    limit: int = Query(_RECORDS_LIST_DEFAULT_LIMIT, ge=1, le=_RECORDS_LIST_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, max_length=200),
    brand: Optional[str] = Query(None, min_length=1, max_length=200),
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
    review_classification: Optional[Literal["PENDING_DEMAND_VERIFICATION"]] = None,
    _principal=Depends(require(RUNS_READ)),
) -> JSONResponse:
    store = _require_execution_run_store()
    run = store.load_execution_run(execution_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")

    page = store.list_records(
        execution_id,
        RecordSnapshotQuery(limit=limit, offset=offset, search=search, brand=brand, decision=decision, sort=sort, direction=direction, min_roi=min_roi, min_profit=min_profit, min_margin=min_margin, confidence=confidence, hazmat=hazmat, bulky=bulky, provenance_field=provenance_field, provenance_status=provenance_status, review_classification=review_classification),
    )
    response = RunRecordsResponse(
        execution_id=execution_id,
        records=[service.record_out(snapshot) for snapshot in page.items],
        pagination=RecordPaginationOut(limit=limit, offset=offset, total=page.total, has_more=offset + len(page.items) < page.total),
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _query_from_params(*, search, brand, decision, sort, direction, min_roi, min_profit, min_margin, confidence, hazmat, bulky, provenance_field, provenance_status, review_classification, limit):
    return RecordSnapshotQuery(limit=limit, offset=0, search=search, brand=brand, decision=decision, sort=sort, direction=direction, min_roi=min_roi, min_profit=min_profit, min_margin=min_margin, confidence=confidence, hazmat=hazmat, bulky=bulky, provenance_field=provenance_field, provenance_status=provenance_status, review_classification=review_classification)


@app.get("/api/v1/runs/{execution_id}/records/export")
async def export_filtered_records(
    execution_id: str,
    search: Optional[str] = Query(None, max_length=200),
    brand: Optional[str] = Query(None, min_length=1, max_length=200),
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
    review_classification: Optional[Literal["PENDING_DEMAND_VERIFICATION"]] = None,
    _principal=Depends(require(RUNS_EXPORT)),
) -> FileResponse:
    store = _require_execution_run_store()
    if store.load_execution_run(execution_id) is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    query = _query_from_params(search=search, brand=brand, decision=decision, sort=sort, direction=direction, min_roi=min_roi, min_profit=min_profit, min_margin=min_margin, confidence=confidence, hazmat=hazmat, bulky=bulky, provenance_field=provenance_field, provenance_status=provenance_status, review_classification=review_classification, limit=_EXPORT_MAX_RECORDS)
    page = store.list_records(execution_id, query)
    path = service.run_dir(execution_id) / "filtered-export.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "catalog_export"
    headers = ("record_ref", "supplier_sku", "asin", "asin_status", "title", "brand", "selling_price", "selling_price_status", "cog", "profit", "profit_status", "roi", "roi_status", "margin", "margin_status", "hazmat_status", "hazmat_severity", "bulky_status", "bulky_severity", "decision", "review_classification", "issue_count", "issues", *DEMAND_EXPORT_HEADERS, *SUGGESTED_PRICE_EXPORT_HEADERS, *SEVERITY_PROVENANCE_EXPORT_HEADERS)
    append_literal_row(sheet, list(headers))
    for record in page.items:
        def value(field): return record.get(field, {}).get("value") if isinstance(record.get(field), dict) else record.get(field)
        def status(field): return record.get(field, {}).get("status") if isinstance(record.get(field), dict) else None
        append_literal_row(sheet, [record.get("record_ref"), record.get("supplier_sku"), value("asin"), status("asin"), value("title"), value("brand"), value("selling_price"), status("selling_price"), record.get("cog"), value("profit"), status("profit"), value("roi"), status("roi"), value("margin"), status("margin"), record.get("hazmat_status"), record.get("hazmat_severity"), record.get("bulky_status"), record.get("bulky_severity"), record.get("decision"), classify_review(record) or "", record.get("issue_count", 0), " ; ".join(record.get("issues", [])), *demand_export_cells(record), *suggested_price_export_cells(record), *severity_provenance_cells(record)])
    metadata = workbook.create_sheet("query_metadata")
    append_literal_row(metadata, ["execution_id", execution_id])
    append_literal_row(metadata, ["generated_at", datetime.now(timezone.utc).isoformat()])
    append_literal_row(metadata, ["filters", json.dumps({"search": search, "brand": brand, "decision": decision, "min_roi": str(min_roi) if min_roi is not None else None, "min_profit": str(min_profit) if min_profit is not None else None, "min_margin": str(min_margin) if min_margin is not None else None, "confidence": confidence, "hazmat": hazmat, "bulky": bulky, "provenance_field": provenance_field, "provenance_status": provenance_status, "review_classification": review_classification}, sort_keys=True)])
    append_literal_row(metadata, ["sort", sort])
    append_literal_row(metadata, ["direction", direction])
    # State the unit explicitly: min_roi/min_margin are canonical ratios, so
    # 0.3 in this sheet is the 30% the operator typed. Without this line a
    # reader could take 0.3 for 0.3% and misjudge a sourcing threshold.
    append_literal_row(metadata, ["units", "min_roi and min_margin are ratios (0.30 = 30%); min_profit and prices are absolute currency amounts"])
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
    return JSONResponse(status_code=200, content=service.record_out(snapshot).model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/analytics", response_model=RunAnalyticsOut)
async def get_run_analytics(execution_id: str, _principal=Depends(require(RUNS_READ))) -> JSONResponse:
    store = _require_execution_run_store()
    if store.load_execution_run(execution_id) is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    response = RunAnalyticsOut(execution_id=execution_id, **store.get_run_analytics(execution_id))
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


def _stored(payload: Optional[dict]) -> Optional[StoredPayloadOut]:
    return StoredPayloadOut(format=payload["format"], version=payload["version"], payload=payload) if payload is not None else None


def _financial_out(store: ExecutionRunStore, execution_id: str, snapshots: list[dict]) -> list[RecordFinancialOut]:
    """Validated stored payloads of these records, read in one batch, or an
    HTTP error that never passes for absence and never echoes stored content
    or storage internals."""
    try:
        reports = record_financial_reports(store, execution_id, snapshots)
    except FinancialStorageUnavailable:
        logger.error("financial tables missing for execution_id=%s (migration not applied)", execution_id)
        raise HTTPException(status_code=503, detail="financial persistence is not available on this deployment")
    except (FinancialSerializationError, FinancialRecordIntegrityError) as exc:
        logger.error("stored financial data failed validation: execution_id=%s error=%s",
                     execution_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="stored financial data failed validation")
    return [RecordFinancialOut(execution_id=execution_id, record_ref=report.record_ref,
                               financial_document=_stored(report.document_payload),
                               capture_diagnostics=_stored(report.diagnostics_payload),
                               inconsistencies=list(report.inconsistencies))
            for report in reports]


@app.get("/api/v1/runs/{execution_id}/financial", response_model=RunFinancialResponse)
async def get_run_financial(
    execution_id: str,
    limit: int = Query(_RECORDS_LIST_DEFAULT_LIMIT, ge=1, le=_RECORDS_LIST_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    _principal=Depends(require(RUNS_READ)),
) -> JSONResponse:
    """Stored ADR-047 financial documents and capture diagnostics of a run's
    records, one entry per record snapshot in `record_ref` order (the Catalog
    default), paginated like `/records`. Read-only: nothing is calculated."""
    store = _require_execution_run_store()
    if store.load_execution_run(execution_id) is None:
        raise HTTPException(status_code=404, detail="unknown execution_id")
    page = store.list_records(execution_id, RecordSnapshotQuery(limit=limit, offset=offset))
    response = RunFinancialResponse(
        execution_id=execution_id,
        records=_financial_out(store, execution_id, page.items),
        pagination=RecordPaginationOut(limit=limit, offset=offset, total=page.total,
                                       has_more=offset + len(page.items) < page.total),
    )
    return JSONResponse(status_code=200, content=response.model_dump(mode="json"))


@app.get("/api/v1/runs/{execution_id}/records/{record_ref}/financial", response_model=RecordFinancialOut)
async def get_record_financial(
    execution_id: str,
    record_ref: str,
    _principal=Depends(require(RUNS_READ)),
) -> JSONResponse:
    """Stored ADR-047 payloads of one `(execution_id, record_ref)`. Unknown run
    and unknown record share the non-enumerating 404 of the record endpoint;
    a known record with nothing stored is 200 with nulls, not 404."""
    store = _require_execution_run_store()
    snapshot = store.load_record(execution_id, record_ref) if store.load_execution_run(execution_id) else None
    if snapshot is None:
        raise HTTPException(status_code=404, detail="unknown record for execution")
    [record] = _financial_out(store, execution_id, [snapshot])
    return JSONResponse(status_code=200, content=record.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error processing %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
