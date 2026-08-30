<template>
  <ion-page>
    <DetailHeader title="摄影师主页" default-href="/tabs/discover">
      <template #action>
        <DetailAgentAction
          aria-label="引用当前摄影师询问 Agent"
          :disabled="agentDisabled"
          @open="openAgent"
        />
      </template>
    </DetailHeader>

    <ion-content class="detail-content">
      <main class="detail-shell">
        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="摄影师主页加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="profile">
          <!-- ============ 个人信息卡 ============ -->
          <section
            class="profile-card"
            :class="{ 'has-cover': Boolean(coverUrl) }"
            :style="coverUrl ? { backgroundImage: `url(${coverUrl})` } : {}"
          >
            <div class="profile-card-overlay" />
            <div class="profile-card-body">
              <div class="avatar-col">
                <div class="avatar-wrap">
                  <AvatarImage :src="profile.user_avatar_url" :name="displayName" :size="80" />
                </div>
              </div>
              <div class="info-col">
                <div class="identity">
                  <div class="identity-title">
                    <h2>{{ displayName }}</h2>
                    <BadgeCheck :size="18" aria-label="已认证摄影师" />
                  </div>
                  <p>@{{ profile.username || `user-${profile.user_id}` }}</p>
                  <p v-if="profile.user_bio" class="profile-bio">{{ profile.user_bio }}</p>
                </div>
                <div class="profile-stats">
                  <div class="profile-stat">
                    <strong>{{ loadingSocial ? '…' : followCounts.following_count }}</strong>
                    <span>关注</span>
                  </div>
                  <div class="profile-stat">
                    <strong>{{ loadingSocial ? '…' : followCounts.follower_count }}</strong>
                    <span>粉丝</span>
                  </div>
                  <div v-if="profile.location" class="profile-location">
                    <MapPin :size="14" />{{ profile.location }}
                  </div>
                </div>
              </div>
              <div v-if="!isSelf" class="follow-col">
                <button
                  type="button"
                  class="card-follow-button"
                  :class="{ active: following }"
                  :aria-label="following ? '取消关注摄影师' : '关注摄影师'"
                  :aria-pressed="following"
                  :disabled="followLoading"
                  @click="togglePhotographerFollow"
                >
                  <ion-spinner v-if="followLoading" name="crescent" aria-hidden="true" />
                  <UserCheck v-else-if="following" :size="22" aria-hidden="true" />
                  <UserPlus v-else :size="22" aria-hidden="true" />
                </button>
              </div>
            </div>
          </section>

          <SegmentSwitch v-model="activeTab" :items="tabItems" class="profile-tab-bar" />

          <!-- ============ 内容选项卡 ============ -->
          <template v-if="activeTab === 'content'">
            <div class="content-card-grid">
              <!-- 作品卡片 -->
              <button type="button" class="content-card pressable" @click="goToUserWorks">
                <div v-if="workCovers.length" class="cover-grid">
                  <div
                    v-for="(url, idx) in workCovers.slice(0, 4)"
                    :key="idx"
                    class="cover-cell"
                  >
                    <img :src="url" alt="" loading="lazy" />
                  </div>
                  <div
                    v-for="i in Math.max(0, 4 - Math.min(workCovers.length, 4))"
                    :key="'w-empty-' + i"
                    class="cover-cell cover-empty"
                  >
                    <ImageIcon :size="20" />
                  </div>
                </div>
                <div v-else class="cover-grid">
                  <div v-for="i in 4" :key="'w-ph-' + i" class="cover-cell cover-empty">
                    <ImageIcon :size="20" />
                  </div>
                </div>
                <div class="content-card-label">
                  <strong>作品</strong>
                  <small>{{ portfolioWorks.length }} 件作品</small>
                </div>
              </button>

              <!-- 方案卡片 -->
              <button type="button" class="content-card pressable" @click="goToUserPackages">
                <div v-if="packageCovers.length" class="cover-grid">
                  <div
                    v-for="(url, idx) in packageCovers.slice(0, 4)"
                    :key="idx"
                    class="cover-cell"
                  >
                    <img :src="url" alt="" loading="lazy" />
                  </div>
                  <div
                    v-for="i in Math.max(0, 4 - Math.min(packageCovers.length, 4))"
                    :key="'p-empty-' + i"
                    class="cover-cell cover-empty"
                  >
                    <Package :size="20" />
                  </div>
                </div>
                <div v-else class="cover-grid">
                  <div v-for="i in 4" :key="'p-ph-' + i" class="cover-cell cover-empty">
                    <Package :size="20" />
                  </div>
                </div>
                <div class="content-card-label">
                  <strong>方案</strong>
                  <small>{{ profilePackages.length }} 个方案</small>
                </div>
              </button>

              <!-- 企划卡片（只显示企划，不显示应邀） -->
              <button type="button" class="content-card pressable" @click="goToUserProjects">
                <div v-if="projectCovers.length" class="cover-grid">
                  <div
                    v-for="(url, idx) in projectCovers.slice(0, 4)"
                    :key="idx"
                    class="cover-cell"
                  >
                    <img :src="url" alt="" loading="lazy" />
                  </div>
                  <div
                    v-for="i in Math.max(0, 4 - Math.min(projectCovers.length, 4))"
                    :key="'pr-empty-' + i"
                    class="cover-cell cover-empty"
                  >
                    <Briefcase :size="20" />
                  </div>
                </div>
                <div v-else class="cover-grid">
                  <div v-for="i in 4" :key="'pr-ph-' + i" class="cover-cell cover-empty">
                    <Briefcase :size="20" />
                  </div>
                </div>
                <div class="content-card-label">
                  <strong>企划</strong>
                  <small>{{ projects.length }} 个企划</small>
                </div>
              </button>
            </div>
          </template>

          <!-- ============ 服务选项卡 ============ -->
          <template v-else>
            <section class="service-section">
              <div class="notice-card">
                <div class="section-heading">
                  <span class="section-icon"><ShieldCheck :size="19" aria-hidden="true" /></span>
                  <div><h3>可信度</h3><p>来自平台真实订单与客户反馈</p></div>
                </div>
                <div class="facts-grid three-col">
                  <div class="fact-item">
                    <span class="fact-value">{{ dashboardData?.trust.completed_orders ?? '--' }}</span>
                    <span class="fact-label">已完成订单</span>
                  </div>
                  <div class="fact-item">
                    <span class="fact-value">{{ formatDashboardRating(dashboardData?.trust.avg_rating) }}</span>
                    <span class="fact-label">评分<template v-if="dashboardData?.trust.rating_count">（{{ dashboardData.trust.rating_count }}）</template></span>
                  </div>
                  <div class="fact-item">
                    <span class="fact-value">{{ dashboardData?.trust.completion_rate_visible ? formatDashboardPercent(dashboardData.trust.completion_rate) : '--' }}</span>
                    <span class="fact-label">完成率</span>
                  </div>
                </div>
                <div class="trust-footer">
                  <span :class="['status-dot', dashboardData?.trust.recent_order_activity ? 'active' : 'inactive']" />
                  <span>{{ dashboardData?.trust.recent_order_activity ? '近90天有活动' : '近期暂无足够活动数据' }}</span>
                </div>
              </div>

              <div class="service-card">
                <div class="section-heading">
                  <span class="section-icon"><Camera :size="19" aria-hidden="true" /></span>
                  <div><h3>服务能力</h3><p>拍摄风格、器材与可预约方案</p></div>
                </div>
                <div class="service-list">
                  <div class="service-row">
                    <span class="service-label">拍摄风格</span>
                    <div v-if="profile.styles?.length" class="tag-list">
                      <span v-for="style in profile.styles" :key="style" class="service-tag">{{ style }}</span>
                    </div>
                    <span v-else class="service-muted">暂未填写</span>
                  </div>
                  <div class="service-row">
                    <span class="service-label">器材能力</span>
                    <span>{{ profile.equipment || '由摄影师根据拍摄方案配置' }}</span>
                  </div>
                  <div class="service-row">
                    <span class="service-label">服务地区</span>
                    <span>{{ profile.location || '以预约沟通为准' }}</span>
                  </div>
                  <div class="service-row">
                    <span class="service-label">在售方案</span>
                    <span>{{ profilePackages.length }} 个可预约方案</span>
                  </div>
                </div>
              </div>

              <div class="service-card">
                <div class="section-heading">
                  <span class="section-icon"><Clock3 :size="19" aria-hidden="true" /></span>
                  <div><h3>预约规则</h3><p>提交预约前请以方案详情和订单快照为准</p></div>
                </div>
                <div class="rule-grid">
                  <div class="rule-item"><strong>{{ formatAdvanceNotice }}</strong><span>最少提前预约</span></div>
                  <div class="rule-item"><strong>{{ profile.max_daily_bookings || 5 }} 单</strong><span>每日最多接单</span></div>
                  <div class="rule-item"><strong>{{ formatMaxBookingDate }}</strong><span>最远可预约日期</span></div>
                </div>
                <p class="service-note">档期日历展示摄影师公开标记的忙碌日期；可预约日期还会结合每日接单上限与已有订单实时校验。</p>
              </div>

              <div class="service-card calendar-card">
                <div class="section-heading">
                  <span class="section-icon"><CalendarDays :size="19" aria-hidden="true" /></span>
                  <div><h3>档期日历</h3><p>绿色为公开可约，红色为已标记忙碌</p></div>
                </div>
                <div class="month-toolbar">
                  <button type="button" class="month-button pressable" aria-label="查看上个月" :disabled="!canGoPreviousMonth" @click="shiftMonth(-1)">
                    <ChevronLeft :size="20" aria-hidden="true" />
                  </button>
                  <h4>{{ monthLabel }}</h4>
                  <button type="button" class="month-button pressable" aria-label="查看下个月" :disabled="!canGoNextMonth" @click="shiftMonth(1)">
                    <ChevronRight :size="20" aria-hidden="true" />
                  </button>
                </div>
                <div class="month-stats" aria-label="本月档期统计">
                  <span><small>可约</small><strong>{{ monthStats.free }}</strong></span>
                  <span class="busy"><small>忙碌</small><strong>{{ monthStats.busy }}</strong></span>
                  <span><small>可预约窗口</small><strong>{{ formatMaxBookingDate }}</strong></span>
                </div>
                <div class="calendar-legend" aria-label="档期状态说明">
                  <span><i />可约</span><span><i class="busy" />忙碌</span>
                </div>
                <div class="calendar-grid" role="grid" :aria-label="monthLabel">
                  <div v-for="weekday in weekdays" :key="weekday" class="weekday" role="columnheader">{{ weekday }}</div>
                  <template v-for="cell in calendarCells" :key="cell.key">
                    <div v-if="cell.isBlank" class="date-cell blank" role="gridcell" aria-hidden="true" />
                    <div
                      v-else
                      class="date-cell"
                      :class="{ busy: cell.status === 'busy', today: cell.isToday, disabled: cell.disabled }"
                      role="gridcell"
                      :aria-label="calendarCellLabel(cell)"
                    >
                      <span>{{ cell.day }}</span>
                      <small>{{ cell.disabled ? '—' : cell.status === 'busy' ? '忙碌' : '可约' }}</small>
                      <i v-if="cell.location" :title="cell.location" aria-hidden="true" />
                    </div>
                  </template>
                </div>
              </div>
            </section>
          </template>
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
      v-if="profile && !loading"
      :primary-label="profilePackages.length ? '选择档期' : '暂无可预约方案'"
      :primary-disabled="!profilePackages.length"
      secondary-label="发消息"
      @primary="goBooking"
      @secondary="goConversation"
    >
      <template #primary-icon><CalendarCheck2 :size="18" aria-hidden="true" /></template>
      <template #secondary-icon><MessageCircle :size="18" aria-hidden="true" /></template>
    </DetailActionBar>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonSpinner, IonToast } from '@ionic/vue'
import {
  BadgeCheck,
  Briefcase,
  Camera,
  CalendarCheck2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ImageIcon,
  MapPin,
  MessageCircle,
  Package,
  ShieldCheck,
  UserCheck,
  UserPlus,
} from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailActionBar from '@/components/DetailActionBar.vue'
import DetailAgentAction from '@/components/DetailAgentAction.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDetail, getProjects } from '@/api/discovery'
import { getFollowStatus, getFollowCounts, toggleFollow } from '@/api/social'
import { getPublicPhotographerDashboard } from '@/api/dashboard'
import type { PhotographerPublicDashboardResponse } from '@/api/dashboard'
import { useAuthStore } from '@/stores/auth'
import type { PackageOffer, PhotographerProfile, ProjectBrief, WorkItem } from '@/types/discovery'
import type { FollowCounts } from '@/types/social'
import { resolveMediaUrl, getWorkPreviewUrl, getPackagePreviewUrl } from '@/utils/media'
import { getProfilePackages, getProfileWorks } from '@/utils/photographerProfile'
import {
  MAX_AVAILABILITY_DAYS,
  addDays,
  addMonths,
  buildAvailabilityCalendar,
  hydrateAvailabilityDays,
  parseDateKey,
  startOfLocalDay,
  toDateKey,
  type AvailabilityCalendarCell,
} from '@/utils/availability'
import SegmentSwitch, { type SegmentItem } from '@/components/SegmentSwitch.vue'
import { buildPhotographerPageContext, stageAIPageContext } from '@/utils/aiPageContext'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const profile = ref<PhotographerProfile | null>(null)
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')
const following = ref(false)
const followLoading = ref(false)
const loadingSocial = ref(false)
const followCounts = ref<FollowCounts>({ follower_count: 0, following_count: 0 })
const dashboardData = ref<PhotographerPublicDashboardResponse | null>(null)

const projects = ref<ProjectBrief[]>([])
const activeTab = ref<'content' | 'service'>('content')
const tabItems: SegmentItem[] = [
  { label: '内容', value: 'content' },
  { label: '服务', value: 'service' },
]
const today = startOfLocalDay()
const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const currentMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))

const agentDisabled = computed(() => loading.value || !!error.value || !profile.value)

function openAgent() {
  if (!profile.value) return
  const context = buildPhotographerPageContext(profile.value, route)
  const handoffKey = stageAIPageContext(context)
  void router.push({ name: 'ai-assistant', query: { context: handoffKey } })
}

const displayName = computed(() => profile.value?.user_display_name || '摄影师')
const isSelf = computed(() => Boolean(profile.value && auth.user?.id === profile.value.user_id))
const coverUrl = computed(() =>
  resolveMediaUrl(profile.value?.background_url || profile.value?.cover_image_url),
)

const portfolioWorks = computed<WorkItem[]>(() => getProfileWorks(profile.value))

const profilePackages = computed<PackageOffer[]>(() => getProfilePackages(profile.value))

const workCovers = computed(() => {
  return portfolioWorks.value
    .map((w) => getWorkPreviewUrl(w))
    .filter(Boolean)
    .slice(0, 4)
})

const packageCovers = computed(() => {
  return profilePackages.value
    .map((p) => getPackagePreviewUrl(p))
    .filter(Boolean)
    .slice(0, 4)
})

const projectCovers = computed(() => {
  return projects.value
    .flatMap((p) => p.reference_images || [])
    .filter(Boolean)
    .slice(0, 4)
    .map((url) => resolveMediaUrl(url))
})

const availabilityDays = computed(() => hydrateAvailabilityDays(profile.value?.availability_exceptions, today))
const currentMonthStart = computed(() => new Date(today.getFullYear(), today.getMonth(), 1))
const maxBookingDate = computed(() => {
  const configured = parseDateKey(profile.value?.max_booking_date)
  return configured && configured >= today
    ? configured
    : addDays(today, MAX_AVAILABILITY_DAYS)
})
const maxMonthStart = computed(() => new Date(maxBookingDate.value.getFullYear(), maxBookingDate.value.getMonth(), 1))
const canGoPreviousMonth = computed(() => currentMonth.value > currentMonthStart.value)
const canGoNextMonth = computed(() => currentMonth.value < maxMonthStart.value)
const monthLabel = computed(() => `${currentMonth.value.getFullYear()}年${currentMonth.value.getMonth() + 1}月`)
const calendarCells = computed<AvailabilityCalendarCell[]>(() => buildAvailabilityCalendar(currentMonth.value, availabilityDays.value, { today })
  .map((cell) => ({
    ...cell,
    disabled: Boolean(cell.disabled || (cell.date && cell.date > maxBookingDate.value)),
  })))
const monthStats = computed(() => {
  const cells = calendarCells.value.filter((cell) => !cell.isBlank && !cell.disabled)
  return {
    free: cells.filter((cell) => cell.status === 'free').length,
    busy: cells.filter((cell) => cell.status === 'busy').length,
  }
})
const formatAdvanceNotice = computed(() => {
  const hours = Number(profile.value?.advance_notice ?? 24)
  if (hours >= 24 && hours % 24 === 0) return `${hours / 24} 天`
  return `${hours} 小时`
})
const formatMaxBookingDate = computed(() => {
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(maxBookingDate.value)
})

function formatDashboardRating(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return value.toFixed(1)
}

function formatDashboardPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(0)}%`
}

function calendarCellLabel(cell: AvailabilityCalendarCell) {
  const date = cell.date
  const dateLabel = date
    ? new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric' }).format(date)
    : cell.key
  if (cell.disabled) return `${dateLabel}，暂不可预约`
  return `${dateLabel}，${cell.status === 'busy' ? '忙碌' : '可约'}${cell.location ? `，所在地 ${cell.location}` : ''}`
}

function shiftMonth(months: number) {
  const next = addMonths(currentMonth.value, months)
  if (next < currentMonthStart.value || next > maxMonthStart.value) return
  currentMonth.value = next
}

function goToUserWorks() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'content_works', page: 'photographer_detail' })
  void router.push({ name: 'user-works', params: { userId: route.params.userId } })
}

function goToUserPackages() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'content_packages', page: 'photographer_detail' })
  void router.push({ name: 'user-packages', params: { userId: route.params.userId } })
}

function goToUserProjects() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'content_projects', page: 'photographer_detail' })
  void router.push({ name: 'user-projects', params: { userId: route.params.userId } })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const userId = Number(route.params.userId)
    const [detail, followStatus] = await Promise.all([
      getPhotographerDetail(userId),
      getFollowStatus(userId).catch(() => false),
    ])
    profile.value = detail
    following.value = followStatus
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }

  // Load supplementary data (silent degradation on failure)
  const userId = Number(route.params.userId)
  await Promise.all([
    loadDashboardData(userId),
    loadSocialData(userId),
    loadProjectData(userId),
  ])
}

async function loadDashboardData(userId: number) {
  try {
    dashboardData.value = await getPublicPhotographerDashboard(userId)
  } catch {
    // Dashboard data is supplementary
  }
}

async function loadSocialData(userId: number) {
  loadingSocial.value = true
  try {
    followCounts.value = await getFollowCounts(userId)
  } catch {
    followCounts.value = { follower_count: 0, following_count: 0 }
  } finally {
    loadingSocial.value = false
  }
}

async function loadProjectData(userId: number) {
  try {
    projects.value = await getProjects({ customer_id: userId, limit: 20 })
  } catch {
    projects.value = []
  }
}

async function refreshFollowStatus() {
  if (!profile.value || isSelf.value) return
  following.value = await getFollowStatus(profile.value.user_id).catch(() => false)
}

async function togglePhotographerFollow() {
  if (!profile.value || followLoading.value || isSelf.value) return
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  followLoading.value = true
  try {
    const result = await toggleFollow(profile.value.user_id)
    following.value = result.following
    profile.value.follower_count = result.follower_count
    toastMessage.value = following.value ? '已关注摄影师' : '已取消关注'
  } catch (followError) {
    toastMessage.value = getApiErrorMessage(followError)
  } finally {
    followLoading.value = false
  }
}

function goBooking() {
  const offer = profilePackages.value[0]
  if (!profile.value || !offer) return
  router.push({
    name: 'booking',
    params: { userId: profile.value.user_id },
    query: { packageId: offer.id },
  })
}

function goConversation() {
  if (!profile.value) return
  void router.push({
    name: 'conversation',
    params: { userId: profile.value.user_id },
    query: {
      introType: 'item',
      introTitle: `${displayName.value}的摄影服务`,
      introUrl: `/photographers/${profile.value.user_id}`,
      ...(coverUrl.value ? { introCoverUrl: coverUrl.value } : {}),
      introText: `你好，我想咨询你的拍摄服务和可预约档期。`,
    },
  })
}

watch(() => auth.token, () => void refreshFollowStatus())
onMounted(() => void load())
</script>

<style scoped>
.detail-content { --background: var(--paper); }
.detail-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding-bottom: var(--space-8); }

/* ===== 个人信息卡（同个人主页风格） ===== */
.profile-card {
  position: relative;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  background-size: cover;
  background-position: center;
  margin: 0 var(--space-4);
}

.profile-card-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(0,0,0,.65) 0%, rgba(0,0,0,.35) 100%);
}

.profile-card.has-cover .profile-card-overlay { background: transparent; }
.profile-card.has-cover .profile-card-body { text-shadow: 0 1px 4px rgba(0,0,0,.72); }

.profile-card-body {
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: stretch;
  min-height: 140px;
}

.avatar-col {
  display: flex;
  align-items: center;
  padding: var(--space-4);
}

.avatar-wrap {
  display: inline-flex;
}

.follow-col {
  display: flex;
  align-items: center;
  padding: var(--space-4);
}

.card-follow-button {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border: 2px solid rgba(255,255,255,.6);
  border-radius: 50%;
  background: rgba(0,0,0,.45);
  color: var(--white);
  cursor: pointer;
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
  transition: border-color .2s, background .2s;
}

.card-follow-button.active {
  border-color: rgba(255,255,255,.4);
  background: rgba(0,0,0,.55);
  color: rgba(255,255,255,.8);
}

.card-follow-button:disabled {
  opacity: .5;
  cursor: default;
}

.card-follow-button ion-spinner {
  width: 20px;
  height: 20px;
}

.info-col {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4) var(--space-4) 0;
  min-height: 120px;
}

.identity {
  min-width: 0;
}

.identity-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--brand);
}

.identity h2 {
  overflow: hidden;
  margin: 0;
  color: var(--white);
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity > p {
  margin: 4px 0 8px;
  color: rgba(255,255,255,.65);
  font-size: var(--text-xs);
}

.profile-bio {
  margin: var(--space-2) 0 0;
  color: rgba(255,255,255,.85);
  font-size: var(--text-sm);
  line-height: 1.65;
}

.profile-stats {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.profile-stat {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(255,255,255,.25);
  border-radius: var(--radius-pill);
  background: rgba(0,0,0,.65);
  color: var(--white);
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
}

.profile-stat strong {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.profile-stat span {
  font-size: 10px;
  color: rgba(255,255,255,.7);
}

.profile-location {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: var(--space-2);
  color: rgba(255,255,255,.7);
  font-size: var(--text-xs);
  white-space: nowrap;
}

/* ===== 服务数据 ===== */
.service-section {
  display: grid;
  gap: var(--space-4);
  margin-top: var(--space-5);
  padding: 0 var(--space-4);
}

.profile-tab-bar { margin: var(--space-5) var(--space-4) 0; }
.content-card-grid { display: grid; gap: var(--space-4); margin: var(--space-5) var(--space-4) 0; }

/* Notice card (trust) */
.notice-card {
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  overflow: hidden;
}

.notice-heading {
  margin: 0;
  padding: var(--space-3) var(--space-4);
  font-family: var(--font-serif);
  font-size: var(--text-sm);
  border-bottom: 1px solid var(--neu-light);
  box-shadow: 0 1px 0 var(--neu-shade-soft);
  color: var(--brand);
}

.service-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.section-heading {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--neu-light);
  box-shadow: 0 1px 0 var(--neu-shade-soft);
}

.section-icon {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
}

.section-heading h3 {
  margin: 0;
  font-size: var(--text-base);
}

.section-heading p {
  margin: 3px 0 0;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.trust-footer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-xs);
  color: var(--ink-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.status-dot.active {
  background: var(--success, #22c55e);
}

.status-dot.inactive {
  background: var(--ink-tertiary);
}

/* Facts grid (inside trust card) */
.facts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
}

.facts-grid.three-col {
  grid-template-columns: repeat(3, 1fr);
}

.fact-item {
  display: grid;
  gap: 4px;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-sm);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  text-align: center;
}

.fact-value {
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  font-variant-numeric: tabular-nums;
}

.fact-label {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.service-list { display: grid; gap: 0; }
.service-row {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: start;
  min-height: 48px;
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--neu-light);
  box-shadow: 0 1px 0 var(--neu-shade-soft);
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.55;
}
.service-row:first-child { padding-top: 0; }
.service-row:last-child { padding-bottom: 0; border-bottom: 0; }
.service-label { color: var(--ink-tertiary); font-size: var(--text-xs); }
.service-muted { color: var(--ink-tertiary); }
.tag-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.service-tag { padding: 4px 9px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-xs); font-weight: 700; }

.rule-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}
.rule-item { display: grid; min-height: 72px; place-items: center; align-content: center; gap: 4px; border-right: 1px solid var(--neu-light); box-shadow: 1px 0 0 var(--neu-shade-soft); background: var(--paper); text-align: center; }
.rule-item:last-child { border-right: 0; }
.rule-item strong { color: var(--brand); font-family: var(--font-serif); font-size: var(--text-base); font-variant-numeric: tabular-nums; }
.rule-item span { color: var(--ink-tertiary); font-size: 10px; }
.service-note { margin: 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.65; }

.calendar-card { gap: var(--space-4); }
.month-toolbar { display: grid; grid-template-columns: 48px minmax(0, 1fr) 48px; align-items: center; gap: var(--space-2); text-align: center; }
.month-toolbar h4 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.month-button { display: grid; width: 48px; height: 48px; place-items: center; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); }
.month-button:disabled { color: var(--ink-tertiary); opacity: .45; }
.month-stats { display: grid; grid-template-columns: repeat(3, 1fr); overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.month-stats span { display: grid; min-height: 58px; place-items: center; align-content: center; gap: 2px; border-right: 1px solid var(--neu-light); box-shadow: 1px 0 0 var(--neu-shade-soft); background: var(--paper); }
.month-stats span:last-child { border-right: 0; }
.month-stats small { color: var(--ink-tertiary); font-size: 10px; }
.month-stats strong { color: var(--brand); font-size: var(--text-base); font-variant-numeric: tabular-nums; }
.month-stats .busy strong { color: var(--danger); }
.calendar-legend { display: flex; flex-wrap: wrap; gap: 8px 14px; color: var(--ink-secondary); font-size: 11px; }
.calendar-legend span { display: inline-flex; align-items: center; gap: 5px; }
.calendar-legend i { width: 9px; height: 9px; border: 0; border-radius: 50%; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.calendar-legend i.busy { border-color: var(--danger); background: rgba(163, 59, 50, .15); }
.calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; }
.weekday { display: grid; min-height: 28px; place-items: center; color: var(--ink-tertiary); font-size: 10px; font-weight: 750; }
.date-cell { position: relative; display: grid; min-width: 0; min-height: 52px; place-items: center; align-content: center; gap: 2px; padding: 3px 1px; border: 0; border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); }
.date-cell > span { font-size: var(--text-xs); font-weight: 800; font-variant-numeric: tabular-nums; }
.date-cell > small { color: var(--brand); font-size: 9px; font-weight: 800; }
.date-cell > i { position: absolute; top: 3px; right: 3px; width: 5px; height: 5px; border-radius: 50%; background: var(--warning); }
.date-cell.busy { border-color: rgba(163, 59, 50, .25); background: #fbefed; }
.date-cell.busy > small { color: var(--danger); }
.date-cell.today { box-shadow: inset 0 0 0 1px var(--brand); }
.date-cell.disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); opacity: .42; }
.date-cell.blank { border-color: transparent; background: transparent; }

/* ===== 内容卡片网格 ===== */
.content-card-grid {
  display: grid;
  gap: var(--space-3);
}

.content-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  cursor: pointer;
  text-align: left;
  padding: 0;
  width: 100%;
}

.cover-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  aspect-ratio: 4 / 1;
  overflow: hidden;
}

.cover-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.cover-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-empty {
  color: var(--ink-tertiary);
}

.content-card-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
}

.content-card-label strong {
  font-size: var(--text-sm);
  color: var(--ink);
}

.content-card-label small {
  font-size: var(--text-xs);
  color: var(--ink-tertiary);
}

/* ===== 档期 ===== */
.availability-card {
  display: flex;
  gap: var(--space-3);
  margin: var(--space-5) var(--space-4) 0;
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  box-shadow: var(--neu-raise);
}

.availability-icon { display: grid; width: 42px; height: 42px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.availability-card strong { font-size: var(--text-sm); }
.availability-card p { margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
</style>
