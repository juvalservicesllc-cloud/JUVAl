import { rmSync } from "node:fs"

/** Removes the disposable database, run storage and fixtures, unless JUVAL_E2E_KEEP=1 asks to keep them for inspection. */
export default function teardown() {
  if (process.env.JUVAL_E2E_KEEP !== "1" && process.env.JUVAL_E2E_DIR) rmSync(process.env.JUVAL_E2E_DIR, { recursive: true, force: true })
}
