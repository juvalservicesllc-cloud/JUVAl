import type { ThemeColors, ThemePreset, ThemeSettings } from "./types"

export const themePresets: Record<Exclude<ThemePreset, "custom">, ThemeColors> = {
  juval: { background: "#0c0d10", sidebar: "#101115", header: "#0c0d10", surface: "#15171c", text: "#eef0f5", muted: "#717887", border: "#292d36", accent: "#7c8cff" },
  light: { background: "#f5f7fb", sidebar: "#172033", header: "#ffffff", surface: "#ffffff", text: "#172033", muted: "#64748b", border: "#d9e0eb", accent: "#4f46e5" },
  dark: { background: "#101216", sidebar: "#0a0c10", header: "#151820", surface: "#1a1e27", text: "#f5f7fb", muted: "#929aab", border: "#323846", accent: "#54a6ff" },
}

export const defaultThemeSettings: ThemeSettings = {
  preset: "juval",
  colors: themePresets.juval,
  logoDataUrl: null,
  backgroundImageDataUrl: null,
  backgroundSize: "cover",
  backgroundPosition: "center",
  overlayOpacity: 0.58,
}
