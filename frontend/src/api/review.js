// frontend/src/api/review.js — 审查 API
import request from './request'

export function createReview(contractId, templateId) {
  // 异步执行：后端立即返回 status=running，详情由报告页轮询
  return request.post('/reviews', {
    contract_id: contractId,
    template_id: templateId ?? null,
  })
}

export function getReview(id) {
  return request.get(`/reviews/${id}`)
}

export function getReviewStatus(id) {
  return request.get(`/reviews/${id}/status`)
}

export function getReviewByContract(contractId) {
  return request.get(`/reviews/by-contract/${contractId}`)
}

export function retryReview(id) {
  return request.post(`/reviews/${id}/retry`, {})
}

/** 风险项处置：pending / confirmed / ignored / todo */
export function updateRiskItem(reviewId, itemId, status) {
  return request.patch(`/reviews/${reviewId}/items/${itemId}`, { status })
}

/** 下载 Word 报告（返回 blob） */
export function downloadReviewReport(id) {
  return request.get(`/reviews/${id}/export`, {
    responseType: 'blob',
    timeout: 120000,
  })
}

/** 报告定稿 / 取消定稿 */
export function finalizeReview(id, finalize = true) {
  return request.post(`/reviews/${id}/finalize`, {}, { params: { finalize } })
}
