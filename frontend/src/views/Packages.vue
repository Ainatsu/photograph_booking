<template>
  <div class="page">
    <div class="page-header">
      <div class="filter-section">
        <el-input v-model="filters.city" placeholder="城市" clearable class="filter-input" />
        <el-input v-model="filters.style_tags" placeholder="风格类型" clearable class="filter-input" />
        <div class="budget-group">
          <el-input-number v-model="filters.budget_min" :min="0" :step="100" placeholder="最低" controls-position="right" />
          <span class="budget-sep">-</span>
          <el-input-number v-model="filters.budget_max" :min="0" :step="100" placeholder="最高" controls-position="right" />
        </div>
        <el-button type="primary" :icon="Search" @click="applyFilters">筛选</el-button>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>
      <div class="action-section">
        <el-button v-if="isCustomer" :icon="FolderOpened" @click="router.push('/my-orders')">
          我的订单
        </el-button>
        <el-button v-if="isPhotographer" :icon="Tickets" @click="router.push('/my-packages')">
          我的方案
        </el-button>
        <el-button v-if="isPhotographer" type="primary" :icon="Plus" @click="router.push('/packages/new')">
          发布方案
        </el-button>
      </div>
    </div>

    <div class="waterfall" v-loading="loading">
      <div
        class="waterfall-card"
        v-for="pkg in filteredPackages"
        :key="pkg.id || pkg.package_name"
        @click="goPackageDetail(pkg)"
      >
        <div
          v-if="pkg.samples && pkg.samples.length"
          class="cover-wrap"
          :style="{ aspectRatio: getOrPreload(getPackageCoverPreviewUrl(pkg), pkg.id || pkg.package_name) }"
        >
          <el-image
            :src="getPackageCoverPreviewUrl(pkg)"
            fit="cover"
            class="cover-img"
            lazy
          />
        </div>
        <div class="card-footer">
          <div class="card-title" v-if="pkg.package_name">
            {{ pkg.package_name }}
          </div>
          <div class="card-meta">
            <span class="card-meta-left">
              <el-avatar :size="24" :src="getFullUrl(pkg.photographer_avatar)">
                {{ (pkg.photographer_name || '?')[0] }}
              </el-avatar>
              <span class="card-subtitle">{{ pkg.photographer_name || '未知摄影师' }}</span>
            </span>
            <span v-if="pkg.price || pkg.price === 0" class="card-price">&yen;{{ pkg.price }}</span>
          </div>
        </div>
      </div>
    </div>
    <el-empty v-if="!loading && !filteredPackages.length" description="暂无方案" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FolderOpen as FolderOpened, Plus, RefreshCw as Refresh, Search, Ticket as Tickets } from 'lucide-vue-next'
import { getAllPackages } from '../api/photographer'
import api from '../utils/api'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { getPackagePreviewUrl } from '@/utils/imagePreview'
import { useProfileMode } from '@/composables/useProfileMode'

defineOptions({ name: 'Packages' })

const router = useRouter()
const packages = ref([])
const loading = ref(false)
const { getOrPreload, preloadAll } = useImageAspectRatio()

const userRole = ref('')
const isLoggedIn = ref(false)
const { profileMode, initProfileMode } = useProfileMode()
const isCustomer = computed(() => isLoggedIn.value && profileMode.value === 'customer')
const isPhotographer = computed(() => isLoggedIn.value && profileMode.value === 'photographer')

const filters = reactive({
  city: '',
  style_tags: '',
  budget_min: undefined,
  budget_max: undefined,
})

const filteredPackages = ref([])

const applyFilters = () => {
  let list = packages.value
  if (filters.city) {
    const keyword = filters.city.toLowerCase()
    list = list.filter(p => {
      // 不限制城市的方案始终匹配
      if (!p.city) return true
      return (p.city || '').toLowerCase().includes(keyword)
    })
  }
  if (filters.style_tags) {
    const keyword = filters.style_tags.toLowerCase()
    list = list.filter(p => (p.styles || []).some(s => s.toLowerCase().includes(keyword)))
  }
  if (filters.budget_min !== undefined && filters.budget_min !== null) {
    list = list.filter(p => p.price >= filters.budget_min)
  }
  if (filters.budget_max !== undefined && filters.budget_max !== null) {
    list = list.filter(p => p.price <= filters.budget_max)
  }
  filteredPackages.value = list
}

const resetFilters = () => {
  filters.city = ''
  filters.style_tags = ''
  filters.budget_min = undefined
  filters.budget_max = undefined
  filteredPackages.value = packages.value
}

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

const fetchPackages = async () => {
  loading.value = true
  try {
    const res = await getAllPackages()
    packages.value = res.data
    filteredPackages.value = res.data
  } finally {
    loading.value = false
  }
}

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getKey = (pkg) => pkg.id || pkg.package_name || ''
const getPackageCoverPreviewUrl = (pkg) => getPackagePreviewUrl(pkg)
const getUrl = (pkg) => getPackageCoverPreviewUrl(pkg)

watch(packages, (list) => {
  preloadAll(list, getUrl, getKey)
})

const goPackageDetail = (pkg) => {
  router.push({
    path: `/package/${pkg.id}`,
    state: { from: router.currentRoute.value.fullPath },
  })
}

onMounted(() => {
  fetchCurrentUserRole()
  fetchPackages()
})
</script>

<style scoped>
.page {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-4);
}

.page-header {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

/* ── Filter bar ── */
.filter-section {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  width: fit-content;
  min-width: 0;
}

.filter-input {
  width: 130px;
}

.budget-group {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.budget-group :deep(.el-input-number) {
  width: 130px;
}

.budget-sep {
  color: var(--color-ink-tertiary);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
}

/* ── Action buttons ── */
.action-section {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.action-section :deep(.el-button) {
  min-height: var(--tap-target-min);
}

/* ── Waterfall grid ── */
.waterfall {
  column-count: 4;
  column-gap: var(--space-4);
}

.waterfall-card {
  break-inside: avoid;
  margin-bottom: var(--space-4);
  cursor: pointer;
  overflow: hidden;
  border-radius: var(--radius-md);
  border: var(--border-default);
  background: var(--color-paper-light);
  transition: border-color .25s;
}

.waterfall-card:hover {
  border-color: var(--color-ink-secondary);
}

.cover-wrap {
  overflow: hidden;
  background: var(--color-divider);
  display: flex;
  align-items: center;
  justify-content: center;
}

.cover-img {
  width: 100%;
  height: 100%;
  display: block;
}

.card-footer {
  padding: var(--space-3) var(--space-3) var(--space-3);
}

.card-title {
  font-size: calc(var(--text-sm) * 1.2);
  font-weight: 600;
  color: var(--color-ink);
  font-family: var(--font-sans);
  margin-bottom: var(--space-1);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.card-meta-left {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.card-subtitle {
  font-size: calc(var(--text-xs) * 1.2);
  color: var(--color-ink-secondary);
  font-family: var(--font-sans);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-price {
  color: var(--color-warning);
  font-size: var(--text-sm);
  font-weight: 700;
  font-family: var(--font-sans);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Responsive ── */
@media (max-width: 992px) {
  .waterfall { column-count: 3; }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
  }
  .waterfall { column-count: 2; }
}

@media (max-width: 560px) {
  .page {
    padding: var(--space-3);
  }
  .filter-section {
    flex-wrap: wrap;
  }
  .action-section {
    flex-wrap: wrap;
  }
  .waterfall { column-count: 1; }
}
</style>
