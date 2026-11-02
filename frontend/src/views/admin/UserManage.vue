<!-- frontend/src/views/admin/UserManage.vue — 用户与权限管理 -->
<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <el-icon><UserFilled /></el-icon>
        <span>用户与权限</span>
        <div class="toolbar">
          <el-input
            v-model="keyword" placeholder="搜索用户名" clearable
            style="width:200px" :prefix-icon="Search"
          />
          <el-button @click="load" :loading="loading">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </div>
    </template>

    <el-alert
      type="info" :closable="false" show-icon style="margin-bottom:16px"
      title="普通用户默认只能使用合同审查、追问与法律问答。勾选权限点后可获得对应管理能力，保存后立即生效，无需对方重新登录。"
    />

    <el-table :data="filteredUsers" v-loading="loading" style="width:100%">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="用户名" min-width="150">
        <template #default="{ row }">
          <span>{{ row.username }}</span>
          <el-tag v-if="row.role === 'admin'" size="small" type="warning" style="margin-left:6px">管理员</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '正常' : '已禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="已授予权限" min-width="280">
        <template #default="{ row }">
          <template v-if="row.role === 'admin'">
            <span class="muted">全部权限（管理员）</span>
          </template>
          <template v-else-if="row.permissions.length">
            <el-tag
              v-for="k in row.permissions" :key="k" size="small"
              type="success" effect="plain" style="margin-right:6px"
            >{{ permLabel(k) }}</el-tag>
          </template>
          <span v-else class="muted">无（仅基础功能）</span>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <template v-if="row.role === 'admin'">
            <span class="muted">—</span>
          </template>
          <template v-else>
            <el-button link type="primary" @click="openPerm(row)">分配权限</el-button>
            <el-button link @click="openReset(row)">重置密码</el-button>
            <el-button
              link :type="row.is_active ? 'danger' : 'success'"
              :loading="statusLoading === row.id" @click="toggleStatus(row)"
            >{{ row.is_active ? '禁用' : '启用' }}</el-button>
          </template>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无用户" :image-size="80" /></template>
    </el-table>

    <!-- 分配权限 -->
    <el-dialog v-model="permVisible" :title="`分配权限 · ${permRow?.username || ''}`" width="520">
      <el-alert
        type="warning" :closable="false" show-icon style="margin-bottom:14px"
        title="模型配置（含 API Key）不开放授权，仅管理员可访问。"
      />
      <el-checkbox-group v-model="permChecked" class="perm-list">
        <div v-for="p in catalog" :key="p.key" class="perm-item">
          <el-checkbox :label="p.key">
            <span class="perm-label">{{ p.label }}</span>
            <span class="perm-desc">{{ p.desc }}</span>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="permVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePerm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetVisible" :title="`重置密码 · ${resetRow?.username || ''}`" width="420">
      <el-form label-width="80px">
        <el-form-item label="新密码">
          <el-input v-model="newPassword" type="password" show-password placeholder="6–64 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetting" @click="savePassword">确认重置</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import {
  listUsers, listPermissionCatalog, updateUserPermissions,
  updateUserStatus, resetUserPassword,
} from '@/api/admin'

const users = ref([])
const catalog = ref([])
const loading = ref(false)
const keyword = ref('')

const permVisible = ref(false)
const permRow = ref(null)
const permChecked = ref([])
const saving = ref(false)

const resetVisible = ref(false)
const resetRow = ref(null)
const newPassword = ref('')
const resetting = ref(false)

const statusLoading = ref(null)

const filteredUsers = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return kw ? users.value.filter((u) => u.username.toLowerCase().includes(kw)) : users.value
})

function permLabel(key) {
  return catalog.value.find((p) => p.key === key)?.label || key
}
function fmtTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN', { hour12: false }) : '-'
}

async function load() {
  loading.value = true
  try {
    users.value = await listUsers()
    if (!catalog.value.length) catalog.value = await listPermissionCatalog()
  } finally { loading.value = false }
}

function openPerm(row) {
  permRow.value = row
  permChecked.value = [...row.permissions]
  permVisible.value = true
}

async function savePerm() {
  saving.value = true
  try {
    await updateUserPermissions(permRow.value.id, permChecked.value)
    ElMessage.success('权限已更新，立即生效')
    permVisible.value = false
    await load()
  } catch (e) { /* 已提示 */ } finally { saving.value = false }
}

function openReset(row) {
  resetRow.value = row
  newPassword.value = ''
  resetVisible.value = true
}

async function savePassword() {
  if (!newPassword.value) { ElMessage.warning('请输入新密码'); return }
  resetting.value = true
  try {
    await resetUserPassword(resetRow.value.id, newPassword.value)
    ElMessage.success('密码已重置，请通知对方使用新密码登录')
    resetVisible.value = false
  } catch (e) { /* 已提示 */ } finally { resetting.value = false }
}

async function toggleStatus(row) {
  statusLoading.value = row.id
  try {
    await updateUserStatus(row.id, !row.is_active)
    ElMessage.success(row.is_active ? '已禁用，该账号将立即无法登录' : '已启用')
    await load()
  } catch (e) { /* 已提示 */ } finally { statusLoading.value = null }
}

onMounted(load)
</script>

<style scoped>
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 700; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.muted { color: #9ca3af; font-size: 13px; }
.perm-list { display: flex; flex-direction: column; gap: 4px; }
.perm-item { padding: 6px 4px; border-bottom: 1px dashed #f0f2f5; }
.perm-item:last-child { border-bottom: none; }
.perm-label { font-weight: 600; margin-right: 8px; }
.perm-desc { color: #9ca3af; font-size: 12px; }
</style>
