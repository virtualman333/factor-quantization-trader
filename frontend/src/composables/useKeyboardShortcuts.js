/**
 * 全局快捷键支持 Hook
 * 用法:
 *   useKeyboardShortcuts({
 *     'ctrl+n': () => router.push('/orders/create'),
 *     'f': () => toggleSearch(),
 *   })
 */
import { onMounted, onBeforeUnmount } from 'vue'

export function useKeyboardShortcuts(bindings) {
  function handler(e) {
    const parts = []
    if (e.ctrlKey || e.metaKey) parts.push('ctrl')
    if (e.shiftKey) parts.push('shift')
    if (e.altKey) parts.push('alt')
    const key = e.key.toLowerCase()
    if (key !== 'control' && key !== 'shift' && key !== 'alt' && key !== 'meta') {
      parts.push(key === ' ' ? 'space' : key)
    }
    const combo = parts.join('+')
    const fn = bindings[combo]
    if (fn) {
      // 不在输入框内才触发（除非显式允许）
      const tag = document.activeElement?.tagName
      const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable
      if (isTyping && !bindings._allowTyping?.[combo]) return
      e.preventDefault()
      fn(e)
    }
  }

  onMounted(() => window.addEventListener('keydown', handler))
  onBeforeUnmount(() => window.removeEventListener('keydown', handler))
}
