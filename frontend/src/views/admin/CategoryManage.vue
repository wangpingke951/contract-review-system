<!-- frontend/src/views/admin/CategoryManage.vue — 风险类别管理 -->
<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <el-icon><CollectionTag /></el-icon>
        <span>风险类别管理</span>
        <el-button type="primary" style="margin-left:auto" @click="dialogVisible = true">
          <el-icon><Plus /></el-icon> 新增类别
        </el-button>
      </div>
    </template>

    <el-alert
      type="info" :closable="false" show-icon style="margin-bottom:16px"
      title="风险类别用于审查报告分类。至少保留 1 个；删除类别不影响历史报告（报告保留类别名快照）。"
    />

    <el-table :data="cats" v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="类别名称" min-width="200" />
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-popconfirm
            :title="cats.length <= 1 ? '至少保留 1 个类别' : `确认删除「${row.name}」？`"
            @confirm="handleDelete(row)"
          >
            <template #reference>
              <el-button link type="danger" :disabled="cats.length <= 1">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="新增风险类别" width="420">
      <el-input v-model="newName" placeholder="输入类别名称，如：数据安全" maxlength="64" show-word-limit />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" :disabled="!newName.trim()" @click="handleAdd">确认新增</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listCategories, addCategory, deleteCategory } from '@/api/admin'

const cats = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const adding = ref(false)
const newName = ref('')

function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

async function loadList() {
  loading.value = true
  try { cats.value = await listCategories() } finally { loading.value = false }
}

async function handleAdd() {
  adding.value = true
  try {
    await addCategory(newName.value.trim())
    ElMessage.success('新增成功')
    dialogVisible.value = false
    newName.value = ''
    await loadList()
  } catch (e) { /* 已提示 */ } finally { adding.value = false }
}

async function handleDelete(row) {
  if (cats.value.length <= 1) {
    ElMessage.warning('至少保留 1 个风险类别')
    return
  }
  await deleteCategory(row.id)
  ElMessage.success('已删除')
  await loadList()
}

onMounted(loadList)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
</style>
