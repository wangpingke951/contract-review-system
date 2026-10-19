// frontend/src/api/template.js — 审查模板 API
import request from './request'

export function listTemplates() {
  return request.get('/templates')
}

export function createTemplate(data) {
  return request.post('/templates', data)
}

export function updateTemplate(id, data) {
  return request.put(`/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return request.delete(`/templates/${id}`)
}
