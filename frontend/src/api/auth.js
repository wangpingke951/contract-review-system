// frontend/src/api/auth.js — 认证 API
import request from './request'

export function login(data) {
  return request.post('/auth/login', data)
}

export function loginAdmin(data) {
  return request.post('/auth/login/admin', data)
}

export function register(data) {
  return request.post('/auth/register', data)
}

export function getMe() {
  return request.get('/auth/me')
}
