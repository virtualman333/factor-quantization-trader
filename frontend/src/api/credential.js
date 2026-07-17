import api from '@/utils/api.js'

export const credentialApi = {
  list: () => api.get('/account/credentials/'),
  active: () => api.get('/account/credentials/active/'),
  byEnv: (env) => api.get('/account/credentials/by_env/', { params: { env } }),
  update: (name, data) => api.put(`/account/credentials/${name}/`, data),
  testConnection: (env) => api.post('/account/credentials/test_connection/', env ? { env } : {}),

  switchEnv: (environment) => api.post('/account/credentials/switch_env/', { environment }),
}

export const systemConfigApi = {
  get: () => api.get('/account/system-config/'),
  update: (data) => api.post('/account/system-config/', data),
}
