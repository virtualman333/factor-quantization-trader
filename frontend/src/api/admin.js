import api from '@/utils/api.js'

export const adminApi = {
  // 用户管理
  listUsers: (params) => api.get('/account/admin/users/', { params }),
  getUserStats: () => api.get('/account/admin/users/stats/'),
  toggleUserActive: (userId) => api.post(`/account/admin/users/${userId}/toggle_active/`),
  toggleUserStaff: (userId) => api.post(`/account/admin/users/${userId}/toggle_staff/`),

  // 配额管理
  listQuotas: (params) => api.get('/account/admin/quotas/', { params }),
  getQuotaByUser: (userId) => api.get('/account/admin/quotas/by_user/', { params: { user_id: userId } }),
  updateQuota: (id, data) => api.put(`/account/admin/quotas/${id}/`, data),
  batchUpdateQuotas: (data) => api.post('/account/admin/quotas/batch_update/', data),

  // 全局配置
  getGlobalConfig: () => api.get('/account/admin/global-config/'),
  updateGlobalConfig: (data) => api.post('/account/admin/global-config/', data),

  // 管理概览
  getOverview: () => api.get('/account/admin/overview/'),
}
