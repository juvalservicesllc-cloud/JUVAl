import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiError, apiErrorMessage, CSRF_HEADER, NetworkError, onAuthRequired, requestJson } from "./client"
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
  minRoi: "", minProfit: "", minMargin: "", confidence: "VERIFIED_ONLY", hazmat: "", bulky: "", provenanceField: "", provenanceStatus: "",
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
})
