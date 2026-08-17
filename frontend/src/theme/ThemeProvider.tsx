import { useEffect, useState, type ReactNode } from "react"
import { appearancePalettes, defaultThemeSettings } from "./presets"
import { clearThemeSettings, loadThemeSettings, saveThemeSettings } from "./storage"
import { ThemeContext } from "./ThemeContext"
import type { AppearanceMode, ThemeColors, ThemeSettings } from "./types"

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<ThemeSettings>(loadThemeSettings)
  const [storageError, setStorageError] = useState<string | null>(null)

  useEffect(() => {
    const root = document.documentElement
    const { colors } = settings
    root.style.setProperty("--bg", colors.background)
    root.style.setProperty("--sidebar", colors.sidebar)
    root.style.setProperty("--header", colors.header)
    root.style.setProperty("--surface", colors.surface)
    root.style.setProperty("--surface-raised", settings.appearanceMode === "dark" ? "#2b2f37" : "#eef2f7")
    root.style.setProperty("--surface-hover", settings.appearanceMode === "dark" ? "#30343d" : "#e7ecf4")
    root.style.setProperty("--text-primary", colors.text)
    root.style.setProperty("--text-secondary", colors.muted)
    root.style.setProperty("--text-muted", colors.muted)
    root.style.setProperty("--border", colors.border)
    root.style.setProperty("--border-strong", colors.border)
    root.style.setProperty("--accent", colors.accent)
    root.style.setProperty("--accent-soft", `${colors.accent}22`)
    root.style.setProperty("--app-background-image", settings.backgroundImageDataUrl ? `url("${settings.backgroundImageDataUrl}")` : "none")
    root.style.setProperty("--app-background-size", settings.backgroundSize)
    root.style.setProperty("--app-background-position", settings.backgroundPosition)
    root.style.setProperty("--app-overlay-opacity", String(settings.backgroundImageDataUrl ? settings.overlayOpacity : 0))
    root.style.setProperty("--app-overlay-color", settings.appearanceMode === "dark" ? "12, 14, 18" : "245, 247, 251")
    try { saveThemeSettings(settings); setStorageError(null) } catch { setStorageError("Live preview is active, but this browser could not save the appearance settings.") }
  }, [settings])

  const updateSettings = (updates: Partial<ThemeSettings>) => setSettings((current) => ({ ...current, ...updates, preset: updates.preset ?? "custom" }))
  const setColor = (key: keyof ThemeColors, value: string) => setSettings((current) => ({ ...current, preset: "custom", colors: { ...current.colors, [key]: value } }))
  const setAppearanceMode = (appearanceMode: AppearanceMode) => setSettings((current) => ({ ...current, appearanceMode, colors: { ...appearancePalettes[appearanceMode], accent: current.colors.accent } }))
  const reset = () => { try { clearThemeSettings(); setStorageError(null) } catch { setStorageError("Defaults are active, but this browser could not clear saved appearance settings.") } setSettings(defaultThemeSettings) }

  return <ThemeContext.Provider value={{ settings, setColor, updateSettings, setAppearanceMode, reset, storageError }}>{children}</ThemeContext.Provider>
}
