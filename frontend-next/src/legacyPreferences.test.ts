import { afterEach, expect, it, vi } from "vitest"
import { importLegacyPreferences, legacyPreference } from "./legacyPreferences"
import { loadAppearance } from "./appearance"
import { loadColumns } from "./catalogColumns"
afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); sessionStorage.clear() })
const theme = { appearanceMode: "light", colors: { background: "#ffffff", sidebar: "#111111", header: "#eeeeee", surface: "#eeeeee", text: "#111111", muted: "#555555", border: "#666666", accent: "#123456" }, logoDataUrl: null, backgroundImageDataUrl: null, backgroundSize: "contain", backgroundPosition: "top", overlayOpacity: 0.2 }

it("previews and imports appearance only on request, preserving legacy and current settings", () => {
  localStorage.setItem("juval-theme-settings-v1", JSON.stringify({ ...theme, appearanceMode: undefined, preset: "custom" }))
  expect(legacyPreference("appearance").values["juval.appearance.dark"]).toBe("true")
  const original = JSON.stringify(theme)
  localStorage.setItem("juval-theme-settings-v1", original)
  expect(legacyPreference("appearance").reason).toBe("")
  expect(localStorage.getItem("juval.appearance.dark")).toBeNull()
  expect(importLegacyPreferences("appearance")).toMatch(/^Imported/)
  expect(loadAppearance()).toMatchObject({ dark: false, accent: "#123456", backgroundFit: "contain", overlayOpacity: 0.2 })
  expect(localStorage.getItem("juval-theme-settings-v1")).toBe(original)
  localStorage.setItem("juval.appearance.accent", "#ffffff")
  expect(importLegacyPreferences("appearance")).toMatch(/not be overwritten/)
  expect(loadAppearance().accent).toBe("#ffffff")
})
it("maps column identities without losing title, and excludes dataset fields from filters", () => {
  localStorage.setItem("juval.catalog.columns.v4", JSON.stringify(["product", "decision", "record_ref", "identity"]))
  expect(importLegacyPreferences("columns")).toMatch(/^Imported/)
  const columns = loadColumns()
  expect(columns.slice(0, 2)).toEqual([{ id: "title", visible: true }, { id: "sku", visible: true }])
  expect(columns.find((c) => c.id === "profit")?.visible).toBe(false)
  sessionStorage.setItem("juval.catalog.query.v1", JSON.stringify({ decision: "REVIEW", minRoi: "30", offset: 80, runId: "never", brand: "never", records: ["never"] }))
  expect(importLegacyPreferences("filters")).toMatch(/^Imported/)
  expect(JSON.parse(sessionStorage.getItem("juval.next.catalog.query.v1")!)).toEqual({ decision: "REVIEW", minRoi: "30" })
  expect(importLegacyPreferences("filters")).toMatch(/not be overwritten/)
})
it("rejects unsafe legacy images and rolls back only its writes after quota failure", () => {
  localStorage.setItem("juval-theme-settings-v1", JSON.stringify({ ...theme, logoDataUrl: "data:image/svg+xml;base64,PHN2Zz4=" }))
  expect(legacyPreference("appearance").reason).toMatch(/invalid/)
  localStorage.setItem("juval-theme-settings-v1", JSON.stringify(theme))
  const real = Storage.prototype.setItem
  let count = 0
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
    if (++count === 2) throw new Error("quota")
    real.call(this, key, value)
  })
  expect(importLegacyPreferences("appearance")).toMatch(/failed/)
  expect(Object.keys(localStorage)).toEqual(["juval-theme-settings-v1"])
})
