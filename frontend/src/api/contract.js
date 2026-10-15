// frontend/src/api/contract.js — 合同 API
import request from './request'

export function uploadContract(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/contracts/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export function listContracts(page = 1, size = 20) {
  return request.get('/contracts', { params: { page, size } })
}

export function getContract(id) {
  return request.get(`/contracts/${id}`)
}

export function deleteContract(id) {
  return request.delete(`/contracts/${id}`)
}
