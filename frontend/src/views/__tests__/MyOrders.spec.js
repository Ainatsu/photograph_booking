/**
 * MyOrders.spec.js — MyOrders 页面组件测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import MyOrders from '../../views/MyOrders.vue'

const {
  mockGetCustomer,
  mockGetPhotographer,
  mockApiGet,
  mockAccept,
  mockReview,
  mockStart,
} = vi.hoisted(() => ({
  mockGetCustomer: vi.fn(() => Promise.resolve({ data: [] })),
  mockGetPhotographer: vi.fn(() => Promise.resolve({ data: [] })),
  mockApiGet: vi.fn(() => Promise.resolve({ data: { id: 1, role: 'customer' } })),
  mockAccept: vi.fn(() => Promise.resolve({ data: {} })),
  mockReview: vi.fn(() => Promise.resolve({ data: {} })),
  mockStart: vi.fn(() => Promise.resolve({ data: {} })),
}))

vi.mock('../../api/order', () => ({
  getMyCustomerOrders: (...args) => mockGetCustomer(...args),
  getMyPhotographerOrders: (...args) => mockGetPhotographer(...args),
  confirmOrder: vi.fn(() => Promise.resolve({ data: {} })),
  rejectOrder: vi.fn(() => Promise.resolve({ data: {} })),
  deliverWorks: vi.fn(() => Promise.resolve({ data: {} })),
  acceptOrder: (...args) => mockAccept(...args),
  reviewOrder: (...args) => mockReview(...args),
  startOrder: (...args) => mockStart(...args),
}))

vi.mock('../../utils/api', () => ({
  default: {
    get: (...args) => mockApiGet(...args),
  },
}))

vi.mock('lucide-vue-next', () => ({
  Plus: { template: '<span>+</span>' },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/', params: {}, query: {} }),
}))

describe('MyOrders', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
  })

  const mountMyOrders = () => mount(MyOrders, {
    global: {
      stubs: {
        'el-tabs': { template: '<div class="el-tabs"><slot /></div>', props: ['modelValue'] },
        'el-tab-pane': { template: '<div class="el-tab-pane"><slot /></div>', props: ['label', 'name'] },
        'el-table': { template: '<div class="el-table"><slot /></div>', props: ['data'] },
        'el-table-column': { template: '<div class="el-table-col" />' },
        'el-tag': { template: '<span class="el-tag"><slot /></span>', props: ['type'] },
        'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
        'el-input': { template: '<input />' },
        'el-dialog': { template: '<div><slot /></div>', props: ['modelValue'] },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-upload': { template: '<div><slot /></div>' },
        'el-image': { template: '<img />', props: ['src', 'fit', 'lazy'] },
        'el-empty': { template: '<div>No data</div>' },
        'el-icon': { template: '<span />' },
      },
      directives: { loading: {} },
    },
  })

  it('renders orders page', () => {
    const wrapper = mountMyOrders()
    expect(wrapper.find('.orders-container').exists()).toBe(true)
  })

  it('shows page title', () => {
    const wrapper = mountMyOrders()
    expect(wrapper.find('h2').text()).toBe('我的订单')
  })

  it('calls getMyCustomerOrders on mount', async () => {
    mountMyOrders()
    await vi.waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/users/me', { skipErrorHandler: true })
    })
    await vi.waitFor(() => {
      expect(mockGetCustomer).toHaveBeenCalled()
    })
  })

  it('renders tabs', () => {
    const wrapper = mountMyOrders()
    expect(wrapper.find('.el-tabs').exists()).toBe(true)
  })

  it('accepts a delivered order from the list action', async () => {
    const wrapper = mountMyOrders()
    await wrapper.vm.$.setupState.handleAccept(42)
    expect(mockAccept).toHaveBeenCalledWith(42)
  })

  it('starts a confirmed order before delivery', async () => {
    const wrapper = mountMyOrders()
    await wrapper.vm.$.setupState.startOrderAction(43)
    expect(mockStart).toHaveBeenCalledWith(43)
  })

  it('submits review only after the order is received', async () => {
    const wrapper = mountMyOrders()
    const setup = wrapper.vm.$.setupState
    setup.openReviewDialog({ id: 44, status: 'received' })
    setup.reviewRating = 9
    setup.reviewText = '体验很好'
    await setup.submitReview()
    expect(mockReview).toHaveBeenCalledWith(44, { rating: 9, review_text: '体验很好' })
  })
})
