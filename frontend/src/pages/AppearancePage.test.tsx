import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import App from "../App"

describe("AppearancePage", () => {
  afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it("applies a preset and resets local customization", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    window.history.pushState({}, "", "/appearance")
    render(<App />)

    await user.click(screen.getByRole("button", { name: "Light" }))
    await waitFor(() => expect(document.documentElement.style.getPropertyValue("--bg")).toBe("#f5f7fb"))
    await user.click(screen.getByRole("button", { name: /reset to juval defaults/i }))
    await waitFor(() => expect(document.documentElement.style.getPropertyValue("--bg")).toBe("#0c0d10"))
  })

  it("updates the selected color token from HEX", async () => {
    const user = userEvent.setup()
    window.history.pushState({}, "", "/appearance")
    render(<App />)
    await user.click(screen.getByRole("button", { name: "Sidebar" }))
    const input = screen.getByLabelText("Sidebar HEX")
    fireEvent.change(input, { target: { value: "#123456" } })
    await waitFor(() => expect(document.documentElement.style.getPropertyValue("--sidebar")).toBe("#123456"))
  })
})
