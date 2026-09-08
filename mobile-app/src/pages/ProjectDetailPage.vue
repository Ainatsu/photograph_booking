<template>
  <ion-page>
    <DetailHeader title="企划详情" default-href="/tabs/showcase">
      <template #action>
        <DetailAgentAction
          aria-label="引用当前企划询问 Agent"
          :disabled="agentDisabled"
          @open="openAgent"
        />
        <button v-if="canEdit" type="button" class="header-action pressable" aria-label="编辑企划" @click="goEdit">
          <FilePenLine :size="20" aria-hidden="true" />
        </button>
        <button type="button" class="header-action" aria-label="分享企划" @click="shareProject">
          <Share2 :size="20" aria-hidden="true" />
        </button>
      </template>
    </DetailHeader>

    <ion-content class="detail-content">
      <main class="detail-shell">
        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="企划加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="project">
          <ImageCarousel
            v-if="referenceUrls.length"
            :images="referenceUrls"
            :alt-prefix="project.title"
          />

          <section class="summary-section">
            <div class="label-row">
              <span class="status" :class="project.status">{{ statusLabel }}</span>
              <span>{{ project.category || '拍摄企划' }}</span>
            </div>
            <h1>{{ project.title }}</h1>
            <strong class="budget">{{ formatProjectBudget(project) }}</strong>
            <p>{{ project.description }}</p>
            <div v-if="project.style_tags?.length" class="tag-list">
              <span v-for="tag in project.style_tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </section>

          <section class="facts-list">
            <div>
              <span class="fact-icon"><CalendarDays :size="19" aria-hidden="true" /></span>
              <span><small>期望日期</small><strong>{{ dateLabel }}</strong></span>
            </div>
            <div>
              <span class="fact-icon"><Clock3 :size="19" aria-hidden="true" /></span>
              <span><small>预计时长</small><strong>{{ formatDuration(project.duration_minutes) }}</strong></span>
            </div>
            <div>
              <span class="fact-icon"><UsersRound :size="19" aria-hidden="true" /></span>
              <span><small>摄影师响应</small><strong>{{ project.application_count || 0 }} 人</strong></span>
            </div>
          </section>

          <section v-if="hasLocation" class="location-section" aria-labelledby="detail-location-title">
            <h2 id="detail-location-title"><MapPin :size="18" aria-hidden="true" /> 拍摄地点</h2>
            <div class="location-map-wrap">
              <LocationMap
                :latitude="Number(project.location_latitude)"
                :longitude="Number(project.location_longitude)"
                aria-label="企划拍摄地点地图"
              />
            </div>
            <div class="location-copy">
              <strong>{{ locationLabel }}</strong>
              <span v-if="project.location_address">{{ project.location_address }}</span>
            </div>
          </section>

          <section class="customer-card">
            <AvatarImage :src="project.customer_avatar_url" :name="project.customer_name" :size="48" />
            <div>
              <small>企划发布者</small>
              <strong>{{ project.customer_name || '平台用户' }}</strong>
              <span>需求与预算将在订单确认时形成不可变快照</span>
            </div>
          </section>

          <section v-if="isPhotographer && !isOwner && myApplication" class="application-section my-application-section">
            <div class="application-heading">
              <div>
                <h2>我的应邀方案</h2>
                <p>客户可以看到你的报价、执行说明和相关作品。</p>
              </div>
              <span class="application-status" :class="myApplication.status">{{ applicationStatusLabel(myApplication.status) }}</span>
            </div>
            <article class="application-card">
              <div class="application-price"><span>本次报价</span><strong>{{ formatCurrency(myApplication.price_quote) }}</strong></div>
              <div v-if="myApplication.package_snapshot" class="package-snapshot"><small>关联方案</small><strong>{{ myApplication.package_snapshot }}</strong></div>
              <p class="application-proposal">{{ myApplication.proposal_text }}</p>
              <p v-if="myApplication.revision_note" class="application-note">条款事项：{{ myApplication.revision_note }}</p>
              <div v-if="applicationPortfolio(myApplication).length" class="application-portfolio">
                <img v-for="(item, index) in applicationPortfolio(myApplication)" :key="item.url" :src="resolveMediaUrl(item.thumbnail_url || item.url)" :alt="item.title || `应邀作品 ${index + 1}`" loading="lazy" />
              </div>
            </article>
          </section>

          <section v-if="!isOwner" class="response-note">
            <Lightbulb :size="20" aria-hidden="true" />
            <div>
              <strong>摄影师响应建议</strong>
              <p>结合对应作品、可执行日期、报价与交付方式提交方案，避免只发送简单问候。</p>
            </div>
          </section>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2500"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <DetailActionBar
      v-if="project && !loading"
      :primary-label="primaryActionLabel"
      :primary-disabled="primaryActionDisabled"
      :secondary-label="canContactPublisher ? '联系发布者' : undefined"
      @primary="handlePrimaryAction"
      @secondary="goConversation"
    >
      <template #primary-icon>
        <ClipboardCheck v-if="isOwner && project?.converted_order_id" :size="18" aria-hidden="true" />
        <UsersRound v-else-if="isOwner && project?.status === 'open'" :size="18" aria-hidden="true" />
        <FilePenLine v-else-if="isOwner" :size="18" aria-hidden="true" />
        <Send v-else :size="18" aria-hidden="true" />
      </template>
      <template #secondary-icon><MessageCircle :size="18" aria-hidden="true" /></template>
    </DetailActionBar>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonToast } from '@ionic/vue'
import {
  CalendarDays,
  ClipboardCheck,
  Clock3,
  FilePenLine,
  Lightbulb,
  MapPin,
  MessageCircle,
  Send,
  Share2,
  UsersRound,
} from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailActionBar from '@/components/DetailActionBar.vue'
import DetailAgentAction from '@/components/DetailAgentAction.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import ImageCarousel from '@/components/ImageCarousel.vue'
import LocationMap from '@/components/location/LocationMap.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getProjectDetail } from '@/api/discovery'
import { useAuthStore } from '@/stores/auth'
import type { ProjectApplication, ProjectBrief, ProjectPortfolioReference } from '@/types/discovery'
import { formatCurrency, formatDuration, formatProjectBudget } from '@/utils/format'
import { resolveMediaUrl } from '@/utils/media'
import { buildProjectPageContext, stageAIPageContext } from '@/utils/aiPageContext'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const project = ref<ProjectBrief | null>(null)
const myApplication = ref<ProjectApplication | null>(null)
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')

const agentDisabled = computed(() => loading.value || !!error.value || !project.value)

function openAgent() {
  if (!project.value) return
  const context = buildProjectPageContext(project.value, route)
  const handoffKey = stageAIPageContext(context)
  void router.push({ name: 'ai-assistant', query: { context: handoffKey } })
}

const referenceUrls = computed(() =>
  (project.value?.reference_images || []).filter(Boolean).map(resolveMediaUrl),
)
const coverUrl = computed(() => referenceUrls.value[0] || '')
const canContactPublisher = computed(() => Boolean(
  project.value?.customer_id && project.value.customer_id !== Number(auth.user?.id || 0),
))
const isOwner = computed(() => Boolean(project.value && auth.user?.id === project.value.customer_id))
const canEdit = computed(() => Boolean(
  isOwner.value && project.value && ['draft', 'open', 'expired'].includes(project.value.status),
))
const isPhotographer = computed(() => auth.isPhotographer)
const primaryActionLabel = computed(() => {
  if (!project.value) return '企划操作'
  if (isOwner.value) {
    if (project.value.converted_order_id) return '查看生成订单'
    if (project.value.status === 'draft') return '继续编辑草稿'
    if (project.value.status === 'expired') return '编辑并重新发布'
    if (project.value.status !== 'open') return '企划已结束'
    return '候选摄影师'
  }
  if (!auth.isAuthenticated) return '摄影师登录后响应'
  if (!isPhotographer.value) return '仅摄影师可响应'
  if (myApplication.value?.status === 'selected' && project.value.converted_order_id) return '查看生成订单'
  if (project.value.status !== 'open') return '企划已结束'
  if (myApplication.value?.status === 'submitted') return '修改应邀方案'
  return '响应这个企划'
})
const primaryActionDisabled = computed(() => {
  if (!project.value) return true
  if (isOwner.value) {
    if (project.value.converted_order_id) return false
    return !['draft', 'open', 'expired'].includes(project.value.status)
  }
  if (!auth.isAuthenticated) return false
  if (!isPhotographer.value) return true
  if (myApplication.value?.status === 'selected' && project.value.converted_order_id) return false
  return project.value.status !== 'open'
})
const locationLabel = computed(() =>
  project.value?.location_name || project.value?.location_text || project.value?.city || '地点待沟通',
)
const hasLocation = computed(() =>
  project.value?.location_address || project.value?.location_name || project.value?.location_text,
)
const statusLabel = computed(() => ({
  draft: '草稿',
  open: '招募中',
  expired: '已截止',
  converted: '已转为订单',
  closed: '已结束',
}[project.value?.status || ''] || '状态待确认'))
const dateLabel = computed(() => {
  if (!project.value?.shoot_date_start) return '时间待沟通'
  const start = new Date(project.value.shoot_date_start)
  if (Number.isNaN(start.getTime())) return '时间待沟通'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(start)
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    await auth.initialize()
    const payload = await getProjectDetail(Number(route.params.projectId))
    project.value = payload.project
    myApplication.value = payload.my_application || null
    const applicationNotice = String(route.query.application || '')
    if (applicationNotice) {
      toastMessage.value = ({
        submitted: '应邀方案已提交',
        updated: '应邀方案已更新',
        withdrawn: '应邀方案已撤回',
      }[applicationNotice] || '')
      const query = { ...route.query }
      delete query.application
      void router.replace({ query })
    }
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

function handlePrimaryAction() {
  if (!project.value) return
  if (isOwner.value) {
    if (project.value.converted_order_id) {
      void router.push({ name: 'order-detail', params: { orderId: project.value.converted_order_id } })
      return
    }
    if (project.value.status === 'open') {
      void router.push({ name: 'project-candidates', params: { projectId: project.value.id } })
      return
    }
    if (['draft', 'open', 'expired'].includes(project.value.status)) {
      void router.push({ name: 'project-edit', params: { projectId: project.value.id } })
    }
    return
  }
  if (!auth.isAuthenticated) {
    void router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (!auth.isPhotographer) {
    toastMessage.value = '当前账号不是摄影师，无法提交应邀方案。'
    return
  }
  if (myApplication.value?.status === 'selected' && project.value.converted_order_id) {
    void router.push({ name: 'order-detail', params: { orderId: project.value.converted_order_id } })
    return
  }
  if (project.value.status !== 'open') {
    toastMessage.value = '这个企划当前不再接受新的响应。'
    return
  }
  void router.push({ name: 'project-apply', params: { projectId: project.value.id } })
}

function goConversation() {
  if (!project.value || !canContactPublisher.value) return
  void router.push({
    name: 'conversation',
    params: { userId: project.value.customer_id },
    query: {
      introType: 'item',
      introTitle: project.value.title,
      introUrl: `/projects/${project.value.id}`,
      ...(coverUrl.value ? { introCoverUrl: coverUrl.value } : {}),
      introText: `你好，我想进一步了解「${project.value.title}」的拍摄需求。`,
    },
  })
}

function goEdit() {
  if (!project.value || !canEdit.value) return
  void router.push({ name: 'project-edit', params: { projectId: project.value.id } })
}

function applicationStatusLabel(status: string) {
  return ({ submitted: '已提交', selected: '已选中', rejected: '未选中', withdrawn: '已撤回' }[status] || status)
}

function applicationPortfolio(application: ProjectApplication): ProjectPortfolioReference[] {
  return Array.isArray(application.portfolio_refs)
    ? application.portfolio_refs.filter((item) => Boolean(item?.url)).slice(0, 8)
    : []
}

async function shareProject() {
  try {
    if (navigator.share) {
      await navigator.share({ title: project.value?.title, url: window.location.href })
    } else {
      await navigator.clipboard.writeText(window.location.href)
      toastMessage.value = '企划链接已复制'
    }
  } catch {
    // 用户取消系统分享时无需提示错误。
  }
}

onMounted(() => void load())
</script>

<style scoped>
.detail-content { --background: var(--paper); }
.detail-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding-bottom: var(--space-8); }

.header-action { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; background: transparent; color: var(--ink); }

.summary-section { padding: var(--space-5) var(--space-4); border-bottom: 1px solid var(--divider); }
.label-row { display: flex; align-items: center; gap: var(--space-2); color: var(--ink-tertiary); font-size: var(--text-xs); }
.status { display: inline-flex; min-height: 27px; align-items: center; padding: 3px 9px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-weight: 700; }
.status.expired, .status.closed { background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); }
.summary-section h1 { margin: var(--space-3) 0 var(--space-2); font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.45; }
.budget { display: block; color: var(--brand); font-size: 24px; font-variant-numeric: tabular-nums; }
.summary-section > p { margin: var(--space-4) 0; color: var(--ink-secondary); font-size: var(--text-base); line-height: 1.75; white-space: pre-wrap; }

.facts-list { display: grid; gap: var(--space-2); margin: var(--space-4); }
.facts-list > div { display: grid; grid-template-columns: 44px minmax(0, 1fr); align-items: center; gap: var(--space-3); min-height: 70px; padding: var(--space-3); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); }
.fact-icon { display: grid; width: 42px; height: 42px; place-items: center; border-radius: var(--radius-sm); background: var(--brand-soft); color: var(--brand); }
.facts-list > div > span:last-child { display: grid; gap: 3px; }
.facts-list small { color: var(--ink-tertiary); font-size: var(--text-xs); }
.facts-list strong { font-size: var(--text-sm); line-height: 1.45; }

/* 地点板块 */
.location-section {
  margin: var(--space-4);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  display: grid;
  gap: var(--space-3);
}
.location-section h2 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--brand);
  font-family: var(--font-serif);
  font-size: var(--text-base);
}
.location-map-wrap {
  height: 160px;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}
.location-copy {
  display: grid;
  gap: 3px;
}
.location-copy strong {
  font-size: var(--text-sm);
}
.location-copy span { color: var(--ink-secondary); font-size: var(--text-xs); }

.customer-card { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: var(--space-3); align-items: center; margin: var(--space-5) var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.customer-card > div { display: grid; gap: 3px; }
.customer-card small { color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.customer-card strong { font-size: var(--text-sm); }
.customer-card span { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }

.application-section { padding: var(--space-5) var(--space-4); border-top: 1px solid var(--divider); }
.my-application-section { background: var(--brand-soft); }
.application-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); }
.application-heading h2 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.application-heading p { margin: 4px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.55; }
.application-card { display: grid; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.application-status { display: inline-flex; min-height: 28px; flex: 0 0 auto; align-items: center; padding: 3px 9px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-2xs); font-weight: 750; }
.application-status.rejected, .application-status.withdrawn { background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); }
.application-status.selected { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.application-price { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--divider); }
.application-price span { color: var(--ink-tertiary); font-size: var(--text-xs); }
.application-price strong { color: var(--brand); font-size: var(--text-xl); font-variant-numeric: tabular-nums; }
.package-snapshot { display: grid; gap: 4px; padding: var(--space-3); border-left: 3px solid var(--brand); background: var(--brand-soft); }
.package-snapshot small { color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.package-snapshot strong { font-size: var(--text-sm); line-height: 1.5; }
.application-proposal, .application-note, .equipment-note { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.7; white-space: pre-wrap; }
.application-note, .equipment-note { padding-top: var(--space-2); border-top: 1px solid var(--divider); font-size: var(--text-xs); }
.application-portfolio { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-2); }
.application-portfolio img { width: 100%; aspect-ratio: 1 / 1; border-radius: var(--radius-sm); object-fit: cover; }
.response-note { display: flex; gap: var(--space-3); margin: 0 var(--space-4); padding: var(--space-4); border-left: 3px solid var(--brand); background: var(--brand-soft); color: var(--brand); }
.response-note strong { color: var(--ink); font-size: var(--text-sm); }
.response-note p { margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
</style>
