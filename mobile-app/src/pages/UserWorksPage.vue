<template>
  <ion-page>
    <DetailHeader :title="pageTitle" :default-href="profileHref" />

    <ion-content class="gallery-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新作品" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="gallery-shell">
        <section class="gallery-intro">
          <span><Camera :size="23" aria-hidden="true" /></span>
          <div>
            <h1>{{ works.length }} 件作品</h1>
            <p>浏览 {{ displayName }} 公开发布的拍摄成果，点开可查看完整图集。</p>
          </div>
        </section>

        <FeedSkeleton v-if="loading" :count="6" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="作品暂时无法加载"
          :description="error"
          action-label="重新加载"
          @action="load"
        />
        <StatePanel
          v-else-if="!works.length"
          title="还没有公开作品"
          :description="`${displayName}暂时没有可浏览的作品。`"
        />

        <div v-else class="work-grid">
          <WorkCard v-for="work in works" :key="work.id" :work="work" @open="openWork" />
        </div>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import { Camera } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import WorkCard from '@/components/WorkCard.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDetail } from '@/api/discovery'
import type { PhotographerProfile, WorkItem } from '@/types/discovery'
import { getProfileWorks } from '@/utils/photographerProfile'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

const route = useRoute()
const router = useRouter()
const profile = ref<PhotographerProfile | null>(null)
const loading = ref(true)
const error = ref('')

const userId = computed(() => Number(route.params.userId))
const works = computed<WorkItem[]>(() => getProfileWorks(profile.value))
const displayName = computed(() => profile.value?.user_display_name || '该用户')
const pageTitle = computed(() => `${displayName.value}的作品`)
const profileHref = computed(() => `/photographers/${route.params.userId}`)

async function load() {
  if (!Number.isInteger(userId.value) || userId.value <= 0) {
    error.value = '用户编号无效。'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    profile.value = await getPhotographerDetail(userId.value)
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  await event.target.complete()
}

function openWork(work: WorkItem) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'work_detail', page: 'user_works' })
  void router.push({ name: 'work-detail', params: { workId: work.id } })
}

onIonViewWillEnter(() => void load())
</script>

<style scoped>
.gallery-content { --background: var(--paper); }
.gallery-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.gallery-intro { display: flex; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.gallery-intro > span { display: grid; width: 46px; height: 46px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.gallery-intro h1 { margin: 1px 0 4px; font-family: var(--font-serif); font-size: var(--text-lg); }
.gallery-intro p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.work-grid { columns: 2; column-gap: var(--space-3); margin-top: var(--space-5); }
</style>
