<template>
  <div class="page-container">
    <div class="page-toolbar">
      <div class="filter-section">
        <el-input v-model="filters.city" placeholder="城市" clearable class="short-input" />
        <el-input v-model="filters.style_tags" placeholder="风格类型" clearable class="short-input" />
        <div class="budget-group">
          <el-input-number v-model="filters.budget_min" :min="0" :step="100" placeholder="最低" controls-position="right" />
          <span class="budget-separator">-</span>
          <el-input-number v-model="filters.budget_max" :min="0" :step="100" placeholder="最高" controls-position="right" />
        </div>
        <el-button type="primary" :icon="Search" @click="fetchProjects">筛选</el-button>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>
      <div class="action-section">
        <el-button v-if="isCustomer" :icon="FolderOpened" @click="router.push('/my-projects')">
          我的企划
        </el-button>
        <el-button v-if="isPhotographer" :icon="Tickets" @click="router.push('/my-applications')">
          我的应邀
        </el-button>
        <el-button v-if="isCustomer" type="primary" :icon="Plus" @click="router.push('/projects/new')">
          发布企划
        </el-button>
      </div>
    </div>

    <div class="card-list" v-loading="loading">
      <article
        v-for="project in projects"
        :key="project.id"
        class="card-item"
        :data-project-recommendation-position="projects.indexOf(project)"
        @click="goDetail(project.id)"
      >
        <div class="card-body">
          <div class="card-header">
            <div>
              <h3>{{ project.title }}</h3>
              <div class="card-meta">
                <span>{{ project.city }}</span>
                <span v-if="project.location_text" class="card-location"><MapPin :size="15" aria-hidden="true" />{{ project.location_name || project.location_text }}</span>
              </div>
              <div v-if="project.match_reason" class="match-reason">{{ project.match_reason }}</div>
            </div>

          </div>

          <p class="card-desc">{{ project.description }}</p>

          <div class="card-tags" v-if="project.style_tags?.length">
            <el-tag v-for="tag in project.style_tags" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </div>

        <div class="card-references" v-if="project.reference_images?.length">
          <div
            v-for="(url, idx) in project.reference_images.slice(0, 2)"
            :key="idx"
            class="ref-thumb"
          >
            <el-image :src="url" fit="cover" class="ref-thumb-img" />
          </div>
        </div>

        <div class="card-footer">
          <span class="footer-label">{{ formatDate(project.shoot_date_start) }}</span>
          <span v-if="project.expires_at" class="footer-label">截止 {{ formatDate(project.expires_at) }}</span>
          <span class="footer-label">{{ project.application_count }} 人应邀</span>
          <span class="footer-price">{{ formatBudget(project) }}</span>
        </div>
      </article>
    </div>

    <el-empty v-if="!loading && projects.length === 0" description="暂无公开企划" />
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { FolderOpen as FolderOpened, MapPin, Plus, RefreshCw as Refresh, Search, Ticket as Tickets } from 'lucide-vue-next'
import { getProjects } from '../api/project'
import { getRecommendedProjects, trackRecommendationEvents } from '../api/recommendation'
import api from '../utils/api'
import { useProfileMode } from '@/composables/useProfileMode'

defineOptions({ name: 'Projects' })

const router = useRouter()
const loading = ref(false)
const projects = ref([])
const recommendationMeta = ref(null)
let recommendationSessionId = ''
let impressionObserver = null
const filters = reactive({
  city: '',
  style_tags: '',
  budget_min: undefined,
  budget_max: undefined,
})

const userRole = ref('')
const isLoggedIn = ref(false)
const { profileMode, initProfileMode } = useProfileMode()
const isCustomer = computed(() => isLoggedIn.value && profileMode.value === 'customer')
const isPhotographer = computed(() => isLoggedIn.value && profileMode.value === 'photographer')

const fetchCurrentUserRole = async () => {
  if (!localStorage.getItem('token')) {
    isLoggedIn.value = false
    userRole.value = ''
    return
  }
  try {
    const res = await api.get('/users/me', { skipErrorHandler: true })
    isLoggedIn.value = true
    userRole.value = res.data.role || ''
    initProfileMode({ userId: res.data.id, role: userRole.value })
  } catch {
    isLoggedIn.value = false
    userRole.value = ''
  }
}

const buildParams = () => {
  const params = {}
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) params[key] = value
  })
  return params
}

const fetchProjects = async () => {
  loading.value = true
  try {
    if (isPhotographer.value) {
      recommendationSessionId = sessionStorage.getItem('recommendation-session-id') || crypto.randomUUID()
      sessionStorage.setItem('recommendation-session-id', recommendationSessionId)
      const params = buildParams()
      if (params.style_tags) {
        params.styles = params.style_tags
        delete params.style_tags
      }
      params.session_id = recommendationSessionId
      const res = await getRecommendedProjects(params)
      recommendationMeta.value = res.data
      projects.value = res.data.items
      observeProjectCards()
    } else {
      recommendationMeta.value = null
      projects.value = (await getProjects(buildParams())).data
    }
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  filters.city = ''
  filters.style_tags = ''
  filters.budget_min = undefined
  filters.budget_max = undefined
  fetchProjects()
}

const buildRecommendationEvent = (project, eventType, position = null) => ({
  event_type: eventType,
  target_type: 'shoot_project',
  target_id: String(project.id),
  owner_user_id: project.customer_id,
  recommendation_id: recommendationMeta.value?.recommendation_id,
  session_id: recommendationSessionId,
  scene: 'photographer_project_feed',
  position: position ?? projects.value.findIndex((item) => item.id === project.id),
  algorithm_version: recommendationMeta.value?.algorithm_version,
  candidate_source: project.candidate_source,
})

const observeProjectCards = async () => {
  impressionObserver?.disconnect()
  if (!recommendationMeta.value) return
  await nextTick()
  impressionObserver = new IntersectionObserver((entries) => {
    entries.filter((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5).forEach((entry) => {
      const position = Number(entry.target.dataset.projectRecommendationPosition)
      const project = projects.value[position]
      window.setTimeout(() => {
        if (project && entry.target.isConnected) trackRecommendationEvents([buildRecommendationEvent(project, 'project_impression', position)]).catch(() => {})
      }, 500)
      impressionObserver?.unobserve(entry.target)
    })
  }, { threshold: 0.5 })
  document.querySelectorAll('[data-project-recommendation-position]').forEach((element) => impressionObserver.observe(element))
}

const goDetail = (id) => {
  const project = projects.value.find((item) => item.id === id)
  if (project && recommendationMeta.value) {
    trackRecommendationEvents([buildRecommendationEvent(project, 'project_click')]).catch(() => {})
  }
  router.push(`/projects/${id}`)
}

const formatBudget = (project) => {
  if (project.budget_min && project.budget_max) return `¥${project.budget_min} - ¥${project.budget_max}`
  if (project.budget_min) return `¥${project.budget_min} 起`
  if (project.budget_max) return `¥${project.budget_max} 内`
  return '预算待沟通'
}

const formatDate = (value) => {
  if (!value) return '时间待沟通'
  return new Date(value).toLocaleDateString()
}

onMounted(async () => {
  await fetchCurrentUserRole()
  await fetchProjects()
})

onUnmounted(() => impressionObserver?.disconnect())
</script>

<style scoped>
.page-container {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-6);
  color: var(--color-ink);
  font-family: var(--font-sans);
}

.page-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: var(--space-4);
}

.filter-section {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  width: fit-content;
  min-width: 0;
}

.short-input {
  width: 130px;
}

.budget-group {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.budget-group .el-input-number {
  width: 130px;
}

.budget-separator {
  color: var(--color-ink-secondary);
  font-size: 0.875rem;
}

.action-section {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.action-section :deep(.el-button) {
  min-height: var(--tap-target-min);
}

.card-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  min-height: 120px;
}

.card-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
  padding: 14px;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.card-item:hover {
  border-color: var(--color-brand);
  background: var(--color-paper);
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.card-header h3 {
  margin: 0 0 var(--space-2);
  color: var(--color-ink);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}

.card-location {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.match-reason {
  margin-top: var(--space-2);
  color: var(--color-brand);
  font-size: var(--text-sm);
}

.card-desc {
  margin: 14px 0;
  color: var(--color-ink-secondary);
  line-height: var(--leading-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.card-references {
  display: flex;
  gap: 6px;
  align-items: flex-start;
  padding-top: 2px;
}

.card-references .ref-thumb {
  width: 118px;
  height: 118px;
  flex-shrink: 0;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--color-paper);
  border: var(--border-default);
}

.ref-thumb-img {
  width: 100%;
  height: 100%;
  display: block;
}

.card-footer {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding-top: 10px;
  border-top: 1px solid var(--color-divider);
  margin-top: var(--space-1);
}

.footer-label {
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}

.footer-price {
  margin-left: auto;
  color: var(--color-warning);
  font-weight: 700;
  font-size: var(--text-lg);
}

@media (max-width: 768px) {
  .page-toolbar {
    flex-direction: column;
  }

  .card-list {
    grid-template-columns: 1fr;
  }

  .card-item {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .page-container {
    padding: var(--space-3);
  }

  .filter-section {
    flex-wrap: wrap;
  }

  .action-section {
    flex-wrap: wrap;
  }
}
</style>
