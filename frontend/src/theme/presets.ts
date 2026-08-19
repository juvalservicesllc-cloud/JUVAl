import type { AppearanceMode, ThemeColors, ThemeSettings } from "./types"

export const appearancePalettes: Record<AppearanceMode, ThemeColors> = {
  light: { background: "#f7f8fb", sidebar: "#14161b", header: "#ffffff", surface: "#ffffff", text: "#16181d", muted: "#56606f", border: "#e2e5ec", accent: "#4f5fe0" },
  dark: { background: "#14161b", sidebar: "#101216", header: "#14161b", surface: "#1a1d24", text: "#eef0f5", muted: "#9aa2b0", border: "#262a33", accent: "#6a7bff" },
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
