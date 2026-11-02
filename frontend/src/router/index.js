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

  // —— 管理类（按权限点控制，管理员天然全部可访问）——
  { path: '/admin/knowledge', name: 'KnowledgeManage', component: () => import('@/views/admin/KnowledgeManage.vue'), meta: { perm: 'knowledge:manage' } },
  { path: '/admin/categories', name: 'CategoryManage', component: () => import('@/views/admin/CategoryManage.vue'), meta: { perm: 'knowledge:manage' } },
  { path: '/admin/templates', name: 'TemplateManage', component: () => import('@/views/admin/TemplateManage.vue'), meta: { perm: 'template:manage' } },
  { path: '/admin/usage', name: 'UsageStats', component: () => import('@/views/admin/UsageStats.vue'), meta: { perm: 'stats:view' } },
  { path: '/admin/audit', name: 'AuditLog', component: () => import('@/views/admin/AuditLog.vue'), meta: { perm: 'audit:view' } },
  { path: '/admin/users', name: 'UserManage', component: () => import('@/views/admin/UserManage.vue'), meta: { perm: 'user:manage' } },
  // 模型配置含 API Key，不可授权，始终管理员独占
  { path: '/admin/model-config', name: 'ModelConfig', component: () => import('@/views/admin/ModelConfig.vue'), meta: { admin: true } },

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

  // 管理员独占（如模型配置）
  if (to.meta.admin && userStore.role !== 'admin') {
    next({ path: '/' })
    return
  }

  // 权限点校验：管理员恒通过
  if (to.meta.perm && !userStore.hasPerm(to.meta.perm)) {
    next({ path: '/' })
    return
  }

  next()
})

export default router
