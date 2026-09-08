<template>
  <ion-page>
    <DetailHeader title="我的作品" default-href="/tabs/profile" />

    <ion-content class="gallery-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新作品" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="gallery-shell">
        <section class="gallery-intro">
          <span><Camera :size="23" aria-hidden="true" /></span>
          <div>
            <h1>{{ portfolioWorks.length }} 件作品</h1>
            <p>管理你的拍摄成果，发布新作让更多人看到。</p>
          </div>
          <button type="button" class="intro-action pressable" @click="router.push({ name: 'publish-work' })">
            <Plus :size="18" aria-hidden="true" />发布作品
          </button>
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
          v-else-if="!portfolioWorks.length"
          title="还没有发布过作品"
          description="上传你最具代表性的成片，展示风格和拍摄实力。"
          action-label="发布第一件作品"
          @action="router.push({ name: 'publish-work' })"
        />

        <div v-else class="work-grid">
          <WorkCard
            v-for="work in portfolioWorks"
            :key="work.id"
            :work="work"
            @open="openWork"
          />
        </div>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { IonContent, IonPage, IonRefresher, IonRefresherContent, onIonViewWillEnter, type RefresherCustomEvent } from '@ionic/vue'
import { Camera, Plus } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import WorkCard from '@/components/WorkCard.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDetail } from '@/api/discovery'
import { useAuthStore } from '@/stores/auth'
import type { WorkItem } from '@/types/discovery'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

const router = useRouter()
const auth = useAuthStore()
const portfolioWorks = ref<WorkItem[]>([])
const loading = ref(true)
const error = ref('')

async function load() {
  if (!auth.user) return
  loading.value = true
  error.value = ''
  try {
    const profile = await getPhotographerDetail(auth.user.id)
    portfolioWorks.value = profile?.portfolio || []
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  event.target.complete()
}

function openWork(work: WorkItem) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'work_detail', page: 'works_gallery' })
  void router.push({ name: 'work-detail', params: { workId: work.id } })
}

onIonViewWillEnter(async () => {
  await auth.initialize()
  await load()
})
</script>

<style scoped>
.gallery-content { --background: var(--paper); }
.gallery-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.gallery-intro { display: flex; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.gallery-intro > span { display: grid; width: 46px; height: 46px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.gallery-intro h1 { margin: 1px 0 4px; font-family: var(--font-serif); font-size: var(--text-lg); }
.gallery-intro p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.intro-action { display: inline-flex; min-height: var(--touch-target); flex: 0 0 auto; align-self: center; align-items: center; gap: 6px; margin-left: auto; padding: 0 var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font-size: var(--text-sm); font-weight: 750; }
.work-grid { columns: 2; column-gap: var(--space-3); margin-top: var(--space-5); }
</style>
