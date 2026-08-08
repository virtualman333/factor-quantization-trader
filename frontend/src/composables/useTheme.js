/**
 * useTheme — 深色/浅色模式切换
 *
 * 通过在 <html> 上切换 `dark` class 控制 Element Plus 暗色主题与全局样式。
 * - 状态持久化到 localStorage，刷新后保持
 * - 与 K 线图表主题联动（Klines.vue 可监听 theme.isDark 同步切换）
 * - 支持系统偏好自动跟随（首次访问时）
 *
 * 注意：需在 main.js 引入 element-plus/theme-chalk/dark/css-vars.css
 */
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'app_theme'

// 单例状态（跨组件共享）
const theme = ref(loadInitialTheme())

function loadInitialTheme() {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  // 首次访问跟随系统偏好
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark'
  }
  return 'light'
}

function applyTheme(val) {
  const html = document.documentElement
  if (val === 'dark') {
    html.classList.add('dark')
  } else {
    html.classList.remove('dark')
  }
  html.setAttribute('data-theme', val)
}

// 初始化时立即应用
if (typeof document !== 'undefined') {
  applyTheme(theme.value)
}

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  function toggle() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function setTheme(val) {
    theme.value = val
    localStorage.setItem(STORAGE_KEY, val)
    applyTheme(val)
  }

  /** 监听主题变化（供 K 线等图表组件同步切换样式） */
  function watchTheme(handler) {
    return watch(theme, (val, old) => handler(val, old), { immediate: false })
  }

  return { theme, isDark, toggle, setTheme, watchTheme }
}
