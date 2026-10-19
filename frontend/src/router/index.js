// frontend/src/router/index.js — Vue Router 4 路由表
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  // —— 公开 ——
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { public: true } },

  // —— 主流程（登录后）——
  { path: '/', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/tasks', name: 'TaskCenter', component: () => import('@/views/TaskCenter.vue') },
  { path: '/assistant', name: 'Assistant', component: () => import('@/views/Assistant.vue') },
  {
    path: '/reviews/contract/:contractId',
    name: 'ReviewByContract',
    component: () => import('@/views/ReviewReport.vue'),
  },
  { path: '/reviews/:id(\\d+)', name: 'ReviewReport', component: () => import('@/views/ReviewReport.vue') },

  // —— 管理员 ——
  { path: '/admin/knowledge', name: 'KnowledgeManage', component: () => import('@/views/admin/KnowledgeManage.vue'), meta: { admin: true } },
  { path: '/admin/categories', name: 'CategoryManage', component: () => import('@/views/admin/CategoryManage.vue'), meta: { admin: true } },
  { path: '/admin/templates', name: 'TemplateManage', component: () => import('@/views/admin/TemplateManage.vue'), meta: { admin: true } },
  { path: '/admin/model-config', name: 'ModelConfig', component: () => import('@/views/admin/ModelConfig.vue'), meta: { admin: true } },
  { path: '/admin/audit', name: 'AuditLog', component: () => import('@/views/admin/AuditLog.vue'), meta: { admin: true } },
  { path: '/admin/usage', name: 'UsageStats', component: () => import('@/views/admin/UsageStats.vue'), meta: { admin: true } },

  // —— 兜底 ——
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// —— 全局守卫 ——
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  // 公开页面，直接过
  if (to.meta.public) {
    next()
    return
  }

  // 未登录 → 跳登录页
  if (!userStore.isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // 需要管理员权限
  if (to.meta.admin && userStore.role !== 'admin') {
    next({ path: '/' })
    return
  }

  next()
})

export default router
