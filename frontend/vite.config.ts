import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { readFileSync } from 'fs'

let config = { backend: { port: 5000 }, frontend: { port: 5173, api_proxy: 'http://127.0.0.1:5000' } }
try {
  const raw = readFileSync(resolve(__dirname, '../config.json'), 'utf-8')
  config = JSON.parse(raw)
} catch {}

export default defineConfig({
  plugins: [vue()],
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
    target: 'es2020',
    cssMinify: 'esbuild',
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/element-plus')) return 'element-plus'
          if (id.includes('node_modules/@xterm')) return 'xterm'
          if (id.includes('node_modules/vue') || id.includes('node_modules/vue-router') || id.includes('node_modules/axios')) return 'vendor'
        },
      },
    },
  },
})
