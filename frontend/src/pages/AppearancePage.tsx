import { useState } from "react"
import { AppearanceModeSwitch } from "../components/AppearanceModeSwitch"
import { BrandAssetControl } from "../components/BrandAssetControl"
import { ColorControl } from "../components/ColorControl"
import { useTheme } from "../theme/useTheme"
import type { ThemeColors } from "../theme/types"

const colorLabels: Record<keyof ThemeColors, string> = { accent: "Accent", sidebar: "Sidebar", header: "Header", background: "App background", surface: "Card surface", text: "Text", muted: "Muted text", border: "Borders" }

export function AppearancePage() {
  const { settings, setColor, updateSettings, setAppearanceMode, reset, storageError } = useTheme()
  const [selectedColor, setSelectedColor] = useState<keyof ThemeColors>("accent")
  const contrast = contrastRatio(settings.colors.text, settings.colors.surface)
  const needsContrastWarning = contrast !== null && contrast < 3.5
  const resetTheme = () => { if (window.confirm("Reset appearance mode, branding, and local brand assets?")) reset() }

  return <><div className="page-intro"><div><p className="eyebrow">WORKSPACE SETTINGS</p><h2>Appearance</h2><p>Choose a comfortable mode, then customize the local workspace brand.</p></div><button className="secondary-button" type="button" onClick={resetTheme}>Reset to JUVAl defaults</button></div>{storageError && <p className="contrast-warning" role="alert">{storageError}</p>}<div className="appearance-layout"><div className="appearance-main"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">APPEARANCE MODE</p><h2>Light or dark</h2><p>Mode updates structural surfaces immediately while preserving your accent and local assets.</p></div></div><div className="mode-control-row"><AppearanceModeSwitch mode={settings.appearanceMode} onChange={setAppearanceMode} /><span className="preset-state">{settings.appearanceMode === "dark" ? "Dark mode active" : "Light mode active"}</span></div></section><section className="panel"><div className="panel-heading"><div><p className="eyebrow">BRANDING COLORS</p><h2>Visual system</h2><p>Customize tokens after selecting a mode. Accent and assets survive mode changes.</p></div></div><div className="token-grid">{(Object.keys(colorLabels) as (keyof ThemeColors)[]).map((key) => <button className={`token-button ${selectedColor === key ? "selected" : ""}`} type="button" key={key} onClick={() => setSelectedColor(key)}><span style={{ background: settings.colors[key] }} />{colorLabels[key]}</button>)}</div><ColorControl key={selectedColor} label={colorLabels[selectedColor]} value={settings.colors[selectedColor]} onChange={(value) => setColor(selectedColor, value)} />{needsContrastWarning && <p className="contrast-warning" role="status">Text-to-surface contrast is low. Consider a lighter text or darker surface.</p>}</section><section className="panel"><div className="panel-heading"><div><p className="eyebrow">BRAND ASSETS</p><h2>Logo and background</h2><p>Stored locally in this browser. PNG, JPEG, and WEBP only; 400 KB maximum per asset.</p></div></div><div className="asset-grid"><BrandAssetControl label="Workspace logo" value={settings.logoDataUrl} onChange={(logoDataUrl) => updateSettings({ logoDataUrl })} description="Replaces the sidebar monogram." /><BrandAssetControl label="Background image" value={settings.backgroundImageDataUrl} onChange={(backgroundImageDataUrl) => updateSettings({ backgroundImageDataUrl })} description="Surfaces remain opaque to protect readability." /></div>{settings.backgroundImageDataUrl && <div className="background-options"><label>Fit<select value={settings.backgroundSize} onChange={(event) => updateSettings({ backgroundSize: event.target.value as "cover" | "contain" })}><option value="cover">Cover</option><option value="contain">Contain</option></select></label><label>Position<select value={settings.backgroundPosition} onChange={(event) => updateSettings({ backgroundPosition: event.target.value as "center" | "top" | "bottom" })}><option value="center">Center</option><option value="top">Top</option><option value="bottom">Bottom</option></select></label><label>Overlay {Math.round(settings.overlayOpacity * 100)}%<input aria-label="Background overlay opacity" type="range" min="0" max="0.9" step="0.05" value={settings.overlayOpacity} onChange={(event) => updateSettings({ overlayOpacity: Number(event.target.value) })} /></label></div>}</section></div><aside className="appearance-preview panel"><p className="eyebrow">LIVE PREVIEW</p><h2>Operational canvas</h2><div className="preview-canvas"><div className="preview-nav" style={{ background: settings.colors.sidebar }} /><div><span style={{ color: settings.colors.muted }}>JUVAl / Preview</span><strong style={{ color: settings.colors.text }}>Catalog review</strong><div className="preview-card" style={{ background: settings.colors.surface, borderColor: settings.colors.border }}><i style={{ background: settings.colors.accent }} /><b style={{ color: settings.colors.text }}>Ready to process</b></div></div></div><small>Changes are already applied to the full workspace.</small></aside></div></>
}

function contrastRatio(first: string, second: string) {
  const parse = (hex: string) => /^#([0-9a-f]{6})$/i.exec(hex)?.[1]
  const firstValue = parse(first); const secondValue = parse(second)
  if (!firstValue || !secondValue) return null
  const luminance = (value: string) => {
    const channels = [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16) / 255).map((channel) => channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
  }
  const [light, dark] = [luminance(firstValue), luminance(secondValue)].sort((a, b) => b - a)
  return (light + 0.05) / (dark + 0.05)
}
