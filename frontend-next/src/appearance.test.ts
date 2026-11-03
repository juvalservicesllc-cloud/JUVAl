import { afterEach, expect, it, vi } from "vitest"
import { accentColors, APPEARANCE_PREFIX, contrastRatio, DEFAULT_APPEARANCE, loadAppearance, MAX_IMAGE_BYTES, readAppearanceImage, resetAppearance, saveAppearance, validImage } from "./appearance"

const png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9xkAAAAASUVORK5CYII="
afterEach(() => { vi.restoreAllMocks(); localStorage.clear() })

it("restores only validated local appearance values", () => {
  saveAppearance({ dark: false, accent: "#1a2b3c", logo: png })
  expect(loadAppearance()).toEqual({ ...DEFAULT_APPEARANCE, dark: false, accent: "#1a2b3c", logo: png })
  localStorage.setItem(APPEARANCE_PREFIX + "accent", "url(https://example.invalid)")
  localStorage.setItem(APPEARANCE_PREFIX + "logo", "data:image/svg+xml;base64,PHN2Zy8+")
  localStorage.setItem(APPEARANCE_PREFIX + "background", "https://example.invalid/image.png")
  localStorage.setItem(APPEARANCE_PREFIX + "dark", "corrupt")
  expect(loadAppearance()).toEqual(DEFAULT_APPEARANCE)
})

it("reset removes only appearance keys, including old appearance preferences", () => {
  saveAppearance({ dark: false, accent: "#123456" })
  localStorage.setItem(APPEARANCE_PREFIX + "legacy", "old")
  localStorage.setItem("juval.catalog.columns.v1", "columns")
  localStorage.setItem("juval.catalog.favorites.v1", "favorites")
  resetAppearance()
  expect(localStorage.length).toBe(2)
  expect(localStorage.getItem("juval.catalog.columns.v1")).toBe("columns")
  expect(localStorage.getItem("juval.catalog.favorites.v1")).toBe("favorites")
})

it("works when storage reads, writes and reset throw", () => {
  for (const method of ["getItem", "setItem", "key", "removeItem"] as const) vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new Error("unavailable") })
  expect(loadAppearance()).toEqual(DEFAULT_APPEARANCE)
  expect(() => saveAppearance({ dark: false })).not.toThrow()
  expect(() => resetAppearance()).not.toThrow()
})

it("computes WCAG contrast against known values", () => {
  expect(contrastRatio("#000000", "#ffffff")).toBe(21)
  expect(contrastRatio("#ffffff", "#ffffff")).toBe(1)
  expect(contrastRatio("#172033", "#f1f5f9")).toBeGreaterThan(4.5)
})

it.each(["#ffffff", "#000000", "#757575", "#ffff00", "#00ff00", "#ff0000", "#6d5dfc", "#9c92ff"])("keeps readable fill and surface text for accent %s in both themes", (accent) => {
  for (const dark of [false, true]) {
    const colors = accentColors(accent, dark)
    expect(contrastRatio(accent, colors.onAccent)).toBeGreaterThanOrEqual(4.5)
    for (const surface of dark ? ["#181b21", "#222730", "#2a303a", "#1e232b"] : ["#f5f6f8", "#ffffff", "#f9fafb"]) {
      expect(contrastRatio(surface, colors.textAccent)).toBeGreaterThanOrEqual(4.5)
    }
  }
})

it("reads raster images locally and rejects SVG, MIME spoofing and oversized data", async () => {
  const file = new File([Uint8Array.from(atob(png.split(",")[1]), (c) => c.charCodeAt(0))], "pixel.png", { type: "image/png" })
  expect(await readAppearanceImage(file)).toBe(png)
  await expect(readAppearanceImage(new File(["<svg/>"], "vector.svg", { type: "image/svg+xml" }))).rejects.toThrow(/PNG, JPEG or WebP/)
  await expect(readAppearanceImage(new File(["<svg/>"], "spoof.png", { type: "image/png" }))).rejects.toThrow(/Invalid image/)
  await expect(readAppearanceImage(new File([new Uint8Array(MAX_IMAGE_BYTES + 1)], "large.png", { type: "image/png" }))).rejects.toThrow(/512 KB/)
  expect(validImage("data:image/png;base64,%%%" )).toBe(false)
  expect(validImage("data:image/png;base64," + btoa("\x89PNG\r\n\x1a\n" + "x".repeat(MAX_IMAGE_BYTES)))).toBe(false)
})
