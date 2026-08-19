import { useEffect, useState } from "react"
import { HexColorPicker } from "react-colorful"

const swatches = ["#6a7bff", "#4f5fe0", "#54a6ff", "#34c77b", "#e0a940", "#e2646c", "#ffffff", "#14161b"]

export function ColorControl({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const validValue = /^#[0-9a-f]{6}$/i.test(value) ? value : "#6a7bff"
  const [hex, setHex] = useState(validValue.toUpperCase())
  useEffect(() => setHex(validValue.toUpperCase()), [validValue])
  function update(next: string) { setHex(next.toUpperCase()); if (/^#[0-9a-f]{6}$/i.test(next)) onChange(next) }
  return <section className="color-control"><div className="color-control-heading"><div><span className="color-dot" style={{ background: validValue }} /><strong>{label}</strong></div><code>{validValue.toUpperCase()}</code></div><HexColorPicker color={validValue} onChange={onChange} /><div className="color-hex-row"><label>HEX<input aria-label={`${label} HEX`} value={hex} onChange={(event) => { const next = event.target.value; if (/^#[0-9a-f]{0,6}$/i.test(next)) update(next) }} /></label></div><div className="swatch-row" aria-label={`${label} swatches`}>{swatches.map((swatch) => <button key={swatch} type="button" aria-label={`Use ${swatch}`} className="swatch" style={{ background: swatch }} onClick={() => onChange(swatch)} />)}</div></section>
}
