import { ImageSquare } from "@phosphor-icons/react"

/**
 * Fixed-size product media slot.
 *
 * JUVAl has no canonical product-image field yet: no approved source, rights,
 * provenance or caching policy exists (see PRODUCT_BEHAVIORAL_PARITY #30,
 * TARGET_PRODUCT_CAPABILITIES "Image pipeline"). So this renders a deliberate
 * unavailable state rather than a supplier URL of unknown origin, a scraped
 * marketplace asset, or a stock photo standing in for a real product.
 *
 * The slot exists now so that adding `RecordOut.image` later is a data change,
 * not a table redesign: the row height and column widths already account for it.
 */
export function ProductThumbnail({ label }: { label: string }) {
  return (
    <span className="product-thumbnail" role="img" aria-label={`No product image available for ${label}`} title="No canonical product image is attached to this snapshot">
      <ImageSquare size={14} weight="thin" aria-hidden="true" />
    </span>
  )
}
