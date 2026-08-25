<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2>我的企划</h2>
      <el-button type="primary" :icon="Plus" @click="router.push('/projects/new')">发布企划</el-button>
    </div>

    <el-tabs v-model="activeStatus" @tab-change="fetchProjects">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="草稿" name="draft" />
      <el-tab-pane label="招募中" name="open" />
      <el-tab-pane label="已过期" name="expired" />
      <el-tab-pane label="已转订单" name="converted" />
      <el-tab-pane label="已关闭" name="closed" />
    </el-tabs>

    <div class="project-card-list" v-loading="loading">
      <article v-for="row in projects" :key="row.id" class="project-card">
        <div class="project-card-content">
          <div class="project-card-info">
            <div class="project-card-head">
              <div><h3>{{ row.title }}</h3><span>{{ row.city || '地点待定' }}</span></div>
              <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </div>
            <div class="project-card-facts">
              <div><span>预算</span><strong>{{ formatBudget(row) }}</strong></div>
              <div><span>收到应邀</span><strong>{{ row.application_count }} 人</strong></div>
              <div><span>发布日期</span><strong>{{ formatDate(row.created_at) }}</strong></div>
            </div>
          </div>
          <el-image v-if="row.reference_images?.length" :src="row.reference_images[0]" fit="cover" class="project-card-cover" :alt="`${row.title} 示意图`" />
        </div>
        <div class="project-card-actions">
          <el-button :icon="View" @click="router.push(`/projects/${row.id}`)">详情</el-button>
          <el-button v-if="row.converted_order_id" type="primary" :icon="Tickets" @click="router.push(`/orders/${row.converted_order_id}`)">订单</el-button>
          <el-button v-if="row.status === 'open' || row.status === 'draft'" :icon="Close" @click="closeRow(row)">关闭</el-button>
          <el-button v-if="row.status === 'open' || row.status === 'draft' || row.status === 'expired'" :icon="Edit" @click="router.push(`/projects/${row.id}/edit`)">编辑</el-button>
        </div>
      </article>
    </div>

    <el-table v-if="false" :data="projects" v-loading="loading" stripe>
      <el-table-column prop="title" label="企划" min-width="220">
        <template #default="{ row }">
          <div class="project-title">{{ row.title }}</div>
          <div class="project-sub">{{ row.city }}</div>
        </template>
      </el-table-column>
      <el-table-column label="预算" width="160">
        <template #default="{ row }">{{ formatBudget(row) }}</template>
      </el-table-column>
      <el-table-column label="应邀" width="90">
        <template #default="{ row }">{{ row.application_count }} 人</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" :icon="View" @click="router.push(`/projects/${row.id}`)">详情</el-button>
          <el-button
            v-if="row.converted_order_id"
            size="small"
            type="primary"
            :icon="Tickets"
            @click="router.push(`/orders/${row.converted_order_id}`)"
          >
            订单
          </el-button>
          <el-button
            v-if="row.status === 'open' || row.status === 'draft'"
            size="small"
            :icon="Close"
            @click="closeRow(row)"
          >
            关闭
          </el-button>
          <el-button
            v-if="row.status === 'open' || row.status === 'draft' || row.status === 'expired'"
            size="small"
            :icon="Edit"
            @click="router.push(`/projects/${row.id}/edit`)"
          >
            编辑
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && projects.length === 0" description="暂无企划" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Eye as View, Pencil as Edit, Plus, Ticket as Tickets, X as Close } from 'lucide-vue-next'
import { closeProject, getMyProjects } from '../api/project'

const router = useRouter()
const activeStatus = ref('all')
const loading = ref(false)
const projects = ref([])

const fetchProjects = async () => {
  loading.value = true
  try {
    const params = activeStatus.value === 'all' ? {} : { status: activeStatus.value }
    const res = await getMyProjects(params)
    projects.value = res.data
  } finally {
    loading.value = false
  }
}

const closeRow = async (row) => {
  try {
    await ElMessageBox.confirm('关闭后不可继续接收应邀。', '关闭企划', { type: 'warning' })
  } catch {
    return
  }
  await closeProject(row.id, '客户关闭企划')
  ElMessage.info('企划已关闭')
  fetchProjects()
}

const statusLabel = (value) => ({ draft: '草稿', open: '招募中', converted: '已转订单', closed: '已关闭', cancelled: '已取消', expired: '已过期' }[value] || value)
const statusType = (value) => ({ draft: 'info', open: 'success', converted: 'primary', closed: 'info', cancelled: 'danger', expired: 'warning' }[value] || '')

const formatBudget = (row) => {
  if (row.budget_min && row.budget_max) return `¥${row.budget_min} - ¥${row.budget_max}`
  if (row.budget_min) return `¥${row.budget_min} 起`
  if (row.budget_max) return `¥${row.budget_max} 内`
  return '待沟通'
}

const formatDate = (value) => value
  ? new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  : '-'

onMounted(fetchProjects)
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

.project-card-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  min-height: 160px;
}

.project-card {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-5);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.project-card-cover {
  display: block;
  width: 210px;
  height: 150px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.project-card-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--space-5);
}

.project-card-info {
  min-width: 0;
}

.project-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.project-card-head h3 {
  margin: 0 0 var(--space-1);
  color: var(--color-ink);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.project-card-head span {
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}

.project-card-facts {
  display: grid;
  grid-template-columns: 1fr;
  border-top: 1px solid var(--color-divider);
  margin-top: var(--space-4);
}

.project-card-facts div {
  display: grid;
  gap: var(--space-1);
  grid-template-columns: 88px minmax(0, 1fr);
  align-items: baseline;
  padding: var(--space-2) 0;
  border-right: 0;
  border-bottom: 1px solid var(--color-divider);
}

.project-card-facts div:first-child {
  padding-left: 0;
}

.project-card-facts div:last-child {
  border-bottom: 0;
}

.project-card-facts span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.project-card-facts strong {
  color: var(--color-ink);
  font-size: var(--text-sm);
  font-weight: 600;
}

.project-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.project-card-actions .el-button {
  min-height: var(--tap-target-min);
  margin: 0;
}

@media (max-width: 900px) {
  .project-card-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .project-card-content {
    grid-template-columns: 1fr;
  }

  .project-card-cover {
    width: 100%;
    height: auto;
    aspect-ratio: 16 / 9;
    order: -1;
  }
}

@media (max-width: 640px) {
  .page-container {
    padding: var(--space-3);
  }

  .page-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .project-card-facts div,
  .project-card-facts div:first-child {
    padding: var(--space-2) 0;
  }

  .project-card-facts div:last-child {
    border-bottom: 0;
  }

  .project-card-actions .el-button {
    flex: 1 1 120px;
  }
}
</style>
