import { createContext } from "react"
import type { AppearanceMode, ThemeColors, ThemeSettings } from "./types"

export type ThemeContextValue = {
  settings: ThemeSettings
  setColor: (key: keyof ThemeColors, value: string) => void
  updateSettings: (updates: Partial<ThemeSettings>) => void
  setAppearanceMode: (mode: AppearanceMode) => void
  reset: () => void
  storageError: string | null
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
