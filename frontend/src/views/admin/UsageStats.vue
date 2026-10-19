<!-- frontend/src/views/admin/UsageStats.vue — LLM 用量统计 -->
<template>
  <div class="usage-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <el-icon><DataLine /></el-icon>
          <span>LLM 用量统计</span>
          <div class="toolbar">
            <el-radio-group v-model="days" @change="load">
              <el-radio-button :value="1">今日</el-radio-button>
              <el-radio-button :value="7">近 7 天</el-radio-button>
              <el-radio-button :value="30">近 30 天</el-radio-button>
            </el-radio-group>
            <el-button :loading="loading" @click="load">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16" class="cards">
        <el-col :span="8">
          <div class="metric">
            <div class="metric-num">{{ stats.total_calls || 0 }}</div>
            <div class="metric-label">模型调用次数</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="metric">
            <div class="metric-num">{{ (stats.total_tokens || 0).toLocaleString() }}</div>
            <div class="metric-label">Token 消耗（非流式可统计）</div>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="metric">
            <div class="metric-num">{{ avgDuration }} <span class="unit">ms</span></div>
            <div class="metric-label">平均耗时</div>
          </div>
        </el-col>
      </el-row>

      <el-table :data="stats.by_scene || []" style="width:100%;margin-top:18px">
        <el-table-column label="场景" width="160">
          <template #default="{ row }">
            <el-tag size="small">{{ sceneText(row.scene) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="calls" label="调用次数" width="120" />
        <el-table-column label="Token" width="140">
          <template #default="{ row }">{{ (row.tokens || 0).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="平均耗时" width="140">
          <template #default="{ row }">{{ row.avg_duration_ms }} ms</template>
        </el-table-column>
        <el-table-column label="占比" min-width="200">
          <template #default="{ row }">
            <div class="bar-wrap">
              <div class="bar" :style="{ width: pct(row.calls) }"></div>
              <span class="pct">{{ pct(row.calls) }}</span>
            </div>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无调用记录" :image-size="70" /></template>
      </el-table>

      <el-alert
        type="info" :closable="false" show-icon style="margin-top:16px"
        title="流式调用（追问）的 token 需服务端开启 include_usage 才可统计，当前只记录次数与耗时。"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getUsageStats } from '@/api/admin'

const days = ref(7)
const loading = ref(false)
const stats = ref({ total_calls: 0, total_tokens: 0, by_scene: [], daily: [] })

const avgDuration = computed(() => {
  const rows = stats.value.by_scene || []
  const calls = rows.reduce((s, r) => s + r.calls, 0)
  if (!calls) return 0
  const total = rows.reduce((s, r) => s + r.avg_duration_ms * r.calls, 0)
  return Math.round(total / calls)
})

function sceneText(s) {
  return { review: '合同审查', chat: '报告追问', assistant: '法律问答', vision: '图片识别' }[s] || s
}
function pct(calls) {
  const total = stats.value.total_calls || 0
  if (!total) return '0%'
  return `${Math.round((calls / total) * 100)}%`
}

async function load() {
  loading.value = true
  try { stats.value = await getUsageStats(days.value) } finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.cards { margin-top: 4px; }
.metric { background: #f8fafc; border: 1px solid #eef2f7; border-radius: 8px; padding: 18px; text-align: center; }
.metric-num { font-size: 26px; font-weight: 800; color: #1e3a8a; }
.metric-num .unit { font-size: 12px; font-weight: 400; color: #94a3b8; }
.metric-label { font-size: 12px; color: #6b7280; margin-top: 4px; }
.bar-wrap { display: flex; align-items: center; gap: 8px; }
.bar { height: 8px; background: linear-gradient(90deg, #3b82f6, #93c5fd); border-radius: 4px; min-width: 2px; }
.pct { font-size: 12px; color: #6b7280; }
</style>
