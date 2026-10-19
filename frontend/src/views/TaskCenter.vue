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
            @selection-change="(rows) => (selected = rows.map((r) => r.contract_id))"
          >
            <el-table-column v-if="t.key === 'pending'" type="selection" width="46" />
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
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.review_id" link type="primary" @click="$router.push(`/reviews/${row.review_id}`)">
                  查看报告
                </el-button>
                <el-button v-else-if="row.contract_status === 'parsed'" link type="success" @click="reviewOne(row)">
                  开始审查
                </el-button>
              </template>
            </el-table-column>
            <template #empty><el-empty :description="`暂无${t.label}任务`" :image-size="70" /></template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getTasks, batchReview } from '@/api/task'
import { listTemplates } from '@/api/template'
import { createReview } from '@/api/review'

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

async function load() {
  loading.value = true
  try {
    const res = await getTasks()
    summary.value = res.summary
    groups.value = {
      running: res.running, failed: res.failed,
      pending: res.pending, parse_failed: res.parse_failed,
    }
  } finally { loading.value = false }
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
  await createReview(row.contract_id, templateId.value)
  ElMessage.success('已提交审查')
  await load()
}

onMounted(async () => {
  await load()
  try { templates.value = await listTemplates() } catch (e) { /* ignore */ }
  timer = setInterval(load, 5000)  // 进行中任务自动刷新
})
onUnmounted(() => { if (timer) clearInterval(timer) })
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
