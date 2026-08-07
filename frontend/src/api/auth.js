import api from '@/utils/api.js'

export function login(username, password) {
  return api.post('/account/auth/login/', { username, password })
}

export function register(data) {
  return api.post('/account/auth/register/', data)
}

export function refreshToken(refresh) {
  return api.post('/account/auth/refresh/', { refresh })
}

export function getMe() {
  return api.get('/account/auth/me/')
}

export function changePassword(oldPassword, newPassword) {
  return api.post('/account/auth/change-password/', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
