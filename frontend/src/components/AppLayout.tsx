import { NavLink, Outlet, useLocation } from "react-router-dom"
import { useTheme } from "../theme/useTheme"

const navigation = [
  ["/", "Dashboard", "⌂"],
  ["/upload", "Upload Catalog", "↑"],
  ["/products", "Products", "▦"],
  ["/runs", "Runs", "↻"],
  ["/appearance", "Appearance", "◐"],
] as const

const titles: Record<string, string> = { "/": "Dashboard", "/upload": "Upload Catalog", "/products": "Products", "/runs": "Processing Runs", "/appearance": "Appearance" }

export function AppLayout() {
  const { pathname } = useLocation()
  const { settings } = useTheme()
  const isLiveRoute = pathname === "/upload"
  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand"><span>{settings.logoDataUrl ? <img src={settings.logoDataUrl} alt="Workspace logo" /> : "J"}</span> JUVAl</NavLink>
        <nav aria-label="Main navigation">{navigation.map(([to, label, icon]) => <NavLink key={to} to={to} end={to === "/"}><span>{icon}</span>{label}</NavLink>)}</nav>
        <div className="sidebar-footer"><span className="avatar">JD</span><div><strong>Juval Demo</strong><small>Operator</small></div></div>
      </aside>
      <div className="workspace"><header className="topbar"><div><small>JUVAl / Operations</small><h1>{titles[pathname] ?? "JUVAl"}</h1></div><span className={`environment ${isLiveRoute ? "environment-live" : ""}`}>{isLiveRoute ? "Live processing" : "Demo workspace"}</span></header><main><Outlet /></main></div>
    </div>
  )
}
