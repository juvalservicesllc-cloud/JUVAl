"""Amazon sourcing product model — the internal domain representation.

Independent of Excel: nothing here knows about column names or cell
positions. Every field that can be sensitive/uncertain (identification,
descriptive info, dimensions, demand, price, competition) is a FieldValue
so its provenance travels with it. Fields that are plain configuration or
unambiguous identifiers supplied directly by the user (sku, supplier_sku,
marketplace) are kept as plain strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from . import units
from .provenance import FieldValue


def _require_unit(fv: Optional[FieldValue], expected_unit: str, name: str) -> None:
    if fv is not None and fv.value is not None and fv.unit != expected_unit:
        raise ValueError(
            f"{name} must be normalized to {expected_unit!r} once VERIFIED/INFERRED, got {fv.unit!r}"
        )


@dataclass(frozen=True)
class Identification:
    asin: FieldValue[str]
    marketplace: str
    upc: Optional[FieldValue[str]] = None
    ean: Optional[FieldValue[str]] = None
    gtin: Optional[FieldValue[str]] = None
    sku: Optional[str] = None
    supplier_sku: Optional[str] = None
    parent_asin: Optional[FieldValue[str]] = None

    def __post_init__(self) -> None:
        if not self.marketplace:
            raise ValueError("Identification.marketplace must not be empty")


@dataclass(frozen=True)
class ProductInfo:
    title: Optional[FieldValue[str]] = None
    brand: Optional[FieldValue[str]] = None
    category: Optional[FieldValue[str]] = None
    model: Optional[FieldValue[str]] = None
    manufacturer: Optional[FieldValue[str]] = None
    part_number: Optional[FieldValue[str]] = None
    description: Optional[FieldValue[str]] = None
    features: Optional[FieldValue[tuple[str, ...]]] = None
    image: Optional[FieldValue[str]] = None
    package_quantity: Optional[FieldValue[int]] = None


class SizeType(str, Enum):
    STANDARD = "STANDARD"
    OVERSIZE = "OVERSIZE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Dimensions:
    """All values normalized to canonical units (units.py) once usable.

    weight -> pounds, height/width/length -> inches, volume -> cubic inches.
    This is enforced structurally, not left to caller discipline: building
    a Dimensions with an un-normalized VERIFIED/INFERRED value raises.
    """

    height: Optional[FieldValue[Decimal]] = None
    width: Optional[FieldValue[Decimal]] = None
    length: Optional[FieldValue[Decimal]] = None
    weight: Optional[FieldValue[Decimal]] = None
    volume: Optional[FieldValue[Decimal]] = None
    size_info: Optional[FieldValue[str]] = None
    size_type: Optional[FieldValue[SizeType]] = None

    def __post_init__(self) -> None:
        _require_unit(self.weight, units.CANONICAL_WEIGHT_UNIT, "Dimensions.weight")
        _require_unit(self.height, units.CANONICAL_LENGTH_UNIT, "Dimensions.height")
        _require_unit(self.width, units.CANONICAL_LENGTH_UNIT, "Dimensions.width")
        _require_unit(self.length, units.CANONICAL_LENGTH_UNIT, "Dimensions.length")
        _require_unit(self.volume, units.CANONICAL_VOLUME_UNIT, "Dimensions.volume")


class StockStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Demand:
    """Demand signals are estimates by nature (Amazon does not publish real
    sales figures). `estimated_monthly_sales` and `sales_velocity` should
    essentially never carry status=VERIFIED unless the source explicitly
    guarantees exact figures — in practice expect INFERRED, with `confidence`
    set on the provenance and the estimation method named in `method`.
    """

    current_bsr: Optional[FieldValue[int]] = None
    average_bsr_30d: Optional[FieldValue[int]] = None
    average_bsr_90d: Optional[FieldValue[int]] = None
    average_bsr_180d: Optional[FieldValue[int]] = None
    sales_rank_drops_30d: Optional[FieldValue[int]] = None
    sales_rank_drops_90d: Optional[FieldValue[int]] = None
    sales_rank_drops_180d: Optional[FieldValue[int]] = None
    estimated_monthly_sales: Optional[FieldValue[int]] = None
    sales_velocity: Optional[FieldValue[Decimal]] = None
    stock_status: Optional[FieldValue[StockStatus]] = None


class SellingPriceSource(str, Enum):
    CURRENT_BUY_BOX = "CURRENT_BUY_BOX"
    AVERAGE_BUY_BOX_30D = "AVERAGE_BUY_BOX_30D"
    AVERAGE_BUY_BOX_90D = "AVERAGE_BUY_BOX_90D"
    AVERAGE_BUY_BOX_180D = "AVERAGE_BUY_BOX_180D"
    MIN_FBA = "MIN_FBA"
    MIN_FBM = "MIN_FBM"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class PriceDynamics:
    """Qualitative price-stability signal, kept separate from the numeric
    price points. May be produced by a rule or by the AI Analyst as an
    *explanation* — never as a numeric input to the Profitability Engine."""

    trend: Optional[FieldValue[str]] = None


@dataclass(frozen=True)
class Price:
    current_buy_box: Optional[FieldValue[Decimal]] = None
    average_buy_box_30d: Optional[FieldValue[Decimal]] = None
    average_buy_box_90d: Optional[FieldValue[Decimal]] = None
    average_buy_box_180d: Optional[FieldValue[Decimal]] = None
    min_fba_price: Optional[FieldValue[Decimal]] = None
    min_fbm_price: Optional[FieldValue[Decimal]] = None
    price_dynamics: Optional[PriceDynamics] = None
    selling_price_used: Optional[FieldValue[Decimal]] = None
    selling_price_source: SellingPriceSource = SellingPriceSource.NOT_FOUND

    def __post_init__(self) -> None:
        has_price = self.selling_price_used is not None
        declared_source = self.selling_price_source != SellingPriceSource.NOT_FOUND
        if declared_source and not has_price:
            raise ValueError("selling_price_source is set but selling_price_used is missing")
        if has_price and not declared_source:
            raise ValueError("selling_price_used is set but selling_price_source is NOT_FOUND")


@dataclass(frozen=True)
class Competition:
    total_offers: Optional[FieldValue[int]] = None
    fba_sellers: Optional[FieldValue[int]] = None
    fbm_sellers: Optional[FieldValue[int]] = None
    buy_box_eligible_fba: Optional[FieldValue[int]] = None
    buy_box_eligible_fbm: Optional[FieldValue[int]] = None
    amazon_in_buy_box: Optional[FieldValue[bool]] = None
    amazon_buy_box_share: Optional[FieldValue[Decimal]] = None
    top_seller_fba: Optional[FieldValue[str]] = None
    top_seller_fbm: Optional[FieldValue[str]] = None
    buy_box_concentration: Optional[FieldValue[Decimal]] = None


@dataclass(frozen=True)
class Product:
    """Aggregate root for a single sourcing candidate's market data."""

    identification: Identification
    info: ProductInfo = field(default_factory=ProductInfo)
    dimensions: Dimensions = field(default_factory=Dimensions)
    demand: Demand = field(default_factory=Demand)
    price: Price = field(default_factory=Price)
    competition: Competition = field(default_factory=Competition)
