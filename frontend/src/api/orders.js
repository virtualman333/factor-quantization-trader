import api from '@/utils/api'

export function getOrders(params) { return api.get('/orders/trades/', { params }) }
export function createOrder(data) { return api.post('/orders/trades/', data) }
export function cancelOrder(id) { return api.post(`/orders/trades/${id}/cancel/`) }
export function syncOrder(id) { return api.post(`/orders/trades/${id}/sync/`) }
export function syncPendingOrders() { return api.post('/orders/trades/sync_pending/') }
export function closePosition(data) { return api.post('/orders/trades/close_position/', data) }

export function getOrderLogs(params) { return api.get('/orders/logs/', { params }) }

export function batchCreateOrders(data) { return api.post('/orders/trades/batch/', data) }
export function placeAlgoOrder(data) { return api.post('/orders/trades/algo/', data) }
export function placeTwapOrder(data) { return api.post('/orders/trades/twap/', data) }
export function placeIcebergOrder(data) { return api.post('/orders/trades/iceberg/', data) }

export function getOrderTemplates(params) { return api.get('/orders/templates/', { params }) }
export function createOrderTemplate(data) { return api.post('/orders/templates/', data) }
export function updateOrderTemplate(id, data) { return api.put(`/orders/templates/${id}/`, data) }
export function deleteOrderTemplate(id) { return api.delete(`/orders/templates/${id}/`) }
export function placeOrderByTemplate(id, data) { return api.post(`/orders/templates/${id}/place/`, data) }

export function listAlgoOrders(params) { return api.get('/orders/trades/algos/', { params }) }
export function cancelAlgoOrder(data) { return api.post('/orders/trades/cancel_algo/', data) }
