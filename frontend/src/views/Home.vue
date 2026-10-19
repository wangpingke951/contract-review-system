<!-- frontend/src/views/Home.vue — 首页：批量上传 → 逐个解析 → 预览确认 → 发起审查 -->
<template>
  <div class="home">
    <el-row :gutter="20">
      <!-- 左：上传 + 本次处理的文件 -->
      <el-col :span="10">
        <el-card class="upload-card">
          <template #header>
            <div class="card-header">
              <el-icon><UploadFilled /></el-icon>
              <span>上传合同并发起审查</span>
            </div>
          </template>

          <el-upload
            drag
            multiple
            :auto-upload="false"
            :show-file-list="false"
            :on-change="onFileChange"
            accept=".pdf,.docx,.png,.jpg,.jpeg"
          >
            <el-icon :size="40" color="#3b82f6"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传 <em>.pdf / .docx / .png / .jpg</em></div>
            <template #tip>
              <div class="el-upload__tip">
                单个 ≤ 50MB · 一次最多 {{ MAX_FILES }} 个 · 仅支持中文合同 · 有文件即可逐个独立解析
              </div>
            </template>
          </el-upload>

          <el-button
            type="primary" size="large" class="start-btn"
            :disabled="!pendingCount || uploading"
            :loading="uploading"
            @click="handleParseAll"
          >
            {{ uploading ? `解析中（${parsedCount}/${queue.length}）` : `开始解析（${pendingCount} 个文件）` }}
          </el-button>

          <!-- 本次上传的文件列表 -->
          <div v-if="queue.length" class="file-queue">
            <div class="fq-head">
              <span>本次文件（{{ queue.length }}）</span>
              <el-button link type="info" size="small" @click="clearQueue">全部清空</el-button>
            </div>

            <div v-for="item in queue" :key="item.uid" class="file-item">
              <div class="fi-head">
                <span class="fi-name" :title="item.name">{{ item.name }}</span>
                <el-tag :type="statusTagType(item.status)" size="small">{{ statusLabel(item.status) }}</el-tag>
              </div>

              <div class="fi-meta">
                <span>{{ fmtSize(item.size) }}</span>
                <span v-if="item.status === 'parsed'">· {{ item.wordCount }} 字 · {{ item.sectionCount }} 个章节</span>
              </div>

              <el-alert
                v-if="item.error" :title="item.error" type="error"
                :closable="false" show-icon class="fi-err"
              />

              <div class="fi-actions">
                <el-button
                  v-if="item.status === 'parsed'" link type="primary" size="small"
                  @click="openPreview(item)"
                >预览</el-button>
                <el-button
                  v-if="item.status === 'parsed'" link type="success" size="small"
                  :loading="reviewingId === item.contractId"
                  @click="startReview(item)"
                >开始审查</el-button>
                <el-button
                  v-if="item.status === 'failed'" link type="warning" size="small"
                  @click="item.status = 'pending'; item.error = ''"
                >重新解析</el-button>
                <el-button v-if="item.status !== 'uploading'" link type="danger" size="small" @click="removeItem(item)">
                  移除
                </el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右：历史 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Clock /></el-icon>
              <span>审查历史</span>
              <el-select
                v-model="templateId" size="small" clearable placeholder="默认模板"
                style="width:150px;margin-left:auto;margin-right:8px"
              >
                <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
              <el-button link type="primary" @click="loadList">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>

          <el-table :data="contracts" v-loading="loading" style="width:100%">
            <el-table-column label="文件名" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.filename }}</span>
                <el-tag v-if="row.version > 1" size="small" effect="plain" style="margin-left:6px">v{{ row.version }}</el-tag>
                <el-tooltip v-if="row.parse_error" :content="row.parse_error" placement="top">
                  <el-icon color="#ef4444" class="err-icon"><WarningFilled /></el-icon>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column prop="file_type" label="类型" width="76" />
            <el-table-column label="状态" width="104">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="追问" width="64">
              <template #default="{ row }">
                <span v-if="row.follow_up_count" class="follow-up">{{ row.follow_up_count }} 条</span>
                <span v-else class="follow-up muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="150">
              <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="228" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'review_done'" link type="primary"
                  @click="$router.push(`/reviews/contract/${row.id}`)"
                >查看报告</el-button>
                <el-button
                  v-if="row.status === 'parsed'" link type="success"
                  :loading="reviewingId === row.id"
                  @click="startReview({ contractId: row.id, name: row.filename })"
                >开始审查</el-button>
                <el-button link @click="triggerNewVersion(row)" title="上传这份合同的新版本">
                  新版本
                </el-button>
                <el-popconfirm title="确认删除该合同？" @confirm="handleDelete(row)">
                  <template #reference>
                    <el-button link type="danger">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无合同，上传第一份开始审查" :image-size="80" />
            </template>
          </el-table>

          <input
            ref="versionInput" type="file" style="display:none"
            accept=".pdf,.docx,.png,.jpg,.jpeg" @change="handleVersionFile"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 解析结果预览确认 -->
    <el-dialog
      v-model="previewVisible"
      :title="`解析预览 · ${previewItem?.name || ''}`"
      width="920px" top="5vh" class="preview-dialog"
    >
      <div v-loading="previewLoading" class="preview-body">
        <div class="preview-stats">
          <el-tag type="success" size="small">解析成功</el-tag>
          <span>共 <b>{{ previewDetail?.parsed_content?.length || 0 }}</b> 字</span>
          <span>{{ previewSections.length }} 个章节</span>
        </div>

        <el-alert
          type="info" :closable="false" show-icon
          title="请确认解析结果是否正确。确认无误后点击「开始审查」，系统将结合知识库生成风险报告。"
          class="preview-tip"
        />

        <el-collapse v-if="previewSections.length" class="preview-sections">
          <el-collapse-item v-for="(s, i) in previewSections" :key="i" :name="i">
            <template #title>
              <span class="sec-title">{{ s.title }}</span>
              <span class="sec-len">{{ (s.content || '').length }} 字</span>
            </template>
            <div class="sec-content">{{ s.content }}</div>
          </el-collapse-item>
        </el-collapse>

        <div class="preview-full">
          <div class="pf-title">合同全文</div>
          <div class="pf-text">{{ previewDetail?.parsed_content }}</div>
        </div>
      </div>

      <template #footer>
        <el-button @click="previewVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="reviewingId === previewItem?.contractId"
          @click="startReview(previewItem, true)"
        >确认无误，开始审查</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { uploadContract, listContracts, deleteContract, getContract, uploadNewVersion } from '@/api/contract'
import { listTemplates } from '@/api/template'
import { createReview } from '@/api/review'

const router = useRouter()

// 单批最多处理文件数（PRD 4.1 假设值）
const MAX_FILES = 5

const queue = ref([])          // 本次上传的文件：[{ uid, raw, name, size, status, error, contractId, wordCount, sectionCount }]
const uploading = ref(false)
const reviewingId = ref(null)  // 正在发起审查的 contractId
const loading = ref(false)
const contracts = ref([])

// 审查模板（发起审查时使用，留空走默认模板）
const templates = ref([])
const templateId = ref(null)

// 上传新版本
const versionInput = ref(null)
const versionTarget = ref(null)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewItem = ref(null)
const previewDetail = ref(null)

const pendingCount = computed(() => queue.value.filter((f) => f.status === 'pending').length)
const parsedCount = computed(() => queue.value.filter((f) => f.status !== 'pending').length)
const previewSections = computed(() => previewDetail.value?.parsed_sections || [])

// —————————— 文件选择 ——————————
function onFileChange(uploadFile) {
  if (uploadFile.status !== 'ready') return
  if (queue.value.length >= MAX_FILES) {
    ElMessage.warning(`一次最多处理 ${MAX_FILES} 个文件`)
    return
  }
  const size = uploadFile.raw?.size || uploadFile.size || 0
  if (queue.value.some((f) => f.name === uploadFile.name && f.size === size)) {
    ElMessage.warning(`「${uploadFile.name}」已在列表中`)
    return
  }
  queue.value.push({
    uid: uploadFile.uid,
    raw: uploadFile.raw,
    name: uploadFile.name,
    size,
    status: 'pending',
    error: '',
    contractId: null,
    wordCount: 0,
    sectionCount: 0,
  })
}

function removeItem(item) {
  queue.value = queue.value.filter((f) => f.uid !== item.uid)
}

function clearQueue() {
  queue.value = []
}

// —————————— 逐个独立解析 ——————————
async function handleParseAll() {
  const targets = queue.value.filter((f) => f.status === 'pending')
  if (!targets.length) return

  uploading.value = true
  let ok = 0
  let failed = 0

  // 顺序解析：单个失败不影响其余文件（后端失败也是 200 + status=parsing_failed）
  for (const item of targets) {
    item.status = 'uploading'
    item.error = ''
    try {
      const res = await uploadContract(item.raw)
      item.contractId = res.id
      item.wordCount = res.word_count || 0
      item.sectionCount = (res.sections || []).length
      if (res.status === 'parsed') {
        item.status = 'parsed'
        ok += 1
      } else {
        item.status = 'failed'
        item.error = res.parse_error || '解析失败，请检查文件内容'
        failed += 1
      }
    } catch (e) {
      item.status = 'failed'
      item.error = e?.response?.data?.message || '上传失败，请重试'
      failed += 1
    }
  }

  uploading.value = false
  await loadList()

  if (ok && !failed) ElMessage.success(`${ok} 个文件解析完成，可预览后发起审查`)
  else if (ok && failed) ElMessage.warning(`解析完成 ${ok} 个，失败 ${failed} 个`)
  else if (failed) ElMessage.error(`${failed} 个文件解析失败，请查看原因`)
}

// —————————— 预览 ——————————
async function openPreview(item) {
  previewItem.value = item
  previewVisible.value = true
  previewDetail.value = null
  previewLoading.value = true
  try {
    previewDetail.value = await getContract(item.contractId)
  } catch {
    ElMessage.error('预览加载失败')
  } finally {
    previewLoading.value = false
  }
}

// —————————— 发起审查 ——————————
async function startReview(item, closePreview = false) {
  const contractId = item?.contractId
  if (!contractId || reviewingId.value) return

  reviewingId.value = contractId
  try {
    const report = await createReview(contractId, templateId.value)
    ElMessage.success('已提交审查，正在后台执行')
    if (closePreview) previewVisible.value = false
    // 该文件已进入报告页，从本次列表移除
    queue.value = queue.value.filter((f) => f.contractId !== contractId)
    router.push(`/reviews/${report.id}`)
  } catch {
    await loadList()
  } finally {
    reviewingId.value = null
  }
}

// —————————— 展示辅助 ——————————
function fmtSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function statusLabel(s) {
  return { pending: '待解析', uploading: '解析中', parsed: '待审查', failed: '解析失败' }[s] || s
}

function statusTagType(s) {
  return { pending: 'info', uploading: 'warning', parsed: 'success', failed: 'danger' }[s] || 'info'
}

function statusText(s) {
  return {
    uploaded: '已上传', parsing: '解析中', parsed: '已解析',
    parsing_failed: '解析失败', reviewing: '审查中',
    review_done: '已审查', review_failed: '审查失败',
  }[s] || s
}

function statusType(s) {
  if (s === 'review_done' || s === 'parsed') return 'success'
  if (s.includes('failed')) return 'danger'
  if (s === 'parsing' || s === 'reviewing') return 'warning'
  return 'info'
}

// —————————— 历史 ——————————
async function loadList() {
  loading.value = true
  try {
    const data = await listContracts()
    contracts.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function handleDelete(row) {
  await deleteContract(row.id)
  ElMessage.success('已删除')
  await loadList()
}

onMounted(async () => {
  await loadList()
  try { templates.value = await listTemplates() } catch (e) { /* ignore */ }
})

// —————————— 上传新版本 ——————————
function triggerNewVersion(row) {
  versionTarget.value = row
  versionInput.value?.click()
}

async function handleVersionFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !versionTarget.value) return
  try {
    const res = await uploadNewVersion(versionTarget.value.id, file)
    ElMessage.success(`已上传 v${res.version}，可发起审查后做版本对比`)
    await loadList()
  } catch (err) {
    // request.js 已提示
  } finally {
    versionTarget.value = null
  }
}
</script>

<style scoped>
.follow-up { font-size: 13px; color: #2563eb; font-weight: 600; }
.follow-up.muted { color: #c0c4cc; font-weight: 400; }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.upload-card { height: 100%; }
.start-btn { width: 100%; margin-top: 16px; }
.home { min-height: calc(100vh - 120px); }

/* —— 本次文件列表 —— */
.file-queue { margin-top: 18px; border-top: 1px solid #f0f0f0; padding-top: 14px; }
.fq-head {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 13px; color: #6b7280; margin-bottom: 10px;
}
.file-item {
  border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 10px 12px; margin-bottom: 10px;
}
.fi-head { display: flex; align-items: center; gap: 8px; }
.fi-name {
  flex: 1; min-width: 0; font-size: 13px; font-weight: 500; color: #1f2329;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.fi-meta { font-size: 12px; color: #9ca3af; margin-top: 4px; display: flex; gap: 6px; }
.fi-err { margin-top: 8px; }
.file-item :deep(.el-alert__title) { font-size: 12px; line-height: 1.6; }
.fi-actions { display: flex; justify-content: flex-end; gap: 4px; margin-top: 8px; }

.err-icon { margin-left: 4px; vertical-align: middle; }

/* —— 预览对话框 —— */
.preview-dialog :deep(.el-dialog__body) { padding-top: 8px; }
.preview-body { max-height: 66vh; overflow-y: auto; }
.preview-stats { display: flex; align-items: center; gap: 14px; font-size: 13px; color: #6b7280; }
.preview-stats b { color: #1f2329; }
.preview-tip { margin: 12px 0; }
.preview-sections { margin-bottom: 16px; }
.sec-title { font-size: 13px; font-weight: 500; }
.sec-len { font-size: 12px; color: #9ca3af; margin-left: 10px; }
.sec-content {
  font-size: 13px; line-height: 1.9; color: #374151;
  white-space: pre-wrap; word-break: break-word;
}
.preview-full { border-top: 1px dashed #e5e7eb; padding-top: 12px; }
.pf-title { font-size: 13px; font-weight: 700; margin-bottom: 8px; }
.pf-text {
  font-size: 13px; line-height: 1.9; color: #1f2329;
  white-space: pre-wrap; word-break: break-word;
  background: #f9fafb; border-radius: 8px; padding: 12px;
  max-height: 320px; overflow-y: auto;
}
</style>
