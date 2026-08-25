import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

const backendPort = process.env.PHOTOGRAPHER_BACKEND_PORT || '8000'
const backendHttpUrl = `http://127.0.0.1:${backendPort}`
const backendWsUrl = `ws://127.0.0.1:${backendPort}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    vueDevTools(),
  ],
  css: {
    transformer: 'lightningcss',
    lightningcss: {
      errorRecovery: true,
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    allowedHosts: ['.frp-put.com', '.frp-xxx.com'],
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
})
