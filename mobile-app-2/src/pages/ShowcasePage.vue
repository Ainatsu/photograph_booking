<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="page-shell">
        <div class="top-bar-area">
          <AppTopBar collapse-on-submit @left-action="goAI" @search="goSearch">
            <template #center>
              <SegmentSwitch
                v-model="activeSection"
                :items="segments"
                label="橱窗内容分类"
                dense
              />
            </template>

            <template #trailing>
              <div ref="filterTriggerRef" class="filter-trigger">
                <button
                  type="button"
                  class="filter-btn pressable"
                  :class="{ active: filterOpen, 'has-filters': filterActiveCount > 0 }"
                  :aria-expanded="filterOpen"
                  aria-label="高级筛选"
                  @click="filterOpen = !filterOpen"
                >
                  <SlidersHorizontal :size="19" aria-hidden="true" />
                  <span v-if="filterActiveCount" class="filter-badge" aria-hidden="true">{{ filterActiveCount }}</span>
                </button>
              </div>
            </template>
          </AppTopBar>

          <div v-if="filterOpen" ref="filterPanelRef" class="filter-dropdown">
            <DiscoveryFilters
              v-model:city="city"
              v-model:style-filter="styleFilter"
              v-model:budget-min="budgetMin"
              v-model:budget-max="budgetMax"
              :show-budget="activeSection === 'packages'"
              :visible="true"
              @reset="handleReset"
              @apply="filterOpen = false"
            />
          </div>
        </div>

        <div class="page-body">
          <template v-if="activeSection === 'packages'">
            <FeedSkeleton v-if="packagesLoading" :count="4" />
            <StatePanel
              v-else-if="packagesError"
              tone="error"
              title="方案暂时无法加载"
              :description="packagesError"
              action-label="重新加载"
              @action="loadPackages"
            />
            <StatePanel
              v-else-if="!packages.length"
              :title="query ? '没有找到相关方案' : '暂时还没有上架方案'"
              description="试着更换城市、风格或预算关键词。"
            />
            <div v-else class="card-list">
              <PackageCard
                v-for="offer in packages"
                :key="offer.id"
                :offer="offer"
                @open="openPackage"
              />
            </div>
          </template>

          <template v-else>
            <FeedSkeleton v-if="projectsLoading" :count="4" />
            <StatePanel
              v-else-if="projectsError"
              tone="error"
              title="企划暂时无法加载"
              :description="projectsError"
              action-label="重新加载"
              @action="loadProjects"
            />
            <StatePanel
              v-else-if="!projects.length"
              :title="query ? '没有找到相关企划' : '暂时没有公开企划'"
              description="客户发布新的拍摄需求后，会在这里开放摄影师响应。"
              action-label="发布拍摄需求"
              @action="goPublish"
            />
            <div v-else class="project-list">
              <ProjectCard
                v-for="(project, index) in projects"
                :key="project.id"
                :project="project"
                @open="trackProjectClick(project, index)"
              />
            </div>
          </template>
        </div>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import { SlidersHorizontal } from 'lucide-vue-next'
import AppTopBar from '@/components/AppTopBar.vue'
import DiscoveryFilters from '@/components/DiscoveryFilters.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PackageCard from '@/components/PackageCard.vue'
import ProjectCard from '@/components/ProjectCard.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPackages, getProjects } from '@/api/discovery'
import { getRecommendedProjects } from '@/api/recommendations'
import { useAuthStore } from '@/stores/auth'
import { trackImpression, trackClick } from '@/utils/recommendationEvents'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'
import type { PackageOffer, ProjectBrief } from '@/types/discovery'

type ShowcaseSection = 'packages' | 'projects'

const router = useRouter()
const route = useRoute()
const activeSection = ref<ShowcaseSection>('packages')
/**
 * 与发现页一样：参照实现里这个 ref 从未被写入，搜索框由 AppTopBar 自管。
 * 下面所有 `query ? A : B` 分支实际都落在 B 上，保留原样以免改变既有文案。
 */
const query = ref('')
const city = ref('')
const styleFilter = ref('')
const budgetMin = ref<number | null>(null)
const budgetMax = ref<number | null>(null)
const packages = ref<PackageOffer[]>([])
const projects = ref<ProjectBrief[]>([])
const packagesLoading = ref(true)
const projectsLoading = ref(true)
const packagesError = ref('')
const projectsError = ref('')
const filterOpen = ref(false)
const filterTriggerRef = ref<HTMLElement | null>(null)
const filterPanelRef = ref<HTMLElement | null>(null)

const filterActiveCount = computed(() => [
  city.value.trim(),
  styleFilter.value.trim(),
  budgetMin.value,
  budgetMax.value,
].filter((v) => v !== '' && v !== null && v !== undefined).length)

function onDocumentClick(e: MouseEvent) {
  if (!filterOpen.value) return
  const target = e.target as Node
  if (filterTriggerRef.value?.contains(target)) return
  if (filterPanelRef.value?.contains(target)) return
  filterOpen.value = false
}

const segments = [
  { label: '方案', value: 'packages' },
  { label: '企划', value: 'projects' },
]

function buildSearchParams() {
  return {
    query: query.value || undefined,
    city: city.value || undefined,
    style: styleFilter.value || undefined,
    budget_min: budgetMin.value,
    budget_max: budgetMax.value,
  }
}

/* ---------- debounce ---------- */
let loadTimer: ReturnType<typeof setTimeout> | null = null

function debouncedLoad() {
  if (loadTimer) clearTimeout(loadTimer)
  loadTimer = setTimeout(() => {
    void Promise.all([loadPackages(), loadProjects()])
  }, 300)
}

async function loadPackages() {
  packagesLoading.value = true
  packagesError.value = ''
  try {
    packages.value = await getPackages(buildSearchParams())
  } catch (error) {
    packagesError.value = getApiErrorMessage(error)
  } finally {
    packagesLoading.value = false
  }
}

async function loadProjects() {
  projectsLoading.value = true
  projectsError.value = ''
  try {
    const auth = useAuthStore()
    await auth.initialize()
    if (auth.isPhotographer) {
      projects.value = await getRecommendedProjects(buildSearchParams())
    } else {
      projects.value = await getProjects(buildSearchParams())
    }
  } catch (error) {
    projectsError.value = getApiErrorMessage(error)
  } finally {
    projectsLoading.value = false
  }
  // 记录曝光
  projects.value.forEach((project, index) => {
    trackImpression('project', project.id, { position: index, scene: 'showcase', ownerUserId: project.customer_id })
  })
}

async function refresh(event: RefresherCustomEvent) {
  await Promise.all([loadPackages(), loadProjects()])
  event.target.complete()
}

function handleReset() {
  city.value = ''
  styleFilter.value = ''
  budgetMin.value = null
  budgetMax.value = null
}

function openPackage(offer: PackageOffer) {
  router.push({ name: 'package-detail', params: { packageId: offer.id } })
}

function openProject(project: ProjectBrief) {
  router.push({ name: 'project-detail', params: { projectId: project.id } })
}

function trackProjectClick(project: ProjectBrief, index: number) {
  trackClick('project', project.id, { position: index, scene: 'showcase', ownerUserId: project.customer_id })
  openProject(project)
}

function goSearch(keyword: string) {
  if (keyword.trim()) {
    router.push({ name: 'search', query: { q: keyword.trim() } })
  }
}

function goAI() {
  router.push({ name: 'ai-assistant' })
}

function goPublish() {
  router.push({ name: 'publish-project' })
}

// document 级监听是 DOM 生命周期，用 onMounted/onUnmounted 正确
onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick, true)
})

/**
 * 取数用 onIonViewWillEnter：Ionic 缓存 Tab 页面，onMounted 只跑一次，
 * 从别的 Tab 回来就不会刷新（见 CODE.md §4.2）。
 */
onIonViewWillEnter(() => {
  void Promise.all([loadPackages(), loadProjects()])
})

watch(query, () => {
  debouncedLoad()
})

watch([city, styleFilter, budgetMin, budgetMax], () => {
  debouncedLoad()
})

watch(activeSection, (section) => {
  trackEvent(AnalyticsEvent.TAB_SWITCH, { tab: section, page: 'showcase' })
})

watch(query, (newQuery, oldQuery) => {
  if (newQuery && newQuery !== oldQuery) {
    trackEvent(AnalyticsEvent.SEARCH, { query: newQuery, page: 'showcase' })
  }
})

watch(() => route.query.section, (section) => {
  if (section === 'projects' || section === 'packages') activeSection.value = section
}, { immediate: true })
</script>

<style scoped>
.top-bar-area {
  position: relative;
  min-height: calc(56px + env(safe-area-inset-top));
}

/* 顶栏改为 fixed，好让筛选浮层相对它定位并铺满整行 */
.top-bar-area :deep(.top-bar) {
  position: fixed;
  z-index: var(--layer-sticky);
  top: 0;
  right: 0;
  left: 0;
  margin-inline: 0;
  padding-inline: max(var(--space-4), calc((100vw - var(--content-max)) / 2 + var(--space-4)));
}

.page-body {
  margin-top: var(--space-4);
}

.filter-trigger {
  flex-shrink: 0;
}

/* 与顶栏其它图标按钮同一形态，不用独立底色 */
.filter-btn {
  position: relative;
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  place-items: center;
  border: 0;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--ink);
}

.filter-btn.active,
.filter-btn.has-filters {
  color: var(--brand);
}

.filter-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  display: grid;
  min-width: 17px;
  height: 17px;
  place-items: center;
  padding: 0 4px;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: var(--on-brand);
  font-size: var(--text-2xs);
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
}

/* 浮层：描边 + 阴影，是 DESIGN.md §6 允许用阴影的少数场合之一 */
.filter-dropdown {
  position: absolute;
  z-index: var(--layer-dropdown);
  top: calc(100% + 8px);
  right: 0;
  width: min(340px, 100%);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
  box-shadow: var(--shadow-2);
}

/* 方案卡高度不一，用列布局做瀑布流 */
.card-list {
  column-count: 2;
  column-gap: var(--space-3);
}

.project-list {
  display: grid;
  gap: var(--space-3);
}
</style>
