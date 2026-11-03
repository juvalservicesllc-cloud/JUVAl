/* Public offline notice only. Never cache application HTML, API, auth,
   requests with credentials, records, exports or uploads. Version on change. */
const CACHE = "juval-next-offline-v1"
const OFFLINE = "/offline.html"
self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const response = await fetch(OFFLINE, { credentials: "omit", cache: "reload", redirect: "error" })
    if (!response.ok || !response.headers.get("content-type")?.includes("text/html")) throw new Error("Offline notice unavailable")
    const cache = await caches.open(CACHE)
    await cache.put(OFFLINE, response)
  })())
  // No skipWaiting: existing sessions keep their active worker until closed.
})
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) if (key.startsWith("juval-next-offline-") && key !== CACHE) await caches.delete(key)
  })())
})
self.addEventListener("fetch", (event) => {
  const request = event.request
  const url = new URL(request.url)
  const frontendRoute = /^\/(?:$|(?:import|catalog|runs|run|batch|appearance|about|favorites|compare|upload|products|batches)(?:\/|$))/.test(url.pathname)
  if (request.method !== "GET" || request.mode !== "navigate" || url.origin !== self.location.origin || !frontendRoute) return
  // Network response is never written to CacheStorage, including errors/401s.
  event.respondWith(fetch(request).catch(async () => (await caches.match(OFFLINE, { cacheName: CACHE })) || Response.error()))
})
