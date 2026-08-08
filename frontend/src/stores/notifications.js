import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElNotification as ElToast } from 'element-plus'
import {
  listNotifications, getNotificationSummary,
  markNotificationsRead, markAllNotificationsRead,
  clearAllNotifications, deleteNotification,
} from '@/api/notifications'

const POLL_INTERVAL = 30_000

const LEVEL_ICON = {
  info: 'InfoFilled',
  success: 'CircleCheckFilled',
  warning: 'WarningFilled',
  danger: 'CircleCloseFilled',
}
const LEVEL_TYPE = {
  info: 'info',
  success: 'success',
  warning: 'warning',
  danger: 'error',
}
const TYPE_ICON = {
  order_state: 'List',
  signal_generated: 'TrendCharts',
  risk_warning: 'Warning',
  strategy_event: 'SetUp',
  backtest_done: 'DataAnalysis',
  system_notice: 'Bell',
  market_alert: 'Coin',
}

export const useNotificationStore = defineStore('notification', () => {
  const list = ref([])
  const loading = ref(false)
  const summary = ref({ total_unread: 0, by_type: {}, by_level: {} })
  const filter = ref({ unread_only: false, type: '' })

  // 最新已接收 id，用于检测“新消息”触发 toast
  const lastSeenMaxId = ref(0)

  const totalUnread = computed(() => summary.value.total_unread || 0)

  async function fetchSummary({ silent = false } = {}) {
    try {
      const res = await getNotificationSummary()
      const before = summary.value.total_unread || 0
      summary.value = res || { total_unread: 0, by_type: {}, by_level: {} }
      const unreadDelta = Math.max(0, (summary.value.total_unread || 0) - before)
      return { unreadDelta }
    } catch (err) {
      if (!silent) console.warn('[notify] summary failed', err)
      return { unreadDelta: 0 }
    }
  }

  async function fetchList({ silent = false } = {}) {
    loading.value = true
    try {
      const res = await listNotifications({
        unread_only: filter.value.unread_only ? 1 : 0,
        type: filter.value.type || undefined,
        limit: 100,
      })
      const results = res?.results || res || []
      const prev = list.value
      const prevIds = new Set((prev || []).map(x => x.id))
      const newItems = results.filter(x => !prevIds.has(x.id) && x.id > (lastSeenMaxId.value || 0))
      // 新消息 toast（最多 3 条，怕轰炸）
      if (newItems.length && prev.length) {
        newItems.slice(0, 3).forEach(item => {
          try { toast(item) } catch {}
        })
      }
      list.value = results
      if (results.length) {
        lastSeenMaxId.value = Math.max(lastSeenMaxId.value, ...results.map(x => x.id))
      }
    } catch (err) {
      if (!silent) console.warn('[notify] list failed', err)
    } finally { loading.value = false }
  }

  function toast(item) {
    const level = (item.level_display || item.level || 'info').toLowerCase()
    const type = LEVEL_TYPE[level] || 'info'
    const title = item.title || '新通知'
    const message = item.content
    const onClick = () => {
      if (item.target_route) {
        try { window.__vue_app__?.config?.globalProperties?.$router?.push(item.target_route) } catch {}
      }
    }
    ElToast({
      title,
      message: message || '',
      type,
      duration: item.level === 'danger' || item.level === 40 ? 0 : 6000,
      showClose: true,
      onClick,
    })
  }

  async function refreshAll({ silent = false } = {}) {
    await Promise.all([
      fetchSummary({ silent }),
      fetchList({ silent }),
    ])
  }

  // ===== 轮询 =====
  let _timer = null
  function startPolling() {
    if (_timer) return
    refreshAll({ silent: true }).catch(() => {})
    _timer = setInterval(() => {
      refreshAll({ silent: true }).catch(() => {})
    }, POLL_INTERVAL)
  }
  function stopPolling() {
    if (_timer) clearInterval(_timer)
    _timer = null
  }

  // ===== 写操作 =====
  async function markRead(items) {
    const ids = Array.isArray(items) ? items.map(x => x.id ?? x).filter(Boolean) : [items?.id ?? items].filter(Boolean)
    if (!ids.length) return 0
    const res = await markNotificationsRead({ ids })
    list.value = list.value.map(x => ids.includes(x.id) ? { ...x, read: true } : x)
    summary.value.total_unread = Math.max(0, (summary.value.total_unread || 0) - ids.length)
    return res?.updated || 0
  }
  async function markAllRead() {
    const res = await markAllNotificationsRead()
    list.value = list.value.map(x => ({ ...x, read: true }))
    summary.value.total_unread = 0
    return res?.updated || 0
  }
  async function remove(id) {
    try { await deleteNotification(id) } catch {}
    list.value = list.value.filter(x => x.id !== id)
  }
  async function clearAll() {
    try { await clearAllNotifications() } catch {}
    list.value = []
    summary.value.total_unread = 0
  }

  function iconFor(item) {
    return TYPE_ICON[item.type] || 'Bell'
  }
  function levelType(item) {
    const l = (item.level_display || 'info').toLowerCase()
    return LEVEL_TYPE[l] || 'info'
  }

  return {
    // state
    list, loading, summary, filter, lastSeenMaxId,
    // getters
    totalUnread,
    // actions
    fetchSummary, fetchList, refreshAll,
    startPolling, stopPolling,
    markRead, markAllRead, remove, clearAll,
    toast, iconFor, levelType,
  }
})
