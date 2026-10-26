import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { RecordFinancialOut } from "../api/types"
import { FinancialEvidenceView } from "./FinancialEvidence"

// Same shape as the API's real output for the repository's synthetic financial
// rows (tests/integration/test_api_financial_flow.py), trimmed to a few entries.
const prov = (status: string, ref: string, source = "financial.xlsx", type = "SUPPLIER_FILE", evidence: string | null = null) =>
  ({ source, source_type: type, verification_status: status, retrieved_at: "2026-10-26T16:20:51+00:00", method: "direct_read", confidence: null, evidence, source_reference: ref })
const fv = (value: unknown, status: string, ref: string, unit: string | null = null, extra: Record<string, unknown> = {}) =>
  ({ value, unit, raw_value: null, provenance: prov(status, ref), ...extra })

const v2 = {
  format: "juval.adr047.financial-record", version: 2,
  evidence: {
    execution_id: "run-1", record_reference: "row_2:FULL",
    scenario: { scenario_id: "synthetic-scenario", scenario_version: "v1", currency: "USD", policy_identity: "synthetic-policy@v1", sellable_unit_definition: "one sellable unit", required_terms: ["COG", "VAT"], context_requirements: [] },
    terms: [
      { term: "COG", amount: fv({ decimal: "4.50" }, "VERIFIED", "row=2;column=fin_cog_amount", "USD"), applicability: { applies: fv({ bool: true }, "VERIFIED", "row=2;column=fin_cog_applies"), justification: "synthetic declaration" }, context: { basis_definition: "synthetic per-unit basis", effective_at: "2026-02-01T00:00:00+00:00", effective_until: null }, allocation_method: null, depends_on: [] },
      { term: "VAT", amount: null, applicability: { applies: fv({ bool: false }, "VERIFIED", "row=2;column=fin_vat_applies"), justification: "synthetic declaration" }, context: { basis_definition: "synthetic per-unit basis", effective_at: "2026-02-01T00:00:00+00:00", effective_until: null }, allocation_method: null, depends_on: [] },
    ],
  },
  selling_price: { amount: fv({ decimal: "20.00" }, "VERIFIED", "row=2;column=fin_selling_price_amount", "USD"), context: { basis_definition: "supplier MAP per sellable unit" } },
  resolution: { execution_id: "run-1", record_reference: "row_2:FULL", results: [{ result: "PROFIT", math_preconditions: [], dependencies: [
    { dependency: "COG", term: "COG", blocker: null, excluded: false, operand: fv({ decimal: "4.50" }, "VERIFIED", "row=2;column=fin_cog_amount", "USD"), detail: null },
    { dependency: "VAT", term: "VAT", blocker: null, excluded: true, operand: null, detail: null },
    { dependency: "STORAGE", term: "STORAGE", blocker: "STRUCTURALLY_ABSENT", excluded: false, operand: null, detail: "required by the scenario but not represented" },
  ] }] },
  calculations: { execution_id: "run-1", record_reference: "row_2:FULL", decimal_precision: 28, decimal_rounding: "ROUND_HALF_EVEN", calculations: [
    { result: "PROFIT", expression: "P - (R + F + O) - (COG + C0)", blocker: null, exact: true, preconditions: [], undeclared_terms: [], value: { value: { decimal: "9.30" }, unit: null, raw_value: null, provenance: prov("VERIFIED", "scenario=synthetic-scenario@v1", "adr047_financial_calculator", "CALCULATED") } },
    { result: "ROI", expression: "profit / (COG + C0)", blocker: null, exact: false, preconditions: [{ expression: "C = COG + C0 > 0", operand: { decimal: "4.50" }, satisfied: true }], undeclared_terms: [], value: { value: { decimal: "2.066666666666666666666666667" }, unit: null, raw_value: null, provenance: prov("INFERRED", "scenario=synthetic-scenario@v1", "adr047_financial_calculator", "CALCULATED") } },
    { result: "MARGIN", expression: "profit / P", blocker: "DEPENDENCIES_UNRESOLVED", exact: null, preconditions: [], undeclared_terms: ["TAXES"], value: { value: null, unit: null, raw_value: null, provenance: prov("NOT_FOUND", "scenario=synthetic-scenario@v1", "adr047_financial_calculator", "CALCULATED", "DEPENDENCIES_UNRESOLVED: COG=STRUCTURALLY_ABSENT") } },
  ] },
  supplied_inputs: {
    selling_price: fv({ decimal: "20.00" }, "VERIFIED", "row=2;column=fin_selling_price_amount", "USD"),
    target_roi: { value: null, unit: "ratio", raw_value: "abc", provenance: { ...prov("INVALID", "request"), source: "juval-api", source_type: "USER_INPUT" } },
    weight: null,
  },
  capture_problems: [{ subject: "COG", column: "fin_cog_source_basis", row: 2, raw_value: { str: "carton" }, text: "COG: source_basis must be one of ['pack', 'sellable_unit'], got 'carton'" }],
  implementation: { application_version: "0.1.0", calculator: "adr047_financial_calculator", code_revision: null, expressions_digest: "4165", dependency_matrix_digest: "a178", derivation_methods: [] },
  future_block: { kept: "as stored" },
}
const diagnostics = { format: "juval.adr047.capture-diagnostics", version: 1, payload: { format: "juval.adr047.capture-diagnostics", version: 1, execution_id: "run-1", record_ref: "row_2:FULL", diagnostics: [
  { code: "SOURCE_BASIS_INVALID", subject: "COG", column: "fin_cog_source_basis", row: 2, raw_value: "carton", message: "source_basis must be one of ['pack', 'sellable_unit'], got 'carton'" },
] } }
const financial = (overrides: Partial<RecordFinancialOut> = {}): RecordFinancialOut => ({
  execution_id: "run-1", record_ref: "row_2:FULL",
  financial_document: { format: "juval.adr047.financial-record", version: 2, payload: v2 },
  capture_diagnostics: diagnostics, inconsistencies: [], ...overrides,
})
const rowOf = (table: string, first: string) => within(screen.getByRole("table", { name: table })).getByText(first).closest("tr") as HTMLElement

describe("Stored ADR-047 evidence, read without recalculation", () => {
  it("shows each calculated result exactly as stored, with its own status", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    const profit = rowOf("Calculated results", "PROFIT")
    expect(profit).toHaveTextContent("9.30")
    expect(within(profit).getByLabelText("Status: VERIFIED")).toBeInTheDocument()
    const roi = rowOf("Calculated results", "ROI")
    expect(roi).toHaveTextContent("2.066666666666666666666666667")          // never rounded
    expect(within(roi).getByLabelText("Status: INFERRED")).toBeInTheDocument()
    expect(roi).toHaveTextContent("C = COG + C0 > 0 with 4.50: satisfied")
    expect(screen.getByText(/precision 28, rounding ROUND_HALF_EVEN/)).toBeInTheDocument()
  })

  it("keeps a blocked result blocked: no value, its blocker, its evidence and undeclared terms", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    const margin = rowOf("Calculated results", "MARGIN")
    expect(margin).toHaveTextContent("No value")
    expect(within(margin).getByLabelText("Status: NOT FOUND")).toBeInTheDocument()
    expect(margin).toHaveTextContent("DEPENDENCIES_UNRESOLVED")
    expect(margin).toHaveTextContent("COG=STRUCTURALLY_ABSENT")
    expect(margin).toHaveTextContent("TAXES")
    expect(margin).not.toHaveTextContent("0.00")
  })

  it("lays out the scenario and every declared term with its source cell", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    expect(screen.getByText("synthetic-scenario@v1")).toBeInTheDocument()
    const cog = rowOf("Declared terms", "COG")
    expect(cog).toHaveTextContent("4.50 USD")
    expect(cog).toHaveTextContent("row=2;column=fin_cog_amount")
    const vat = rowOf("Declared terms", "VAT")
    expect(vat).toHaveTextContent("no")
    expect(vat).toHaveTextContent("No amount")
  })

  it("summarises dependency resolution and keeps excluded apart from blocked", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    expect(screen.getByText("PROFIT: 1 resolved · 1 excluded · 1 blocked")).toBeInTheDocument()
    expect(rowOf("PROFIT dependencies", "STORAGE")).toHaveTextContent("blocked: STRUCTURALLY_ABSENT")
    expect(rowOf("PROFIT dependencies", "VAT")).toHaveTextContent("excluded (does not apply)")
  })

  it("shows supplied inputs as supplied, including invalid ones and absent ones", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    const roi = rowOf("Supplied inputs", "target_roi")
    expect(within(roi).getByLabelText("Status: INVALID")).toBeInTheDocument()
    expect(roi).toHaveTextContent("raw abc")
    expect(rowOf("Supplied inputs", "weight")).toHaveTextContent("Not supplied")
  })

  it("preserves capture problems and the separate diagnostics set", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    expect(rowOf("Capture problems", "COG")).toHaveTextContent("carton")
    expect(rowOf("Capture diagnostics", "SOURCE_BASIS_INVALID")).toHaveTextContent("fin_cog_source_basis")
  })

  it("lists keys it does not know instead of dropping them, and keeps the original JSON", () => {
    render(<FinancialEvidenceView financial={financial()} />)
    expect(screen.getByText("future_block")).toBeInTheDocument()
    expect(screen.getByText("Financial document: original stored JSON (juval.adr047.financial-record v2)")).toBeInTheDocument()
    expect(screen.getByText("Capture diagnostics: original stored JSON (juval.adr047.capture-diagnostics v1)")).toBeInTheDocument()
    expect(document.body.textContent).toContain('"kept": "as stored"')
  })

  it("says what a v1 document cannot contain rather than showing empty v2 blocks", () => {
    const { supplied_inputs: _s, capture_problems: _c, implementation: _i, future_block: _f, ...v1 } = v2
    render(<FinancialEvidenceView financial={financial({ financial_document: { format: "juval.adr047.financial-record", version: 1, payload: { ...v1, version: 1 } } })} />)
    expect(screen.getByText(/v1 documents do not store supplied inputs/)).toBeInTheDocument()
    expect(screen.queryByRole("table", { name: "Supplied inputs" })).not.toBeInTheDocument()
  })

  it("shows a record with diagnostics but no document, and disagreements without choosing a side", () => {
    render(<FinancialEvidenceView financial={financial({ financial_document: null, inconsistencies: ["document lists 1 problem, diagnostics 2"] })} />)
    expect(screen.getByText(/no financial document was stored/i)).toBeInTheDocument()
    expect(screen.getByRole("table", { name: "Capture diagnostics" })).toBeInTheDocument()
    expect(screen.getByText("document lists 1 problem, diagnostics 2")).toBeInTheDocument()
  })

  it("never fails on an unexpected value encoding; it shows it verbatim", () => {
    const odd = { ...v2, calculations: { calculations: [{ result: "PROFIT", value: { value: { money: "1.00" }, provenance: prov("VERIFIED", "x") } }] } }
    render(<FinancialEvidenceView financial={financial({ financial_document: { format: "juval.adr047.financial-record", version: 2, payload: odd } })} />)
    expect(rowOf("Calculated results", "PROFIT")).toHaveTextContent('{"money":"1.00"}')
  })
})
