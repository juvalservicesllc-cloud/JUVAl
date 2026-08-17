import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ProductsPage } from "./ProductsPage"

describe("ProductsPage", () => {
  it("labels fixtures as demo data and renders distinct provenance badges", () => {
    render(<ProductsPage />)
    expect(screen.getByText("DEMO MODE")).toBeInTheDocument()
    expect(screen.getByText("Marine Sealant 3 oz")).toBeInTheDocument()
    expect(screen.getAllByText("VERIFIED").length).toBeGreaterThan(0)
    expect(screen.getAllByText("INFERRED").length).toBeGreaterThan(0)
    expect(screen.getByText("NOT FOUND")).toBeInTheDocument()
  })
})
