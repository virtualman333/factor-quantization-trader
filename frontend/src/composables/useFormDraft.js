/**
 * useFormDraft — 表单草稿持久化
 *
 * 将表单数据自动持久化到 localStorage，浏览器关闭或刷新后可恢复未提交内容。
 * 适用于：策略编辑、订单创建等长表单场景。
 *
 * 用法：
 *   const { draft, saveDraft, loadDraft, clearDraft, hasDraft } = useFormDraft('strategy_form', {
 *     name: '', symbols: [], params: {}
 *   })
 *   // 读取草稿（组件挂载时）
 *   loadDraft()  // 若存在草稿会合并到 draft
 *   // 自动保存（监听变化）
 *   watch(draft, () => saveDraft(), { deep: true })
 *   // 提交成功后清除
 *   clearDraft()
 */
import { ref, watch, onMounted } from 'vue'

const STORAGE_PREFIX = 'form_draft:'

export function useFormDraft(key, defaultForm = {}) {
  const storageKey = STORAGE_PREFIX + key
  const draft = ref({ ...defaultForm })
  const hasDraft = ref(false)
  const savedAt = ref(null)

  /** 从 localStorage 读取草稿 */
  function loadDraft() {
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object' && parsed.data) {
        draft.value = mergeDeep({ ...defaultForm }, parsed.data)
        savedAt.value = parsed.savedAt || null
        hasDraft.value = true
        return draft.value
      }
    } catch (e) {
      console.warn('[useFormDraft] 读取草稿失败', e)
    }
    return null
  }

  /** 保存当前表单到 localStorage */
  function saveDraft(data) {
    const payload = data || draft.value
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ data: payload, savedAt: Date.now() }),
      )
      hasDraft.value = true
      savedAt.value = Date.now()
    } catch (e) {
      console.warn('[useFormDraft] 保存草稿失败', e)
    }
  }

  /** 清除草稿（提交成功后调用） */
  function clearDraft() {
    localStorage.removeItem(storageKey)
    hasDraft.value = false
    savedAt.value = null
  }

  /** 重置为默认值并清除草稿 */
  function resetDraft() {
    draft.value = { ...defaultForm }
    clearDraft()
  }

  /**
   * 自动持久化：监听 draft 变化自动保存（防抖）
   * @param {number} debounceMs 防抖间隔，默认 500ms
   */
  function autoSave(debounceMs = 500) {
    let timer = null
    const stop = watch(
      draft,
      () => {
        if (timer) clearTimeout(timer)
        timer = setTimeout(() => saveDraft(), debounceMs)
      },
      { deep: true },
    )
    return stop
  }

  onMounted(() => {
    loadDraft()
  })

  return { draft, hasDraft, savedAt, loadDraft, saveDraft, clearDraft, resetDraft, autoSave }
}

/** 深合并（保留默认值的结构，覆盖已有字段） */
function mergeDeep(target, source) {
  if (!source) return target
  const out = { ...target }
  for (const key of Object.keys(source)) {
    if (
      source[key] &&
      typeof source[key] === 'object' &&
      !Array.isArray(source[key]) &&
      target[key] &&
      typeof target[key] === 'object'
    ) {
      out[key] = mergeDeep(target[key], source[key])
    } else {
      out[key] = source[key]
    }
  }
  return out
}
