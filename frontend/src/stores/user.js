// frontend/src/stores/user.js — Pinia 用户状态管理
// token / role / username 存 localStorage，刷新后自动恢复
import { defineStore } from 'pinia'

const STORAGE_KEY = 'cr_user_session'

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function saveToStorage(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function clearStorage() {
  localStorage.removeItem(STORAGE_KEY)
}

export const useUserStore = defineStore('user', {
  state: () => {
    const saved = loadFromStorage()
    return {
      token: saved?.token || '',
      username: saved?.username || '',
      role: saved?.role || '',
      userId: saved?.userId || null,
    }
  },

  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.role === 'admin',
  },

  actions: {
    login(payload) {
      this.token = payload.access_token
      this.role = payload.role
      this.username = payload.username || ''
      this.userId = payload.userId || null
      saveToStorage({
        token: this.token,
        role: this.role,
        username: this.username,
        userId: this.userId,
      })
    },
    logout() {
      this.token = ''
      this.role = ''
      this.username = ''
      this.userId = null
      clearStorage()
    },
    setMe(payload) {
      this.username = payload.username
      this.userId = payload.id
      this.role = payload.role
      saveToStorage({
        token: this.token,
        role: this.role,
        username: this.username,
        userId: this.userId,
      })
    },
  },
})
