import axios from 'axios'

import { getToken, removeToken, removeRefreshToken, removeStoredUser } from './token.js'

let logoutCallback = null

/**
 * 注册 401 无权限时的退出回调。
 * 在 main.js 中注入，避免循环依赖。
 * @param {Function} cb
 */
export function setLogoutCallback(cb) {
  logoutCallback = cb
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：自动附加 JWT
api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => Promise.reject(err)
)

// 响应拦截：统一提取 data；401 时执行退出并跳转登录
api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status
    const data = err.response?.data || {}
    const msg = data.message || data.detail || err.message || '请求失败'
    if (status === 401) {
      removeToken()
      removeRefreshToken()
      removeStoredUser()
      if (typeof logoutCallback === 'function') {
        logoutCallback()
      }
    }
    return Promise.reject(new Error(msg))
  }
)

export default api
