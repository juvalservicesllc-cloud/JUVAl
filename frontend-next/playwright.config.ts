import { execFileSync } from "node:child_process"
import { mkdirSync, mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { defineConfig } from "@playwright/test"

/**
 * Real-browser E2E for frontend-next: a disposable API (SQLite in a fresh temp
 * directory, auth disabled, loopback only) and the Vite dev server, both
 * started here on isolated ports and stopped by Playwright afterwards. Nothing
 * touches Supabase, a migration or a running service.
 *
 * The browser is Playwright's own Chromium, or any local Chromium given as
 * JUVAL_CHROME_BIN (no browser download needed). See e2e/README.md.
 */

const repo = resolve(import.meta.dirname, "..")
const python = process.env.JUVAL_PYTHON ?? join(repo, ".venv/bin/python")
const apiPort = Number(process.env.JUVAL_E2E_API_PORT ?? 18771)
const webPort = Number(process.env.JUVAL_E2E_WEB_PORT ?? 18772)

// The config is evaluated again in each worker; the directory is created once
// and handed to the workers through the environment they inherit.
if (!process.env.JUVAL_E2E_DIR) {
  process.env.JUVAL_E2E_DIR = mkdtempSync(join(tmpdir(), "juval-e2e-"))
  mkdirSync(join(process.env.JUVAL_E2E_DIR, "runs"))
  execFileSync(python, [join(import.meta.dirname, "e2e/fixtures.py"), "build", join(process.env.JUVAL_E2E_DIR, "files")])
}
const dir = process.env.JUVAL_E2E_DIR
process.env.JUVAL_E2E_API = `http://127.0.0.1:${apiPort}`

const { JUVAL_SUPABASE_DB_URL: _ignored, ...inherited } = process.env

export default defineConfig({
  testDir: "./e2e",
  globalTeardown: "./e2e/teardown.ts",
  outputDir: process.env.JUVAL_E2E_OUTPUT ?? "test-results",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"], ["json", { outputFile: join(process.env.JUVAL_E2E_OUTPUT ?? "test-results", "report.json") }]],
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: { executablePath: process.env.JUVAL_CHROME_BIN || undefined },
  },
  webServer: [
    {
      command: `${python} -m uvicorn juval.interfaces.api.main:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: repo,
      url: `http://127.0.0.1:${apiPort}/api/v1/runs`,
      reuseExistingServer: false,
      env: {
        ...inherited as Record<string, string>,
        JUVAL_AUTH_MODE: "disabled",
        JUVAL_EXECUTION_STORE: "sqlite",
        JUVAL_EXECUTION_DB_PATH: join(dir, "juval.db"),
        JUVAL_RUN_STORAGE_DIR: join(dir, "runs"),
        JUVAL_CORS_ORIGINS: `http://127.0.0.1:${webPort}`,
      },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: false,
      env: { VITE_API_BASE_URL: `http://127.0.0.1:${apiPort}` },
    },
  ],
})
