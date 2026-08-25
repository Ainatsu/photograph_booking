<template>
  <div class="admin-layout">
    <el-container>
      <el-header class="admin-header">
        <span class="logo">管理后台</span>
        <el-button text @click="logout">退出登录</el-button>
      </el-header>
      <el-container>
        <el-aside width="200px" class="admin-aside">
          <el-menu
            :default-active="route.path"
            router
            class="side-menu"
          >
            <el-menu-item index="/dashboard">
              <el-icon><ChartNoAxesCombined /></el-icon>
              <span>仪表盘</span>
            </el-menu-item>
            <el-menu-item index="/users">
              <el-icon><UserRound /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item index="/photographer-applications">
              <el-icon><FileCheck2 /></el-icon>
              <span>摄影师审核</span>
            </el-menu-item>
            <el-menu-item index="/orders">
              <el-icon><ReceiptText /></el-icon>
              <span>订单管理</span>
            </el-menu-item>
            <el-menu-item index="/finance">
              <el-icon><WalletCards /></el-icon>
              <span>财务记录</span>
            </el-menu-item>
            <el-menu-item index="/disputes">
              <el-icon><TriangleAlert /></el-icon>
              <span>争议仲裁</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main class="admin-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ChartNoAxesCombined, FileCheck2, ReceiptText, TriangleAlert, UserRound, WalletCards } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const logout = () => {
  localStorage.removeItem('admin_token')
  router.push('/login')
}
</script>

<style>
html, body, #app { margin: 0; height: 100%; }
</style>

<style scoped>
.admin-layout {
  height: 100vh;
  font-family: serif;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #FFFDF9;
  color: #1A1A1A;
  padding: 0 20px;
  border-bottom: 1px solid #D9D3CB;
  height: 56px;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  color: #1A1A1A;
}

.admin-header :deep(.el-button) {
  color: #6B6560;
}

.admin-header :deep(.el-button:hover) {
  color: #2D5A27;
}

.admin-aside {
  background: #FFFDF9;
  border-right: 1px solid #D9D3CB;
}

.side-menu {
  border-right: none;
}

.side-menu :deep(.el-menu-item) {
  color: #6B6560;
  border-radius: 0;
  margin: 2px 8px;
  min-height: 44px;
  line-height: 44px;
}

.side-menu :deep(.el-menu-item:hover) {
  background: #EBF2EA;
  color: #1A1A1A;
}

.side-menu :deep(.el-menu-item.is-active) {
  color: #2D5A27;
  background: #EBF2EA;
  border-radius: 4px;
}

.side-menu :deep(.el-menu-item .el-icon) {
  color: inherit;
}

.admin-main {
  padding: 24px;
  background: #FAF7F2;
  min-height: 100%;
}

@media (max-width: 768px) {
  .admin-aside {
    width: 160px !important;
  }
  .admin-main {
    padding: 16px;
  }
}
</style>
