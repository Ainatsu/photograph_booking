<template>
  <div>
    <h3>用户管理</h3>
    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="display_name" label="昵称" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'photographer' ? 'warning' : 'info'" size="small">
            {{ row.role === 'photographer' ? '摄影师' : '客户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_banned ? 'danger' : 'success'" size="small">
            {{ row.is_banned ? '已封禁' : '正常' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" width="170">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            v-if="!row.is_banned"
            type="danger" size="small" @click="toggleBan(row)"
          >
            封禁
          </el-button>
          <el-button
            v-else
            type="success" size="small" @click="toggleBan(row)"
          >
            解封
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import api from '../utils/api'

const users = ref([])
const loading = ref(false)

const fetch = async () => {
  loading.value = true
  try {
    const res = await api.get('/users')
    users.value = res.data
  } finally {
    loading.value = false
  }
}

const toggleBan = async (user) => {
  const action = user.is_banned ? '解封' : '封禁'
  try {
    await ElMessageBox.confirm(`确定${action}用户 ${user.display_name}？`, '提示', { type: 'warning' })
  } catch { return }

  const url = user.is_banned ? `/users/${user.id}/unban` : `/users/${user.id}/ban`
  await api.put(url)
  fetch()
}

onMounted(fetch)
</script>

<style scoped>
h3 {
  color: #1A1A1A;
  font-weight: 700;
  margin: 0 0 16px 0;
}

:deep(.el-table) {
  --el-table-border-color: #D9D3CB;
  --el-table-header-bg-color: #FAF7F2;
  --el-table-tr-bg-color: #FFFDF9;
  --el-table-row-hover-bg-color: #EBF2EA;
  font-size: 0.875rem;
}

:deep(.el-table th.el-table__cell) {
  background: #FAF7F2;
  color: #6B6560;
  font-weight: 600;
  border-bottom: 1px solid #D9D3CB;
}

:deep(.el-table .el-table__cell) {
  border-bottom: 1px solid #E8E2DA;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: #FAF7F2;
}

:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: #EBF2EA;
}

:deep(.el-tag--success) {
  background: #EBF2EA;
  border-color: #2D5A27;
  color: #2D5A27;
}

:deep(.el-tag--danger) {
  background: #FDF2F2;
  border-color: #C53030;
  color: #C53030;
}

:deep(.el-tag--warning) {
  background: #FDF8ED;
  border-color: #8B6914;
  color: #8B6914;
}

:deep(.el-tag--info) {
  background: #FAF7F2;
  border-color: #D9D3CB;
  color: #6B6560;
}

:deep(.el-button--danger) {
  background: #C53030;
  border-color: #C53030;
}

:deep(.el-button--danger:hover) {
  background: #A02020;
  border-color: #A02020;
}

:deep(.el-button--success) {
  background: #2D5A27;
  border-color: #2D5A27;
}

:deep(.el-button--success:hover) {
  background: #3A6E33;
  border-color: #3A6E33;
}
</style>
