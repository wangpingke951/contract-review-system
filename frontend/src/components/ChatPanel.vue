<!-- frontend/src/components/ChatPanel.vue — WebSocket 流式对话面板 -->
<template>
  <div class="chat-panel">
    <div class="chat-header">
      <el-icon><ChatDotRound /></el-icon>
      <span>报告追问</span>
      <el-tag size="small" type="info" v-if="streaming">回答中...</el-tag>
    </div>

    <div class="chat-messages" ref="msgBox">
      <div v-if="messages.length === 0 && !streaming" class="chat-empty">
        <el-empty description="围绕审查报告提问，例如：&quot;付款条款怎么改？&quot;" :image-size="60" />
      </div>

      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="bubble">
          <div class="md" v-html="renderMarkdown(m.content)"></div>
          <span v-if="m.streaming" class="cursor">▌</span>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <el-input
        v-model="draft"
        type="textarea"
        :rows="2"
        placeholder="输入追问内容，Enter 发送（Shift+Enter 换行）"
        :disabled="streaming"
        @keydown.enter.exact.prevent="send"
      />
      <el-button type="primary" :loading="streaming" :disabled="!draft.trim()" @click="send">
        <el-icon><Promotion /></el-icon> 发送
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConversation, getMessages, createChatSocket } from '@/api/chat'
import { renderMarkdown } from '@/utils/markdown'
import { useUserStore } from '@/stores/user'

const props = defineProps({ reviewId: { type: Number, required: true } })

const userStore = useUserStore()
const messages = ref([])
const draft = ref('')
const streaming = ref(false)
const msgBox = ref(null)
let socket = null

function scrollToBottom() {
  nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
}

function send() {
  const q = draft.value.trim()
  if (!q || streaming.value) return
  draft.value = ''
  messages.value.push({ role: 'user', content: q })
  const assistantMsg = { role: 'assistant', content: '', streaming: true }
  messages.value.push(assistantMsg)
  streaming.value = true
  scrollToBottom()
  socket.send(q)
  // 引用 assistantMsg 以便流式追加
  socket._current = assistantMsg
}

onMounted(async () => {
  // 加载历史 + 建立连接
  try {
    const conv = await getConversation(props.reviewId)
    const history = await getMessages(conv.id)
    messages.value = history.map((m) => ({ role: m.role, content: m.content }))
    scrollToBottom()

    socket = createChatSocket(conv.id, userStore.token, {
      onDelta(text) {
        const cur = socket._current
        if (cur) { cur.content += text; scrollToBottom() }
      },
      onDone() {
        const cur = socket._current
        if (cur) cur.streaming = false
        streaming.value = false
        socket._current = null
        scrollToBottom()
      },
      onError(msg) {
        ElMessage.error(msg)
        const cur = socket._current
        if (cur) { cur.streaming = false; if (!cur.content) cur.content = '（回答失败）' }
        streaming.value = false
        socket._current = null
      },
    })
  } catch (e) {
    ElMessage.error('对话初始化失败')
  }
})

onUnmounted(() => { socket?.close() })
</script>

<style scoped>
.chat-panel {
  display: flex; flex-direction: column;
  height: 560px; max-height: 70vh;
  border: 1px solid #e5e7eb; border-radius: 10px;
  background: #fff; overflow: hidden;
}
.chat-header {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; border-bottom: 1px solid #e5e7eb;
  font-weight: 700; background: #f8fafc;
}
.chat-messages { flex: 1; overflow-y: auto; padding: 16px; }
.chat-empty { height: 100%; display: flex; align-items: center; justify-content: center; }
.msg { display: flex; margin: 8px 0; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 85%; padding: 10px 14px; border-radius: 12px;
  font-size: 14px; line-height: 1.7; word-break: break-word;
}
.msg.user .bubble { background: #3b82f6; color: #fff; border-bottom-right-radius: 4px; white-space: pre-wrap; }
.msg.assistant .bubble { background: #f3f4f6; color: #1f2329; border-bottom-left-radius: 4px; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* markdown 渲染节点（v-html 内容需 :deep） */
.md :deep(h4) { margin: 10px 0 5px; font-size: 13px; font-weight: 500; }
.md :deep(h4:first-child) { margin-top: 0; }
.md :deep(p) { margin: 5px 0; }
.md :deep(p:first-child) { margin-top: 0; }
.md :deep(ul), .md :deep(ol) { margin: 5px 0; padding-left: 20px; }
.md :deep(li) { margin: 2px 0; }
.md :deep(strong) { font-weight: 500; }
.md :deep(code) {
  background: rgba(0,0,0,.06); padding: 1px 4px; border-radius: 3px;
  font-family: var(--font-mono, ui-monospace, monospace); font-size: 13px;
}
.chat-input {
  display: flex; gap: 10px; padding: 12px;
  border-top: 1px solid #e5e7eb; align-items: flex-end;
}
.chat-input .el-button { height: 54px; }
</style>
