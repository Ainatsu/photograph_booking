<template>
  <div class="stats-section">
    <div v-if="!isPublicView" class="dashboard-toolbar">
      <div class="dashboard-switcher" role="tablist" aria-label="仪表盘内容切换">
        <button
          v-for="panel in panelOptions"
          :key="panel.value"
          type="button"
          class="view-switch-button"
          :class="{ active: activePanel === panel.value }"
          @click="activePanel = panel.value"
        >
          {{ panel.label }}
        </button>
      </div>
      <div class="dashboard-toolbar-meta">
        <p>{{ activePanelDescription }}</p>
        <el-segmented v-model="rangeKey" :options="rangeOptions" />
      </div>
    </div>

    <template v-if="isPublicView || activePanel === 'performance'">
      <el-row :gutter="16" class="stats-row">
        <el-col :xs="12" :sm="12" :md="6" v-for="card in statCards" :key="card.key">
          <transition name="stat-fade" mode="out-in">
            <el-skeleton animated :loading="loading" v-if="loading">
              <template #template>
                <el-skeleton-item variant="text" style="width:40%;height:14px;margin-bottom:8px" />
                <el-skeleton-item variant="text" style="width:70%;height:32px" />
              </template>
            </el-skeleton>

            <div v-else class="stat-card" :key="card.key + '-' + card.value">
              <div class="stat-icon" :style="{ color: card.color, backgroundColor: card.bg }">
                <el-icon :size="22">
                  <component :is="card.icon" />
                </el-icon>
              </div>
              <div class="stat-body">
                <div class="stat-label">{{ card.label }}</div>
                <div class="stat-value">
                  <span class="stat-number" :class="{ 'animate-pop': card.justUpdated }">
                    {{ card.value }}
                  </span>
                  <span class="stat-unit" v-if="card.unit">{{ card.unit }}</span>
                </div>
                <div v-if="card.trendText" class="stat-trend" :class="card.trendClass">
                  {{ card.trendText }}
                </div>
              </div>
            </div>
          </transition>
        </el-col>
      </el-row>

      <section v-if="!isPublicView" class="dashboard-section revenue-section">
        <div class="section-heading">
          <div>
            <h3>收入指标</h3>
            <p>仅在订单金额结构化后展示</p>
          </div>
        </div>
        <div v-if="revenue.available" class="revenue-grid">
          <div class="revenue-metric">
            <span>本月预估</span>
            <strong>{{ formatCurrency(revenue.month_estimated) }}</strong>
          </div>
          <div class="revenue-metric">
            <span>已完成</span>
            <strong>{{ formatCurrency(revenue.completed) }}</strong>
          </div>
          <div class="revenue-metric">
            <span>待确认</span>
            <strong>{{ formatCurrency(revenue.pending) }}</strong>
          </div>
          <div class="revenue-metric">
            <span>平均客单价</span>
            <strong>{{ formatCurrency(revenue.average_order_value) }}</strong>
          </div>
        </div>
        <div v-else class="revenue-unavailable">
          {{ revenue.reason || '收入指标暂不可用' }}
        </div>
      </section>

      <template v-if="isPublicView">
        <div class="public-dashboard-grid">
          <section class="dashboard-section public-trust-section">
            <div class="section-heading">
              <div>
                <h3>服务可信度</h3>
                <p>基于已完成服务、客户评价和近期服务记录</p>
              </div>
            </div>
            <div v-if="loading" class="panel-loading">
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
            </div>
            <div v-else class="trust-list">
              <div
                v-for="item in publicTrustItems"
                :key="item.key"
                class="trust-row"
                :class="{ 'is-muted': item.muted }"
              >
                <span class="trust-status" :class="{ 'is-good': item.good, 'is-muted': item.muted }"></span>
                <span>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.description }}</small>
                </span>
              </div>
            </div>
          </section>

          <section class="dashboard-section public-activity-section">
            <div class="section-heading">
              <div>
                <h3>内容活跃度</h3>
                <p>作品、套餐和近期更新情况</p>
              </div>
            </div>
            <div v-if="loading" class="panel-loading">
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
            </div>
            <div v-else class="public-metric-grid">
              <div v-for="item in publicContentItems" :key="item.key" class="public-metric">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.description }}</small>
              </div>
            </div>
          </section>
        </div>

        <section class="dashboard-section public-popular-section">
          <div class="section-heading">
            <div>
              <h3>热门内容</h3>
              <p>按点赞和收藏形成的公开偏好信号</p>
            </div>
          </div>
          <div v-if="loading" class="panel-loading">
            <el-skeleton-item variant="text" style="width:100%;height:68px" />
            <el-skeleton-item variant="text" style="width:100%;height:68px" />
          </div>
          <div v-else class="top-content-grid">
            <div class="top-content-column">
              <div class="subsection-title">热门作品</div>
              <div v-if="topWorks.length" class="top-list">
                <button
                  v-for="work in topWorks"
                  :key="work.id"
                  type="button"
                  class="top-row"
                  @click="goWorkDetail(work)"
                >
                  <span class="top-thumb">
                    <img v-if="work.thumbnail_url || work.url" :src="work.thumbnail_url || work.url" alt="" />
                  </span>
                  <span class="top-copy">
                    <strong>{{ work.title }}</strong>
                    <small>{{ work.like_count }} 赞 · {{ work.favorite_count }} 收藏</small>
                  </span>
                </button>
              </div>
              <div v-else class="quiet-empty compact">
                暂无公开作品互动数据
              </div>
            </div>

            <div class="top-content-column">
              <div class="subsection-title">热门套餐</div>
              <div v-if="topPackages.length" class="top-list">
                <button
                  v-for="pkg in topPackages"
                  :key="pkg.id"
                  type="button"
                  class="top-row"
                  @click="goPackageDetail(pkg)"
                >
                  <span class="top-thumb">
                    <img v-if="pkg.sample_url" :src="pkg.sample_url" alt="" />
                  </span>
                  <span class="top-copy">
                    <strong>{{ pkg.name }}</strong>
                    <small>{{ formatPublicPackageMeta(pkg) }}</small>
                  </span>
                </button>
              </div>
              <div v-else class="quiet-empty compact">
                暂无公开套餐收藏数据
              </div>
            </div>
          </div>
        </section>
      </template>
    </template>

    <template v-if="!isPublicView">
      <template v-if="activePanel === 'workbench'">
        <div class="dashboard-grid">
          <section class="dashboard-section">
            <div class="section-heading">
              <div>
                <h3>待处理事项</h3>
                <p>优先处理会影响客户等待的订单</p>
              </div>
              <el-button text size="small" @click="goOrders()">全部订单</el-button>
            </div>

            <div v-if="loading" class="panel-loading">
              <el-skeleton-item variant="text" style="width:100%;height:42px" />
              <el-skeleton-item variant="text" style="width:100%;height:42px" />
              <el-skeleton-item variant="text" style="width:100%;height:42px" />
            </div>

            <div v-else class="todo-list">
              <button
                v-for="item in todoItems"
                :key="item.key"
                class="todo-row"
                type="button"
                @click="goOrders(item.query)"
              >
                <span class="todo-icon" :style="{ color: item.color, backgroundColor: item.bg }">
                  <el-icon><component :is="item.icon" /></el-icon>
                </span>
                <span class="todo-copy">
                  <span class="todo-label">{{ item.label }}</span>
                  <span class="todo-desc">{{ item.description }}</span>
                </span>
                <strong class="todo-count">{{ item.count }}</strong>
                <el-icon class="todo-arrow"><ArrowRight /></el-icon>
              </button>

              <div v-if="!hasTodo" class="quiet-empty">
                暂无待处理事项
              </div>
            </div>
          </section>

          <section class="dashboard-section">
            <div class="section-heading">
              <div>
                <h3>近期日程</h3>
                <p>确认过的拍摄和即将到来的预约</p>
              </div>
              <el-button text size="small" @click="goProfileTab('availability')">档期</el-button>
            </div>

            <div v-if="loading" class="panel-loading">
              <el-skeleton-item variant="text" style="width:100%;height:52px" />
              <el-skeleton-item variant="text" style="width:100%;height:88px" />
              <el-skeleton-item variant="text" style="width:100%;height:42px" />
            </div>

            <div v-else class="schedule-panel">
              <div class="schedule-metrics">
                <div class="schedule-metric">
                  <span>今日拍摄</span>
                  <strong>{{ schedule.today_orders }}</strong>
                </div>
                <div class="schedule-metric">
                  <span>本周已确认</span>
                  <strong>{{ schedule.week_confirmed_orders }}</strong>
                </div>
              </div>

              <button
                v-if="schedule.next_order"
                type="button"
                class="next-order"
                @click="goOrderDetail(schedule.next_order)"
              >
                <span class="next-label">下一场拍摄</span>
                <strong>{{ formatShortDate(schedule.next_order.appointment_time) }}</strong>
                <span>{{ schedule.next_order.package_snapshot }}</span>
              </button>
              <div v-else class="next-order is-empty">
                <span class="next-label">下一场拍摄</span>
                <strong>暂无已确认拍摄</strong>
                <span>可以先设置可预约档期</span>
              </div>

              <div class="upcoming-list" v-if="schedule.upcoming_orders.length">
                <button
                  v-for="order in schedule.upcoming_orders"
                  :key="order.id"
                  type="button"
                  class="upcoming-row"
                  @click="goOrderDetail(order)"
                >
                  <span class="upcoming-time">{{ formatShortDate(order.appointment_time) }}</span>
                  <span class="upcoming-title">{{ order.package_snapshot }}</span>
                  <el-tag size="small" :type="statusType(order.status)">{{ statusLabel(order.status) }}</el-tag>
                </button>
              </div>
              <div v-else class="quiet-empty">
                最近暂无预约
              </div>
            </div>
          </section>
        </div>

        <div v-if="showEmptyGuide" class="empty-guide">
          <div class="guide-copy">
            <h3>先搭好接单基础</h3>
            <p>完善作品、方案和档期后，客户更容易完成预约。</p>
          </div>
          <div class="guide-actions">
            <el-button type="primary" :icon="Upload" @click="goUploadWork">上传作品</el-button>
            <el-button :icon="Plus" @click="goProfileTab('pkg-mgmt')">新增方案</el-button>
            <el-button :icon="Calendar" @click="goProfileTab('availability')">设置档期</el-button>
          </div>
        </div>
      </template>

      <section v-else-if="activePanel === 'content'" class="dashboard-section content-section">
        <div class="section-heading">
          <div>
            <h3>内容健康度</h3>
            <p>作品、套餐和样片会直接影响客户决策</p>
          </div>
        </div>

        <div class="content-layout">
          <div class="health-list">
            <div
              v-for="item in contentHealthItems"
              :key="item.key"
              class="health-row"
              :class="{ 'is-good': item.good }"
            >
              <span class="health-dot"></span>
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.description }}</small>
              </span>
            </div>
          </div>

          <div class="top-content-grid">
            <div class="top-content-column">
              <div class="subsection-title">热门作品</div>
              <div v-if="topWorks.length" class="top-list">
                <button
                  v-for="work in topWorks"
                  :key="work.id"
                  type="button"
                  class="top-row"
                  @click="goWorkDetail(work)"
                >
                  <span class="top-thumb">
                    <img v-if="work.thumbnail_url || work.url" :src="work.thumbnail_url || work.url" alt="" />
                  </span>
                  <span class="top-copy">
                    <strong>{{ work.title }}</strong>
                    <small>{{ work.like_count }} 赞 · {{ work.favorite_count }} 收藏</small>
                  </span>
                </button>
              </div>
              <div v-else class="quiet-empty compact">
                暂无作品互动数据
              </div>
            </div>

            <div class="top-content-column">
              <div class="subsection-title">热门套餐</div>
              <div v-if="topPackages.length" class="top-list">
                <button
                  v-for="pkg in topPackages"
                  :key="pkg.id"
                  type="button"
                  class="top-row"
                  @click="goPackageDetail(pkg)"
                >
                  <span class="top-thumb">
                    <img v-if="pkg.sample_url" :src="pkg.sample_url" alt="" />
                  </span>
                  <span class="top-copy">
                    <strong>{{ pkg.name }}</strong>
                    <small>{{ formatPackageMeta(pkg) }}</small>
                  </span>
                </button>
              </div>
              <div v-else class="quiet-empty compact">
                暂无套餐收藏数据
              </div>
            </div>
          </div>
        </div>
      </section>

      <template v-else-if="activePanel === 'conversion'">
        <div class="conversion-grid">
          <section class="dashboard-section">
            <div class="section-heading">
              <div>
                <h3>客户互动</h3>
                <p>粉丝、私信、点赞和收藏的近期变化</p>
              </div>
              <el-button text size="small" @click="goMessages">私信</el-button>
            </div>
            <div v-if="loading" class="panel-loading">
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
            </div>
            <div v-else class="interaction-grid">
              <div v-for="item in interactionCards" :key="item.key" class="interaction-metric">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
                <small>{{ item.description }}</small>
              </div>
            </div>
          </section>

          <section class="dashboard-section">
            <div class="section-heading">
              <div>
                <h3>企划表现</h3>
                <p>应邀提交、被选中和转订单情况</p>
              </div>
              <el-button text size="small" @click="goApplications">我的应邀</el-button>
            </div>
            <div v-if="loading" class="panel-loading">
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
              <el-skeleton-item variant="text" style="width:100%;height:58px" />
            </div>
            <div v-else class="project-metrics">
              <div v-for="item in projectMetricCards" :key="item.key" class="project-metric">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
          </section>
        </div>

        <section class="dashboard-section funnel-section">
          <div class="section-heading">
            <div>
              <h3>转化漏斗</h3>
              <p>客户从看到主页到完成订单的大致路径</p>
            </div>
          </div>
          <div v-if="loading" class="panel-loading">
            <el-skeleton-item variant="text" style="width:100%;height:52px" />
            <el-skeleton-item variant="text" style="width:100%;height:52px" />
            <el-skeleton-item variant="text" style="width:100%;height:52px" />
          </div>
          <div v-else>
            <div class="funnel-list">
              <div v-for="node in funnelNodes" :key="node.key" class="funnel-node">
                <div class="funnel-node-head">
                  <span>{{ node.label }}</span>
                  <strong>{{ node.count }}</strong>
                </div>
                <div class="funnel-bar">
                  <span :style="funnelBarStyle(node)"></span>
                </div>
                <small>{{ formatFunnelRate(node) }}</small>
              </div>
            </div>
            <div v-if="!funnel.tracked_event_count" class="funnel-note">
              访问和曝光数据会从现在开始累积；已有订单、私信、点赞和收藏会立即进入漏斗。
            </div>
            <div v-if="conversionHints.length" class="conversion-hints">
              <div v-for="hint in conversionHints" :key="hint.key" class="conversion-hint">
                {{ hint.text }}
              </div>
            </div>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Calendar,
  ChartNoAxesCombined as DataAnalysis,
  CircleCheckBig as Finished,
  Clock,
  Plus,
  Star,
  Ticket as Tickets,
  TrendingUp as TrendCharts,
  TriangleAlert as Warning,
  Upload,
} from 'lucide-vue-next'
import {
  getPhotographerDashboard,
  getPublicPhotographerDashboard,
} from '../api/order'

const props = defineProps({
  refreshTrigger: { type: Number, default: 0 },
  userId: { type: Number, default: null }
})

const router = useRouter()
const loading = ref(true)
const activePanel = ref('performance')
const rangeKey = ref('month')
const panelOptions = [
  { label: '经营表现', value: 'performance' },
  { label: '工作台', value: 'workbench' },
  { label: '内容表现', value: 'content' },
  { label: '转化互动', value: 'conversion' },
]
const rangeOptions = [
  { label: '近 7 天', value: '7d' },
  { label: '本月', value: 'month' },
  { label: '近 90 天', value: '90d' },
  { label: '全部', value: 'all' },
]
const stats = ref({
  monthly_orders: 0,
  weekly_orders: 0,
  period_orders: 0,
  confirmed_shoots: 0,
  completion_rate: 0,
  avg_rating: 0
})
const dashboard = ref({
  period: {
    range_key: 'month',
    label: '本月',
    current_start: null,
    current_end: null,
    previous_start: null,
    previous_end: null,
    has_comparison: false,
  },
  trends: {
    has_comparison: false,
    period_orders_delta: null,
    confirmed_shoots_delta: null,
    completion_rate_delta: null,
    avg_rating_delta: null,
  },
  revenue: {
    available: false,
    reason: '订单尚未记录结构化金额字段，暂不展示收入统计。',
    month_estimated: null,
    completed: null,
    pending: null,
    average_order_value: null,
  },
  content: {
    portfolio_count: 0,
    package_count: 0,
    packages_with_samples: 0,
    recent_upload_count: 0,
  },
  top_works: [],
  top_packages: [],
  todo: {
    pending_orders: 0,
    reschedule_requests: 0,
    orders_to_deliver: 0,
    orders_waiting_review: 0,
  },
  schedule: {
    today_orders: 0,
    week_confirmed_orders: 0,
    next_order: null,
    upcoming_orders: [],
  },
  interactions: {
    new_followers: 0,
    message_conversations: 0,
    work_likes: 0,
    work_favorites: 0,
    package_favorites: 0,
    profile_views: 0,
    portfolio_views: 0,
    package_views: 0,
  },
  funnel: {
    nodes: [],
    tracked_event_count: 0,
  },
  project_performance: {
    submitted_applications: 0,
    selected_applications: 0,
    converted_orders: 0,
    application_conversion_rate: null,
    average_quote: null,
    budget_match_rate: null,
    budget_match_sample_count: 0,
  },
})
const publicDashboard = ref({
  trust: {
    completed_orders: 0,
    avg_rating: null,
    rating_count: 0,
    rating_visible: false,
    completion_rate: null,
    completion_rate_visible: false,
    completion_sample_count: 0,
    recent_order_activity: false,
  },
  content: {
    portfolio_count: 0,
    package_count: 0,
    packages_with_samples: 0,
    recent_upload_count: 0,
  },
  top_works: [],
  top_packages: [],
})

const prevValues = ref({ ...stats.value })
const updatedKeys = ref([])

const isPublicView = computed(() => Boolean(props.userId))
const period = computed(() => dashboard.value.period)
const trends = computed(() => dashboard.value.trends)
const revenue = computed(() => dashboard.value.revenue)
const publicTrust = computed(() => publicDashboard.value.trust)
const content = computed(() => isPublicView.value ? publicDashboard.value.content : dashboard.value.content)
const topWorks = computed(() => isPublicView.value ? publicDashboard.value.top_works : dashboard.value.top_works)
const topPackages = computed(() => isPublicView.value ? publicDashboard.value.top_packages : dashboard.value.top_packages)
const schedule = computed(() => dashboard.value.schedule)
const interactions = computed(() => dashboard.value.interactions)
const funnel = computed(() => dashboard.value.funnel)
const projectPerformance = computed(() => dashboard.value.project_performance)

const activePanelDescription = computed(() => {
  const map = {
    performance: `${period.value.label}数据和上一周期对比`,
    workbench: '待办、日程和接单基础动作',
    content: '作品、套餐和样片的吸引力',
    conversion: '曝光、互动、咨询、预约和企划应邀',
  }
  return map[activePanel.value] || map.performance
})

const formatTrend = (delta, unit = '') => {
  if (!trends.value.has_comparison || delta === null || delta === undefined) {
    return { text: '暂无对比', className: 'is-muted' }
  }
  if (delta === 0) return { text: '较上周期持平', className: 'is-flat' }
  const prefix = delta > 0 ? '+' : ''
  return {
    text: `较上周期 ${prefix}${delta}${unit}`,
    className: delta > 0 ? 'is-up' : 'is-down',
  }
}

const statCards = computed(() => {
  if (isPublicView.value) {
    return [
      {
        key: 'completed_orders',
        label: '完成服务',
        value: publicTrust.value.completed_orders,
        unit: '单',
        icon: Tickets,
        color: 'var(--color-brand)',
        bg: 'var(--color-brand-light)',
        trendText: publicTrust.value.recent_order_activity ? '近 90 天有服务记录' : '近期服务记录待积累',
        trendClass: publicTrust.value.recent_order_activity ? 'is-up' : 'is-muted',
      },
      {
        key: 'avg_rating',
        label: '客户评分',
        value: publicTrust.value.rating_visible ? publicTrust.value.avg_rating : '-',
        unit: publicTrust.value.rating_visible ? '分' : '',
        icon: TrendCharts,
        color: 'var(--color-brand)',
        bg: 'var(--color-brand-light)',
        trendText: publicTrust.value.rating_count ? `${publicTrust.value.rating_count} 条评价` : '暂无评价',
        trendClass: publicTrust.value.rating_count ? 'is-up' : 'is-muted',
      },
      {
        key: 'completion_rate',
        label: '履约完成率',
        value: publicTrust.value.completion_rate_visible ? publicTrust.value.completion_rate : '-',
        unit: publicTrust.value.completion_rate_visible ? '%' : '',
        icon: DataAnalysis,
        color: 'var(--color-brand)',
        bg: 'var(--color-brand-light)',
        trendText: publicTrust.value.completion_rate_visible
          ? `基于 ${publicTrust.value.completion_sample_count} 单服务`
          : '样本积累中',
        trendClass: publicTrust.value.completion_rate_visible ? 'is-up' : 'is-muted',
      },
      {
        key: 'recent_upload_count',
        label: '近期更新',
        value: content.value.recent_upload_count,
        unit: '个',
        icon: Star,
        color: 'var(--color-brand)',
        bg: 'var(--color-brand-light)',
        trendText: '近 30 天新增作品',
        trendClass: content.value.recent_upload_count > 0 ? 'is-up' : 'is-muted',
      },
    ]
  }

  const orderTrend = formatTrend(trends.value.period_orders_delta, '单')
  const shootTrend = formatTrend(trends.value.confirmed_shoots_delta, '场')
  const completionTrend = formatTrend(trends.value.completion_rate_delta, '个百分点')
  const ratingTrend = formatTrend(trends.value.avg_rating_delta, '分')
  return [
    {
      key: 'period_orders',
      label: `${period.value.label}接单`,
      value: stats.value.period_orders,
      unit: '单',
      icon: Tickets,
      color: 'var(--color-brand)',
      bg: 'var(--color-brand-light)',
      trendText: orderTrend.text,
      trendClass: orderTrend.className,
      justUpdated: updatedKeys.value.includes('period_orders')
    },
    {
      key: 'confirmed_shoots',
      label: `${period.value.label}确认拍摄`,
      value: stats.value.confirmed_shoots,
      unit: '场',
      icon: TrendCharts,
      color: 'var(--color-brand)',
      bg: 'var(--color-brand-light)',
      trendText: shootTrend.text,
      trendClass: shootTrend.className,
      justUpdated: updatedKeys.value.includes('confirmed_shoots')
    },
    {
      key: 'completion_rate',
      label: '完成率',
      value: stats.value.completion_rate,
      unit: '%',
      icon: DataAnalysis,
      color: 'var(--color-brand)',
      bg: 'var(--color-brand-light)',
      trendText: completionTrend.text,
      trendClass: completionTrend.className,
      justUpdated: updatedKeys.value.includes('completion_rate')
    },
    {
      key: 'avg_rating',
      label: '平均评分',
      value: stats.value.avg_rating,
      unit: '分',
      icon: Star,
      color: 'var(--color-brand)',
      bg: 'var(--color-brand-light)',
      trendText: ratingTrend.text,
      trendClass: ratingTrend.className,
      justUpdated: updatedKeys.value.includes('avg_rating')
    },
  ]
})

const todoItems = computed(() => [
  {
    key: 'pending',
    label: '待确认预约',
    description: '需要确认或拒绝',
    count: dashboard.value.todo.pending_orders,
    query: { status: 'pending' },
    icon: Warning,
    color: 'var(--color-brand)',
    bg: 'var(--color-brand-light)',
  },
  {
    key: 'reschedule',
    label: '待处理改期',
    description: '客户提交了新时间',
    count: dashboard.value.todo.reschedule_requests,
    query: { todo: 'reschedule' },
    icon: Clock,
    color: 'var(--color-brand)',
    bg: 'var(--color-brand-light)',
  },
  {
    key: 'delivery',
    label: '待交付订单',
    description: '已确认或拍摄中',
    count: dashboard.value.todo.orders_to_deliver,
    query: { todo: 'to_deliver' },
    icon: Upload,
    color: 'var(--color-brand)',
    bg: 'var(--color-brand-light)',
  },
  {
    key: 'review',
    label: '待客户评价',
    description: '客户已接收作品',
    count: dashboard.value.todo.orders_waiting_review,
    query: { status: 'completed' },
    icon: Finished,
    color: 'var(--color-brand)',
    bg: 'var(--color-brand-light)',
  },
])

const hasTodo = computed(() => todoItems.value.some(item => item.count > 0))
const contentHealthItems = computed(() => {
  const portfolioCount = content.value.portfolio_count
  const packageCount = content.value.package_count
  const packagesWithSamples = content.value.packages_with_samples
  const recentUploadCount = content.value.recent_upload_count

  return [
    {
      key: 'portfolio',
      good: portfolioCount >= 6,
      title: `已上传 ${portfolioCount} 个作品`,
      description: portfolioCount >= 6 ? '作品数量已达到基础展示量' : '建议至少补充到 6 个不同风格作品',
    },
    {
      key: 'packages',
      good: packageCount > 0,
      title: `已创建 ${packageCount} 个套餐`,
      description: packageCount > 0 ? '客户可以直接比较和预约' : '还没有可预约套餐',
    },
    {
      key: 'samples',
      good: packageCount > 0 && packagesWithSamples === packageCount,
      title: `${packageCount} 个套餐中 ${packagesWithSamples} 个有示例图`,
      description: packageCount > 0 && packagesWithSamples === packageCount ? '套餐样片完整' : '缺少样片会降低客户判断效率',
    },
    {
      key: 'recent',
      good: recentUploadCount > 0,
      title: `近 30 天上传 ${recentUploadCount} 个作品`,
      description: recentUploadCount > 0 ? '近期有内容更新' : '可以补充近期作品保持主页活跃',
    },
  ]
})

const publicTrustItems = computed(() => [
  {
    key: 'verified',
    good: true,
    title: '已完成摄影师认证',
    description: '该用户已通过平台摄影师身份审核',
  },
  {
    key: 'rating',
    good: publicTrust.value.rating_visible,
    muted: !publicTrust.value.rating_visible,
    title: publicTrust.value.rating_visible
      ? `${publicTrust.value.avg_rating} 分客户评分`
      : '评分样本待积累',
    description: publicTrust.value.rating_visible
      ? `来自 ${publicTrust.value.rating_count} 条客户评价`
      : '完成服务并收到评价后展示平均评分',
  },
  {
    key: 'completion',
    good: publicTrust.value.completion_rate_visible,
    muted: !publicTrust.value.completion_rate_visible,
    title: publicTrust.value.completion_rate_visible
      ? `${publicTrust.value.completion_rate}% 履约完成率`
      : '履约样本待积累',
    description: publicTrust.value.completion_rate_visible
      ? `基于 ${publicTrust.value.completion_sample_count} 单非取消服务统计`
      : '服务样本达到基础量后展示完成率',
  },
  {
    key: 'recent',
    good: publicTrust.value.recent_order_activity,
    muted: !publicTrust.value.recent_order_activity,
    title: publicTrust.value.recent_order_activity ? '近期有服务记录' : '近期服务记录待积累',
    description: '按近 90 天非取消订单判断，不公开具体接单数',
  },
])

const publicContentItems = computed(() => {
  const packageCount = content.value.package_count
  const sampleText = packageCount
    ? `${content.value.packages_with_samples}/${packageCount}`
    : '-'
  return [
    {
      key: 'portfolio',
      label: '公开作品',
      value: content.value.portfolio_count,
      description: '可浏览的作品数量',
    },
    {
      key: 'packages',
      label: '可预约套餐',
      value: packageCount,
      description: '可直接比较的服务方案',
    },
    {
      key: 'samples',
      label: '套餐示例',
      value: sampleText,
      description: '带有示例图的套餐占比',
    },
    {
      key: 'recent',
      label: '近 30 天更新',
      value: content.value.recent_upload_count,
      description: '最近新增的作品数量',
    },
  ]
})

const interactionCards = computed(() => [
  {
    key: 'followers',
    label: '新增粉丝',
    value: interactions.value.new_followers,
    description: '关注你的新用户',
  },
  {
    key: 'messages',
    label: '私信会话',
    value: interactions.value.message_conversations,
    description: '发生过沟通的客户',
  },
  {
    key: 'work_likes',
    label: '作品点赞',
    value: interactions.value.work_likes,
    description: '作品收到的点赞',
  },
  {
    key: 'work_favorites',
    label: '作品收藏',
    value: interactions.value.work_favorites,
    description: '作品被收藏次数',
  },
  {
    key: 'package_favorites',
    label: '套餐收藏',
    value: interactions.value.package_favorites,
    description: '方案被收藏次数',
  },
  {
    key: 'views',
    label: '访问曝光',
    value: interactions.value.profile_views + interactions.value.portfolio_views + interactions.value.package_views,
    description: '主页、作品和套餐访问',
  },
])

const funnelNodes = computed(() => funnel.value.nodes || [])
const maxFunnelCount = computed(() => Math.max(...funnelNodes.value.map(node => node.count || 0), 1))

const projectMetricCards = computed(() => [
  {
    key: 'submitted',
    label: '已提交应邀',
    value: projectPerformance.value.submitted_applications,
  },
  {
    key: 'selected',
    label: '被选中',
    value: projectPerformance.value.selected_applications,
  },
  {
    key: 'converted',
    label: '转订单',
    value: projectPerformance.value.converted_orders,
  },
  {
    key: 'conversion',
    label: '选中率',
    value: formatPercent(projectPerformance.value.application_conversion_rate),
  },
  {
    key: 'quote',
    label: '平均报价',
    value: formatCurrency(projectPerformance.value.average_quote),
  },
  {
    key: 'budget',
    label: '预算匹配',
    value: formatPercent(projectPerformance.value.budget_match_rate),
  },
])

const funnelCount = (key) => funnelNodes.value.find(node => node.key === key)?.count || 0
const conversionHints = computed(() => {
  const hints = []
  if (funnelCount('work_interactions') > 0 && funnelCount('created_orders') === 0) {
    hints.push({
      key: 'work_to_order',
      text: '作品互动已有积累但预约偏少，可以检查套餐说明、价格和可预约档期。',
    })
  }
  if (funnelCount('package_favorites') > 0 && funnelCount('message_conversations') === 0) {
    hints.push({
      key: 'favorite_to_message',
      text: '套餐有人收藏但咨询偏少，可以补充服务边界、交付样片和常见问题。',
    })
  }
  if (
    projectPerformance.value.submitted_applications > 0 &&
    projectPerformance.value.selected_applications === 0
  ) {
    hints.push({
      key: 'project_selection',
      text: '企划应邀尚未被选中，可以检查报价、方案说明和相关作品匹配度。',
    })
  }
  return hints.slice(0, 3)
})

const showEmptyGuide = computed(() => (
  !loading.value &&
  !isPublicView.value &&
  !hasTodo.value &&
  stats.value.period_orders === 0 &&
  stats.value.confirmed_shoots === 0 &&
  schedule.value.upcoming_orders.length === 0
))

const normalizeDashboard = (payload = {}) => ({
  period: {
    range_key: payload.period?.range_key ?? rangeKey.value,
    label: payload.period?.label ?? '本月',
    current_start: payload.period?.current_start ?? null,
    current_end: payload.period?.current_end ?? null,
    previous_start: payload.period?.previous_start ?? null,
    previous_end: payload.period?.previous_end ?? null,
    has_comparison: payload.period?.has_comparison ?? false,
  },
  summary: {
    monthly_orders: payload.summary?.monthly_orders ?? 0,
    weekly_orders: payload.summary?.weekly_orders ?? 0,
    period_orders: payload.summary?.period_orders ?? payload.summary?.monthly_orders ?? 0,
    confirmed_shoots: payload.summary?.confirmed_shoots ?? payload.summary?.weekly_orders ?? 0,
    completion_rate: payload.summary?.completion_rate ?? 0,
    avg_rating: payload.summary?.avg_rating ?? 0,
  },
  trends: {
    has_comparison: payload.trends?.has_comparison ?? false,
    period_orders_delta: payload.trends?.period_orders_delta ?? null,
    confirmed_shoots_delta: payload.trends?.confirmed_shoots_delta ?? null,
    completion_rate_delta: payload.trends?.completion_rate_delta ?? null,
    avg_rating_delta: payload.trends?.avg_rating_delta ?? null,
  },
  revenue: {
    available: payload.revenue?.available ?? false,
    reason: payload.revenue?.reason ?? '订单尚未记录结构化金额字段，暂不展示收入统计。',
    month_estimated: payload.revenue?.month_estimated ?? null,
    completed: payload.revenue?.completed ?? null,
    pending: payload.revenue?.pending ?? null,
    average_order_value: payload.revenue?.average_order_value ?? null,
  },
  content: {
    portfolio_count: payload.content?.portfolio_count ?? 0,
    package_count: payload.content?.package_count ?? 0,
    packages_with_samples: payload.content?.packages_with_samples ?? 0,
    recent_upload_count: payload.content?.recent_upload_count ?? 0,
  },
  top_works: payload.top_works ?? [],
  top_packages: payload.top_packages ?? [],
  todo: {
    pending_orders: payload.todo?.pending_orders ?? 0,
    reschedule_requests: payload.todo?.reschedule_requests ?? 0,
    orders_to_deliver: payload.todo?.orders_to_deliver ?? 0,
    orders_waiting_review: payload.todo?.orders_waiting_review ?? 0,
  },
  schedule: {
    today_orders: payload.schedule?.today_orders ?? 0,
    week_confirmed_orders: payload.schedule?.week_confirmed_orders ?? 0,
    next_order: payload.schedule?.next_order ?? null,
    upcoming_orders: payload.schedule?.upcoming_orders ?? [],
  },
  interactions: {
    new_followers: payload.interactions?.new_followers ?? 0,
    message_conversations: payload.interactions?.message_conversations ?? 0,
    work_likes: payload.interactions?.work_likes ?? 0,
    work_favorites: payload.interactions?.work_favorites ?? 0,
    package_favorites: payload.interactions?.package_favorites ?? 0,
    profile_views: payload.interactions?.profile_views ?? 0,
    portfolio_views: payload.interactions?.portfolio_views ?? 0,
    package_views: payload.interactions?.package_views ?? 0,
  },
  funnel: {
    nodes: payload.funnel?.nodes ?? [],
    tracked_event_count: payload.funnel?.tracked_event_count ?? 0,
  },
  project_performance: {
    submitted_applications: payload.project_performance?.submitted_applications ?? 0,
    selected_applications: payload.project_performance?.selected_applications ?? 0,
    converted_orders: payload.project_performance?.converted_orders ?? 0,
    application_conversion_rate: payload.project_performance?.application_conversion_rate ?? null,
    average_quote: payload.project_performance?.average_quote ?? null,
    budget_match_rate: payload.project_performance?.budget_match_rate ?? null,
    budget_match_sample_count: payload.project_performance?.budget_match_sample_count ?? 0,
  },
})

const normalizePublicDashboard = (payload = {}) => ({
  trust: {
    completed_orders: payload.trust?.completed_orders ?? 0,
    avg_rating: payload.trust?.avg_rating ?? null,
    rating_count: payload.trust?.rating_count ?? 0,
    rating_visible: payload.trust?.rating_visible ?? false,
    completion_rate: payload.trust?.completion_rate ?? null,
    completion_rate_visible: payload.trust?.completion_rate_visible ?? false,
    completion_sample_count: payload.trust?.completion_sample_count ?? 0,
    recent_order_activity: payload.trust?.recent_order_activity ?? false,
  },
  content: {
    portfolio_count: payload.content?.portfolio_count ?? 0,
    package_count: payload.content?.package_count ?? 0,
    packages_with_samples: payload.content?.packages_with_samples ?? 0,
    recent_upload_count: payload.content?.recent_upload_count ?? 0,
  },
  top_works: payload.top_works ?? [],
  top_packages: payload.top_packages ?? [],
})

const setSummary = (newStats) => {
  const changed = []
  if (newStats.monthly_orders !== prevValues.value.monthly_orders) changed.push('monthly_orders')
  if (newStats.weekly_orders !== prevValues.value.weekly_orders) changed.push('weekly_orders')
  if (newStats.period_orders !== prevValues.value.period_orders) changed.push('period_orders')
  if (newStats.confirmed_shoots !== prevValues.value.confirmed_shoots) changed.push('confirmed_shoots')
  if (newStats.completion_rate !== prevValues.value.completion_rate) changed.push('completion_rate')
  if (newStats.avg_rating !== prevValues.value.avg_rating) changed.push('avg_rating')

  prevValues.value = { ...newStats }
  stats.value = newStats
  updatedKeys.value = changed

  if (changed.length) {
    setTimeout(() => { updatedKeys.value = [] }, 600)
  }
}

const fetchStats = async () => {
  loading.value = true
  try {
    if (props.userId) {
      const res = await getPublicPhotographerDashboard(props.userId)
      publicDashboard.value = normalizePublicDashboard(res.data)
      return
    }

    const res = await getPhotographerDashboard({ range: rangeKey.value })
    const normalized = normalizeDashboard(res.data)
    dashboard.value = {
      period: normalized.period,
      trends: normalized.trends,
      revenue: normalized.revenue,
      content: normalized.content,
      top_works: normalized.top_works,
      top_packages: normalized.top_packages,
      todo: normalized.todo,
      schedule: normalized.schedule,
      interactions: normalized.interactions,
      funnel: normalized.funnel,
      project_performance: normalized.project_performance,
    }
    setSummary(normalized.summary)
  } finally {
    loading.value = false
  }
}

const goOrders = (query = {}) => {
  router.push({
    path: '/my-orders',
    query: { role: 'photographer', ...query },
  })
}

const goOrderDetail = (order) => {
  if (order?.id) router.push(`/orders/${order.id}`)
}

const goWorkDetail = (work) => {
  if (work?.id) router.push(`/work/${work.id}`)
}

const goPackageDetail = (pkg) => {
  if (pkg?.id) router.push(`/package/${pkg.id}`)
}

const goProfileTab = (tab) => {
  router.push({ path: '/profile', query: { tab } })
}

const goUploadWork = () => {
  router.push('/upload-work')
}

const goMessages = () => {
  router.push('/messages')
}

const goApplications = () => {
  router.push('/my-applications')
}

const formatDateTime = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatShortDate = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '-'
  return `¥${Number(value).toLocaleString('zh-CN')}`
}

const formatPercent = (value) => {
  if (value === null || value === undefined) return '-'
  return `${value}%`
}

const formatPackageMeta = (pkg) => {
  const parts = []
  if (pkg.price !== null && pkg.price !== undefined) parts.push(`¥${pkg.price}`)
  parts.push(`${pkg.favorite_count} 收藏`)
  if (pkg.booking_count_available) {
    parts.push(`${pkg.booking_count || 0} 预约`)
  } else {
    parts.push('预约数据待接入')
  }
  return parts.join(' · ')
}

const formatPublicPackageMeta = (pkg) => {
  const parts = []
  if (pkg.price !== null && pkg.price !== undefined) parts.push(`¥${pkg.price}`)
  if (pkg.duration) parts.push(`${pkg.duration} 分钟`)
  parts.push(`${pkg.favorite_count} 收藏`)
  return parts.join(' · ')
}

const funnelBarStyle = (node) => {
  const rawWidth = maxFunnelCount.value ? (node.count || 0) / maxFunnelCount.value * 100 : 0
  const width = node.count > 0 ? Math.max(rawWidth, 6) : 0
  return { width: `${Math.min(width, 100)}%` }
}

const formatFunnelRate = (node) => {
  if (node.conversion_rate === null || node.conversion_rate === undefined) {
    return node.key === 'profile_views' ? '漏斗起点' : '暂无上一步基数'
  }
  return `上一步转化 ${node.conversion_rate}%`
}

const statusType = (status) => {
  const map = {
    pending: 'warning',
    confirmed: 'success',
    reschedule_requested: 'warning',
    in_progress: 'success',
    delivered: '',
    received: '',
    reviewed: '',
    completed: 'success',
    cancelled: 'info',
  }
  return map[status] || ''
}

const statusLabel = (status) => {
  const map = {
    pending: '待确认',
    awaiting_customer_payment: '待客户支付',
    confirmed: '已确认',
    reschedule_requested: '改期待确认',
    in_progress: '拍摄中/待交付',
    delivered: '待接收',
    received: '已完成',
    reviewed: '已完成',
    completed: '已完成',
    cancelled: '已取消',
  }
  return map[status] || status
}

onMounted(fetchStats)

watch(() => props.refreshTrigger, () => {
  fetchStats()
})

watch(() => props.userId, () => {
  fetchStats()
})

watch(rangeKey, () => {
  if (!isPublicView.value) fetchStats()
})
</script>

<style scoped>
.stats-section {
  margin-bottom: var(--space-5, 20px);
}

/* ===== 切换栏 ===== */
.dashboard-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4, 16px);
  margin-bottom: var(--space-4, 16px);
  padding: var(--space-2, 8px) var(--space-4, 16px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-lg, 6px);
  background: var(--color-paper-light, #FFFDF9);
}

.dashboard-switcher {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 2px;
}

.view-switch-button {
  height: var(--el-component-size, 36px);
  padding: 0 var(--space-4, 16px);
  border: none;
  border-radius: var(--radius-md, 4px);
  background: transparent;
  color: var(--color-ink-secondary, #6B6560);
  cursor: pointer;
  font-size: var(--text-sm, 0.875rem);
  font-weight: 500;
  line-height: var(--el-component-size, 36px);
  transition: background-color 0.2s, color 0.2s;
}

.view-switch-button:hover {
  background-color: var(--color-brand-light, #EBF2EA);
  color: var(--color-ink, #1A1A1A);
}

.view-switch-button.active {
  background: var(--color-brand-light, #EBF2EA);
  color: var(--color-brand, #2D5A27);
  font-weight: 600;
}

.view-switch-button:focus-visible {
  outline: var(--border-focus, 2px solid var(--color-focus-ring, #2D5A27));
  outline-offset: 2px;
}

.dashboard-toolbar-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3, 12px);
  min-width: 0;
}

.dashboard-toolbar h3 {
  margin: 0;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-base, 1rem);
  line-height: 1.4;
}

.dashboard-toolbar p {
  margin: 0;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.5;
  text-align: right;
}

/* ===== 统计卡片行 ===== */
.stats-row {
  margin-bottom: 0;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-4, 16px);
  min-height: 96px;
  background: var(--color-paper-light, #FFFDF9);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  padding: var(--space-5, 20px) var(--space-4, 16px);
  transition: border-color 0.2s ease;
  cursor: default;
  margin-bottom: var(--space-4, 16px);
}

.stat-card:hover {
  border-color: var(--color-border, #D9D3CB);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md, 4px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-label {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-ink-secondary, #6B6560);
  margin-bottom: var(--space-1, 4px);
}

.stat-value {
  display: flex;
  align-items: baseline;
  gap: var(--space-1, 4px);
}

.stat-number {
  font-size: var(--text-3xl, 2rem);
  font-weight: 700;
  color: var(--color-ink, #1A1A1A);
  line-height: 1.2;
}

.stat-unit {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-ink-secondary, #6B6560);
}

.stat-trend {
  margin-top: 5px;
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.3;
}

.stat-trend.is-up {
  color: var(--color-brand, #2D5A27);
}

.stat-trend.is-down {
  color: var(--color-danger, #C53030);
}

.stat-trend.is-flat {
  color: var(--color-ink-secondary, #6B6560);
}

.stat-trend.is-muted {
  color: var(--color-ink-tertiary, #9C9892);
}

/* ===== 栅格布局 ===== */
.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  gap: var(--space-4, 16px);
}

.dashboard-section {
  min-width: 0;
  background: var(--color-paper-light, #FFFDF9);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  padding: var(--space-5, 20px);
}

.public-dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: var(--space-4, 16px);
  margin-bottom: var(--space-4, 16px);
}

.public-popular-section {
  margin-top: 0;
}

/* ===== 信任列表（公开视图） ===== */
.trust-list {
  display: grid;
  gap: var(--space-3, 12px);
}

.trust-row {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: var(--space-3, 12px);
  align-items: start;
  min-height: 58px;
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.trust-row.is-muted {
  background: var(--color-paper-light, #FFFDF9);
}

.trust-status {
  width: 9px;
  height: 9px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--color-warning, #8B6914);
}

.trust-status.is-good {
  background: var(--color-brand, #2D5A27);
}

.trust-status.is-muted {
  background: var(--color-ink-tertiary, #9C9892);
}

.trust-row strong {
  display: block;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
  line-height: 1.35;
}

.trust-row small {
  display: block;
  margin-top: 3px;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

/* ===== 公开数据指标 ===== */
.public-metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3, 12px);
}

.public-metric {
  min-height: 78px;
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.public-metric span {
  display: block;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

.public-metric strong {
  display: block;
  margin-top: var(--space-1, 4px);
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-2xl, 1.5rem);
  line-height: 1.2;
}

.public-metric small {
  display: block;
  margin-top: var(--space-1, 4px);
  color: var(--color-ink-tertiary, #9C9892);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

/* ===== 通用标题栏 ===== */
.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3, 12px);
  margin-bottom: var(--space-4, 16px);
}

.section-heading h3,
.guide-copy h3 {
  margin: 0;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-base, 1rem);
  line-height: 1.4;
}

.section-heading p,
.guide-copy p {
  margin: var(--space-1, 4px) 0 0;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.5;
}

/* ===== 待办/日程面板 ===== */
.panel-loading,
.todo-list,
.schedule-panel {
  display: grid;
  gap: var(--space-3, 12px);
}

.todo-row,
.next-order,
.upcoming-row {
  width: 100%;
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  background: var(--color-paper-light, #FFFDF9);
  border-radius: var(--radius-md, 4px);
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.todo-row:hover,
.next-order:hover,
.upcoming-row:hover {
  border-color: var(--color-brand, #2D5A27);
  background: var(--color-brand-light, #EBF2EA);
}

.todo-row {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) max-content 18px;
  align-items: center;
  gap: var(--space-3, 12px);
  min-height: 62px;
  padding: var(--space-3, 12px);
  text-align: left;
}

.todo-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md, 4px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.todo-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.todo-label,
.upcoming-title {
  overflow: hidden;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todo-desc {
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
}

.todo-count {
  min-width: 28px;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-2xl, 1.5rem);
  line-height: 1;
  text-align: right;
}

.todo-arrow {
  color: var(--color-ink-tertiary, #9C9892);
}

/* ===== 日程 ===== */
.schedule-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3, 12px);
}

.schedule-metric {
  min-height: 64px;
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.schedule-metric span {
  display: block;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  margin-bottom: var(--space-1, 4px);
}

.schedule-metric strong {
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-2xl, 1.5rem);
  line-height: 1;
}

.next-order {
  display: grid;
  gap: var(--space-1, 4px);
  padding: var(--space-4, 16px);
  text-align: left;
}

.next-order.is-empty {
  cursor: default;
  background: var(--color-paper, #FAF7F2);
}

.next-order.is-empty:hover {
  border-color: var(--color-border-light, #EBE5DE);
  background: var(--color-paper, #FAF7F2);
}

.next-label {
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
}

.next-order strong {
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-lg, 1.125rem);
}

.next-order span:last-child {
  overflow: hidden;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-sm, 0.875rem);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upcoming-list {
  display: grid;
  gap: var(--space-2, 8px);
}

.upcoming-row {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr) max-content;
  align-items: center;
  gap: var(--space-3, 12px);
  min-height: 44px;
  padding: var(--space-2, 8px) var(--space-3, 12px);
  text-align: left;
}

.upcoming-time {
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  white-space: nowrap;
}

/* ===== 空状态 ===== */
.quiet-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 88px;
  color: var(--color-ink-tertiary, #9C9892);
  font-size: var(--text-sm, 0.875rem);
  border: 1px dashed var(--color-border, #D9D3CB);
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.quiet-empty.compact {
  min-height: 68px;
  padding: var(--space-2, 8px);
  font-size: var(--text-sm, 0.875rem);
}

/* ===== 收入/内容区块间距 ===== */
.revenue-section,
.content-section,
.funnel-section {
  margin-top: var(--space-4, 16px);
}

.content-layout {
  display: grid;
  grid-template-columns: minmax(240px, 0.9fr) minmax(0, 1.6fr);
  gap: var(--space-4, 16px);
  align-items: start;
}

/* ===== 健康度列表 ===== */
.health-list {
  display: grid;
  gap: var(--space-3, 12px);
}

.health-row {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: var(--space-3, 12px);
  align-items: start;
  min-height: 58px;
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.health-dot {
  width: 9px;
  height: 9px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--color-warning, #8B6914);
}

.health-row.is-good .health-dot {
  background: var(--color-brand, #2D5A27);
}

.health-row strong,
.top-copy strong {
  display: block;
  overflow: hidden;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.health-row small,
.top-copy small {
  display: block;
  margin-top: 3px;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

/* ===== 热门内容栅格 ===== */
.top-content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4, 16px);
}

.top-content-column {
  min-width: 0;
}

.subsection-title {
  margin-bottom: var(--space-2, 8px);
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
}

.top-list {
  display: grid;
  gap: var(--space-2, 8px);
}

.top-row {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr);
  align-items: center;
  gap: var(--space-3, 12px);
  width: 100%;
  min-height: 68px;
  padding: var(--space-2, 8px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper-light, #FFFDF9);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s, background-color 0.2s;
}

.top-row:hover {
  border-color: var(--color-brand, #2D5A27);
  background: var(--color-brand-light, #EBF2EA);
}

.top-thumb {
  width: 54px;
  height: 54px;
  overflow: hidden;
  border-radius: var(--radius-md, 4px);
  background: var(--color-border-light, #EBE5DE);
}

.top-thumb img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.top-copy {
  min-width: 0;
}

/* ===== 收入指标 ===== */
.revenue-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3, 12px);
}

.revenue-metric {
  min-height: 62px;
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.revenue-metric span {
  display: block;
  margin-bottom: var(--space-1, 4px);
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
}

.revenue-metric strong {
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-xl, 1.25rem);
}

.revenue-unavailable {
  padding: var(--space-4, 16px);
  border: 1px dashed var(--color-border, #D9D3CB);
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.6;
}

/* ===== 转化互动栅格 ===== */
.conversion-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: var(--space-4, 16px);
}

.interaction-grid,
.project-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3, 12px);
}

.interaction-metric,
.project-metric {
  min-height: 72px;
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.interaction-metric span,
.project-metric span {
  display: block;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

.interaction-metric strong,
.project-metric strong {
  display: block;
  margin-top: 3px;
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-2xl, 1.5rem);
  line-height: 1.2;
}

.interaction-metric small {
  display: block;
  margin-top: 3px;
  color: var(--color-ink-tertiary, #9C9892);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

/* ===== 转化漏斗 ===== */
.funnel-list {
  display: grid;
  gap: var(--space-3, 12px);
}

.funnel-node {
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper-light, #FFFDF9);
}

.funnel-node-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3, 12px);
  margin-bottom: var(--space-2, 8px);
}

.funnel-node-head span {
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
}

.funnel-node-head strong {
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-lg, 1.125rem);
}

.funnel-bar {
  height: 8px;
  overflow: hidden;
  border-radius: var(--radius-full, 9999px);
  background: var(--color-border-light, #EBE5DE);
}

.funnel-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-brand, #2D5A27);
}

.funnel-node small,
.funnel-note {
  display: block;
  margin-top: 7px;
  color: var(--color-ink-secondary, #6B6560);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.5;
}

.funnel-note {
  padding: var(--space-3, 12px);
  border: 1px dashed var(--color-border, #D9D3CB);
  border-radius: var(--radius-md, 4px);
  background: var(--color-paper, #FAF7F2);
}

.conversion-hints {
  display: grid;
  gap: var(--space-2, 8px);
  margin-top: var(--space-3, 12px);
}

.conversion-hint {
  padding: var(--space-3, 12px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-brand-light, #EBF2EA);
  color: var(--color-ink, #1A1A1A);
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.5;
}

/* ===== 空指引 ===== */
.empty-guide {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4, 16px);
  margin-top: var(--space-4, 16px);
  padding: var(--space-4, 16px) var(--space-5, 20px);
  border: var(--border-light, 1px solid var(--color-border-light, #EBE5DE));
  border-radius: var(--radius-md, 4px);
  background: var(--color-brand-light, #EBF2EA);
}

.guide-copy {
  min-width: 0;
}

.guide-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2, 8px);
}

/* ===== 数值更新动画 ===== */
.animate-pop {
  animation: popIn 0.4s ease;
}

@keyframes popIn {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.stat-fade-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.stat-fade-leave-active {
  transition: opacity 0.2s ease;
}

.stat-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.stat-fade-leave-to {
  opacity: 0;
}

/* ===== 响应式 - 中屏 ===== */
@media (max-width: 900px) {
  .dashboard-grid,
  .public-dashboard-grid,
  .conversion-grid {
    grid-template-columns: 1fr;
  }
}

/* ===== 响应式 - 平板 ===== */
@media (max-width: 767px) {
  .dashboard-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .dashboard-toolbar-meta {
    align-items: stretch;
    flex-direction: column;
  }
  .dashboard-toolbar p {
    text-align: left;
  }
  .stat-card {
    padding: var(--space-4, 16px) var(--space-3, 12px);
  }
  .stat-icon {
    width: 40px;
    height: 40px;
  }
  .stat-number {
    font-size: var(--text-2xl, 1.5rem);
  }
  .empty-guide {
    align-items: stretch;
    flex-direction: column;
  }
  .guide-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .guide-actions .el-button {
    margin-left: 0;
  }
  .revenue-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .content-layout,
  .top-content-grid {
    grid-template-columns: 1fr;
  }
}

/* ===== 响应式 - 手机 ===== */
@media (max-width: 560px) {
  .todo-row {
    grid-template-columns: 34px minmax(0, 1fr) max-content;
  }
  .todo-arrow {
    display: none;
  }
  .upcoming-row {
    grid-template-columns: 1fr;
    gap: var(--space-1, 4px);
  }
  .revenue-grid {
    grid-template-columns: 1fr;
  }
  .interaction-grid,
  .public-metric-grid,
  .project-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
