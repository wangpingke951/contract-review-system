// frontend/src/stores/user.js — Pinia 用户状态管理
// token / role / username / permissions 存 localStorage，刷新后自动恢复
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
      // 细粒度权限点，由后端返回；管理员返回全部
      permissions: saved?.permissions || [],
    }
  },

  getters: {
    isLoggedIn: (state) => !!state.token,
    isAdmin: (state) => state.role === 'admin',
    // 菜单与路由守卫共用：管理员恒为 true，普通用户看授予情况
    hasPerm: (state) => (key) => state.role === 'admin' || state.permissions.includes(key),
  },

  actions: {
    _persist() {
      saveToStorage({
        token: this.token,
        role: this.role,
        username: this.username,
        userId: this.userId,
        permissions: this.permissions,
      })
    },
    login(payload) {
      this.token = payload.access_token
      this.role = payload.role
      this.username = payload.username || ''
      this.userId = payload.userId || null
      this.permissions = payload.permissions || []
      this._persist()
    },
    logout() {
      this.token = ''
      this.role = ''
      this.username = ''
      this.userId = null
      this.permissions = []
      clearStorage()
    },
    setMe(payload) {
      this.username = payload.username
      this.userId = payload.id
      this.role = payload.role
      // 权限可能被管理员调整，每次拉 me 都以服务端为准
      this.permissions = payload.permissions || []
      this._persist()
    },
  },
})
