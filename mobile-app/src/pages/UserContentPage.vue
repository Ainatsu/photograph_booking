<template>
  <ion-page>
    <DetailHeader :title="pageTitle" :default-href="profileHref" />

    <ion-content class="section-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="section-shell">
        <SegmentSwitch
          v-model="activeSection"
          :items="segments"
          label="主页内容分类"
        />

        <FeedSkeleton v-if="loading" :count="4" />
        <StatePanel
          v-else-if="error"
          tone="error"
          :title="`${sectionLabel}加载失败`"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="activeSection === 'works'">
          <StatePanel
            v-if="!works.length"
            title="还没有公开作品"
            :description="`${displayName}暂时没有可浏览的作品。`"
          />
          <div v-else class="work-grid">
            <WorkCard v-for="work in works" :key="work.id" :work="work" @open="openWork" />
          </div>
        </template>

        <template v-else-if="activeSection === 'packages'">
          <StatePanel
            v-if="!packages.length"
            title="还没有上架方案"
            :description="`${displayName}暂时没有可预约的拍摄方案。`"
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
          <StatePanel
            v-if="!projects.length"
            title="还没有发布企划"
            :description="`${displayName}暂时没有公开的拍摄企划。`"
          />
          <div v-else class="project-list">
            <ProjectCard
              v-for="project in projects"
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
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PackageCard from '@/components/PackageCard.vue'
import ProjectCard from '@/components/ProjectCard.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import WorkCard from '@/components/WorkCard.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDetail, getProjects } from '@/api/discovery'
import type { PackageOffer, PhotographerProfile, ProjectBrief, WorkItem } from '@/types/discovery'
import { getProfilePackages, getProfileWorks } from '@/utils/photographerProfile'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

type UserContentSection = 'works' | 'packages' | 'projects'

const sectionLabels: Record<UserContentSection, string> = {
  works: '作品',
  packages: '方案',
  projects: '企划',
}

const route = useRoute()
const router = useRouter()
const profile = ref<PhotographerProfile | null>(null)
const projects = ref<ProjectBrief[]>([])
const loading = ref(true)
const error = ref('')

function normalizeSection(value: unknown): UserContentSection {
  const section = Array.isArray(value) ? value[0] : value
  return section === 'packages' || section === 'projects' ? section : 'works'
}

const activeSection = ref<UserContentSection>(normalizeSection(route.params.section))
const userId = computed(() => Number(route.params.userId))
const works = computed<WorkItem[]>(() => getProfileWorks(profile.value))
const packages = computed<PackageOffer[]>(() => getProfilePackages(profile.value))
const displayName = computed(() => profile.value?.user_display_name || '该用户')
const sectionLabel = computed(() => sectionLabels[activeSection.value])
const pageTitle = computed(() => `${displayName.value}的${sectionLabel.value}`)
const profileHref = computed(() => `/photographers/${route.params.userId}`)

const segments = computed(() => [
  { label: sectionLabels.works, value: 'works', count: works.value.length },
  { label: sectionLabels.packages, value: 'packages', count: packages.value.length },
  { label: sectionLabels.projects, value: 'projects', count: projects.value.length },
])

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

  // 企划数据为补充信息，失败时静默降级。
  try {
    projects.value = await getProjects({ customer_id: userId.value, limit: 50 })
  } catch {
    projects.value = []
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  event.target.complete()
}

function openWork(work: WorkItem) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'work_detail', page: 'user_content' })
  void router.push({ name: 'work-detail', params: { workId: work.id } })
}

function openPackage(offer: PackageOffer) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'package_detail', page: 'user_content' })
  void router.push({ name: 'package-detail', params: { packageId: offer.id } })
}

function openProject(project: ProjectBrief) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'project_detail', page: 'user_content' })
  void router.push({ name: 'project-detail', params: { projectId: project.id } })
}

watch(activeSection, (section) => {
  trackEvent(AnalyticsEvent.TAB_SWITCH, { tab: section, page: 'user_content' })
  if (normalizeSection(route.params.section) === section) return
  void router.replace({
    name: 'user-content',
    params: { userId: route.params.userId, section },
  })
})

watch(() => route.params.section, (value) => {
  activeSection.value = normalizeSection(value)
})

onIonViewWillEnter(() => void load())
</script>

<style scoped>
.section-content { --background: var(--paper); }
.section-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.section-shell > :not(:first-child) { margin-top: var(--space-4); }
.work-grid, .card-list { columns: 2; column-gap: var(--space-3); }
.project-list { display: grid; gap: var(--space-4); }
</style>
