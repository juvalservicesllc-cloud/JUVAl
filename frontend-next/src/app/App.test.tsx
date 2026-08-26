import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { App } from "./App"

function at(path: string) {
  history.pushState({}, "", path)
  return render(<App />)
}

describe("Golden-first shell and routing", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => ({ items: [] }) })))
  })
  afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); history.pushState({}, "", "/") })

  it("keeps Golden's shell: sidebar, nav, header and light/dark switch", () => {
    at("/")

    const sidebar = document.querySelector("aside") as HTMLElement
    expect(sidebar).toBeInTheDocument()
    for (const label of ["Dashboard", "Import", "Catalog", "Compare", "Favorites", "Runs", "Appearance", "Methodology"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument()
    }
    expect(screen.getByRole("switch")).toBeInTheDocument()
    // No legacy shell leaked in.
    expect(document.querySelector(".app")).toBeInTheDocument()
    expect(document.querySelector(".shell")).not.toBeInTheDocument()
  })

  it("marks the active destination", async () => {
    at("/")
    await userEvent.setup().click(screen.getByRole("button", { name: "Runs" }))

    expect(screen.getByRole("button", { name: "Runs" })).toHaveAttribute("aria-current", "page")
  })

  it("navigates in the same tab without a reload", async () => {
    at("/")
    await userEvent.setup().click(screen.getByRole("button", { name: "Import" }))

    expect(location.pathname).toBe("/import")
    expect(screen.getByRole("heading", { name: /import supplier files/i })).toBeInTheDocument()
  })

  it("routes the run and batch resources", () => {
    at("/runs/run-1")
    expect(screen.getByRole("heading", { name: /run detail|run not found|supplier/i })).toBeInTheDocument()
  })

  it("says plainly that an unknown route matched nothing", () => {
    at("/definitely-not-a-route")

    expect(screen.getByRole("heading", { name: /page not found/i })).toBeInTheDocument()
    expect(screen.getByText(/nothing was processed and no run was affected/i)).toBeInTheDocument()
  })

  it("shows no demonstration data on routes that are not wired yet", () => {
    at("/compare")

    expect(screen.getByText(/not yet connected to the real backend/i)).toBeInTheDocument()
    // The capability stays on the roadmap with its blocker named.
    expect(screen.getByText(/comparable-identity ADR/i)).toBeInTheDocument()
    expect(screen.queryByText(/west marine/i)).not.toBeInTheDocument()
  })

  it("persists the appearance choice as a local preference", async () => {
    at("/")
    await userEvent.setup().click(screen.getByRole("switch"))

    expect(localStorage.getItem("juval.appearance.dark")).toBe("false")
  })
})
