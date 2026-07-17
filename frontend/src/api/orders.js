import api from '@/utils/api'

export function getOrders(params) { return api.get('/orders/trades/', { params }) }
export function createOrder(data) { return api.post('/orders/trades/', data) }
export function cancelOrder(id) { return api.post(`/orders/trades/${id}/cancel/`) }
export function syncOrder(id) { return api.post(`/orders/trades/${id}/sync/`) }
export function syncPendingOrders() { return api.post('/orders/trades/sync_pending/') }
export function closePosition(data) { return api.post('/orders/trades/close_position/', data) }

export function getOrderLogs(params) { return api.get('/orders/logs/', { params }) }
