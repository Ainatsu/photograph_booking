import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AIContextEntry from '../AIContextEntry.vue'

const {
  assistantState,
  mockGetPackageDetail,
  mockGetPhotographerDetail,
  mockGetProjectDetail,
  mockGetWorkDetail,
  mockRoute,
} = vi.hoisted(() => ({
  assistantState: { mountCount: 0 },
  mockGetPackageDetail: vi.fn(),
  mockGetPhotographerDetail: vi.fn(),
  mockGetProjectDetail: vi.fn(),
  mockGetWorkDetail: vi.fn(),
  mockRoute: {
    name: 'WorkDetail',
    fullPath: '/work/work-1',
    params: { workId: 'work-1' },
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
}))

vi.mock('../../api/photographer', () => ({
  getPackageDetail: (...args) => mockGetPackageDetail(...args),
  getPhotographerDetail: (...args) => mockGetPhotographerDetail(...args),
  getWorkDetail: (...args) => mockGetWorkDetail(...args),
}))

vi.mock('../../api/project', () => ({
  getProjectDetail: (...args) => mockGetProjectDetail(...args),
}))

vi.mock('../../views/AIAssistant.vue', () => ({
  __esModule: true,
  default: {
    name: 'AIAssistant',
    props: ['embedded', 'pageContext', 'quickPrompts', 'contextLabel'],
    emits: ['close'],
    mounted() {
      assistantState.mountCount += 1
    },
    template: `
      <section class="assistant-stub">
        <button type="button" class="assistant-close" @click="$emit('close')">close</button>
        <span class="assistant-label">{{ contextLabel }}</span>
        <span class="assistant-image-url">{{ pageContext?.current_object?.image_url }}</span>
      </section>
    `,
  },
}))

const mountEntry = () => mount(AIContextEntry, {
  props: { enabled: true },
  attachTo: document.body,
  global: {
    stubs: {
      teleport: true,
      'el-icon': { template: '<span><slot /></span>' },
      'el-tooltip': { template: '<div><slot /></div>' },
    },
  },
})

describe('AIContextEntry', () => {
  beforeEach(() => {
    assistantState.mountCount = 0
    document.body.innerHTML = ''
    localStorage.clear()
    mockRoute.name = 'WorkDetail'
    mockRoute.fullPath = '/work/work-1'
    mockRoute.params = { workId: 'work-1' }
    mockGetPackageDetail.mockReset()
    mockGetPhotographerDetail.mockReset()
    mockGetProjectDetail.mockReset()
    mockGetWorkDetail.mockReset()
    mockGetWorkDetail.mockResolvedValue({
      data: {
        id: 'work-1',
        title: 'Spring Portrait',
        tag: 'natural',
        url: '/static/work.jpg',
        images: ['/static/work-full.jpg'],
        user_id: 2,
        user_display_name: 'Test Photographer',
      },
    })
  })

  it('keeps the embedded assistant mounted when the floating panel is closed', async () => {
    const wrapper = mountEntry()
    await flushPromises()

    expect(wrapper.find('.assistant-stub').exists()).toBe(false)

    await wrapper.find('.ai-context-fab').trigger('click')
    await flushPromises()

    expect(wrapper.find('.assistant-stub').exists()).toBe(true)
    expect(assistantState.mountCount).toBe(1)
    expect(wrapper.find('.assistant-image-url').text()).toBe('/static/work-full.jpg')

    await wrapper.find('.assistant-close').trigger('click')
    await flushPromises()

    expect(wrapper.find('.ai-context-panel').exists()).toBe(true)
    expect(wrapper.find('.assistant-stub').exists()).toBe(true)
    expect(wrapper.find('.ai-context-panel').attributes('style')).toContain('display: none')

    await wrapper.find('.ai-context-fab').trigger('click')
    await flushPromises()

    expect(wrapper.find('.assistant-stub').exists()).toBe(true)
    expect(assistantState.mountCount).toBe(1)

    wrapper.unmount()
  })
})
