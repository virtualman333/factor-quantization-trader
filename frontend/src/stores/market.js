/**
 * 行情 Store（Pinia）
 *
 * 职责：
 * - 缓存 Ticker 数据（按 inst_id 索引），避免 Tickers / 仪表盘重复轮询
 * - 与 realtime Store 联动：实时推送到达时调用 updateTicker 增量更新缓存
 * - 缓存交易品种列表，按 inst_type 分组
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getTickers, refreshTicker, getInstruments } from '@/api/market'
import { useRealtimeStore } from '@/stores/realtime'

export const useMarketStore = defineStore('market', () => {
  // inst_id -> ticker
  const tickers = ref(new Map())
  const tickersLoading = ref(false)
  const tickersLastFetchedAt = ref(0)

  // 品种缓存
  const instruments = ref([])
  const instrumentsByType = ref(new Map())
  const instrumentsLoading = ref(false)

  const tickerList = computed(() => [...tickers.value.values()])
  const tickerCount = computed(() => tickers.value.size)

  /**
   * 拉取 Ticker 列表
   * @param {Object} params { inst_type?, inst_ids? }
   * @param {Object} options { force?: boolean }
   */
  async function fetchTickers(params = {}, options = {}) {
    const force = options.force !== false
    if (!force && tickers.value.size > 0 && Date.now() - tickersLastFetchedAt.value < 15_000) {
      return tickerList.value
    }
    tickersLoading.value = true
    try {
      const res = await getTickers(params)
      const rows = res.results || res || []
      const next = new Map()
      for (const t of rows) {
        if (t.inst_id) next.set(t.inst_id, normalizeTicker(t))
      }
      // 合并：保留缓存中已有但本次未返回的 ticker（避免列表请求缩小时丢失）
      if (force) {
        tickers.value = next
      } else {
        const merged = new Map(tickers.value)
        for (const [k, v] of next) merged.set(k, v)
        tickers.value = merged
      }
      tickersLastFetchedAt.value = Date.now()
      return tickerList.value
    } finally {
      tickersLoading.value = false
    }
  }

  /** 主动刷新单个品种 ticker（触发后端从 OKX 拉取最新价） */
  async function refreshSingle(instId) {
    const res = await refreshTicker({ inst_id: instId })
    if (res?.inst_id) {
      tickers.value.set(instId, normalizeTicker(res))
      tickers.value = new Map(tickers.value)
    }
    return res
  }

  /** 从缓存读取单个 ticker */
  function getTicker(instId) {
    return tickers.value.get(instId) || null
  }

  /**
   * 实时推送到达时增量更新缓存
   * @param {Object} payload realtime Store 推送的 ticker 数据
   */
  function updateTicker(payload) {
    if (!payload?.inst_id) return
    const existing = tickers.value.get(payload.inst_id) || {}
    tickers.value.set(payload.inst_id, normalizeTicker({ ...existing, ...payload }))
    tickers.value = new Map(tickers.value)
  }

  /**
   * 订阅指定品种的实时 ticker 推送，并自动写入缓存
   * 返回取消订阅函数
   */
  function subscribeTicker(instId, handler) {
    const realtime = useRealtimeStore()
    const key = `tickers:${instId}`
    const wrapped = (payload) => {
      updateTicker(payload)
      handler?.(payload)
    }
    return realtime.subscribe(key, wrapped)
  }

  /**
   * 拉取交易品种列表（按 inst_type 缓存）
   * @param {Object} params { inst_type?, keyword?, page_size? }
   * @param {Object} options { force?: boolean }
   */
  async function fetchInstruments(params = {}, options = {}) {
    const instType = params.inst_type || 'ALL'
    const force = options.force !== false
    if (!force && instrumentsByType.value.has(instType)) {
      return instrumentsByType.value.get(instType)
    }
    instrumentsLoading.value = true
    try {
      const res = await getInstruments(params)
      const rows = res.results || res || []
      instrumentsByType.value.set(instType, rows)
      instruments.value = rows
      return rows
    } finally {
      instrumentsLoading.value = false
    }
  }

  function getInstrumentsByType(instType) {
    return instrumentsByType.value.get(instType || 'ALL') || []
  }

  function invalidateTickers() {
    tickers.value = new Map()
    tickersLastFetchedAt.value = 0
  }

  function invalidateInstruments() {
    instruments.value = []
    instrumentsByType.value = new Map()
  }

  return {
    tickers, tickerList, tickerCount, tickersLoading,
    instruments, instrumentsLoading,
    fetchTickers, refreshSingle, getTicker, updateTicker, subscribeTicker,
    fetchInstruments, getInstrumentsByType,
    invalidateTickers, invalidateInstruments,
  }
})

/** 归一化 ticker 字段，兼容后端不同返回格式 */
function normalizeTicker(raw) {
  return {
    inst_id: raw.inst_id,
    last: raw.last ?? raw.last_price ?? null,
    last_price: raw.last ?? raw.last_price ?? null,
    bid: raw.bid ?? null,
    ask: raw.ask ?? null,
    open24h: raw.open24h ?? raw.open_24h ?? null,
    high24h: raw.high24h ?? raw.high_24h ?? null,
    low24h: raw.low24h ?? raw.low_24h ?? null,
    vol24h: raw.vol24h ?? raw.vol_24h ?? null,
    change24h: raw.change24h ?? raw.change_24h ?? null,
    change_percent: raw.change_percent ?? raw.chg ?? null,
    ts: raw.ts ?? Date.now(),
    updated_at: raw.updated_at ?? new Date().toISOString(),
  }
}
