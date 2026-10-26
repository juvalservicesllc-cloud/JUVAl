import { configDefaults, defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: false, setupFiles: ["./src/setupTests.ts"],
    // e2e/ is Playwright's (npm run e2e), not vitest's.
    exclude: [...configDefaults.exclude, "e2e/**"] },
})
