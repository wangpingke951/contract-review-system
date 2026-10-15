// frontend/src/api/review.js — 审查 API
import request from './request'

export function createReview(contractId) {
  return request.post('/reviews', { contract_id: contractId }, { timeout: 300000 })
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
  return request.post(`/reviews/${id}/retry`, {}, { timeout: 300000 })
}
