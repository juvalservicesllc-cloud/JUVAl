import { defaultThemeSettings } from "./presets"
import type { ThemeSettings } from "./types"

const STORAGE_KEY = "juval-theme-settings-v1"
const imageTypes = new Set(["image/png", "image/jpeg", "image/webp"])
export const MAX_BRAND_ASSET_BYTES = 400 * 1024

export function loadThemeSettings(): ThemeSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return defaultThemeSettings
    const value: unknown = JSON.parse(raw)
    return normalizeThemeSettings(value) ?? defaultThemeSettings
  } catch {
    return defaultThemeSettings
  }
}

export function saveThemeSettings(settings: ThemeSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

export function clearThemeSettings() {
  localStorage.removeItem(STORAGE_KEY)
}

export function validateBrandAsset(file: File): string | null {
  if (!imageTypes.has(file.type)) return "Use a PNG, JPEG, or WEBP image."
  if (file.size > MAX_BRAND_ASSET_BYTES) return "Image must be 400 KB or smaller for local browser storage."
  return null
}

export function readBrandAsset(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error("The image could not be read."))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(file)
  })
}

function normalizeThemeSettings(value: unknown): ThemeSettings | null {
  if (!value || typeof value !== "object") return null
  const settings = value as Record<string, unknown>
  const colors = settings.colors
  if (!colors || typeof colors !== "object") return null
  const keys = ["background", "sidebar", "header", "surface", "text", "muted", "border", "accent"]
  const legacyPreset = String(settings.preset)
  const appearanceMode = settings.appearanceMode === "light" || settings.appearanceMode === "dark"
    ? settings.appearanceMode
    : legacyPreset === "light" ? "light" : "dark"
  const valid = keys.every((key) => typeof (colors as Record<string, unknown>)[key] === "string")
    && (settings.logoDataUrl === null || typeof settings.logoDataUrl === "string")
    && (settings.backgroundImageDataUrl === null || typeof settings.backgroundImageDataUrl === "string")
    && ["cover", "contain"].includes(String(settings.backgroundSize))
    && ["center", "top", "bottom"].includes(String(settings.backgroundPosition))
    && typeof settings.overlayOpacity === "number" && settings.overlayOpacity >= 0 && settings.overlayOpacity <= 0.9
  if (!valid) return null
  return { ...(settings as Omit<ThemeSettings, "appearanceMode" | "preset">), appearanceMode, preset: legacyPreset === "custom" ? "custom" : "juval" }
}
