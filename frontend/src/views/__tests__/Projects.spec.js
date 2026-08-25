import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import Projects from '../../views/Projects.vue'
import { setProfileMode } from '../../composables/useProfileMode'

const { mockGet, mockGetProjects, mockGetRecommendedProjects, mockTrackRecommendationEvents, mockPush } = vi.hoisted(() => ({
  mockGet: vi.fn(() => Promise.resolve({ data: { id: 1, role: 'photographer' } })),
  mockGetProjects: vi.fn(() => Promise.resolve({ data: [] })),
  mockGetRecommendedProjects: vi.fn(() => Promise.resolve({
    data: { items: [], recommendation_id: 'test-recommendation', algorithm_version: 'test' },
  })),
  mockTrackRecommendationEvents: vi.fn(() => Promise.resolve()),
  mockPush: vi.fn(),
}))

vi.mock('../../utils/api', () => ({
  default: {
    get: (...args) => mockGet(...args),
  },
}))

vi.mock('../../api/project', () => ({
  getProjects: (...args) => mockGetProjects(...args),
}))

vi.mock('../../api/recommendation', () => ({
  getRecommendedProjects: (...args) => mockGetRecommendedProjects(...args),
  trackRecommendationEvents: (...args) => mockTrackRecommendationEvents(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

vi.mock('lucide-vue-next', () => ({
  FolderOpen: { template: '<span />' },
  MapPin: { template: '<span />' },
  Plus: { template: '<span />' },
  RefreshCw: { template: '<span />' },
  Search: { template: '<span />' },
  Ticket: { template: '<span />' },
}))

describe('Projects', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    localStorage.setItem('token', 'test-token')
    mockGet.mockResolvedValue({ data: { id: 1, role: 'photographer' } })
    mockGetProjects.mockResolvedValue({ data: [] })
    mockGetRecommendedProjects.mockResolvedValue({
      data: { items: [], recommendation_id: 'test-recommendation', algorithm_version: 'test' },
    })
    vi.stubGlobal('IntersectionObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    })
  })

  const mountProjects = () => mount(Projects, {
    global: {
      stubs: {
        'el-button': { template: '<button><slot /></button>' },
        'el-input': { template: '<input />', props: ['modelValue', 'placeholder', 'clearable'] },
        'el-input-number': { template: '<input />', props: ['modelValue', 'min', 'step', 'placeholder'] },
        'el-empty': { template: '<div />' },
        'el-image': { template: '<img />', props: ['src', 'fit'] },
        'el-tag': { template: '<span><slot /></span>' },
      },
      directives: { loading: {} },
    },
  })

  it('defaults project actions to the account role when no mode is stored', async () => {
    const wrapper = mountProjects()
    await flushPromises()

    expect(wrapper.vm.isPhotographer).toBe(true)
    expect(wrapper.vm.isCustomer).toBe(false)
  })

  it('uses stored customer mode for a photographer account', async () => {
    localStorage.setItem('profileMode:1', 'customer')

    const wrapper = mountProjects()
    await flushPromises()

    expect(wrapper.vm.isCustomer).toBe(true)
    expect(wrapper.vm.isPhotographer).toBe(false)
  })

  it('updates project actions when profile mode changes', async () => {
    const wrapper = mountProjects()
    await flushPromises()

    expect(wrapper.vm.isPhotographer).toBe(true)

    setProfileMode('customer')
    await nextTick()

    expect(wrapper.vm.isCustomer).toBe(true)
    expect(wrapper.vm.isPhotographer).toBe(false)
  })

  it('does not show personal project actions when logged out', async () => {
    localStorage.clear()
    mockGet.mockClear()

    const wrapper = mountProjects()
    await flushPromises()

    expect(wrapper.vm.isCustomer).toBe(false)
    expect(wrapper.vm.isPhotographer).toBe(false)
    expect(mockGet).not.toHaveBeenCalled()
  })
})
