/**
 * Profile.spec.js — Profile 页面组件测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import Profile from '../../views/Profile.vue'
import { initProfileMode } from '../../composables/useProfileMode'

const { mockGet, mockPut, mockPost, mockPush, mockReplace, mockResolve, mockRoute } = vi.hoisted(() => ({
  mockGet: vi.fn(() => Promise.resolve({
    data: { display_name: 'Test User', bio: 'bio text', avatar_url: '', role: 'customer' },
  })),
  mockPut: vi.fn(() => Promise.resolve({ data: {} })),
  mockPost: vi.fn(() => Promise.resolve({ data: {} })),
  mockPush: vi.fn(),
  mockReplace: vi.fn(() => Promise.resolve()),
  mockResolve: vi.fn((target) => {
    const query = target.query || {}
    const queryString = Object.keys(query)
      .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(query[key])}`)
      .join('&')
    return { fullPath: `${target.path}${queryString ? `?${queryString}` : ''}` }
  }),
  mockRoute: { path: '/', fullPath: '/', params: {}, query: {} },
}))

const { mockGetMyCustomerOrders, mockGetMyPhotographerOrders } = vi.hoisted(() => ({
  mockGetMyCustomerOrders: vi.fn(() => Promise.resolve({ data: [] })),
  mockGetMyPhotographerOrders: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../utils/api', () => ({
  default: {
    get: (...args) => mockGet(...args),
    put: (...args) => mockPut(...args),
    post: (...args) => mockPost(...args),
  },
}))

vi.mock('../../api/order', () => ({
  getMyCustomerOrders: (...args) => mockGetMyCustomerOrders(...args),
  getMyPhotographerOrders: (...args) => mockGetMyPhotographerOrders(...args),
  confirmOrder: vi.fn(() => Promise.resolve({ data: {} })),
  rejectOrder: vi.fn(() => Promise.resolve({ data: {} })),
  deliverWorks: vi.fn(() => Promise.resolve({ data: {} })),
  acceptOrder: vi.fn(() => Promise.resolve({ data: {} })),
  reviewOrder: vi.fn(() => Promise.resolve({ data: {} })),
  getPhotographerStats: vi.fn(() => Promise.resolve({
    data: { monthly_orders: 0, weekly_orders: 0, completion_rate: 0, avg_rating: 0 },
  })),
}))

vi.mock('../../api/photographer', () => ({
  getPhotographerDetail: vi.fn(() => Promise.resolve({ data: { portfolio: [], packages: [] } })),
}))

vi.mock('lucide-vue-next', () => ({
  ArrowLeft: { template: '<span />' },
  ArrowRight: { template: '<span />' },
  Camera: { template: '<span />' },
  Check: { template: '<span />' },
  Eye: { template: '<span />' },
  Heart: { template: '<span />' },
  LoaderCircle: { template: '<span />' },
  Pencil: { template: '<span />' },
  Play: { template: '<span />' },
  Plus: { template: '<span />' },
  RefreshCw: { template: '<span />' },
  Star: { template: '<span />' },
  Ticket: { template: '<span />' },
  Trash2: { template: '<span />' },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    resolve: mockResolve,
    currentRoute: { value: mockRoute },
  }),
  useRoute: () => mockRoute,
}))

describe('Profile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    initProfileMode({ userId: null, role: 'customer' })
    mockGet.mockImplementation(() => Promise.resolve({
      data: { id: 7, display_name: 'Test User', bio: 'bio text', avatar_url: '', role: 'customer' },
    }))
    mockRoute.path = '/'
    mockRoute.fullPath = '/'
    mockRoute.params = {}
    mockRoute.query = {}
  })

  const mountProfile = () => mount(Profile, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'el-avatar': { template: '<div class="el-avatar"><slot /></div>', props: ['size', 'src'] },
        'el-upload': { template: '<div class="el-upload"><slot /></div>' },
        'el-button': { template: '<button class="el-btn"><slot /></button>' },
        'el-switch': { template: '<button class="el-switch"><slot /></button>', props: ['modelValue'] },
        'el-checkbox': { template: '<label class="el-checkbox"><slot /></label>', props: ['modelValue'] },
        'el-radio-group': { template: '<div class="el-radio-group"><slot /></div>', props: ['modelValue'] },
        'el-radio-button': { template: '<button class="el-radio-button"><slot /></button>', props: ['value'] },
        'el-tabs': { template: '<div class="el-tabs"><slot /></div>', props: ['modelValue'] },
        'el-tab-pane': { template: '<div class="el-tab-pane"><slot /></div>', props: ['label', 'name'] },
        'el-table': { template: '<div class="el-table"><slot /></div>', props: ['data'] },
        'el-table-column': { template: '<div class="el-table-col" />' },
        'el-tag': { template: '<span class="el-tag"><slot /></span>' },
        'el-image': { template: '<img :src="src" @error="$emit(\'error\')" />', props: ['src', 'fit', 'lazy'], emits: ['error'] },
        'el-empty': { template: '<div>No data</div>' },
        'el-dialog': { template: '<div><slot /></div>', props: ['modelValue'] },
        'el-divider': { template: '<div><slot /></div>' },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-input': { template: '<input />' },
        'el-input-number': { template: '<input />' },
        'el-select': { template: '<select><slot /></select>' },
        'el-option': { template: '<option />' },
        'el-skeleton': { template: '<div />' },
        'el-skeleton-item': { template: '<div />' },
        'el-icon': { template: '<span />' },
        'el-row': { template: '<div><slot /></div>' },
        'el-col': { template: '<div><slot /></div>' },
        'transition': { template: '<div><slot /></div>' },
        'router-link': { template: '<a><slot /></a>' },
        'PhotographerStats': { template: '<div class="photographer-stats" />' },
        'PhotographerApplicationGate': { template: '<div class="photographer-application-gate" />' },
        'photographer-application-gate': { template: '<div class="photographer-application-gate" />' },
      },
      directives: { loading: {} },
    },
  })

  it('renders profile page wrapper', () => {
    const wrapper = mountProfile()
    expect(wrapper.find('.profile-page').exists()).toBe(true)
  })

  it('renders profile header section', () => {
    const wrapper = mountProfile()
    expect(wrapper.find('.profile-header').exists()).toBe(true)
  })

  it('renders tabs container', () => {
    const wrapper = mountProfile()
    expect(wrapper.find('.el-tabs').exists()).toBe(true)
  })

  it('renders at least 2 tab panes', () => {
    const wrapper = mountProfile()
    const panes = wrapper.findAll('.el-tab-pane')
    expect(panes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders edit button', () => {
    const wrapper = mountProfile()
    expect(wrapper.findAll('.el-btn').length).toBeGreaterThan(0)
  })

  it('shows immutable numeric ID and login username separately', async () => {
    mockGet.mockImplementation((url) => {
      if (url === '/users/me') {
        return Promise.resolve({
          data: {
            id: 8,
            username: 'user_8_temp',
            username_requires_update: true,
            display_name: '测试摄影师1',
            role: 'photographer',
          },
        })
      }
      if (String(url).startsWith('/photographers/profile/')) {
        return Promise.resolve({ data: { portfolio: [], packages: [] } })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.text()).toContain('用户 ID')
    expect(wrapper.text()).toContain('系统生成的唯一数字标识，不可修改。')
    expect(wrapper.text()).toContain('@user_8_temp')
    expect(wrapper.text()).toContain('注册时设置，可用于登录，不可修改。')
  })

  it('falls back to video preview when a video thumbnail fails', async () => {
    mockGet.mockImplementation((url) => {
      if (url === '/users/me') {
        return Promise.resolve({
          data: {
            id: 1,
            display_name: 'Approved Photographer',
            bio: 'bio text',
            avatar_url: '',
            role: 'photographer',
          },
        })
      }
      if (String(url).startsWith('/photographers/profile/')) {
        return Promise.resolve({
          data: {
            portfolio: [
              {
                id: 'video-1',
                url: '/static/videos/demo.mp4',
                media_type: 'video',
                thumbnail_url: '/static/videos/missing-thumb.jpg',
                title: 'Video Work',
              },
            ],
            packages: [],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.find('.work-img-wrap video').exists()).toBe(false)

    await wrapper.find('.work-img-wrap img').trigger('error')
    await nextTick()

    const video = wrapper.find('.work-img-wrap video.work-video-preview')
    expect(video.exists()).toBe(true)
    expect(video.attributes('src')).toContain('/api/v1/photographers/video/stream')
    expect(video.attributes('src')).toContain(encodeURIComponent('/static/videos/demo.mp4'))
  })

  it('shows photographer application gate for customer in photographer-only tab', async () => {
    const wrapper = mountProfile()
    await flushPromises()

    wrapper.vm.switchProfileMode('photographer')
    await nextTick()
    wrapper.vm.activeTab = 'orders'
    await nextTick()

    expect(wrapper.find('.photographer-application-gate').exists()).toBe(true)
  })

  it('uses customer orders on customer profile orders tab', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=orders'
    mockRoute.query = { tab: 'orders' }

    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.vm.profileMode).toBe('customer')
    expect(wrapper.vm.activeTab).toBe('orders')
    expect(mockGetMyCustomerOrders).toHaveBeenCalled()
    expect(mockGetMyPhotographerOrders).not.toHaveBeenCalled()
  })

  it('does not show photographer gate when customer orders are visible', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=orders'
    mockRoute.query = { tab: 'orders' }
    mockGetMyCustomerOrders.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          package_snapshot: '测试方案',
          appointment_time: '2026-06-19T10:00:00',
          notes: '',
          status: 'pending',
        },
      ],
    })

    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.vm.canViewCurrentModeOrders).toBe(true)
    expect(wrapper.find('.photographer-application-gate').exists()).toBe(false)
  })

  it('uses photographer orders on photographer profile orders tab', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=orders'
    mockRoute.query = { tab: 'orders' }
    mockGet.mockImplementation((url) => {
      if (url === '/users/me') {
        return Promise.resolve({
          data: {
            id: 1,
            display_name: 'Approved Photographer',
            bio: 'bio text',
            avatar_url: '',
            role: 'photographer',
          },
        })
      }
      if (String(url).startsWith('/photographers/profile/')) {
        return Promise.resolve({ data: { portfolio: [], packages: [] } })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.vm.profileMode).toBe('photographer')
    expect(wrapper.vm.activeTab).toBe('orders')
    expect(mockGetMyPhotographerOrders).toHaveBeenCalled()
    expect(mockGetMyCustomerOrders).not.toHaveBeenCalled()
  })

  it('keeps selected customer mode after refreshing photographer profile data', async () => {
    mockGet.mockImplementation((url) => {
      if (url === '/users/me') {
        return Promise.resolve({
          data: {
            id: 1,
            display_name: 'Approved Photographer',
            bio: 'bio text',
            avatar_url: '',
            role: 'photographer',
          },
        })
      }
      if (String(url).startsWith('/photographers/profile/')) {
        return Promise.resolve({ data: { portfolio: [], packages: [] } })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.vm.profileMode).toBe('photographer')

    wrapper.vm.switchProfileMode('customer')
    await nextTick()

    expect(localStorage.setItem).toHaveBeenCalledWith('profileMode:1', 'customer')

    await wrapper.vm.fetchUserData()
    await flushPromises()

    expect(wrapper.vm.profileMode).toBe('customer')
  })

  it('removes favorites and liked works from photographer mode', async () => {
    const wrapper = mountProfile()
    await flushPromises()

    expect(wrapper.vm.isTabAvailableForMode('favorites', 'customer')).toBe(true)
    expect(wrapper.vm.isTabAvailableForMode('likes', 'customer')).toBe(true)
    expect(wrapper.vm.isTabAvailableForMode('favorites', 'photographer')).toBe(false)
    expect(wrapper.vm.isTabAvailableForMode('likes', 'photographer')).toBe(false)

    wrapper.vm.activeTab = 'favorites'
    wrapper.vm.switchProfileMode('photographer')
    await nextTick()

    expect(wrapper.vm.activeTab).toBe('works')
  })

  it('does not show photographer application gate for approved photographer applications tab', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=applications'
    mockRoute.query = { tab: 'applications' }
    mockGet.mockImplementation((url) => {
      if (url === '/users/me') {
        return Promise.resolve({
          data: {
            id: 1,
            display_name: 'Approved Photographer',
            bio: 'bio text',
            avatar_url: '',
            role: 'photographer',
          },
        })
      }
      if (String(url).startsWith('/photographers/profile/')) {
        return Promise.resolve({ data: { portfolio: [], packages: [] } })
      }
      if (url === '/projects/my-applications') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              project_id: 9,
              price_quote: 1200,
              status: 'submitted',
              created_at: '2026-06-19T00:00:00',
              project: { title: 'Portrait Project', city: 'Hong Kong' },
            },
          ],
        })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = mountProfile()
    await flushPromises()
    await nextTick()

    expect(wrapper.vm.canUsePhotographerFeatures).toBe(true)
    expect(wrapper.vm.activeTab).toBe('applications')
    expect(wrapper.vm.applications.length).toBe(1)
    expect(wrapper.find('.photographer-application-gate').exists()).toBe(false)
  })

  it('restores favorites package tab from query', () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=favorites&fav=packages'
    mockRoute.query = { tab: 'favorites', fav: 'packages' }

    const wrapper = mountProfile()

    expect(wrapper.vm.activeTab).toBe('favorites')
    expect(wrapper.vm.favTab).toBe('packages')
  })

  it('restores liked works tab from query', () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=likes'
    mockRoute.query = { tab: 'likes' }

    const wrapper = mountProfile()

    expect(wrapper.vm.activeTab).toBe('likes')
  })

  it('navigates favorite work detail with favorites return route', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=favorites&fav=works'
    mockRoute.query = { tab: 'favorites', fav: 'works' }

    const wrapper = mountProfile()
    await wrapper.vm.goFavoriteWork({ work_id: 'work-1', work_data: { id: 'work-1', title: '收藏作品' } })

    expect(mockReplace).not.toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith({
      path: '/work/work-1',
      state: {
        from: '/profile?tab=favorites&fav=works',
        work: { id: 'work-1', title: '收藏作品' },
      },
    })
  })

  it('navigates favorite package detail with package favorites return route', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=favorites&fav=packages'
    mockRoute.query = { tab: 'favorites', fav: 'packages' }

    const wrapper = mountProfile()
    await wrapper.vm.goFavoritePackage({ package_id: 'package-1' })

    expect(mockReplace).not.toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith({
      path: '/package/package-1',
      state: { from: '/profile?tab=favorites&fav=packages' },
    })
  })

  it('navigates liked work detail with liked works return route', async () => {
    mockRoute.path = '/profile'
    mockRoute.fullPath = '/profile?tab=likes'
    mockRoute.query = { tab: 'likes' }

    const wrapper = mountProfile()
    await wrapper.vm.goLikedWork({ work_id: 'work-2', work_data: { id: 'work-2', title: 'Liked Work' } })

    expect(mockReplace).not.toHaveBeenCalled()
    expect(mockPush).toHaveBeenCalledWith({
      path: '/work/work-2',
      state: {
        from: '/profile?tab=likes',
        work: { id: 'work-2', title: 'Liked Work' },
      },
    })
  })
})
