import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it } from "vitest"
import { AppearanceModeSwitch } from "../components/AppearanceModeSwitch"
import { ThemeProvider } from "./ThemeProvider"
import { useTheme } from "./useTheme"

function ModeHarness() {
  const { settings, setAppearanceMode } = useTheme()
  return <AppearanceModeSwitch mode={settings.appearanceMode} onChange={setAppearanceMode} />
}

describe("appearance mode drives the native color scheme", () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.style.colorScheme = ""
  })

  // Native controls the browser paints itself -- select dropdowns, scrollbars,
  // focus rings -- ignore our custom properties and follow `color-scheme`.
  // Without it the Catalog's filter selects track the OS instead of the
  // appearance the operator chose.
  it("declares color-scheme so UA controls follow the app, not the OS", async () => {
    render(<ThemeProvider><ModeHarness /></ThemeProvider>)
    const initial = document.documentElement.style.colorScheme
    expect(["light", "dark"]).toContain(initial)

    await userEvent.click(screen.getByRole("switch", { name: /appearance mode/i }))
    const toggled = document.documentElement.style.colorScheme
    expect(["light", "dark"]).toContain(toggled)
    expect(toggled).not.toBe(initial)
  })
})
