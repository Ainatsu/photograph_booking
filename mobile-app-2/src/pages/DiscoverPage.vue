<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="page-shell">
        <AppTopBar collapse-on-submit @left-action="goAI" @search="goSearch">
          <template #center>
            <SegmentSwitch
              v-model="activeSection"
              :items="segments"
              label="发现内容分类"
              dense
            />
          </template>
        </AppTopBar>

        <div class="page-body">
          <template v-if="activeSection === 'works'">
            <FeedSkeleton v-if="worksLoading" variant="masonry" />
            <StatePanel
              v-else-if="worksError"
              tone="error"
              title="作品暂时没有加载出来"
              :description="worksError"
              action-label="重新加载"
              @action="loadWorks"
            />
            <StatePanel
              v-else-if="!works.length"
              :title="query ? '没有找到相关作品' : '还没有公开作品'"
              :description="query ? '换一个摄影风格、地点或创作者名称试试。' : '摄影师发布作品后，会在这里形成灵感画廊。'"
            />
            <div v-else class="work-masonry">
              <WorkCard
                v-for="work in works"
                :key="work.id"
                :work="work"
                @open="openWork"
              />
            </div>
          </template>

          <template v-else>
            <FeedSkeleton v-if="photographersLoading" :count="4" />
            <StatePanel
              v-else-if="photographersError"
              tone="error"
              title="摄影师列表加载失败"
              :description="photographersError"
              action-label="重新加载"
              @action="loadPhotographers"
            />
            <StatePanel
              v-else-if="!photographers.length"
              :title="query ? '没有找到相关摄影师' : '还没有摄影师入驻'"
              :description="query ? '可以尝试搜索城市或拍摄风格。' : '完成摄影师资料后，会在这里展示作品、评分和服务风格。'"
            />
            <div v-else class="photographer-list">
              <PhotographerCard
                v-for="profile in photographers"
                :key="profile.user_id"
                :profile="profile"
                @open="openPhotographer"
              />
            </div>
          </template>
        </div>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import AppTopBar from '@/components/AppTopBar.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PhotographerCard from '@/components/PhotographerCard.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import WorkCard from '@/components/WorkCard.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographers, getWorkFeed, getWorks } from '@/api/discovery'
import { getBatchLikeCounts } from '@/api/engagement'
import { debounce } from '@/utils/debounce'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'
import type { PhotographerProfile, WorkItem } from '@/types/discovery'

type DiscoverSection = 'works' | 'photographers'

const router = useRouter()
const activeSection = ref<DiscoverSection>('works')
/**
 * 参照实现里这个 ref 从来没有被写入过（搜索框由 AppTopBar 自管，只在提交时 emit），
 * 所以下面所有 `query ? A : B` 的空态文案分支实际都落在 B 上。
 * 保留原样以免改变既有文案；接站内搜索时再把它接上。
 */
const query = ref('')
const works = ref<WorkItem[]>([])
const photographers = ref<PhotographerProfile[]>([])
const worksLoading = ref(true)
const photographersLoading = ref(true)
const worksError = ref('')
const photographersError = ref('')

const segments = [
  { label: '作品', value: 'works' },
  { label: '摄影师', value: 'photographers' },
]

async function loadWorks(searchQuery?: string) {
  worksLoading.value = true
  worksError.value = ''
  try {
    works.value = searchQuery?.trim()
      ? await getWorks({ query: searchQuery.trim() })
      : await getWorkFeed()
    const workIds = works.value.map((w) => w.id).filter(Boolean)
    if (workIds.length) {
      const counts = await getBatchLikeCounts('portfolio', workIds)
      works.value = works.value.map((w) => ({
        ...w,
        like_count: counts[w.id] ?? 0,
      }))
    }
  } catch (error) {
    worksError.value = getApiErrorMessage(error)
  } finally {
    worksLoading.value = false
  }
}

async function loadPhotographers(searchQuery?: string) {
  photographersLoading.value = true
  photographersError.value = ''
  try {
    photographers.value = await getPhotographers(
      searchQuery?.trim() ? { query: searchQuery.trim() } : {},
    )
  } catch (error) {
    photographersError.value = getApiErrorMessage(error)
  } finally {
    photographersLoading.value = false
  }
}

const debouncedSearch = debounce((searchQuery: string) => {
  void loadWorks(searchQuery)
  void loadPhotographers(searchQuery)
}, 300)

watch(query, (newQuery) => {
  debouncedSearch(newQuery)
})

async function refresh(event: RefresherCustomEvent) {
  await Promise.all([loadWorks(), loadPhotographers()])
  event.target.complete()
}

function openWork(work: WorkItem) {
  if (work.id) router.push({ name: 'work-detail', params: { workId: work.id } })
}

function openPhotographer(profile: PhotographerProfile) {
  router.push({ name: 'photographer-detail', params: { userId: profile.user_id } })
}

function goSearch(keyword: string) {
  if (keyword.trim()) {
    router.push({ name: 'search', query: { q: keyword.trim() } })
  }
}

function goAI() {
  router.push({ name: 'ai-assistant' })
}

watch(activeSection, (section) => {
  trackEvent(AnalyticsEvent.TAB_SWITCH, { tab: section, page: 'discover' })
})

/**
 * 用 onIonViewWillEnter 而不是参照实现的 onMounted：Ionic 会缓存 Tab 页面，
 * onMounted 只执行一次，回到本页就永远是首次拉取的旧数据（见 CODE.md §4.2）。
 * 参照实现自身在这一点上并不一致 —— 灵感页用的是 onIonViewWillEnter。
 */
onIonViewWillEnter(() => {
  void Promise.all([loadWorks(), loadPhotographers()])
})
</script>

<style scoped>
.page-body {
  margin-top: var(--space-4);
}

/* 瀑布流：纵向间距靠卡片自身 margin，横向靠 column-gap */
.work-masonry {
  columns: 2;
  column-gap: var(--space-2);
}

.photographer-list {
  display: grid;
  gap: var(--space-4);
}

@media (min-width: 600px) {
  .work-masonry {
    columns: 3;
  }
}
</style>
