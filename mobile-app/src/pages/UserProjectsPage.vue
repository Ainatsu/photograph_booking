<template>
  <ion-page>
    <DetailHeader :title="pageTitle" :default-href="profileHref" />

    <ion-content class="user-projects-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="user-projects-shell">
        <section class="list-intro">
          <span class="intro-icon"><BriefcaseBusiness :size="24" aria-hidden="true" /></span>
          <div>
            <p>Open projects</p>
            <h1>{{ projects.length }} 个公开企划</h1>
            <small>只展示正在招募的拍摄需求，点开可查看完整需求并提交应邀。</small>
          </div>
        </section>

        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="企划列表加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />
        <StatePanel
          v-else-if="!projects.length"
          title="还没有公开企划"
          :description="`${displayName}暂时没有正在招募的拍摄企划。`"
        />

        <section v-else class="project-list" :aria-label="`${displayName}的企划列表`">
          <article v-for="project in projects" :key="project.id" class="project-card">
            <button
              type="button"
              class="card-main pressable"
              :class="{ 'without-cover': !project.reference_images?.[0] }"
              @click="openProject(project)"
            >
              <img
                v-if="project.reference_images?.[0]"
                class="project-cover"
                :src="resolveMediaUrl(project.reference_images[0])"
                :alt="`${project.title} 参考图`"
                loading="lazy"
              />
              <div class="card-copy">
                <header class="card-heading">
                  <span class="status-badge" :class="project.status">{{ projectStatusLabel(project.status) }}</span>
                  <span class="card-date">{{ formatCreatedAt(project.updated_at || project.created_at) }}</span>
                </header>
                <h2>{{ project.title }}</h2>
                <p>{{ project.description }}</p>
              </div>
            </button>

            <div class="fact-grid">
              <div><CircleDollarSign :size="17" aria-hidden="true" /><span><small>预算</small><strong>{{ formatProjectBudget(project) }}</strong></span></div>
              <div><UsersRound :size="17" aria-hidden="true" /><span><small>收到应邀</small><strong>{{ project.application_count || 0 }} 人</strong></span></div>
              <div><MapPin :size="17" aria-hidden="true" /><span><small>地点</small><strong>{{ project.location_name || project.city || '待沟通' }}</strong></span></div>
              <div><CalendarDays :size="17" aria-hidden="true" /><span><small>拍摄日期</small><strong>{{ formatShortDate(project.shoot_date_start) }}</strong></span></div>
            </div>
          </article>
        </section>
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
import {
  BriefcaseBusiness,
  CalendarDays,
  CircleDollarSign,
  MapPin,
  UsersRound,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDetail, getProjects } from '@/api/discovery'
import type { ProjectBrief } from '@/types/discovery'
import { formatProjectBudget, formatShortDate } from '@/utils/format'
import { resolveMediaUrl } from '@/utils/media'
import { projectStatusLabel } from '@/utils/project'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

const route = useRoute()
const router = useRouter()
const projects = ref<ProjectBrief[]>([])
const ownerName = ref('')
const loading = ref(true)
const error = ref('')

const userId = computed(() => Number(route.params.userId))
const displayName = computed(() => ownerName.value || projects.value[0]?.customer_name || '该用户')
const pageTitle = computed(() => `${displayName.value}的企划`)
const profileHref = computed(() => `/photographers/${route.params.userId}`)

function formatCreatedAt(value?: string | null) {
  if (!value) return '时间待确认'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间待确认'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

async function load() {
  if (!Number.isInteger(userId.value) || userId.value <= 0) {
    error.value = '用户编号无效。'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    projects.value = await getProjects({ customer_id: userId.value, limit: 50 })
  } catch (loadError) {
    projects.value = []
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }

  // 展示名称为补充信息，失败时回退到企划里的客户名称。
  try {
    const profile = await getPhotographerDetail(userId.value)
    ownerName.value = profile.user_display_name || ''
  } catch {
    ownerName.value = ''
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  await event.target.complete()
}

function openProject(project: ProjectBrief) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'project_detail', page: 'user_projects' })
  void router.push({ name: 'project-detail', params: { projectId: project.id } })
}

onIonViewWillEnter(() => void load())
</script>

<style scoped>
.user-projects-content { --background: var(--paper); }
.user-projects-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-4) var(--space-4) calc(var(--space-8) + env(safe-area-inset-bottom)); }
.list-intro { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.intro-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: var(--radius-md); background: var(--brand-soft); color: var(--brand); }
.list-intro div { min-width: 0; }
.list-intro p { margin: 0 0 3px; color: var(--brand); font-size: 10px; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.list-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); line-height: 1.4; }
.list-intro small { display: block; margin-top: 5px; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.project-list { display: grid; gap: var(--space-4); margin-top: var(--space-4); }
.project-card { overflow: hidden; border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.card-main { display: grid; grid-template-columns: 96px minmax(0, 1fr); width: 100%; gap: var(--space-3); padding: var(--space-4); border: 0; background: transparent; color: inherit; text-align: left; }
.card-main.without-cover { grid-template-columns: 1fr; }
.project-cover { width: 96px; height: 112px; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); object-fit: cover; }
.card-copy { min-width: 0; }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.status-badge { display: inline-flex; min-height: 27px; align-items: center; padding: 3px 9px; border-radius: var(--radius-pill); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); font-size: 11px; font-weight: 800; }
.status-badge.open, .status-badge.selected { background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); border: 0; }
.status-badge.expired { background: #f4ead8; color: var(--warning); }
.card-date { flex: 0 0 auto; color: var(--ink-tertiary); font-size: 10px; font-variant-numeric: tabular-nums; }
.card-copy h2 { margin: var(--space-2) 0 5px; font-family: var(--font-serif); font-size: var(--text-base); line-height: 1.45; }
.card-copy p { display: -webkit-box; margin: 0; overflow: hidden; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.fact-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); }
.fact-grid > div { display: grid; grid-template-columns: 24px minmax(0, 1fr); min-height: 68px; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); color: var(--brand); }
.fact-grid > div:nth-child(odd) { border-right: 1px solid var(--neu-light); box-shadow: 1px 0 0 var(--neu-shade-soft); }
.fact-grid > div:nth-child(-n + 2) { border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); }
.fact-grid span { display: grid; min-width: 0; gap: 2px; }
.fact-grid small { color: var(--ink-tertiary); font-size: 10px; }
.fact-grid strong { overflow: hidden; color: var(--ink); font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 374px) { .card-main { grid-template-columns: 80px minmax(0, 1fr); } .project-cover { width: 80px; height: 104px; } }
</style>
