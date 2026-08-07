/**
 * 实时行情通道 Store（SSE over fetch）
 *
 * 维护一条到 /api/market/realtime/stream/ 的长连接：
 * - 页面通过 subscribe(key, handler) 订阅，handler 收到归一化行情后自行更新 UI；
 * - 订阅集合变化时自动重连（合并去重）；
 * - 断线后指数退避自动重连，401 时停止；
 * - 连接状态供导航栏指示器实时展示。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getToken } from '@/utils/token.js'

const STREAM_URL = '/api/market/realtime/stream/'

function encodeKeys(keys) {
  return keys.map((key) => encodeURIComponent(key)).join(',')
}

export const useRealtimeStore = defineStore('realtime', () => {
  const status = ref('disconnected') // connecting | connected | disconnected
  const serverConnected = ref(false) // OKX 上游 WS 是否已连接
  const error = ref('')
  const lastMessageAt = ref(null)

  // key('tickers:BTC-USDT' / 'candle1H:BTC-USDT') -> Set(handler)
  const subscriptions = new Map()

  let controller = null
  let openTimer = null
  let reconnectTimer = null
  let reconnectAttempts = 0
  let stopRequested = false
  let opening = false

  const statusText = computed(() => {
    if (status.value === 'connected') {
      return serverConnected.value ? '实时已连接' : '通道已连接'
    }
    if (status.value === 'connecting') return '实时连接中'
    return '实时未连接'
  })

  const statusType = computed(() => {
    if (status.value === 'connected' && serverConnected.value) return 'success'
    if (status.value === 'connected' || status.value === 'connecting') return 'warning'
    return 'danger'
  })

  function currentKeys() {
    return [...subscriptions.keys()].sort()
  }

  function subscribe(key, handler) {
    if (typeof handler !== 'function') return () => {}
    if (!subscriptions.has(key)) subscriptions.set(key, new Set())
    subscriptions.get(key).add(handler)
    scheduleOpen()
    return () => unsubscribe(key, handler)
  }

  function unsubscribe(key, handler) {
    const set = subscriptions.get(key)
    if (!set) return
    set.delete(handler)
    if (set.size === 0) subscriptions.delete(key)
    scheduleOpen()
  }

  /** 订阅集合变化后，合并触发一次重连 */
  function scheduleOpen() {
    if (stopRequested) return
    if (openTimer) clearTimeout(openTimer)
    reconnectAttempts = 0
    openTimer = setTimeout(() => {
      openStream()
    }, 150)
  }

  /** 打开/重开流（MainLayout 挂载时调用，无订阅也会建立以跟踪状态） */
  function ensureOpen() {
    if (stopRequested) stopRequested = false
    scheduleOpen()
  }

  /** 手动重连（点击状态指示器） */
  function reconnect() {
    if (stopRequested) stopRequested = false
    scheduleOpen()
  }

  /** 完全关闭（MainLayout 卸载时调用） */
  function close() {
    stopRequested = true
    if (openTimer) clearTimeout(openTimer)
    if (reconnectTimer) clearTimeout(reconnectTimer)
    abortCurrentStream()
    subscriptions.clear()
    status.value = 'disconnected'
    serverConnected.value = false
  }

  function abortCurrentStream() {
    if (controller) {
      controller.abort()
      controller = null
    }
  }

  function scheduleReconnect() {
    if (stopRequested) return
    if (reconnectTimer) clearTimeout(reconnectTimer)
    const delay = Math.min(15000, 1000 * 2 ** reconnectAttempts)
    reconnectAttempts += 1
    reconnectTimer = setTimeout(() => openStream(), delay)
  }

  async function openStream() {
    if (stopRequested || opening) return
    opening = true
    try {
      abortCurrentStream()
      status.value = 'connecting'
      error.value = ''

      const token = getToken()
      if (!token) {
        status.value = 'disconnected'
        serverConnected.value = false
        return
      }

      const keys = currentKeys()
      const url = `${STREAM_URL}?subscribe=${encodeKeys(keys)}`
      controller = new AbortController()
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      })

      if (stopRequested) return
      if (res.status === 401) {
        status.value = 'disconnected'
        serverConnected.value = false
        error.value = '登录已过期，实时通道已停止'
        return
      }
      if (!res.ok || !res.body) {
        throw new Error(`实时通道请求失败 (HTTP ${res.status})`)
      }

      status.value = 'connected'
      reconnectAttempts = 0
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (!stopRequested) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let sep = buffer.indexOf('\n\n')
        while (sep !== -1) {
          const frame = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)
          handleFrame(frame)
          sep = buffer.indexOf('\n\n')
        }
      }

      if (!stopRequested) {
        status.value = 'disconnected'
        serverConnected.value = false
        scheduleReconnect()
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        // 主动取消（订阅变化 / 关闭），不触发重连
      } else {
        error.value = err.message || '实时通道异常'
        status.value = 'disconnected'
        serverConnected.value = false
        if (!stopRequested) scheduleReconnect()
      }
    } finally {
      opening = false
    }
  }

  function handleFrame(frame) {
    if (!frame || frame.startsWith(':')) return
    let event = 'message'
    const dataLines = []
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (dataLines.length === 0) return

    let payload
    try {
      payload = JSON.parse(dataLines.join('\n'))
    } catch {
      return
    }
    lastMessageAt.value = Date.now()

    if (event === 'status') {
      serverConnected.value = payload.connected === true
      return
    }
    if (event === 'heartbeat') return

    const key =
      event === 'ticker'
        ? `tickers:${payload.inst_id}`
        : `${payload.channel}:${payload.inst_id}`
    const handlers = subscriptions.get(key)
    if (!handlers) return
    for (const handler of [...handlers]) {
      try {
        handler(payload)
      } catch (e) {
        console.error(`realtime handler error [${key}]`, e)
      }
    }
  }

  return {
    status,
    serverConnected,
    error,
    lastMessageAt,
    statusText,
    statusType,
    subscribe,
    ensureOpen,
    reconnect,
    close,
  }
})
