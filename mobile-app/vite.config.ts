import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const backendPort = process.env.PHOTOGRAPHER_BACKEND_PORT || '8000'
const backendHttpUrl = `http://127.0.0.1:${backendPort}`
const backendWsUrl = `ws://127.0.0.1:${backendPort}`

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': {
        target: backendHttpUrl,
        changeOrigin: true,
      },
      '/static': {
        target: backendHttpUrl,
        changeOrigin: true,
      },
      '/ws': {
        target: backendWsUrl,
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
