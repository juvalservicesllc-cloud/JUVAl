import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    globals: true,
    // e2e/ is Playwright-only (`npm run test:e2e`) -- excluded here so
    // Vitest doesn't try to run Playwright specs under jsdom.
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
