<!-- frontend/src/views/Assistant.vue — 法律智能问答（日常场景咨询） -->
<template>
  <div class="assistant-page">
    <!-- 左：咨询记录 -->
    <aside class="session-pane">
      <div class="pane-head">
        <span class="pane-title">咨询记录</span>
        <el-button type="primary" size="small" @click="newSession">
          <el-icon><Plus /></el-icon> 新对话
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="s in sessions" :key="s.id"
          :class="['session-item', { active: s.id === currentId }]"
          @click="switchSession(s.id)"
        >
          <div class="s-title">{{ s.title }}</div>
          <div class="s-meta">{{ s.message_count }} 条 · {{ fmtTime(s.last_active_at) }}</div>
          <el-icon class="s-del" @click.stop="removeSession(s)"><Delete /></el-icon>
        </div>
        <el-empty v-if="!sessions.length" description="还没有咨询记录" :image-size="60" />
      </div>
    </aside>

    <!-- 右：问答区 -->
    <section class="chat-pane">
      <div class="chat-head">
        <el-icon color="#3b82f6"><ChatDotRound /></el-icon>
        <b>法律智能问答</b>
        <span class="sub">劳动 · 租房 · 消费 · 借贷 · 日常法律问题</span>
        <el-tag v-if="streaming" size="small" type="info">回答中...</el-tag>
      </div>

      <div class="chat-body" ref="msgBox">
        <!-- 空状态：常见问题引导 -->
        <div v-if="!messages.length && !streaming" class="welcome">
          <el-icon :size="36" color="#3b82f6"><ChatDotRound /></el-icon>
          <h3>有什么法律问题想问？</h3>
          <p>可以问劳动、租房、消费、借贷等日常问题，也可以直接贴一段合同条款让我分析</p>
          <div class="quick-list">
            <div v-for="q in quickQuestions" :key="q" class="quick" @click="ask(q)">{{ q }}</div>
          </div>
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
          :rows="3"
          resize="none"
          placeholder="描述你的问题，Enter 发送（Shift+Enter 换行）"
          :disabled="streaming"
          @keydown.enter.exact.prevent="send"
        />
        <div class="input-foot">
          <span class="disclaimer">回答仅供参考，重大权益问题请咨询执业律师</span>
          <el-button type="primary" :loading="streaming" :disabled="!draft.trim()" @click="send">
            <el-icon><Promotion /></el-icon> 发送
          </el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSession, listSessions, getMessages, deleteSession, createAssistantSocket,
} from '@/api/assistant'
import { renderMarkdown } from '@/utils/markdown'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const sessions = ref([])
const currentId = ref(null)
const messages = ref([])
const draft = ref('')
const streaming = ref(false)
const msgBox = ref(null)

let socket = null
let socketSid = null

const quickQuestions = [
  '试用期最长可以有多久？试用期工资怎么算？',
  '公司不支付加班费，我可以拒绝加班吗？',
  '被辞退能拿多少经济补偿？怎么计算？',
  '租房押金房东不退，我该怎么办？',
  '房东要提前收房，我能拒绝吗？',
  '二房东转租的合同有法律效力吗？',
  '网购七天无理由退货，哪些商品不能退？',
  '借条怎么写才有法律效力？民间借贷利息最高多少受保护？',
]

function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'
}

function scrollToBottom() {
  nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
}

async function refreshSessions() {
  try {
    sessions.value = await listSessions()
  } catch { /* 已提示 */ }
}

function ensureSocket(sid) {
  if (socket && socketSid === sid) return socket
  socket?.close()
  socketSid = sid
  socket = createAssistantSocket(sid, userStore.token, {
    onDelta(text) {
      const cur = socket?._current
      if (cur) { cur.content += text; scrollToBottom() }
    },
    onDone() {
      const cur = socket?._current
      if (cur) cur.streaming = false
      streaming.value = false
      if (socket) socket._current = null
      scrollToBottom()
      refreshSessions()   // 标题/消息数可能变了
    },
    onError(msg) {
      ElMessage.error(msg)
      const cur = socket?._current
      if (cur) { cur.streaming = false; if (!cur.content) cur.content = '（回答失败，请重试）' }
      streaming.value = false
      if (socket) socket._current = null
    },
  })
  return socket
}

/** 首次提问自动建会话 */
async function ensureSession() {
  if (currentId.value) return currentId.value
  const s = await createSession()
  currentId.value = s.id
  await refreshSessions()
  return s.id
}

async function send() {
  const q = draft.value.trim()
  if (!q || streaming.value) return

  let sid
  try {
    sid = await ensureSession()
  } catch { return }

  draft.value = ''
  messages.value.push({ role: 'user', content: q })
  const assistantMsg = { role: 'assistant', content: '', streaming: true }
  messages.value.push(assistantMsg)
  streaming.value = true
  scrollToBottom()

  const sk = ensureSocket(sid)
  sk._current = assistantMsg
  sk.send(q)
}

function ask(q) {
  draft.value = q
  send()
}

async function switchSession(id) {
  if (id === currentId.value) return
  // 切换时中断进行中的回答
  if (streaming.value) {
    socket?.close()
    socket = null
    socketSid = null
    streaming.value = false
  }
  currentId.value = id
  try {
    const history = await getMessages(id)
    messages.value = history.map((m) => ({ role: m.role, content: m.content }))
  } catch {
    messages.value = []
  }
  scrollToBottom()
}

function newSession() {
  socket?.close()
  socket = null
  socketSid = null
  streaming.value = false
  currentId.value = null
  messages.value = []
  draft.value = ''
}

async function removeSession(s) {
  try {
    await ElMessageBox.confirm(`确认删除会话「${s.title}」？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await deleteSession(s.id)
    ElMessage.success('已删除')
    if (s.id === currentId.value) newSession()
    await refreshSessions()
  } catch { /* 已提示 */ }
}

onMounted(async () => {
  await refreshSessions()
  // 默认展开最近一次咨询
  if (sessions.value.length) await switchSession(sessions.value[0].id)
})

onUnmounted(() => { socket?.close() })
</script>

<style scoped>
.assistant-page { height: calc(100vh - 130px); display: flex; gap: 16px; }

/* —— 左：会话列表 —— */
.session-pane {
  width: 260px; flex: none; display: flex; flex-direction: column;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;
}
.pane-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; border-bottom: 1px solid #e5e7eb; background: #f8fafc;
}
.pane-title { font-weight: 700; font-size: 14px; }
.session-list { flex: 1; overflow-y: auto; padding: 8px; }
.session-item {
  position: relative; padding: 10px 12px; border-radius: 8px; cursor: pointer;
  transition: background .15s;
}
.session-item:hover { background: #f3f4f6; }
.session-item.active { background: #eff6ff; }
.session-item .s-title {
  font-size: 13px; font-weight: 500; color: #1f2329;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-right: 18px;
}
.session-item .s-meta { font-size: 12px; color: #9ca3af; margin-top: 4px; }
.session-item .s-del {
  position: absolute; right: 8px; top: 10px; color: #cbd5e1;
  opacity: 0; transition: opacity .15s, color .15s;
}
.session-item:hover .s-del { opacity: 1; }
.session-item .s-del:hover { color: #ef4444; }

/* —— 右：问答区 —— */
.chat-pane {
  flex: 1; min-width: 0; display: flex; flex-direction: column;
  background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;
}
.chat-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 20px; border-bottom: 1px solid #e5e7eb; background: #f8fafc;
}
.chat-head b { font-size: 15px; }
.chat-head .sub { font-size: 12px; color: #9ca3af; }

.chat-body { flex: 1; overflow-y: auto; padding: 20px 24px; }

.welcome {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center;
}
.welcome h3 { margin: 14px 0 6px; font-size: 17px; font-weight: 500; color: #1f2329; }
.welcome p { margin: 0 0 22px; font-size: 13px; color: #9ca3af; }
.quick-list {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px; max-width: 660px; width: 100%;
}
.quick {
  padding: 11px 14px; font-size: 13px; color: #374151; text-align: left;
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
  cursor: pointer; transition: all .15s;
}
.quick:hover { background: #eff6ff; border-color: #93c5fd; color: #1d4ed8; }

.msg { display: flex; margin: 12px 0; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 78%; padding: 11px 15px; border-radius: 12px;
  font-size: 14px; line-height: 1.8; word-break: break-word;
}
.msg.user .bubble { background: #3b82f6; color: #fff; border-bottom-right-radius: 4px; white-space: pre-wrap; }
.msg.assistant .bubble { background: #f3f4f6; color: #1f2329; border-bottom-left-radius: 4px; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* 渲染后的 markdown 内容（v-html 生成的节点需要 :deep 才能命中 scoped 样式） */
.md :deep(h4) { margin: 12px 0 6px; font-size: 14px; font-weight: 500; color: #1f2329; }
.md :deep(h4:first-child) { margin-top: 0; }
.md :deep(p) { margin: 6px 0; }
.md :deep(p:first-child) { margin-top: 0; }
.md :deep(ul), .md :deep(ol) { margin: 6px 0; padding-left: 22px; }
.md :deep(li) { margin: 3px 0; }
.md :deep(strong) { font-weight: 500; color: #111827; }
.md :deep(code) {
  background: rgba(0,0,0,.06); padding: 1px 4px; border-radius: 3px;
  font-family: var(--font-mono, ui-monospace, monospace); font-size: 13px;
}

.chat-input { padding: 14px 20px 16px; border-top: 1px solid #e5e7eb; }
.input-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.disclaimer { font-size: 12px; color: #9ca3af; }
</style>
