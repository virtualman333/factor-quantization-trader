/**
 * 量化交易系统 Service Worker
 *
 * 策略：
 * - 预缓存应用壳（app shell），离线可打开
 * - 静态资源走缓存优先（stale-while-revalidate）
 * - API 请求（/api /admin）走网络优先，失败时回退缓存
 * - 不缓存 OKX 实时流
 */
const CACHE_VERSION = 'quant-v1'
const APP_SHELL = ['/', '/index.html', '/manifest.json']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL)).catch(() => {}),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)),
      ),
    ),
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)

  // 不拦截实时流（SSE / WebSocket）
  if (url.pathname.includes('/realtime/stream/') || url.protocol === 'ws:' || url.protocol === 'wss:') {
    return
  }

  // API 请求：网络优先
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/admin')) {
    event.respondWith(networkFirst(request))
    return
  }

  // 静态资源：缓存优先 + 后台更新
  event.respondWith(staleWhileRevalidate(request))
})

async function networkFirst(request) {
  try {
    const res = await fetch(request)
    if (res && res.ok) {
      const cache = await caches.open(CACHE_VERSION)
      cache.put(request, res.clone())
    }
    return res
  } catch (err) {
    const cached = await caches.match(request)
    if (cached) return cached
    throw err
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_VERSION)
  const cached = await cache.match(request)
  const fetchPromise = fetch(request)
    .then((res) => {
      if (res && res.ok && res.type === 'basic') {
        cache.put(request, res.clone())
      }
      return res
    })
    .catch(() => cached)
  return cached || fetchPromise
}
