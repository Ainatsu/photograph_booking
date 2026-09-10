<template>
  <ion-page>
    <ion-content class="page-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="page-shell">
        <AppTopBar @left-action="goAI" @search="doSearchFromTop" />

        <div class="segment-wrap">
          <SegmentSwitch v-model="activeTab" :items="tabs" label="搜索结果分类" />
        </div>

        <!-- 全部结果 -->
        <template v-if="activeTab === 'all'">
          <div v-if="loading" class="results-skeleton">
            <FeedSkeleton :count="4" />
          </div>

          <StatePanel
            v-else-if="error"
            tone="error"
            title="搜索结果加载失败"
            :description="error"
            action-label="重新搜索"
            @action="doSearch"
          />

          <StatePanel
            v-else-if="totalCount === 0"
            title="没有找到相关结果"
            description="换个关键词试试，或者调整筛选条件。"
          />

          <template v-else>
            <div class="section-title-row">
              <div><h2>全部结果</h2></div>
              <span class="result-count">{{ totalCount }} 项</span>
            </div>

            <!-- 作品部分 -->
            <div v-if="results.works.length" class="result-section">
              <div class="section-header">
                <h3>作品</h3>
                <span class="subsection-count">{{ results.works.length }}</span>
              </div>
              <div class="work-masonry">
                <WorkCard
                  v-for="work in limitedWorks"
                  :key="work.id"
                  :work="work"
                  @open="openWork"
                />
              </div>
              <button
                v-if="results.works.length > 4"
                type="button"
                class="view-more pressable"
                @click="activeTab = 'works'"
              >
                查看更多作品
                <ChevronRight :size="16" aria-hidden="true" />
              </button>
            </div>

            <!-- 摄影师部分 -->
            <div v-if="results.photographers.length" class="result-section">
              <div class="section-header">
                <h3>摄影师</h3>
                <span class="subsection-count">{{ results.photographers.length }}</span>
              </div>
              <div class="photographer-list">
                <PhotographerCard
                  v-for="profile in limitedPhotographers"
                  :key="profile.user_id"
                  :profile="profile"
                  @open="openPhotographer"
                />
              </div>
              <button
                v-if="results.photographers.length > 4"
                type="button"
                class="view-more pressable"
                @click="activeTab = 'photographers'"
              >
                查看更多摄影师
                <ChevronRight :size="16" aria-hidden="true" />
              </button>
            </div>

            <!-- 方案部分 -->
            <div v-if="results.packages.length" class="result-section">
              <div class="section-header">
                <h3>方案</h3>
                <span class="subsection-count">{{ results.packages.length }}</span>
              </div>
              <div class="card-list">
                <PackageCard
                  v-for="offer in limitedPackages"
                  :key="offer.id"
                  :offer="offer"
                  @open="openPackage"
                />
              </div>
              <button
                v-if="results.packages.length > 4"
                type="button"
                class="view-more pressable"
                @click="activeTab = 'packages'"
              >
                查看更多方案
                <ChevronRight :size="16" aria-hidden="true" />
              </button>
            </div>

            <!-- 企划部分 -->
            <div v-if="results.projects.length" class="result-section">
              <div class="section-header">
                <h3>企划</h3>
                <span class="subsection-count">{{ results.projects.length }}</span>
              </div>
              <div class="project-list">
                <ProjectCard
                  v-for="project in limitedProjects"
                  :key="project.id"
                  :project="project"
                  @open="openProject"
                />
              </div>
              <button
                v-if="results.projects.length > 4"
                type="button"
                class="view-more pressable"
                @click="activeTab = 'projects'"
              >
                查看更多企划
                <ChevronRight :size="16" aria-hidden="true" />
              </button>
            </div>
          </template>
        </template>

        <!-- 作品列表 -->
        <template v-if="activeTab === 'works'">
          <div class="section-title-row">
            <div><h2>作品</h2></div>
            <span v-if="!loading" class="result-count">{{ results.works.length }} 项</span>
          </div>

          <FeedSkeleton v-if="loading" variant="masonry" />
          <StatePanel
            v-else-if="error"
            tone="error"
            title="作品加载失败"
            :description="error"
            action-label="重新搜索"
            @action="doSearch"
          />
          <StatePanel
            v-else-if="!results.works.length"
            title="没有找到相关作品"
            description="换一个关键词试试。"
          />
          <div v-else class="work-masonry">
            <WorkCard
              v-for="work in results.works"
              :key="work.id"
              :work="work"
              @open="openWork"
            />
          </div>
        </template>

        <!-- 摄影师列表 -->
        <template v-if="activeTab === 'photographers'">
          <div class="section-title-row">
            <div><h2>摄影师</h2></div>
            <span v-if="!loading" class="result-count">{{ results.photographers.length }} 位</span>
          </div>

          <FeedSkeleton v-if="loading" :count="4" />
          <StatePanel
            v-else-if="error"
            tone="error"
            title="摄影师加载失败"
            :description="error"
            action-label="重新搜索"
            @action="doSearch"
          />
          <StatePanel
            v-else-if="!results.photographers.length"
            title="没有找到相关摄影师"
            description="换一个关键词试试。"
          />
          <div v-else class="photographer-list">
            <PhotographerCard
              v-for="profile in results.photographers"
              :key="profile.user_id"
              :profile="profile"
              @open="openPhotographer"
            />
          </div>
        </template>

        <!-- 方案列表 -->
        <template v-if="activeTab === 'packages'">
          <div class="section-title-row">
            <div><h2>方案</h2></div>
            <span v-if="!loading" class="result-count">{{ results.packages.length }} 项</span>
          </div>

          <FeedSkeleton v-if="loading" :count="4" />
          <StatePanel
            v-else-if="error"
            tone="error"
            title="方案加载失败"
            :description="error"
            action-label="重新搜索"
            @action="doSearch"
          />
          <StatePanel
            v-else-if="!results.packages.length"
            title="没有找到相关方案"
            description="换一个关键词试试。"
          />
          <div v-else class="card-list">
            <PackageCard
              v-for="offer in results.packages"
              :key="offer.id"
              :offer="offer"
              @open="openPackage"
            />
          </div>
        </template>

        <!-- 企划列表 -->
        <template v-if="activeTab === 'projects'">
          <div class="section-title-row">
            <div><h2>企划</h2></div>
            <span v-if="!loading" class="result-count">{{ results.projects.length }} 项</span>
          </div>

          <FeedSkeleton v-if="loading" :count="4" />
          <StatePanel
            v-else-if="error"
            tone="error"
            title="企划加载失败"
            :description="error"
            action-label="重新搜索"
            @action="doSearch"
          />
          <StatePanel
            v-else-if="!results.projects.length"
            title="没有找到相关企划"
            description="换一个关键词试试。"
          />
          <div v-else class="project-list">
            <ProjectCard
              v-for="project in results.projects"
              :key="project.id"
              :project="project"
              @open="openProject"
            />
          </div>
        </template>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  toastController,
  type RefresherCustomEvent,
} from '@ionic/vue'
import { ChevronRight } from 'lucide-vue-next'
import AppTopBar from '@/components/AppTopBar.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PackageCard from '@/components/PackageCard.vue'
import PhotographerCard from '@/components/PhotographerCard.vue'
import ProjectCard from '@/components/ProjectCard.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import WorkCard from '@/components/WorkCard.vue'
import { getApiErrorMessage } from '@/api/client'
import { searchDiscovery } from '@/api/discovery'
import { debounce } from '@/utils/debounce'
import type { DiscoverySearchResults } from '@/api/discovery'
import type { PackageOffer, PhotographerProfile, ProjectBrief, WorkItem } from '@/types/discovery'

type SearchTab = 'all' | 'works' | 'photographers' | 'packages' | 'projects'

const router = useRouter()
const route = useRoute()

function goAI() {
  void router.push({ name: 'ai-assistant' })
}

function doSearchFromTop(keyword: string) {
  if (keyword.trim()) {
    query.value = keyword.trim()
    void doSearch()
  }
}

const query = ref('')
const activeTab = ref<SearchTab>('all')
const results = ref<DiscoverySearchResults>({
  works: [],
  photographers: [],
  packages: [],
  projects: [],
})
const loading = ref(false)
const error = ref('')

const tabs = computed(() => [
  { label: '全部', value: 'all', count: totalCount.value },
  { label: '作品', value: 'works', count: results.value.works.length },
  { label: '摄影师', value: 'photographers', count: results.value.photographers.length },
  { label: '方案', value: 'packages', count: results.value.packages.length },
  { label: '企划', value: 'projects', count: results.value.projects.length },
])

const totalCount = computed(
  () => results.value.works.length + results.value.photographers.length + results.value.packages.length + results.value.projects.length,
)

const limitedWorks = computed(() => results.value.works.slice(0, 4))
const limitedPhotographers = computed(() => results.value.photographers.slice(0, 4))
const limitedPackages = computed(() => results.value.packages.slice(0, 4))
const limitedProjects = computed(() => results.value.projects.slice(0, 4))

async function doSearch() {
  const q = query.value.trim()
  if (!q) return

  loading.value = true
  error.value = ''
  try {
    results.value = await searchDiscovery({ query: q, limit: 20 })
  } catch (err) {
    error.value = getApiErrorMessage(err)
    const toast = await toastController.create({
      message: error.value,
      duration: 3000,
      position: 'top',
      color: 'danger',
    })
    void toast.present()
  } finally {
    loading.value = false
  }
}

const debouncedSearch = debounce(doSearch, 300)

watch(query, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    debouncedSearch()
  }
})

/**
 * 搜索词的真源是 URL query，所以用 immediate watcher 覆盖首次加载。
 *
 * 参照实现这里还额外写了一个 onMounted 做同样的事 —— 那个和 immediate watcher
 * 会各发一次请求，首屏固定打两次同一个接口。本应用去掉重复的那次。
 * 也因此不需要 onIonViewWillEnter：每次带新关键词进入本页时 watcher 都会触发。
 */
watch(
  () => route.query.q,
  (q) => {
    if (typeof q === 'string' && q.trim()) {
      query.value = q.trim()
      void doSearch()
    }
  },
  { immediate: true },
)

async function refresh(event: RefresherCustomEvent) {
  await doSearch()
  event.target.complete()
}

function openWork(work: WorkItem) {
  if (work.id) router.push({ name: 'work-detail', params: { workId: work.id } })
}

function openPhotographer(profile: PhotographerProfile) {
  router.push({ name: 'photographer-detail', params: { userId: profile.user_id } })
}

function openPackage(offer: PackageOffer) {
  router.push({ name: 'package-detail', params: { packageId: offer.id } })
}

function openProject(project: ProjectBrief) {
  router.push({ name: 'project-detail', params: { projectId: project.id } })
}
</script>

<style scoped>
.segment-wrap {
  margin: var(--space-4) 0;
}

/* ── 分区标题 ── */

.section-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin: var(--space-6) 0 var(--space-3);
}

.section-title-row:first-of-type {
  margin-top: var(--space-2);
}

.section-title-row h2 {
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 700;
}

.result-count {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
}

.result-section {
  margin-top: var(--space-5);
}

.section-header {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.section-header h3 {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 700;
}

.subsection-count {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
}

/* ── 结果布局：与发现页/橱窗页同一套 ── */

.work-masonry {
  columns: 2;
  column-gap: var(--space-2);
}

.photographer-list {
  display: grid;
  gap: var(--space-4);
}

/* 方案卡高度不一，用列布局做瀑布流 */
.card-list {
  column-count: 2;
  column-gap: var(--space-3);
}

/* 企划卡是左文右图的行式卡片，单列堆叠 */
.project-list {
  display: grid;
  gap: var(--space-3);
}

.view-more {
  display: flex;
  width: 100%;
  min-height: 44px;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: var(--space-3);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  color: var(--brand);
  font-size: var(--text-sm);
  font-weight: 700;
}

.results-skeleton {
  margin-top: var(--space-4);
}

@media (min-width: 600px) {
  .work-masonry {
    columns: 3;
  }

  .card-list {
    column-count: 3;
  }
}
</style>
