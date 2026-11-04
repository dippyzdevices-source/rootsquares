import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // pdf.js is only ever imported lazily (utils/pdfjs.ts), so Vite's dev server would discover it late,
  // re-optimise dependencies mid-session and leave the page pointing at a deleted chunk
  // ("Failed to fetch dynamically imported module … pdfjs-dist.js?v=…"). Pre-bundle it at startup.
  optimizeDeps: { include: ['pdfjs-dist'] },
  // rootsquares (W6-R27): supabaseClient.ts waits for the square's sign-in settings with a top-level await.
  build: { target: 'esnext' },
  server: {
    // The square is found by the host name (first-org.localhost:5274), so the API is reached through this server with the Host header kept.
    proxy: { '/api': { target: 'http://127.0.0.1:5002', changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    // Baseline auth-provider env for every test file, mirroring the backend's TestingConfig
    // pin — supabaseClient.ts throws at import time with no default, so any spec that
    // transitively imports it (most api-service mocks use vi.importActual) needs one.
    // Individual specs override via vi.stubEnv/vi.unstubAllEnvs to exercise other providers.
    env: {
      VITE_AUTH_PROVIDER: 'supabase',
      VITE_AUTH_URL: 'https://example.supabase.co',
      VITE_AUTH_PUBLIC_KEY: 'test-anon-key',
    },
  },

  // for local tunneling with loca.lt - but getting Bad Gateway errors
  // server: {
  //   host: true,
  //   allowedHosts: ['bca-oslo.loca.lt'],
  // },
})
