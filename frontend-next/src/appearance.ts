/** Browser-only preferences. Images never leave the browser. */
export const APPEARANCE_PREFIX = "juval.appearance."
export const MAX_IMAGE_BYTES = 512 * 1024
export const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"]
export const COLOR_LABELS = { backgroundColor: "Background", sidebarColor: "Sidebar", headerColor: "Header", surfaceColor: "Surface", textColor: "Text", mutedColor: "Muted", borderColor: "Border" } as const
export const DEFAULT_APPEARANCE = { dark: true, accent: "", logo: "", background: "", backgroundColor: "", sidebarColor: "", headerColor: "", surfaceColor: "", textColor: "", mutedColor: "", borderColor: "", backgroundFit: "cover", backgroundPosition: "center", overlayOpacity: 0 }
export type Appearance = typeof DEFAULT_APPEARANCE
export const isAccent = (value: unknown): value is string => typeof value === "string" && /^#[\da-f]{6}$/i.test(value)

export function validImage(value: unknown): value is string {
  if (typeof value !== "string" || value.length > Math.ceil(MAX_IMAGE_BYTES / 3) * 4 + 32) return false
  const match = value.match(/^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/]+={0,2})$/)
  if (!match) return false
  try {
    const bytes = atob(match[2])
    if (!bytes.length || bytes.length > MAX_IMAGE_BYTES) return false
    // Check signatures as well as the declared MIME; SVG is never accepted.
    if (match[1] === "image/png") return bytes.startsWith("\x89PNG\r\n\x1a\n")
    if (match[1] === "image/jpeg") return bytes.startsWith("\xff\xd8\xff")
    return bytes.startsWith("RIFF") && bytes.slice(8, 12) === "WEBP"
  } catch { return false }
}

export function loadAppearance(): Appearance {
  const read = (key: keyof Appearance) => {
    try { return localStorage.getItem(APPEARANCE_PREFIX + key) } catch { return null }
  }
  const accent = read("accent"), logo = read("logo"), background = read("background")
  const colors = Object.fromEntries(Object.keys(COLOR_LABELS).map((key) => { const value = read(key as keyof Appearance); return [key, isAccent(value) ? value : ""] })) as Pick<Appearance, keyof typeof COLOR_LABELS>
  const fit = read("backgroundFit"), position = read("backgroundPosition"), overlay = read("overlayOpacity")
  return { ...DEFAULT_APPEARANCE, ...colors, dark: read("dark") !== "false", accent: isAccent(accent) ? accent : "", logo: validImage(logo) ? logo : "", background: validImage(background) ? background : "", backgroundFit: fit === "contain" ? fit : "cover", backgroundPosition: position === "top" || position === "bottom" ? position : "center", overlayOpacity: overlay !== null && Number.isFinite(Number(overlay)) && Number(overlay) >= 0 && Number(overlay) <= 0.9 ? Number(overlay) : 0 }
}

/** Rendering tokens only. Preserve chosen colors; protect text on each opaque
 * surface independently when a custom combination cannot provide 4.5:1. */
export function appearanceTokens(a: Appearance): Record<string, string> {
  const tokens: Record<string, string> = {}
  const mapping = { backgroundColor: "--bg", sidebarColor: "--sidebar", headerColor: "--header", surfaceColor: "--surface", borderColor: "--border" }
  for (const [key, token] of Object.entries(mapping)) if (isAccent(a[key as keyof Appearance])) tokens[token] = a[key as keyof Appearance] as string
  const ink = (surface: string, chosen: string) => contrastRatio(surface, chosen) >= 4.5 ? chosen : accentColors(surface, a.dark).onAccent
  const text = a.textColor || (a.dark ? "#f1f5f9" : "#172033")
  const muted = a.mutedColor || (a.dark ? "#a7b0c0" : "#667085")
  const surfaces = { page: a.backgroundColor || (a.dark ? "#181b21" : "#f5f6f8"), panel: a.surfaceColor || (a.dark ? "#222730" : "#ffffff"), nav: a.sidebarColor || (a.dark ? "#1e232b" : "#ffffff"), header: a.headerColor || a.backgroundColor || (a.dark ? "#181b21" : "#f5f6f8") }
  if (Object.keys(COLOR_LABELS).some((key) => a[key as keyof Appearance])) {
    tokens["--surface-2"] = surfaces.panel
    for (const [name, surface] of Object.entries(surfaces)) {
      tokens[`--${name}-text`] = ink(surface, text)
      tokens[`--${name}-muted`] = ink(surface, muted)
      for (const [semantic, color] of Object.entries({ success: a.dark ? "#5fce99" : "#16835d", warning: a.dark ? "#f0b763" : "#a36508", danger: a.dark ? "#f4879a" : "#bd3c52" })) tokens[`--${name}-${semantic}`] = ink(surface, color)
    }
    const accent = a.accent || (a.dark ? "#9c92ff" : "#6d5dfc")
    // Neutral links remain legible on the selected reading surfaces.
    tokens["--accent-text"] = Object.values(surfaces).every((surface) => contrastRatio(surface, accent) >= 4.5) ? accent : "currentColor"
  }
  return tokens
}

export function saveAppearance(patch: Partial<Appearance>): void {
  for (const [key, value] of Object.entries(patch)) {
    try { localStorage.setItem(APPEARANCE_PREFIX + key, String(value)) } catch { /* preference only */ }
  }
}

export function resetAppearance(): void {
  try {
    const keys = Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i))
    for (const key of keys) {
      if (key?.startsWith(APPEARANCE_PREFIX)) {
        try { localStorage.removeItem(key) } catch { /* preference only */ }
      }
    }
  } catch { /* browser storage may be unavailable */ }
}

/** WCAG relative luminance and contrast; presentation only, no business data. */
export function contrastRatio(first: string, second: string): number {
  function luminance(hex: string) {
    const rgb = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255)
      .map((c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
  }
  const a = luminance(first), b = luminance(second)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** Keep the chosen fill; choose readable ink independently. Black or white
 *  always gives at least 4.5:1 on an opaque sRGB fill. For accent-colored text,
 *  check the least favorable theme surface (style.css tokens) before using it.
 *  The browser E2E also checks the actual rendered surface/color pairs. */
export function accentColors(accent: string, dark: boolean) {
  return {
    onAccent: contrastRatio(accent, "#000000") > contrastRatio(accent, "#ffffff") ? "#000000" : "#ffffff",
    textAccent: contrastRatio(accent, dark ? "#2a303a" : "#f5f6f8") >= 4.5 ? accent : dark ? "#f1f5f9" : "#172033",
  }
}

export function readAppearanceImage(file: File): Promise<string> {
  if (!IMAGE_TYPES.includes(file.type)) return Promise.reject(new Error("Use PNG, JPEG or WebP only. SVG is not supported."))
  if (file.size > MAX_IMAGE_BYTES) return Promise.reject(new Error("Image exceeds 512 KB. Choose a smaller image."))
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error("Image could not be read."))
    reader.onload = () => validImage(reader.result) ? resolve(reader.result) : reject(new Error("Invalid image content. Use PNG, JPEG or WebP."))
    reader.readAsDataURL(file)
  })
}
