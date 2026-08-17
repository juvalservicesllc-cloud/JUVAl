export type ThemeColors = {
  background: string
  sidebar: string
  header: string
  surface: string
  text: string
  muted: string
  border: string
  accent: string
}

export type ThemePreset = "juval" | "light" | "dark" | "custom"

export interface ThemeSettings {
  preset: ThemePreset
  colors: ThemeColors
  logoDataUrl: string | null
  backgroundImageDataUrl: string | null
  backgroundSize: "cover" | "contain"
  backgroundPosition: "center" | "top" | "bottom"
  overlayOpacity: number
}
