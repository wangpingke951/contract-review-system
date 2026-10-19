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

/** 原地重新解析已保存的原始文件（配置修复后免重传） */
export function reparseContract(id) {
  return request.post(`/contracts/${id}/reparse`, {}, { timeout: 180000 })
}

/** 用新文件替换原始文件并重新解析（解析失败后重传，不新增记录） */
export function replaceContractFile(id, file) {
  const form = new FormData()
  form.append('file', file)
  return request.post(`/contracts/${id}/replace`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}
