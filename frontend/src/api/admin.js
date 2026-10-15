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

export function listKnowledge() {
  return request.get('/admin/knowledge')
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
