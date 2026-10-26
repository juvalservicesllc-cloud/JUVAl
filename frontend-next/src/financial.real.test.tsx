/**
 * Opt-in: render real `GET /api/v1/runs/{id}/financial` output through the
 * evidence view. Skipped unless JUVAL_FINANCIAL_JSON names a saved response
 * (for example from a disposable API fed the synthetic rows of
 * tests/integration/test_api_financial_flow.py). Nothing is committed from it.
 */
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { RecordFinancialOut } from "./api/types"
import { FinancialEvidenceView } from "./pages/FinancialEvidence"

declare const process: { env: Record<string, string | undefined> }
const PATH = process.env.JUVAL_FINANCIAL_JSON

describe.skipIf(!PATH)("real stored ADR-047 evidence", () => {
  it("renders every stored record, every exact calculated value and every blocker", async () => {
    const { readFileSync } = await import("node:" + "fs") as { readFileSync(path: string, encoding: "utf8"): string }
    const response = JSON.parse(readFileSync(PATH!, "utf8")) as { records: RecordFinancialOut[] }
    expect(response.records.length).toBeGreaterThan(0)
    for (const record of response.records) {
      const { unmount } = render(<FinancialEvidenceView financial={record} />)
      const calculations = ((record.financial_document?.payload as { calculations?: { calculations?: { value: { value: { decimal?: string } | null }; blocker: string | null }[] } })?.calculations?.calculations) ?? []
      for (const c of calculations) {
        if (c.value.value?.decimal) expect(document.body.textContent).toContain(c.value.value.decimal)
        if (c.blocker) expect(document.body.textContent).toContain(c.blocker)
      }
      expect(screen.queryByText("Other stored fields")).not.toBeInTheDocument()   // the view knows every real key
      unmount()
    }
  })
})
