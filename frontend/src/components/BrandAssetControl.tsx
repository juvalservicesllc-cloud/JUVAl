import { useState, type ChangeEvent } from "react"
import { readBrandAsset, validateBrandAsset } from "../theme/storage"

export function BrandAssetControl({ label, value, onChange, description }: { label: string; value: string | null; onChange: (value: string | null) => void; description: string }) {
  const [error, setError] = useState<string | null>(null)
  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    const message = validateBrandAsset(file)
    if (message) { setError(message); event.target.value = ""; return }
    try { onChange(await readBrandAsset(file)); setError(null) } catch (readError) { setError(readError instanceof Error ? readError.message : "The image could not be read.") }
  }
  return <section className="asset-control"><div><strong>{label}</strong><p>{description}</p></div>{value ? <img className="asset-preview" src={value} alt={`${label} preview`} /> : <div className="asset-placeholder">No asset selected</div>}<div className="asset-actions"><label className="secondary-button">{value ? "Replace" : "Upload"}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={handleFile} /></label>{value && <button className="text-button danger-button" type="button" onClick={() => onChange(null)}>Remove</button>}</div>{error && <p className="form-error" role="alert">{error}</p>}</section>
}
