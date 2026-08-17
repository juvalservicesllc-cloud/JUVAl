import { StatusBadge } from "../components/StatusBadge"
import { products } from "../data/demo"

export function ProductsPage() {
  return <><div className="page-intro"><div><p className="eyebrow">CATALOG</p><h2>Products</h2><p>Review normalized product data and its verification status.</p></div></div><div className="demo-banner"><strong>DEMO MODE</strong> Product rows are typed fixtures, not production records.</div><section className="panel table-panel"><table><thead><tr><th>SKU</th><th>Product</th><th>Brand</th><th>Cost</th><th>ASIN</th><th>Hazmat</th><th>Bulky</th><th>Decision</th><th>Provenance</th></tr></thead><tbody>{products.map(product => <tr key={product.sku}><td className="mono">{product.sku}</td><td><strong>{product.product}</strong></td><td>{product.brand}</td><td>{product.cost}</td><td className="mono">{product.asin ?? "—"}</td><td>{product.hazmat ? "Yes" : "No"}</td><td>{product.bulky ? "Yes" : "No"}</td><td><StatusBadge value={product.decision} /></td><td><StatusBadge value={product.asinStatus} /></td></tr>)}</tbody></table></section></>
}
