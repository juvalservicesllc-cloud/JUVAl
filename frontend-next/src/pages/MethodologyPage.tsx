import { ProvenanceBadge } from "./shared"

export function MethodologyPage() {
  return <>
    <h1>Methodology</h1>
    <section className="panel" aria-label="Processing workflow">
      <h2>From supplier file to recorded decision</h2>
      <ol>
        <li><strong>Import.</strong> XLSX and CSV share one tabular contract (ADR-026). Columns are identified by header name, never by position. Files are read by the backend.</li>
        <li><strong>Normalize.</strong> The importer normalizes supported values and units while preserving their source.</li>
        <li><strong>Validate.</strong> Missing and invalid values stay explicit. Validation issues are recorded; missing data is never silently replaced with zero.</li>
        <li><strong>Profitability.</strong> Backend deterministic code calculates profit, ROI, margin, break-even and max COG (ADR-006). The frontend displays stored results and never recalculates them.</li>
        <li><strong>Risks.</strong> HazMat and Bulky have separate presence and severity provenance (ADR-020). The internal HAZMAT → HIGH and BULKY → MEDIUM policy is approved by ADR-044; derived severity remains INFERRED, not an external verification. Unknown risks stay unknown.</li>
        <li><strong>Decision.</strong> PASS rules take precedence over REVIEW rules. If no rule fires, the result is BUY. Thresholds are explicitly declared by the processor (ADR-007), not invented by the UI. They are not yet stored on the run.</li>
      </ol>
      <p>Unknown demand leads to REVIEW through DEMAND_UNKNOWN. Demand declared in a supplier file is informative evidence only; it does not feed the Decision Engine or enable BUY (ADR-052). Other PASS rules still take precedence.</p>
      <p>The Decision Score is experimental, separate from BUY / REVIEW / PASS, and is not a validated commercial ranking.</p>
    </section>
    <section className="panel" aria-label="Verification and provenance">
      <h2>Read the evidence with every value</h2>
      <dl>
        <dt><ProvenanceBadge status="VERIFIED" /> VERIFIED</dt><dd>Sufficient evidence from a trusted source for that field. A supplier-file value is not an Amazon or Keepa verification.</dd>
        <dt><ProvenanceBadge status="INFERRED" /> INFERRED</dt><dd>Derived by a rule or heuristic with a recorded method. It never becomes VERIFIED just because it is usable.</dd>
        <dt><ProvenanceBadge status="NOT_FOUND" /> NOT_FOUND</dt><dd>Insufficient evidence; no value is available. It is never zero or a commercial default.</dd>
        <dt><ProvenanceBadge status="INVALID" /> INVALID</dt><dd>A supplied value failed validation. Its raw value is preserved for diagnosis; no usable normalized value is assumed.</dd>
        <dt><ProvenanceBadge status="DEMO_FIXTURE" /> DEMO_FIXTURE</dt><dd>A demonstration label, not a verification state. Synthetic examples never count as VERIFIED evidence and do not supply production decisions.</dd>
      </dl>
      <p>Calculated results keep the weakest input status: missing or invalid inputs yield NOT_FOUND; any usable INFERRED input keeps the result INFERRED; only all-VERIFIED inputs can yield VERIFIED.</p>
    </section>
    <section className="panel" aria-label="Current capabilities">
      <h2>Current data sources and limits</h2>
      <p>No external data sources are integrated today. Amazon and Keepa are not connected. Product images, external supplier links and market history require an approved source and contract.</p>
      <p>Product Detail includes a separately labelled DEMO_FIXTURE chart of 90 synthetic days for presentation. It is not the current product's history, has no real observation dates, and never enters calculations, decisions or exports.</p>
      <p>The AI analyst is not implemented. Its accepted design is downstream, read-only explanation of existing calculations, risks and decisions; it cannot invent missing evidence or replace deterministic calculations.</p>
      <p>Catalog filters change the displayed and exported subset, never the recorded decision. Appearance and column settings are local browser preferences.</p>
    </section>
  </>
}
