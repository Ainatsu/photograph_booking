import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './assets/main.css'

import App from './App.vue'
import router from './router'

// 忽略 ResizeObserver 无害警告
const resizeObserverError = 'ResizeObserver loop completed with undelivered notifications.'
window.addEventListener('error', (e) => {
  if (e.message === resizeObserverError) {
    e.stopImmediatePropagation()
  }
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
