import { defineConfig } from "@playwright/test"

// Minimal E2E smoke test config (Fase 4B brief §12): one happy-path
// flow against the real backend, no infrastructure beyond what's
// needed to run a single browser test. Both servers (FastAPI +
// `vite dev`) must already be running -- see e2e/README.md.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:5173",
  },
  reporter: "list",
})
