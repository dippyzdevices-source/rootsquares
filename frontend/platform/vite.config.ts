import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // 127.0.0.1 so that <slug>.localhost (which browsers send to the loopback address) reaches the dev server; not open to the network.
  server: { host: '127.0.0.1' },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
})
