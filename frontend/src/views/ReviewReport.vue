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

      <!-- 三栏主体：5 / 13 / 6，中间原文为主，右侧辅助窄一些 -->
      <el-row :gutter="16" class="main-area">
        <!-- 左：风险项（目录导航） -->
        <el-col :span="5">
          <el-card shadow="never" class="col-card">
            <template #header><b>风险项（{{ riskCount }}）</b></template>
            <div class="risk-list">
              <div
                v-for="item in review.risk_items" :key="item.id"
                :class="['risk-card', item.is_positive ? 'positive' : item.risk_level, { active: activeId === item.id }]"
                @click="focusItem(item)"
              >
                <div class="risk-head">
                  <el-tag v-if="item.is_positive" type="success" size="small">正面</el-tag>
                  <el-tag v-else :type="riskType(item.risk_level)" size="small">
                    {{ riskText(item.risk_level) }}
                  </el-tag>
                  <span class="cat">{{ item.category_name }}</span>
                </div>
                <div class="snippet">"{{ item.contract_snippet }}"</div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 中：合同原文（风险就地批注） -->
        <el-col :span="13">
          <el-card shadow="never" class="col-card">
            <template #header>
              <div class="contract-header">
                <b>合同原文</b>
                <span class="hint">风险已就地标注，点击文中标签查看说明</span>
              </div>
            </template>
            <div class="contract-text" ref="contractBox">
              <template v-for="(seg, i) in renderedSegments" :key="i"><span v-if="!seg.items.length">{{ seg.text }}</span><template v-else><mark :class="['hl', 'hl-' + topLevel(seg.items)]" @click="focusItem(seg.items[0])">{{ seg.text }}</mark><span class="anno-chips"><span v-for="it in seg.items" :key="it.id" :data-rid="it.id" :class="['chip', chipClass(it), { open: activeId === it.id }]" @click="focusItem(it)">{{ it.is_positive ? '正面发现' : riskText(it.risk_level) }} · {{ it.category_name }}</span></span><template v-for="it in seg.items" :key="'d' + it.id"><div v-if="activeId === it.id" :class="['anno-detail', chipClass(it)]">
                <div class="anno-title">
                  <el-tag v-if="it.is_positive" type="success" size="small">正面</el-tag>
                  <el-tag v-else :type="riskType(it.risk_level)" size="small">{{ riskText(it.risk_level) }}</el-tag>
                  <b>{{ it.category_name }}</b>
                </div>
                <p v-if="it.issue" class="anno-issue"><span class="k">问题</span>{{ it.issue }}</p>
                <p v-if="it.suggestion" class="anno-sug"><span class="k">建议</span>{{ it.suggestion }}</p>
              </div></template></template></template>

              <div v-if="unlocatedItems.length" class="unlocated">
                <div class="unlocated-title">以下条目未能在原文中精确定位（多为“条款缺失”类，原文无对应片段）</div>
                <div v-for="it in unlocatedItems" :key="'u' + it.id" :class="['anno-detail', chipClass(it)]">
                  <div class="anno-title">
                    <el-tag v-if="it.is_positive" type="success" size="small">正面</el-tag>
                    <el-tag v-else :type="riskType(it.risk_level)" size="small">{{ riskText(it.risk_level) }}</el-tag>
                    <b>{{ it.category_name }}</b>
                  </div>
                  <p v-if="it.contract_snippet" class="anno-quote">「{{ it.contract_snippet }}」</p>
                  <p v-if="it.issue" class="anno-issue"><span class="k">问题</span>{{ it.issue }}</p>
                  <p v-if="it.suggestion" class="anno-sug"><span class="k">建议</span>{{ it.suggestion }}</p>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 右：对话追问 -->
        <el-col :span="6" class="chat-col-wrap">
          <ChatPanel :review-id="review.id" class="chat-col" />
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
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
const activeId = ref(null)
const contractBox = ref(null)

const riskCount = computed(() => review.value?.risk_items.filter((i) => !i.is_positive).length || 0)

// —————————— 风险项在合同原文中的定位 ——————————
/** 在原文中查找片段位置；对 LLM 输出做多级容错匹配 */
function locate(text, snippet) {
  const raw = (snippet || '').trim()
  if (!raw || !text) return null

  // 1) 原样匹配
  let idx = text.indexOf(raw)
  if (idx >= 0) return { start: idx, end: idx + raw.length }

  // 2) 去掉包裹的引号 / 书名号
  const unquoted = raw.replace(/^[“”"'「」《》]+/, '').replace(/[“”"'「」《》]+$/, '').trim()
  if (unquoted && unquoted !== raw) {
    idx = text.indexOf(unquoted)
    if (idx >= 0) return { start: idx, end: idx + unquoted.length }
  }

  // 3) 去掉省略号（LLM 常把长句缩写成 "……"）
  const base = unquoted.length >= 6 ? unquoted : raw
  const stripped = base.replace(/[.。…]{2,}/g, '')
  if (stripped.length >= 8) {
    idx = text.indexOf(stripped)
    if (idx >= 0) return { start: idx, end: idx + stripped.length }

    // 4) 取最长前缀（≥8 字）匹配，尽量定位
    const head = stripped.slice(0, 20)
    for (let n = head.length; n >= 8; n--) {
      idx = text.indexOf(head.slice(0, n))
      if (idx >= 0) return { start: idx, end: idx + n }
    }
  }
  return null
}

/** 定位 + 区间合并（重叠片段合并为一处，多条目共用一个高亮） */
const located = computed(() => {
  const text = contract.value?.parsed_content || ''
  const items = review.value?.risk_items || []
  const hits = []
  const unlocated = []

  for (const item of items) {
    const pos = locate(text, item.contract_snippet)
    if (pos) hits.push({ item, ...pos })
    else unlocated.push(item)
  }

  hits.sort((a, b) => a.start - b.start || a.end - b.end)
  const merged = []
  for (const h of hits) {
    const last = merged[merged.length - 1]
    if (last && h.start < last.end) {
      last.end = Math.max(last.end, h.end)
      if (!last.items.includes(h.item)) last.items.push(h.item)
    } else {
      merged.push({ start: h.start, end: h.end, items: [h.item] })
    }
  }
  return { text, merged, unlocated }
})

const renderedSegments = computed(() => {
  const { text, merged } = located.value
  const segs = []
  let cursor = 0
  for (const m of merged) {
    if (m.start > cursor) segs.push({ text: text.slice(cursor, m.start), items: [] })
    segs.push({ text: text.slice(m.start, m.end), items: m.items })
    cursor = m.end
  }
  if (cursor < text.length) segs.push({ text: text.slice(cursor), items: [] })
  return segs
})

const unlocatedItems = computed(() => located.value.unlocated)
const activeClass = computed(() => (activeSnippet.value ? 'active' : ''))

/** 一组条目里最严重的等级（用于高亮配色） */
function topLevel(items) {
  const rank = { high: 3, medium: 2, low: 1 }
  let best = null
  for (const it of items) {
    if (it.is_positive) continue
    if (!best || (rank[it.risk_level] || 0) > (rank[best] || 0)) best = it.risk_level
  }
  return best || 'positive'
}

function chipClass(it) {
  return it.is_positive ? 'lv-positive' : `lv-${it.risk_level || 'medium'}`
}

function focusItem(item) {
  if (!item) return
  activeSnippet.value = item.contract_snippet || ''
  activeId.value = item.id
  nextTick(() => {
    const el = contractBox.value?.querySelector(`[data-rid="${item.id}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

function riskText(r) {
  return { high: '高风险', medium: '中风险', low: '低风险' }[r] || r || '-'
}
function riskType(r) {
  return { high: 'danger', medium: 'warning', low: 'success' }[r] || 'info'
}
function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
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
  border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px;
  cursor: pointer; transition: box-shadow .15s, border-color .15s;
}
.risk-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }
.risk-card.high { border-left: 4px solid #dc2626; }
.risk-card.medium { border-left: 4px solid #f59e0b; }
.risk-card.low { border-left: 4px solid #16a34a; }
.risk-card.positive { border-left: 4px solid #16a34a; background: #f0fdf4; }
.risk-card.active { border-color: #93c5fd; background: #f5faff; box-shadow: 0 0 0 2px rgba(59,130,246,.22); }
.risk-head { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.risk-head .cat { font-weight: 700; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-card .snippet {
  font-size: 12px; color: #374151; background: #f9fafb;
  padding: 5px 7px; border-radius: 6px; margin-bottom: 5px;
  font-style: italic;
}
.risk-card .issue { font-size: 12px; color: #6b7280; margin-bottom: 5px; }
.risk-card .suggestion {
  font-size: 12px; color: #065f46; display: flex; gap: 4px; align-items: flex-start;
}

.contract-header { display: flex; align-items: baseline; gap: 10px; }
.contract-header .hint { font-size: 12px; color: #9ca3af; font-weight: 400; }

.contract-text {
  font-size: 14px; line-height: 2; white-space: pre-wrap; word-break: break-word;
  color: #1f2329;
}

/* ——— 原文内联批注 ——— */
mark.hl { border-radius: 3px; padding: 1px 2px; cursor: pointer; }
mark.hl.hl-high { background: #fecaca; box-shadow: inset 0 -2px 0 #dc2626; }
mark.hl.hl-medium { background: #fde68a; box-shadow: inset 0 -2px 0 #f59e0b; }
mark.hl.hl-low, mark.hl.hl-positive { background: #bbf7d0; box-shadow: inset 0 -2px 0 #16a34a; }
mark.hl:hover { filter: brightness(.95); }

.anno-chips { display: inline-flex; flex-wrap: wrap; gap: 6px; margin: 0 2px 0 8px; }
.chip {
  display: inline-block; font-size: 12px; line-height: 1.5;
  padding: 1px 8px; border-radius: 999px; cursor: pointer;
  border: 1px solid transparent; white-space: nowrap;
  transition: box-shadow .15s, transform .15s;
}
.chip.lv-high { background: #fee2e2; color: #b91c1c; border-color: #fca5a5; }
.chip.lv-medium { background: #fef3c7; color: #b45309; border-color: #fcd34d; }
.chip.lv-low, .chip.lv-positive { background: #dcfce7; color: #15803d; border-color: #86efac; }
.chip:hover { transform: translateY(-1px); }
.chip.open { box-shadow: 0 0 0 2px rgba(59,130,246,.4); }

.anno-detail {
  margin: 8px 0 12px; padding: 10px 12px; border-radius: 8px;
  font-size: 13px; line-height: 1.75; white-space: normal;
  border-left: 3px solid #e5e7eb; background: #f9fafb;
}
.anno-detail.lv-high { border-left-color: #dc2626; background: #fef7f7; }
.anno-detail.lv-medium { border-left-color: #f59e0b; background: #fffcf5; }
.anno-detail.lv-low, .anno-detail.lv-positive { border-left-color: #16a34a; background: #f7fdf9; }
.anno-title { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.anno-detail .k { display: inline-block; min-width: 34px; color: #9ca3af; margin-right: 6px; }
.anno-quote { margin: 0 0 4px; color: #6b7280; font-style: italic; }
.anno-issue { margin: 0 0 4px; color: #374151; }
.anno-sug { margin: 0; color: #065f46; }

.unlocated { margin-top: 20px; padding-top: 14px; border-top: 1px dashed #e5e7eb; }
.unlocated-title { font-size: 12px; color: #9ca3af; margin-bottom: 10px; }

.chat-col-wrap { display: flex; align-items: center; justify-content: center; height: 100%; }
.chat-col { width: 100%; }
</style>
