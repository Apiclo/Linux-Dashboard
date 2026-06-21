import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'
import { readFileSync } from 'fs'

let config = { backend: { port: 5000 }, frontend: { port: 5173, api_proxy: 'http://127.0.0.1:5000' } }
try {
  const raw = readFileSync(resolve(__dirname, '../config.json'), 'utf-8')
  config = JSON.parse(raw)
} catch {}

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: config.frontend?.port || 5173,
    host: config.frontend?.host || '0.0.0.0',
    proxy: {
      '/api': {
        target: config.frontend?.api_proxy || `http://127.0.0.1:${config.backend?.port || 5000}`,
        changeOrigin: true,
      },
      '/api/stream': {
        target: config.frontend?.api_proxy || `http://127.0.0.1:${config.backend?.port || 5000}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
