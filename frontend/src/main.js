import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './style.css'
import { setLogoutCallback } from './utils/api.js'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: undefined })
// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 注册 401 退出回调：清除 auth 并跳转登录
setLogoutCallback(() => {
  import('./stores/auth.js').then(({ useAuthStore }) => {
    useAuthStore().clearAuth()
    router.push('/login')
  })
})

app.mount('#app')
