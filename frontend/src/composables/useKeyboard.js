/**
 * useKeyboard — 全局快捷键支持
 *
 * 在组件内注册快捷键，自动在组件卸载时解绑。
 * 支持组合键（Ctrl / Shift / Alt / Meta）。
 *
 * 用法：
 *   const { registerShortcut, unregisterShortcut } = useKeyboard()
 *   registerShortcut({ key: 's', ctrl: true, handler: () => save(), description: '保存' })
 *   registerShortcut({ key: 'r', ctrl: true, handler: () => refresh(), description: '刷新' })
 *   registerShortcut({ key: '/', handler: () => focusSearch(), description: '聚焦搜索' })
 *
 * 内置快捷键（在 MainLayout 注册）：
 *   Ctrl+K  聚焦品种搜索
 *   Ctrl+B  折叠/展开侧边栏
 *   Ctrl+D  切换深色/浅色模式
 *   ?       打开快捷键帮助
 *   Esc     关闭弹窗（Element Plus 默认支持）
 */
import { onMounted, onBeforeUnmount } from 'vue'

const shortcuts = []

export function useKeyboard() {
  const registered = []

  /**
   * 注册快捷键
   * @param {Object} option
   * @param {string} option.key 单个按键（不区分大小写），如 's' / 'Enter' / '/'
   * @param {boolean} option.ctrl 是否需要 Ctrl/Cmd
   * @param {boolean} option.shift 是否需要 Shift
   * @param {boolean} option.alt 是否需要 Alt
   * @param {Function} option.handler 触发函数
   * @param {string} option.description 描述（用于帮助面板）
   * @param {boolean} option.allowInInput 是否在输入框内也触发（默认 false）
   */
  function registerShortcut(option) {
    shortcuts.push(option)
    registered.push(option)
    return () => unregisterShortcut(option)
  }

  function unregisterShortcut(option) {
    const idx = shortcuts.indexOf(option)
    if (idx !== -1) shortcuts.splice(idx, 1)
  }

  onMounted(() => {
    // 多次挂载只绑定一次全局监听
    if (shortcuts.__bound) return
    shortcuts.__bound = true
    document.addEventListener('keydown', handleKeydown)
  })

  onBeforeUnmount(() => {
    // 移除当前组件注册的快捷键
    for (const opt of registered) {
      const idx = shortcuts.indexOf(opt)
      if (idx !== -1) shortcuts.splice(idx, 1)
    }
    registered.length = 0
  })

  return { registerShortcut, unregisterShortcut, shortcuts }
}

function handleKeydown(e) {
  const target = e.target
  const isInput =
    target &&
    (target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable)

  // 查找匹配的快捷键（后注册的优先）
  for (let i = shortcuts.length - 1; i >= 0; i--) {
    const opt = shortcuts[i]
    if (!opt || typeof opt.handler !== 'function') continue
    if (isInput && opt.allowInInput === false) continue
    if (!matchKey(e, opt)) continue
    e.preventDefault()
    try {
      opt.handler(e)
    } catch (err) {
      console.error('[useKeyboard] 快捷键处理异常', err)
    }
    return
  }
}

function matchKey(e, opt) {
  const key = (opt.key || '').toLowerCase()
  const eKey = (e.key || '').toLowerCase()
  if (key !== eKey) return false
  const ctrl = !!opt.ctrl
  const shift = !!opt.shift
  const alt = !!opt.alt
  // Ctrl 或 Meta（Mac Cmd）都算
  const eCtrl = e.ctrlKey || e.metaKey
  if (ctrl !== eCtrl) return false
  if (shift !== e.shiftKey) return false
  if (alt !== e.altKey) return false
  return true
}

/** 获取当前所有已注册快捷键（用于帮助面板） */
export function listShortcuts() {
  return [...shortcuts].reverse()
}
