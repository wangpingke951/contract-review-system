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
