<!-- frontend/src/views/Login.vue — 登录 / 注册 -->
<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <el-icon :size="36" color="#1e3a8a"><DocumentChecked /></el-icon>
        <h1>合同智能审查系统</h1>
        <p>RAG + 多模态 + 对话追问</p>
      </div>

      <el-tabs v-model="activeTab" stretch class="auth-tabs">
        <!-- ——— 登录 ——— -->
        <el-tab-pane label="登录" name="login">
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
        </el-tab-pane>

        <!-- ——— 注册 ——— -->
        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" :rules="regRules" ref="regFormRef" @submit.prevent="handleRegister">
            <el-form-item prop="username">
              <el-input
                v-model="regForm.username" placeholder="用户名（3–32 位，字母/数字/下划线/中文）"
                prefix-icon="User" size="large" maxlength="32"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input
                v-model="regForm.password" type="password" placeholder="密码（至少 6 位）"
                prefix-icon="Lock" show-password size="large" maxlength="64"
              />
            </el-form-item>
            <el-form-item prop="confirm">
              <el-input
                v-model="regForm.confirm" type="password" placeholder="确认密码"
                prefix-icon="Lock" show-password size="large" maxlength="64"
                @keyup.enter="handleRegister"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" size="large" :loading="regLoading" class="btn" @click="handleRegister">
                注 册
              </el-button>
            </el-form-item>
          </el-form>

          <p class="reg-tip">
            注册后为<strong>普通用户</strong>，可使用合同审查、追问、法律问答；
            知识库与模板管理需管理员权限。
          </p>
        </el-tab-pane>
      </el-tabs>

      <p class="footer-hint">合同智能审查系统 · 本系统输出仅供参考，不构成法律意见</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { login, register } from '@/api/auth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('login')

// —————————— 登录 ——————————
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

// —————————— 注册 ——————————
const regFormRef = ref(null)
const regLoading = ref(false)
const regForm = reactive({ username: '', password: '', confirm: '' })

const regRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度需为 3–32 位', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9_\u4e00-\u9fa5]+$/,
      message: '只能包含字母、数字、下划线或中文',
      trigger: 'blur',
    },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6–64 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (rule, value, cb) => {
        if (value !== regForm.password) cb(new Error('两次输入的密码不一致'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function handleRegister() {
  await regFormRef.value.validate()
  regLoading.value = true
  try {
    const res = await register({
      username: regForm.username,
      password: regForm.password,
      confirm_password: regForm.confirm,
    })
    // 后端注册成功即签发 token，直接进入系统
    userStore.login({
      access_token: res.access_token,
      role: res.role,
      username: res.username,
      userId: res.user_id,
    })
    ElMessage.success('注册成功，已自动登录')
    router.push('/')
  } catch (e) {
    // request.js 已提示
  } finally {
    regLoading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex; justify-content: center; align-items: center;
  background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
}
.login-card {
  width: 440px; padding: 36px 36px 28px;
  background: #fff; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,.2);
}
.brand { text-align: center; margin-bottom: 18px; }
.brand h1 { margin: 10px 0 4px; font-size: 22px; color: #1e3a8a; }
.brand p { margin: 0; color: #6b7280; font-size: 13px; }
.auth-tabs :deep(.el-tabs__header) { margin-bottom: 20px; }
.btn { width: 100%; }
.quick-access {
  display: flex; align-items: center; gap: 10px; justify-content: center;
}
.hint { color: #6b7280; font-size: 12px; }
.reg-tip {
  margin: 4px 0 0; padding: 10px 12px; border-radius: 8px;
  background: #f8fafc; color: #6b7280; font-size: 12px; line-height: 1.7;
}
.reg-tip strong { color: #1e3a8a; }
.footer-hint {
  text-align: center; color: #9ca3af; font-size: 11px; margin-top: 16px;
}
</style>
