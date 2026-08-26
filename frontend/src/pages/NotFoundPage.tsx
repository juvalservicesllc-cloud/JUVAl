import { Link, useLocation } from "react-router-dom"

/**
 * Unknown-route state, recovered from the Golden Product Experience
 * (ADR-029, `demo/src/pages/NotFoundPage.tsx`).
 *
 * Rendered inside `AppLayout`, so the sidebar and topbar stay usable and the
 * operator is never stranded on a blank shell. Recovery is a `Link`, not a
 * reload: the router already has the app mounted, and a hard navigation would
 * throw away the loaded bundle for no reason.
 *
 * This is deliberately not a "record not found" state -- that one lives in
 * Product Detail and means the run really was queried. This one means the URL
 * itself matches no route, so it must not imply anything about the data.
 */
export function NotFoundPage() {
  const { pathname } = useLocation()

  return (
    <>
      <div className="page-intro">
        <div>
          <p className="eyebrow">PAGE NOT FOUND</p>
          <h2>That page does not exist</h2>
          <p>No JUVAl route matches this address. Nothing was processed and no run was affected.</p>
        </div>
      </div>

      <section className="panel not-found-panel">
        <p className="text-muted">Requested address</p>
        <p className="mono not-found-path">{pathname}</p>
        <div className="asset-actions">
          <Link to="/" className="primary-button">Back to Dashboard</Link>
          <Link to="/runs" className="secondary-button">Processing Runs</Link>
          <Link to="/products" className="secondary-button">Catalog</Link>
        </div>
      </section>
    </>
  )
}
