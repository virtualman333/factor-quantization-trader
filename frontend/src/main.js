import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { setLogoutCallback } from './utils/api.js'
import TermTip from '@/components/TermTip.vue'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: undefined })
// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
// 全局注册术语提示组件（任意页面可直接 <term-tip term-key="leverage" />）
app.component('TermTip', TermTip)

// 注册 401 退出回调：清除 auth 并跳转登录
setLogoutCallback(() => {
  import('./stores/auth.js').then(({ useAuthStore }) => {
    useAuthStore().clearAuth()
    router.push('/login')
  })
})

app.mount('#app')

// ===== 注册 PWA Service Worker（仅生产环境） =====
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.warn('[PWA] Service Worker 注册失败', err)
    })
  })
}
