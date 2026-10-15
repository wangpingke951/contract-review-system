// frontend/src/api/chat.js — 对话 API（REST + WebSocket 工厂）
import request from './request'

export function getConversation(reviewId) {
  return request.get(`/chat/conversations/${reviewId}`)
}

export function getMessages(convId) {
  return request.get(`/chat/conversations/${convId}/messages`)
}

export function postMessage(convId, content) {
  return request.post(`/chat/conversations/${convId}/messages`, { content }, { timeout: 120000 })
}

/**
 * 创建流式对话 WebSocket
 * 回调：onDelta(text片段) / onDone(完整回答) / onError(msg)
 * 返回 { send(question), close() }
 */
export function createChatSocket(convId, token, { onDelta, onDone, onError }) {
  // WebSocket 走相对路径会经 vite proxy（开发）/nginx（生产）
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${convId}?token=${encodeURIComponent(token)}`)

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
      } else {
        onError?.('连接未就绪')
      }
    },
    close() {
      try { ws.close() } catch { /* */ }
    },
  }
}
