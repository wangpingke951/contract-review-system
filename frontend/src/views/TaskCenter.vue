<!-- frontend/src/views/TaskCenter.vue — 任务中心 -->
<template>
  <div class="task-page">
    <el-row :gutter="14" class="stat-row">
      <el-col :span="6" v-for="s in statCards" :key="s.key">
        <el-card shadow="never" :class="['stat', s.key]">
          <div class="stat-num">{{ summary[s.key] || 0 }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>审查任务</span>
          <div class="toolbar">
            <el-select v-model="templateId" clearable placeholder="默认模板" style="width:180px">
              <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-button
              type="primary" :loading="batching"
              :disabled="!selected.length"
              @click="handleBatch"
            >批量审查{{ selected.length ? `（${selected.length}）` : '' }}</el-button>
            <el-button :loading="loading" @click="load">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="tab">
        <el-tab-pane v-for="t in tabs" :key="t.key" :name="t.key" :label="`${t.label}（${summary[t.key] || 0}）`">
          <el-table
            :data="groups[t.key] || []"
            v-loading="loading"
            style="width:100%"
            row-key="contract_id"
            @selection-change="(rows) => (selected = rows.map((r) => r.contract_id))"
          >
            <el-table-column v-if="t.key === 'pending'" type="selection" width="46" reserve-selection />
            <el-table-column prop="filename" label="合同" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.filename }}
                <el-tag v-if="row.version > 1" size="small" effect="plain" style="margin-left:6px">v{{ row.version }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusType(row)" size="small">{{ statusText(row) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="风险" width="86">
              <template #default="{ row }">
                <el-tag v-if="row.overall_risk" :type="riskType(row.overall_risk)" size="small">
                  {{ riskText(row.overall_risk) }}
                </el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column label="模板" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.template_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="说明" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.finalized" class="ok">已定稿</span>
                <span v-else-if="row.error_message" class="err">{{ row.error_message }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="160">
              <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <!-- 审查完成：看报告 -->
                <el-button
                  v-if="row.review_status === 'done'" link type="primary"
                  @click="$router.push(`/reviews/${row.review_id}`)"
                >查看报告</el-button>

                <!-- 审查失败：重试 -->
                <el-button
                  v-else-if="row.review_status === 'failed'" link type="warning"
                  :loading="busyId === row.contract_id"
                  @click="retryOne(row)"
                >重试审查</el-button>

                <!-- 已解析待审查 -->
                <el-button
                  v-else-if="row.contract_status === 'parsed'" link type="success"
                  :loading="busyId === row.contract_id"
                  @click="reviewOne(row)"
                >开始审查</el-button>

                <!-- 解析失败：重解析 / 重传 -->
                <template v-else-if="row.contract_status === 'parsing_failed'">
                  <el-button
                    link type="warning" :loading="busyId === row.contract_id"
                    @click="reparseOne(row)"
                  >重新解析</el-button>
                  <el-button link type="primary" @click="triggerReplace(row)">重新上传</el-button>
                </template>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="`暂无${t.label}任务`" :image-size="70" /></template>
          </el-table>

          <!-- 解析失败时给出可操作提示 -->
          <el-alert
            v-if="t.key === 'parse_failed' && (groups.parse_failed || []).length"
            type="info" :closable="false" show-icon style="margin-top:10px"
            title="解析失败常见原因：文件损坏 / 非中文合同 / 图片未配置多模态模型。可先点「重新解析」（配置已修复时无需重传），仍失败则「重新上传」替换文件。"
          />
        </el-tab-pane>
      </el-tabs>

      <input
        ref="replaceInput" type="file" style="display:none"
        accept=".pdf,.docx,.png,.jpg,.jpeg" @change="handleReplaceFile"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTasks, batchReview } from '@/api/task'
import { listTemplates } from '@/api/template'
import { createReview, retryReview } from '@/api/review'
import { reparseContract, replaceContractFile } from '@/api/contract'

const tabs = [
  { key: 'running', label: '进行中' },
  { key: 'failed', label: '失败' },
  { key: 'pending', label: '待审查' },
  { key: 'parse_failed', label: '解析失败' },
]
const statCards = [
  { key: 'running', label: '进行中' },
  { key: 'failed', label: '审查失败' },
  { key: 'pending', label: '待审查' },
  { key: 'parse_failed', label: '解析失败' },
]

const tab = ref('pending')
const groups = ref({})
const summary = ref({})
const loading = ref(false)
const batching = ref(false)
const selected = ref([])
const templates = ref([])
const templateId = ref(null)
let timer = null

function statusType(row) {
  if (row.review_status === 'running' || row.contract_status === 'reviewing') return 'warning'
  if (row.review_status === 'failed' || row.contract_status === 'review_failed') return 'danger'
  if (row.contract_status === 'parsing_failed') return 'info'
  if (row.review_status === 'done') return 'success'
  return ''
}
function statusText(row) {
  if (row.review_status === 'running') return '审查中'
  if (row.review_status === 'done') return '已审查'
  if (row.review_status === 'failed') return '审查失败'
  if (row.contract_status === 'parsing_failed') return '解析失败'
  if (row.contract_status === 'parsed') return '待审查'
  return row.contract_status
}
function riskText(r) { return { high: '高', medium: '中', low: '低' }[r] || r }
function riskType(r) { return { high: 'danger', medium: 'warning', low: 'success' }[r] || 'info' }
function fmtTime(t) { return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-' }

async function load(opts = {}) {
  const silent = opts.silent === true
  if (!silent) loading.value = true
  try {
    const res = await getTasks()
    summary.value = res.summary
    groups.value = {
      running: res.running, failed: res.failed,
      pending: res.pending, parse_failed: res.parse_failed,
    }
    syncPoll()
  } finally {
    if (!silent) loading.value = false
  }
}

/**
 * 只有存在「进行中」任务时才轮询，且轮询走静默模式（不亮 loading 遮罩）。
 * 没有进行中任务时完全停止，避免页面一直闪。
 */
function syncPoll() {
  const needPoll = (summary.value.running || 0) > 0
  if (needPoll && !timer) {
    timer = setInterval(() => load({ silent: true }), 5000)
  } else if (!needPoll && timer) {
    clearInterval(timer)
    timer = null
  }
}

async function handleBatch() {
  if (!selected.value.length) return
  batching.value = true
  try {
    const res = await batchReview(selected.value, templateId.value)
    ElMessage.success(`已提交 ${res.accepted.length} 份${res.skipped.length ? `，跳过 ${res.skipped.length} 份` : ''}`)
    if (res.skipped.length) {
      ElMessage.warning(res.skipped.map((s) => `#${s.contract_id}：${s.reason}`).join('；'))
    }
    selected.value = []
    await load()
  } finally { batching.value = false }
}

async function reviewOne(row) {
  busyId.value = row.contract_id
  try {
    await createReview(row.contract_id, templateId.value)
    ElMessage.success('已提交审查')
    await load()
  } catch (e) { /* 已提示 */ } finally {
    busyId.value = null
  }
}

// —————————— 失败重试 ——————————
const busyId = ref(null)

async function retryOne(row) {
  busyId.value = row.contract_id
  try {
    await retryReview(row.review_id)
    ElMessage.success('已重新提交审查')
    await load()
  } catch (e) { /* 已提示 */ } finally {
    busyId.value = null
  }
}

async function reparseOne(row) {
  busyId.value = row.contract_id
  try {
    const res = await reparseContract(row.contract_id)
    if (res.status === 'parsed') {
      ElMessage.success(`重新解析成功（${res.word_count} 字）`)
    } else {
      ElMessage.warning(res.parse_error || '仍然解析失败，建议重新上传文件')
    }
    await load()
  } catch (e) { /* 已提示 */ } finally {
    busyId.value = null
  }
}

// —————————— 解析失败后重新上传 ——————————
const replaceInput = ref(null)
const replaceTarget = ref(null)

function triggerReplace(row) {
  replaceTarget.value = row
  replaceInput.value?.click()
}

async function handleReplaceFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !replaceTarget.value) return
  const id = replaceTarget.value.contract_id
  busyId.value = id
  try {
    const res = await replaceContractFile(id, file)
    if (res.status === 'parsed') {
      ElMessage.success(`已替换并解析成功（${res.word_count} 字）`)
    } else {
      ElMessage.warning(res.parse_error || '替换后仍解析失败')
    }
    await load()
  } catch (err) { /* 已提示 */ } finally {
    busyId.value = null
    replaceTarget.value = null
  }
}

onMounted(async () => {
  await load()
  try { templates.value = await listTemplates() } catch (e) { /* ignore */ }
})
onUnmounted(() => {
  if (timer) { clearInterval(timer); timer = null }
})
</script>

<style scoped>
.task-page { display: flex; flex-direction: column; gap: 14px; }
.stat-row .stat { text-align: center; }
.stat .stat-num { font-size: 26px; font-weight: 800; color: #1f2937; line-height: 1.2; }
.stat.running .stat-num { color: #d97706; }
.stat.failed .stat-num { color: #dc2626; }
.stat.pending .stat-num { color: #2563eb; }
.stat.parse_failed .stat-num { color: #6b7280; }
.stat .stat-label { font-size: 12px; color: #6b7280; margin-top: 2px; }
.card-header { display: flex; align-items: center; gap: 10px; font-weight: 700; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.ok { color: #16a34a; font-size: 12px; }
.err { color: #dc2626; font-size: 12px; }
.muted { color: #c0c4cc; }
</style>
