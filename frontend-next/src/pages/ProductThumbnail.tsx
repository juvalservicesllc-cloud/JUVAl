import { useState } from "react"
import "./catalog-density.css"

export function ProductThumbnail({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(!src)
  return <span className="catalog-table-image">{failed ? <span aria-label="Supplier image unavailable">No image</span> : <img src={src} alt={alt} onError={() => setFailed(true)} />}</span>
}
