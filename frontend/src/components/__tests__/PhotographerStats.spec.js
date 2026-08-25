/**
 * PhotographerStats.spec.js — PhotographerStats 组件测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PhotographerStats from '../../components/PhotographerStats.vue'

const { mockGetStats, mockGetPublicDashboard } = vi.hoisted(() => ({
  mockGetStats: vi.fn(() => Promise.resolve({
    data: {
      period: {
        range_key: 'month',
        label: '本月',
        has_comparison: true,
      },
      summary: {
        monthly_orders: 5,
        weekly_orders: 2,
        period_orders: 5,
        confirmed_shoots: 3,
        completion_rate: 85.5,
        avg_rating: 4.2,
      },
      trends: {
        has_comparison: true,
        period_orders_delta: 2,
        confirmed_shoots_delta: 1,
        completion_rate_delta: -3.5,
        avg_rating_delta: 0.2,
      },
      revenue: {
        available: false,
        reason: '订单尚未记录结构化金额字段，暂不展示收入统计。',
      },
      content: {
        portfolio_count: 2,
        package_count: 2,
        packages_with_samples: 1,
        recent_upload_count: 1,
      },
      top_works: [
        {
          id: 'work-1',
          title: '春日写真',
          url: '/static/portfolios/work-1.jpg',
          thumbnail_url: '/static/portfolios/work-1-thumb.jpg',
          like_count: 2,
          favorite_count: 1,
          total_interactions: 3,
        },
      ],
      top_packages: [
        {
          id: 'pkg-1',
          name: '个人写真',
          price: 699,
          sample_url: '/static/package_samples/pkg-1.jpg',
          favorite_count: 2,
          booking_count: null,
          booking_count_available: false,
        },
      ],
      todo: {
        pending_orders: 1,
        reschedule_requests: 0,
        orders_to_deliver: 2,
        orders_waiting_review: 1,
      },
      schedule: {
        today_orders: 1,
        week_confirmed_orders: 3,
        next_order: {
          id: 12,
          package_snapshot: '个人写真 - ¥699/120分钟',
          appointment_time: '2026-07-01T14:00:00',
          duration_minutes: 120,
          status: 'confirmed',
          customer_id: 1,
          customer_name: '测试客户',
        },
        upcoming_orders: [],
      },
      interactions: {
        new_followers: 1,
        message_conversations: 2,
        work_likes: 3,
        work_favorites: 1,
        package_favorites: 2,
        profile_views: 8,
        portfolio_views: 4,
        package_views: 3,
      },
      funnel: {
        tracked_event_count: 15,
        nodes: [
          { key: 'profile_views', label: '主页访问', count: 8, conversion_rate: null, source: 'analytics_events.profile_view' },
          { key: 'work_interactions', label: '作品互动', count: 4, conversion_rate: 50, source: 'likes + work favorites' },
          { key: 'package_favorites', label: '套餐收藏', count: 2, conversion_rate: 50, source: 'package favorites' },
          { key: 'message_conversations', label: '私信咨询', count: 2, conversion_rate: 100, source: 'messages' },
          { key: 'created_orders', label: '创建预约', count: 1, conversion_rate: 50, source: 'orders.created_at' },
          { key: 'completed_orders', label: '完成订单', count: 1, conversion_rate: 100, source: 'orders.status' },
        ],
      },
      project_performance: {
        submitted_applications: 2,
        selected_applications: 1,
        converted_orders: 1,
        application_conversion_rate: 50,
        average_quote: 799,
        budget_match_rate: 50,
        budget_match_sample_count: 2,
      },
    },
  })),
  mockGetPublicDashboard: vi.fn(() => Promise.resolve({
    data: {
      trust: {
        completed_orders: 8,
        avg_rating: 4.8,
        rating_count: 6,
        rating_visible: true,
        completion_rate: 92.3,
        completion_rate_visible: true,
        completion_sample_count: 13,
        recent_order_activity: true,
      },
      content: {
        portfolio_count: 9,
        package_count: 3,
        packages_with_samples: 2,
        recent_upload_count: 1,
      },
      top_works: [
        {
          id: 'public-work-1',
          title: '公开热门作品',
          url: '/static/portfolios/public-work-1.jpg',
          thumbnail_url: '/static/portfolios/public-work-1-thumb.jpg',
          like_count: 4,
          favorite_count: 2,
          total_interactions: 6,
        },
      ],
      top_packages: [
        {
          id: 'public-pkg-1',
          name: '公开热门套餐',
          price: 899,
          duration: 120,
          sample_url: '/static/package_samples/public-pkg-1.jpg',
          favorite_count: 5,
          booking_count: null,
          booking_count_available: false,
        },
      ],
    },
  })),
}))

vi.mock('../../api/order', () => ({
  getPhotographerDashboard: (...args) => mockGetStats(...args),
  getPublicPhotographerDashboard: (...args) => mockGetPublicDashboard(...args),
}))

vi.mock('lucide-vue-next', () => ({
  ArrowRight: { name: 'ArrowRight', template: '<span />' },
  Calendar: { name: 'Calendar', template: '<span />' },
  ChartNoAxesCombined: { name: 'ChartNoAxesCombined', template: '<span />' },
  CircleCheckBig: { name: 'CircleCheckBig', template: '<span />' },
  Clock: { name: 'Clock', template: '<span />' },
  Plus: { name: 'Plus', template: '<span />' },
  Star: { name: 'Star', template: '<span />' },
  Ticket: { name: 'Ticket', template: '<span />' },
  TrendingUp: { name: 'TrendingUp', template: '<span />' },
  TriangleAlert: { name: 'TriangleAlert', template: '<span />' },
  Upload: { name: 'Upload', template: '<span />' },
}))

describe('PhotographerStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mountStats = (props = {}) => mount(PhotographerStats, {
    props: { refreshTrigger: 0, ...props },
    global: {
      stubs: {
        'el-row': { template: '<div class="el-row"><slot /></div>' },
        'el-col': { template: '<div class="el-col"><slot /></div>' },
        'el-skeleton': { template: '<div class="el-skeleton"><slot name="template" /></div>' },
        'el-skeleton-item': { template: '<div class="el-skeleton-item" />' },
        'el-icon': { template: '<span class="el-icon" />', props: ['size'] },
        'el-button': { template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>' },
        'el-tag': { template: '<span class="el-tag"><slot /></span>' },
        'el-segmented': {
          props: ['modelValue', 'options'],
          template: '<div class="el-segmented"></div>',
        },
        'transition': { template: '<div><slot /></div>' },
      },
    },
  })

  it('renders stats section', () => {
    const wrapper = mountStats()
    expect(wrapper.find('.stats-section').exists()).toBe(true)
  })

  it('calls getPhotographerDashboard on mount', () => {
    mountStats()
    expect(mockGetStats).toHaveBeenCalledWith({ range: 'month' })
  })

  it('renders stat cards when loaded', async () => {
    const wrapper = mountStats()
    await new Promise(r => setTimeout(r, 100))
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.stat-card').length).toBe(4)
  })

  it('renders grouped dashboard panels when loaded', async () => {
    const wrapper = mountStats()
    await new Promise(r => setTimeout(r, 100))
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.dashboard-section').length).toBe(1)
    expect(wrapper.findAll('.view-switch-button').length).toBe(4)
    expect(wrapper.text()).toContain('较上周期 +2单')
    expect(wrapper.text()).toContain('收入指标')

    await wrapper.findAll('.view-switch-button')[1].trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.todo-row').length).toBe(4)
    expect(wrapper.text()).toContain('近期日程')

    await wrapper.findAll('.view-switch-button')[2].trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('内容健康度')
    expect(wrapper.text()).toContain('春日写真')
    expect(wrapper.text()).toContain('预约数据待接入')

    await wrapper.findAll('.view-switch-button')[3].trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('客户互动')
    expect(wrapper.text()).toContain('转化漏斗')
    expect(wrapper.text()).toContain('企划表现')
    expect(wrapper.text()).toContain('主页访问')
  })

  it('refetches on refreshTrigger change', async () => {
    const wrapper = mountStats({ refreshTrigger: 0 })
    await new Promise(r => setTimeout(r, 100))
    await wrapper.vm.$nextTick()
    mockGetStats.mockClear()

    await wrapper.setProps({ refreshTrigger: 1 })
    await new Promise(r => setTimeout(r, 100))
    expect(mockGetStats).toHaveBeenCalled()
  })

  it('renders public trust dashboard for another photographer', async () => {
    const wrapper = mountStats({ userId: 7 })
    await new Promise(r => setTimeout(r, 100))
    await wrapper.vm.$nextTick()

    expect(mockGetPublicDashboard).toHaveBeenCalledWith(7)
    expect(mockGetStats).not.toHaveBeenCalled()
    expect(wrapper.find('.dashboard-toolbar').exists()).toBe(false)
    expect(wrapper.text()).toContain('服务可信度')
    expect(wrapper.text()).toContain('内容活跃度')
    expect(wrapper.text()).toContain('热门内容')
    expect(wrapper.text()).toContain('公开热门作品')
    expect(wrapper.text()).toContain('公开热门套餐')
    expect(wrapper.text()).not.toContain('私信会话')
    expect(wrapper.text()).not.toContain('转化漏斗')
  })
})
