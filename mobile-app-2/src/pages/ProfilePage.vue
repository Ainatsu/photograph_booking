<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <main class="page-shell">
        <AppTopBar :show-left="false" :show-search="false" />

        <FeedSkeleton v-if="auth.initializing" :count="3" />

        <template v-else-if="!auth.isAuthenticated">
          <section class="guest-card">
            <span class="guest-icon"><UserRound :size="31" aria-hidden="true" /></span>
            <div>
              <h2>登录后继续使用</h2>
              <p>同步真实订单、预约档期和摄影师工作流，不再显示模拟数据。</p>
            </div>
            <button type="button" class="login-button pressable" @click="router.push({ name: 'login' })">
              登录
            </button>
            <button type="button" class="register-button pressable" @click="router.push({ name: 'register' })">
              创建账号
            </button>
          </section>

          <section class="guest-benefits">
            <div><CalendarCheck2 :size="20" aria-hidden="true" /><span><strong>预约真实档期</strong><small>避开摄影师已有订单</small></span></div>
            <div><ClipboardList :size="20" aria-hidden="true" /><span><strong>跟踪订单状态</strong><small>确认、支付、履约与验收</small></span></div>
            <div><ShieldCheck :size="20" aria-hidden="true" /><span><strong>保留站内记录</strong><small>重要约定以服务端数据为准</small></span></div>
          </section>
        </template>

        <template v-else-if="auth.user">
          <section
            class="profile-card"
            :class="{ 'has-cover': Boolean(auth.user.background_url) }"
            :style="auth.user.background_url ? { backgroundImage: `url(${resolveMediaUrl(auth.user.background_url)})` } : {}"
          >
            <div class="profile-card-overlay" />
            <div class="profile-card-body">
              <div class="avatar-col">
                <div class="avatar-wrap">
                  <AvatarImage :src="auth.user.avatar_url" :name="auth.user.display_name" :size="80" />
                </div>
              </div>
              <div class="info-col">
                <div class="identity">
                  <div class="identity-title">
                    <h2>{{ auth.user.display_name }}</h2>
                    <BadgeCheck v-if="auth.isPhotographer" :size="18" aria-label="已认证摄影师" />
                  </div>
                  <p>@{{ auth.user.username || `user-${auth.user.id}` }}</p>
                  <p v-if="auth.user.bio" class="profile-bio">{{ auth.user.bio }}</p>
                </div>
                <div class="profile-stats">
                  <button type="button" class="profile-stat pressable" @click="openSocial('following')">
                    <strong>{{ loadingSocial ? '…' : followCounts.following_count }}</strong>
                    <span>我的关注</span>
                  </button>
                  <button type="button" class="profile-stat pressable" @click="openSocial('followers')">
                    <strong>{{ loadingSocial ? '…' : followCounts.follower_count }}</strong>
                    <span>关注者</span>
                  </button>
                  <span v-if="residencyLabel" class="profile-stat profile-stat-static">
                    <strong>{{ residencyLabel }}</strong>
                    <span></span>
                  </span>
                </div>
              </div>
            </div>
          </section>

          <!-- 内容/功能 切换栏 -->
          <SegmentSwitch v-model="activeTab" :items="tabItems" class="profile-tab-bar" />

          <!-- ============ 内容选项卡 ============ -->
          <template v-if="activeTab === 'content'">
            <div class="content-card-grid">
              <!-- 作品卡片 -->
              <button type="button" class="content-card pressable" @click="goToWorks">
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

              <!-- 方案卡片（仅摄影师） -->
              <button
                v-if="auth.isPhotographer"
                type="button"
                class="content-card pressable"
                @click="goToPackages"
              >
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
                  <small>{{ portfolioPackages.length }} 个方案</small>
                </div>
              </button>

              <!-- 企划卡片 -->
              <button type="button" class="content-card pressable" @click="goToProjects">
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
                  <small>{{ myProjects.length }} 个企划</small>
                </div>
              </button>

              <!-- 灵感卡片 -->
              <button type="button" class="content-card pressable" @click="goTo('inspirations', 'content_inspirations')">
                <div v-if="inspirationCovers.length" class="cover-grid">
                  <div
                    v-for="(url, idx) in inspirationCovers.slice(0, 4)"
                    :key="idx"
                    class="cover-cell"
                  >
                    <img :src="url" alt="" loading="lazy" />
                  </div>
                  <div
                    v-for="i in Math.max(0, 4 - Math.min(inspirationCovers.length, 4))"
                    :key="'in-empty-' + i"
                    class="cover-cell cover-empty"
                  >
                    <Lightbulb :size="20" />
                  </div>
                </div>
                <div v-else class="cover-grid">
                  <div v-for="i in 4" :key="'in-ph-' + i" class="cover-cell cover-empty">
                    <Lightbulb :size="20" />
                  </div>
                </div>
                <div class="content-card-label">
                  <strong>灵感</strong>
                  <small>{{ myInspirations.length ? `${myInspirations.length} 条灵感` : '记录下一次拍摄的起点' }}</small>
                </div>
              </button>
            </div>
          </template>

          <!-- ============ 功能选项卡 ============ -->
          <template v-if="activeTab === 'functions'">
            <section class="menu-section">
              <button
                type="button"
                class="menu-item theme-menu-item pressable"
                role="switch"
                :aria-checked="activeTheme === 'light'"
                :aria-label="activeTheme === 'light' ? '切换为暗色主题' : '切换为亮浅色主题'"
                @click="switchTheme"
              >
                <span class="menu-icon">
                  <Sun v-if="activeTheme === 'light'" :size="20" aria-hidden="true" />
                  <Moon v-else :size="20" aria-hidden="true" />
                </span>
                <span>
                  <strong>亮浅色主题</strong>
                  <small>{{ activeTheme === 'light' ? '已开启，界面清爽明亮' : '当前为暗色，点击切换为亮浅色' }}</small>
                </span>
                <span class="theme-switch" :class="{ active: activeTheme === 'light' }" aria-hidden="true">
                  <span />
                </span>
              </button>
              <button type="button" class="menu-item pressable" @click="goToOrders">
                <span class="menu-icon"><ClipboardList :size="20" aria-hidden="true" /></span>
                <span><strong>我的订单</strong><small>查看确认、支付和履约进度，切换应邀列表</small></span>
                <ChevronRight :size="19" aria-hidden="true" />
              </button>
              <button type="button" class="menu-item pressable" @click="goTo('photographer-application', 'photographer_application')">
                <span class="menu-icon"><FileBadge2 :size="20" aria-hidden="true" /></span>
                <span><strong>摄影师认证</strong><small>{{ photographerApplicationSummaryText }}</small></span>
                <ChevronRight :size="19" aria-hidden="true" />
              </button>
              <button v-if="auth.isPhotographer" type="button" class="menu-item pressable" @click="goTo('photographer-dashboard', 'photographer_dashboard')">
                <span class="menu-icon"><BarChart3 :size="20" aria-hidden="true" /></span>
                <span><strong>经营看板</strong><small>接单数据、待办事项与经营概览</small></span>
                <ChevronRight :size="19" aria-hidden="true" />
              </button>
              <button v-if="auth.isPhotographer" type="button" class="menu-item pressable" @click="goTo('photographer-settings', 'photographer_settings')">
                <span class="menu-icon"><CalendarClock :size="20" aria-hidden="true" /></span>
                <span><strong>档期与服务能力</strong><small>设置忙碌日期、器材风格与接单规则</small></span>
                <ChevronRight :size="19" aria-hidden="true" />
              </button>
              <button type="button" class="menu-item pressable" @click="openSocial('works')">
                <span class="menu-icon"><Heart :size="20" aria-hidden="true" /></span>
                <span><strong>收藏、点赞与关注</strong><small>候选清单、赞过内容、关注与粉丝列表</small></span>
                <ChevronRight :size="19" aria-hidden="true" />
              </button>
              <button type="button" class="menu-item pressable" @click="goTo('account-settings', 'account_settings')">
                <span class="menu-icon"><ShieldCheck :size="20" aria-hidden="true" /></span>
                <span><strong>资料与账号安全</strong><small>{{ contactSummary }}</small></span>
                <ChevronRight :size="19" aria-hidden="true" />
              </button>
            </section>

            <section v-if="auth.isPhotographer" class="creator-note">
              <Camera :size="21" aria-hidden="true" />
              <div>
                <strong>摄影师订单已可处理</strong>
                <p>进入"我的订单"后可切换摄影师身份，确认或拒绝预约并开始服务。</p>
              </div>
            </section>
          </template>

          <button v-if="activeTab === 'functions'" type="button" class="logout-button pressable" @click="confirmLogout">
            <LogOut :size="18" aria-hidden="true" />
            退出当前账号
          </button>
        </template>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { IonContent, IonPage, alertController, onIonViewWillEnter } from '@ionic/vue'
import {
  BadgeCheck,
  BarChart3,
  Briefcase,
  CalendarCheck2,
  CalendarClock,
  Camera,
  ChevronRight,
  ClipboardList,
  FileBadge2,
  Heart,
  ImageIcon,
  Lightbulb,
  LogOut,
  Moon,
  Package,
  ShieldCheck,
  Sun,
  UserRound,
} from 'lucide-vue-next'
import AppTopBar from '@/components/AppTopBar.vue'
import AvatarImage from '@/components/AvatarImage.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import { getPhotographerDetail } from '@/api/discovery'
import { getInspirations } from '@/api/inspirations'
import { getMyProjects } from '@/api/projects'
import { getMyPhotographerApplication } from '@/api/photographerApplications'
import { getFollowCounts } from '@/api/social'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import type { PackageOffer, ProjectBrief, WorkItem } from '@/types/discovery'
import type { Inspiration } from '@/types/inspiration'
import type { FollowCounts } from '@/types/social'
import { resolveMediaUrl, getWorkPreviewUrl, getPackagePreviewUrl, getInspirationPreviewUrl } from '@/utils/media'
import { photographerApplicationSummary } from '@/utils/photographerApplication'
import { formatResidencyLabel } from '@/utils/photographerProfile'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'
import { getInitialTheme, toggleTheme, type AppTheme } from '@/utils/theme'

const router = useRouter()
const auth = useAuthStore()
const notifications = useNotificationStore()

const activeTab = ref<'content' | 'functions'>('content')
const activeTheme = ref<AppTheme>(getInitialTheme())
const tabItems = computed(() => [
  { label: '内容', value: 'content' as const },
  { label: '功能', value: 'functions' as const },
])

const loadingSocial = ref(false)
const followCounts = ref<FollowCounts>({ follower_count: 0, following_count: 0 })
const photographerApplicationStatus = ref<string | null>(null)

// 内容数据
const portfolioWorks = ref<WorkItem[]>([])
const portfolioPackages = ref<PackageOffer[]>([])
const myProjects = ref<ProjectBrief[]>([])
const myInspirations = ref<Inspiration[]>([])
const loadingContent = ref(false)
const residency = ref('')

/** 常驻地标签：只保留最详细的一级（「中国-四川-成都」→「成都」）。 */
const residencyLabel = computed(() => formatResidencyLabel(residency.value))

const workCovers = computed(() => {
  return portfolioWorks.value
    .map((w) => getWorkPreviewUrl(w))
    .filter(Boolean)
    .slice(0, 4)
})

const packageCovers = computed(() => {
  return portfolioPackages.value
    .map((p) => getPackagePreviewUrl(p))
    .filter(Boolean)
    .slice(0, 4)
})

const projectCovers = computed(() => {
  return myProjects.value
    .flatMap((p) => p.reference_images || [])
    .filter(Boolean)
    .slice(0, 4)
    .map((url) => resolveMediaUrl(url))
})

const inspirationCovers = computed(() => {
  return myInspirations.value
    .map((item) => getInspirationPreviewUrl(item))
    .filter(Boolean)
    .slice(0, 4)
})

const contactSummary = computed(() => {
  if (auth.user?.phone) return `手机号 ${auth.user.phone}`
  if (auth.user?.email) return `邮箱 ${auth.user.email}`
  if (auth.user?.pending_email) return `待验证邮箱 ${auth.user.pending_email}`
  return '尚未绑定联系方式'
})

const photographerApplicationSummaryText = computed(() => photographerApplicationSummary(
  photographerApplicationStatus.value,
  auth.isPhotographer,
))

function openSocial(tab: 'works' | 'following' | 'followers') {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: `social_${tab}`, page: 'profile' })
  void router.push({ name: 'social', query: { tab } })
}

function goTo(name: string, buttonName: string) {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: buttonName, page: 'profile' })
  void router.push({ name })
}

function goToOrders() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'orders', page: 'profile' })
  void router.push({ name: 'orders' })
}

function goToWorks() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'content_works', page: 'profile' })
  void router.push({ name: 'works-gallery' })
}

function goToPackages() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'content_packages', page: 'profile' })
  void router.push({ name: 'package-management' })
}

function goToProjects() {
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'content_projects', page: 'profile' })
  void router.push({ name: 'project-management' })
}

function switchTheme() {
  activeTheme.value = toggleTheme(activeTheme.value)
  trackEvent(AnalyticsEvent.BUTTON_CLICK, {
    button_name: `theme_${activeTheme.value}`,
    page: 'profile',
  })
}

async function loadSocialSummary() {
  if (!auth.user) return
  loadingSocial.value = true
  try {
    followCounts.value = await getFollowCounts(auth.user.id)
  } catch {
    followCounts.value = { follower_count: 0, following_count: 0 }
  } finally {
    loadingSocial.value = false
  }
}

async function loadNotificationSummary() {
  if (!auth.isAuthenticated) return
  await notifications.refreshUnread().catch(() => undefined)
}

async function loadPhotographerApplicationSummary() {
  if (!auth.isAuthenticated) return
  if (auth.isPhotographer) {
    photographerApplicationStatus.value = 'approved'
    return
  }
  try {
    const application = await getMyPhotographerApplication()
    photographerApplicationStatus.value = application?.status || null
    if (application?.status === 'approved' && !auth.isPhotographer) {
      await auth.loadCurrentUser().catch(() => undefined)
    }
  } catch {
    photographerApplicationStatus.value = null
  }
}

async function loadContentData() {
  if (!auth.user) return
  loadingContent.value = true
  try {
    const [profile, projects, inspirations] = await Promise.all([
      auth.isPhotographer ? getPhotographerDetail(auth.user.id).catch(() => null) : Promise.resolve(null),
      getMyProjects().catch(() => [] as ProjectBrief[]),
      getInspirations({ limit: 100 }).catch(() => [] as Inspiration[]),
    ])
    portfolioWorks.value = profile?.portfolio || []
    portfolioPackages.value = profile?.packages || []
    myProjects.value = projects
    myInspirations.value = inspirations
    residency.value = profile?.location || ''
  } catch {
    portfolioWorks.value = []
    portfolioPackages.value = []
    myProjects.value = []
    myInspirations.value = []
    residency.value = ''
  } finally {
    loadingContent.value = false
  }
}

async function confirmLogout() {
  const alert = await alertController.create({
    header: '退出登录',
    message: '退出后仍可浏览公开内容，但预约和订单功能需要重新登录。',
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: '退出', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'destructive') return
  auth.logout()
  await router.replace({ name: 'profile' })
}

/**
 * 参照实现这里还跑了一个 loadOrderSummary()：拉最多 100 条订单算「进行中订单数」，
 * 但模板里从来没有渲染过这个值（「我的订单」那一行的小字是静态文案）。
 * 也就是说每次进入本页都会白打一个重请求。本应用移除了它。
 * 如果需要把进行中订单数显示出来，得先补 UI，再把这个调用加回来。
 */
onIonViewWillEnter(async () => {
  await auth.initialize()
  await Promise.all([
    loadSocialSummary(),
    loadNotificationSummary(),
    loadPhotographerApplicationSummary(),
    loadContentData(),
  ])
})
</script>

<style scoped>
/* ===== 未登录 ===== */

.guest-card {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: var(--space-4);
  padding: var(--space-5);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
}

.guest-icon {
  display: grid;
  width: 64px;
  height: 64px;
  place-items: center;
  border-radius: var(--radius-pill);
  background: var(--brand-soft);
  color: var(--brand);
}

.guest-card h2 {
  margin: 2px 0 5px;
  font-size: var(--text-lg);
  font-weight: 700;
}

.guest-card p {
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.6;
}

.login-button,
.register-button {
  grid-column: 1 / -1;
  min-height: var(--touch-target);
  border-radius: var(--radius-pill);
  font-weight: 700;
}

.login-button {
  border: 0;
  background: var(--brand);
  color: var(--on-brand);
}

.register-button {
  border: 1px solid var(--brand);
  background: var(--surface-solid);
  color: var(--brand);
}

.guest-benefits {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-5);
}

.guest-benefits > div {
  display: grid;
  min-height: 68px;
  grid-template-columns: 40px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  color: var(--brand);
}

.guest-benefits span {
  display: grid;
  gap: 3px;
}

.guest-benefits strong {
  color: var(--ink);
  font-size: var(--text-sm);
}

.guest-benefits small {
  color: var(--ink-secondary);
  font-size: var(--text-xs);
}

/* ===== 个人卡：与摄影师主页同一套处理 ===== */

.profile-card {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background-color: var(--surface-secondary);
  background-size: cover;
  background-position: center;
}

/* 无封面不出遮罩，文字用常规深色 */
.profile-card-overlay {
  position: absolute;
  inset: 0;
  display: none;
}

/* 有封面才压平面遮罩，文字转白 + 阴影 */
.profile-card.has-cover .profile-card-overlay {
  display: block;
  background: var(--surface-overlay);
}

.profile-card.has-cover .profile-card-body {
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.72);
}

.profile-card.has-cover .identity-title,
.profile-card.has-cover .identity h2,
.profile-card.has-cover .identity p,
.profile-card.has-cover .profile-stat strong,
.profile-card.has-cover .profile-stat span {
  color: var(--on-overlay);
}

.profile-card-body {
  position: relative;
  display: grid;
  min-height: 140px;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: stretch;
}

.avatar-col {
  display: flex;
  align-items: center;
  padding: var(--space-5);
}

.avatar-wrap {
  display: inline-flex;
}

.info-col {
  display: flex;
  min-width: 0;
  min-height: 140px;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--space-5) var(--space-5) var(--space-5) 0;
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
  color: var(--ink);
  font-size: var(--text-lg);
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity p {
  margin: 4px 0 0;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.profile-bio {
  display: -webkit-box;
  margin-top: 6px;
  overflow: hidden;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.profile-stats {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  margin-top: var(--space-3);
}

/* 统计项可能是可点按钮（关注/关注者），也可能是纯展示的 span（常驻地） */
.profile-stat {
  display: grid;
  gap: 2px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.profile-stat-static {
  cursor: default;
}

.profile-stat strong,
.profile-stat span {
  white-space: nowrap;
}

.profile-stat strong {
  color: var(--ink);
  font-size: var(--text-base);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.profile-stat span {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.profile-tab-bar {
  margin: var(--space-5) 0 0;
}

/* ===== 内容三宫格 ===== */

.content-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.content-card {
  display: grid;
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
  color: var(--ink);
  text-align: left;
}

.cover-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  background: var(--border);
}

.cover-cell {
  min-width: 0;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  background: var(--surface-secondary);
}

.cover-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-empty {
  display: grid;
  place-items: center;
  color: var(--ink-tertiary);
}

.content-card-label {
  display: grid;
  gap: 2px;
  padding: 0 var(--space-3) var(--space-3);
}

.content-card-label strong {
  font-size: var(--text-sm);
  font-weight: 700;
}

.content-card-label small {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

/* ===== 功能菜单 ===== */

.menu-section {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.menu-item {
  display: grid;
  min-height: var(--touch-target);
  grid-template-columns: 40px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
  color: var(--ink);
  text-align: left;
}

.menu-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
}

.menu-item > span:nth-child(2) {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.menu-item strong {
  font-size: var(--text-sm);
  font-weight: 700;
}

.menu-item small {
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.menu-item > svg {
  color: var(--ink-tertiary);
}

/* 主题开关：只动 transform 与 background */
.theme-switch {
  position: relative;
  width: 46px;
  height: 28px;
  flex: 0 0 auto;
  border-radius: var(--radius-pill);
  background: var(--surface-tertiary);
  transition: background var(--motion-fast) ease-out;
}

.theme-switch > span {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--surface-solid);
  box-shadow: var(--shadow-1);
  transition: transform var(--motion-fast) ease-out;
}

.theme-switch.active {
  background: var(--brand);
}

.theme-switch.active > span {
  transform: translateX(18px);
}

.creator-note {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--brand-soft);
  color: var(--brand);
}

.creator-note strong {
  color: var(--ink);
  font-size: var(--text-sm);
}

.creator-note p {
  margin: 4px 0 0;
  color: var(--brand);
  font-size: var(--text-xs);
  line-height: 1.6;
}

.logout-button {
  display: flex;
  width: 100%;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: var(--space-5);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  background: var(--surface-solid);
  color: var(--danger);
  font-size: var(--text-sm);
  font-weight: 700;
}
</style>
