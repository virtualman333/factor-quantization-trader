/**
 * 主题 Store：深色/浅色模式切换（持久化到 localStorage）
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const KEY = 'quant_theme'
  const isDark = ref(localStorage.getItem(KEY) === 'dark')

  const themeLabel = computed(() => (isDark.value ? '深色模式' : '浅色模式'))

  function apply() {
    const el = document.documentElement
    if (isDark.value) {
      el.classList.add('dark')
    } else {
      el.classList.remove('dark')
    }
  }

  function toggle() {
    isDark.value = !isDark.value
    localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
    apply()
  }

  function init() {
    // 首次进入跟随系统偏好
    if (localStorage.getItem(KEY) === null) {
      isDark.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
    }
    apply()
  }

  return { isDark, themeLabel, toggle, init }
})
