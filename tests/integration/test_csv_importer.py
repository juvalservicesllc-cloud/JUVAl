"""CSV ingestion parity: a CSV and an XLSX with the same headers must produce
identical records, identical issues and identical provenance (ADR-002 -- the
file format is interchange, never the domain model)."""

import csv
import io
from datetime import datetime, timezone
from pathlib import Path

import openpyxl
import pytest

from juval.domain.provenance import VerificationStatus
from juval.infrastructure.excel.importer import (
    SUPPORTED_INPUT_SUFFIXES,
    UnsupportedInputFormat,
    import_csv,
    import_excel,
    import_file,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sourcing_TEST_DATA.xlsx"

HEADER = "marketplace,asin,sku,title,brand,cost,selling_price,hazmat,bulky\n"


def _write(tmp_path, name, text, *, encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding, newline="")
    return path


def _fixture_csv(tmp_path) -> Path:
    workbook = openpyxl.load_workbook(FIXTURE, data_only=True, read_only=True)
    try:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\r\n")
        for row in workbook.worksheets[0].iter_rows(values_only=True):
            writer.writerow(["" if cell is None else cell for cell in row])
    finally:
        workbook.close()
    return _write(tmp_path, "fixture.csv", buffer.getvalue())


def test_csv_matches_the_workbook_record_for_record(tmp_path):
    from_xlsx = import_excel(FIXTURE, now=NOW)
    from_csv = import_csv(_fixture_csv(tmp_path), now=NOW)

    assert from_csv.rows_scanned == from_xlsx.rows_scanned
    assert [r.record_ref for r in from_csv.records] == [r.record_ref for r in from_xlsx.records]
    assert [i.code for i in from_csv.issues] == [i.code for i in from_xlsx.issues]
    for csv_record, xlsx_record in zip(from_csv.records, from_xlsx.records):
        assert csv_record.product.identification.asin.value == xlsx_record.product.identification.asin.value
        assert csv_record.product.identification.asin.status == xlsx_record.product.identification.asin.status
        assert (csv_record.costs is None) == (xlsx_record.costs is None)
        if csv_record.costs is not None:
            assert csv_record.costs.cog == xlsx_record.costs.cog


def test_blank_csv_cell_is_not_found_and_never_zero(tmp_path):
    path = _write(tmp_path, "blank.csv", HEADER + "US,B000000001,SKU1,Widget,Acme,10,,false,false\n")
    record = import_csv(path, now=NOW).records[0]
    assert record.product.price.selling_price_used is None
    assert record.costs.cog == 10


def test_invalid_csv_number_is_preserved_as_invalid_not_dropped(tmp_path):
    path = _write(tmp_path, "bad.csv", HEADER + "US,B000000001,SKU1,Widget,Acme,ten,20,false,false\n")
    result = import_csv(path, now=NOW)
    assert "INVALID_NUMBER" in {issue.code for issue in result.issues}
    assert result.records[0].costs is None


def test_fully_blank_csv_row_is_skipped_not_scanned(tmp_path):
    path = _write(tmp_path, "gaps.csv", HEADER + "US,B000000001,SKU1,Widget,Acme,10,20,false,false\n,,,,,,,,\n\n")
    result = import_csv(path, now=NOW)
    assert result.rows_scanned == 1
    assert result.rows_skipped_blank == 2


def test_missing_required_column_is_fatal_for_csv_too(tmp_path):
    path = _write(tmp_path, "no-asin.csv", "marketplace,sku,cost\nUS,SKU1,10\n")
    result = import_csv(path, now=NOW)
    assert result.fatal
    assert "MISSING_REQUIRED_COLUMN" in {issue.code for issue in result.issues}


def test_excel_exported_csv_bom_does_not_corrupt_the_first_header(tmp_path):
    path = _write(tmp_path, "bom.csv", HEADER + "US,B000000001,SKU1,Widget,Acme,10,20,false,false\n", encoding="utf-8-sig")
    result = import_csv(path, now=NOW)
    assert not result.fatal
    assert result.records[0].product.identification.marketplace == "US"


def test_csv_provenance_records_the_real_source_file_and_row(tmp_path):
    path = _write(tmp_path, "supplier.csv", HEADER + "US,B000000001,SKU1,Widget,Acme,10,20,false,false\n")
    asin = import_csv(path, now=NOW).records[0].product.identification.asin
    assert asin.status == VerificationStatus.VERIFIED
    assert asin.provenance.source == "supplier.csv"
    assert asin.provenance.source_reference == "row=2"


def test_import_file_dispatches_by_suffix_and_refuses_anything_else(tmp_path):
    path = _write(tmp_path, "supplier.csv", HEADER + "US,B000000001,SKU1,Widget,Acme,10,20,false,false\n")
    assert import_file(path, now=NOW).records[0].record_ref == "row_2:SKU1"
    assert import_file(FIXTURE, now=NOW).rows_scanned == 5
    assert SUPPORTED_INPUT_SUFFIXES == {".xlsx", ".csv"}
    with pytest.raises(UnsupportedInputFormat):
        import_file(tmp_path / "notes.txt", now=NOW)
