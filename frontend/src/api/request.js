// frontend/src/api/request.js — Axios 统一封装
// baseURL 从 .env 的 VITE_API_BASE_URL 读取；所有请求自动带 JWT；401 自动登出
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const request = axios.create({
  // Vite 开发时 vite proxy 把 /api 代理到 localhost:8000
  // 生产时 Nginx 反代把 /api 转到 backend
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
})

// —— 请求拦截器：自动挂 JWT ——
request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

// —— 响应拦截器：统一解包 + 错误处理 ——
// 兼容两种后端响应格式：
// 1) 信封格式 {code:0, data:..., message:""}（/api/health 等少数端点）
// 2) 裸 JSON（FastAPI response_model 直接返回，如 login/reviews/contracts）
request.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        ElMessage.error(body.message || '请求失败')
        return Promise.reject(new Error(body.message || 'Request failed'))
      }
      return body.data
    }
    return body // 裸 JSON 直接返回
  },
  (err) => {
    // 401 → 强制登出
    if (err.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      ElMessage.warning('登录已过期，请重新登录')
      router.push('/login')
    } else if (err.response?.data?.message) {
      ElMessage.error(err.response.data.message)
    } else {
      ElMessage.error(err.message || '网络错误')
    }
    return Promise.reject(err)
  }
)

export default request
