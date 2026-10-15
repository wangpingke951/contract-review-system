<!-- frontend/src/App.vue — 应用根组件 + 全局布局 -->
<template>
  <div id="app">
    <!-- 未登录：只显示 router-view -->
    <template v-if="!isLoggedIn">
      <router-view />
    </template>

    <!-- 已登录：侧边栏 + 顶栏 + 主内容区 -->
    <el-container v-else class="layout">
      <el-aside width="220px" class="sidebar">
        <div class="logo">
          <el-icon :size="24"><DocumentChecked /></el-icon>
          <span>合同智能审查</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          router
          background-color="#1e3a8a"
          text-color="#e2e8f0"
          active-text-color="#ffffff"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <span>首页 / 审查</span>
          </el-menu-item>
          <el-menu-item index="/assistant">
            <el-icon><ChatDotRound /></el-icon>
            <span>法律问答</span>
          </el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin/knowledge">
            <el-icon><FolderOpened /></el-icon>
            <span>知识库管理</span>
          </el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin/categories">
            <el-icon><Tag /></el-icon>
            <span>风险类别</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-icon :size="18"><User /></el-icon>
            <span>{{ userStore.username }}</span>
            <el-tag v-if="isAdmin" size="small" type="warning">管理员</el-tag>
          </div>
          <div class="header-right">
            <el-button link type="primary" @click="handleLogout">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-button>
          </div>
        </el-header>

        <el-main class="main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isLoggedIn = computed(() => userStore.isLoggedIn)
const isAdmin = computed(() => userStore.role === 'admin')
const activeMenu = computed(() => route.path)

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
    userStore.logout()
    router.push('/login')
  } catch { /* 取消 */ }
}
</script>

<style scoped>
.layout { height: 100vh; }
.sidebar {
  background: #1e3a8a;
  color: #fff;
  overflow-x: hidden;
}
.sidebar .logo {
  display: flex; align-items: center; gap: 10px;
  padding: 20px 20px;
  font-size: 16px; font-weight: 700;
  border-bottom: 1px solid rgba(255,255,255,.1);
}
.header {
  background: #fff; border-bottom: 1px solid #e5e7eb;
  display: flex; justify-content: space-between; align-items: center;
}
.header-left { display: flex; align-items: center; gap: 8px; }
.main { background: #f3f4f6; padding: 24px; }
</style>
