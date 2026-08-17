import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import App from "../App"
import { defaultThemeSettings } from "../theme/presets"

describe("AppearancePage", () => {
  afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })

  it("switches appearance mode and resets local customization", async () => {
    const user = userEvent.setup()
    vi.spyOn(window, "confirm").mockReturnValue(true)
    window.history.pushState({}, "", "/appearance")
    render(<App />)

    const switchControl = screen.getByRole("switch", { name: /appearance mode/i })
    expect(switchControl).toHaveAttribute("aria-checked", "true")
    await user.click(switchControl)
    await waitFor(() => expect(document.documentElement.style.getPropertyValue("--bg")).toBe("#f5f7fb"))
    expect(switchControl).toHaveAttribute("aria-checked", "false")
    await user.click(screen.getByRole("button", { name: /reset to juval defaults/i }))
    await waitFor(() => expect(document.documentElement.style.getPropertyValue("--bg")).toBe("#181a1f"))
  })

  it("preserves accent and local brand assets when changing mode", async () => {
    const user = userEvent.setup()
    localStorage.setItem("juval-theme-settings-v1", JSON.stringify({ ...defaultThemeSettings, appearanceMode: "light", colors: { ...defaultThemeSettings.colors, accent: "#112233" }, logoDataUrl: "data:image/png;base64,AA==", backgroundImageDataUrl: "data:image/png;base64,AA==" }))
    window.history.pushState({}, "", "/appearance")
    render(<App />)

    await user.click(screen.getByRole("switch", { name: /appearance mode/i }))
    await waitFor(() => expect(document.documentElement.style.getPropertyValue("--bg")).toBe("#181a1f"))
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("#112233")
    expect(document.documentElement.style.getPropertyValue("--app-background-image")).toContain("data:image/png")
    expect(screen.getByAltText("Workspace logo")).toBeInTheDocument()
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
