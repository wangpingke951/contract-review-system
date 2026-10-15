// frontend/src/api/assistant.js — 法律智能问答 API（REST + WebSocket 工厂）
import request from './request'

export function createSession(title) {
  return request.post('/assistant/sessions', { title })
}

export function listSessions() {
  return request.get('/assistant/sessions')
}

export function getMessages(sessionId) {
  return request.get(`/assistant/sessions/${sessionId}/messages`)
}

export function postMessage(sessionId, content) {
  return request.post(`/assistant/sessions/${sessionId}/messages`, { content }, { timeout: 120000 })
}

export function deleteSession(sessionId) {
  return request.delete(`/assistant/sessions/${sessionId}`)
}

/**
 * 创建流式问答 WebSocket
 * 回调：onDelta(片段) / onDone(完整回答) / onError(msg)
 * 返回 { send(question), close() }
 */
export function createAssistantSocket(sessionId, token, { onDelta, onDone, onError }) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(
    `${proto}://${location.host}/ws/assistant/${sessionId}?token=${encodeURIComponent(token)}`
  )

  // 连接尚未就绪时先把问题排队，onopen 后补发，避免首轮提问丢失
  let pending = []

  ws.onopen = () => {
    pending.forEach((q) => ws.send(JSON.stringify({ type: 'question', content: q })))
    pending = []
  }

  ws.onmessage = (evt) => {
    try {
      const frame = JSON.parse(evt.data)
      if (frame.type === 'delta') onDelta?.(frame.content)
      else if (frame.type === 'done') onDone?.(frame.answer)
      else if (frame.type === 'error') onError?.(frame.message)
    } catch { /* 忽略坏帧 */ }
  }
  ws.onerror = () => onError?.('连接中断，请稍后重试')

  return {
    send(question) {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'question', content: question }))
      } else if (ws.readyState === WebSocket.CONNECTING) {
        pending.push(question)
      } else {
        onError?.('连接未就绪，请稍后重试')
      }
    },
    close() {
      pending = []
      try { ws.close() } catch { /* */ }
    },
  }
}
