import { useEffect, useState, type CSSProperties } from "react"
import { accentColors, DEFAULT_APPEARANCE, loadAppearance, resetAppearance, saveAppearance, type Appearance } from "../appearance"
import { AppearancePage } from "../pages/AppearancePage"
import { loginUrl, onAuthRequired } from "../api/client"
import { BatchPage } from "../pages/BatchPage"
import { CatalogPage } from "../pages/CatalogPage"
import { DashboardPage } from "../pages/DashboardPage"
import { FavoritesPage } from "../pages/FavoritesPage"
import { NotWiredPage } from "../pages/NotWiredPage"
import { MethodologyPage } from "../pages/MethodologyPage"
import { ProductDetailPage } from "../pages/ProductDetailPage"
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
  const [appearance, setAppearance] = useState(loadAppearance)
  const { dark } = appearance
  const changeAppearance = (patch: Partial<Appearance>) => {
    saveAppearance(patch)
    setAppearance((current) => ({ ...current, ...patch }))
  }

  const go = (path: string) => { history.pushState({}, "", path); setRoute(path) }

  useEffect(() => {
    const onPop = () => setRoute(location.pathname + location.search)
    addEventListener("popstate", onPop)
    return () => removeEventListener("popstate", onPop)
  }, [])

  // The API answered 401: offer sign-in, never redirect on our own -- an
  // automatic redirect on every 401 is how login loops start.
  const [signInNeeded, setSignInNeeded] = useState(false)
  useEffect(() => onAuthRequired(() => setSignInNeeded(true)), [])

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
  const productMatch = pathname.match(/^\/run\/([^/]+)\/product\/(.+)$/)

  const page =
    pathname === "/catalog" ? <CatalogPage initialRunId={search.get("run") ?? ""} initialPendingDemand={search.get("review") === "pending-demand"} />
    : pathname === "/import" ? <UploadPage go={go} />
    : pathname === "/runs" ? <RunsPage go={go} />
    : productMatch ? <ProductDetailPage executionId={decodeURIComponent(productMatch[1])} recordRef={decodeURIComponent(productMatch[2])} go={go} />
    : runMatch ? <RunDetailPage executionId={decodeURIComponent(runMatch[1])} go={go} />
    : batchMatch ? <BatchPage batchId={decodeURIComponent(batchMatch[1])} go={go} />
    : pathname === "/" ? <DashboardPage initialRunId={search.get("run") ?? ""} go={go} />
    : pathname === "/compare" ? <NotWiredPage title="Compare matched products" capability="Side-by-side comparison of records sharing an identifier across the source files of one batch." blocker="A comparable-identity ADR (ADR-011/ADR-012 refuse a global product identity) and a batch-scoped cross-run record query." />
    : pathname === "/favorites" ? <FavoritesPage initialRunId={search.get("run") ?? ""} go={go} />
    : pathname === "/appearance" ? <AppearancePage appearance={appearance} onChange={changeAppearance} onReset={() => { resetAppearance(); setAppearance({ ...DEFAULT_APPEARANCE }) }} />
    : pathname === "/about" ? <MethodologyPage />
    : <NotWiredPage title="Page not found" capability="No JUVAl route matches this address. Nothing was processed and no run was affected." />

  const colors = accentColors(appearance.accent || (dark ? "#9c92ff" : "#6d5dfc"), dark)
  const appearanceStyle = {
    colorScheme: dark ? "dark" : "light",
    ...(appearance.accent ? { "--accent": appearance.accent } : {}),
    "--on-accent": colors.onAccent,
    "--accent-text": colors.textAccent,
    ...(appearance.background ? { backgroundImage: `url("${appearance.background}")` } : {}),
  } as CSSProperties
  return <div className={`app${dark ? " dark" : ""}${appearance.background ? " has-custom-background" : ""}`} style={appearanceStyle}>
    <aside>
      <nav aria-label="Main navigation">
        {appearance.logo && <img className="appearance-logo" src={appearance.logo} alt="Custom JUVAl logo" />}
        <b>JUVAl</b>
        {NAVIGATION.map(([path, label]) => <button key={path} onClick={() => go(path)} aria-current={pathname === path ? "page" : undefined}>{label}</button>)}
      </nav>
    </aside>
    <main>
      <header>
        <span>LIVE — real backend, real persisted runs</span>
        <button onClick={() => changeAppearance({ dark: !dark })} role="switch" aria-checked={dark}>{dark ? "Light" : "Dark"}</button>
      </header>
      {signInNeeded && <p role="alert" className="notice">
        You are not signed in or your session has expired. <a href={loginUrl()}>Sign in</a> to continue; nothing on this page was changed.
      </p>}
      {page}
    </main>
  </div>
}
