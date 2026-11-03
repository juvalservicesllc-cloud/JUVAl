// @vitest-environment node
import { readFileSync } from "node:fs"
import { runInNewContext } from "node:vm"
import { expect, it, vi } from "vitest"

it("caches only the anonymous offline notice and never intercepts API/auth/uploads", async () => {
  const handlers = {}
  const put = vi.fn(), open = vi.fn(async () => ({ put }))
  const fetch = vi.fn(async () => new Response("Offline", { headers: { "content-type": "text/html" } }))
  runInNewContext(readFileSync(new URL("../public/sw.js", import.meta.url), "utf8"), {
    self: { location: { origin: "https://app.example" }, addEventListener: (name, handler) => { handlers[name] = handler } },
    caches: { open, match: vi.fn(), keys: vi.fn(async () => []) }, fetch, URL, Response,
  })
  let installed
  handlers.install({ waitUntil: (value) => { installed = value } })
  await installed
  expect(fetch).toHaveBeenCalledWith("/offline.html", { credentials: "omit", cache: "reload", redirect: "error" })
  expect(put).toHaveBeenCalledTimes(1)
  for (const [path, mode, method] of [["/api/v1/runs", "navigate", "GET"], ["/auth/login", "navigate", "GET"], ["/catalog", "cors", "GET"], ["/import", "navigate", "POST"], ["https://api.example/runs", "navigate", "GET"]]) {
    const respondWith = vi.fn()
    handlers.fetch({ request: { url: new URL(path, "https://app.example").href, mode, method }, respondWith })
    expect(respondWith).not.toHaveBeenCalled()
  }
  const respondWith = vi.fn()
  handlers.fetch({ request: { url: "https://app.example/catalog", mode: "navigate", method: "GET" }, respondWith })
  await respondWith.mock.calls[0][0]
  expect(put).toHaveBeenCalledTimes(1) // online navigation was not cached
})

it("returns only the public notice offline and removes only its own obsolete caches", async () => {
  const handlers = {}
  const notice = new Response("Public offline notice")
  const remove = vi.fn()
  const match = vi.fn(async () => notice)
  runInNewContext(readFileSync(new URL("../public/sw.js", import.meta.url), "utf8"), {
    self: { location: { origin: "https://app.example" }, addEventListener: (name, handler) => { handlers[name] = handler } },
    caches: { match, keys: vi.fn(async () => ["workbox-legacy", "juval-next-offline-v0", "juval-next-offline-v1"]), delete: remove },
    fetch: vi.fn(async () => { throw new Error("offline") }), URL, Response,
  })
  let response
  handlers.fetch({ request: { url: "https://app.example/runs", mode: "navigate", method: "GET" }, respondWith: (value) => { response = value } })
  expect(await (await response).text()).toBe("Public offline notice")
  expect(match).toHaveBeenCalledWith("/offline.html", { cacheName: "juval-next-offline-v1" })
  let activated
  handlers.activate({ waitUntil: (value) => { activated = value } })
  await activated
  expect(remove.mock.calls).toEqual([["juval-next-offline-v0"]])
})
