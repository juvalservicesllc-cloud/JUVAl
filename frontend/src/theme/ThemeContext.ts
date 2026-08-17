import { createContext } from "react"
import type { ThemeColors, ThemePreset, ThemeSettings } from "./types"

export type ThemeContextValue = {
  settings: ThemeSettings
  setColor: (key: keyof ThemeColors, value: string) => void
  updateSettings: (updates: Partial<ThemeSettings>) => void
  applyPreset: (preset: Exclude<ThemePreset, "custom">) => void
  reset: () => void
  storageError: string | null
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
