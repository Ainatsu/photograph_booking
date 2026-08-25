import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import PhotographerDetail from '../../views/PhotographerDetail.vue'

const { mockGetPhotographerDetail, mockPush, mockRoute } = vi.hoisted(() => ({
  mockGetPhotographerDetail: vi.fn(),
  mockPush: vi.fn(),
  mockRoute: {
    path: '/photographer/42',
    fullPath: '/photographer/42',
    params: { userId: '42' },
    query: {},
  },
}))

vi.mock('../../api/photographer', () => ({
  getPhotographerDetail: (...args) => mockGetPhotographerDetail(...args),
}))

vi.mock('../../api/analytics', () => ({
  trackAnalyticsEvent: vi.fn(() => Promise.resolve()),
}))

vi.mock('../../api/like', () => ({
  getLikeSummary: vi.fn(() => Promise.resolve({ data: { items: {} } })),
  setLikeState: vi.fn(() => Promise.resolve({ data: { liked: true, count: 1 } })),
}))

vi.mock('../../api/favorite', () => ({
  getBatchFavoriteStatus: vi.fn(() => Promise.resolve({ data: {} })),
  getBatchPackageFavoriteStatus: vi.fn(() => Promise.resolve({ data: {} })),
  toggleFavorite: vi.fn(() => Promise.resolve({ data: { favorited: true } })),
  togglePackageFavorite: vi.fn(() => Promise.resolve({ data: { favorited: true } })),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
    currentRoute: { value: mockRoute },
  }),
  useRoute: () => mockRoute,
}))

describe('PhotographerDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockRoute.params = { userId: '42' }
    mockRoute.fullPath = '/photographer/42'
    mockGetPhotographerDetail.mockResolvedValue({
      data: {
        user_id: 42,
        user_role: 'photographer',
        user_display_name: 'Video Maker',
        user_avatar_url: '',
        portfolio: [],
        packages: [],
      },
    })
  })

  const mountDetail = () => mount(PhotographerDetail, {
    global: {
      plugins: [createPinia()],
      stubs: {
        LikeButton: { template: '<button class="like-button" />' },
        FavoriteButton: { template: '<button class="favorite-button" />' },
        PhotographerStats: { template: '<div class="photographer-stats" />' },
        FollowButton: { template: '<button class="follow-button" />' },
        FollowCounts: { template: '<div class="follow-counts" />' },
        Check: { template: '<span />' },
        VideoPlay: { template: '<span />' },
        'el-avatar': { template: '<div class="el-avatar"><slot /></div>', props: ['size', 'src'] },
        'el-button': { template: '<button class="el-button"><slot /></button>' },
        'el-card': { template: '<div class="el-card"><slot /></div>' },
        'el-empty': { template: '<div class="el-empty" />' },
        'el-icon': { template: '<span class="el-icon"><slot /></span>' },
        'el-image': {
          template: '<img :src="src" @error="$emit(\'error\')" />',
          props: ['src', 'fit', 'lazy'],
          emits: ['error'],
        },
        'el-tab-pane': { template: '<div class="el-tab-pane"><slot /></div>', props: ['label', 'name'] },
        'el-tabs': { template: '<div class="el-tabs"><slot /></div>', props: ['modelValue'] },
        'el-tag': { template: '<span class="el-tag"><slot /></span>' },
        'el-tooltip': { template: '<span><slot /></span>' },
      },
      directives: { loading: {} },
    },
  })

  it('falls back to a video stream when a video thumbnail fails', async () => {
    mockGetPhotographerDetail.mockResolvedValue({
      data: {
        user_id: 42,
        user_role: 'photographer',
        user_display_name: 'Video Maker',
        user_avatar_url: '',
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

    const wrapper = mountDetail()
    await flushPromises()

    expect(wrapper.find('.work-card-media video').exists()).toBe(false)

    await wrapper.find('.work-card-media img').trigger('error')
    await nextTick()

    const video = wrapper.find('.work-card-media video.work-video')
    expect(video.exists()).toBe(true)
    expect(video.attributes('src')).toContain('/api/v1/photographers/video/stream')
    expect(video.attributes('src')).toContain(encodeURIComponent('/static/videos/demo.mp4'))
  })

  it('shows public username and opted-in public email', async () => {
    mockGetPhotographerDetail.mockResolvedValueOnce({
      data: {
        user_id: 42,
        user_role: 'photographer',
        user_display_name: 'Public Maker',
        username: 'public_maker',
        public_email: 'hello@example.com',
        portfolio: [],
        packages: [],
      },
    })
    const wrapper = mountDetail()
    await flushPromises()
    expect(wrapper.find('.hero-identity').text()).toContain('@public_maker')
    expect(wrapper.find('a.public-email').attributes('href')).toBe('mailto:hello@example.com')
  })

  it('does not render an empty email placeholder when email is private', async () => {
    const wrapper = mountDetail()
    await flushPromises()
    expect(wrapper.find('.public-email').exists()).toBe(false)
  })
})
