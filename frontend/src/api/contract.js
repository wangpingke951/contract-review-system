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

/** 上传同一份合同的新版本（保留历史版本） */
export function uploadNewVersion(id, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/contracts/${id}/versions`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

/** 与上一版本比对：文本差异 + 上一版问题闭环 */
export function getContractDiff(id) {
  return request.get(`/contracts/${id}/diff`)
}
