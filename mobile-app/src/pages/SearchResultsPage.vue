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
                  v-for="(work, index) in limitedWorks"
                  :key="work.id"
                  :work="work"
                  :index="index"
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
              <div class="card-list">
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
              v-for="(work, index) in results.works"
              :key="work.id"
              :work="work"
              :index="index"
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
          <div v-else class="card-list">
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
import { computed, onMounted, ref, watch } from 'vue'
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

onMounted(() => {
  const q = route.query.q
  if (typeof q === 'string' && q.trim()) {
    query.value = q.trim()
    void doSearch()
  }
})
</script>

<style scoped>
.segment-wrap {
  margin-top: var(--space-4);
  margin-bottom: var(--space-4);
}

.result-count {
  flex: 0 0 auto;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
}

.result-section {
  margin-bottom: var(--space-6);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.section-header h3 {
  margin: 0;
  font-size: var(--text-base);
  font-weight: 700;
}

.subsection-count {
  padding: 1px 7px;
  border-radius: var(--radius-pill);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--ink-tertiary);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.work-masonry {
  columns: 2;
  column-gap: var(--space-3);
}

.photographer-list {
  display: grid;
  gap: var(--space-4);
}

.card-list {
  display: grid;
  gap: var(--space-4);
}

.view-more {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-3);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--brand);
  font-size: var(--text-sm);
  font-weight: 650;
}

.results-skeleton {
  display: grid;
  gap: var(--space-4);
}

@media (min-width: 600px) {
  .work-masonry {
    columns: 3;
  }
}
</style>
