"""Severity provenance (ADR-020) in the .xlsx exports.

Three exports, two models:
- run workbook: CLI and the API `/download` both call `export_excel` on
  SourcingRecords -- the same function, so the same columns;
- catalog export (`/records/export`): built from stored snapshots, with its own
  narrower column set.
Both take the four cells from one derivation (`record_snapshot.severity_provenance`),
append them last and leave every earlier column where it was.
CSV is an input format only (ADR-026): there is no CSV export to extend.
"""

import io
import json

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.infrastructure.excel.exporter import HEADERS
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app
from .api_lab import LAB_OWNER, LOOPBACK
from juval.interfaces.cli.main import main as cli_main

NEW = ("hazmat_severity_status", "hazmat_severity_source_type", "bulky_severity_status", "bulky_severity_source_type")
# Run workbook headers as of d9f8085, before this change -- order and names pinned.
PREVIOUS_RUN_HEADERS = (
    "record_ref", "marketplace", "supplier_sku", "asin", "asin_status", "asin_source", "upc", "upc_status", "title",
    "brand", "category", "weight_lb", "weight_status", "height_in", "width_in", "length_in", "cog", "shipping_per_unit",
    "selling_price", "selling_price_status", "selling_price_source", "profit", "profit_status", "roi", "roi_status",
    "margin", "margin_status", "break_even_price", "break_even_price_status", "max_cog_target_profit",
    "max_cog_target_profit_status", "max_cog_target_roi", "max_cog_target_roi_status", "hazmat_status",
    "hazmat_severity", "bulky_status", "bulky_severity", "decision", "decision_reasons", "issue_count", "issues",
    "demand_evidence_state", "demand_declared_units", "demand_status", "demand_raw_value", "demand_window_start",
    "demand_window_end", "demand_observed_at", "demand_population", "demand_method", "demand_source_reference",
    "demand_diagnostics", "supplier_suggested_price_state", "supplier_suggested_price",
    "supplier_suggested_price_currency", "supplier_suggested_price_status", "supplier_suggested_price_raw",
    "supplier_suggested_price_currency_raw", "supplier_suggested_price_source_reference",
    "supplier_suggested_price_diagnostics",
)
PREVIOUS_CATALOG_HEADERS_START = (
    "record_ref", "supplier_sku", "asin", "asin_status", "title", "brand", "selling_price", "selling_price_status",
    "cog", "profit", "profit_status", "roi", "roi_status", "margin", "margin_status", "hazmat_status",
    "hazmat_severity", "bulky_status", "bulky_severity", "decision", "review_classification", "issue_count", "issues",
)
# hazmat cell -> (severity status, source type); bulky is "no" on every row.
CASES = {
    "yes": ("INFERRED", "CALCULATED"),       # internal policy HIGH (ADR-044)
    "no": ("VERIFIED", "SUPPLIER_FILE"),     # NONE of an absence declared in the file
    "": ("NOT_FOUND", "NOT_FOUND"),          # blank: nothing assumed
    "maybe": ("INVALID", "SUPPLIER_FILE"),   # unreadable cell
}
THRESHOLDS = {"target_profit": "3", "target_roi": "0.3", "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "MEDIUM"}
FEES = {"referral_fee": "0", "referral_fee_rate": "0.15", "fulfillment_fee": "5"}


def _input(tmp_path):
    lines = ["marketplace,asin,sku,cost,selling_price,hazmat,bulky"] + [
        f"US,B00000000{i},S{i},10,40,{cell},no" for i, cell in enumerate(CASES, start=1)]
    path = tmp_path / "risk.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return path


def _rows(content, sheet=None):
    workbook = openpyxl.load_workbook(io.BytesIO(content) if isinstance(content, bytes) else content)
    rows = list((workbook[sheet] if sheet else workbook.active).iter_rows(values_only=True))
    return rows[0], rows[1:]


def _cells(header, body):
    """record_ref -> the four new cells."""
    ref = header.index("record_ref")
    return {row[ref]: tuple(row[header.index(name)] for name in NEW) for row in body}


EXPECTED = [status + ("VERIFIED", "SUPPLIER_FILE") for status in CASES.values()]


@pytest.fixture
def client(tmp_path, monkeypatch, auth_lab):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    return TestClient(app, **LOOPBACK)


def _upload(client, path):
    response = client.post("/api/v1/runs", files={"file": (path.name, path.read_bytes(), "text/csv")},
                           data={"thresholds": json.dumps(THRESHOLDS), "fees": json.dumps(FEES), "persist": "true"})
    assert response.status_code == 200
    return response.json()


# -- Headers --------------------------------------------------------------------

def test_run_workbook_headers_append_the_four_columns_last():
    assert HEADERS == PREVIOUS_RUN_HEADERS + NEW


def test_catalog_export_headers_append_the_four_columns_last(client, tmp_path):
    run_id = _upload(client, _input(tmp_path))["execution_id"]
    header, _ = _rows(client.get(f"/api/v1/runs/{run_id}/records/export").content, "catalog_export")

    assert header[:len(PREVIOUS_CATALOG_HEADERS_START)] == PREVIOUS_CATALOG_HEADERS_START
    assert header[-4:] == NEW
    assert header[len(PREVIOUS_CATALOG_HEADERS_START):-4][0] == "demand_evidence_state"  # evidence groups unmoved


# -- Values, per export ------------------------------------------------------------

def test_cli_workbook_values(tmp_path):
    output = tmp_path / "out.xlsx"
    assert cli_main([str(_input(tmp_path)), str(output), "--target-profit", "3", "--target-roi", "0.3",
                     "--max-risk-severity", "MEDIUM", "--referral-fee", "0", "--referral-fee-rate", "0.15",
                     "--fulfillment-fee", "5"]) == 0
    header, body = _rows(output)

    assert list(_cells(header, body).values()) == EXPECTED
    # The plain severity columns are unchanged next to them.
    assert [row[header.index("hazmat_severity")] for row in body] == ["HIGH", "NONE", None, None]


def test_api_download_values_match_the_api_record_fields(client, tmp_path):
    body_json = _upload(client, _input(tmp_path))
    header, body = _rows(client.get(f"/api/v1/runs/{body_json['execution_id']}/download").content)

    exported = _cells(header, body)
    assert list(exported.values()) == EXPECTED
    for record in body_json["records"]:
        assert exported[record["record_ref"]] == tuple(record[name] for name in NEW)


def test_catalog_export_values_match_the_api_record_fields(client, tmp_path):
    body_json = _upload(client, _input(tmp_path))
    run_id = body_json["execution_id"]
    header, body = _rows(client.get(f"/api/v1/runs/{run_id}/records/export",
                                    params={"confidence": "INCLUDE_INFERRED"}).content, "catalog_export")
    stored = client.get(f"/api/v1/runs/{run_id}/records", params={"limit": 10, "confidence": "INCLUDE_INFERRED"}).json()["records"]

    exported = _cells(header, body)
    assert len(exported) == len(CASES)
    for record in stored:
        assert exported[record["record_ref"]] == tuple(record[name] for name in NEW)


# -- Parity -----------------------------------------------------------------------------

def test_cli_api_download_and_catalog_export_agree(client, tmp_path):
    path = _input(tmp_path)
    output = tmp_path / "cli.xlsx"
    cli_main([str(path), str(output), "--target-profit", "3", "--target-roi", "0.3", "--max-risk-severity", "MEDIUM",
              "--referral-fee", "0", "--referral-fee-rate", "0.15", "--fulfillment-fee", "5"])
    run_id = _upload(client, path)["execution_id"]

    cli = _rows(output)
    download = _rows(client.get(f"/api/v1/runs/{run_id}/download").content)
    catalog = _rows(client.get(f"/api/v1/runs/{run_id}/records/export",
                               params={"confidence": "INCLUDE_INFERRED"}).content, "catalog_export")

    # Same function, same model: the whole run workbook is identical.
    assert cli == download
    # Different model (snapshots), same derivation: the four cells agree.
    assert _cells(*catalog) == _cells(*cli)


# -- Historical snapshots ---------------------------------------------------------------

def test_historical_snapshot_exports_empty_cells_never_verified(client, tmp_path):
    from .test_record_snapshot_pagination import run, snapshot

    old = snapshot(0)  # hazmat_status ABSENT, written before the severity provenance existed
    assert not set(NEW) & set(old)
    SqliteExecutionRunStore(tmp_path / "runs.db").save_execution_run(run(), [old], owner=LAB_OWNER)

    header, body = _rows(client.get("/api/v1/runs/run-page/records/export").content, "catalog_export")
    assert _cells(header, body) == {old["record_ref"]: (None, None, None, None)}
    assert body[0][header.index("hazmat_status")] == "ABSENT"  # existing column untouched
    record = client.get(f"/api/v1/runs/run-page/records/{old['record_ref']}").json()
    assert tuple(record[name] for name in NEW) == (None, None, None, None)
