<!-- frontend/src/views/ReviewReport.vue — 审查报告三栏布局 -->
<template>
  <div class="report-page" v-loading="loading">
    <template v-if="review">
      <!-- 顶部概要条 -->
      <el-card class="summary-bar" shadow="never">
        <div class="summary-inner">
          <div class="summary-item">
            <span class="label">整体风险</span>
            <el-tag :type="riskType(review.overall_risk)" effect="dark" size="large">
              {{ riskText(review.overall_risk) }}
            </el-tag>
          </div>
          <div class="summary-item">
            <span class="label">风险项</span>
            <span class="num">{{ riskCount }}</span>
          </div>
          <div class="summary-item">
            <span class="label">知识库依据</span>
            <el-tag :type="review.has_rag ? 'success' : 'info'" size="small">
              {{ review.has_rag ? '已命中' : '未命中' }}
            </el-tag>
          </div>
          <div class="summary-item">
            <span class="label">生成时间</span>
            <span class="time">{{ fmtTime(review.generated_at) }}</span>
          </div>
          <div style="margin-left:auto; display:flex; gap:10px">
            <el-button @click="$router.push('/')">返回首页</el-button>
            <el-button type="primary" plain :loading="retrying" @click="handleRetry">重新审查</el-button>
          </div>
        </div>
        <el-alert
          v-if="!review.has_rag" type="info" :closable="false" show-icon
          title="本次审查未命中知识库依据，结果基于通用审查规则，可在管理后台上传知识文档提升准确性"
          style="margin-top:10px"
        />
      </el-card>

      <!-- 三栏主体 -->
      <el-row :gutter="16" class="main-area">
        <!-- 左：风险项 -->
        <el-col :span="7">
          <el-card shadow="never" class="col-card">
            <template #header><b>风险项（{{ riskCount }}）</b></template>
            <div class="risk-list">
              <div
                v-for="item in review.risk_items" :key="item.id"
                :class="['risk-card', item.is_positive ? 'positive' : item.risk_level]"
                @click="jumpTo(item)"
              >
                <div class="risk-head">
                  <el-tag v-if="item.is_positive" type="success" size="small">正面</el-tag>
                  <el-tag v-else :type="riskType(item.risk_level)" size="small">
                    {{ riskText(item.risk_level) }}
                  </el-tag>
                  <span class="cat">{{ item.category_name }}</span>
                </div>
                <div class="snippet">"{{ item.contract_snippet }}"</div>
                <div class="issue" v-if="item.issue">{{ item.issue }}</div>
                <div class="suggestion" v-if="item.suggestion">
                  <el-icon><EditPen /></el-icon> {{ item.suggestion }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 中：合同原文 -->
        <el-col :span="9">
          <el-card shadow="never" class="col-card">
            <template #header><b>合同原文</b></template>
            <div class="contract-text" ref="contractBox">
              <template v-for="(seg, i) in renderedSegments" :key="i">
                <mark v-if="seg.highlight" :class="['hl', activeClass]">{{ seg.text }}</mark>
                <span v-else>{{ seg.text }}</span>
              </template>
            </div>
          </el-card>
        </el-col>

        <!-- 右：对话追问 -->
        <el-col :span="8">
          <ChatPanel :review-id="review.id" class="chat-col" />
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReview, getReviewByContract, retryReview } from '@/api/review'
import { getContract } from '@/api/contract'
import ChatPanel from '@/components/ChatPanel.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const retrying = ref(false)
const review = ref(null)
const contract = ref(null)
const activeSnippet = ref('')
const contractBox = ref(null)

const riskCount = computed(() => review.value?.risk_items.filter((i) => !i.is_positive).length || 0)

const renderedSegments = computed(() => {
  const text = contract.value?.parsed_content || ''
  const snip = activeSnippet.value
  if (!snip || !text.includes(snip)) return [{ text, highlight: false }]
  const idx = text.indexOf(snip)
  return [
    { text: text.slice(0, idx), highlight: false },
    { text: snip, highlight: true },
    { text: text.slice(idx + snip.length), highlight: false },
  ]
})

const activeClass = computed(() => (activeSnippet.value ? 'active' : ''))

function riskText(r) {
  return { high: '高风险', medium: '中风险', low: '低风险' }[r] || r || '-'
}
function riskType(r) {
  return { high: 'danger', medium: 'warning', low: 'success' }[r] || 'info'
}
function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function jumpTo(item) {
  activeSnippet.value = item.contract_snippet || ''
  // 高亮片段在合同原文中滚动定位
  setTimeout(() => {
    const mark = contractBox.value?.querySelector('mark')
    mark?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, 50)
}

async function loadAll() {
  loading.value = true
  try {
    // 两种入口：/reviews/:id（报告ID）或 /reviews/contract/:contractId（合同ID）
    if (route.name === 'ReviewByContract') {
      const st = await getReviewByContract(route.params.contractId)
      review.value = await getReview(st.id)
    } else {
      review.value = await getReview(Number(route.params.id))
    }
    contract.value = await getContract(review.value.contract_id)
  } catch (e) {
    ElMessage.error('报告加载失败')
  } finally {
    loading.value = false
  }
}

async function handleRetry() {
  retrying.value = true
  try {
    review.value = await retryReview(review.value.id)
    contract.value = await getContract(review.value.contract_id)
    ElMessage.success('重新审查完成')
  } catch (e) { /* 已提示 */ } finally {
    retrying.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.report-page { height: calc(100vh - 130px); display: flex; flex-direction: column; }
.summary-bar { margin-bottom: 14px; }
.summary-inner { display: flex; align-items: center; gap: 28px; }
.summary-item { display: flex; align-items: center; gap: 8px; }
.summary-item .label { color: #6b7280; font-size: 13px; }
.summary-item .num { font-size: 20px; font-weight: 700; color: #dc2626; }
.summary-item .time { font-size: 13px; color: #374151; }
.main-area { flex: 1; min-height: 0; }
.col-card { height: 100%; display: flex; flex-direction: column; }
.col-card :deep(.el-card__body) { flex: 1; overflow-y: auto; min-height: 0; }

.risk-list { display: flex; flex-direction: column; gap: 12px; }
.risk-card {
  border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px;
  cursor: pointer; transition: box-shadow .15s, border-color .15s;
}
.risk-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }
.risk-card.high { border-left: 4px solid #dc2626; }
.risk-card.medium { border-left: 4px solid #f59e0b; }
.risk-card.low { border-left: 4px solid #16a34a; }
.risk-card.positive { border-left: 4px solid #16a34a; background: #f0fdf4; }
.risk-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.risk-head .cat { font-weight: 700; font-size: 14px; }
.risk-card .snippet {
  font-size: 13px; color: #374151; background: #f9fafb;
  padding: 6px 8px; border-radius: 6px; margin-bottom: 6px;
  font-style: italic;
}
.risk-card .issue { font-size: 13px; color: #6b7280; margin-bottom: 6px; }
.risk-card .suggestion {
  font-size: 13px; color: #065f46; display: flex; gap: 4px; align-items: flex-start;
}

.contract-text {
  font-size: 14px; line-height: 2; white-space: pre-wrap; word-break: break-all;
  color: #1f2329;
}
mark.hl { background: #fde68a; padding: 2px 0; }
mark.hl.active { background: #fbbf24; }

.chat-col { height: 100%; }
.chat-col :deep(.el-card__body) { height: 100%; padding: 0; }
</style>
