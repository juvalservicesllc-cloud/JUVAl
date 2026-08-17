import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { RunsPage } from "./RunsPage"

describe("RunsPage", () => {
  it("clearly labels its current rows as demo data", () => {
    render(<RunsPage />)
    expect(screen.getByText("DEMO MODE")).toBeInTheDocument()
    expect(screen.getByText("run-20260817-0942")).toBeInTheDocument()
    expect(screen.getByText("SUCCESS")).toBeInTheDocument()
  })
})
