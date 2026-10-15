<!-- frontend/src/views/admin/KnowledgeManage.vue — 知识库管理 -->
<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <el-icon><FolderOpened /></el-icon>
        <span>知识库管理</span>
        <el-button type="primary" style="margin-left:auto" @click="dialogVisible = true">
          <el-icon><Plus /></el-icon> 上传知识文档
        </el-button>
      </div>
    </template>

    <el-alert
      type="info" :closable="false" show-icon style="margin-bottom:16px"
      title="知识文档是审查报告的依据来源。支持 PDF / Word / 图片（OCR），仅限中文。上传后自动切块并向量化，删除将同步清除向量库。"
    />

    <el-table :data="docs" v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
      <el-table-column label="类别" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ catText(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'enabled' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="chunk_count" label="切块数" width="80" />
      <el-table-column label="上传时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
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
    <el-dialog v-model="dialogVisible" title="上传知识文档" width="480">
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
            drag :auto-upload="false" :limit="1"
            accept=".pdf,.docx,.png,.jpg,.jpeg"
            :on-change="(f) => (form.file = f.raw)"
            :on-remove="() => (form.file = null)"
          >
            <el-icon :size="32" color="#3b82f6"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!form.file" @click="handleUpload">
          {{ uploading ? '切块向量化中...' : '上传入库' }}
        </el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadKnowledge, listKnowledge, deleteKnowledge } from '@/api/admin'

const docs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const uploading = ref(false)
const form = reactive({ category: 'guide', file: null })

function catText(c) {
  return { template: '合同模板', guide: '审查指引', case: '历史判例', law: '法律法规' }[c] || c
}
function statusText(s) {
  return { chunking: '处理中', enabled: '已启用', failed: '失败' }[s] || s
}
function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

async function loadList() {
  loading.value = true
  try { docs.value = await listKnowledge() } finally { loading.value = false }
}

async function handleUpload() {
  if (!form.file) return
  uploading.value = true
  try {
    const d = await uploadKnowledge(form.file, form.category)
    ElMessage.success(`入库成功：${d.chunk_count} 个知识条目`)
    dialogVisible.value = false
    form.file = null
    await loadList()
  } catch (e) { /* 已提示 */ } finally { uploading.value = false }
}

async function handleDelete(row) {
  await deleteKnowledge(row.id)
  ElMessage.success('已删除（向量库同步清除）')
  await loadList()
}

onMounted(loadList)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
</style>
