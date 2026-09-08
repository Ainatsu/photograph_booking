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
              <div class="filter-trigger" ref="filterTriggerRef">
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

          <div v-if="filterOpen" class="filter-dropdown" ref="filterPanelRef">
            <DiscoveryFilters
              v-model:city="city"
              v-model:styleFilter="styleFilter"
              v-model:budgetMin="budgetMin"
              v-model:budgetMax="budgetMax"
              :show-budget="activeSection === 'packages'"
              :visible="true"
              @reset="handleReset"
              @apply="filterOpen = false"
            />
          </div>
        </div>

        <div v-if="false" class="intro-card">
          <span class="intro-mark"><Sparkles :size="20" aria-hidden="true" /></span>
          <div>
            <strong>两种开始合作的方式</strong>
            <p>直接选择成熟方案，或浏览客户公开发布的拍摄企划。</p>
          </div>
        </div>

        <div class="page-body">
          <template v-if="activeSection === 'packages'">
            <div v-if="false" class="section-title-row">
              <div>
                <h2>摄影方案</h2>
                <p>价格、时长与交付内容提前说清楚</p>
              </div>
            </div>

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
            <div v-if="false" class="section-title-row">
              <div>
                <h2>公开企划</h2>
                <p>客户发布需求，摄影师带着方案来响应</p>
              </div>
            </div>

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
  type RefresherCustomEvent,
} from '@ionic/vue'
import { Sparkles, SlidersHorizontal } from 'lucide-vue-next'
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

onMounted(() => {
  document.addEventListener('click', onDocumentClick, true)
  void Promise.all([loadPackages(), loadProjects()])
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick, true)
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
.intro-card {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--brand-soft);
  box-shadow: var(--neu-raise);
}

.intro-mark {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
}

.intro-card strong {
  display: block;
  margin: 1px 0 4px;
  font-size: var(--text-sm);
}

.intro-card p {
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.6;
}

.top-bar-area {
  position: relative;
  min-height: calc(56px + env(safe-area-inset-top));
}

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

.filter-btn {
  position: relative;
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--ink-tertiary);
  cursor: pointer;
  transition: box-shadow var(--motion-fast), color var(--motion-fast);
}

.filter-btn.active {
  border-color: var(--brand);
  color: var(--brand);
}

.filter-btn.has-filters {
  color: var(--brand);
}

.filter-badge {
  position: absolute;
  top: -1px;
  right: -1px;
  min-width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  padding: 0 5px;
  border-radius: var(--radius-pill);
  background: var(--neu-surface-brand);
  color: var(--white);
  font-size: var(--text-2xs);
  font-weight: 700;
  line-height: 1;
  box-shadow: var(--shadow-1);
  pointer-events: none;
}

.filter-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: min(340px, 100%);
  z-index: var(--layer-dropdown);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.card-list {
  column-count: 2;
  column-gap: var(--space-3);
}

.project-list {
  display: grid;
  gap: var(--space-4);
}
</style>
