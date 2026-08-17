import { beforeEach, describe, expect, it } from "vitest"
import { defaultThemeSettings } from "./presets"
import { MAX_BRAND_ASSET_BYTES, loadThemeSettings, saveThemeSettings, validateBrandAsset } from "./storage"

describe("theme storage", () => {
  beforeEach(() => localStorage.clear())

  it("falls back to JUVAl defaults for corrupt local settings", () => {
    localStorage.setItem("juval-theme-settings-v1", "not json")
    expect(loadThemeSettings()).toEqual(defaultThemeSettings)
  })

  it("persists a valid custom setting", () => {
    const settings = { ...defaultThemeSettings, preset: "custom" as const, colors: { ...defaultThemeSettings.colors, accent: "#112233" } }
    saveThemeSettings(settings)
    expect(loadThemeSettings().colors.accent).toBe("#112233")
    expect(loadThemeSettings().appearanceMode).toBe("dark")
  })

  it("migrates legacy light settings without losing their colors", () => {
    const { appearanceMode: _appearanceMode, ...legacySettings } = defaultThemeSettings
    localStorage.setItem("juval-theme-settings-v1", JSON.stringify({ ...legacySettings, preset: "light" }))
    expect(loadThemeSettings()).toMatchObject({ appearanceMode: "light", preset: "juval" })
  })

  it("rejects unsupported and oversized brand assets", () => {
    expect(validateBrandAsset(new File(["svg"], "logo.svg", { type: "image/svg+xml" }))).toMatch(/PNG, JPEG, or WEBP/)
    expect(validateBrandAsset(new File([new Uint8Array(MAX_BRAND_ASSET_BYTES + 1)], "logo.png", { type: "image/png" }))).toMatch(/400 KB/)
  })
})
