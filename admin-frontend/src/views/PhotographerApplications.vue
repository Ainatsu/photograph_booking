<template>
  <div class="photographer-applications-page">
    <div class="page-head">
      <h3>摄影师审核</h3>
      <el-radio-group v-model="statusFilter" size="small" @change="fetchApplications">
        <el-radio-button value="pending">待审核</el-radio-button>
        <el-radio-button value="approved">已通过</el-radio-button>
        <el-radio-button value="rejected">未通过</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="applications" v-loading="loading" row-key="id" stripe>
      <el-table-column label="申请人" min-width="220">
        <template #default="{ row }">
          <div class="applicant">
            <el-avatar :size="36" :src="getFullUrl(row.user_avatar_url)">
              {{ (row.user_display_name || '?')[0] }}
            </el-avatar>
            <div>
              <div class="applicant-name">{{ row.user_display_name || `用户 #${row.user_id}` }}</div>
              <div class="muted">{{ row.user_email || '-' }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="资料" min-width="320">
        <template #default="{ row }">
          <div class="info-lines">
            <div><span>地区</span>{{ row.location || '-' }}</div>
            <div><span>设备</span>{{ row.equipment || '-' }}</div>
            <div class="intro">{{ row.profile_intro || '-' }}</div>
            <div class="tags">
              <el-tag v-for="style in row.styles || []" :key="style" size="small" effect="plain">
                {{ style }}
              </el-tag>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="作品" min-width="260">
        <template #default="{ row }">
          <div v-if="row.portfolio_refs?.length" class="portfolio-list">
            <div v-for="work in row.portfolio_refs" :key="work.id || work.url" class="portfolio-item">
              <el-image
                :src="getFullUrl(work.thumbnail_url || work.url)"
                :preview-src-list="portfolioPreviewList(row)"
                fit="cover"
                preview-teleported
              />
              <span>{{ work.title || '作品' }}</span>
            </div>
          </div>
          <span v-else class="muted">无作品</span>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="审核备注" min-width="160">
        <template #default="{ row }">{{ row.review_note || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="170" fixed="right">
        <template #default="{ row }">
          <el-button
            type="success"
            size="small"
            :disabled="row.status === 'approved'"
            @click="reviewApplication(row, 'approve')"
          >
            通过
          </el-button>
          <el-button
            type="danger"
            size="small"
            :disabled="row.status === 'rejected'"
            @click="reviewApplication(row, 'reject')"
          >
            拒绝
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../utils/api'

const applications = ref([])
const loading = ref(false)
const statusFilter = ref('pending')

const getFullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

const statusLabel = (status) => ({
  pending: '待审核',
  approved: '已通过',
  rejected: '未通过',
}[status] || status)

const statusType = (status) => ({
  pending: 'warning',
  approved: 'success',
  rejected: 'danger',
}[status] || 'info')

const formatDate = (value) => value ? new Date(value).toLocaleString() : '-'

const portfolioPreviewList = (row) => (
  row.portfolio_refs || []
).map((work) => getFullUrl(work.url || work.thumbnail_url)).filter(Boolean)

const fetchApplications = async () => {
  loading.value = true
  try {
    const params = { limit: 100 }
    if (statusFilter.value !== 'all') {
      params.status = statusFilter.value
    }
    const res = await api.get('/photographer-applications', { params })
    applications.value = res.data
  } finally {
    loading.value = false
  }
}

const getReviewNote = async (action) => {
  if (action === 'reject') {
    const result = await ElMessageBox.prompt('填写拒绝原因', '拒绝申请', {
      inputType: 'textarea',
      inputPlaceholder: '例如：作品数量不足或资料不完整',
      confirmButtonText: '拒绝',
      cancelButtonText: '取消',
      type: 'warning',
    })
    return result.value || ''
  }

  await ElMessageBox.confirm('确认通过该摄影师申请？', '审核确认', {
    type: 'success',
    confirmButtonText: '通过',
    cancelButtonText: '取消',
  })
  return ''
}

const reviewApplication = async (row, action) => {
  let reviewNote = ''
  try {
    reviewNote = await getReviewNote(action)
  } catch {
    return
  }

  await api.put(`/photographer-applications/${row.id}/${action}`, {
    review_note: reviewNote,
  })
  ElMessage.success(action === 'approve' ? '已通过申请' : '已拒绝申请')
  fetchApplications()
}

onMounted(fetchApplications)
</script>

<style scoped>
.photographer-applications-page {
  background: #FFFDF9;
  padding: 20px;
  border-radius: 4px;
  border: 1px solid #D9D3CB;
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.page-head h3 {
  margin: 0;
  color: #1A1A1A;
  font-weight: 700;
}

:deep(.el-radio-group) {
  --el-radio-button-border-color: #D9D3CB;
}

:deep(.el-radio-button__inner) {
  background: #FAF7F2;
  border-color: #D9D3CB;
  color: #6B6560;
}

:deep(.el-radio-button:hover .el-radio-button__inner) {
  color: #2D5A27;
}

:deep(.el-radio-button.is-active .el-radio-button__inner) {
  background: #2D5A27;
  border-color: #2D5A27;
  color: #FFFDF9;
  box-shadow: none;
}

.applicant {
  display: flex;
  align-items: center;
  gap: 10px;
}

.applicant :deep(.el-avatar) {
  background: #EBF2EA;
  color: #2D5A27;
  font-weight: 600;
}

.applicant-name {
  font-weight: 600;
  color: #1A1A1A;
}

.muted {
  color: #9C9892;
  font-size: 0.75rem;
}

.info-lines {
  display: grid;
  gap: 6px;
  font-size: 0.875rem;
  color: #1A1A1A;
}

.info-lines span {
  display: inline-block;
  width: 38px;
  color: #9C9892;
}

.intro {
  color: #6B6560;
  line-height: 1.5;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tags :deep(.el-tag--plain) {
  background: #FAF7F2;
  border-color: #D9D3CB;
  color: #6B6560;
}

.portfolio-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.portfolio-item {
  width: 72px;
}

.portfolio-item :deep(.el-image) {
  width: 72px;
  height: 72px;
  display: block;
  border-radius: 4px;
  overflow: hidden;
  background: #FAF7F2;
  border: 1px solid #E8E2DA;
}

.portfolio-item span {
  display: block;
  margin-top: 4px;
  font-size: 0.75rem;
  color: #6B6560;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Table overrides */
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

:deep(.el-button--success) {
  background: #2D5A27;
  border-color: #2D5A27;
}

:deep(.el-button--success:hover) {
  background: #3A6E33;
  border-color: #3A6E33;
}

:deep(.el-button--success.is-disabled) {
  background: #D9D3CB;
  border-color: #D9D3CB;
  color: #9C9892;
}

:deep(.el-button--danger) {
  background: #C53030;
  border-color: #C53030;
}

:deep(.el-button--danger:hover) {
  background: #A02020;
  border-color: #A02020;
}

:deep(.el-button--danger.is-disabled) {
  background: #D9D3CB;
  border-color: #D9D3CB;
  color: #9C9892;
}

@media (max-width: 768px) {
  .photographer-applications-page {
    padding: 12px;
  }

  .page-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
