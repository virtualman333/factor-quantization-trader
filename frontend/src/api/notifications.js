import api from '@/utils/api'

/** 通知列表：分页 + 筛选
 * @param {Object} params
 * @param {0|1} [params.unread_only]
 * @param {string} [params.type] order_state / signal_generated / risk_warning / strategy_event / backtest_done / system_notice / market_alert
 * @param {number} [params.limit] 拉取条数，默认 200
 */
export function listNotifications(params) { return api.get('/notifications/', { params }) }

/** 未读数汇总（顶栏铃铛角标） */
export function getNotificationSummary() { return api.get('/notifications/summary/') }

/** 单条或批量标记已读
 * @param {{id?: number, ids?: number[]}} data
 */
export function markNotificationsRead(data) { return api.post('/notifications/mark_read/', data) }

/** 全部标记已读 */
export function markAllNotificationsRead() { return api.post('/notifications/mark_all_read/') }

/** 清空所有通知 */
export function clearAllNotifications() { return api.post('/notifications/clear_all/') }

/** 删除一条 */
export function deleteNotification(id) { return api.delete(`/notifications/${id}/`) }
