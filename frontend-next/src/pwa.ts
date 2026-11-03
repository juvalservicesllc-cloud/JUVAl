/** Register only from the production entry point; no forced reload or takeover. */
export async function registerPwa() {
  if (!("serviceWorker" in navigator)) return
  try { await navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }) }
  catch { /* The online app remains available if SW registration is blocked. */ }
}
