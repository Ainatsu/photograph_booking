<template>
  <ion-page>
    <DetailHeader title="企划" default-href="/tabs/profile" />

    <ion-content class="management-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="management-shell">
        <section class="management-intro">
          <span class="intro-icon"><BriefcaseBusiness :size="24" aria-hidden="true" /></span>
          <div>
            <p>Project workspace</p>
            <h1>管理自己的拍摄需求</h1>
            <small>查看应邀人数，继续编辑草稿，或在招募结束后关闭企划。</small>
          </div>
          <button type="button" class="intro-action pressable" @click="createProject">
            <Plus :size="18" aria-hidden="true" />
            新建企划
          </button>
        </section>

        <nav class="status-tabs" aria-label="企划状态筛选">
            <button
              v-for="option in projectStatusOptions"
              :key="option.value"
              type="button"
              class="pressable"
              :class="{ active: projectStatus === option.value }"
              :aria-pressed="projectStatus === option.value"
              @click="setProjectStatus(option.value)"
            >
              {{ option.label }}
            </button>
          </nav>

          <FeedSkeleton v-if="projectsLoading" :count="3" />
          <StatePanel
            v-else-if="projectsError"
            tone="error"
            title="企划列表加载失败"
            :description="projectsError"
            action-label="重新加载"
            @action="loadProjects"
          />
          <StatePanel
            v-else-if="!projects.length"
            :title="projectStatus === 'all' ? '还没有发布过企划' : '这个状态下暂无企划'"
            :description="projectStatus === 'all' ? '先写下拍摄时间、预算与交付需求，再等待摄影师提交方案。' : '切换其他状态查看，或新建一份拍摄需求。'"
            :action-label="projectStatus === 'all' ? '新建企划' : '查看全部'"
            @action="projectStatus === 'all' ? createProject() : setProjectStatus('all')"
          />

          <section v-else class="management-list" aria-label="我的企划列表">
            <article v-for="project in projects" :key="project.id" class="management-card">
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

              <footer class="card-actions">
                <button type="button" class="pressable" :disabled="busyProjectId !== null" @click="openProject(project)">
                  <ChevronRight :size="17" aria-hidden="true" />查看详情
                </button>
                <button
                  v-if="project.converted_order_id"
                  type="button"
                  class="primary pressable"
                  :disabled="busyProjectId !== null"
                  @click="openOrder(project.converted_order_id)"
                >
                  <TicketCheck :size="17" aria-hidden="true" />关联订单
                </button>
                <button
                  v-if="canEditProject(project)"
                  type="button"
                  class="pressable"
                  :disabled="busyProjectId !== null"
                  @click="editProject(project)"
                >
                  <FilePenLine :size="17" aria-hidden="true" />{{ project.status === 'draft' ? '继续编辑' : project.status === 'expired' ? '更新并重发' : '编辑企划' }}
                </button>
                <button
                  v-if="canPublishProject(project) && project.status === 'draft'"
                  type="button"
                  class="primary pressable"
                  :disabled="busyProjectId !== null"
                  @click="confirmPublish(project)"
                >
                  <ion-spinner v-if="busyProjectId === project.id && busyAction === 'publish'" name="crescent" aria-hidden="true" />
                  <Send v-else :size="17" aria-hidden="true" />发布草稿
                </button>
                <button
                  v-if="canCloseProject(project)"
                  type="button"
                  class="danger pressable"
                  :disabled="busyProjectId !== null"
                  @click="confirmClose(project)"
                >
                  <ion-spinner v-if="busyProjectId === project.id && busyAction === 'close'" name="crescent" aria-hidden="true" />
                  <XCircle v-else :size="17" aria-hidden="true" />关闭企划
                </button>
              </footer>
            </article>
          </section>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2800"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  alertController,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  BriefcaseBusiness,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  FilePenLine,
  MapPin,
  Plus,
  Send,
  TicketCheck,
  UsersRound,
  XCircle,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  closeProject,
  getMyProjects,
  publishProject,
} from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import type { ProjectBrief } from '@/types/discovery'
import { formatProjectBudget, formatShortDate } from '@/utils/format'
import { resolveMediaUrl } from '@/utils/media'
import {
  canCloseProject,
  canEditProject,
  canPublishProject,
  projectStatusLabel,
  projectStatusOptions,
} from '@/utils/project'

type BusyAction = 'publish' | 'close' | ''

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const projectStatus = ref('all')
const projects = ref<ProjectBrief[]>([])
const projectsLoading = ref(false)
const projectsError = ref('')
const toastMessage = ref('')
const busyProjectId = ref<number | null>(null)
const busyAction = ref<BusyAction>('')

function statusParam(value: string) {
  return value === 'all' ? undefined : value
}

async function loadProjects() {
  projectsLoading.value = true
  projectsError.value = ''
  try {
    projects.value = await getMyProjects(statusParam(projectStatus.value))
  } catch (error) {
    projects.value = []
    projectsError.value = getApiErrorMessage(error)
  } finally {
    projectsLoading.value = false
  }
}

async function setProjectStatus(status: string) {
  if (projectStatus.value === status && projects.value.length) return
  projectStatus.value = status
  await router.replace({ query: { ...route.query, projectStatus: status } })
  await loadProjects()
}

function createProject() {
  void router.push({ name: 'publish-project' })
}

function openProject(project: ProjectBrief) {
  void router.push({ name: 'project-detail', params: { projectId: project.id } })
}

function editProject(project: ProjectBrief) {
  void router.push({ name: 'project-edit', params: { projectId: project.id } })
}

function openOrder(orderId: number) {
  void router.push({ name: 'order-detail', params: { orderId } })
}

async function confirmAction(header: string, message: string, confirmText: string, destructive = false) {
  const alert = await alertController.create({
    header,
    message,
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: confirmText, role: destructive ? 'destructive' : 'confirm' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === (destructive ? 'destructive' : 'confirm')
}

async function confirmPublish(project: ProjectBrief) {
  const confirmed = await confirmAction(
    project.status === 'expired' ? '重新发布企划' : '发布企划草稿',
    '发布后会出现在公开企划列表，并开始接收摄影师应邀。请确认时间、预算和联系方式描述准确。',
    '确认发布',
  )
  if (!confirmed) return

  busyProjectId.value = project.id
  busyAction.value = 'publish'
  try {
    await publishProject(project.id)
    toastMessage.value = project.status === 'expired' ? '企划已重新发布' : '企划已发布'
    await loadProjects()
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    busyProjectId.value = null
    busyAction.value = ''
  }
}

async function confirmClose(project: ProjectBrief) {
  const confirmed = await confirmAction(
    '关闭企划',
    project.status === 'open'
      ? '关闭后将停止接收应邀，尚未选中的摄影师方案会结束处理。此操作不可撤销。'
      : '关闭后这份草稿将不能继续编辑或发布。此操作不可撤销。',
    '确认关闭',
    true,
  )
  if (!confirmed) return

  busyProjectId.value = project.id
  busyAction.value = 'close'
  try {
    await closeProject(project.id, '客户在移动端关闭企划')
    toastMessage.value = '企划已关闭'
    await loadProjects()
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    busyProjectId.value = null
    busyAction.value = ''
  }
}

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

async function refresh(event: RefresherCustomEvent) {
  await loadProjects()
  await event.target.complete()
}

onMounted(async () => {
  await auth.initialize()
  const requestedProjectStatus = String(route.query.projectStatus || 'all')
  projectStatus.value = projectStatusOptions.some((option) => option.value === requestedProjectStatus)
    ? requestedProjectStatus
    : 'all'
  await loadProjects()
})
</script>

<style scoped>
.management-content { --background: var(--paper); }
.management-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-4) var(--space-4) calc(var(--space-8) + env(safe-area-inset-bottom)); }
.management-intro { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.intro-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: var(--radius-md); background: var(--brand-soft); color: var(--brand); }
.management-intro div { min-width: 0; }
.management-intro p { margin: 0 0 3px; color: var(--brand); font-size: var(--text-2xs); font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.management-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); line-height: 1.4; }
.management-intro small { display: block; margin-top: 5px; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.intro-action { display: inline-flex; grid-column: 1 / -1; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font-weight: 750; }
.status-tabs { display: flex; gap: var(--space-2); margin: var(--space-4) calc(var(--space-4) * -1); padding: 0 var(--space-4) var(--space-2); overflow-x: auto; scrollbar-width: none; }
.status-tabs::-webkit-scrollbar { display: none; }
.status-tabs button { min-width: max-content; min-height: 44px; padding: 0 var(--space-4); border: 0; border-radius: var(--radius-pill); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 700; }
.status-tabs button.active { border-color: var(--brand); background: var(--brand-soft); color: var(--brand); }
.management-list { display: grid; gap: var(--space-4); }
.management-card { overflow: hidden; border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.card-main { display: grid; grid-template-columns: 96px minmax(0, 1fr); width: 100%; gap: var(--space-3); padding: var(--space-4); border: 0; background: transparent; color: inherit; text-align: left; }
.card-main.without-cover { grid-template-columns: 1fr; }
.project-cover { width: 96px; height: 112px; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); object-fit: cover; }
.card-copy { min-width: 0; }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.status-badge { display: inline-flex; min-height: 27px; align-items: center; padding: 3px 9px; border-radius: var(--radius-pill); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); font-size: var(--text-2xs); font-weight: 800; }
.status-badge.open, .status-badge.selected { background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); border: 0; }
.status-badge.expired { background: #f4ead8; color: var(--warning); }
.status-badge.rejected, .status-badge.withdrawn, .status-badge.closed, .status-badge.cancelled { background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); }
.card-date { flex: 0 0 auto; color: var(--ink-tertiary); font-size: var(--text-2xs); font-variant-numeric: tabular-nums; }
.card-copy h2 { margin: var(--space-2) 0 5px; font-family: var(--font-serif); font-size: var(--text-base); line-height: 1.45; }
.card-copy p { display: -webkit-box; margin: 0; overflow: hidden; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.fact-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-top: 1px solid var(--divider); border-bottom: 1px solid var(--divider); }
.fact-grid > div { display: grid; grid-template-columns: 24px minmax(0, 1fr); min-height: 68px; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); color: var(--brand); }
.fact-grid > div:nth-child(odd) { border-right: 1px solid var(--divider); }
.fact-grid > div:nth-child(-n + 2) { border-bottom: 1px solid var(--divider); }
.fact-grid span { display: grid; min-width: 0; gap: 2px; }
.fact-grid small { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.fact-grid strong { overflow: hidden; color: var(--ink); font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.card-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); padding: var(--space-3); }
.card-actions button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 6px; padding: 0 var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 750; }
.card-actions button.primary { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); border: 0; }
.card-actions button.danger { border-color: color-mix(in srgb, var(--danger) 35%, transparent); color: var(--danger); }
.card-actions button:disabled { opacity: .55; }
.card-actions ion-spinner { width: 18px; height: 18px; }
@media (max-width: 374px) { .card-main { grid-template-columns: 80px minmax(0, 1fr); } .project-cover { width: 80px; height: 104px; } .card-actions { grid-template-columns: 1fr; } }
</style>
