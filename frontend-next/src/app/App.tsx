import { useEffect, useState } from "react"
import { BatchPage } from "../pages/BatchPage"
import { CatalogPage } from "../pages/CatalogPage"
import { NotWiredPage } from "../pages/NotWiredPage"
import { RunDetailPage } from "../pages/RunDetailPage"
import { RunsPage } from "../pages/RunsPage"
import { UploadPage } from "../pages/UploadPage"

/**
 * Golden's application shell, productionized (ADR-030).
 *
 * Navigation, layout, light/dark and routing behaviour are Golden's — this is
 * the experience the user approved, and productionization is not a redesign.
 *
 * Golden's data layer is absent: no local run store, no browser CSV/XLSX
 * engine, no simulated enrichment, no client-side decision policy, no demo
 * bootstrap. A screen either speaks to the real API or says it is not
 * connected yet.
 */

const NAVIGATION: [path: string, label: string][] = [
  ["/", "Dashboard"],
  ["/import", "Import"],
  ["/catalog", "Catalog"],
  ["/compare", "Compare"],
  ["/favorites", "Favorites"],
  ["/runs", "Runs"],
  ["/appearance", "Appearance"],
  ["/about", "Methodology"],
]

export function App() {
  const [route, setRoute] = useState(() => location.pathname + location.search)
  const [dark, setDark] = useState(() => localStorage.getItem("juval.appearance.dark") !== "false")

  const go = (path: string) => { history.pushState({}, "", path); setRoute(path) }

  useEffect(() => {
    const onPop = () => setRoute(location.pathname + location.search)
    addEventListener("popstate", onPop)
    return () => removeEventListener("popstate", onPop)
  }, [])

  useEffect(() => { localStorage.setItem("juval.appearance.dark", String(dark)) }, [dark])

  // Internal navigation stays in this tab: intercept same-origin anchors so a
  // link routes instead of reloading the application. Anything explicitly
  // targeted elsewhere (a download, a genuinely external destination) is left
  // to the browser.
  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
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

  const [pathname, search] = [route.split("?")[0], new URLSearchParams(route.split("?")[1] ?? "")]
  const batchMatch = pathname.match(/^\/batch\/(.+)$/)
  const runMatch = pathname.match(/^\/runs\/(.+)$/)

  const page =
    pathname === "/catalog" ? <CatalogPage initialRunId={search.get("run") ?? ""} />
    : pathname === "/import" ? <UploadPage go={go} />
    : pathname === "/runs" ? <RunsPage go={go} />
    : runMatch ? <RunDetailPage executionId={decodeURIComponent(runMatch[1])} go={go} />
    : batchMatch ? <BatchPage batchId={decodeURIComponent(batchMatch[1])} go={go} />
    : pathname === "/" ? <NotWiredPage title="Dashboard" capability="Run analytics: decision distribution, profitability, risk and provenance for a persisted run." />
    : pathname === "/compare" ? <NotWiredPage title="Compare matched products" capability="Side-by-side comparison of records sharing an identifier across the source files of one batch." blocker="A comparable-identity ADR (ADR-011/ADR-012 refuse a global product identity) and a batch-scoped cross-run record query." />
    : pathname === "/favorites" ? <NotWiredPage title="Favorites" capability="Every starred record across runs. Starring already works in Catalog and is stored in this browser." blocker="A cross-run record lookup: production keeps no records in the browser to list them from." />
    : pathname === "/appearance" ? <NotWiredPage title="Appearance & branding" capability="Light/dark, accent and brand assets, stored in this browser." />
    : pathname === "/about" ? <NotWiredPage title="Methodology" capability="How JUVAl derives a decision: import, normalize, validate, calculate profitability, apply risk, decide." />
    : <NotWiredPage title="Page not found" capability="No JUVAl route matches this address. Nothing was processed and no run was affected." />

  return <div className={dark ? "app dark" : "app"}>
    <aside>
      <b>JUVAl</b>
      {NAVIGATION.map(([path, label]) => <button key={path} onClick={() => go(path)} aria-current={pathname === path ? "page" : undefined}>{label}</button>)}
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
