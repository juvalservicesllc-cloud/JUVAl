import { render, screen } from "@testing-library/react"
import { afterEach, expect, it, vi } from "vitest"
import { App } from "../app/App"
import { MethodologyPage } from "./MethodologyPage"

afterEach(() => { vi.unstubAllGlobals(); history.pushState({}, "", "/") })

it("explains the actual workflow, decision precedence and unknown-demand gate", () => {
  render(<MethodologyPage />)
  expect(screen.getAllByRole("listitem").map((li) => li.querySelector("strong")?.textContent)).toEqual(["Import.", "Normalize.", "Validate.", "Profitability.", "Risks.", "Decision."])
  expect(screen.getByLabelText("Processing workflow")).toHaveTextContent(/XLSX and CSV share one tabular contract/)
  expect(screen.getByLabelText("Processing workflow")).toHaveTextContent(/PASS rules take precedence over REVIEW/)
  expect(screen.getByText(/Unknown demand leads/)).toHaveTextContent(/does not feed the Decision Engine or enable BUY/)
  expect(screen.getByText(/Decision Score is experimental/)).toBeInTheDocument()
})

it("keeps provenance states and demonstration labels distinct and discloses unimplemented capabilities", () => {
  render(<MethodologyPage />)
  for (const status of ["VERIFIED", "INFERRED", "NOT FOUND", "INVALID", "DEMO FIXTURE"]) expect(screen.getByLabelText(`Status: ${status}`)).toBeInTheDocument()
  expect(screen.getByText(/A demonstration label/)).toHaveTextContent(/not a verification state/)
  expect(screen.getByText(/No external data sources/)).toHaveTextContent(/Amazon and Keepa are not connected/)
  expect(screen.getByText(/AI analyst is not implemented/)).toBeInTheDocument()
})

it("wires /about as a static page without a network request", () => {
  const fetch = vi.fn()
  vi.stubGlobal("fetch", fetch)
  history.pushState({}, "", "/about")
  render(<App />)
  expect(screen.getByRole("heading", { level: 1, name: "Methodology" })).toBeInTheDocument()
  expect(screen.queryByText(/Not yet connected/)).not.toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalled()
})
