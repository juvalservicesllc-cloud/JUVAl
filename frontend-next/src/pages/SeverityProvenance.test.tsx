import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { ProvenanceStatus, SeveritySourceType } from "../api/types"
import { SeverityProvenance } from "./SeverityProvenance"

const show = (status: ProvenanceStatus | null | undefined, sourceType: SeveritySourceType | null | undefined, compact = false) =>
  render(<p data-testid="cell"><SeverityProvenance risk="HazMat" status={status} sourceType={sourceType} compact={compact} /></p>)

describe("Severity provenance (ADR-020), shown as stored", () => {
  it.each([
    ["INFERRED", "CALCULATED", "JUVAl classification (inferred)", "JUVAl", "prov-inferred"],
    ["VERIFIED", "SUPPLIER_FILE", "Absence declared in supplier file", "file", "prov-verified"],
    ["NOT_FOUND", "NOT_FOUND", "Not found", "N/F", "prov-not-found"],
    ["INVALID", "SUPPLIER_FILE", "Invalid in supplier file", "INV", "prov-invalid"],
  ] as const)("%s / %s reads as “%s”", (status, source, label, short, tone) => {
    const { unmount } = show(status, source)
    const full = screen.getByLabelText(`HazMat severity provenance: ${label}`)
    expect(full).toHaveTextContent(label)
    expect(full).toHaveClass("prov", tone)
    unmount()

    show(status, source, true)
    const compact = screen.getByLabelText(`HazMat severity provenance: ${label}`)
    expect(compact).toHaveTextContent(short)
    // Compact is never hover-only: the full words are in the accessible name and the title.
    expect(compact).toHaveAttribute("title", `Severity: ${label} — not an Amazon verification`)
  })

  it.each([null, undefined])("renders nothing for a historical snapshot (%s), never a default state", (missing) => {
    show(missing, missing)
    expect(screen.getByTestId("cell")).toBeEmptyDOMElement()
  })

  it("does not derive a state from the source type alone", () => {
    show(null, "SUPPLIER_FILE")
    expect(screen.getByTestId("cell")).toBeEmptyDOMElement()
  })

  it("shows an unexpected pair literally instead of interpreting it", () => {
    show("VERIFIED", "AUTHORIZED_EXTERNAL_SOURCE")
    expect(screen.getByLabelText("HazMat severity provenance: VERIFIED · AUTHORIZED_EXTERNAL_SOURCE")).toBeInTheDocument()
  })

  it("never claims an Amazon or source verification", () => {
    for (const [status, source] of [["INFERRED", "CALCULATED"], ["VERIFIED", "SUPPLIER_FILE"], ["NOT_FOUND", "NOT_FOUND"], ["INVALID", "SUPPLIER_FILE"]] as const) {
      const { container, unmount } = show(status, source)
      const text = `${container.textContent} ${container.querySelector("em")?.getAttribute("title")}`
      expect(text).not.toMatch(/verified by amazon|amazon[- ]verified|VERIFIED_SOURCE|verified source/i)
      expect(text).not.toMatch(/^\s*VERIFIED\b/)
      unmount()
    }
  })
})
