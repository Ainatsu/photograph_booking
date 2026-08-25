import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'

const backendPort = process.env.PHOTOGRAPHER_BACKEND_PORT || '8000'
const backendHttpUrl = `http://127.0.0.1:${backendPort}`

export default defineConfig({
  plugins: [vue(), vueJsx()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': { target: backendHttpUrl, changeOrigin: true },
      '/static': { target: backendHttpUrl, changeOrigin: true },
    },
  },
})
