"""Generates tests/fixtures/sample_sourcing_TEST_DATA.xlsx.

TEST DATA ONLY. Every SKU/ASIN/title here is synthetic and prefixed
"JUVAL TEST" / "B0TEST..." specifically so it can never be mistaken for a
real Amazon listing. Re-run this script (`python generate_sample.py`) if
the fixture's shape needs to change — the file is committed so tests don't
depend on regenerating it.

Row-by-row intent (mirrors Fase 2 requirement 4):
  2  valid baseline row (all required data present and well-formed)
  3  missing data (blank ASIN, blank selling price)
  4  invalid data (bad ASIN format, bad UPC checksum, non-numeric weight,
     missing COG, non-numeric price, unrecognized HazMat value)
  5  risk present (HazMat = TRUE)
  6  malformed row (blank marketplace -> the whole row is unbuildable)

An extra "Notes" column is included to exercise "unknown column" handling,
and header casing/spacing is varied to exercise header normalization.
"""

from pathlib import Path

import openpyxl

HEADERS = [
    "Supplier SKU",
    "Marketplace",
    "ASIN",
    "UPC",
    "Title",
    "Brand",
    "Category",
    "Weight",
    "Weight Unit",
    "Height",
    "Width",
    "Length",
    "Dimension Unit",
    "Cost",
    "Shipping Per Unit",
    "Selling Price",
    "HazMat",
    "Bulky",
    "Notes",
]

ROWS = [
    # valid baseline row
    [
        "SUP-001", "US", "B0TESTAAA1", "036000291452",
        "JUVAL TEST WIDGET ALPHA", "JuvalTestBrand", "Home",
        1.5, "lb", 4, 3, 2, "in",
        5.00, 1.00, 19.99, "FALSE", "FALSE",
        "valid baseline row",
    ],
    # missing data: no ASIN, no selling price
    [
        "SUP-002", "US", None, None,
        "JUVAL TEST WIDGET BETA (MISSING DATA)", "JuvalTestBrand", "Home",
        None, None, None, None, None, None,
        6.00, 0.50, None, None, None,
        "missing asin and selling price",
    ],
    # invalid data: bad ASIN, bad UPC, non-numeric weight, missing COG, non-numeric price, bad hazmat value
    [
        "SUP-003", "US", "NOT-AN-ASIN!", "1234",
        "JUVAL TEST WIDGET GAMMA (INVALID DATA)", "JuvalTestBrand", "Home",
        "abc", "lb", None, None, None, None,
        None, 0, "N/A", "maybe", "FALSE",
        "invalid asin, upc, weight, missing cost, invalid price and hazmat",
    ],
    # risk present: hazmat = TRUE
    [
        "SUP-004", "US", "B0TESTAAA4", None,
        "JUVAL TEST WIDGET DELTA (HAZMAT RISK)", "JuvalTestBrand", "Home",
        2, "lb", 5, 5, 5, "in",
        4.00, 0.75, 15.00, "TRUE", "FALSE",
        "hazmat present",
    ],
    # malformed row: blank marketplace -> row cannot be built at all
    [
        "SUP-005", None, "B0TESTAAA5", None,
        "JUVAL TEST WIDGET EPSILON (MALFORMED ROW)", "JuvalTestBrand", "Home",
        1, "lb", 2, 2, 2, "in",
        3.00, 0.25, 9.99, "FALSE", "FALSE",
        "malformed row: missing required marketplace",
    ],
]


def generate(path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "TEST DATA - Juval Sourcing"
    sheet.append(HEADERS)
    for row in ROWS:
        sheet.append(row)
    workbook.save(path)


if __name__ == "__main__":
    generate(Path(__file__).parent / "sample_sourcing_TEST_DATA.xlsx")
