/**
 * 策略 Store（Pinia）
 *
 * 职责：
 * - 缓存策略列表与详情，避免跨页面重复请求
 * - 提供统一的列表加载 / 失效 / 增删改接口
 * - 维护活跃策略数量等聚合状态，供仪表盘复用
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getStrategies, getStrategy, createStrategy, updateStrategy, deleteStrategy,
  activateStrategy, pauseStrategy,
} from '@/api/strategy'

export const useStrategyStore = defineStore('strategy', () => {
  // 列表缓存
  const list = ref([])
  const total = ref(0)
  const loading = ref(false)
  const lastParams = ref(null)
  const lastFetchedAt = ref(0)

  // 详情缓存：id -> { data, fetchedAt }
  const detailCache = ref(new Map())

  const activeCount = computed(() => list.value.filter((s) => s.status === 'active').length)
  const hasCache = computed(() => list.value.length > 0 && Date.now() - lastFetchedAt.value < 60_000)

  /**
   * 拉取策略列表
   * @param {Object} params 查询参数（page / page_size / 过滤条件）
   * @param {Object} options { force?: boolean } 强制刷新
   * @returns {Promise<{results, count}>}
   */
  async function fetchList(params = {}, options = {}) {
    const force = options.force !== false
    if (!force && lastParams.value && sameParams(lastParams.value, params) && hasCache.value) {
      return { results: list.value, count: total.value }
    }
    loading.value = true
    try {
      const res = await getStrategies(params)
      const results = res.results || res
      list.value = results
      total.value = res.count ?? results.length
      lastParams.value = { ...params }
      lastFetchedAt.value = Date.now()
      // 同步写入详情缓存
      for (const item of results) {
        if (item?.id != null) {
          detailCache.value.set(item.id, { data: item, fetchedAt: Date.now() })
        }
      }
      return { results, count: total.value }
    } finally {
      loading.value = false
    }
  }

  /** 拉取单个策略详情（带 30s 缓存） */
  async function fetchById(id, options = {}) {
    const cached = detailCache.value.get(id)
    if (cached && !options.force && Date.now() - cached.fetchedAt < 30_000) {
      return cached.data
    }
    const data = await getStrategy(id)
    detailCache.value.set(id, { data, fetchedAt: Date.now() })
    // 同步更新列表缓存中的同一条目
    const idx = list.value.findIndex((s) => s.id === id)
    if (idx !== -1) list.value[idx] = { ...list.value[idx], ...data }
    return data
  }

  /** 从缓存读取（不发请求） */
  function getById(id) {
    return detailCache.value.get(id)?.data || list.value.find((s) => s.id === id) || null
  }

  async function create(data) {
    const res = await createStrategy(data)
    invalidate()
    return res
  }

  async function update(id, data) {
    const res = await updateStrategy(id, data)
    detailCache.value.delete(id)
    invalidateListOnly()
    return res
  }

  async function remove(id) {
    const res = await deleteStrategy(id)
    detailCache.value.delete(id)
    invalidateListOnly()
    return res
  }

  async function activate(id) {
    const res = await activateStrategy(id)
    detailCache.value.delete(id)
    invalidateListOnly()
    return res
  }

  async function pause(id) {
    const res = await pauseStrategy(id)
    detailCache.value.delete(id)
    invalidateListOnly()
    return res
  }

  /** 清空所有缓存（增删改后调用） */
  function invalidate() {
    list.value = []
    total.value = 0
    lastParams.value = null
    lastFetchedAt.value = 0
    detailCache.value.clear()
  }

  /** 仅清空列表缓存，保留详情 */
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
    list, total, loading, activeCount, hasCache,
    fetchList, fetchById, getById,
    create, update, remove, activate, pause,
    invalidate, invalidateListOnly,
  }
})
