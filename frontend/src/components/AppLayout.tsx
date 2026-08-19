import { useEffect, useState } from "react"
import {
  ArrowLeft,
  CaretLineLeft,
  CaretLineRight,
  ClockCounterClockwise,
  Gear,
  GridFour,
  House,
  UploadSimple,
} from "@phosphor-icons/react"
import { Link, NavLink, Outlet, useLocation, useParams } from "react-router-dom"
import { useTheme } from "../theme/useTheme"

const primaryNavigation = [
  { to: "/", label: "Dashboard", icon: House, end: true },
  { to: "/upload", label: "Upload Catalog", icon: UploadSimple, end: false },
  { to: "/products", label: "Products", icon: GridFour, end: false },
  { to: "/runs", label: "Runs", icon: ClockCounterClockwise, end: false },
] as const

const titles: Record<string, string> = { "/": "Dashboard", "/upload": "Upload Catalog", "/products": "Products", "/runs": "Processing Runs", "/appearance": "Appearance" }
// Live/demo data-source signal only makes sense for surfaces that render
// data -- Appearance is a local settings page, neither "live" nor "demo".
const liveDataRoutes = new Set(["/", "/upload", "/products", "/runs"])
const COLLAPSE_STORAGE_KEY = "juval-sidebar-collapsed"

function pageTitle(pathname: string): string {
  if (pathname.includes("/records/")) return "Record Detail"
  if (pathname.startsWith("/runs/")) return "Run Detail"
  return titles[pathname] ?? "JUVAl"
}

function loadCollapsed(): boolean {
  try { return localStorage.getItem(COLLAPSE_STORAGE_KEY) === "1" } catch { return false }
}

export function AppLayout() {
  const { pathname } = useLocation()
  const { executionId } = useParams<{ executionId?: string }>()
  const { settings } = useTheme()
  const [collapsed, setCollapsed] = useState(loadCollapsed)

  useEffect(() => {
    try { localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? "1" : "0") } catch { /* local preference only, safe to skip if storage is unavailable */ }
  }, [collapsed])

  // Upload, Runs (list + detail + record detail), and Dashboard are real
  // backend data -- only Products' demo/live status is per-run, already
  // labelled inline; the shell only needs a coarse route check here.
  const isLiveRoute = pathname === "/upload" || pathname === "/" || pathname.startsWith("/runs")
  const isRecordDetail = pathname.includes("/records/")
  const isRunDetail = pathname.startsWith("/runs/") && !isRecordDetail
  const showEnvironmentBadge = liveDataRoutes.has(pathname) || isRunDetail || isRecordDetail
  const CollapseIcon = collapsed ? CaretLineRight : CaretLineLeft

  return (
    <div className={`shell ${collapsed ? "collapsed" : ""}`}>
      <aside className="sidebar">
        <NavLink to="/" className="brand" title="JUVAl"><span>{settings.logoDataUrl ? <img src={settings.logoDataUrl} alt="Workspace logo" /> : "J"}</span><span className="brand-name">JUVAl</span></NavLink>
        <nav aria-label="Main navigation">
          {primaryNavigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} title={label}>
              <span aria-hidden="true"><Icon size={18} weight="regular" /></span>
              <span className="nav-label">{label}</span>
            </NavLink>
          ))}
        </nav>
        <button type="button" className="sidebar-collapse-toggle" onClick={() => setCollapsed((value) => !value)} aria-expanded={!collapsed} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
          <CollapseIcon size={16} weight="regular" aria-hidden="true" />
          <span className="nav-label">{collapsed ? "Expand" : "Collapse"}</span>
        </button>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-context">
            {isRecordDetail && executionId
              ? <Link to={`/runs/${encodeURIComponent(executionId)}`} className="topbar-back"><ArrowLeft size={13} weight="bold" aria-hidden="true" />Run Detail</Link>
              : isRunDetail
                ? <Link to="/runs" className="topbar-back"><ArrowLeft size={13} weight="bold" aria-hidden="true" />Runs</Link>
                : <small>{pathname === "/appearance" ? "Settings" : "Workspace"}</small>}
            <h1>{pageTitle(pathname)}</h1>
          </div>
          <div className="topbar-actions">
            {showEnvironmentBadge && <span className={`environment ${isLiveRoute ? "environment-live" : ""}`}>{isLiveRoute ? "Live processing" : "Demo workspace"}</span>}
            {/* Dashboard already carries its own "Upload catalog" CTA in its page-intro -- avoid two competing primary actions on one screen. */}
            {pathname !== "/upload" && pathname !== "/" && <Link to="/upload" className="primary-button topbar-cta"><UploadSimple size={14} weight="regular" aria-hidden="true" />New run</Link>}
            <NavLink to="/appearance" className={({ isActive }) => `icon-button${isActive ? " active" : ""}`} aria-label="Appearance settings" title="Appearance settings"><Gear size={18} weight="regular" aria-hidden="true" /></NavLink>
          </div>
        </header>
        <main><Outlet /></main>
      </div>
    </div>
  )
}
