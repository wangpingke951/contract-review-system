<!-- frontend/src/views/Login.vue — 登录页（完整实现） -->
<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <el-icon :size="36" color="#1e3a8a"><DocumentChecked /></el-icon>
        <h1>合同智能审查系统</h1>
        <p>RAG + 多模态 + 对话追问</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            show-password
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" class="btn" @click="handleLogin">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <el-divider />

      <div class="quick-access">
        <span class="hint">开发环境快速入口：</span>
        <el-button size="small" @click="quickLogin('user')">普通用户</el-button>
        <el-button size="small" type="warning" @click="quickLogin('admin')">管理员</el-button>
      </div>

      <p class="footer-hint">Phase 3 骨架 · Mock 登录返回 JWT · 真实 DB 查询留后续 Phase</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { login, loginAdmin } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    // Phase 3 用 /login（返回 mock token），后续 Phase 补真实 DB 查询
    const data = await login(form)
    userStore.login({
      access_token: data.access_token,
      role: data.role,
      username: form.username,
    })
    ElMessage.success('登录成功')
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    // request.js 已弹 ElMessage
  } finally {
    loading.value = false
  }
}

async function quickLogin(role) {
  loading.value = true
  try {
    const creds = role === 'admin'
      ? { username: 'admin', password: 'admin123' }
      : { username: 'user', password: 'user123' }
    const data = await login(creds)
    userStore.login({
      access_token: data.access_token,
      role: data.role,
      username: creds.username,
    })
    ElMessage.success(`已登录为 ${role === 'admin' ? '管理员' : '普通用户'}`)
    router.push('/')
  } catch (e) { /* 已提示 */ } finally { loading.value = false }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex; justify-content: center; align-items: center;
  background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
}
.login-card {
  width: 420px; padding: 40px 36px;
  background: #fff; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,.2);
}
.brand { text-align: center; margin-bottom: 28px; }
.brand h1 { margin: 10px 0 4px; font-size: 22px; color: #1e3a8a; }
.brand p { margin: 0; color: #6b7280; font-size: 13px; }
.btn { width: 100%; }
.quick-access {
  display: flex; align-items: center; gap: 10px; justify-content: center;
}
.hint { color: #6b7280; font-size: 12px; }
.footer-hint {
  text-align: center; color: #9ca3af; font-size: 11px; margin-top: 16px;
}
</style>
