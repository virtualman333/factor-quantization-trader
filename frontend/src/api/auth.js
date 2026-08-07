import api from '@/utils/api.js'

export function login(username, password) {
  return api.post('/auth/login/', { username, password })
}

export function register(data) {
  return api.post('/auth/register/', data)
}

export function refreshToken(refresh) {
  return api.post('/auth/refresh/', { refresh })
}

export function getMe() {
  return api.get('/auth/me/')
}
