import { useEffect, useRef, useState } from "react"
import { accentColors, contrastRatio, IMAGE_TYPES, isAccent, readAppearanceImage, type Appearance } from "../appearance"
import "./appearance.css"

export function AppearancePage({ appearance, onChange, onReset }: {
  appearance: Appearance; onChange: (patch: Partial<Appearance>) => void; onReset: () => void
}) {
  const [hex, setHex] = useState(appearance.accent)
  const [error, setError] = useState("")
  const versions = useRef({ logo: 0, background: 0 })
  useEffect(() => () => { versions.current.logo++; versions.current.background++ }, [])
  const accent = appearance.accent || (appearance.dark ? "#9c92ff" : "#6d5dfc")
  const light = contrastRatio(appearance.accent || "#6d5dfc", "#172033")
  const dark = contrastRatio(appearance.accent || "#9c92ff", "#f1f5f9")
  const button = contrastRatio(accent, accentColors(accent, appearance.dark).onAccent)
  async function image(key: "logo" | "background", file?: File) {
    const version = ++versions.current[key]
    setError("")
    if (!file) return
    try {
      const value = await readAppearanceImage(file)
      if (version === versions.current[key]) onChange({ [key]: value })
    } catch (e) { if (version === versions.current[key]) setError(e instanceof Error ? e.message : "Image could not be read.") }
  }
  return <>
    <h1>Appearance & branding</h1>
    <section className="panel">
      <h2>Browser preferences</h2>
      <p>Appearance is stored locally in this browser when storage is available. It is not business data and does not affect records, calculations or exports. Images are never uploaded.</p>
      <label>Theme<select value={String(appearance.dark)} onChange={(e) => onChange({ dark: e.target.value === "true" })}>
        <option value="false">Light</option><option value="true">Dark</option>
      </select></label>
      <div className="appearance-inputs">
        <label>Accent color<input type="color" value={accent} onChange={(e) => { setHex(e.target.value); onChange({ accent: e.target.value }) }} /></label>
        <label>Accent hex<input value={hex} placeholder={accent} aria-invalid={hex !== "" && !isAccent(hex)} aria-describedby="accent-help" onChange={(e) => {
          const value = e.target.value
          setHex(value)
          if (value === "" || isAccent(value)) onChange({ accent: value })
        }} /></label>
      </div>
      <p id="accent-help">Use six hex digits, for example #6d5dfc. Empty uses the theme default.</p>
      <p>The selected accent is kept for fills. Button text adapts for contrast; accent text and focus outlines use a readable fallback when needed.</p>
      {hex !== "" && !isAccent(hex) && <p role="alert">Enter a valid six-digit hex color. The last valid accent is still applied.</p>}
      <p>Contrast with light-theme text: {light.toFixed(2)}:1. With dark-theme text: {dark.toFixed(2)}:1. With button text: {button.toFixed(2)}:1.</p>
      {(light < 4.5 || dark < 4.5 || button < 4.5) && <p role="status" className="notice">Insufficient contrast in one or more text combinations (WCAG AA requires 4.5:1). You can keep this accent or choose another.</p>}
      <p>PNG, JPEG and WebP only; maximum 512 KB per image. SVG is excluded.</p>
      {(["logo", "background"] as const).map((key) => <div className="appearance-inputs" key={key}>
        <label>{key === "logo" ? "Logo image" : "Background image"}<input type="file" accept={IMAGE_TYPES.join(",")} onChange={(e) => {
          void image(key, e.target.files?.[0])
          e.target.value = ""
        }} /></label>
        <button disabled={!appearance[key]} onClick={() => { versions.current[key]++; onChange({ [key]: "" }) }}>Remove {key}</button>
      </div>)}
      {error && <p role="alert">{error}</p>}
      <button onClick={() => {
        versions.current.logo++; versions.current.background++
        setHex(""); setError(""); onReset()
      }}>Reset appearance defaults</button>
    </section>
    <section className="panel appearance-preview" aria-label="Appearance preview" style={appearance.background ? { backgroundImage: `url("${appearance.background}")` } : undefined}>
      <div>
        {appearance.logo && <img className="appearance-logo" src={appearance.logo} alt="Logo preview" />}
        <h2>JUVAl preview</h2>
        <p>Your selected theme and accent. No sourcing data is shown here.</p>
        <button type="button">Accent preview</button>
      </div>
    </section>
  </>
}
