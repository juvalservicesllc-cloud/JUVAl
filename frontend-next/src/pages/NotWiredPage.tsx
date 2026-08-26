/** A Golden route that is not yet running on the real backend (ADR-030).
 *
 * The route and its place in the navigation are kept deliberately: the
 * capability is not being removed, it is being migrated. What is *not* kept is
 * the demo data behind it — showing simulated records inside a production
 * candidate is exactly the failure mode this pivot exists to avoid.
 */
export function NotWiredPage({ title, capability, blocker }: { title: string; capability: string; blocker?: string }) {
  return <section className="panel">
    <h1>{title}</h1>
    <p className="not-wired">Not yet connected to the real backend.</p>
    <p>{capability}</p>
    {blocker && <p><b>Blocked by:</b> {blocker}</p>}
    <p>This screen deliberately shows nothing rather than demonstration data. Catalog is the first surface running on real persisted runs; the rest follow after review.</p>
  </section>
}
