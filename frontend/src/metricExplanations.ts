/** One place the wording lives, so Catalog and Product Detail cannot drift
 *  into two different explanations of the same figure. Descriptions state the
 *  definition and the inputs only. */
export const METRIC_EXPLANATIONS: Record<string, string> = {
  profit: "Selling price minus cost of goods, shipping and total fees, computed by the backend Profitability Engine. It is money per unit, not per order or per month.",
  roi: "Profit divided by the cost of goods, shown as a percentage. It answers what each currency unit of stock is expected to return, so it is sensitive to a low COG in a way margin is not.",
  margin: "Profit divided by the selling price, shown as a percentage. It answers how much of the sale price survives as profit, so it is sensitive to the price rather than to what the stock cost.",
  break_even_price: "The selling price at which profit would be exactly zero, given this record's cost, shipping and fees. Below it the unit loses money.",
  max_cog_target_profit: "The highest cost of goods that would still reach the target profit submitted with this run. It is a buying ceiling, not a supplier quote.",
  max_cog_target_roi: "The highest cost of goods that would still reach the target ROI submitted with this run. It is a buying ceiling, not a supplier quote.",
  selling_price: "The selling price recorded for this record, carried with its verification status. JUVAl does not fetch or estimate a marketplace price.",
  cog: "Cost of goods per unit as imported from the supplier file. It is source data, not a calculation.",
  decision: "BUY, REVIEW or PASS, produced by the backend Decision Engine from this run's thresholds and rules. Disqualifying risk takes precedence over economics, so a profitable record can still be PASS.",
}
