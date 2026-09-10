import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { IonicVue } from '@ionic/vue'

import '@ionic/vue/css/core.css'
import '@ionic/vue/css/normalize.css'
import '@ionic/vue/css/structure.css'
import '@ionic/vue/css/typography.css'
import '@ionic/vue/css/padding.css'
import '@ionic/vue/css/display.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import './theme/tokens.css'
import './theme/global.css'
import { initializeTheme } from '@/utils/theme'

// 在 Vue 挂载前写入主题属性，避免首屏先以默认主题闪烁一次。
initializeTheme()

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(IonicVue, { mode: 'ios' })
app.use(router)

const auth = useAuthStore(pinia)

// 401 一律由 api/client.ts 的响应拦截器派发此事件，页面不要各写一套处理。
window.addEventListener('auth:expired', () => {
  auth.clearSession()
  if (router.currentRoute.value.meta.requiresAuth) {
    void router.replace({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
})

// 挂载前恢复会话，避免首屏先渲染出未登录状态再跳一下。
router.isReady().then(async () => {
  await auth.initialize()
  app.mount('#app')
})
