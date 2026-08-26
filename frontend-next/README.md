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
