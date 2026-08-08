/**
 * 表单持久化 Hook：浏览器关闭/刷新后恢复未提交内容
 * 用法:
 *   const form = reactive({ ... })
 *   useFormPersistence('strategy-create', form)
 */
import { watch, onBeforeUnmount } from 'vue'

const PREFIX = 'quant_form_draft_'

export function useFormPersistence(key, form, options = {}) {
  const storageKey = PREFIX + key
  const exclude = options.exclude || []
  const saveDelay = options.saveDelay || 300

  // 恢复
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw) {
      const saved = JSON.parse(raw)
      for (const [k, v] of Object.entries(saved)) {
        if (k in form && !exclude.includes(k)) {
          form[k] = v
        }
      }
    }
  } catch { /* 忽略恢复失败 */ }

  // 防抖自动保存
  let timer = null
  const unwatch = watch(
    () => JSON.stringify({ ...form }),
    (val) => {
      clearTimeout(timer)
      timer = setTimeout(() => {
        try {
          localStorage.setItem(storageKey, val)
        } catch { /* 存储失败忽略 */ }
      }, saveDelay)
    }
  )

  // 页面隐藏/关闭时立即保存
  const flush = () => {
    clearTimeout(timer)
    try {
      localStorage.setItem(storageKey, JSON.stringify({ ...form }))
    } catch { /* 忽略 */ }
  }
  window.addEventListener('beforeunload', flush)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush()
  })

  /** 清除草稿（提交成功后调用） */
  function clear() {
    clearTimeout(timer)
    try { localStorage.removeItem(storageKey) } catch {}
  }

  onBeforeUnmount(() => {
    clearTimeout(timer)
    window.removeEventListener('beforeunload', flush)
    document.removeEventListener('visibilitychange', flush)
    unwatch()
  })

  return { clear }
}
