import { act, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, expect, it, vi } from "vitest"
import * as client from "../api/client"
import { App } from "./App"

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status })
const signedIn = { authenticated: true, subject: "synthetic-alice", roles: ["operator"], permissions: ["runs:read", "runs:create"], expires_at: "2026-11-11T07:00:00Z", csrf_token: "synthetic-csrf" }

/** Only the named routes are allowed; an unexpected request fails the test. */
function backend(session: () => Promise<Response> | Response, data = () => json(200, { items: [] })) {
  const calls: string[] = []
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = new URL(url).pathname
    calls.push(path)
    if (path === "/api/v1/auth/session") return session()
    if (path.startsWith("/api/v1/runs") || path.startsWith("/api/v1/batches") || path === "/api/v1/auth/logout") return data()
    throw new Error(`Unexpected API request: ${path}`)
  }))
  return calls
}

function at(path = "/about") {
  history.replaceState({}, "", path)
  return render(<App />)
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  history.replaceState({}, "", "/")
  localStorage.clear()
})

it("shows sign out only for an authenticated session", async () => {
  const calls = backend(() => json(200, signedIn))
  at()
  expect(await screen.findByRole("button", { name: "Sign out" })).toBeEnabled()
  expect(calls).toEqual(["/api/v1/auth/session"])
  expect(document.body).not.toHaveTextContent(signedIn.csrf_token)
  expect(document.body).not.toHaveTextContent(signedIn.subject)
})

it("keeps account controls hidden in the auth-disabled lab", async () => {
  backend(() => json(200, { authenticated: false }))
  at("/runs")
  await screen.findByText(/no persisted runs yet/i)
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument()
})

it("offers deliberate login with the current path, query and fragment after a 401", async () => {
  backend(() => json(200, { authenticated: false }), () => json(401, { detail: "missing bearer token" }))
  const path = "/runs?tab=history#recent"
  at(path)
  const link = await screen.findByRole("link", { name: "Sign in" })
  const url = new URL(link.getAttribute("href")!)
  expect(url.pathname).toBe("/api/v1/auth/login")
  expect(url.searchParams.get("return_to")).toBe(path)
  expect(location.pathname + location.search + location.hash).toBe(path)
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument()
})

it("hides sign out on a later 401 and preserves the route without navigating", async () => {
  let expired = false
  backend(() => json(200, signedIn), () => expired ? json(401, { detail: "missing bearer token" }) : json(200, { items: [] }))
  at()
  await screen.findByRole("button", { name: "Sign out" })
  expired = true
  await userEvent.setup().click(screen.getByRole("button", { name: "Runs" }))
  await screen.findByRole("link", { name: "Sign in" })
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument()
  expect(location.pathname).toBe("/runs")
})

it("does not restore stale authenticated UI when startup finishes after a data 401", async () => {
  let resolveSession!: (response: Response) => void
  backend(() => new Promise<Response>((resolve) => { resolveSession = resolve }), () => json(401, { detail: "missing bearer token" }))
  at("/runs")
  await screen.findByRole("link", { name: "Sign in" })
  await act(async () => { resolveSession(json(200, signedIn)) })
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument()
})

it.each(["identity provider temporarily unavailable", "session service unavailable"])("allows manual session retry after 503 %s without declaring logout", async (detail) => {
  let unavailable = true
  const calls = backend(() => unavailable ? json(503, { detail }) : json(200, signedIn))
  at()
  expect(await screen.findByRole("alert")).toHaveTextContent("The service is temporarily unavailable. Try again in a moment.")
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument()
  expect(calls).toHaveLength(1)
  unavailable = false
  await userEvent.setup().click(screen.getByRole("button", { name: "Retry session" }))
  await screen.findByRole("button", { name: "Sign out" })
  expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  expect(calls).toHaveLength(2)
})

it("keeps an authenticated account on data 503 and on an unreachable API", async () => {
  let offline = false
  backend(() => json(200, signedIn), () => {
    if (offline) throw new TypeError("fetch failed")
    return json(503, { detail: "identity provider temporarily unavailable" })
  })
  at("/runs")
  await screen.findByRole("button", { name: "Sign out" })
  expect(await screen.findByRole("alert")).toHaveTextContent(/service is temporarily unavailable/i)
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument()
  offline = true
  await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }))
  expect(await screen.findByRole("alert")).toHaveTextContent(/could not be reached/i)
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument()
})

it("reports failed logout without hiding the account or creating a login prompt", async () => {
  backend(() => json(200, signedIn), () => json(503, { detail: "session service unavailable" }))
  at()
  await userEvent.setup().click(await screen.findByRole("button", { name: "Sign out" }))
  expect(await screen.findByRole("alert")).toHaveTextContent(/service is temporarily unavailable/i)
  expect(screen.getByRole("button", { name: "Sign out" })).toBeEnabled()
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument()
})

it("wires the account action to logout and prevents duplicate clicks while it is pending", async () => {
  backend(() => json(200, signedIn))
  let finish!: () => void
  const logout = vi.spyOn(client, "logout").mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))
  at()
  await userEvent.setup().click(await screen.findByRole("button", { name: "Sign out" }))
  expect(screen.getByRole("button", { name: "Signing out…" })).toBeDisabled()
  expect(logout).toHaveBeenCalledTimes(1)
  await act(async () => { finish() })
  expect(screen.queryByRole("button", { name: /sign.*out/i })).not.toBeInTheDocument()
})

it.each(["/", "/catalog", "/runs", "/favorites", "/runs/synthetic", "/batch/synthetic", "/run/synthetic/product/row_2"])("explains unassigned organization without offering retry on %s", async (path) => {
  backend(() => json(200, signedIn), () => json(403, { detail: "no organization access for this identity" }))
  at(path)
  expect(await screen.findByRole("alert")).toHaveTextContent("Your account is not assigned to an organization. Contact your JUVAl administrator.")
  expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument()
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument()
})

it("never polls session when the shell sits idle for eight hours or navigates locally", async () => {
  const calls = backend(() => json(200, signedIn))
  at()
  await screen.findByRole("button", { name: "Sign out" })
  await userEvent.setup().click(screen.getByRole("button", { name: "Appearance" }))
  await waitFor(() => expect(location.pathname).toBe("/appearance"))
  vi.useFakeTimers()
  await act(async () => { await vi.advanceTimersByTimeAsync(8 * 60 * 60 * 1000) })
  expect(calls).toEqual(["/api/v1/auth/session"])
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument()
})
