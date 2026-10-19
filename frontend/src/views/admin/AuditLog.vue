<!-- frontend/src/views/admin/AuditLog.vue — 操作审计日志（PRD 5.3） -->
<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <el-icon><Tickets /></el-icon>
        <span>操作审计日志</span>
        <div class="toolbar">
          <el-select v-model="action" clearable placeholder="全部动作" style="width:170px" @change="reload">
            <el-option v-for="(label, key) in ACTIONS" :key="key" :label="label" :value="key" />
          </el-select>
          <el-button :loading="loading" @click="reload">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      type="info" :closable="false" show-icon style="margin-bottom:14px"
      title="记录合同上传/删除、发起与重新审查、风险项处置、知识库上传/替换/删除，以及管理员登录。"
    />

    <el-table :data="items" v-loading="loading" style="width:100%">
      <el-table-column label="时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="actor_name" label="操作人" width="110" />
      <el-table-column label="动作" width="140">
        <template #default="{ row }">
          <el-tag size="small" :type="actionType(row.action)">{{ actionText(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="对象" width="130">
        <template #default="{ row }">
          <span v-if="row.target_type">{{ row.target_type }} #{{ row.target_id ?? '-' }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="detail" label="详情" min-width="240" show-overflow-tooltip />
      <template #empty><el-empty description="暂无日志" :image-size="80" /></template>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load"
      />
    </div>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listAuditLogs } from '@/api/admin'

const ACTIONS = {
  'contract.upload': '上传合同',
  'contract.delete': '删除合同',
  'review.create': '发起审查',
  'review.retry': '重新审查',
  'review.item_handle': '处置风险项',
  'knowledge.upload': '上传知识文档',
  'knowledge.replace': '替换知识文档',
  'knowledge.delete': '删除知识文档',
  'auth.login': '登录',
}

const items = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(30)
const action = ref('')
const loading = ref(false)

function actionText(a) { return ACTIONS[a] || a }
function actionType(a) {
  if (a.startsWith('knowledge')) return 'success'
  if (a.startsWith('review')) return 'warning'
  if (a === 'auth.login') return 'info'
  if (a.endsWith('delete')) return 'danger'
  return ''
}
function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

async function load() {
  loading.value = true
  try {
    const res = await listAuditLogs({ page: page.value, size: size.value, action: action.value })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.pager { display: flex; justify-content: flex-end; margin-top: 14px; }
</style>
