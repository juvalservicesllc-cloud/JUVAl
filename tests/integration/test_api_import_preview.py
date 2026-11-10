"""POST /api/v1/runs/preview -- validate-only importer verdict. Synthetic data only."""

from __future__ import annotations

import hashlib
import io
import sqlite3
from datetime import datetime, timezone

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.application.import_preview import PREVIEW_ISSUE_LIMIT, preview_import
from juval.infrastructure.excel.importer import import_file
from juval.interfaces.api.main import app
from .api_lab import LOOPBACK, add_member

from .test_api_auth import ISSUER, bearer, enable_auth, keypair, make_token  # noqa: F401 (fixtures)

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)
HEADERS = ["SKU", "Marketplace", "ASIN", "Cost", "Brand", "brand", "Mystery Column", "", "fin_currency"]
ROWS = [
    ["S-1", "US", "B000000001", "4.50", "Acme", "Other", "x", "", "USD"],
    ["S-2", "US", "not-an-asin", "3.00", "Acme", "", "", "", "USD"],
]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def csv_bytes(headers=HEADERS, rows=ROWS) -> bytes:
    return "\n".join(",".join(cells) for cells in [headers, *rows]).encode()


def xlsx_bytes(headers=HEADERS, rows=ROWS) -> bytes:
    workbook = openpyxl.Workbook()
    for cells in [headers, *rows]:
        workbook.active.append([cell or None for cell in cells])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch, auth_lab):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.delenv("JUVAL_MAX_UPLOAD_BYTES", raising=False)
    return TestClient(app, **LOOPBACK)


def preview(client, content: bytes, name="supplier.csv", content_type="text/csv", **kwargs):
    return client.post("/api/v1/runs/preview", files={"file": (name, content, content_type)}, **kwargs)


def test_every_header_is_reported_with_the_importers_decision(client):
    response = preview(client, csv_bytes())
    assert response.status_code == 200
    columns = {c["position"]: c for c in response.json()["columns"]}

    assert len(columns) == len(HEADERS)
    assert columns[1] == {"position": 1, "header": "SKU", "normalized": "sku", "status": "MAPPED",
                               "canonical": "supplier_sku", "alias_of": "supplier_sku",
                               "target": "product.identification.supplier_sku", "required": False, "group": "core"}
    assert (columns[3]["status"], columns[3]["canonical"], columns[3]["required"], columns[3]["alias_of"]) == ("MAPPED", "asin", True, None)
    assert (columns[5]["status"], columns[5]["target"]) == ("MAPPED", "product.info.brand")   # first occurrence wins
    assert (columns[6]["status"], columns[6]["canonical"], columns[6]["target"], columns[6]["group"]) == ("DUPLICATE", "brand", None, None)
    assert (columns[7]["status"], columns[7]["canonical"], columns[7]["target"]) == ("UNKNOWN", None, None)
    assert (columns[8]["status"], columns[8]["header"]) == ("BLANK", "")
    assert (columns[9]["status"], columns[9]["group"]) == ("MAPPED", "native_financial_evidence")


def test_preview_reports_exactly_what_a_run_would_import(client, tmp_path):
    path = tmp_path / "supplier.csv"
    path.write_bytes(csv_bytes())
    imported = import_file(path, now=NOW)
    body = preview(client, csv_bytes()).json()

    assert body["fatal"] is False
    # An INVALID ASIN is kept on its record with a RECORD_ERROR issue, not dropped.
    assert body["records_importable"] == len(imported.records) == 2
    assert {"level": "RECORD_ERROR", "code": "INVALID_ASIN_FORMAT", "count": 1} in body["issue_counts"]
    assert body["rows_scanned"] == imported.rows_scanned == 2
    assert [(i["level"], i["code"], i["field"], i["record_ref"]) for i in body["issues"]] == \
           [(i.level.value, i.code, i.field, i.record_ref) for i in imported.issues]
    assert body["issues_total"] == len(imported.issues) and body["issues_truncated"] is False
    assert sum(c["count"] for c in body["issue_counts"]) == body["issues_total"]
    assert body["input_hash"] == hashlib.sha256(csv_bytes()).hexdigest()
    assert body["input_filename"] == "supplier.csv"


def test_csv_and_xlsx_with_the_same_headers_get_the_same_verdict(client):
    as_csv = preview(client, csv_bytes()).json()
    as_xlsx = preview(client, xlsx_bytes(), name="supplier.xlsx", content_type=XLSX).json()
    ignore = {"input_filename", "input_hash"}
    assert {k: v for k, v in as_csv.items() if k not in ignore} == {k: v for k, v in as_xlsx.items() if k not in ignore}


def test_missing_required_columns_are_a_fatal_200_not_an_error(client):
    body = preview(client, csv_bytes(headers=["SKU", "Brand"], rows=[["S-1", "Acme"]])).json()
    assert body["fatal"] is True
    assert [c["canonical"] for c in body["missing_required_columns"]] == ["marketplace", "asin", "cost"]
    assert all(c["target"] for c in body["missing_required_columns"])
    assert body["records_importable"] == 0 and body["rows_scanned"] == 0
    assert {c["code"] for c in body["issue_counts"]} == {"MISSING_REQUIRED_COLUMN"}
    assert [c["status"] for c in body["columns"]] == ["MAPPED", "MAPPED"]


def test_an_empty_file_reports_empty_file_and_no_evaluated_columns(client):
    body = preview(client, b"").json()
    assert body["fatal"] is True
    assert body["columns"] == [] and body["missing_required_columns"] == []
    assert [i["code"] for i in body["issues"]] == ["EMPTY_FILE"]


def test_issue_list_is_bounded_but_counts_cover_every_issue(client):
    rows = [[f"S-{n}", "US", "bad", "1", "Acme", "", "", "", "USD"] for n in range(PREVIEW_ISSUE_LIMIT + 20)]
    body = preview(client, csv_bytes(rows=rows)).json()
    assert body["issues_total"] > PREVIEW_ISSUE_LIMIT
    assert len(body["issues"]) == PREVIEW_ISSUE_LIMIT and body["issues_truncated"] is True
    assert sum(c["count"] for c in body["issue_counts"]) == body["issues_total"]


def test_preview_stores_nothing_and_leaves_no_upload_behind(client, tmp_path):
    assert preview(client, csv_bytes()).status_code == 200
    assert preview(client, xlsx_bytes(), name="s.xlsx", content_type=XLSX).status_code == 200
    db = tmp_path / "runs.db"
    if db.exists():
        with sqlite3.connect(db) as conn:
            tables = [name for (name,) in conn.execute("select name from sqlite_master where type='table'")]
            assert all(conn.execute(f"select count(*) from {t}").fetchone()[0] == 0 for t in tables)
    assert [p for p in (tmp_path / "storage").rglob("*") if p.is_file()] == []


@pytest.mark.parametrize("name,content,status", [
    ("broken.xlsx", b"not a workbook", 422),
    ("notes.txt", b"a,b\n1,2", 422),
    ("latin1.csv", "ASIN,Café\n".encode("latin-1"), 422),
])
def test_unreadable_or_unsupported_files_are_rejected(client, tmp_path, name, content, status):
    assert preview(client, content, name=name).status_code == status
    assert [p for p in (tmp_path / "storage").rglob("*") if p.is_file()] == []


def test_upload_limit_applies(client, monkeypatch):
    monkeypatch.setenv("JUVAL_MAX_UPLOAD_BYTES", "10")
    assert preview(client, csv_bytes()).status_code == 413


def test_uploaded_filename_is_sanitized(client):
    body = preview(client, csv_bytes(), name="../../etc/su<p>plier.csv").json()
    assert body["input_filename"] == "su_p_plier.csv"


def test_preview_needs_the_permission_to_create_runs(enable_auth, keypair, client, tmp_path):  # noqa: F811
    add_member(tmp_path / "runs.db", ISSUER)  # ADR-056: preview is a data route too
    assert preview(client, csv_bytes()).status_code == 401
    viewer = make_token(keypair, roles=("viewer",))
    assert preview(client, csv_bytes(), headers=bearer(viewer)).status_code == 403
    operator = make_token(keypair, roles=("operator",))
    assert preview(client, csv_bytes(), headers=bearer(operator)).status_code == 200


def test_application_preview_matches_the_endpoint(client, tmp_path):
    path = tmp_path / "supplier.csv"
    path.write_bytes(csv_bytes())
    result = preview_import(path, now=NOW)
    body = preview(client, csv_bytes()).json()
    assert [c.status for c in result.columns] == [c["status"] for c in body["columns"]]
    assert result.records_importable == body["records_importable"]
