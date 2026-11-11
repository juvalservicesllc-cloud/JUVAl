/** Real JUVAl API client for the Golden-first production candidate (ADR-030).
 *
 * `frontend-next/` keeps Golden's application and UI; what it does not keep is
 * Golden's data. Every value that reaches a screen from here comes from the
 * FastAPI backend with its provenance attached — nothing is generated, hashed
 * or simulated in the browser.
 *
 * Authentication is the BFF's (ADR-034); this client holds no credential:
 *
 * - The session is an `HttpOnly` cookie the browser attaches itself. Every
 *   request is sent with `credentials: "include"` because the app and the API
 *   are separate origins (ADR-038 app/api subdomains; a different port in dev).
 * - State-changing requests echo the CSRF token in `X-JUVAL-CSRF` (double
 *   submit). The `juval_csrf` cookie belongs to the API host, so the app cannot
 *   read it; it gets the token from `GET /api/v1/auth/session` and keeps it in
 *   memory only — never localStorage, never logged.
 * - With `JUVAL_AUTH_MODE=disabled` there is no session (`/auth/session`
 *   answers `authenticated: false`) and so no token: requests go out exactly as
 *   before, and the API, which has no session to protect, does not ask for one.
 * - A 401 is never answered with an automatic redirect (that is how login
 *   loops start). It is reported to the shell, which offers a sign-in link the
 *   operator follows deliberately.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export const CSRF_HEADER = "X-JUVAL-CSRF"
const CSRF_REJECTED = "csrf token missing or invalid"
const NO_ORGANIZATION = "no organization access for this identity"

export class ApiError extends Error {
  constructor(readonly status: number, readonly body: unknown) {
    super(`API request failed with status ${status}`)
  }
}

/** The API could not be reached at all: no status, nothing was answered. */
export class NetworkError extends Error {
  constructor() {
    super("The JUVAl API could not be reached. Check that it is running and try again.")
  }
}

function detailOf(error: ApiError): unknown {
  return error.body && typeof error.body === "object" && "detail" in error.body ? (error.body as { detail: unknown }).detail : undefined
}

const shortLine = (value: unknown): value is string => typeof value === "string" && value.length <= 300 && !value.includes("\n")

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = detailOf(error)
    if (error.status === 401) return "You are not signed in or your session has expired. Sign in to continue."
    if (error.status === 503) return "The service is temporarily unavailable. Try again in a moment."
    if (error.status >= 500) return "The API request failed. Please try again."
    if (error.status === 403) {
      if (detail === NO_ORGANIZATION) return "Your account is not assigned to an organization. Contact your JUVAl administrator."
      return detail === CSRF_REJECTED
        ? "The security check for this action failed. Reload the page and try again."
        : "Your account does not have permission for this action."
    }
    if (shortLine(detail)) return detail
    // FastAPI validation errors: a list of { loc, msg }. Show the first message.
    if (error.status === 422 && Array.isArray(detail) && detail.length && shortLine(detail[0]?.msg)) {
      return `The request was rejected: ${detail[0].msg}${detail.length > 1 ? ` (and ${detail.length - 1} more)` : ""}.`
    }
    return "The API request failed. Please try again."
  }
  return error instanceof Error ? error.message : String(error)
}

/** Retrying cannot assign an organization; the administrator must do that. */
export function canRetryApiError(error: unknown): boolean {
  return !(error instanceof ApiError && error.status === 403 && detailOf(error) === NO_ORGANIZATION)
}

export function apiUrl(path: string): string {
  return new URL(path, `${API_BASE_URL.replace(/\/$/, "")}/`).toString()
}

/** Where the operator goes to sign in: a top-level navigation to the BFF. */
export function loginUrl(returnTo?: string): string {
  const url = new URL(apiUrl("api/v1/auth/login"))
  // Accept app paths only, following the BFF's return_to restrictions.
  if (returnTo?.startsWith("/") && !returnTo.startsWith("//") && !returnTo.includes("\\") &&
    !Array.from(returnTo).some((c) => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127)) {
    url.search = new URLSearchParams({ return_to: returnTo }).toString()
  }
  return url.toString()
}

// --- Session ---------------------------------------------------------

type AuthListener = () => void
const authListeners = new Set<AuthListener>()

/** The shell subscribes to learn that the API answered 401. */
export function onAuthRequired(listener: AuthListener): () => void {
  authListeners.add(listener)
  return () => { authListeners.delete(listener) }
}

export type BrowserSession =
  | { authenticated: false }
  | { authenticated: true; subject: string; roles: string[]; permissions: string[]; expires_at: string }
type SessionResponse = BrowserSession & { csrf_token?: string }

// One in-memory lookup shared by the shell and mutations. No timer: polling
// would count as activity and defeat the server's idle-session timeout.
let session: Promise<SessionResponse> | null = null

function currentSession(): Promise<SessionResponse> {
  if (!session) {
    const pending = requestJson("api/v1/auth/session").then((body) => body as SessionResponse)
    session = pending
    // A transport/service failure is not a signed-out session and must not
    // poison the cache. Do not let an old failure evict a newer lookup.
    void pending.catch(() => { if (session === pending) session = null })
  }
  return session
}

/** Session metadata for the shell; the CSRF value stays private to this client. */
export async function getSession(): Promise<BrowserSession> {
  const body = await currentSession()
  return body.authenticated === true
    ? { authenticated: true, subject: body.subject, roles: body.roles, permissions: body.permissions, expires_at: body.expires_at }
    : { authenticated: false }
}

async function currentCsrfToken(): Promise<string | null> {
  try {
    let body = await currentSession()
    if (body.authenticated === true && !body.csrf_token) {
      resetSession()
      body = await currentSession()
    }
    return body.authenticated === true && typeof body.csrf_token === "string" ? body.csrf_token : null
  } catch {
    // Preserve lab behaviour: the data route remains authoritative. Its 503
    // or 401 is handled normally, never guessed from a failed session lookup.
    return null
  }
}

/** Forget the cached token (tests, and whenever the session may have changed). */
export function resetSession(): void {
  session = null
}

/** Revoke the BFF session before navigating to the IdP's SSO logout. */
export async function logout(): Promise<void> {
  const body = await requestJson("api/v1/auth/logout", { method: "POST" }) as { end_session_url?: string }
  resetSession()
  window.location.assign(body.end_session_url || "/")
}

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"])

/** The one place a request leaves the app. Every API module goes through it. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase()
  const protectedCall = !SAFE_METHODS.has(method)

  const send = async () => {
    const headers = new Headers(init.headers)
    if (protectedCall) {
      const token = await currentCsrfToken()
      if (token) headers.set(CSRF_HEADER, token)
    }
    try {
      return await fetch(apiUrl(path), { ...init, method, headers, credentials: "include" })
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error
      throw new NetworkError()
    }
  }

  let response = await send()
  // A token can go stale (the session was refreshed or replaced in another
  // tab). Re-read it once and retry once; a second rejection is reported.
  if (protectedCall && response.status === 403 && await rejectedForCsrf(response)) {
    resetSession()
    response = await send()
  }
  if (response.status === 401) {
    resetSession()
    for (const listener of authListeners) listener()
  }
  return response
}

async function rejectedForCsrf(response: Response): Promise<boolean> {
  try {
    const body = await response.clone().json() as { detail?: unknown }
    return body?.detail === CSRF_REJECTED
  } catch {
    return false
  }
}

/** JSON request through `apiFetch`; a non-2xx answer becomes an `ApiError`. */
export async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await apiFetch(path, init)
  let body: unknown
  try { body = await response.json() } catch { body = null }
  if (!response.ok) throw new ApiError(response.status, body)
  return body
}
