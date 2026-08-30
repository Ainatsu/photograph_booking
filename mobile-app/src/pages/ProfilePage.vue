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

              <button type="button" class="content-card pressable inspiration-content-card" @click="goTo('inspirations', 'content_inspirations')">
                <div class="inspiration-card-icon"><Lightbulb :size="28" aria-hidden="true" /></div>
                <div class="content-card-label"><strong>灵感</strong><small>记录下一次拍摄的起点</small></div>
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
import { getMyProjects } from '@/api/projects'
import { getCustomerOrders } from '@/api/orders'
import { getMyPhotographerApplication } from '@/api/photographerApplications'
import { getFollowCounts } from '@/api/social'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import type { PackageOffer, ProjectBrief, WorkItem } from '@/types/discovery'
import type { FollowCounts } from '@/types/social'
import { resolveMediaUrl, getWorkPreviewUrl, getPackagePreviewUrl } from '@/utils/media'
import { isActiveOrder } from '@/utils/order'
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

const activeOrderCount = ref(0)
const loadingOrders = ref(false)
const loadingSocial = ref(false)
const followCounts = ref<FollowCounts>({ follower_count: 0, following_count: 0 })
const photographerApplicationStatus = ref<string | null>(null)

// 内容数据
const portfolioWorks = ref<WorkItem[]>([])
const portfolioPackages = ref<PackageOffer[]>([])
const myProjects = ref<ProjectBrief[]>([])
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

async function loadOrderSummary() {
  if (!auth.isAuthenticated) return
  loadingOrders.value = true
  try {
    const orders = await getCustomerOrders({ limit: 100 })
    activeOrderCount.value = orders.filter(isActiveOrder).length
  } catch {
    activeOrderCount.value = 0
  } finally {
    loadingOrders.value = false
  }
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
    const [profile, projects] = await Promise.all([
      auth.isPhotographer ? getPhotographerDetail(auth.user.id).catch(() => null) : Promise.resolve(null),
      getMyProjects().catch(() => [] as ProjectBrief[]),
    ])
    portfolioWorks.value = profile?.portfolio || []
    portfolioPackages.value = profile?.packages || []
    myProjects.value = projects
    residency.value = profile?.location || ''
  } catch {
    portfolioWorks.value = []
    portfolioPackages.value = []
    myProjects.value = []
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
  activeOrderCount.value = 0
  await router.replace({ name: 'profile' })
}

onIonViewWillEnter(async () => {
  await auth.initialize()
  await Promise.all([
    loadOrderSummary(),
    loadSocialSummary(),
    loadNotificationSummary(),
    loadPhotographerApplicationSummary(),
    loadContentData(),
  ])
})
</script>

<style scoped>
.guest-card { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: var(--space-4); padding: var(--space-5); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.guest-icon { display: grid; width: 64px; height: 64px; place-items: center; border-radius: 50%; background: var(--brand-soft); color: var(--brand); }
.guest-card h2 { margin: 2px 0 5px; font-family: var(--font-serif); font-size: var(--text-lg); }
.guest-card p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.login-button, .register-button { min-height: var(--touch-target); border-radius: var(--radius-md); font-weight: 750; }
.login-button { grid-column: 1 / -1; border: 0; background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.register-button { grid-column: 1 / -1; border: 0; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
.guest-benefits { display: grid; gap: var(--space-2); margin-top: var(--space-5); }
.guest-benefits > div { display: grid; grid-template-columns: 40px minmax(0, 1fr); align-items: center; gap: var(--space-3); min-height: 68px; padding: var(--space-3); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); }
.guest-benefits span { display: grid; gap: 3px; }
.guest-benefits strong { color: var(--ink); font-size: var(--text-sm); }
.guest-benefits small { color: var(--ink-tertiary); font-size: var(--text-xs); }
.profile-card { position: relative; overflow: hidden; border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); background-size: cover; background-position: center; }
.profile-card-overlay { position: absolute; inset: 0; background: linear-gradient(135deg, rgba(0,0,0,.65) 0%, rgba(0,0,0,.35) 100%); }
.profile-card.has-cover .profile-card-overlay { background: transparent; }
.profile-card.has-cover .profile-card-body { text-shadow: 0 1px 4px rgba(0,0,0,.72); }
.profile-card-body { position: relative; display: grid; grid-template-columns: auto 1fr; align-items: stretch; min-height: 140px; }
.avatar-col { display: flex; align-items: center; padding: var(--space-5); }
.avatar-wrap { display: inline-flex; }
.info-col { display: flex; flex-direction: column; justify-content: space-between; padding: var(--space-5) var(--space-5) var(--space-5) 0; min-height: 140px; }
.identity { min-width: 0; }
.identity-title { display: flex; align-items: center; gap: 6px; color: var(--brand); }
.identity h2 { overflow: hidden; margin: 0; color: var(--white); font-family: var(--font-serif); font-size: var(--text-lg); text-overflow: ellipsis; white-space: nowrap; }
.identity p { margin: 4px 0 8px; color: rgba(255,255,255,.65); font-size: var(--text-xs); }
.role-badge { display: inline-flex; min-height: 27px; align-items: center; padding: 3px 9px; border-radius: var(--radius-pill); background: rgba(255,255,255,.18); color: var(--white); font-size: 11px; font-weight: 700; -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px); }
.profile-bio { margin: var(--space-3) 0 0; color: rgba(255,255,255,.85); font-size: var(--text-sm); line-height: 1.65; }
.profile-stats { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.profile-stat { display: flex; align-items: center; gap: 4px; min-height: 28px; padding: 0 10px; border: 1px solid rgba(255,255,255,.25); border-radius: var(--radius-pill); background: rgba(0,0,0,.65); color: var(--white); -webkit-backdrop-filter: blur(4px); backdrop-filter: blur(4px); cursor: pointer; }
.profile-stat strong { font-size: 11px; font-variant-numeric: tabular-nums; }
.profile-stat span { font-size: 10px; color: rgba(255,255,255,.7); }
.profile-stat-static { max-width: 45%; cursor: default; }
.profile-stat-static strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.profile-stat-static span { flex: 0 0 auto; }

/* 切换栏 */
.profile-tab-bar { margin-top: var(--space-5); }

/* 内容卡片网格 */
.content-card-grid { display: grid; gap: var(--space-4); margin-top: var(--space-5); }
.content-card { display: flex; flex-direction: column; overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); cursor: pointer; text-align: left; padding: 0; width: 100%; }
.cover-grid { display: grid; grid-template-columns: repeat(4, 1fr); aspect-ratio: 4 / 1; overflow: hidden; }
.cover-cell { display: flex; align-items: center; justify-content: center; overflow: hidden; background: var(--paper); box-shadow: var(--neu-inset); }
.cover-cell img { width: 100%; height: 100%; object-fit: cover; }
.cover-empty { color: var(--ink-tertiary); }
.content-card-label { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) var(--space-4); }
.content-card-label strong { font-size: var(--text-sm); color: var(--ink); }
.content-card-label small { font-size: var(--text-xs); color: var(--ink-tertiary); }
.inspiration-content-card { min-height: 118px; }
.inspiration-card-icon { display: grid; min-height: 72px; place-items: center; background: linear-gradient(135deg, var(--brand-soft), var(--surface-secondary)); color: var(--brand); }

.menu-section { margin-top: var(--space-6); }
.menu-section h2 { margin: 0 0 var(--space-3); font-family: var(--font-serif); font-size: var(--text-lg); }
.menu-item { display: grid; grid-template-columns: 40px minmax(0, 1fr) 24px; width: 100%; min-height: 68px; align-items: center; gap: var(--space-3); padding: 8px var(--space-3); border: 0; border-bottom: 1px solid var(--neu-light); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); text-align: left; }
.menu-item:first-of-type { border-radius: var(--radius-md) var(--radius-md) 0 0; }
.menu-item:last-child { border-bottom: 0; border-radius: 0 0 var(--radius-md) var(--radius-md); }
.menu-icon { display: grid; width: 38px; height: 38px; place-items: center; border-radius: var(--radius-sm); background: var(--brand-soft); color: var(--brand); }
.menu-item > span:nth-child(2) { display: grid; gap: 4px; }
.menu-item strong { font-size: var(--text-sm); }
.menu-item small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.45; }
.theme-menu-item { grid-template-columns: 40px minmax(0, 1fr) 46px; border-bottom-color: var(--divider); }
.theme-switch { position: relative; display: block; width: 46px; height: 28px; border: 1px solid var(--border); border-radius: var(--radius-pill); background: var(--paper-deep); box-shadow: var(--neu-inset); transition: background var(--motion-normal) ease, border-color var(--motion-normal) ease; }
.theme-switch > span { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: var(--paper-light); box-shadow: var(--neu-raise-sm); transition: transform var(--motion-normal) cubic-bezier(0.2, 0, 0, 1); }
.theme-switch.active { border-color: color-mix(in srgb, var(--brand) 32%, transparent); background: var(--brand-soft); }
.theme-switch.active > span { transform: translateX(18px); background: var(--brand); }

.creator-note { display: flex; gap: var(--space-3); margin-top: var(--space-5); padding: var(--space-4); border-left: 3px solid var(--brand); background: var(--brand-soft); color: var(--brand); }
.creator-note strong { color: var(--ink); font-size: var(--text-sm); }
.creator-note p { margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.logout-button { display: flex; width: 100%; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); margin-top: var(--space-6); border: 1px solid rgba(163, 59, 50, .32); border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--danger); font-weight: 700; }

/* 个人页：顶部栏只保留安全距离，不占额外高度 */
.page-shell :deep(.top-bar) { min-height: 0; padding-top: env(safe-area-inset-top); }
.page-shell :deep(.top-bar .top-bar-spacer) { display: none; }
/* 个人信息卡与顶部保持间距 */
.page-shell { padding-top: var(--space-5); }
</style>
