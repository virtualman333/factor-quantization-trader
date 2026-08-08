/**
 * 多 Tab 标签页 Store
 *
 * 职责：
 * - 维护已打开的页面标签列表
 * - 缓存视图名列表（供 keep-alive include 使用）
 * - 提供添加/关闭/关闭其它/关闭全部等操作
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'app_tabs'

function loadTabs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export const useTabsStore = defineStore('tabs', () => {
  const tabs = ref(loadTabs())

  // 固定标签（不可关闭）
  const affixTabs = [
    { path: '/dashboard', title: '仪表盘', name: 'Dashboard', affix: true },
  ]

  // 展示用的完整列表：固定 + 已打开
  const tabList = computed(() => {
    const open = tabs.value.map((t) => ({ ...t, affix: false }))
    return [...affixTabs, ...open]
  })

  // 缓存视图名（keep-alive include）：仅缓存已打开且非实时页面的组件
  const cachedViews = computed(() =>
    tabs.value.filter((t) => !t.noCache).map((t) => t.name)
  )

  // 当前激活标签路径
  const activePath = computed(() => {
    const t = tabList.value.find((x) => x.active)
    return t ? t.path : ''
  })

  // 待刷新标签路径（MainLayout 监听后执行重建）
  const refreshQueue = ref([])

  function persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tabs.value))
  }

  /**
   * 路由变化时同步标签
   * @param {Object} route vue-router route 对象
   */
  function addTab(route) {
    const { path, fullPath, meta } = route
    if (!path || path === '/login' || path === '/404') return
    const title = meta?.title || '未命名'
    const name = route.name || String(path)
    const noCache = !!meta?.noCache
    const existing = tabs.value.find((t) => t.path === path)
    if (existing) {
      existing.fullPath = fullPath
      existing.active = true
      existing.title = title
      // 切换回时若当前页不可缓存，允许其再次加载
      return
    }
    // 去掉其它标签的高亮
    tabs.value.forEach((t) => { t.active = false })
    tabs.value.push({ path, fullPath, title, name, noCache, active: true })
    persist()
  }

  /** 关闭指定标签，返回需要跳转的路径（null 表示无需跳转） */
  function removeTab(path) {
    const idx = tabs.value.findIndex((t) => t.path === path)
    if (idx === -1) return null
    const wasActive = tabs.value[idx].active
    tabs.value.splice(idx, 1)
    persist()
    if (!wasActive) return null
    // 关闭的是激活标签：优先激活右侧，否则左侧
    const next = tabs.value[idx] || tabs.value[idx - 1]
    return next ? next.path : '/dashboard'
  }

  /** 关闭其它标签，保留指定 path */
  function closeOthers(path) {
    tabs.value = tabs.value.filter((t) => t.path === path)
    tabs.value.forEach((t) => { t.active = t.path === path })
    persist()
  }

  /** 关闭全部（固定标签保留），返回跳转路径 */
  function closeAll() {
    tabs.value = []
    persist()
    return '/dashboard'
  }

  /** 请求刷新指定标签（MainLayout 监听 refreshQueue 重建组件） */
  function refresh(path) {
    const t = tabs.value.find((x) => x.path === path)
    if (!t) return
    refreshQueue.value.push(path)
  }

  /** 消费刷新队列（MainLayout 调用） */
  function consumeRefresh() {
    refreshQueue.value = []
  }

  return {
    tabs, tabList, cachedViews, activePath, refreshQueue,
    addTab, removeTab, closeOthers, closeAll, refresh, consumeRefresh,
  }
})
