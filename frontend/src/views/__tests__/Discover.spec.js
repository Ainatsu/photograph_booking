/**
 * Discover.spec.js — Discover 页面组件测试
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Discover from '../../views/Discover.vue'

const { mockGetProfiles } = vi.hoisted(() => ({
  mockGetProfiles: vi.fn(() => Promise.resolve({ data: [] })),
}))

vi.mock('../../api/photographer', () => ({
  getPhotographerList: (...args) => mockGetProfiles(...args),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/', params: {}, query: {} }),
}))

describe('Discover', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const mountDiscover = () => mount(Discover, {
    global: {
      stubs: {
        'el-card': { template: '<div class="el-card"><slot /></div>' },
        'el-image': { template: '<img />', props: ['src', 'fit', 'lazy'] },
        'el-avatar': { template: '<div class="el-avatar"><slot /></div>', props: ['size', 'src'] },
        'el-tag': { template: '<span class="el-tag"><slot /></span>', props: ['size'] },
        'el-empty': { template: '<div class="el-empty"><slot /></div>', props: ['description'] },
      },
      directives: { loading: {} },
    },
  })

  it('renders discover page structure', () => {
    const wrapper = mountDiscover()
    expect(wrapper.find('.discover').exists()).toBe(true)
  })

  it('calls getPhotographerList on mount', () => {
    mountDiscover()
    expect(mockGetProfiles).toHaveBeenCalled()
  })

  it('shows empty state when no photographers loaded', async () => {
    const wrapper = mountDiscover()
    await flushPromises()
    const empty = wrapper.find('.empty-state')
    expect(empty.exists()).toBe(true)
    expect(empty.text()).toContain('暂无摄影师')
  })
})
