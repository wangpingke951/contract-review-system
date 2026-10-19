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
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openReplace(row)">替换</el-button>
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
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
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
            drag :auto-upload="false" :limit="1"
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
            :on-change="(f) => (replaceForm.file = f.raw)"
            :on-remove="() => (replaceForm.file = null)"
          >
            <el-icon :size="32" color="#3b82f6"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽或点击上传</div>
          </el-upload>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import {
  uploadKnowledge, replaceKnowledge, listKnowledge,
  listKnowledgeVersions, deleteKnowledge,
} from '@/api/admin'

const docs = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const uploading = ref(false)
const form = reactive({ category: 'guide', file: null })

// 搜索 / 筛选（PRD 4.5：顶部搜索框 + 分类筛选）
const keyword = ref('')
const filterCat = ref('')

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

async function loadList() {
  loading.value = true
  try { docs.value = await listKnowledge() } finally { loading.value = false }
}

function openUpload() {
  form.file = null
  dialogVisible.value = true
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
    const d = await replaceKnowledge(replaceRow.value.id, replaceForm.file, replaceForm.category)
    ElMessage.success(`替换成功：${d.chunk_count} 个知识条目`)
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

onMounted(loadList)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.cur-file { color: #6b7280; font-size: 13px; }
</style>
