import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError, apiErrorMessage, canRetryApiError, CSRF_HEADER, getSession, loginUrl, logout, NetworkError, onAuthRequired, requestJson, resetSession } from "./client"
import { createBatch } from "./batches"
import { filteredExportUrl, getRunBrands, getRunRecords, getRuns } from "./catalog"
import { previewImport } from "./preview"
import { getRun, listRuns } from "./runs"
import type { CatalogQuery } from "./types"

const TOKEN = "csrf-token-of-this-session"
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })

type Call = { url: string; init: RequestInit }
/** A fake BFF: `session` is what GET /api/v1/auth/session answers; `answer`
 *  decides every other response. Every call is recorded. */
function backend({ session, answer = () => json(200, {}) }: { session: () => Response; answer?: (call: Call, n: number) => Response }) {
  const calls: Call[] = []
  let n = 0
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit = {}) => {
    const call = { url: String(url), init }
    calls.push(call)
    return call.url.endsWith("/api/v1/auth/session") ? session() : answer(call, n++)
  }))
  const api = () => calls.filter((c) => !c.url.endsWith("/api/v1/auth/session"))
  const sessionLookups = () => calls.length - api().length
  return { calls, api, sessionLookups }
}
const signedIn = () => json(200, { authenticated: true, subject: "u-1", roles: ["operator"], permissions: [], expires_at: "2026-10-26T20:00:00Z", csrf_token: TOKEN })
// What JUVAL_AUTH_MODE=disabled really answers (measured against a local API).
const authDisabled = () => json(200, { authenticated: false })
const signedOut = () => json(200, { authenticated: false })
const csrfHeader = (call: Call) => new Headers(call.init.headers).get(CSRF_HEADER)
const file = () => new File(["ASIN,COG\n"], "s.csv", { type: "text/csv" })

const query: CatalogQuery = {
  limit: 20, offset: 0, search: "", brand: "", decision: "ALL", sort: "profit", direction: "desc",
  minRoi: "", minProfit: "", minMargin: "", confidence: "VERIFIED_ONLY", hazmat: "", bulky: "", provenanceField: "", provenanceStatus: "", pendingDemand: false,
}

describe("shared API client: BFF cookie session and CSRF (ADR-034)", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

  it("sends every read with the session cookie and without a CSRF header or session lookup", async () => {
    const fake = backend({ session: signedIn, answer: () => json(200, { items: [], brands: { items: [], distinct: 0, not_recorded: 0 }, records: [], pagination: {} }) })
    await listRuns()
    await getRun("r1")
    await getRuns()
    await getRunRecords("r1", query)
    await getRunBrands("r1")
    expect(fake.api()).toHaveLength(5)
    for (const call of fake.api()) {
      expect(call.init.credentials).toBe("include")
      expect(call.init.method).toBe("GET")
      expect(csrfHeader(call)).toBeNull()
      expect(new Headers(call.init.headers).has("Authorization")).toBe(false)
    }
    expect(fake.sessionLookups()).toBe(0)
  })

  it("echoes the session's CSRF token on preview and batch submission", async () => {
    const fake = backend({ session: signedIn, answer: () => json(200, {}) })
    await previewImport(file())
    await createBatch([file()], { target_profit: "5", target_roi: "0.3", minimum_estimated_monthly_sales: 0, maximum_risk_severity: "LOW", allow_restricted: false, allow_approval_required: false, allow_unknown_risk: false }, { referral_fee: "3", referral_fee_rate: "0.15", fulfillment_fee: "2", other_selling_fees: "0" }, true)
    expect(fake.api().map((c) => [new URL(c.url).pathname, c.init.method, c.init.credentials, csrfHeader(c)])).toEqual([
      ["/api/v1/runs/preview", "POST", "include", TOKEN],
      ["/api/v1/batches", "POST", "include", TOKEN],
    ])
    // The token is read once per page and reused, not looked up per request.
    expect(fake.sessionLookups()).toBe(1)
    expect(fake.calls[0].init.credentials).toBe("include")
  })

  it("sends no CSRF header when authentication is disabled (dev mode unchanged)", async () => {
    const fake = backend({ session: authDisabled })
    await previewImport(file())
    expect(csrfHeader(fake.api()[0])).toBeNull()
    expect(fake.api()[0].init.credentials).toBe("include")
  })

  it("still sends the request when the session lookup itself fails", async () => {
    const fake = backend({ session: () => json(500, { detail: "internal server error" }) })
    await previewImport(file())
    expect(fake.api()).toHaveLength(1)
    expect(csrfHeader(fake.api()[0])).toBeNull()   // the server, not a guess, decides
  })

  it("reports a 401 to the shell once, without retrying or redirecting", async () => {
    const fake = backend({ session: signedOut, answer: () => json(401, { detail: "missing bearer token" }) })
    const listener = vi.fn()
    const before = location.href
    const unsubscribe = onAuthRequired(listener)
    const error = await previewImport(file()).catch((e: unknown) => e)
    unsubscribe()

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(401)
    expect(apiErrorMessage(error)).toMatch(/not signed in or your session has expired/i)
    expect(listener).toHaveBeenCalledTimes(1)
    expect(fake.api()).toHaveLength(1)
    expect(csrfHeader(fake.api()[0])).toBeNull()   // signed out: there is no token to send
    expect(location.href).toBe(before)             // no automatic redirect
  })

  it("treats an expired session as signed out and looks the session up again afterwards", async () => {
    let expired = false
    const fake = backend({ session: () => expired ? signedOut() : signedIn(), answer: () => expired ? json(401, { detail: "missing bearer token" }) : json(200, {}) })
    await previewImport(file())
    expired = true
    await expect(previewImport(file())).rejects.toMatchObject({ status: 401 })
    await previewImport(file()).catch(() => undefined)
    // The 401 dropped the cached token: the next protected call re-reads the session.
    expect(fake.sessionLookups()).toBe(2)
    expect(csrfHeader(fake.api()[2])).toBeNull()
  })

  it("re-reads a stale CSRF token once and retries once -- never more", async () => {
    let tokens = 0
    const fake = backend({
      session: () => json(200, { authenticated: true, csrf_token: `token-${++tokens}` }),
      answer: () => json(403, { detail: "csrf token missing or invalid" }),
    })
    const error = await previewImport(file()).catch((e: unknown) => e)
    expect(fake.api().map(csrfHeader)).toEqual(["token-1", "token-2"])
    expect(fake.sessionLookups()).toBe(2)
    expect(apiErrorMessage(error)).toMatch(/security check for this action failed/i)
  })

  it("succeeds on the retry when the refreshed token is accepted", async () => {
    let tokens = 0
    backend({
      session: () => json(200, { authenticated: true, csrf_token: `token-${++tokens}` }),
      answer: (call) => csrfHeader(call) === "token-2" ? json(200, { columns: [] }) : json(403, { detail: "csrf token missing or invalid" }),
    })
    await expect(previewImport(file())).resolves.toEqual({ columns: [] })
  })

  it("does not retry a permission denial and says so plainly", async () => {
    const fake = backend({ session: signedIn, answer: () => json(403, { detail: "insufficient permissions" }) })
    const error = await previewImport(file()).catch((e: unknown) => e)
    expect(fake.api()).toHaveLength(1)
    expect((error as ApiError).status).toBe(403)
    expect(apiErrorMessage(error)).toBe("Your account does not have permission for this action.")
  })

  it("distinguishes an unreachable API from an HTTP error, and lets aborts through", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("fetch failed"))))
    const error = await requestJson("api/v1/runs").catch((e: unknown) => e)
    expect(error).toBeInstanceOf(NetworkError)
    expect(apiErrorMessage(error)).toMatch(/could not be reached/i)

    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new DOMException("aborted", "AbortError"))))
    await expect(requestJson("api/v1/runs")).rejects.toMatchObject({ name: "AbortError" })
  })

  it("summarizes FastAPI validation errors instead of a generic failure", async () => {
    backend({ session: authDisabled, answer: () => json(422, { detail: [{ loc: ["body", "file"], msg: "Field required" }, { loc: ["body", "x"], msg: "bad" }] }) })
    const error = await previewImport(file()).catch((e: unknown) => e)
    expect(apiErrorMessage(error)).toBe("The request was rejected: Field required (and 1 more).")
  })

  it("keeps the CSRF token out of storage, logs and error messages", async () => {
    const logs = (["log", "info", "warn", "error", "debug"] as const).map((m) => vi.spyOn(console, m).mockImplementation(() => {}))
    backend({ session: signedIn, answer: () => json(403, { detail: "insufficient permissions" }) })
    const error = await previewImport(file()).catch((e: unknown) => e)

    const stored = [localStorage, sessionStorage].flatMap((s) => Object.keys(s).map((k) => s.getItem(k) ?? ""))
    expect(stored.join()).not.toContain(TOKEN)
    for (const spy of logs) expect(JSON.stringify(spy.mock.calls)).not.toContain(TOKEN)
    expect(String(error)).not.toContain(TOKEN)
    expect(apiErrorMessage(error)).not.toContain(TOKEN)
  })

  it("leaves export as a top-level navigation: a GET the cookie rides on, with no token in the URL", () => {
    const url = new URL(filteredExportUrl("r1", { ...query, brand: "Acme" }))
    expect(url.pathname).toBe("/api/v1/runs/r1/records/export")
    expect(url.search).not.toMatch(/csrf|token|session/i)
  })

  it.each(["/", "/runs/abc?tab=x#record", "/catalog?search=lamp%20shade&run=a%2Fb", "/import?name=café #preview"])("encodes an app return path exactly: %s", (path) => {
    const url = new URL(loginUrl(path))
    expect(url.pathname).toBe("/api/v1/auth/login")
    expect(url.searchParams.get("return_to")).toBe(path)
    expect(url.hash).toBe("")
  })

  it.each([undefined, "", "https://evil.example/runs", "http://localhost:5173/runs", "//evil.example", "runs/a", "/\\evil.example", "/\t/evil.example", "/runs\n", "/runs\u007f"])("discards an unsafe return destination: %s", (path) => {
    expect(new URL(loginUrl(path)).search).toBe("")
  })

  it("shares one session lookup between the shell and concurrent mutations without exposing the CSRF value", async () => {
    const fake = backend({ session: signedIn })
    const [session] = await Promise.all([getSession(), previewImport(file()), previewImport(file())])
    expect(session).toEqual({ authenticated: true, subject: "u-1", roles: ["operator"], permissions: [], expires_at: "2026-10-26T20:00:00Z" })
    expect(session).not.toHaveProperty("csrf_token")
    expect(fake.sessionLookups()).toBe(1)
    expect(fake.api().map(csrfHeader)).toEqual([TOKEN, TOKEN])
  })

  it("re-reads session if an authenticated response is missing the CSRF projection", async () => {
    let lookups = 0
    const fake = backend({ session: () => ++lookups === 1 ? json(200, { authenticated: true }) : signedIn() })
    await getSession()
    await previewImport(file())
    expect(fake.sessionLookups()).toBe(2)
    expect(csrfHeader(fake.api()[0])).toBe(TOKEN)
  })

  it.each(["https://id.juval.test/oauth2/logout?client_id=synthetic", undefined])("logs out with CSRF, forgets the session, then navigates to %s", async (endSessionUrl) => {
    const assign = vi.fn()
    vi.stubGlobal("window", { location: { assign } })
    const fake = backend({ session: signedIn, answer: () => json(200, { logged_out: true, end_session_url: endSessionUrl }) })
    await getSession()
    await logout()
    expect(fake.api()).toHaveLength(1)
    expect(new URL(fake.api()[0].url).pathname).toBe("/api/v1/auth/logout")
    expect(fake.api()[0].init.method).toBe("POST")
    expect(fake.api()[0].init.credentials).toBe("include")
    expect(csrfHeader(fake.api()[0])).toBe(TOKEN)
    expect(assign).toHaveBeenCalledExactlyOnceWith(endSessionUrl ?? "/")
    await getSession()
    expect(fake.sessionLookups()).toBe(2) // logout invalidated the shared cache
  })

  it("can log out again after the server has already ended the session", async () => {
    const assign = vi.fn()
    vi.stubGlobal("window", { location: { assign } })
    const fake = backend({ session: signedOut, answer: () => json(200, { logged_out: true }) })
    await logout()
    expect(csrfHeader(fake.api()[0])).toBeNull()
    expect(assign).toHaveBeenCalledExactlyOnceWith("/")
  })

  it("uses the same bounded CSRF retry for logout", async () => {
    const assign = vi.fn()
    vi.stubGlobal("window", { location: { assign } })
    let tokens = 0
    const fake = backend({
      session: () => json(200, { authenticated: true, csrf_token: `token-${++tokens}` }),
      answer: (_, n) => n === 0 ? json(403, { detail: "csrf token missing or invalid" }) : json(200, { logged_out: true }),
    })
    await logout()
    expect(fake.api().map(csrfHeader)).toEqual(["token-1", "token-2"])
    expect(assign).toHaveBeenCalledExactlyOnceWith("/")
  })

  it.each([403, 503])("does not navigate or forget a valid session after failed logout (%s)", async (status) => {
    const assign = vi.fn()
    vi.stubGlobal("window", { location: { assign } })
    const fake = backend({ session: signedIn, answer: () => json(status, { detail: "session service unavailable" }) })
    await expect(logout()).rejects.toMatchObject({ status })
    expect(assign).not.toHaveBeenCalled()
    await expect(getSession()).resolves.toMatchObject({ authenticated: true })
    expect(fake.sessionLookups()).toBe(1)
  })

  it("explains an unassigned organization and does not retry the request", async () => {
    const fake = backend({ session: signedIn, answer: () => json(403, { detail: "no organization access for this identity" }) })
    const error = await previewImport(file()).catch((e: unknown) => e)
    expect(fake.api()).toHaveLength(1)
    expect(apiErrorMessage(error)).toBe("Your account is not assigned to an organization. Contact your JUVAl administrator.")
    expect(canRetryApiError(error)).toBe(false)
    expect(canRetryApiError(new ApiError(503, {}))).toBe(true)
  })

  it.each(["session service unavailable", "identity provider temporarily unavailable", "organization membership is temporarily unavailable", "authentication is not initialised", "anything"])("keeps a 503 (%s) distinct from session expiry", async (detail) => {
    const fake = backend({ session: signedIn, answer: () => json(503, { detail }) })
    const listener = vi.fn()
    const unsubscribe = onAuthRequired(listener)
    try {
      const error = await previewImport(file()).catch((e: unknown) => e)
      expect(apiErrorMessage(error)).toBe("The service is temporarily unavailable. Try again in a moment.")
      expect(listener).not.toHaveBeenCalled()
      expect(fake.api()).toHaveLength(1)
      await expect(getSession()).resolves.toMatchObject({ authenticated: true })
      expect(fake.sessionLookups()).toBe(1)
    } finally { unsubscribe() }
  })

  it("surfaces a session-service error and permits a manual retry without caching signed-out state", async () => {
    let unavailable = true
    const fake = backend({ session: () => unavailable ? json(503, { detail: "identity provider temporarily unavailable" }) : signedIn() })
    const listener = vi.fn()
    const unsubscribe = onAuthRequired(listener)
    try {
      await expect(getSession()).rejects.toMatchObject({ status: 503 })
      expect(listener).not.toHaveBeenCalled()
      unavailable = false
      await expect(getSession()).resolves.toMatchObject({ authenticated: true })
      expect(fake.sessionLookups()).toBe(2)
    } finally { unsubscribe() }
  })

  it.each([500, 502])("uses a generic message for server errors (%s) without exposing deployment details", (status) => {
    expect(apiErrorMessage(new ApiError(status, { detail: "stored financial data failed validation" }))).toBe("The API request failed. Please try again.")
  })

  it("reports session network failure as a network error, not as signed out", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("fetch failed"))))
    await expect(getSession()).rejects.toBeInstanceOf(NetworkError)
  })

  it("does not let an old failed lookup evict the current session", async () => {
    let rejectOld!: (error: Error) => void
    vi.stubGlobal("fetch", vi.fn().mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject }))
      .mockImplementationOnce(async () => signedIn()))
    const old = getSession().catch(() => undefined)
    resetSession()
    await getSession()
    rejectOld(new TypeError("old lookup failed"))
    await old
    await expect(getSession()).resolves.toMatchObject({ authenticated: true })
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it("never polls the session or simulates activity during eight hours", async () => {
    vi.useFakeTimers()
    try {
      const fake = backend({ session: signedIn })
      await getSession()
      await vi.advanceTimersByTimeAsync(8 * 60 * 60 * 1000)
      expect(fake.sessionLookups()).toBe(1)
      expect(fake.api()).toHaveLength(0)
    } finally { vi.useRealTimers() }
  })
})
