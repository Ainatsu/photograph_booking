<template>
  <div ref="detailPageRef" class="page-container" v-loading="loading">
    <template v-if="project">
      <section class="shell">
        <div
          class="layout fade-in"
          :style="currentReferenceImage ? getDetailLayoutStyle(getFullUrl(currentReferenceImage), currentReferenceKey) : null"
        >
          <button class="back-btn-circle" @click="goBack" title="返回" aria-label="返回">
            <el-icon><ArrowLeft /></el-icon>
          </button>

          <div
            class="gallery-section"
            :style="currentReferenceImage ? getDetailImageStyle(getFullUrl(currentReferenceImage), currentReferenceKey) : null"
          >
            <div v-if="currentReferenceImage" ref="imageHostRef" class="main-image">
              <div
                class="main-image-frame"
                :style="getDetailImageStyle(getFullUrl(currentReferenceImage), currentReferenceKey)"
              >
                <el-image
                  :src="getFullUrl(currentReferenceImage)"
                  fit="cover"
                  class="main-img"
                  :preview-src-list="referencePreviewList"
                  :initial-index="currentReferenceIndex"
                />
              </div>
            </div>
            <div v-else class="empty-gallery">
              <span>暂无参考图</span>
            </div>
            <div class="thumb-strip" v-if="project.reference_images?.length > 1">
              <button
                v-for="(url, index) in project.reference_images"
                :key="url"
                class="thumb-item"
                :class="{ active: currentReferenceIndex === index }"
                type="button"
                @click="currentReferenceIndex = index"
              >
                <el-image :src="getFullUrl(url)" fit="cover" class="thumb-img" />
              </button>
            </div>
          </div>

          <aside
            ref="infoSectionRef"
            class="info-section"
            :style="currentReferenceImage ? getDetailLayoutStyle(getFullUrl(currentReferenceImage), currentReferenceKey) : null"
          >
            <div class="customer-section">
              <div class="customer-actions">
                <div class="customer-card">
                  <el-avatar :size="48" :src="getFullUrl(project.customer_avatar_url)">
                    {{ (project.customer_name || '?')[0] }}
                  </el-avatar>
                  <div class="customer-copy">
                    <span class="customer-name">{{ project.customer_name || '未知发起人' }}</span>
                    <span class="customer-role">企划发起人 · {{ statusLabel(project.status) }}</span>
                  </div>
                </div>
                <button v-if="project.customer_id" class="message-btn" type="button" @click="goCustomerMessage">
                  <el-icon><ChatLineRound /></el-icon>
                  <span>发消息</span>
                </button>
              </div>
            </div>

            <h1 class="project-title">{{ project.title }}</h1>

            <div class="project-price-location">
              <span class="project-budget">{{ formatBudget(project) }}</span>
              <span class="project-location">{{ formatProjectLocation(project) }}</span>
            </div>

            <div class="project-time-duration">
              <span>{{ formatDateTime(project.shoot_date_start) }}</span>
              <span>{{ formatDuration(project.duration_minutes) }}</span>
              <span v-if="project.expires_at" :class="{ 'deadline-ended': project.status === 'expired' }">
                {{ formatRecruitmentDeadline(project) }}
              </span>
            </div>

            <LocationMapCard
              v-if="project.location_text || project.location_latitude != null"
              :location="project"
            />

            <p v-if="project.description" class="project-desc">{{ project.description }}</p>
            <p v-else class="project-desc muted">暂无详情描述</p>

            <div class="application-row">
              <div class="count-card">
                <span>应邀人数</span>
                <strong>{{ project.application_count }} 人</strong>
              </div>
              <el-button
                v-if="isPhotographer && !isOwner && !myApplication && canApplyProject"
                type="primary"
                size="large"
                :icon="Check"
                class="cta-btn"
                @click="goApplyPage"
              >
                发起应邀
              </el-button>
              <el-button
                v-else-if="isPhotographer && !isOwner && myApplication && canApplyProject"
                type="primary"
                size="large"
                :icon="Edit"
                class="cta-btn"
                @click="goApplyPage"
              >
                我的应邀
              </el-button>
              <div v-else-if="isPhotographer && !isOwner && myApplication" class="status-chip">
                <span>我的应邀</span>
                <strong>{{ applicationStatusLabel(myApplication.status) }}</strong>
              </div>
              <el-button
                v-else-if="project.converted_order_id"
                type="primary"
                size="large"
                :icon="View"
                class="cta-btn"
                @click="router.push(`/orders/${project.converted_order_id}`)"
              >
                查看订单
              </el-button>
              <el-button
                v-else-if="isOwner && project.status === 'open'"
                size="large"
                :icon="Close"
                class="cta-btn"
                @click="closeCurrentProject"
              >
                关闭企划
              </el-button>
              <el-button
                v-if="isOwner && canEditProject"
                size="large"
                :icon="Edit"
                class="cta-btn"
                @click="router.push(`/projects/${project.id}/edit`)"
              >
                {{ project.status === 'expired' ? '编辑并重新发布' : '编辑企划' }}
              </el-button>
            </div>
          </aside>
        </div>
      </section>

      <section v-if="isPhotographer && !isOwner && myApplication && !canApplyProject" class="content-section">
        <div class="section-header">
          <h2>我的应邀方案</h2>
          <el-tag>{{ applicationStatusLabel(myApplication.status) }}</el-tag>
        </div>
        <div class="application-summary">
          <div v-if="myApplication.package_snapshot" class="application-package-summary">
            <span>应邀方案</span>
            <strong>{{ myApplication.package_snapshot }}</strong>
          </div>
          <p>{{ myApplication.proposal_text }}</p>
          <div class="summary-grid">
            <span>报价：¥{{ myApplication.price_quote }}</span>
          </div>
          <p v-if="myApplication.revision_note" class="application-note">条款事项：{{ myApplication.revision_note }}</p>
          <div v-if="applicationPortfolio(myApplication).length" class="application-portfolio">
            <img
              v-for="item in applicationPortfolio(myApplication)"
              :key="item.url"
              :src="getFullUrl(item.url)"
              :alt="item.title || '应邀作品'"
            />
          </div>
        </div>
      </section>

      <section v-if="isOwner" class="content-section">
        <div class="section-header">
          <h2>候选摄影师</h2>
          <div class="application-toolbar">
            <span>{{ applications.length }} 个方案<span v-if="lowestApplicationQuote !== null"> · 最低 ¥{{ lowestApplicationQuote }}</span></span>
            <el-select v-model="applicationSort" size="small" aria-label="候选方案排序">
              <el-option label="推荐排序" value="recommended" />
              <el-option label="报价从低到高" value="price_asc" />
            </el-select>
          </div>
        </div>

        <div class="application-list">
          <article v-for="application in visibleApplications" :key="application.id" class="application-card">
            <div class="photographer-row">
              <el-avatar :size="46" :src="application.photographer_avatar_url">
                {{ (application.photographer_name || '?')[0] }}
              </el-avatar>
              <div>
                <h3>{{ application.photographer_name || `摄影师 #${application.photographer_id}` }}</h3>
                <div class="meta-row">
                  <span v-if="application.photographer_city">{{ application.photographer_city }}</span>
                  <span>{{ applicationStatusLabel(application.status) }}</span>
                </div>
              </div>
            </div>

            <div class="application-meta">
              <strong>¥{{ application.price_quote }}</strong>
            </div>

            <div v-if="applicationCompareLabels(application).length" class="comparison-badges">
              <el-tag v-for="label in applicationCompareLabels(application)" :key="label" size="small" type="warning" effect="plain">{{ label }}</el-tag>
            </div>

            <div v-if="application.package_snapshot" class="application-package-summary">
              <span>应邀方案</span>
              <strong>{{ application.package_snapshot }}</strong>
            </div>

            <p class="application-proposal">{{ application.proposal_text }}</p>

            <p v-if="application.revision_note" class="application-note">条款事项：{{ application.revision_note }}</p>

            <p v-if="application.photographer_equipment" class="equipment-note">常用器材：{{ application.photographer_equipment }}</p>

            <div class="tag-row" v-if="application.photographer_styles?.length">
              <el-tag v-for="tag in application.photographer_styles" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>

            <div v-if="applicationPortfolio(application).length" class="application-portfolio">
              <img
                v-for="item in applicationPortfolio(application)"
                :key="item.url"
                :src="getFullUrl(item.url)"
                :alt="item.title || '应邀作品'"
              />
            </div>

            <div class="candidate-actions">
              <el-button :icon="ChatDotRound" @click="goPhotographerMessage(application)">
                私信沟通
              </el-button>
              <el-button :icon="User" @click="router.push(`/photographer/${application.photographer_id}`)">
                查看主页
              </el-button>
              <el-button
                v-if="project.status === 'open' && application.status === 'submitted'"
                type="primary"
                :icon="Check"
                @click="selectApplication(application)"
              >
                选定摄影师
              </el-button>
            </div>
          </article>
        </div>

        <el-empty v-if="applications.length === 0" description="暂无摄影师应邀" />
      </section>
    </template>

    <el-empty v-else-if="!loading" description="企划不存在" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Check,
  Eye as View,
  MessageSquare as ChatDotRound,
  MessageSquare as ChatLineRound,
  Pencil as Edit,
  UserRound as User,
  X as Close,
} from 'lucide-vue-next'
import {
  closeProject,
  getProjectDetail,
  selectProjectApplication,
} from '../api/project'
import api from '../utils/api'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { useDetailImageFrame } from '@/composables/useDetailImageFrame'
import LocationMapCard from '../components/location/LocationMapCard.vue'

const route = useRoute()
const router = useRouter()
const { getSteppedDetailOrPreload } = useImageAspectRatio()
const { detailPageRef, imageHostRef, infoSectionRef, getFrameStyle, getLayoutStyle } = useDetailImageFrame()
const loading = ref(false)
const project = ref(null)
const applications = ref([])
const myApplication = ref(null)
const currentReferenceIndex = ref(0)
const applicationSort = ref('recommended')

const currentUser = ref(null)
const userRole = computed(() => currentUser.value?.role || '')
const isPhotographer = computed(() => userRole.value === 'photographer')
const isOwner = computed(() => project.value?.customer_id === Number(currentUser.value?.id))
const canApplyProject = computed(() => (
  project.value?.status === 'open'
  && (!myApplication.value || myApplication.value.status === 'submitted')
))
const canEditProject = computed(() => ['draft', 'open', 'expired'].includes(project.value?.status))
const currentReferenceImage = computed(() => {
  const images = project.value?.reference_images || []
  return images[currentReferenceIndex.value] || images[0] || ''
})
const currentReferenceKey = computed(() => {
  return `${project.value?.id || currentReferenceImage.value}:${currentReferenceIndex.value}`
})
const referencePreviewList = computed(() => {
  return (project.value?.reference_images || []).map(getFullUrl)
})
const lowestApplicationQuote = computed(() => {
  const quotes = applications.value.map((item) => Number(item.price_quote)).filter(Number.isFinite)
  return quotes.length ? Math.min(...quotes) : null
})
const visibleApplications = computed(() => {
  const items = [...applications.value]
  if (applicationSort.value === 'price_asc') {
    return items.sort((a, b) => Number(a.price_quote || 0) - Number(b.price_quote || 0))
  }
  return items
})

const applicationCompareLabels = (application) => {
  const labels = []
  if (lowestApplicationQuote.value !== null && Number(application.price_quote) === lowestApplicationQuote.value) {
    labels.push('最低报价')
  }
  const quote = Number(application.price_quote)
  const budgetMin = Number(project.value?.budget_min)
  const budgetMax = Number(project.value?.budget_max)
  const meetsMin = !Number.isFinite(budgetMin) || budgetMin <= 0 || quote >= budgetMin
  const meetsMax = !Number.isFinite(budgetMax) || budgetMax <= 0 || quote <= budgetMax
  if (Number.isFinite(quote) && meetsMin && meetsMax && (budgetMin > 0 || budgetMax > 0)) {
    labels.push('符合预算')
  }
  return labels
}

const fetchCurrentUser = async () => {
  if (!localStorage.getItem('token')) {
    currentUser.value = null
    return
  }
  try {
    const res = await api.get('/users/me', { skipErrorHandler: true })
    currentUser.value = res.data
  } catch {
    currentUser.value = null
  }
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const res = await getProjectDetail(route.params.projectId)
    project.value = res.data.project
    applications.value = res.data.applications || []
    myApplication.value = res.data.my_application || null
    currentReferenceIndex.value = 0
  } finally {
    loading.value = false
  }
}

const goApplyPage = () => {
  if (!project.value?.id) return
  router.push(`/projects/${project.value.id}/apply`)
}

const getCurrentUserId = () => {
  if (currentUser.value?.id) return Number(currentUser.value.id)
  const token = localStorage.getItem('token')
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return Number(payload.sub)
  } catch {
    return null
  }
}

const goCustomerMessage = () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再发消息')
    router.push('/login')
    return
  }
  if (!project.value?.customer_id) return
  if (Number(project.value.customer_id) === getCurrentUserId()) {
    ElMessage.warning('不能给自己发送私信')
    return
  }

  const projectTitle = project.value.title || '这个企划'
  router.push({
    path: '/messages',
    query: {
      to: project.value.customer_id,
      introType: 'project',
      introTitle: projectTitle,
      introUrl: `/projects/${project.value.id}`,
      introCoverUrl: currentReferenceImage.value || '',
      introText: `你好，我刚刚看到你的企划「${projectTitle}」，想了解一下拍摄安排和细节。`,
    },
  })
}

const goPhotographerMessage = (application) => {
  if (!project.value?.id || !application?.photographer_id) return
  const projectTitle = project.value.title || '这个企划'
  router.push({
    path: '/messages',
    query: {
      to: application.photographer_id,
      introType: 'project',
      introTitle: projectTitle,
      introUrl: `/projects/${project.value.id}`,
      introCoverUrl: currentReferenceImage.value || '',
      introText: `你好，我正在查看你针对企划「${projectTitle}」提交的应邀方案，想进一步确认拍摄安排和方案细节。`,
    },
  })
}

const selectApplication = async (application) => {
  try {
    await ElMessageBox.confirm('选定后将创建一笔待确认订单，其他应邀会自动落选。', '选定摄影师', { type: 'warning' })
  } catch {
    return
  }
  const res = await selectProjectApplication(project.value.id, application.id)
  ElMessage.success('已创建订单')
  router.push(`/orders/${res.data.order.id}`)
}

const closeCurrentProject = async () => {
  try {
    await ElMessageBox.confirm('关闭后摄影师将不能继续应邀。', '关闭企划', { type: 'warning' })
  } catch {
    return
  }
  await closeProject(project.value.id, '客户关闭企划')
  ElMessage.info('企划已关闭')
  await fetchDetail()
}

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/projects')
}

const statusLabel = (value) => ({ draft: '草稿', open: '招募中', converted: '已转订单', closed: '已关闭', cancelled: '已取消', expired: '已过期' }[value] || value)
const applicationStatusLabel = (value) => ({ submitted: '已提交', selected: '已选中', rejected: '未选中', withdrawn: '已撤回' }[value] || value)

const applicationPortfolio = (application) => {
  if (!Array.isArray(application?.portfolio_refs)) return []
  return application.portfolio_refs.filter((item) => item?.url).slice(0, 8)
}

const getDetailImageRatio = (url, key) => {
  return getSteppedDetailOrPreload(url, key)
}

const getDetailImageStyle = (url, key) => {
  return getFrameStyle(getDetailImageRatio(url, key))
}

const getDetailLayoutStyle = (url, key) => {
  return getLayoutStyle(getDetailImageRatio(url, key))
}

const formatBudget = (item) => {
  if (item.budget_min && item.budget_max) return `¥${item.budget_min} - ¥${item.budget_max}`
  if (item.budget_min) return `¥${item.budget_min} 起`
  if (item.budget_max) return `¥${item.budget_max} 内`
  return '待沟通'
}

const formatProjectLocation = (item) => {
  const parts = [item.city, item.location_text].filter(Boolean)
  return parts.length ? parts.join(' · ') : '地点待定'
}

const formatDateTime = (value) => {
  if (!value) return '待沟通'
  return new Date(value).toLocaleString()
}

const formatRecruitmentDeadline = (item) => {
  if (item?.status === 'expired') return '招募已截止'
  return `招募截止：${formatDateTime(item?.expires_at)}`
}

const formatDuration = (value) => {
  return value ? `${value} 分钟` : '时长待沟通'
}

const getFullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

onMounted(async () => {
  await fetchCurrentUser()
  fetchDetail()
})
</script>

<style scoped>
.page-container {
  --detail-page-padding: 20px;
  --detail-back-gutter: 52px;
  --detail-layout-gap: 20px;
  --detail-info-width: clamp(400px, 25vw, 480px);
  --detail-content-offset-top: clamp(32px, 5vh, 64px);
  --detail-card-height: min(720px, calc(100vh - 76px - (var(--detail-page-padding) * 2) - var(--detail-content-offset-top)));
  box-sizing: border-box;
  min-height: calc(100vh - 76px);
  max-width: 1920px;
  margin: 0 auto 56px;
  padding: var(--detail-page-padding);
  color: var(--color-ink);
  font-family: var(--font-sans);
  position: relative;
}

@media (min-width: 861px) {
  .page-container {
    padding-top: calc(var(--detail-page-padding) + var(--detail-content-offset-top));
  }
}

.shell {
  position: relative;
}

.back-btn-circle {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: var(--border-default);
  background: var(--color-paper-light);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  color: var(--color-ink);
  transition: background 0.2s, border-color 0.2s;
  padding: 0;
  line-height: 1;
}

.back-btn-circle:hover {
  background: var(--color-paper);
  border-color: var(--color-brand);
}

.back-btn-circle:active {
  background: var(--color-border-light);
}

.fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.content-section {
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.content-section {
  margin-top: 18px;
  padding: 28px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.section-header {
  margin-bottom: 20px;
}

.section-header h2,
.application-card h3 {
  margin: 0;
  color: var(--color-ink);
  font-size: 22px;
  line-height: 1.3;
}

.application-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-ink-tertiary);
  font-size: var(--text-sm);
}

.comparison-badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0 0 var(--space-3);
}

.customer-section {
  margin-bottom: 22px;
}

.customer-card {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: var(--space-3) 14px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.customer-actions {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 10px;
  align-items: stretch;
}

.message-btn {
  appearance: none;
  min-width: 0;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-brand);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 0.875rem;
  font-weight: 600;
  transition: background 0.2s, border-color 0.2s;
}

.message-btn:hover {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}

.customer-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.customer-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.customer-role {
  font-size: var(--text-xs);
  color: var(--color-brand);
  margin-top: 2px;
}

.project-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  margin: 0 0 var(--space-3);
  line-height: 1.3;
  color: var(--color-ink);
}

.project-price-location {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  margin-bottom: var(--space-2);
}

.project-budget {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-ink);
}

.project-location {
  display: inline-block;
  padding: 1px var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-brand);
  background: var(--color-brand-light);
  border-radius: var(--radius-sm);
  font-weight: 500;
}

.project-time-duration {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  margin-bottom: var(--space-4);
  color: var(--color-ink-secondary);
  font-size: 0.875rem;
  line-height: var(--leading-normal);
}

.project-time-duration .deadline-ended {
  color: var(--color-danger);
  font-weight: 700;
}

.project-desc {
  font-size: 0.875rem;
  color: var(--color-ink-secondary);
  line-height: var(--leading-relaxed);
  margin: 0;
  white-space: pre-wrap;
}

.project-desc.muted {
  color: var(--color-ink-tertiary);
}

.application-row {
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  z-index: 1;
  margin-top: auto;
  padding-top: 28px;
  background: var(--color-paper-light);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(138px, 1fr);
  gap: var(--space-3);
  align-items: stretch;
}

.count-card,
.status-chip {
  min-width: 0;
  min-height: 48px;
  padding: var(--space-2) var(--space-3);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.count-card span,
.status-chip span {
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
}

.count-card strong,
.status-chip strong {
  color: var(--color-ink);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.status-chip {
  border-color: var(--color-border);
  background: var(--color-brand-light);
}

.status-chip strong {
  color: var(--color-brand);
}

.cta-btn {
  width: 100%;
  height: 48px;
  margin-left: 0;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-md);
}

.application-summary {
  color: var(--color-ink-secondary);
  line-height: var(--leading-relaxed);
}

.application-package-summary,
.included-items {
  display: grid;
  gap: 4px;
  margin-bottom: var(--space-3);
  padding: 12px 14px;
  background: var(--color-paper);
  border-radius: var(--radius-md);
}

.application-package-summary span,
.included-items > span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.application-package-summary strong {
  color: var(--color-ink);
  font-size: var(--text-sm);
  line-height: 1.5;
}

.application-proposal {
  white-space: pre-wrap;
}

.application-note,
.equipment-note {
  padding-left: var(--space-3);
  border-left: 3px solid var(--color-border);
}

.equipment-note {
  color: var(--color-ink-tertiary) !important;
  font-size: var(--text-sm);
}

.application-portfolio {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  margin-top: var(--space-3);
  padding-bottom: 4px;
}

.application-portfolio img {
  width: 72px;
  height: 72px;
  flex: 0 0 auto;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: var(--border-default);
}

.summary-grid,
.application-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  color: var(--color-ink-secondary);
}

.application-list {
  display: grid;
  gap: 14px;
}

.application-card {
  border: var(--border-default);
  border-radius: var(--radius-md);
  padding: 18px;
  background: var(--color-paper-light);
  transition: border-color 0.2s;
}

.application-card:hover {
  border-color: var(--color-brand);
}

.photographer-row {
  justify-content: flex-start;
}

.photographer-row,
.candidate-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  color: var(--color-ink-secondary);
  font-size: 0.875rem;
}

.application-meta {
  margin: 14px 0 8px;
}

.application-meta strong {
  color: var(--color-ink);
}

.application-card p {
  color: var(--color-ink-secondary);
  line-height: var(--leading-relaxed);
  margin: 0 0 var(--space-3);
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.candidate-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
  margin-top: 14px;
}

.customer-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

/* Detail layout refresh */
.layout {
  box-sizing: border-box;
  display: flex;
  gap: var(--detail-layout-gap);
  align-items: stretch;
  min-height: 0;
  flex: 0 0 auto;
  position: relative;
  padding-left: var(--detail-back-gutter);
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
}

.gallery-section,
.info-section {
  box-sizing: border-box;
  border: var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.gallery-section {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  background: var(--color-paper);
}

.main-image,
.empty-gallery {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  background: var(--color-paper);
}

.main-image {
  cursor: zoom-in;
}

.main-image-frame {
  box-sizing: border-box;
  flex: 0 0 auto;
  overflow: hidden;
  background: var(--color-paper);
}

.main-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.main-img :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.empty-gallery {
  width: min(624px, calc(100vw - 40px - var(--detail-back-gutter) - var(--detail-info-width) - var(--detail-layout-gap)));
  height: var(--detail-card-height);
  color: var(--color-ink-tertiary);
  font-size: 0.875rem;
}

.thumb-strip {
  position: absolute;
  left: var(--space-3);
  right: var(--space-3);
  bottom: var(--space-3);
  z-index: 2;
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  padding: var(--space-3) 0 0;
  border: 0;
  background: transparent;
  scrollbar-width: thin;
}

.thumb-item {
  appearance: none;
  flex: 0 0 auto;
  width: 64px;
  height: 64px;
  padding: 0;
  overflow: hidden;
  border: 2px solid transparent;
  border-radius: var(--radius-sm);
  background: var(--color-paper-light);
  cursor: pointer;
  box-shadow: none;
  transition: border-color 0.2s;
}

.thumb-item.active {
  border-color: var(--color-brand);
}

.thumb-item:hover {
  border-color: var(--color-border);
}

.thumb-img,
.thumb-img :deep(img) {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.info-section {
  width: var(--detail-info-width);
  flex-shrink: 0;
  padding: var(--space-8) 28px;
  background: var(--color-paper-light);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
}

/* legacy class guards */
.title-row {
  align-items: flex-start;
}

.customer-card.is-vertical {
  flex-direction: column;
  align-items: center;
}

@media (min-width: 861px) {
  .page-container {
    --detail-card-height: min(
      720px,
      calc(100vh - 76px - (var(--detail-page-padding) * 2) - var(--detail-content-offset-top))
    );
  }

  .layout {
    align-items: center;
    height: var(--detail-card-height);
  }

  .gallery-section {
    height: 100%;
    width: fit-content;
  }

  .main-image {
    flex: 0 0 auto;
    width: auto;
    height: 100%;
  }

  .main-image-frame {
    max-width: 100%;
  }

  .info-section {
    height: var(--detail-card-height);
    max-height: none;
  }
}

@media (max-width: 920px) {
  .page-container {
    width: auto;
    margin-top: 0;
  }

  .back-btn-circle {
    top: 0;
    left: 0;
  }
}

@media (max-width: 860px) {
  .page-container {
    padding: var(--space-3);
  }

  .layout {
    width: 100%;
    flex-direction: column;
    padding-left: 0;
  }

  .back-btn-circle {
    top: var(--space-3);
    left: var(--space-3);
  }

  .gallery-section {
    width: 100%;
  }

  .main-image {
    width: 100%;
  }

  .info-section {
    width: 100%;
    max-height: none;
    padding: var(--space-6) 20px;
  }

  .empty-gallery {
    width: 100%;
    height: 300px;
  }

  .application-row {
    position: static;
    margin-top: 28px;
    padding-top: 0;
  }
}

@media (max-width: 480px) {
  .info-section {
    padding: 18px 14px;
  }

  .customer-actions,
  .application-row {
    grid-template-columns: 1fr;
  }

  .project-title {
    font-size: 20px;
  }

  .project-budget {
    font-size: 24px;
  }

  .thumb-item {
    width: 48px;
    height: 48px;
  }
}
</style>
