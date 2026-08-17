import { NavLink, Outlet, useLocation } from "react-router-dom"

const navigation = [
  ["/", "Dashboard", "⌂"],
  ["/upload", "Upload Catalog", "↑"],
  ["/products", "Products", "▦"],
  ["/runs", "Runs", "↻"],
] as const

const titles: Record<string, string> = { "/": "Dashboard", "/upload": "Upload Catalog", "/products": "Products", "/runs": "Processing Runs" }

export function AppLayout() {
  const { pathname } = useLocation()
  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand"><span>J</span> JUVAl</NavLink>
        <nav aria-label="Main navigation">
          {navigation.map(([to, label, icon]) => <NavLink key={to} to={to} end={to === "/"}><span>{icon}</span>{label}</NavLink>)}
        </nav>
        <div className="sidebar-footer"><span className="avatar">JD</span><div><strong>Juval Demo</strong><small>Operator</small></div></div>
      </aside>
      <div className="workspace">
        <header className="topbar"><div><small>JUVAl / Operations</small><h1>{titles[pathname] ?? "JUVAl"}</h1></div><span className="environment">Demo workspace</span></header>
        <main><Outlet /></main>
      </div>
    </div>
  )
}
