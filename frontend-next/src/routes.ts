/** Legacy aliases only where the same run-scoped resource has an exact mapping.
 * Preserve encoded segments and the query byte-for-byte; decode only in App. */
export function canonicalRoute(route: string): string {
  const at = route.search(/[?#]/)
  const path = at < 0 ? route : route.slice(0, at)
  const suffix = at < 0 ? "" : route.slice(at)
  if (path === "/upload") return "/import" + suffix
  if (path === "/products") return "/catalog" + suffix
  const batch = path.match(/^\/batches\/([^/]+)$/)
  if (batch) return `/batch/${batch[1]}${suffix}`
  const product = path.match(/^\/runs\/([^/]+)\/records\/([^/]+)$/)
  if (product) return `/run/${product[1]}/product/${product[2]}${suffix}`
  return route
}

export function currentRoute(): string {
  const original = location.pathname + location.search
  const canonical = canonicalRoute(original)
  if (canonical !== original) history.replaceState(history.state, "", canonical + location.hash)
  return canonical
}
