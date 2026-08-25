<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2>我的应邀</h2>
      <el-button type="primary" :icon="Search" @click="router.push('/projects')">浏览企划</el-button>
    </div>

    <el-tabs v-model="activeStatus" @tab-change="fetchApplications">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="已提交" name="submitted" />
      <el-tab-pane label="被选中" name="selected" />
      <el-tab-pane label="未选中" name="rejected" />
      <el-tab-pane label="已撤回" name="withdrawn" />
    </el-tabs>

    <el-table :data="applications" v-loading="loading" stripe>
      <el-table-column label="企划" min-width="240">
        <template #default="{ row }">
          <div class="project-title">{{ row.project?.title || `企划 #${row.project_id}` }}</div>
          <div class="project-sub">
            {{ row.project?.city || '-' }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="客户预算" width="150">
        <template #default="{ row }">{{ formatProjectBudget(row.project) }}</template>
      </el-table-column>
      <el-table-column label="我的报价" width="120">
        <template #default="{ row }">¥{{ row.price_quote }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230">
        <template #default="{ row }">
          <el-button size="small" :icon="View" @click="router.push(`/projects/${row.project_id}`)">详情</el-button>
          <el-button
            v-if="row.status === 'selected' && row.project?.converted_order_id"
            size="small"
            type="primary"
            :icon="Tickets"
            @click="router.push(`/orders/${row.project.converted_order_id}`)"
          >
            订单
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && applications.length === 0" description="暂无应邀" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Eye as View, Search, Ticket as Tickets } from 'lucide-vue-next'
import { getMyApplications } from '../api/project'
import api from '../utils/api'

const router = useRouter()
const activeStatus = ref('all')
const loading = ref(false)
const applications = ref([])

const fetchApplications = async () => {
  if (!(await ensurePhotographer())) return
  loading.value = true
  try {
    const params = activeStatus.value === 'all' ? {} : { status: activeStatus.value }
    const res = await getMyApplications(params)
    applications.value = res.data
  } finally {
    loading.value = false
  }
}

const ensurePhotographer = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录')
    router.push('/login')
    return false
  }
  try {
    const res = await api.get('/users/me', { skipErrorHandler: true })
    if (res.data.role !== 'photographer') {
      ElMessage.warning('仅摄影师可以查看我的应邀')
      router.push('/projects')
      return false
    }
  } catch {
    router.push('/login')
    return false
  }
  return true
}

const statusLabel = (value) => ({ submitted: '已提交', selected: '被选中', rejected: '未选中', withdrawn: '已撤回' }[value] || value)
const statusType = (value) => ({ submitted: 'warning', selected: 'success', rejected: 'info', withdrawn: 'info' }[value] || '')
const formatDate = (value) => value ? new Date(value).toLocaleString() : '-'

const formatProjectBudget = (project) => {
  if (!project) return '-'
  if (project.budget_min && project.budget_max) return `¥${project.budget_min} - ¥${project.budget_max}`
  if (project.budget_min) return `¥${project.budget_min} 起`
  if (project.budget_max) return `¥${project.budget_max} 内`
  return '待沟通'
}

onMounted(fetchApplications)
</script>

<style scoped>
.page-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-5);
  color: var(--color-ink);
  font-family: var(--font-sans);
}

.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.page-toolbar h2 {
  margin: 0;
  color: var(--color-ink);
  font-size: var(--text-2xl);
}

.project-title {
  color: var(--color-ink);
  font-weight: 600;
  line-height: var(--leading-normal);
}

.project-sub {
  margin-top: var(--space-1);
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
}

@media (max-width: 640px) {
  .page-container {
    padding: var(--space-3);
  }

  .page-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
