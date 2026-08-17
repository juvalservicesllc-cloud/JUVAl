import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // Minimal PWA config (manifest + service worker only) -- no offline
    // processing, no background sync, no push notifications yet (out of
    // scope for the Fase 4B MVP, see docs/PROJECT_PLAN.md §Fase 4).
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'JUVAl',
        short_name: 'JUVAl',
        description: 'Amazon Sourcing Decision Engine',
        theme_color: '#0a7d24',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [
          {
            src: 'icon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
            purpose: 'any',
          },
        ],
      },
    }),
  ],
})
