import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

import {
  getToken, setToken, removeToken,
  getRefreshToken, setRefreshToken, removeRefreshToken,
  getStoredUser, setStoredUser, removeStoredUser,
  clearAuthStorage,
} from '@/utils/token.js'
import { login as loginApi, getMe } from '@/api/auth.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken() || '')
  const refreshToken = ref(getRefreshToken() || '')
  const user = ref(getStoredUser())

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => !!user.value?.is_staff)

  function setAuth(access, refresh, userData) {
    token.value = access
    refreshToken.value = refresh
    user.value = userData
    setToken(access)
    setRefreshToken(refresh)
    setStoredUser(userData)
  }

  function clearAuth() {
    token.value = ''
    refreshToken.value = ''
    user.value = null
    clearAuthStorage()
  }

  async function login(username, password) {
    const res = await loginApi(username, password)
    if (res.code !== 200) {
      throw new Error(res.message || '登录失败')
    }
    setAuth(res.data.access, res.data.refresh, res.data.user)
    return res.data
  }

  async function loadUser() {
    if (!token.value) return
    try {
      const res = await getMe()
      if (res.code === 200) {
        user.value = res.data
        setStoredUser(res.data)
      }
    } catch (err) {
      clearAuth()
      throw err
    }
  }

  function logout() {
    clearAuth()
  }

  return {
    token,
    refreshToken,
    user,
    isLoggedIn,
    isAdmin,
    setAuth,
    clearAuth,
    login,
    logout,
    loadUser,
  }
})
