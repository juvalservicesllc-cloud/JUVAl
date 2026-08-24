# JUVAl West Marine Demo

Independent browser-only React/Vite demo. It accepts West Marine scraper CSV columns directly, uses Papa Parse for CSV syntax, preserves raw source rows, creates deterministic demo enrichment, calculates transparent demo profitability and decision output, and never calls JUVAl, Amazon, Supabase, or another backend.

`VERIFIED_SOURCE` only identifies CSV-origin fields. Amazon, weight, Hazmat, Bulky, price and fees are `DEMO_FIXTURE`, `INFERRED`, or `NOT_FOUND`.

The included representative file is `public/westmarine-2026-08-16.csv`. Its supplier fields are `VERIFIED_SOURCE`; Amazon, weight, Hazmat, Bulky, selling price and fees remain `DEMO_FIXTURE`, `INFERRED`, or `NOT_FOUND`. Profitability and decisions are demo calculations, not production JUVAl output.

Run: `npm install`, then `npm run dev`. Validate with `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`.
