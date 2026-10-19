<!-- frontend/src/views/admin/TemplateManage.vue — 审查模板管理 -->
<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <el-icon><Collection /></el-icon>
        <span>审查模板</span>
        <span class="hint">不同合同类型可用不同审查维度</span>
        <el-button type="primary" style="margin-left:auto" @click="openCreate">
          <el-icon><Plus /></el-icon> 新建模板
        </el-button>
      </div>
    </template>

    <el-table :data="templates" v-loading="loading" style="width:100%">
      <el-table-column prop="name" label="模板名称" width="200">
        <template #default="{ row }">
          <b>{{ row.name }}</b>
          <el-tag v-if="row.is_default" size="small" type="success" style="margin-left:6px">默认</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '—' }}</template>
      </el-table-column>
      <el-table-column label="审查维度" width="300">
        <template #default="{ row }">
          <el-tag v-for="d in row.dimensions" :key="d.name" size="small" class="dim-tag">{{ d.name }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="!row.is_default" link @click="handleSetDefault(row)">设为默认</el-button>
          <el-popconfirm title="删除后不可恢复，确认？" width="220" @confirm="handleDelete(row)">
            <template #reference>
              <el-button link type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑模板' : '新建模板'" width="760">
      <el-form label-width="90px">
        <el-form-item label="模板名称">
          <el-input v-model="form.name" maxlength="64" show-word-limit placeholder="如：采购合同专项" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" maxlength="200" placeholder="这套模板关注什么" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
          <span class="tip">发起审查未指定模板时使用</span>
        </el-form-item>
        <el-form-item label="审查维度">
          <div class="dims">
            <div v-for="(d, i) in form.dimensions" :key="i" class="dim-row">
              <el-input v-model="d.name" placeholder="维度名（如：付款与账期）" style="width:180px" maxlength="64" />
              <el-input v-model="d.prompt" placeholder="审查要求（会作为检索与提示词依据）" style="flex:1" maxlength="300" />
              <el-button link type="danger" :disabled="form.dimensions.length <= 1" @click="removeDim(i)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addDim">
              <el-icon><Plus /></el-icon> 添加维度
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listTemplates, createTemplate, updateTemplate, deleteTemplate,
} from '@/api/template'

const templates = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(null)

const form = reactive({
  name: '',
  description: '',
  is_default: false,
  dimensions: [{ name: '', prompt: '' }],
})

async function load() {
  loading.value = true
  try { templates.value = await listTemplates() } finally { loading.value = false }
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    name: '', description: '', is_default: false,
    dimensions: [{ name: '', prompt: '' }],
  })
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    is_default: row.is_default,
    dimensions: row.dimensions.map((d) => ({ name: d.name, prompt: d.prompt })),
  })
  dialogVisible.value = true
}

function addDim() {
  form.dimensions.push({ name: '', prompt: '' })
}

function removeDim(i) {
  form.dimensions.splice(i, 1)
}

async function handleSave() {
  const dims = form.dimensions
    .map((d) => ({ name: (d.name || '').trim(), prompt: (d.prompt || '').trim() }))
    .filter((d) => d.name && d.prompt)
  if (!form.name.trim()) return ElMessage.warning('请填写模板名称')
  if (!dims.length) return ElMessage.warning('至少填写一个完整的审查维度')

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description,
      dimensions: dims,
      is_default: form.is_default,
    }
    if (editing.value) {
      await updateTemplate(editing.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await createTemplate(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e) { /* 已提示 */ } finally { saving.value = false }
}

async function handleSetDefault(row) {
  await updateTemplate(row.id, { is_default: true })
  ElMessage.success(`「${row.name}」已设为默认模板`)
  await load()
}

async function handleDelete(row) {
  await deleteTemplate(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.card-header .hint { font-weight: 400; font-size: 12px; color: #9ca3af; }
.dim-tag { margin: 2px 4px 2px 0; }
.dims { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.dim-row { display: flex; gap: 8px; align-items: center; }
.tip { margin-left: 10px; font-size: 12px; color: #9ca3af; }
</style>
