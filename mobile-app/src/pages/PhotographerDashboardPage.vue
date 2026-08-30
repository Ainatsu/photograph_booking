<template>
  <ion-page>
    <DetailHeader title="经营看板" default-href="/tabs/profile" />

    <ion-content class="page-content" :fullscreen="true">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="page-shell">

        <template v-if="!auth.isPhotographer">
          <StatePanel
            title="仅摄影师可用"
            description="经营看板为摄影师角色提供数据概览和待办事项。"
          />
        </template>

        <template v-else-if="initialLoading">
          <FeedSkeleton :count="4" />
        </template>

        <template v-else-if="loadError && !dashboard">
          <StatePanel
            tone="error"
            title="看板加载失败"
            :description="loadError"
            action-label="重新加载"
            @action="reload"
          />
        </template>

        <template v-else-if="dashboard">
          <div class="range-switch">
            <SegmentSwitch v-model="range" :items="rangeOptions" label="时间范围" />
          </div>

          <!-- 摘要统计 -->
          <section class="dashboard-section">
            <div class="summary-grid">
              <div class="summary-card">
                <span class="summary-icon"><ShoppingCart :size="18" aria-hidden="true" /></span>
                <strong class="summary-value">{{ dashboard.summary.period_orders }}</strong>
                <span class="summary-label">期间接单</span>
              </div>
              <div class="summary-card">
                <span class="summary-icon"><Camera :size="18" aria-hidden="true" /></span>
                <strong class="summary-value">{{ dashboard.summary.confirmed_shoots }}</strong>
                <span class="summary-label">确认拍摄</span>
              </div>
              <div class="summary-card">
                <span class="summary-icon"><Percent :size="18" aria-hidden="true" /></span>
                <strong class="summary-value">{{ formatPercent(dashboard.summary.completion_rate) }}</strong>
                <span class="summary-label">完成率</span>
              </div>
              <div class="summary-card">
                <span class="summary-icon"><Star :size="18" aria-hidden="true" /></span>
                <strong class="summary-value">{{ formatRating(dashboard.summary.avg_rating) }}</strong>
                <span class="summary-label">平均评分</span>
              </div>
            </div>
          </section>

          <!-- 待办事项 -->
          <section v-if="hasTodos" class="dashboard-section">
            <div class="notice-card">
              <h2 class="notice-heading">待办事项</h2>
              <div class="todo-list">
                <button
                  v-if="dashboard.todo.pending_orders > 0"
                  type="button"
                  class="todo-item pressable"
                  @click="goOrders"
                >
                  <span class="todo-icon"><Clock :size="18" aria-hidden="true" /></span>
                  <span class="todo-info">
                    <strong>{{ dashboard.todo.pending_orders }}</strong>
                    <span>待确认订单</span>
                  </span>
                  <ChevronRight :size="16" class="todo-arrow" />
                </button>
                <button
                  v-if="dashboard.todo.reschedule_requests > 0"
                  type="button"
                  class="todo-item pressable"
                  @click="goOrders"
                >
                  <span class="todo-icon"><CalendarSync :size="18" aria-hidden="true" /></span>
                  <span class="todo-info">
                    <strong>{{ dashboard.todo.reschedule_requests }}</strong>
                    <span>改期请求</span>
                  </span>
                  <ChevronRight :size="16" class="todo-arrow" />
                </button>
                <button
                  v-if="dashboard.todo.orders_to_deliver > 0"
                  type="button"
                  class="todo-item pressable"
                  @click="goOrders"
                >
                  <span class="todo-icon"><Upload :size="18" aria-hidden="true" /></span>
                  <span class="todo-info">
                    <strong>{{ dashboard.todo.orders_to_deliver }}</strong>
                    <span>待交付作品</span>
                  </span>
                  <ChevronRight :size="16" class="todo-arrow" />
                </button>
                <button
                  v-if="dashboard.todo.orders_waiting_review > 0"
                  type="button"
                  class="todo-item pressable"
                  @click="goOrders"
                >
                  <span class="todo-icon"><MessageSquare :size="18" aria-hidden="true" /></span>
                  <span class="todo-info">
                    <strong>{{ dashboard.todo.orders_waiting_review }}</strong>
                    <span>待客户评价</span>
                  </span>
                  <ChevronRight :size="16" class="todo-arrow" />
                </button>
              </div>
            </div>
          </section>

          <!-- 今日/近期日程 -->
          <section class="dashboard-section">
            <div class="content-card">
              <h2 class="content-card-heading">
                <CalendarDays :size="18" aria-hidden="true" />
                日程
              </h2>
              <div class="facts-grid">
                <div class="fact-item">
                  <span class="fact-value">{{ dashboard.schedule.today_orders }}</span>
                  <span class="fact-label">今日订单</span>
                </div>
                <div class="fact-item">
                  <span class="fact-value">{{ dashboard.schedule.upcoming_orders.length }}</span>
                  <span class="fact-label">近期预约</span>
                </div>
              </div>
              <div v-if="dashboard.schedule.next_order" class="next-order">
                <span class="next-order-label">下一个预约</span>
                <span class="next-order-time">{{ formatDate(dashboard.schedule.next_order.appointment_time) }}</span>
              </div>
              <div v-if="dashboard.schedule.upcoming_orders.length > 0" class="upcoming-list">
                <div
                  v-for="order in dashboard.schedule.upcoming_orders.slice(0, 3)"
                  :key="order.id"
                  class="upcoming-item"
                >
                  <span class="upcoming-time">{{ formatDate(order.appointment_time) }}</span>
                  <span class="upcoming-id">#{{ order.id }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- 热门内容 -->
          <section v-if="dashboard.top_works.length > 0 || dashboard.top_packages.length > 0" class="dashboard-section">
            <div class="content-card">
              <h2 class="content-card-heading">
                <TrendingUp :size="18" aria-hidden="true" />
                热门内容
              </h2>
              <div v-if="dashboard.top_works.length > 0" class="top-section">
                <h3 class="sub-heading">热门作品</h3>
                <div class="top-works-grid">
                  <div
                    v-for="work in dashboard.top_works.slice(0, 3)"
                    :key="work.id"
                    class="top-work-card"
                  >
                    <div class="top-work-thumb">
                      <img
                        v-if="work.thumbnail_url"
                        :src="work.thumbnail_url"
                        :alt="work.title"
                      />
                      <ImageOff v-else :size="24" class="thumb-placeholder" />
                    </div>
                    <div class="top-work-info">
                      <span class="top-work-title">{{ work.title }}</span>
                      <span class="top-work-meta">
                        <Heart :size="12" aria-hidden="true" />
                        {{ work.like_count }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <div v-if="dashboard.top_packages.length > 0" class="top-section">
                <h3 class="sub-heading">热门方案</h3>
                <div class="top-packages-list">
                  <div
                    v-for="pkg in dashboard.top_packages.slice(0, 3)"
                    :key="pkg.id"
                    class="top-package-item"
                  >
                    <div class="top-package-thumb">
                      <img
                        v-if="pkg.sample_url"
                        :src="pkg.sample_url"
                        :alt="pkg.name"
                      />
                      <PackageIcon :size="20" v-else class="thumb-placeholder" />
                    </div>
                    <div class="top-package-info">
                      <span class="top-package-name">{{ pkg.name }}</span>
                      <span class="top-package-price">{{ formatPrice(pkg.price) }}</span>
                    </div>
                    <span class="top-package-favs">
                      <Heart :size="12" aria-hidden="true" />
                      {{ pkg.favorite_count }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- 互动指标 -->
          <section class="dashboard-section">
            <div class="content-card">
              <h2 class="content-card-heading">
                <Users :size="18" aria-hidden="true" />
                互动
              </h2>
              <div class="facts-grid three-col">
                <div class="fact-item">
                  <span class="fact-value">{{ dashboard.interactions.new_followers }}</span>
                  <span class="fact-label">新增关注</span>
                </div>
                <div class="fact-item">
                  <span class="fact-value">{{ dashboard.interactions.message_conversations }}</span>
                  <span class="fact-label">消息会话</span>
                </div>
                <div class="fact-item">
                  <span class="fact-value">{{ dashboard.interactions.work_likes }}</span>
                  <span class="fact-label">作品获赞</span>
                </div>
              </div>
            </div>
          </section>

          <!-- 转化漏斗 -->
          <section v-if="dashboard.funnel?.nodes?.length" class="dashboard-section">
            <div class="content-card">
              <h2 class="content-card-heading">
                <GitFork :size="18" aria-hidden="true" />
                转化漏斗
              </h2>
              <div class="funnel-list">
                <div
                  v-for="(node, index) in dashboard.funnel.nodes"
                  :key="node.key"
                  class="funnel-item"
                >
                  <span class="funnel-index">{{ index + 1 }}</span>
                  <div class="funnel-info">
                    <span class="funnel-label">{{ node.label }}</span>
                    <span class="funnel-count">{{ node.count }}</span>
                  </div>
                  <span v-if="node.conversion_rate !== null" class="funnel-rate">
                    {{ (node.conversion_rate * 100).toFixed(1) }}%
                  </span>
                </div>
              </div>
            </div>
          </section>
        </template>
      </main>
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  CalendarDays,
  CalendarSync,
  Camera,
  ChevronRight,
  Clock,
  GitFork,
  Heart,
  ImageOff,
  MessageSquare,
  Package as PackageIcon,
  Percent,
  ShoppingCart,
  Star,
  TrendingUp,
  Upload,
  Users,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerDashboard } from '@/api/dashboard'
import type { PhotographerDashboardResponse } from '@/api/dashboard'
import { useAuthStore } from '@/stores/auth'

type DashboardRange = '7d' | 'month' | '90d' | 'all'

const router = useRouter()
const auth = useAuthStore()

const range = ref<DashboardRange>('month')
const dashboard = ref<PhotographerDashboardResponse | null>(null)
const initialLoading = ref(true)
const loadError = ref('')

const rangeOptions = [
  { label: '7天', value: '7d' },
  { label: '本月', value: 'month' },
  { label: '90天', value: '90d' },
  { label: '全部', value: 'all' },
]

const hasTodos = computed(() => {
  if (!dashboard.value) return false
  const t = dashboard.value.todo
  return t.pending_orders > 0 || t.reschedule_requests > 0 || t.orders_to_deliver > 0 || t.orders_waiting_review > 0
})

async function load() {
  if (!auth.isPhotographer) {
    initialLoading.value = false
    return
  }
  loadError.value = ''
  try {
    dashboard.value = await getPhotographerDashboard(range.value)
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    initialLoading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  event.target.complete()
}

async function reload() {
  initialLoading.value = true
  await load()
}

function goOrders() {
  router.push({ name: 'orders' })
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return '--'
  return `${(value * 100).toFixed(1)}%`
}

function formatRating(value: number | null): string {
  if (value === null || value === undefined) return '--'
  return value.toFixed(1)
}

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${month}-${day}`
}

function formatPrice(price: number | null): string {
  if (price === null || price === undefined) return '面议'
  return `¥${price}`
}

watch(range, () => {
  initialLoading.value = true
  load()
})

// initial load
auth.initialize().then(() => load())
</script>

<style scoped>
.refresh-action {
  display: grid;
  place-items: center;
}

.range-switch {
  margin-top: var(--space-4);
}

.dashboard-section {
  margin-top: var(--space-5);
}

/* Summary grid */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3);
}

.summary-card {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: var(--space-2) var(--space-2);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  align-content: start;
}

.summary-icon {
  grid-row: 1 / 3;
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--brand-soft);
  color: var(--brand);
}

.summary-value {
  font-family: var(--font-serif);
  font-size: var(--text-xl);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.summary-label {
  grid-column: 2;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
}

/* Notice card (todo) */
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

.todo-list {
  display: grid;
}

.todo-item {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) 20px;
  width: 100%;
  min-height: 60px;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 0;
  border-bottom: 1px solid var(--neu-light);
  box-shadow: 0 1px 0 var(--neu-shade-soft);
  background: transparent;
  color: var(--ink);
  text-align: left;
}

.todo-item:last-child {
  border-bottom: 0;
}

.todo-icon {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--brand-soft);
  color: var(--brand);
}

.todo-info {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  min-width: 0;
}

.todo-info strong {
  font-size: var(--text-base);
  font-variant-numeric: tabular-nums;
  color: var(--brand);
}

.todo-info span:last-child {
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-arrow {
  color: var(--ink-tertiary);
  flex: 0 0 auto;
}

/* Content card */
.content-card {
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  padding: var(--space-4);
}

.content-card-heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 0 var(--space-3);
  font-family: var(--font-serif);
  font-size: var(--text-base);
  color: var(--ink);
}

/* Facts grid */
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

/* Next order */
.next-order {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--neu-light);
  box-shadow: 0 1px 0 var(--neu-shade-soft);
}

.next-order-label {
  color: var(--ink-secondary);
  font-size: var(--text-sm);
}

.next-order-time {
  font-weight: 700;
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
}

/* Upcoming list */
.upcoming-list {
  display: grid;
  gap: var(--space-2);
  padding-top: var(--space-3);
}

.upcoming-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.upcoming-time {
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
}

.upcoming-id {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

/* Top works */
.top-section {
  margin-top: var(--space-3);
}

.top-section:first-child {
  margin-top: 0;
}

.sub-heading {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  font-weight: 650;
  color: var(--ink-secondary);
}

.top-works-grid {
  display: grid;
  gap: var(--space-2);
}

.top-work-card {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: center;
}

.top-work-thumb {
  width: 56px;
  height: 56px;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.top-work-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumb-placeholder {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  color: var(--ink-tertiary);
}

.top-work-info {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.top-work-title {
  overflow: hidden;
  font-size: var(--text-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-work-meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

/* Top packages */
.top-packages-list {
  display: grid;
  gap: var(--space-2);
}

.top-package-item {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--neu-light);
  box-shadow: 0 1px 0 var(--neu-shade-soft);
}

.top-package-item:last-child {
  border-bottom: 0;
}

.top-package-thumb {
  width: 44px;
  height: 44px;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.top-package-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.top-package-info {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.top-package-name {
  overflow: hidden;
  font-size: var(--text-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-package-price {
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 700;
}

.top-package-favs {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  white-space: nowrap;
}

/* Funnel */
.funnel-list {
  display: grid;
  gap: var(--space-2);
}

.funnel-item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-2) 0;
}

.funnel-item + .funnel-item { border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); }

.funnel-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 700;
}

.funnel-info {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.funnel-label {
  color: var(--ink);
  font-size: var(--text-sm);
}

.funnel-count {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
}

.funnel-rate {
  color: var(--brand);
  font-size: var(--text-sm);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
