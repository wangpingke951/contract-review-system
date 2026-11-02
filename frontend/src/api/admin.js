// frontend/src/api/admin.js — 管理后台 API
import request from './request'

export function uploadKnowledge(file, category) {
  const form = new FormData()
  form.append('file', file)
  form.append('category', category)
  return request.post('/admin/knowledge/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

/**
 * 批量上传：一次最多 20 个文件。
 * 返回 { uploaded: [...], rejected: [{filename, reason}] }，
 * 单个文件校验失败不会影响其它文件。
 */
export function uploadKnowledgeBatch(files, category) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  form.append('category', category)
  return request.post('/admin/knowledge/upload-batch', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

/** 入库进度（前端轮询用） */
export function getKnowledgeProgress(id) {
  return request.get(`/admin/knowledge/${id}/progress`)
}

/** 失败文档原地重试入库 */
export function retryKnowledge(id) {
  return request.post(`/admin/knowledge/${id}/retry`)
}

/** 原位替换知识文档内容（旧版本进历史） */
export function replaceKnowledge(id, file, category) {
  const form = new FormData()
  form.append('file', file)
  form.append('category', category)
  return request.put(`/admin/knowledge/${id}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

export function listKnowledge() {
  return request.get('/admin/knowledge')
}

export function listKnowledgeVersions(id) {
  return request.get(`/admin/knowledge/${id}/versions`)
}

export function deleteKnowledge(id) {
  return request.delete(`/admin/knowledge/${id}`)
}

export function listCategories() {
  return request.get('/admin/categories')
}

export function addCategory(name) {
  return request.post('/admin/categories', { name })
}

export function deleteCategory(id) {
  return request.delete(`/admin/categories/${id}`)
}

/** 审计日志分页查询 */
export function listAuditLogs({ page = 1, size = 50, action = '' } = {}) {
  const params = { page, size }
  if (action) params.action = action
  return request.get('/admin/audit-logs', { params })
}

/** LLM 用量统计 */
export function getUsageStats(days = 7) {
  return request.get('/admin/usage-stats', { params: { days } })
}

// ——— 模型配置 ———
export function getModelConfig() {
  return request.get('/admin/model-config')
}

export function updateModelConfig(data) {
  return request.put('/admin/model-config', data)
}

export function testModelConnection(data) {
  return request.post('/admin/model-config/test', data, { timeout: 40000 })
}

export function listModelProviders() {
  return request.get('/admin/model-config/providers')
}

// ——— 用户与权限 ———
export function listUsers() {
  return request.get('/admin/users')
}

export function listPermissionCatalog() {
  return request.get('/admin/users/permissions')
}

/** 全量覆盖该用户的权限点，传勾选后的完整列表 */
export function updateUserPermissions(id, permissions) {
  return request.put(`/admin/users/${id}/permissions`, { permissions })
}

export function updateUserStatus(id, isActive) {
  return request.put(`/admin/users/${id}/status`, { is_active: isActive })
}

export function resetUserPassword(id, newPassword) {
  return request.put(`/admin/users/${id}/password`, { new_password: newPassword })
}
