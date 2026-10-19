// frontend/src/api/task.js — 任务中心 API
import request from './request'

export function getTasks() {
  return request.get('/tasks')
}

export function batchReview(contractIds, templateId) {
  return request.post('/tasks/batch-review', {
    contract_ids: contractIds,
    template_id: templateId ?? null,
  })
}
