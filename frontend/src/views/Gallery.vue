<template>
  <div class="gallery-page">
    <div v-if="searchQuery" class="title-row">
      <h2 class="page-title">搜索"{{ searchQuery }}"的结果</h2>
      <div class="search-type-toggle" role="tablist" aria-label="搜索结果分类">
        <button
          v-for="item in searchFilterOptions"
          :key="item.key"
          type="button"
          role="tab"
          :aria-selected="searchType === item.key"
          :class="['filter-btn', { 'filter-btn-active': searchType === item.key }]"
          @click="searchType = item.key"
        >
          {{ item.label }}
          <span v-if="item.count !== null" class="filter-count">{{ item.count }}</span>
        </button>
      </div>
    </div>

    <div v-if="searchType === 'works'" class="gallery-waterfall" v-loading="loading">
      <div
        class="gallery-card"
        v-for="work in filteredWorks"
        :key="work.id || work.url"
        :data-gallery-work-key="getWorkAnchorKey(work)"
        :data-recommendation-position="filteredWorks.indexOf(work)"
        @click="openWork(work)"
      >
        <div class="gallery-card-inner">
          <div class="gallery-card-media" :style="{ aspectRatio: getWorkCardRatio(work) }">
            <video
              v-if="isVideoWork(work) && !getWorkPreviewUrl(work)"
              :src="getVideoStreamUrl(work)"
              class="gallery-card-img gallery-card-video"
              preload="metadata"
              muted
              playsinline
            />
            <el-image v-else :src="getWorkPreviewUrl(work)" fit="cover" class="gallery-card-img" lazy />
            <!-- 视频播放按钮叠加 -->
            <div v-if="work.media_type === 'video'" class="gallery-video-overlay">
              <el-icon :size="28"><VideoPlay /></el-icon>
            </div>
          </div>
          <div class="gallery-card-body">
            <div class="gallery-card-title" v-if="work.title">{{ work.title }}</div>
            <div class="gallery-card-meta">
              <span class="gallery-card-author">
                <el-avatar :size="24" :src="getAvatarUrl(work)" class="gallery-card-avatar">
                  {{ (work.user_display_name || '?')[0] }}
                </el-avatar>
                <span class="gallery-card-name">{{ work.user_display_name || '摄影师' }}</span>
              </span>
              <span @click.stop>
                <LikeButton
                  v-if="work.id"
                  target-type="portfolio"
                  :target-id="work.id"
                  :liked="likeStore.get('portfolio', work.id).liked"
                  :count="likeStore.get('portfolio', work.id).count"
                  class="row-like-btn"
                />
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="searchType === 'photographers'" class="gallery-photographer-list" v-loading="loadingPhotographers">
      <div
        class="photographer-entry"
        v-for="p in filteredPhotographers"
        :key="p.id"
        @click="goDetail(p.user_id)"
      >
        <div class="gallery-card-inner">
          <div class="photographer-images">
            <div class="photographer-img-cell" v-for="i in 3" :key="i">
              <el-image
                v-if="getProfileWorkUrl(p, i - 1)"
                :src="getProfileWorkUrl(p, i - 1)"
                fit="cover"
                class="photographer-img"
                lazy
              />
              <div v-else class="photographer-img-placeholder"></div>
            </div>
          </div>
          <div class="photographer-body">
            <div class="photographer-name-row">
              <span class="photographer-display-name">{{ p.user_display_name || '摄影师' }}</span>
              <el-avatar :size="32" :src="getProfileAvatarUrl(p)" class="photographer-display-avatar">
                {{ (p.user_display_name || '?')[0] }}
              </el-avatar>
            </div>
            <div class="photographer-tags" v-if="p.styles && p.styles.length">
              <el-tag v-for="tag in p.styles" :key="tag" size="small" class="photographer-tag">{{ tag }}</el-tag>
            </div>
            <div class="photographer-bio" v-if="p.user_bio">{{ p.user_bio }}</div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="searchType === 'packages'" class="gallery-waterfall" v-loading="loadingPackages">
      <div
        class="gallery-card"
        v-for="pkg in filteredPackages"
        :key="pkg.id || pkg.package_name"
        :data-package-recommendation-position="filteredPackages.indexOf(pkg)"
        @click="goPackageDetail(pkg)"
      >
        <div class="gallery-card-inner">
          <div
            v-if="pkg.samples && pkg.samples.length"
            class="gallery-card-cover"
            :style="{ aspectRatio: getPkgOrPreload(getPackageCoverPreviewUrl(pkg), pkg.id || pkg.package_name) }"
          >
            <el-image
              :src="getPackageCoverPreviewUrl(pkg)"
              fit="cover"
              class="gallery-cover-img"
            />
          </div>
          <div v-else class="gallery-card-placeholder">暂无示例图</div>
          <div class="gallery-card-body">
            <div class="gallery-card-title">{{ pkg.package_name }}</div>
            <div class="gallery-card-price">¥{{ pkg.price }} / {{ pkg.duration }}分钟</div>
            <div class="gallery-card-desc" v-if="pkg.description">{{ pkg.description }}</div>
            <div class="gallery-card-tags" v-if="getPackageStyles(pkg).length">
              <el-tag v-for="tag in getPackageStyles(pkg).slice(0, 4)" :key="tag" size="small" class="gallery-tag">{{ tag }}</el-tag>
            </div>
            <div class="gallery-card-meta">
              <span class="gallery-card-author">
                <el-avatar :size="24" :src="getUrl(pkg.photographer_avatar)" class="gallery-card-avatar">
                  {{ (pkg.photographer_name || '?')[0] }}
                </el-avatar>
                <span class="gallery-card-name">{{ pkg.photographer_name || '未知摄影师' }}</span>
              </span>
              <span @click.stop>
                <FavoriteButton
                  v-if="pkg.id"
                  target-type="package"
                  :target-id="String(pkg.id)"
                  :photographer-id="pkg.photographer_id || 0"
                  :target-data="pkg"
                  class="row-like-btn"
                />
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="searchType === 'projects'" class="gallery-project-list" v-loading="loadingProjects">
      <article
        v-for="project in filteredProjects"
        :key="project.id"
        class="gallery-project-card"
        tabindex="0"
        role="link"
        @click="goProjectDetail(project)"
        @keydown.enter="goProjectDetail(project)"
        @keydown.space.prevent="goProjectDetail(project)"
      >
        <div class="gallery-project-info">
          <div class="gallery-project-heading">
            <div>
              <h3>{{ project.title }}</h3>
              <span>{{ [project.category, project.city].filter(Boolean).join(' · ') || '企划信息待补充' }}</span>
            </div>
            <span class="gallery-project-status">{{ projectStatusLabel(project.status) }}</span>
          </div>
          <p class="gallery-project-description">{{ project.description }}</p>
          <div v-if="project.style_tags?.length" class="gallery-project-tags">
            <el-tag v-for="tag in project.style_tags.slice(0, 4)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
          </div>
          <div class="gallery-project-facts">
            <div><span>预算</span><strong>{{ formatProjectBudget(project) }}</strong></div>
            <div><span>拍摄日期</span><strong>{{ formatProjectDate(project.shoot_date_start) }}</strong></div>
            <div><span>收到应邀</span><strong>{{ project.application_count || 0 }} 人</strong></div>
          </div>
        </div>
        <el-image
          v-if="project.reference_images?.length"
          :src="project.reference_images[0]"
          fit="cover"
          class="gallery-project-cover"
          :alt="`${project.title} 示意图`"
          lazy
        />
        <div v-else class="gallery-project-cover gallery-project-cover-placeholder">暂无参考图</div>
      </article>
    </div>

    <el-empty v-if="!loading && !filteredWorks.length && searchType === 'works'" :description="searchQuery ? '未搜索到相关作品' : '暂无作品'" />
    <el-empty v-if="!loadingPhotographers && !filteredPhotographers.length && searchType === 'photographers'" description="未搜索到相关摄影师" />
    <el-empty v-if="!loadingPackages && !filteredPackages.length && searchType === 'packages'" description="未搜索到相关方案" />
    <el-empty v-if="!loadingProjects && !filteredProjects.length && searchType === 'projects'" description="未搜索到相关企划" />

    <!-- 发布作品入口 -->
    <el-button
      class="gallery-upload-fab"
      circle
      size="large"
      type="primary"
      aria-label="上传作品"
      @click="goUploadWork"
    >
      <el-icon :size="24"><Plus /></el-icon>
    </el-button>
  </div>
</template>

<script setup>
import { computed, reactive, onActivated, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAllPackages, getAllWorks, getPhotographerList } from '../api/photographer'
import { getProjects } from '../api/project'
import { getRecommendedPackages, getRecommendedWorks, trackRecommendationEvents } from '../api/recommendation'
import { Play as VideoPlay, Plus } from 'lucide-vue-next'
import LikeButton from '../components/LikeButton.vue'
import FavoriteButton from '../components/FavoriteButton.vue'
import { useLikeStore } from '@/stores/like'
import { useFavoriteStore } from '@/stores/favorite'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { getPackagePreviewUrl, getVideoStreamUrl, getWorkPreviewUrl, isVideoWork } from '@/utils/imagePreview'
import { resolveRouteScrollPosition } from '@/router/scrollRestoration'

defineOptions({ name: 'Gallery' })

const router = useRouter()
const route = useRoute()
const likeStore = useLikeStore()
const favStore = useFavoriteStore()
const works = ref([])
const loading = ref(false)
const worksLoaded = ref(false)
const searchType = ref('works')
const photographers = ref([])
const loadingPhotographers = ref(false)
const photographersLoaded = ref(false)
const packages = ref([])
const loadingPackages = ref(false)
const packagesLoaded = ref(false)
const projects = ref([])
const loadingProjects = ref(false)
const projectsLoaded = ref(false)
const recommendationMeta = ref(null)
const packageRecommendationMeta = ref(null)
let recommendationSessionId = ''
let impressionObserver = null
let packageImpressionObserver = null

// ---- 方案封面动态裁剪比例 ----
const { getOrPreload: getPkgOrPreload, preloadAll: preloadPkgAll } = useImageAspectRatio()

// ---- 响应式窗口宽度 ----
const windowWidth = ref(window.innerWidth)
const updateWindowWidth = () => { windowWidth.value = window.innerWidth }
onMounted(() => { window.addEventListener('resize', updateWindowWidth) })
onUnmounted(() => {
  window.removeEventListener('resize', updateWindowWidth)
  impressionObserver?.disconnect()
  packageImpressionObserver?.disconnect()
})

// ---- 瀑布流作品卡片动态裁剪比例 ----
// 规则: ratio > 4/3 → 4:3  /  ratio < 3/4 → 3:4  /  其余 → 1:1
const workAspectRatios = reactive({})

const preloadWorkImage = (work) => {
  const key = work.id || work.url
  if (workAspectRatios[key] !== undefined) return
  const previewUrl = getWorkPreviewUrl(work)
  if (!previewUrl) {
    workAspectRatios[key] = isVideoWork(work) ? 16 / 9 : 1
    return
  }
  const img = new Image()
  img.onload = () => {
    if (img.naturalWidth && img.naturalHeight) {
      workAspectRatios[key] = img.naturalWidth / img.naturalHeight
    }
  }
  img.onerror = () => {
    workAspectRatios[key] = 1 // fallback 1:1
  }
  img.src = previewUrl
}

const getWorkCardRatio = (work) => {
  const key = work.id || work.url
  const ratio = workAspectRatios[key]
  if (ratio === undefined) {
    preloadWorkImage(work)
    return '1/1'
  }
  if (ratio > 4 / 3) return '4/3'
  if (ratio < 3 / 4) return '3/4'
  return '1/1'
}

watch(works, (list) => {
  if (list && list.length) list.forEach(preloadWorkImage)
})

// 方案封面预加载
watch(packages, (list) => {
  if (list && list.length) {
    preloadPkgAll(list,
      (pkg) => getPackageCoverPreviewUrl(pkg),
      (pkg) => pkg.id || pkg.package_name || ''
    )
  }
})

const searchQuery = computed(() => route.query.q || '')

const filteredWorks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return works.value
  return works.value.filter((work) => {
    const title = (work.title || '').toLowerCase()
    const name = (work.user_display_name || '').toLowerCase()
    const desc = (work.description || '').toLowerCase()
    const tag = (work.tag || '').toLowerCase()
    return title.includes(q) || name.includes(q) || desc.includes(q) || tag.includes(q)
  })
})

const filteredPhotographers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return photographers.value.filter((photographer) => {
    const name = (photographer.user_display_name || '').toLowerCase()
    const styles = (photographer.styles || []).join(' ').toLowerCase()
    const location = (photographer.location || '').toLowerCase()
    return name.includes(q) || styles.includes(q) || location.includes(q)
  })
})

const filteredPackages = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return packages.value.filter((pkg) => {
    const name = (pkg.package_name || '').toLowerCase()
    const desc = (pkg.description || '').toLowerCase()
    const photographer = (pkg.photographer_name || '').toLowerCase()
    const styles = getPackageStyles(pkg).join(' ').toLowerCase()
    return name.includes(q) || desc.includes(q) || photographer.includes(q) || styles.includes(q)
  })
})

const filteredProjects = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  return projects.value.filter((project) => {
    const searchableText = [
      project.title,
      project.description,
      project.category,
      project.city,
      project.location_text,
      project.location_name,
      project.location_address,
      project.customer_name,
      ...(Array.isArray(project.style_tags) ? project.style_tags : []),
    ].filter(Boolean).join(' ').toLowerCase()
    return searchableText.includes(q)
  })
})

const searchFilterOptions = computed(() => [
  { key: 'works', label: '作品', count: worksLoaded.value ? filteredWorks.value.length : null },
  { key: 'photographers', label: '摄影师', count: photographersLoaded.value ? filteredPhotographers.value.length : null },
  { key: 'packages', label: '方案', count: packagesLoaded.value ? filteredPackages.value.length : null },
  { key: 'projects', label: '企划', count: projectsLoaded.value ? filteredProjects.value.length : null },
])

const fetchWorks = async () => {
  if (loading.value || worksLoaded.value) return
  loading.value = true
  try {
    if (!searchQuery.value) {
      try {
        recommendationSessionId = sessionStorage.getItem('recommendation-session-id') || crypto.randomUUID()
        sessionStorage.setItem('recommendation-session-id', recommendationSessionId)
        const res = await getRecommendedWorks({ scene: 'gallery_for_you', limit: 50, session_id: recommendationSessionId })
        recommendationMeta.value = res.data
        works.value = res.data.items
      } catch {
        works.value = (await getAllWorks({ limit: 200 })).data
      }
    } else {
      works.value = (await getAllWorks({ limit: 200 })).data
    }
    const ids = works.value.map((work) => work.id).filter(Boolean)
    worksLoaded.value = true
    likeStore.loadMany('portfolio', ids).catch(() => {})
    favStore.loadMany(ids)
  } finally {
    loading.value = false
  }
}

const fetchPhotographers = async () => {
  if (loadingPhotographers.value || photographersLoaded.value) return
  loadingPhotographers.value = true
  try {
    const res = await getPhotographerList({ limit: 200 })
    photographers.value = res.data
    photographersLoaded.value = true
  } finally {
    loadingPhotographers.value = false
  }
}

const fetchPackages = async () => {
  if (loadingPackages.value || packagesLoaded.value) return
  loadingPackages.value = true
  try {
    try {
      recommendationSessionId = recommendationSessionId || sessionStorage.getItem('recommendation-session-id') || crypto.randomUUID()
      sessionStorage.setItem('recommendation-session-id', recommendationSessionId)
      const res = await getRecommendedPackages({ limit: 50, session_id: recommendationSessionId })
      packageRecommendationMeta.value = res.data
      packages.value = res.data.items
    } catch {
      packages.value = (await getAllPackages()).data
    }
    packagesLoaded.value = true
    favStore.loadPkgMany(packages.value.map((pkg) => String(pkg.id)).filter(Boolean))
  } finally {
    loadingPackages.value = false
  }
}

const fetchProjects = async () => {
  if (loadingProjects.value || projectsLoaded.value) return
  loadingProjects.value = true
  try {
    projects.value = (await getProjects({ limit: 200 })).data
    projectsLoaded.value = true
  } finally {
    loadingProjects.value = false
  }
}

const ensureSearchTypeData = () => {
  if (searchType.value === 'works') {
    fetchWorks()
  } else if (searchType.value === 'photographers') {
    fetchPhotographers()
  } else if (searchType.value === 'packages') {
    fetchPackages()
  } else if (searchType.value === 'projects') {
    fetchProjects()
  }
}

const getUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getPackageStyles = (pkg) => pkg.styles || pkg.includes || []

const getPackageCoverPreviewUrl = (pkg) => getPackagePreviewUrl(pkg)

const getAvatarUrl = (work) => {
  if (!work.user_avatar_url) return ''
  return work.user_avatar_url.startsWith('http') ? work.user_avatar_url : work.user_avatar_url
}

const getProfileWorkUrl = (profile, index) => {
  if (profile.portfolio && profile.portfolio[index]) {
    return getWorkPreviewUrl(profile.portfolio[index])
  }
  return ''
}

const getProfileAvatarUrl = (profile) => {
  if (!profile.user_avatar_url) return ''
  return profile.user_avatar_url.startsWith('http') ? profile.user_avatar_url : profile.user_avatar_url
}

const getWorkAnchorKey = (work) => String(work?.id || work?.url || '')

const openWork = (work) => {
  if (work.id) {
    if (recommendationMeta.value) {
      trackRecommendationEvents([buildRecommendationEvent(work, 'portfolio_click')]).catch(() => {})
    }
    router.push({
      name: 'WorkDetail',
      params: { workId: work.id },
      state: { from: route.fullPath },
    })
  }
}

const goDetail = (userId) => {
  router.push(`/photographer/${userId}`)
}

const goPackageDetail = (pkg) => {
  if (packageRecommendationMeta.value) {
    trackRecommendationEvents([buildPackageRecommendationEvent(pkg, 'package_click')]).catch(() => {})
  }
  router.push({
    path: `/package/${pkg.id}`,
    state: { from: router.currentRoute.value.fullPath },
  })
}

const goProjectDetail = (project) => {
  if (project?.id) router.push(`/projects/${project.id}`)
}

const projectStatusLabel = (value) => ({
  open: '招募中',
  expired: '已过期',
  converted: '已转订单',
}[value] || value || '状态待定')

const formatProjectBudget = (project) => {
  if (project?.budget_min && project?.budget_max) return `¥${project.budget_min} - ¥${project.budget_max}`
  if (project?.budget_min) return `¥${project.budget_min} 起`
  if (project?.budget_max) return `¥${project.budget_max} 内`
  return '预算待沟通'
}

const formatProjectDate = (value) => value
  ? new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  : '时间待沟通'

const buildPackageRecommendationEvent = (pkg, eventType, position = null) => ({
  event_type: eventType,
  target_type: 'package',
  target_id: String(pkg.id),
  owner_user_id: pkg.photographer_id,
  recommendation_id: packageRecommendationMeta.value?.recommendation_id,
  session_id: recommendationSessionId,
  scene: 'gallery_packages',
  position: position ?? packages.value.findIndex((item) => item.id === pkg.id),
  algorithm_version: packageRecommendationMeta.value?.algorithm_version,
  candidate_source: pkg.candidate_source,
})

const observePackageRecommendationCards = async () => {
  packageImpressionObserver?.disconnect()
  if (!packageRecommendationMeta.value || searchType.value !== 'packages') return
  await nextTick()
  packageImpressionObserver = new IntersectionObserver((entries) => {
    entries.filter((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5).forEach((entry) => {
      const position = Number(entry.target.dataset.packageRecommendationPosition)
      const pkg = filteredPackages.value[position]
      window.setTimeout(() => {
        if (pkg && entry.target.isConnected) trackRecommendationEvents([buildPackageRecommendationEvent(pkg, 'package_impression', position)]).catch(() => {})
      }, 500)
      packageImpressionObserver?.unobserve(entry.target)
    })
  }, { threshold: 0.5 })
  document.querySelectorAll('[data-package-recommendation-position]').forEach((element) => packageImpressionObserver.observe(element))
}

const goUploadWork = () => {
  router.push('/upload-work')
}

const buildRecommendationEvent = (work, eventType, position = null) => ({
  event_type: eventType,
  target_type: 'portfolio',
  target_id: String(work.id),
  owner_user_id: work.photographer_id || work.user_id,
  recommendation_id: recommendationMeta.value?.recommendation_id,
  session_id: recommendationSessionId,
  scene: 'gallery_for_you',
  position: position ?? works.value.findIndex((item) => item.id === work.id),
  algorithm_version: recommendationMeta.value?.algorithm_version,
  candidate_source: work.candidate_source,
})

const observeRecommendationCards = async () => {
  impressionObserver?.disconnect()
  if (!recommendationMeta.value) return
  await nextTick()
  impressionObserver = new IntersectionObserver((entries) => {
    entries.filter((entry) => entry.isIntersecting && entry.intersectionRatio >= 0.5).forEach((entry) => {
      const position = Number(entry.target.dataset.recommendationPosition)
      const work = filteredWorks.value[position]
      window.setTimeout(() => {
        if (work && entry.target.isConnected) {
          trackRecommendationEvents([buildRecommendationEvent(work, 'portfolio_impression', position)]).catch(() => {})
        }
      }, 500)
      impressionObserver?.unobserve(entry.target)
    })
  }, { threshold: 0.5 })
  document.querySelectorAll('[data-recommendation-position]').forEach((element) => impressionObserver.observe(element))
}

onMounted(() => {
  ensureSearchTypeData()
})

onActivated(() => {
  const position = resolveRouteScrollPosition(route)
  if (position) {
    window.scrollTo({ left: position.left, top: position.top, behavior: 'auto' })
  }
})

watch(searchType, () => {
  ensureSearchTypeData()
  observePackageRecommendationCards()
})
watch(searchQuery, ensureSearchTypeData)
watch(works, () => {
  observeRecommendationCards()
})
watch(packages, observePackageRecommendationCards)
</script>

<style scoped>
/* ===== Gallery Page – E-Ink / Paper Style ===== */

.gallery-page {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-6) var(--space-4);
  color: var(--color-ink);
}

/* ---- Title Row ---- */
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: var(--border-default);
}

.page-title {
  font-family: var(--font-sans);
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--color-ink);
  margin: 0;
}

.search-type-toggle {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
  max-width: 100%;
  padding: var(--space-3);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.filter-btn {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, color 0.2s;
}

.filter-btn:hover {
  border-color: var(--color-brand);
  color: var(--color-brand);
}

.filter-btn:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.filter-btn-active {
  background: var(--color-brand);
  border-color: var(--color-brand);
  color: #fff;
}

.filter-btn-active:hover {
  background: var(--color-brand-hover);
  border-color: var(--color-brand-hover);
  color: #fff;
}

.filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1;
  transition: background 0.2s, color 0.2s;
}

.filter-btn-active .filter-count {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

/* ---- Waterfall Layout (works + packages) ---- */
.gallery-waterfall {
  column-count: 4;
  column-gap: var(--space-4);
}

.gallery-card {
  break-inside: avoid;
  margin-bottom: var(--space-4);
  cursor: pointer;
}

/* ---- Card Inner (replaces el-card) ---- */
.gallery-card-inner {
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  overflow: hidden;
}

.gallery-card:hover .gallery-card-inner {
  border-color: var(--color-ink-secondary);
  background: var(--color-paper);
}

/* ---- Card Media (image / video wrapper) ---- */
.gallery-card-media {
  overflow: hidden;
  background: var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.gallery-card-img {
  width: 100%;
  height: 100%;
  display: block;
}

.gallery-card-video {
  object-fit: cover;
  background: var(--color-ink);
}

/* ---- Video Play Overlay ---- */
.gallery-video-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-paper-light);
  pointer-events: none;
  z-index: 2;
}

.gallery-video-overlay :deep(.el-icon) {
  margin-left: 1px;
}

/* ---- Card Body ---- */
.gallery-card-body {
  padding: 12px 14px;
}

.gallery-card-title {
  font-family: var(--font-sans);
  font-size: calc(var(--text-sm) * 1.2);
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: 6px;
  line-height: var(--leading-relaxed);
}

/* ---- Card Meta Row (photographer + action) ---- */
.gallery-card-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--color-divider);
  min-height: var(--tap-target-min);
}

.gallery-card-author {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}

.gallery-card-avatar {
  flex-shrink: 0;
}

.gallery-card-name {
  font-family: var(--font-sans);
  font-size: calc(var(--text-xs) * 1.2);
  color: var(--color-ink-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-like-btn {
  flex-shrink: 0;
}

/* ---- Package Card Specific ---- */
.gallery-card-cover {
  width: 100%;
  overflow: hidden;
  background: var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
}

.gallery-cover-img {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}

.gallery-card-placeholder {
  width: 100%;
  height: 160px;
  background: var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-tertiary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}

.gallery-card-price {
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: 6px;
}

.gallery-card-desc {
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  color: var(--color-ink-secondary);
  margin-bottom: 8px;
  line-height: var(--leading-relaxed);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.gallery-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 10px;
}

/* ---- Project Search Results ---- */
.gallery-project-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  min-height: 160px;
}

.gallery-project-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-5);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.gallery-project-card:hover {
  border-color: var(--color-brand);
  background: var(--color-paper);
}

.gallery-project-card:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.gallery-project-info {
  min-width: 0;
}

.gallery-project-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.gallery-project-heading h3 {
  margin: 0 0 var(--space-1);
  color: var(--color-ink);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.gallery-project-heading > div > span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.gallery-project-status {
  flex: 0 0 auto;
  padding: 4px 8px;
  border: 1px solid var(--color-brand);
  border-radius: var(--radius-sm);
  background: var(--color-brand-light);
  color: var(--color-brand);
  font-size: var(--text-xs);
  font-weight: 600;
}

.gallery-project-description {
  display: -webkit-box;
  margin: var(--space-3) 0;
  overflow: hidden;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.gallery-project-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}

.gallery-project-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid var(--color-divider);
}

.gallery-project-facts div {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
  padding: var(--space-2) var(--space-3) 0;
  border-right: 1px solid var(--color-divider);
}

.gallery-project-facts div:first-child {
  padding-left: 0;
}

.gallery-project-facts div:last-child {
  padding-right: 0;
  border-right: 0;
}

.gallery-project-facts span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.gallery-project-facts strong {
  overflow: hidden;
  color: var(--color-ink);
  font-size: var(--text-sm);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gallery-project-cover {
  display: block;
  width: 160px;
  height: 160px;
  overflow: hidden;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.gallery-project-cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

/* ---- Photographer List ---- */
.gallery-photographer-list {
  column-count: 4;
  column-gap: var(--space-4);
}

.photographer-entry {
  break-inside: avoid;
  margin-bottom: var(--space-4);
  cursor: pointer;
}

.photographer-entry:hover .gallery-card-inner {
  border-color: var(--color-ink-secondary);
  background: var(--color-paper);
}

.photographer-images {
  display: flex;
  gap: 2px;
}

.photographer-img-cell {
  flex: 1;
  aspect-ratio: 1/1;
  overflow: hidden;
  background: var(--color-border-light);
}

.photographer-img {
  width: 100%;
  height: 100%;
  display: block;
}

.photographer-img-placeholder {
  width: 100%;
  height: 100%;
  background: var(--color-border-light);
}

.photographer-body {
  padding: 12px 14px;
}

.photographer-name-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  min-height: var(--tap-target-min);
}

.photographer-display-name {
  font-family: var(--font-sans);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-ink);
}

.photographer-display-avatar {
  flex-shrink: 0;
}

.photographer-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.photographer-bio {
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  color: var(--color-ink-secondary);
  line-height: var(--leading-relaxed);
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* ---- Floating Upload FAB ---- */
.gallery-upload-fab {
  position: fixed !important;
  bottom: 32px;
  right: 32px;
  z-index: 1000;
  width: 56px !important;
  height: 56px !important;
  font-size: 28px;
  border: var(--border-default);
  border-color: var(--color-brand);
  background: var(--color-brand) !important;
  color: var(--color-paper-light) !important;
}

.gallery-upload-fab:hover {
  background: var(--color-brand-hover) !important;
  border-color: var(--color-brand-hover);
}

/* ---- el-tag Overrides ---- */
:deep(.el-tag) {
  background: var(--color-brand-light);
  border: 1px solid var(--color-border);
  color: var(--color-brand);
  font-family: var(--font-sans);
}

/* ---- Empty State ---- */
:deep(.el-empty__description) {
  color: var(--color-ink-tertiary);
  font-family: var(--font-sans);
}

/* ---- Responsive ---- */
@media (max-width: 992px) {
  .gallery-waterfall,
  .gallery-photographer-list {
    column-count: 3;
  }

  .gallery-project-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .gallery-waterfall,
  .gallery-photographer-list {
    column-count: 2;
  }

  .gallery-page {
    padding: var(--space-4) var(--space-3);
  }

  .title-row {
    align-items: stretch;
    flex-direction: column;
  }

  .search-type-toggle {
    width: 100%;
  }

  .gallery-project-card {
    grid-template-columns: minmax(0, 1fr) 140px;
    gap: var(--space-4);
  }

  .gallery-project-cover {
    width: 140px;
    height: 140px;
  }

  .gallery-upload-fab {
    bottom: var(--space-6);
    right: var(--space-6);
    width: 48px !important;
    height: 48px !important;
  }
}

@media (max-width: 480px) {
  .gallery-waterfall,
  .gallery-photographer-list {
    column-count: 1;
  }

  .gallery-project-card {
    grid-template-columns: 1fr;
  }

  .gallery-project-cover {
    width: 100%;
    height: auto;
    aspect-ratio: 1;
    order: -1;
  }

  .gallery-project-facts {
    grid-template-columns: 1fr;
  }

  .gallery-project-facts div,
  .gallery-project-facts div:first-child,
  .gallery-project-facts div:last-child {
    padding: var(--space-2) 0;
    border-right: 0;
    border-bottom: 1px solid var(--color-divider);
  }

  .gallery-project-facts div:last-child {
    border-bottom: 0;
  }
}
</style>
