import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// The admin application (ADR 083, 084): its own package, its own port, its own dependency cache (node_modules/.vite of this folder), its own output folder.
// It shares the design system with the customer app through @rootsquares/ui and nothing else (tests/separation.test.mjs keeps the two import graphs apart).
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // public/ holds robots.txt and the headers file of the admin host only
  server: { host: '127.0.0.1', port: 5275, strictPort: true, headers: { 'X-Frame-Options': 'DENY', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Robots-Tag': 'noindex, nofollow' } },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false }, // no source maps of the staff application are published
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
})
