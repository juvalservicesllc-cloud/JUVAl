"""Declared demand observations (ADR-052, amendment to ADR-046) -- D7-B.

Evidence only: every test that checks a decision checks that it did NOT
change. Synthetic files only; nothing here is real demand or Amazon data.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from decimal import Decimal

import openpyxl
import pytest
from fastapi.testclient import TestClient

from juval.application.demand_evidence import NOT_CAPTURED, NOT_DECLARED, DECLARED, demand_evidence_state, demand_export_cells
from juval.application.import_preview import preview_import
from juval.application.record_snapshot import record_to_snapshot
from juval.application.run_pipeline import run_pipeline
from juval.domain.costs import FeeInputs
from juval.domain.decision import Thresholds
from juval.domain.risk import Severity
from juval.infrastructure.excel.exporter import DEMAND_EXPORT_HEADERS, demand_cells_from_capture
from juval.infrastructure.logging.sqlite_execution_run_store import SqliteExecutionRunStore
from juval.interfaces.api.main import app

NOW = datetime(2026, 10, 26, 15, tzinfo=timezone.utc)
PERMISSIVE = Thresholds(target_profit=Decimal("0"), target_roi=Decimal("0"), minimum_estimated_monthly_sales=0,
                        maximum_risk_severity=Severity.CRITICAL, allow_restricted=True, allow_approval_required=True,
                        allow_unknown_risk=True)
FEES = FeeInputs(referral_fee=Decimal("1"), referral_fee_rate=Decimal("0.15"))
BASE = {"marketplace": "US", "asin": "B000000001", "cost": "3", "selling_price": "30", "hazmat": "false", "bulky": "false"}
CONTEXT = {"demand_window_start": "2026-09-01T00:00:00-04:00", "demand_window_end": "2026-10-01T00:00:00-04:00",
           "demand_observed_at": "2026-10-01T00:00:00-04:00", "demand_population": "all sellers of this listing on amazon.com",
           "demand_method": "synthetic test declaration"}


def write_csv(tmp_path, rows, name="demand.csv"):
    headers = list(dict.fromkeys(k for row in rows for k in row))
    path = tmp_path / name
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") for h in headers])
    return path


def records(path, thresholds=PERMISSIVE):
    _, out = run_pipeline(path, thresholds, fees=FEES, application_version="test", execution_id="d7b", now=NOW)
    return out


def capture(tmp_path, **cells):
    [record] = records(write_csv(tmp_path, [{**BASE, **cells}]))
    return record, record_to_snapshot(record)["demand_evidence"]


def codes(document):
    return [d["code"] for d in document["diagnostics"]]


# -- the mandatory guarantee ---------------------------------------------------------------------------------------


def test_one_million_declared_units_leave_the_decision_exactly_as_without_demand(tmp_path):
    with_demand = records(write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "1000000", **CONTEXT}], "a.csv"))[0]
    without = records(write_csv(tmp_path, [BASE], "b.csv"))[0]
    for record in (with_demand, without):
        snapshot = record_to_snapshot(record)
        assert snapshot["decision"] == "REVIEW"
        assert snapshot["decision_reason_codes"] == ["DEMAND_UNKNOWN"]
        assert record.product.demand.estimated_monthly_sales is None      # never copied to the engine's field
    assert [(r.code, r.message) for r in with_demand.decision.reasons] == [(r.code, r.message) for r in without.decision.reasons]
    assert record_to_snapshot(with_demand)["demand_evidence"]["observations"][0]["value"]["value"] == 1000000


def test_processing_never_imports_declared_demand():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2] / "src" / "juval" / "processing"
    for source in root.glob("*.py"):
        text = source.read_text()
        assert "declared_demand" not in text and "market_evidence" not in text, source.name


# -- values --------------------------------------------------------------------------------------------------------


def test_a_valid_value_is_inferred_with_full_provenance(tmp_path):
    _, document = capture(tmp_path, estimated_monthly_sales="420", **CONTEXT)
    assert document["format"] == "juval.adr046.demand-evidence" and document["version"] == 1
    assert document["captured_at"] == NOW.isoformat()
    [observation] = document["observations"]
    value = observation["value"]
    assert (value["value"], value["status"], value["unit"]) == (420, "INFERRED", "units")
    provenance = value["provenance"]
    assert provenance["source"] == "demand.csv"
    assert provenance["source_type"] == "USER_INPUT"           # E6: author not accredited, never SUPPLIER_FILE
    assert provenance["source_reference"] == "row=2;column=estimated_monthly_sales"
    assert provenance["method"] == "synthetic test declaration"
    assert provenance["retrieved_at"] == NOW.isoformat()
    assert "not verified" in provenance["evidence"]
    assert observation["observation_id"] == "row_2#ESTIMATED_SALES#1"
    assert observation["window"] == {"start": "2026-09-01T00:00:00-04:00", "end": "2026-10-01T00:00:00-04:00"}
    assert observation["observed_at"] == "2026-10-01T00:00:00-04:00"
    assert observation["population_definition"] == "all sellers of this listing on amazon.com"
    assert document["diagnostics"] == []


def test_zero_is_a_declared_zero_not_absence(tmp_path):
    _, document = capture(tmp_path, demand_estimated_sales="0", **CONTEXT)
    assert document["observations"][0]["value"]["value"] == 0
    assert document["observations"][0]["value"]["status"] == "INFERRED"


def test_an_empty_value_with_valid_context_is_not_found_never_zero(tmp_path):
    _, document = capture(tmp_path, demand_estimated_sales="", **CONTEXT)
    value = document["observations"][0]["value"]
    assert (value["value"], value["status"]) == (None, "NOT_FOUND")
    assert value["provenance"]["evidence"] == "declared demand column present; value cell empty"


def test_an_empty_value_without_context_is_only_a_diagnostic(tmp_path):
    _, document = capture(tmp_path, demand_estimated_sales="")
    assert document["observations"] == []
    assert codes(document) == ["DEMAND_VALUE_EMPTY"]


@pytest.mark.parametrize("raw", ["about 400", "-5", "1.5", "true", "4e2"])
def test_invalid_values_keep_their_raw_text(tmp_path, raw):
    record, document = capture(tmp_path, demand_estimated_sales=raw, **CONTEXT)
    value = document["observations"][0]["value"]
    assert (value["value"], value["status"], value["raw_value"]) == (None, "INVALID", raw)
    assert codes(document) == ["DEMAND_VALUE_INVALID"]
    assert "DEMAND_VALUE_INVALID" in {i.code for i in record.issues}           # visible as a WARNING
    assert record_to_snapshot(record)["decision_reason_codes"] == ["DEMAND_UNKNOWN"]


# -- context -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("missing,code", [
    ("demand_window_start", "DEMAND_CONTEXT_MISSING"), ("demand_window_end", "DEMAND_CONTEXT_MISSING"),
    ("demand_observed_at", "DEMAND_CONTEXT_MISSING"), ("demand_population", "DEMAND_CONTEXT_MISSING"),
    ("demand_method", "DEMAND_CONTEXT_MISSING"),
])
def test_incomplete_context_keeps_the_value_raw_and_unusable(tmp_path, missing, code):
    context = {k: v for k, v in CONTEXT.items() if k != missing}
    record, document = capture(tmp_path, demand_estimated_sales="420", **context)
    assert document["observations"] == []
    assert codes(document) == ["DEMAND_VALUE_NOT_USABLE", code]
    assert document["diagnostics"][0]["raw_value"] == "420"
    assert record.product.identification.asin.value == "B000000001"           # the rest of the row is processed


@pytest.mark.parametrize("override,code", [
    ({"demand_window_end": "2026-09-01T00:00:00-04:00"}, "DEMAND_CONTEXT_INVALID"),        # start == end
    ({"demand_observed_at": "2026-09-15T00:00:00-04:00"}, "DEMAND_CONTEXT_INVALID"),       # window ends after observed_at
    ({"demand_observed_at": "2026-11-01T00:00:00+00:00", "demand_window_end": "2026-10-01T00:00:00-04:00"}, "DEMAND_CONTEXT_INVALID"),  # after import
    ({"demand_window_start": "next tuesday"}, "DEMAND_CONTEXT_INVALID"),
    ({"demand_population": "x" * 501}, "DEMAND_CONTEXT_INVALID"),
])
def test_invalid_windows_and_instants_are_refused(tmp_path, override, code):
    _, document = capture(tmp_path, demand_estimated_sales="420", **{**CONTEXT, **override})
    assert document["observations"] == []
    assert codes(document)[-1] == code


def test_a_date_without_a_zone_needs_a_declared_timezone(tmp_path):
    naive = {**CONTEXT, "demand_window_start": "2026-09-01T00:00:00", "demand_window_end": "2026-10-01T00:00:00",
             "demand_observed_at": "2026-10-01T00:00:00"}
    _, document = capture(tmp_path, demand_estimated_sales="420", **naive)
    assert codes(document)[-1] == "DEMAND_TIME_NAIVE"
    _, document = capture(tmp_path, demand_estimated_sales="420", demand_timezone="America/New_York", **naive)
    observation = document["observations"][0]
    assert observation["window"]["start"] == "2026-09-01T00:00:00-04:00"
    assert observation["declared_timezone"] == "America/New_York"


def test_xlsx_date_cells_are_naive_and_follow_the_same_rule(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    headers = [*BASE, "demand_estimated_sales", "demand_window_start", "demand_window_end", "demand_observed_at",
               "demand_population", "demand_method", "demand_timezone"]
    sheet.append(headers)
    sheet.append([*BASE.values(), 420, datetime(2026, 9, 1), datetime(2026, 10, 1), datetime(2026, 10, 1),
                  "all sellers of this listing on amazon.com", "synthetic", "Europe/Madrid"])
    path = tmp_path / "demand.xlsx"
    workbook.save(path)
    [record] = records(path)
    observation = record_to_snapshot(record)["demand_evidence"]["observations"][0]
    assert observation["window"]["start"] == "2026-09-01T00:00:00+02:00"
    assert observation["value"]["value"] == 420


@pytest.mark.parametrize("instant,code", [("2026-03-08T02:30:00", "DEMAND_TIME_NONEXISTENT"),
                                          ("2026-11-01T01:30:00", "DEMAND_TIME_AMBIGUOUS")])
def test_dst_gaps_and_folds_are_never_resolved_silently(tmp_path, instant, code):
    context = {**CONTEXT, "demand_window_start": "2026-02-01T00:00:00-05:00", "demand_window_end": instant,
               "demand_observed_at": "2026-11-02T00:00:00-05:00", "demand_timezone": "America/New_York"}
    _, document = capture(tmp_path, demand_estimated_sales="420", **context)
    assert document["observations"] == []
    assert codes(document)[-1] == code


def test_an_offset_contradicting_the_declared_zone_is_a_conflict(tmp_path):
    _, document = capture(tmp_path, demand_estimated_sales="420", demand_timezone="Europe/Madrid", **CONTEXT)
    assert codes(document)[-1] == "DEMAND_TIMEZONE_CONFLICT"


def test_an_unknown_timezone_is_refused(tmp_path):
    _, document = capture(tmp_path, demand_estimated_sales="420", demand_timezone="Mars/Olympus", **CONTEXT)
    assert codes(document)[-1] == "DEMAND_TIMEZONE_INVALID"


def test_a_declared_calendar_month_gives_its_exact_bounds(tmp_path):
    context = {k: v for k, v in CONTEXT.items() if not k.startswith("demand_window")}
    _, document = capture(tmp_path, demand_estimated_sales="420", demand_month="2026-09", demand_timezone="America/New_York", **context)
    observation = document["observations"][0]
    assert observation["window"] == {"start": "2026-09-01T00:00:00-04:00", "end": "2026-10-01T00:00:00-04:00"}
    assert (observation["window_source"], observation["declared_month"]) == ("DECLARED_MONTH", "2026-09")


def test_a_month_needs_its_timezone_and_never_combines_with_an_explicit_window(tmp_path):
    context = {k: v for k, v in CONTEXT.items() if not k.startswith("demand_window")}
    _, document = capture(tmp_path, demand_estimated_sales="420", demand_month="2026-09", **context)
    assert codes(document)[-1] == "DEMAND_CONTEXT_MISSING"
    _, document = capture(tmp_path, demand_estimated_sales="420", demand_month="2026-09", demand_timezone="UTC", **CONTEXT)
    assert codes(document)[-1] == "DEMAND_WINDOW_CONFLICT"


# -- columns, provenance and history -------------------------------------------------------------------------------


def test_monthly_sales_is_not_an_alias_in_v1(tmp_path):
    path = write_csv(tmp_path, [{**BASE, "monthly_sales": "420", **CONTEXT}])
    [record] = records(path)
    assert record.market_evidence is not None                         # context columns make the file declare demand
    assert record.market_evidence.observations[0].observation.value.status.value == "NOT_FOUND"   # value column absent
    statuses = {c.header: c.status for c in preview_import(path, now=NOW).columns}
    assert statuses["monthly_sales"] == "UNKNOWN"


def test_a_duplicate_value_column_uses_the_first_and_reports_the_second(tmp_path):
    path = write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "420", "estimated_monthly_sales": "999", **CONTEXT}])
    [record] = records(path)
    document = record_to_snapshot(record)["demand_evidence"]
    assert document["observations"][0]["value"]["value"] == 420
    assert document["observations"][0]["value"]["provenance"]["source_reference"] == "row=2;column=demand_estimated_sales"
    # A header-level issue of the file, reported once by the existing importer rule.
    assert "DUPLICATE_COLUMN" in {i.code for i in preview_import(path, now=NOW).issues}


def test_a_file_without_demand_columns_is_not_declared_and_imports_as_before(tmp_path):
    [record] = records(write_csv(tmp_path, [BASE]))
    snapshot = record_to_snapshot(record)
    assert record.market_evidence is None
    assert snapshot["demand_evidence"] is None and demand_evidence_state(snapshot) == NOT_DECLARED
    assert not any(i.code.startswith("DEMAND_") for i in record.issues)


def test_states_distinguish_history_absence_and_declaration():
    assert demand_evidence_state({}) == NOT_CAPTURED
    assert demand_evidence_state({"demand_evidence": None}) == NOT_DECLARED
    assert demand_evidence_state({"demand_evidence": {"observations": []}}) == DECLARED


def test_reimporting_later_is_a_new_capture_not_a_rewrite(tmp_path):
    path = write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "420", **{**CONTEXT, "demand_observed_at": "2026-10-27T00:00:00+00:00",
                                                                            "demand_window_end": "2026-10-27T00:00:00+00:00"}}])
    _, early = run_pipeline(path, PERMISSIVE, fees=FEES, application_version="t", execution_id="e", now=NOW)
    later_now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    _, later = run_pipeline(path, PERMISSIVE, fees=FEES, application_version="t", execution_id="l", now=later_now)
    assert record_to_snapshot(early[0])["demand_evidence"]["observations"] == []            # observed_at was in the future
    assert record_to_snapshot(later[0])["demand_evidence"]["observations"][0]["value"]["status"] == "INFERRED"
    assert record_to_snapshot(later[0])["demand_evidence"]["captured_at"] == later_now.isoformat()


def test_both_exports_build_identical_demand_cells(tmp_path):
    [record] = records(write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "420", **CONTEXT}]))
    from_capture = demand_cells_from_capture(record.market_evidence)
    from_snapshot = demand_export_cells(record_to_snapshot(record))
    assert from_capture == from_snapshot
    assert dict(zip(DEMAND_EXPORT_HEADERS, from_capture))["demand_declared_units"] == 420


def test_preview_maps_demand_columns_to_their_own_group(tmp_path):
    path = write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "x", **CONTEXT}])
    preview = preview_import(path, now=NOW)
    groups = {c.header: c.group for c in preview.columns if c.status == "MAPPED"}
    assert {groups[h] for h in ("demand_estimated_sales", *CONTEXT)} == {"declared_demand"}
    assert any(i.code == "DEMAND_VALUE_INVALID" for i in preview.issues)


# -- persistence, API and export -----------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JUVAL_RUN_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("JUVAL_EXECUTION_DB_PATH", str(tmp_path / "runs.db"))
    return TestClient(app)


THRESHOLDS = json.dumps({"target_profit": "0", "target_roi": "0", "minimum_estimated_monthly_sales": 0, "maximum_risk_severity": "CRITICAL",
                         "allow_restricted": True, "allow_approval_required": True, "allow_unknown_risk": True})
API_FEES = json.dumps({"referral_fee": "1", "referral_fee_rate": "0.15"})


def upload(client, path):
    response = client.post("/api/v1/runs", files={"file": (path.name, path.read_bytes(), "text/csv")},
                           data={"thresholds": THRESHOLDS, "fees": API_FEES, "persist": "true"})
    assert response.status_code == 200, response.text
    return response.json()["execution_id"]


def test_the_preview_endpoint_serves_the_declared_demand_group(client, tmp_path):
    # Found by the frontend-next E2E: the response model refused the group and the endpoint answered 500.
    path = write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "1000000", **CONTEXT}])
    response = client.post("/api/v1/runs/preview", files={"file": (path.name, path.read_bytes(), "text/csv")})
    assert response.status_code == 200, response.text
    groups = {c["header"]: c["group"] for c in response.json()["columns"] if c["status"] == "MAPPED"}
    assert {groups[h] for h in ("demand_estimated_sales", *CONTEXT)} == {"declared_demand"}


def test_api_and_filtered_export_expose_the_stored_document(client, tmp_path):
    path = write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "1000000", **CONTEXT},
                                {**BASE, "asin": "B000000002", "demand_estimated_sales": "approx", **CONTEXT},
                                {**BASE, "asin": "B000000003"},
                                {**BASE, "asin": "B000000004", "demand_estimated_sales": "", **CONTEXT}])
    run_id = upload(client, path)
    listed = client.get(f"/api/v1/runs/{run_id}/records", params={"limit": 10, "confidence": "INCLUDE_INFERRED"}).json()["records"]
    first, second, third, fourth = listed
    assert first["demand_evidence_state"] == "DECLARED"
    assert first["demand_evidence"]["observations"][0]["value"]["value"] == 1000000
    assert first["decision"] == "REVIEW" and first["review_classification"] == "PENDING_DEMAND_VERIFICATION"   # D7-D intact
    assert second["demand_evidence"]["observations"][0]["value"]["raw_value"] == "approx"
    # No value and no context: a diagnostic, no observation.
    assert third["demand_evidence_state"] == "DECLARED" and third["demand_evidence"]["observations"] == []
    assert [d["code"] for d in third["demand_evidence"]["diagnostics"]] == ["DEMAND_VALUE_EMPTY"]
    assert fourth["demand_evidence"]["observations"][0]["value"]["status"] == "NOT_FOUND"
    detail = client.get(f"/api/v1/runs/{run_id}/records/{first['record_ref']}").json()
    assert detail["demand_evidence"] == first["demand_evidence"]

    exported = client.get(f"/api/v1/runs/{run_id}/records/export", params={"confidence": "INCLUDE_INFERRED"})
    rows = list(openpyxl.load_workbook(io.BytesIO(exported.content))["catalog_export"].iter_rows(values_only=True))
    header, body = rows[0], rows[1:]
    column = lambda name: [row[header.index(name)] for row in body]
    assert column("demand_declared_units") == [1000000, None, None, None]                   # absent stays empty, never 0
    assert column("demand_status") == ["INFERRED", "INVALID", None, "NOT_FOUND"]
    assert column("demand_raw_value") == [None, "approx", None, None]
    assert column("demand_diagnostics") == [None, "DEMAND_VALUE_INVALID", "DEMAND_VALUE_EMPTY", None]
    assert column("decision") == ["REVIEW", "REVIEW", "REVIEW", "REVIEW"]
    # No new query parameter exists for declared demand (no filters, rankings or analytics in v1).
    assert client.get(f"/api/v1/runs/{run_id}/records", params={"sort": "demand"}).status_code == 422


def test_run_download_carries_the_same_demand_columns(client, tmp_path):
    run_id = upload(client, write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "420", **CONTEXT}]))
    download = client.get(f"/api/v1/runs/{run_id}/download")
    rows = list(openpyxl.load_workbook(io.BytesIO(download.content)).active.iter_rows(values_only=True))
    values = dict(zip(rows[0], rows[1]))
    assert (values["demand_evidence_state"], values["demand_declared_units"], values["demand_status"]) == ("DECLARED", 420, "INFERRED")


def test_historical_snapshots_are_not_captured_everywhere(client, tmp_path):
    from .test_record_snapshot_pagination import run, snapshot
    SqliteExecutionRunStore(tmp_path / "runs.db").save_execution_run(run(), [snapshot(0)])
    record = client.get("/api/v1/runs/run-page/records/row_00").json()
    assert (record["demand_evidence"], record["demand_evidence_state"]) == (None, "NOT_CAPTURED")
    exported = client.get("/api/v1/runs/run-page/records/export")
    rows = list(openpyxl.load_workbook(io.BytesIO(exported.content))["catalog_export"].iter_rows(values_only=True))
    assert rows[1][rows[0].index("demand_evidence_state")] == "NOT_CAPTURED"


def test_declared_demand_survives_a_sqlite_round_trip(tmp_path):
    [record] = records(write_csv(tmp_path, [{**BASE, "demand_estimated_sales": "420", **CONTEXT}]))
    from .test_record_snapshot_pagination import run
    store = SqliteExecutionRunStore(tmp_path / "runs.db")
    snapshot = record_to_snapshot(record)
    store.save_execution_run(run(), [snapshot])
    assert store.load_record("run-page", record.record_ref)["demand_evidence"] == snapshot["demand_evidence"]
