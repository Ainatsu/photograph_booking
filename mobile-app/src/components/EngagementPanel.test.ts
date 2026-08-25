import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import EngagementPanel from './EngagementPanel.vue'
import {
  createComment,
  getComments,
  getLikeSummary,
  toggleLike,
} from '@/api/engagement'

vi.mock('@/api/engagement', () => ({
  createComment: vi.fn(),
  getComments: vi.fn(),
  getLikeSummary: vi.fn(),
  toggleLike: vi.fn(),
}))

const mockedCreateComment = vi.mocked(createComment)
const mockedGetComments = vi.mocked(getComments)
const mockedGetLikeSummary = vi.mocked(getLikeSummary)
const mockedToggleLike = vi.mocked(toggleLike)

async function mountPanel(authenticated = false) {
  if (authenticated) localStorage.setItem('token', 'test-token')
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/works/:workId', name: 'work-detail', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
    ],
  })
  await router.push('/works/work-1')
  await router.isReady()

  const wrapper = mount(EngagementPanel, {
    props: { targetType: 'portfolio', targetId: 'work-1' },
    global: {
      plugins: [pinia, router],
      stubs: { IonSpinner: true },
    },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('EngagementPanel', () => {
  beforeEach(() => {
    localStorage.clear()
    mockedGetLikeSummary.mockResolvedValue({ liked: false, count: 2 })
    mockedGetComments.mockResolvedValue({ items: [], total: 0 })
    mockedToggleLike.mockResolvedValue({ liked: true, count: 3 })
    mockedCreateComment.mockResolvedValue({
      id: 9,
      user_id: 4,
      user_display_name: '测试用户',
      target_type: 'portfolio',
      target_id: 'work-1',
      content: '很喜欢这组光线。',
      created_at: '2026-07-23T12:00:00+08:00',
    })
  })

  it('shows a clear login action instead of a disabled comment box for guests', async () => {
    const { wrapper, router } = await mountPanel(false)
    expect(wrapper.text()).toContain('登录后参与讨论')
    await wrapper.get('.login-comment-button').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/works/work-1')
  })

  it('updates like state and prepends a submitted comment for signed-in users', async () => {
    const { wrapper } = await mountPanel(true)
    const likeButton = wrapper.get('button[aria-label="点赞，当前 2 个赞"]')
    await likeButton.trigger('click')
    await flushPromises()
    expect(mockedToggleLike).toHaveBeenCalledWith('portfolio', 'work-1')
    expect(wrapper.text()).toContain('已点赞')

    await wrapper.get('textarea').setValue('很喜欢这组光线。')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mockedCreateComment).toHaveBeenCalledWith('portfolio', 'work-1', '很喜欢这组光线。')
    expect(wrapper.text()).toContain('测试用户')
    expect(wrapper.text()).toContain('很喜欢这组光线。')
  })
})
