# frontend-next — Golden-first production candidate

The user-approved Golden application experience (`demo/`) running on the real
JUVAl backend. See `docs/adr/ADR-030-golden-first-frontend-productionization.md`.

- `demo/` stays the immutable Golden reference and is never modified.
- `frontend/` stays the legacy production implementation and the API/provenance
  behavioural reference.
- This app contains **no fixture engine**: no simulated enrichment, no browser
  CSV/XLSX processing, no client-side decision policy, no generated ASIN.
  A screen either speaks to the real API or says it is not connected yet.

Run: `npm run dev -- --port 5183` with `VITE_API_BASE_URL` pointing at the API.

## Authentication (ADR-034 BFF)

All requests go through `src/api/client.ts::apiFetch`; no page talks to `fetch`
directly. It sends `credentials: "include"` (the HttpOnly `juval_session`
cookie), and on POST adds `X-JUVAL-CSRF` with the token read once from
`GET /api/v1/auth/session` and kept in memory only. A stale token is re-read and
the POST retried **once**. A 401 shows a "Sign in" link to
`/api/v1/auth/login` (no automatic redirect, so no login loop); 403 says
"permission" or "security check"; an unreachable API is a `NetworkError`.
With `JUVAL_AUTH_MODE=disabled` the session is `authenticated: false`, no token
is sent and behaviour is unchanged. The API must list the app origin in
`JUVAL_CORS_ORIGINS` (credentialed CORS, never `*`). Not yet built: a session
indicator and logout.

## Visual review from the Windows workstation

Both servers bind to loopback on `juval-server` (192.168.0.26); the browser
reaches them through an SSH tunnel, so nothing is exposed on the LAN and no
firewall rule changes. Auth mode is `disabled` (local development: every
endpoint is unauthenticated, which is why it stays on loopback). Data is a
throwaway SQLite file.

On the Linux server, two terminals, from the repository root:

```bash
# 1 — API on 127.0.0.1:8010
mkdir -p /tmp/juval-visual/runs
JUVAL_CORS_ORIGINS=http://localhost:5183,http://127.0.0.1:5183 \
JUVAL_EXECUTION_DB_PATH=/tmp/juval-visual/juval.db \
JUVAL_RUN_STORAGE_DIR=/tmp/juval-visual/runs \
.venv/bin/python -m uvicorn juval.interfaces.api.main:app --host 127.0.0.1 --port 8010

# 2 — frontend-next on 127.0.0.1:5183
cd frontend-next
VITE_API_BASE_URL=http://localhost:8010 npm run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

On Windows (PowerShell), keep this open, then browse to http://localhost:5183:

```powershell
ssh -N -L 5183:127.0.0.1:5183 -L 8010:127.0.0.1:8010 <linux-user>@192.168.0.26
```

`VITE_API_BASE_URL` is `localhost:8010` because the *browser* calls the API,
and on Windows that address is the tunnel. Upload
`tests/fixtures/sample_sourcing_TEST_DATA.xlsx` (from a Windows clone, or copied
from the server with `scp`) to see Preview, Runs decision
counts and the Catalog brand filter. Stop both servers with Ctrl+C.

Serving on the LAN directly (`--host 0.0.0.0`) would publish an
unauthenticated API to the network; that needs the operator's decision and,
possibly, a firewall rule, and is not part of this guide.
