import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"
import { NotFoundPage } from "./NotFoundPage"

// C1.1 -- unknown-route experience recovered from Golden (ADR-029).
describe("NotFoundPage", () => {
  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="*" element={<NotFoundPage />} /></Routes>
      </MemoryRouter>,
    )
  }

  it("explains that the route does not exist and names the address", () => {
    renderAt("/definitely-not-a-route")

    expect(screen.getByRole("heading", { name: /that page does not exist/i })).toBeInTheDocument()
    expect(screen.getByText("/definitely-not-a-route")).toBeInTheDocument()
  })

  it("never implies that data was processed or lost", () => {
    renderAt("/nope")

    expect(screen.getByText(/nothing was processed and no run was affected/i)).toBeInTheDocument()
  })

  it("offers same-tab recovery into the app, not a reload", () => {
    renderAt("/nope")

    const dashboard = screen.getByRole("link", { name: /back to dashboard/i })
    expect(dashboard).toHaveAttribute("href", "/")
    // Internal navigation stays in this tab (shared UX rule).
    expect(dashboard).not.toHaveAttribute("target")
    expect(screen.getByRole("link", { name: /processing runs/i })).toHaveAttribute("href", "/runs")
    expect(screen.getByRole("link", { name: /catalog/i })).toHaveAttribute("href", "/products")
  })
})
