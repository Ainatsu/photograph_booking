import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import Gallery from '../../views/Gallery.vue'

const { mockGetAllPackages, mockGetAllWorks, mockGetPhotographerList, mockGetProjects, mockPush, mockRoute } = vi.hoisted(() => ({
  mockGetAllPackages: vi.fn(() => Promise.resolve({ data: [] })),
  mockGetAllWorks: vi.fn(() => Promise.resolve({ data: [] })),
  mockGetPhotographerList: vi.fn(() => Promise.resolve({ data: [] })),
  mockGetProjects: vi.fn(() => Promise.resolve({ data: [] })),
  mockPush: vi.fn(),
  mockRoute: { path: '/works', fullPath: '/works?q=成都', params: {}, query: { q: '成都' } },
}))

vi.mock('../../api/photographer', () => ({
  getAllPackages: (...args) => mockGetAllPackages(...args),
  getAllWorks: (...args) => mockGetAllWorks(...args),
  getPhotographerList: (...args) => mockGetPhotographerList(...args),
}))

vi.mock('../../api/project', () => ({
  getProjects: (...args) => mockGetProjects(...args),
}))

vi.mock('../../api/recommendation', () => ({
  getRecommendedPackages: vi.fn(() => Promise.resolve({ data: { items: [] } })),
  getRecommendedWorks: vi.fn(() => Promise.resolve({ data: { items: [] } })),
  trackRecommendationEvents: vi.fn(() => Promise.resolve()),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
    currentRoute: { value: mockRoute },
  }),
  useRoute: () => mockRoute,
}))

vi.mock('lucide-vue-next', () => ({
  Play: { template: '<span />' },
  Plus: { template: '<span />' },
}))

describe('Gallery project search', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRoute.path = '/works'
    mockRoute.fullPath = '/works?q=成都'
    mockRoute.query = { q: '成都' }
    mockGetAllPackages.mockResolvedValue({ data: [] })
    mockGetAllWorks.mockResolvedValue({ data: [] })
    mockGetPhotographerList.mockResolvedValue({ data: [] })
    mockGetProjects.mockResolvedValue({
      data: [
        {
          id: 42,
          title: '成都婚礼企划',
          description: '寻找婚礼摄影师',
          category: '婚礼',
          city: '成都',
          style_tags: ['纪实'],
          reference_images: [],
          status: 'open',
          budget_min: 800,
          budget_max: 1200,
          shoot_date_start: '2026-08-01T00:00:00Z',
          application_count: 2,
        },
        {
          id: 43,
          title: '上海人像企划',
          description: '城市人像记录',
          category: '人像',
          city: '上海',
          style_tags: [],
          reference_images: [],
          status: 'open',
        },
      ],
    })
  })

  const mountGallery = () => mount(Gallery, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'el-avatar': { template: '<div><slot /></div>', props: ['size', 'src'] },
        'el-button': { template: '<button><slot /></button>' },
        'el-empty': { template: '<div class="el-empty" />', props: ['description'] },
        'el-icon': { template: '<span><slot /></span>' },
        'el-image': { template: '<img :src="src" />', props: ['src', 'fit', 'lazy', 'alt'] },
        'el-tag': { template: '<span><slot /></span>', props: ['size', 'effect'] },
      },
      directives: { loading: {} },
    },
  })

  it('loads and filters public projects from the project search tab', async () => {
    const wrapper = mountGallery()
    await flushPromises()

    const projectTab = wrapper.findAll('.filter-btn').find((button) => button.text().includes('企划'))
    expect(projectTab).toBeTruthy()

    await projectTab.trigger('click')
    await flushPromises()

    expect(mockGetProjects).toHaveBeenCalledWith({ limit: 200 })
    expect(wrapper.findAll('.gallery-project-card')).toHaveLength(1)
    expect(wrapper.find('.gallery-project-card').text()).toContain('成都婚礼企划')
    expect(projectTab.classes()).toContain('filter-btn-active')
    expect(projectTab.find('.filter-count').text()).toBe('1')
  })

  it('opens a matching project detail when a result is activated', async () => {
    const wrapper = mountGallery()
    await flushPromises()
    const projectTab = wrapper.findAll('.filter-btn').find((button) => button.text().includes('企划'))
    await projectTab.trigger('click')
    await flushPromises()

    await wrapper.find('.gallery-project-card').trigger('keydown', { key: 'Enter' })
    expect(mockPush).toHaveBeenCalledWith('/projects/42')
  })
})
