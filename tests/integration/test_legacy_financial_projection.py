"""A real imported legacy record, diagnosed read-only (ADR-047 §20). Synthetic CSV only."""
from datetime import datetime, timezone
from decimal import Decimal

from juval.application.legacy_financial_projection import legacy_financial_operands
from juval.domain.financial_evidence import FinancialTerm, LegacyGap, assess_legacy_financial_operands
from juval.infrastructure.excel.importer import import_file

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
CSV = ("marketplace,asin,sku,title,brand,cost,selling_price,shipping_per_unit,hazmat,bulky\n"
       "US,B000SYNTH1,SKU-1,Synthetic item,SynthBrand,4.50,19.99,,no,no\n")


def test_imported_record_blank_shipping_default_is_not_an_accredited_zero(tmp_path):
    path = tmp_path / "synthetic.csv"
    path.write_text(CSV, encoding="utf-8", newline="")
    [record] = import_file(path, now=NOW).records
    costs_before = (record.costs.cog, record.costs.shipping_per_unit)
    price = record.product.price.selling_price_used

    report = assess_legacy_financial_operands(legacy_financial_operands(record.costs, record.fees))

    assert record.costs.shipping_per_unit == Decimal("0")  # importer default for a blank cell
    shipping = report.gap_for(FinancialTerm.SHIPPING_PER_UNIT)
    assert LegacyGap.ZERO_INDISTINGUISHABLE_FROM_DEFAULT in shipping.gaps
    assert LegacyGap.ALLOCATION_UNDECLARED in shipping.gaps
    assert LegacyGap.NO_PROVENANCE in report.gap_for(FinancialTerm.COG).gaps
    # The importer attaches no FeeInputs: fee slots are absent, not zero.
    assert record.fees is None
    assert report.gap_for(FinancialTerm.REFERRAL_FEE).gaps == (LegacyGap.STRUCTURALLY_ABSENT,)
    assert not report.satisfies_contract
    assert (record.costs.cog, record.costs.shipping_per_unit) == costs_before
    # The selling price has no FinancialTerm slot: left untouched, never an observation.
    assert record.product.price.selling_price_used is price
    assert price.value == Decimal("19.99")
