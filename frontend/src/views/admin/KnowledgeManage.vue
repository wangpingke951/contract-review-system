<!-- frontend/src/views/admin/KnowledgeManage.vue — 知识库管理 -->
<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <el-icon><FolderOpened /></el-icon>
        <span>知识库管理</span>
        <div class="toolbar">
          <el-input
            v-model="keyword" placeholder="搜索文件名" clearable
            style="width:200px" :prefix-icon="Search"
          />
          <el-select v-model="filterCat" clearable placeholder="全部分类" style="width:130px">
            <el-option label="合同模板" value="template" />
            <el-option label="审查指引" value="guide" />
            <el-option label="历史判例" value="case" />
            <el-option label="法律法规" value="law" />
          </el-select>
          <el-button type="primary" @click="openUpload">
            <el-icon><Plus /></el-icon> 上传知识文档
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      type="info" :closable="false" show-icon style="margin-bottom:16px"
      title="知识文档是审查报告的依据来源。支持 PDF / Word / TXT / 图片（多模态识别），仅限中文。上传后自动切块并向量化，删除将同步清除向量库。"
    />

    <el-table :data="filteredDocs" v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column label="类别" width="110">
        <template #default="{ row }">
          <el-tag size="small">{{ catText(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="150">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.status === 'failed' && row.error_message"
            :content="row.error_message" placement="top"
          >
            <el-tag type="danger" size="small">失败</el-tag>
          </el-tooltip>
          <el-tag
            v-else
            :type="row.status === 'enabled' ? 'success' : 'warning'" size="small"
          >
            {{ statusText(row.status) }}
          </el-tag>
          <!-- 处理中显示进度，避免用户以为卡住了 -->
          <el-progress
            v-if="row.status === 'chunking'"
            :percentage="row.progress || 0" :stroke-width="4" :show-text="false"
            style="margin-top:4px"
          />
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="切块数" width="80" />
      <el-table-column label="上传时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'failed'" link type="primary"
            :loading="retryingId === row.id" @click="handleRetry(row)"
          >重试入库</el-button>
          <el-button v-if="row.status === 'enabled'" link type="primary" @click="openReplace(row)">替换</el-button>
          <el-button link @click="openVersions(row)">历史</el-button>
          <el-popconfirm title="删除后向量库同步清除，不可恢复，确认？" width="260" @confirm="handleDelete(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无知识文档" :image-size="80" /></template>
    </el-table>

    <!-- 上传对话框 -->
    <el-dialog v-model="dialogVisible" title="上传知识文档" width="560">
      <el-form label-width="80px">
        <el-form-item label="类别">
          <el-select v-model="form.category" style="width:100%">
            <el-option label="审查指引" value="guide" />
            <el-option label="合同模板" value="template" />
            <el-option label="历史判例" value="case" />
            <el-option label="法律法规" value="law" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            ref="uploadRef"
            drag multiple :auto-upload="false" :show-file-list="false"
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
            :on-change="onFilesPicked"
          >
            <el-icon :size="32" color="#3b82f6"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击选择（支持多选）</div>
          </el-upload>
          <div class="upload-hint">
            支持 PDF / Word / TXT / MD / 图片，单文件 ≤ {{ MAX_MB }}MB，一次最多 {{ MAX_FILES }} 个。<br />
            上传后后台入库，可离开本页；50 万字约需 20 秒。
          </div>
        </el-form-item>
      </el-form>

      <!-- 待入库列表：逐个文件显示进度 -->
      <div v-if="queue.length" class="queue">
        <div v-for="item in queue" :key="item.uid" class="queue-item">
          <div class="queue-row">
            <span class="q-name" :title="item.name">{{ item.name }}</span>
            <span class="q-size">{{ (item.size / 1024 / 1024).toFixed(2) }}MB</span>
            <el-tag v-if="item.status === 'enabled'" type="success" size="small">已入库</el-tag>
            <el-tag v-else-if="item.status === 'failed'" type="danger" size="small">失败</el-tag>
            <el-tag v-else-if="item.status === 'uploading'" type="info" size="small">上传中</el-tag>
            <el-tag v-else-if="item.status === 'waiting'" type="info" size="small">排队中</el-tag>
            <el-tag v-else type="warning" size="small">入库中</el-tag>
          </div>
          <el-progress
            v-if="item.status === 'chunking' || item.status === 'enabled'"
            :percentage="item.progress" :stroke-width="6" :status="item.status === 'enabled' ? 'success' : ''"
          />
          <div v-if="item.error" class="q-err">{{ item.error }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="closeUpload" :disabled="processing">关闭</el-button>
        <el-button
          type="primary" :loading="processing" :disabled="!waitingCount"
          @click="handleUpload"
        >
          {{ processing ? '提交中...' : (waitingCount ? `上传入库（${waitingCount}）` : '上传入库') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 替换对话框 -->
    <el-dialog v-model="replaceVisible" title="替换知识文档内容" width="500">
      <el-alert
        type="warning" :closable="false" show-icon style="margin-bottom:14px"
        title="替换后旧版本会进入「历史」，旧向量同步清除，编号不变。"
      />
      <el-form label-width="80px">
        <el-form-item label="当前文件">
          <span class="cur-file">{{ replaceRow?.filename }}</span>
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="replaceForm.category" style="width:100%">
            <el-option label="审查指引" value="guide" />
            <el-option label="合同模板" value="template" />
            <el-option label="历史判例" value="case" />
            <el-option label="法律法规" value="law" />
          </el-select>
        </el-form-item>
        <el-form-item label="新文件">
          <el-upload
            ref="replaceUploadRef"
            drag :auto-upload="false" :limit="1"
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
            :on-change="pickReplaceFile"
            :on-remove="() => (replaceForm.file = null)"
          >
            <el-icon :size="32" color="#3b82f6"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传</div>
          </el-upload>
          <div class="upload-hint">单文件 ≤ {{ MAX_MB }}MB；替换后同样走后台入库</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="replaceVisible = false">取消</el-button>
        <el-button type="primary" :loading="replacing" :disabled="!replaceForm.file" @click="handleReplace">
          {{ replacing ? '替换中...' : '确认替换' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 版本历史 -->
    <el-dialog v-model="versionsVisible" title="历史版本" width="560">
      <el-table :data="versions" size="small">
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column label="类别" width="100">
          <template #default="{ row }">{{ catText(row.category) }}</template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="切块数" width="80" />
        <el-table-column label="替换时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.replaced_at) }}</template>
        </el-table-column>
        <template #empty><el-empty description="暂无历史版本（仅替换过的文档会有记录）" :image-size="70" /></template>
      </el-table>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  replaceKnowledge, listKnowledge, uploadKnowledgeBatch,
  getKnowledgeProgress, retryKnowledge,
  listKnowledgeVersions, deleteKnowledge,
} from '@/api/admin'

const docs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const processing = ref(false)
const form = reactive({ category: 'guide' })

// 与后端 MAX_UPLOAD_SIZE_MB / MAX_BATCH_FILES 保持一致
const MAX_MB = 50
const MAX_FILES = 20
const uploadRef = ref(null)
const replaceUploadRef = ref(null)

// 待入库队列：每个文件独立跟踪 id / 进度 / 状态
const queue = ref([])
let queueSeq = 0
let pollTimer = null

/**
 * 选择文件：追加到队列并做前置校验。
 * el-upload 在 auto-upload=false 时不会走 before-upload，只能在 on-change 里判断。
 */
function onFilesPicked(uploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return

  if (raw.size > MAX_MB * 1024 * 1024) {
    ElMessage.error(`${raw.name}：${(raw.size / 1024 / 1024).toFixed(1)}MB，超过 ${MAX_MB}MB 上限`)
    return
  }
  if (queue.value.filter((q) => q.status === 'waiting').length >= MAX_FILES) {
    ElMessage.warning(`一次最多 ${MAX_FILES} 个文件`)
    return
  }
  if (queue.value.some((q) => q.name === raw.name && q.status === 'waiting')) {
    ElMessage.warning(`${raw.name} 已在列表中`)
    return
  }
  queue.value.push({
    uid: ++queueSeq,
    raw,
    name: raw.name,
    size: raw.size,
    id: null,
    progress: 0,
    status: 'waiting',
    error: '',
  })
}

// 搜索 / 筛选（PRD 4.5：顶部搜索框 + 分类筛选）
const keyword = ref('')
const filterCat = ref('')

const waitingCount = computed(() => queue.value.filter((q) => q.status === 'waiting').length)

const filteredDocs = computed(() =>
  docs.value.filter((d) => {
    const kw = keyword.value.trim().toLowerCase()
    if (kw && !d.filename.toLowerCase().includes(kw)) return false
    if (filterCat.value && d.category !== filterCat.value) return false
    return true
  })
)

// 替换
const replaceVisible = ref(false)
const replacing = ref(false)
const replaceRow = ref(null)
const replaceForm = reactive({ category: 'guide', file: null })
const retryingId = ref(null)

function pickReplaceFile(uploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return
  if (raw.size > MAX_MB * 1024 * 1024) {
    ElMessage.error(`文件 ${(raw.size / 1024 / 1024).toFixed(1)}MB，超过 ${MAX_MB}MB 上限`)
    replaceForm.file = null
    replaceUploadRef.value?.clearFiles()
    return
  }
  replaceForm.file = raw
}

// 版本
const versionsVisible = ref(false)
const versions = ref([])

function catText(c) {
  return { template: '合同模板', guide: '审查指引', case: '历史判例', law: '法律法规' }[c] || c
}
function statusText(s) {
  return { chunking: '处理中', enabled: '已启用', failed: '失败' }[s] || s
}
function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

async function loadList(silent = false) {
  if (!silent) loading.value = true
  try {
    docs.value = await listKnowledge()
    syncListPoll()
  } finally { if (!silent) loading.value = false }
}

// 列表里只要还有「处理中」的文档，就静默轮询刷新进度；全部完成即停
let listTimer = null
function syncListPoll() {
  const need = docs.value.some((d) => d.status === 'chunking')
  if (need && !listTimer) {
    listTimer = setInterval(() => loadList(true), 3000)
  } else if (!need && listTimer) {
    clearInterval(listTimer)
    listTimer = null
  }
}

function openUpload() {
  queue.value = []
  dialogVisible.value = true
}

function closeUpload() {
  stopQueuePoll()
  dialogVisible.value = false
  queue.value = []
  loadList()
}

/**
 * 批量上传 + 进度轮询。
 *
 * 后端上传接口只做「落盘 + 建记录」立即返回（50 万字约 0.8 秒），
 * 真正的解析/向量化在后台跑，这里按 1 秒粒度轮询进度。
 */
async function handleUpload() {
  const pending = queue.value.filter((q) => q.status === 'waiting')
  if (!pending.length) return

  processing.value = true
  pending.forEach((q) => (q.status = 'uploading'))

  try {
    const res = await uploadKnowledgeBatch(pending.map((q) => q.raw), form.category)

    // 回填 id：按文件名匹配
    const byName = {}
    res.uploaded.forEach((d) => { byName[d.filename] = d })
    pending.forEach((q) => {
      const d = byName[q.name]
      if (d) {
        q.id = d.id
        q.status = 'chunking'
        q.progress = d.progress || 0
      }
    })

    res.rejected.forEach((x) => {
      const q = queue.value.find((i) => i.name === x.filename && i.status === 'uploading')
      if (q) { q.status = 'failed'; q.error = x.reason }
    })

    if (res.uploaded.length) {
      ElMessage.success(`已提交 ${res.uploaded.length} 个文件，后台入库中`)
      startQueuePoll()
    }
    if (res.rejected.length) {
      ElMessage.warning(`${res.rejected.length} 个文件被拒绝，见列表说明`)
    }
  } catch (e) {
    pending.forEach((q) => { q.status = 'waiting' })
  } finally {
    processing.value = false
  }
}

function startQueuePoll() {
  stopQueuePoll()
  pollTimer = setInterval(async () => {
    const active = queue.value.filter((q) => q.id && q.status === 'chunking')
    if (!active.length) { stopQueuePoll(); loadList(); return }
    for (const q of active) {
      try {
        const p = await getKnowledgeProgress(q.id)
        q.progress = p.progress
        if (p.status === 'enabled') {
          q.status = 'enabled'
          q.progress = 100
        } else if (p.status === 'failed') {
          q.status = 'failed'
          q.error = p.error_message || '入库失败'
        }
      } catch (e) { /* 轮询失败忽略，下一轮再试 */ }
    }
  }, 1000)
}

function stopQueuePoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function handleRetry(row) {
  retryingId.value = row.id
  try {
    await retryKnowledge(row.id)
    ElMessage.success('已重新提交入库')
    await loadList()
  } catch (e) { /* 已提示 */ } finally { retryingId.value = null }
}

function openReplace(row) {
  replaceRow.value = row
  replaceForm.category = row.category
  replaceForm.file = null
  replaceVisible.value = true
}

async function handleReplace() {
  if (!replaceForm.file || !replaceRow.value) return
  replacing.value = true
  try {
    await replaceKnowledge(replaceRow.value.id, replaceForm.file, replaceForm.category)
    ElMessage.success('已替换，后台入库中')
    replaceVisible.value = false
    await loadList()
  } catch (e) { /* 已提示 */ } finally { replacing.value = false }
}

async function openVersions(row) {
  versionsVisible.value = true
  versions.value = []
  try {
    versions.value = await listKnowledgeVersions(row.id)
  } catch (e) { /* 已提示 */ }
}

async function handleDelete(row) {
  await deleteKnowledge(row.id)
  ElMessage.success('已删除（向量库同步清除）')
  await loadList()
}

onMounted(() => loadList())
onUnmounted(() => {
  stopQueuePoll()
  if (listTimer) { clearInterval(listTimer); listTimer = null }
})
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.cur-file { color: #6b7280; font-size: 13px; }
.upload-hint { margin-top: 6px; font-size: 12px; color: #9ca3af; line-height: 1.6; }

/* 待入库队列 */
.queue { max-height: 260px; overflow-y: auto; padding: 4px 2px; }
.queue-item { padding: 8px 10px; border: 1px solid #eef0f3; border-radius: 6px; margin-bottom: 8px; }
.queue-item:last-child { margin-bottom: 0; }
.queue-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.q-name {
  flex: 1; font-size: 13px; color: #374151;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.q-size { font-size: 12px; color: #9ca3af; }
.q-err { margin-top: 4px; font-size: 12px; color: #ef4444; }
</style>
