import { useEffect, useState } from "react"
import { CatalogPage } from "../pages/CatalogPage"
import { NotWiredPage } from "../pages/NotWiredPage"

/**
 * Golden's application shell, productionized (ADR-030).
 *
 * The navigation, layout, light/dark control and routing behaviour are
 * Golden's — this is the experience the user approved, and productionization is
 * not a redesign.
 *
 * Every piece of Golden's *data* layer is gone from this shell: there is no
 * local run store, no browser CSV/XLSX engine, no simulated enrichment, no
 * client-side decision policy and no demo-run bootstrap. A screen either speaks
 * to the real API or says plainly that it is not connected yet.
 */

const NAVIGATION: [path: string, label: string][] = [
  ["/", "Dashboard"],
  ["/import", "Import"],
  ["/process", "Pipeline"],
  ["/catalog", "Catalog"],
  ["/compare", "Compare"],
  ["/favorites", "Favorites"],
  ["/runs", "Runs"],
  ["/appearance", "Appearance"],
  ["/about", "Methodology"],
]

export function App() {
  const [route, setRoute] = useState(location.pathname)
  const [dark, setDark] = useState(() => localStorage.getItem("juval.appearance.dark") !== "false")

  const go = (path: string) => { history.pushState({}, "", path); setRoute(path) }

  useEffect(() => {
    const onPop = () => setRoute(location.pathname)
    addEventListener("popstate", onPop)
    return () => removeEventListener("popstate", onPop)
  }, [])

  useEffect(() => { localStorage.setItem("juval.appearance.dark", String(dark)) }, [dark])

  // Internal navigation stays in this tab: intercept same-origin anchors so a
  // row link routes instead of reloading the whole application.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      const anchor = (event.target as HTMLElement | null)?.closest?.("a")
      if (!anchor) return
      const href = anchor.getAttribute("href")
      if (!href || !href.startsWith("/") || anchor.target === "_blank") return
      event.preventDefault()
      go(href)
    }
    addEventListener("click", onClick)
    return () => removeEventListener("click", onClick)
  }, [])

  const page = route === "/catalog" ? <CatalogPage />
    : route === "/" ? <NotWiredPage title="Dashboard" capability="Run analytics: decision distribution, profitability, risk and provenance for a persisted run." />
    : route === "/import" ? <NotWiredPage title="Import supplier files" capability="Multi-file upload to the real validation and processing pipeline, one ExecutionRun per file, with per-file results." />
    : route === "/process" ? <NotWiredPage title="Pipeline" capability="Processing status for a submitted batch." blocker="The API reports a completed run, not granular stage progress — the demo's stage list was decorative and is not being carried over as fact." />
    : route === "/compare" ? <NotWiredPage title="Compare matched products" capability="Side-by-side comparison of records that share an identifier across the source files of one batch." blocker="A comparable-identity ADR (ADR-011/ADR-012 refuse a global product identity) and a batch-scoped cross-run record query." />
    : route === "/favorites" ? <NotWiredPage title="Favorites" capability="Every starred record across runs. Starring already works in Catalog and is stored in this browser." blocker="A cross-run record lookup: production stores no records in the browser to list them from." />
    : route === "/runs" ? <NotWiredPage title="Processing runs" capability="Persisted run history with status, counts and drill-down. The run selector in Catalog already reads this list from the API." />
    : route === "/appearance" ? <NotWiredPage title="Appearance & branding" capability="Light/dark, accent and brand assets, stored in this browser." />
    : route.startsWith("/run/") ? <NotWiredPage title="Product detail" capability="One record's identity, economics, risk, data quality and full field provenance." />
    : route === "/about" ? <NotWiredPage title="Methodology" capability="How JUVAl derives a decision: import, normalize, validate, calculate profitability, apply risk, decide." />
    : <NotWiredPage title="Page not found" capability="No JUVAl route matches this address. Nothing was processed and no run was affected." />

  return <div className={dark ? "app dark" : "app"}>
    <aside>
      <b>JUVAl</b>
      {NAVIGATION.map(([path, label]) => <button key={path} onClick={() => go(path)} aria-current={route === path ? "page" : undefined}>{label}</button>)}
    </aside>
    <main>
      <header>
        <span>LIVE — real backend, real persisted runs</span>
        <button onClick={() => setDark(!dark)} role="switch" aria-checked={dark}>{dark ? "Light" : "Dark"}</button>
      </header>
      {page}
    </main>
  </div>
}
