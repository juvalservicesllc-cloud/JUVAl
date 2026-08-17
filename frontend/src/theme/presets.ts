import type { AppearanceMode, ThemeColors, ThemeSettings } from "./types"

export const appearancePalettes: Record<AppearanceMode, ThemeColors> = {
  light: { background: "#f5f7fb", sidebar: "#172033", header: "#ffffff", surface: "#ffffff", text: "#172033", muted: "#64748b", border: "#d9e0eb", accent: "#7c8cff" },
  dark: { background: "#181a1f", sidebar: "#121419", header: "#1d2026", surface: "#24272e", text: "#f2f4f8", muted: "#9aa1ae", border: "#373c46", accent: "#7c8cff" },
}

export const defaultThemeSettings: ThemeSettings = {
  appearanceMode: "dark",
  preset: "juval",
  colors: appearancePalettes.dark,
  logoDataUrl: null,
  backgroundImageDataUrl: null,
  backgroundSize: "cover",
  backgroundPosition: "center",
  overlayOpacity: 0.58,
}
