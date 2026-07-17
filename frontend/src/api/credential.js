import api from '@/utils/api.js'

export const credentialApi = {
  list: () => api.get('/account/credentials/'),
  active: () => api.get('/account/credentials/active/'),
  create: (data) => api.post('/account/credentials/', data),
  update: (id, data) => api.put(`/account/credentials/${id}/`, data),
  testConnection: () => api.post('/account/credentials/test_connection/'),
  delete: (id) => api.delete(`/account/credentials/${id}/`),
}
