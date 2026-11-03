import { useState } from "react"

/** Approved G12 presentation fixture. No record, ASIN, price or run is an input.
 * Synthetic day labels are deliberately not real observation timestamps. */
export const DEMO_MARKET = Array.from({ length: 90 }, (_, day) => ({ day: day + 1, amount: Number((20 * (1 + Math.sin((day + 7) / 7) * 0.07 + ((7 + day * 13) % 9 - 4) * 0.006)).toFixed(2)) }))

export function MarketDemo() {
  const [type, setType] = useState("line")
  const values = DEMO_MARKET.map((point) => point.amount)
  const low = Math.min(...values), high = Math.max(...values)
  const y = (value: number) => 170 - (value - low) / (high - low) * 130
  return <section className="panel" aria-label="Illustrative market chart">
    <h2>Market chart — illustrative example</h2>
    <p><strong>DEMO_FIXTURE · NOT VERIFIED · NOT INFERRED FROM PRODUCTION DATA</strong></p>
    <p>90 synthetic days for presentation only. Not Amazon or Keepa data, not this product's history. These amounts never affect sourcing calculations, decisions, filters or exports.</p>
    <div className="chart-controls" role="group" aria-label="Market chart type">
      <button aria-pressed={type === "line"} onClick={() => setType("line")}>Line</button>
      <button aria-pressed={type === "bar"} onClick={() => setType("bar")}>Bar</button>
    </div>
    <svg className="market-demo-chart" role="img" aria-label={`DEMO_FIXTURE 90-day ${type} chart, illustrative USD amounts`} viewBox="0 0 700 210">
      <title>90 synthetic days, unrelated to the current record</title>
      <path d="M30 20V180H680" fill="none" stroke="currentColor" />
      {type === "line" ? <polyline fill="none" stroke="currentColor" strokeWidth="2" points={DEMO_MARKET.map((point, i) => `${35 + i * 7.1},${y(point.amount)}`).join(" ")} /> :
        DEMO_MARKET.map((point, i) => <rect key={point.day} x={35 + i * 7.1} y={y(point.amount)} width="5" height={180 - y(point.amount)} fill="currentColor" />)}
      <text x="30" y="202" fill="currentColor" fontSize="14">Day 1</text><text x="620" y="202" fill="currentColor" fontSize="14">Day 90</text>
    </svg>
    <p>Illustrative USD range: {low.toFixed(2)}–{high.toFixed(2)}. No real observation dates or freshness claims.</p>
    <details><summary>View all 90 DEMO values</summary><div className="table"><table aria-label="DEMO market values"><thead><tr><th>Synthetic day</th><th>Illustrative USD amount</th></tr></thead><tbody>{DEMO_MARKET.map((point) => <tr key={point.day}><td>Day {point.day}</td><td>{point.amount.toFixed(2)}</td></tr>)}</tbody></table></div></details>
  </section>
}
