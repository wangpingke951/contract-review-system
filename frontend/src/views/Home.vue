<!-- frontend/src/views/Home.vue — 首页：合同上传 + 发起审查 + 历史列表 -->
<template>
  <div class="home">
    <el-row :gutter="20">
      <!-- 左：上传 -->
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
            :auto-upload="false"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="() => (file = null)"
            accept=".pdf,.docx,.png,.jpg,.jpeg"
          >
            <el-icon :size="40" color="#3b82f6"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传 <em>.pdf / .docx / .png / .jpg</em></div>
            <template #tip>
              <div class="el-upload__tip">单文件 ≤ 50MB · 仅支持中文合同 · 解析后自动预览</div>
            </template>
          </el-upload>

          <el-button
            type="primary" size="large" class="start-btn"
            :disabled="!file || uploading"
            :loading="uploading"
            @click="handleUploadAndReview"
          >
            {{ uploading ? '上传解析中...' : '上传并开始审查' }}
          </el-button>
        </el-card>
      </el-col>

      <!-- 右：历史 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Clock /></el-icon>
              <span>审查历史</span>
              <el-button link type="primary" style="margin-left:auto" @click="loadList">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>
          </template>

          <el-table :data="contracts" v-loading="loading" style="width:100%">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
            <el-table-column prop="file_type" label="类型" width="80" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="170">
              <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'review_done'" link type="primary"
                  @click="$router.push(`/reviews/contract/${row.id}`)"
                >查看报告</el-button>
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
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { uploadContract, listContracts, deleteContract } from '@/api/contract'
import { createReview } from '@/api/review'

const router = useRouter()
const file = ref(null)
const uploading = ref(false)
const loading = ref(false)
const contracts = ref([])

function onFileChange(uploadFile) {
  file.value = uploadFile.raw
}

function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
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

async function loadList() {
  loading.value = true
  try {
    const data = await listContracts()
    contracts.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function handleUploadAndReview() {
  if (!file.value) return
  uploading.value = true
  let contractId = null
  try {
    // 1) 上传 + 解析
    const c = await uploadContract(file.value)
    contractId = c.id
    ElMessage.success(`解析完成：${c.word_count} 字，${c.sections.length} 个章节`)
    // 2) 发起审查（同步执行，报告完成后跳转）
    const report = await createReview(contractId)
    ElMessage.success('审查完成')
    router.push(`/reviews/${report.id}`)
  } catch (e) {
    await loadList()
  } finally {
    uploading.value = false
  }
}

async function handleDelete(row) {
  await deleteContract(row.id)
  ElMessage.success('已删除')
  await loadList()
}

onMounted(loadList)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.upload-card { height: 100%; }
.start-btn { width: 100%; margin-top: 16px; }
.home { min-height: calc(100vh - 120px); }
</style>
