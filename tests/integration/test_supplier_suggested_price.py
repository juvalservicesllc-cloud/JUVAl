"""Supplier suggested price (ADR-053, GOLDEN 17).

Evidence only: every test that checks a decision checks that it did NOT
change. Synthetic files only; no value here is a real supplier price.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.application.import_preview import preview_import
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.application.suggested_price_evidence import suggested_price_export_cells, suggested_price_state
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.provenance import FieldValue, SourceType
from juval.domain.risk import Severity
from juval.domain.supplier_price import SupplierSuggestedPrice
from juval.infrastructure.excel.exporter import SUGGESTED_PRICE_EXPORT_HEADERS, suggested_price_cells_from_capture
from juval.infrastructure.excel.importer import SUPPORTED_INPUT_SUFFIXES, import_file
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app
from .api_lab import LOOPBACK

NOW = datetime(2026, 10, 27, 15, tzinfo=timezone.utc)
THRESHOLDS = Thresholds(target_profit=Decimal("5"), target_roi=Decimal("0"), minimum_estimated_monthly_sales=0,
                        maximum_risk_severity=Severity.CRITICAL, allow_restricted=True, allow_approval_required=True,
                        allow_unknown_risk=True)
FEES = FeeInputs(referral_fee=Decimal("1"), referral_fee_rate=Decimal("0.15"))
BASE = {"marketplace": "US", "asin": "B000000001", "cost": "3", "selling_price": "30", "hazmat": "false", "bulky": "false"}
PRICE = {"supplier_suggested_price": "24.99", "supplier_suggested_price_currency": "USD"}


def write_csv(tmp_path, rows, name="price.csv"):
    headers = list(dict.fromkeys(k for row in rows for k in row))
    path = tmp_path / name
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") for h in headers])
    return path


def records(path):
    _, out = run_pipeline(path, THRESHOLDS, fees=FEES, application_version="test", execution_id="g17", now=NOW)
    return out


def capture(tmp_path, **cells):
    [record] = records(write_csv(tmp_path, [{**BASE, **cells}]))
    return record, record_to_snapshot(record)["supplier_suggested_price"]


def codes(document):
    return [d["code"] for d in document["diagnostics"]]


# -- the mandatory guarantee ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("price", [PRICE, {**PRICE, "supplier_suggested_price": "99999"},
                                   {**PRICE, "supplier_suggested_price": "-1"}, {**PRICE, "supplier_suggested_price": "x"}])
def test_decisions_reasons_profit_and_roi_are_identical_with_and_without_the_columns(tmp_path, price):
    rows = [BASE, {**BASE, "asin": "B000000002", "selling_price": "6"}, {**BASE, "asin": "B000000003", "selling_price": "2"}]
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()      # same file name: provenance must match too
    with_price = records(write_csv(tmp_path / "a", [{**row, **price} for row in rows]))
    without = records(write_csv(tmp_path / "b", rows))
    keys = ("decision", "decision_reasons", "decision_reason_codes", "profit", "roi", "margin", "break_even_price",
            "selling_price", "cog", "total_fees", "seller_proceeds", "total_cost")
    for a, b in zip(with_price, without):
        sa, sb = record_to_snapshot(a), record_to_snapshot(b)
        for key in keys:
            if key in ("profit", "roi", "margin", "break_even_price", "selling_price"):
                assert (sa[key]["value"], sa[key]["status"]) == (sb[key]["value"], sb[key]["status"]), key
            else:
                assert sa[key] == sb[key], key
        assert a.product == b.product and a.costs == b.costs          # never copied into Product or CostInputs
    assert [record_to_snapshot(r)["decision"] for r in without] == ["REVIEW", "REVIEW", "PASS"]


def test_a_buy_stays_a_buy_and_nothing_else_moves_when_the_price_is_attached():
    """The importer cannot reach BUY (no demand column feeds the engine, D7), so
    BUY is proven on a record built for the engine directly."""
    from juval.domain.costs import CostInputs
    from juval.domain.product import Demand, Identification, Price, Product, SellingPriceSource
    from juval.domain.sourcing_record import SourcingRecord
    from juval.processing.pipeline import process_record

    common = dict(source="engine-test", method="m", retrieved_at=NOW)
    price = FieldValue.verified(Decimal("30"), **common)
    product = Product(identification=Identification(asin=FieldValue.verified("B000000001", **common), marketplace="US"),
                      price=Price(current_buy_box=price, selling_price_used=price, selling_price_source=SellingPriceSource.CURRENT_BUY_BOX),
                      demand=Demand(estimated_monthly_sales=FieldValue.verified(500, **common)))
    plain = SourcingRecord(record_ref="row_1", product=product, costs=CostInputs(cog=Decimal("3")))
    suggested = SupplierSuggestedPrice(FieldValue.inferred(Decimal("99.99"), unit="USD", source_type=SourceType.USER_INPUT, **common))
    a = process_record(plain, THRESHOLDS, fees=FEES, now=NOW)
    b = process_record(replace(plain, supplier_suggested_price=suggested), THRESHOLDS, fees=FEES, now=NOW)
    sa, sb = record_to_snapshot(a), record_to_snapshot(b)
    assert sa["decision"] == "BUY"
    assert {k: v for k, v in sa.items() if k != "supplier_suggested_price"} == {k: v for k, v in sb.items() if k != "supplier_suggested_price"}


def test_processing_never_reads_the_suggested_price():
    root = pathlib.Path(__file__).resolve().parents[2] / "src" / "juval" / "processing"
    for source in root.glob("*.py"):
        text = source.read_text()
        assert "suggested" not in text and "supplier_price" not in text, source.name


# -- values --------------------------------------------------------------------------------------------------------


def test_a_valid_decimal_is_inferred_with_its_currency_and_row_column_provenance(tmp_path):
    record, document = capture(tmp_path, **PRICE)
    assert document["format"] == "juval.supplier-suggested-price" and document["version"] == 1
    amount = document["amount"]
    assert (amount["value"], amount["unit"], amount["status"], amount["raw_value"]) == ("24.99", "USD", "INFERRED", None)
    provenance = amount["provenance"]
    # The uploaded file's author is not accredited: never attributed to the supplier as a source (ADR-052 §3.6).
    assert provenance["source_type"] == "USER_INPUT" and provenance["source"] == "price.csv"
    assert provenance["method"] == "declared_in_uploaded_file"
    assert provenance["source_reference"] == "row=2;column=supplier_suggested_price"
    assert "author not accredited; not verified" in provenance["evidence"] and provenance["retrieved_at"] == NOW.isoformat()
    assert record.supplier_suggested_price.amount.value == Decimal("24.99")
    assert document["diagnostics"] == [] and not any(i.code.startswith("SUGGESTED_PRICE") for i in record.issues)


def test_the_original_header_is_the_provenance_column(tmp_path):
    _, document = capture(tmp_path, **{"Supplier Suggested Price": "10", "Supplier-Suggested-Price Currency": "EUR"})
    assert document["amount"]["provenance"]["source_reference"] == "row=2;column=Supplier Suggested Price"
    assert (document["amount"]["value"], document["amount"]["unit"]) == ("10", "EUR")


@pytest.mark.parametrize("raw", ["12.3450", "1234567890.123456789012345678", "0.0001"])
def test_the_amount_is_kept_exactly_as_declared(tmp_path, raw):
    record, document = capture(tmp_path, **{**PRICE, "supplier_suggested_price": raw})
    assert document["amount"]["value"] == raw                         # not rounded, truncated or normalised
    assert record.supplier_suggested_price.amount.value == Decimal(raw)


def test_raw_cells_keep_their_text_as_received(tmp_path):
    _, document = capture(tmp_path, **{"supplier_suggested_price": " $5 ", "supplier_suggested_price_currency": " usd "})
    assert document["amount"]["raw_value"] == " $5 " and document["currency_raw"] == " usd "
    assert [d["raw_value"] for d in document["diagnostics"]] == [" $5 ", " usd "]
    # Surrounding whitespace alone is not a defect, as for every other column.
    _, padded = capture(tmp_path, **{"supplier_suggested_price": " 24.99 ", "supplier_suggested_price_currency": " USD "})
    assert (padded["amount"]["value"], padded["amount"]["unit"], padded["amount"]["status"]) == ("24.99", "USD", "INFERRED")


@pytest.mark.parametrize("raw", ["0", "0.00", "-0", "-5", "-0.01"])
def test_zero_and_negative_are_invalid_with_their_raw_text(tmp_path, raw):
    record, document = capture(tmp_path, **{**PRICE, "supplier_suggested_price": raw})
    assert (document["amount"]["value"], document["amount"]["status"], document["amount"]["raw_value"]) == (None, "INVALID", raw)
    assert document["amount"]["unit"] is None
    assert codes(document) == ["SUGGESTED_PRICE_NOT_POSITIVE"]
    assert document["diagnostics"][0]["raw_value"] == raw and document["diagnostics"][0]["column"] == "supplier_suggested_price"
    [issue] = [i for i in record.issues if i.code == "SUGGESTED_PRICE_NOT_POSITIVE"]
    assert issue.level.value == "WARNING" and issue.field == "supplier_suggested_price"


@pytest.mark.parametrize("raw", ["$24.99", "24,99", "1,000.00", "1_000", "1e3", "approx 25", "NaN", "Infinity", "USD 24.99"])
def test_non_numeric_text_is_invalid_and_never_interpreted(tmp_path, raw):
    _, document = capture(tmp_path, **{**PRICE, "supplier_suggested_price": raw})
    assert (document["amount"]["status"], document["amount"]["raw_value"]) == ("INVALID", raw)
    assert codes(document) == ["SUGGESTED_PRICE_INVALID"]


def test_an_empty_amount_is_not_found_never_zero(tmp_path):
    record, document = capture(tmp_path, **{**PRICE, "supplier_suggested_price": ""})
    assert (document["amount"]["value"], document["amount"]["status"]) == (None, "NOT_FOUND")
    assert document["amount"]["provenance"]["evidence"] == "suggested price column present; amount cell empty"
    assert document["currency_raw"] == "USD" and document["diagnostics"] == []
    assert not any(i.code.startswith("SUGGESTED_PRICE") for i in record.issues)


def test_a_file_without_the_columns_is_not_declared_and_imports_as_before(tmp_path):
    [record] = records(write_csv(tmp_path, [BASE]))
    snapshot = record_to_snapshot(record)
    assert record.supplier_suggested_price is None
    assert snapshot["supplier_suggested_price"] is None and suggested_price_state(snapshot) == "NOT_DECLARED"


@pytest.mark.parametrize("currency", ["EUR", "GBP", "JPY"])
def test_an_explicit_currency_is_the_unit_and_is_never_converted(tmp_path, currency):
    _, document = capture(tmp_path, **{**PRICE, "supplier_suggested_price_currency": currency})
    assert (document["amount"]["value"], document["amount"]["unit"]) == ("24.99", currency)


def test_a_missing_currency_column_or_cell_leaves_the_amount_unusable(tmp_path):
    _, no_column = capture(tmp_path, supplier_suggested_price="24.99")
    for document in (no_column, capture(tmp_path, **{**PRICE, "supplier_suggested_price_currency": ""})[1]):
        assert (document["amount"]["status"], document["amount"]["raw_value"], document["amount"]["unit"]) == ("INVALID", "24.99", None)
        assert codes(document) == ["SUGGESTED_PRICE_CURRENCY_MISSING"]
    # The marketplace (US) is never read as a currency.
    assert no_column["currency_raw"] is None


@pytest.mark.parametrize("currency", ["usd", "US$", "$", "DOLLARS", "US", "€", "U5D"])
def test_an_unknown_currency_is_refused_and_kept_raw(tmp_path, currency):
    _, document = capture(tmp_path, **{**PRICE, "supplier_suggested_price_currency": currency})
    assert (document["amount"]["status"], document["amount"]["raw_value"]) == ("INVALID", "24.99")
    assert document["currency_raw"] == currency
    assert codes(document) == ["SUGGESTED_PRICE_CURRENCY_INVALID"]
    assert document["diagnostics"][0]["raw_value"] == currency
    assert document["diagnostics"][0]["column"] == "supplier_suggested_price_currency"


def test_a_currency_only_file_declares_no_amount(tmp_path):
    record, document = capture(tmp_path, supplier_suggested_price_currency="USD")
    assert (document["amount"]["status"], document["currency_raw"], document["diagnostics"]) == ("NOT_FOUND", "USD", [])
    assert record_to_snapshot(record)["decision"] == "REVIEW"


def test_a_duplicate_currency_column_uses_the_first_and_reports_the_second(tmp_path):
    path = tmp_path / "dup.csv"
    path.write_text("marketplace,asin,cost,selling_price,supplier_suggested_price,supplier_suggested_price_currency,"
                    "supplier_suggested_price_currency\nUS,B000000001,3,30,24.99,USD,EUR\n")
    result = import_file(path, now=NOW)
    assert result.records[0].supplier_suggested_price.amount.unit == "USD"
    assert any(i.code == "DUPLICATE_COLUMN" and i.field == "supplier_suggested_price_currency" for i in result.issues)


def test_every_problem_of_a_row_is_reported(tmp_path):
    _, document = capture(tmp_path, **{"supplier_suggested_price": "abc", "supplier_suggested_price_currency": "usd"})
    assert codes(document) == ["SUGGESTED_PRICE_INVALID", "SUGGESTED_PRICE_CURRENCY_INVALID"]


def test_xlsx_numeric_cells_follow_the_same_contract_as_csv(tmp_path):
    book = openpyxl.Workbook()
    sheet = book.active
    headers = [*BASE, *PRICE]
    sheet.append(headers)
    sheet.append([*BASE.values(), 24.99, "USD"])
    sheet.append([*BASE.values(), 25, "USD"])
    sheet.append([*BASE.values(), True, "USD"])
    book.save(tmp_path / "price.xlsx")
    amounts = [record_to_snapshot(r)["supplier_suggested_price"]["amount"] for r in records(tmp_path / "price.xlsx")]
    assert [(a["value"], a["status"]) for a in amounts] == [("24.99", "INFERRED"), ("25", "INFERRED"), (None, "INVALID")]


# -- contract boundaries -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("header", ["suggested_price", "msrp", "list_price", "rrp", "srp", "map", "retail_price",
                                    "supplier_price", "suggested_price_currency"])
def test_ambiguous_names_are_not_aliases(tmp_path, header):
    result = import_file(write_csv(tmp_path, [{**BASE, header: "24.99"}]), now=NOW)
    assert result.records[0].supplier_suggested_price is None
    assert any(i.code == "UNKNOWN_COLUMN" and i.field == header for i in result.issues)


def test_no_input_format_was_added():
    assert SUPPORTED_INPUT_SUFFIXES == frozenset({".xlsx", ".csv"})


def test_the_domain_refuses_verified_and_a_usable_amount_without_currency():
    common = dict(source="f.csv", method="declared_in_uploaded_file", retrieved_at=NOW, source_type=SourceType.SUPPLIER_FILE)
    with pytest.raises(ValueError, match="never VERIFIED"):
        SupplierSuggestedPrice(FieldValue.verified(Decimal("1"), unit="USD", **common))
    with pytest.raises(ValueError, match="currency"):
        SupplierSuggestedPrice(FieldValue.inferred(Decimal("1"), **common))
    with pytest.raises(ValueError, match="> 0"):
        SupplierSuggestedPrice(FieldValue.inferred(Decimal("0"), unit="USD", **common))


def test_states_distinguish_history_absence_and_declaration():
    assert suggested_price_state({}) == "NOT_CAPTURED"
    assert suggested_price_state({"supplier_suggested_price": None}) == "NOT_DECLARED"
    assert suggested_price_state({"supplier_suggested_price": {"amount": {}}}) == "DECLARED"


@pytest.mark.parametrize("cells", [PRICE, {**PRICE, "supplier_suggested_price": "x"}, {**PRICE, "supplier_suggested_price": ""}])
def test_both_exports_build_identical_cells(tmp_path, cells):
    [record] = records(write_csv(tmp_path, [{**BASE, **cells}]))
    from_capture = suggested_price_cells_from_capture(record.supplier_suggested_price)
    assert from_capture == suggested_price_export_cells(record_to_snapshot(record))
    assert len(from_capture) == len(SUGGESTED_PRICE_EXPORT_HEADERS)


def test_preview_maps_the_columns_to_their_own_group(tmp_path):
    preview = preview_import(write_csv(tmp_path, [{**BASE, **PRICE, "supplier_suggested_price": "x"}]), now=NOW)
    groups = {c.header: c.group for c in preview.columns if c.status == "MAPPED"}
    assert {groups[h] for h in PRICE} == {"supplier_suggested_price"}
    assert any(i.code == "SUGGESTED_PRICE_INVALID" for i in preview.issues)


# -- persistence, API and export -----------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch, auth_lab):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    return TestClient(app, **LOOPBACK)


API_THRESHOLDS = json.dumps({"target_profit": "5", "target_roi": "0", "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "CRITICAL",
                             "allow_restricted": True, "allow_approval_required": True, "allow_unknown_risk": True})
API_FEES = json.dumps({"referral_fee": "1", "referral_fee_rate": "0.15"})


def upload(client, path):
    response = client.post("/api/v1/runs", files={"file": (path.name, path.read_bytes(), "text/csv")},
                           data={"thresholds": API_THRESHOLDS, "fees": API_FEES, "persist": "true"})
    assert response.status_code == 200, response.text
    return response.json()["execution_id"]


def test_the_preview_endpoint_serves_the_group(client, tmp_path):
    path = write_csv(tmp_path, [{**BASE, **PRICE}])
    response = client.post("/api/v1/runs/preview", files={"file": (path.name, path.read_bytes(), "text/csv")})
    assert response.status_code == 200, response.text
    groups = {c["header"]: c["group"] for c in response.json()["columns"] if c["status"] == "MAPPED"}
    assert {groups[h] for h in PRICE} == {"supplier_suggested_price"}


def test_api_and_both_exports_agree(client, tmp_path):
    path = write_csv(tmp_path, [{**BASE, **PRICE},
                                {**BASE, "asin": "B000000002", "supplier_suggested_price": "$5", "supplier_suggested_price_currency": "USD"},
                                {**BASE, "asin": "B000000003", "supplier_suggested_price": "", "supplier_suggested_price_currency": ""},
                                {**BASE, "asin": "B000000004", "supplier_suggested_price": "7.5", "supplier_suggested_price_currency": "eur"}])
    run_id = upload(client, path)
    listed = client.get(f"/api/v1/runs/{run_id}/records", params={"limit": 10, "confidence": "INCLUDE_INFERRED"}).json()["records"]
    assert [r["supplier_suggested_price_state"] for r in listed] == ["DECLARED"] * 4
    assert [r["supplier_suggested_price"]["amount"]["status"] for r in listed] == ["INFERRED", "INVALID", "NOT_FOUND", "INVALID"]
    assert listed[0]["supplier_suggested_price"]["amount"]["value"] == "24.99"
    assert listed[0]["selling_price"]["value"] == "30" and listed[0]["cog"] == "3"        # untouched
    detail = client.get(f"/api/v1/runs/{run_id}/records/{listed[0]['record_ref']}").json()
    assert detail["supplier_suggested_price"] == listed[0]["supplier_suggested_price"]

    exported = client.get(f"/api/v1/runs/{run_id}/records/export", params={"confidence": "INCLUDE_INFERRED"})
    rows = list(openpyxl.load_workbook(io.BytesIO(exported.content))["catalog_export"].iter_rows(values_only=True))
    download = client.get(f"/api/v1/runs/{run_id}/download")
    run_rows = list(openpyxl.load_workbook(io.BytesIO(download.content)).active.iter_rows(values_only=True))
    for sheet in (rows, run_rows):
        header, body = sheet[0], sheet[1:]
        column = lambda name: [row[header.index(name)] for row in body]
        assert column("supplier_suggested_price") == ["24.99", None, None, None]          # exact text; absent stays empty
        assert column("supplier_suggested_price_currency") == ["USD", None, None, None]
        assert column("supplier_suggested_price_status") == ["INFERRED", "INVALID", "NOT_FOUND", "INVALID"]
        assert column("supplier_suggested_price_raw") == [None, "$5", None, "7.5"]
        assert column("supplier_suggested_price_currency_raw") == ["USD", "USD", None, "eur"]
        assert column("supplier_suggested_price_diagnostics") == [None, "SUGGESTED_PRICE_INVALID", None,
                                                                  "SUGGESTED_PRICE_CURRENCY_INVALID"]
        assert column("supplier_suggested_price_source_reference")[0] == "row=2;column=supplier_suggested_price"
        api = [(r["supplier_suggested_price"]["amount"]["value"], r["supplier_suggested_price"]["amount"]["status"]) for r in listed]
        assert list(zip(column("supplier_suggested_price"), column("supplier_suggested_price_status"))) == api
    # No sort, filter or analytics exist for it (mixing currencies would invent an equivalence).
    assert client.get(f"/api/v1/runs/{run_id}/records", params={"sort": "supplier_suggested_price"}).status_code == 422


def test_historical_snapshots_are_not_captured_everywhere(client, tmp_path):
    from .test_record_snapshot_pagination import run, snapshot
    SqliteExecutionRunStore(tmp_path / "runs.db").save_execution_run(run(), [snapshot(0)])
    record = client.get("/api/v1/runs/run-page/records/row_00").json()
    assert (record["supplier_suggested_price"], record["supplier_suggested_price_state"]) == (None, "NOT_CAPTURED")
    exported = client.get("/api/v1/runs/run-page/records/export")
    rows = list(openpyxl.load_workbook(io.BytesIO(exported.content))["catalog_export"].iter_rows(values_only=True))
    assert rows[1][rows[0].index("supplier_suggested_price_state")] == "NOT_CAPTURED"
    assert rows[1][rows[0].index("supplier_suggested_price")] is None


def test_the_document_survives_a_sqlite_round_trip(tmp_path):
    [record] = records(write_csv(tmp_path, [{**BASE, **PRICE}]))
    from .test_record_snapshot_pagination import run
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    snapshot = record_to_snapshot(record)
    store.save_execution_run(run(), [snapshot])
    assert store.load_record("run-page", record.record_ref)["supplier_suggested_price"] == snapshot["supplier_suggested_price"]
