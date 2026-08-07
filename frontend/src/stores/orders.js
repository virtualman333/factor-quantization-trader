/**
 * 订单 Store（Pinia）
 *
 * 职责：
 * - 缓存订单列表，避免订单页/仪表盘重复请求
 * - 实时更新订单状态：对接 realtime 推送或主动同步结果时增量更新缓存
 * - 维护活跃订单数等聚合状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getOrders, createOrder, cancelOrder, syncOrder, syncPendingOrders,
  closePosition as closePositionApi,
} from '@/api/orders'

export const useOrderStore = defineStore('orders', () => {
  const list = ref([])
  const total = ref(0)
  const loading = ref(false)
  const lastParams = ref(null)
  const lastFetchedAt = ref(0)

  // 活跃订单：未完全成交且未撤销
  const liveCount = computed(() =>
    list.value.filter((o) => o.state === 'live' || o.state === 'partially_filled').length
  )

  const hasCache = computed(() => list.value.length > 0 && Date.now() - lastFetchedAt.value < 10_000)

  /**
   * 拉取订单列表
   * @param {Object} params { page?, page_size?, state?, side? }
   * @param {Object} options { force?: boolean }
   */
  async function fetchList(params = {}, options = {}) {
    const force = options.force !== false
    if (!force && lastParams.value && sameParams(lastParams.value, params) && hasCache.value) {
      return { results: list.value, count: total.value }
    }
    loading.value = true
    try {
      const res = await getOrders(params)
      const results = res.results || res
      list.value = results
      total.value = res.count ?? results.length
      lastParams.value = { ...params }
      lastFetchedAt.value = Date.now()
      return { results, count: total.value }
    } finally {
      loading.value = false
    }
  }

  async function create(data) {
    const res = await createOrder(data)
    invalidateListOnly()
    return res
  }

  async function cancel(id) {
    const res = await cancelOrder(id)
    updateOrderState(id, 'canceled')
    return res
  }

  async function sync(id) {
    const res = await syncOrder(id)
    // 同步后刷新单条（后端可能返回更新后的订单）
    if (res && res.id) {
      upsert(res)
    } else {
      invalidateListOnly()
    }
    return res
  }

  async function syncPending() {
    const res = await syncPendingOrders()
    invalidateListOnly()
    return res
  }

  async function closePosition(data) {
    const res = await closePositionApi(data)
    invalidateListOnly()
    return res
  }

  /**
   * 实时推送到达时增量更新订单
   * @param {Object} payload 订单更新数据（含 id / state / fill_sz 等）
   */
  function updateOrder(payload) {
    if (!payload?.id) return
    upsert(payload)
  }

  /** 更新单条订单状态（乐观更新） */
  function updateOrderState(id, state) {
    const idx = list.value.findIndex((o) => o.id === id)
    if (idx !== -1) {
      list.value[idx] = { ...list.value[idx], state }
      list.value = [...list.value]
    }
  }

  /** 插入或更新单条订单 */
  function upsert(order) {
    if (!order?.id) return
    const idx = list.value.findIndex((o) => o.id === order.id)
    if (idx !== -1) {
      list.value[idx] = { ...list.value[idx], ...order }
    } else {
      list.value.unshift(order)
      total.value += 1
    }
    list.value = [...list.value]
  }

  function invalidate() {
    list.value = []
    total.value = 0
    lastParams.value = null
    lastFetchedAt.value = 0
  }

  function invalidateListOnly() {
    lastFetchedAt.value = 0
  }

  function sameParams(a, b) {
    const ka = Object.keys(a || {}).sort()
    const kb = Object.keys(b || {}).sort()
    if (ka.length !== kb.length) return false
    return ka.every((k, i) => k === kb[i] && String(a[k]) === String(b[k]))
  }

  return {
    list, total, loading, liveCount, hasCache,
    fetchList, create, cancel, sync, syncPending, closePosition,
    updateOrder, updateOrderState, upsert,
    invalidate, invalidateListOnly,
  }
})
