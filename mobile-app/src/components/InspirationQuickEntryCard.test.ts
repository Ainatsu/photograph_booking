import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import InspirationQuickEntryCard from './InspirationQuickEntryCard.vue'

describe('InspirationQuickEntryCard', () => {
  it('exposes separate open and edit actions', async () => {
    const wrapper = mount(InspirationQuickEntryCard, {
      props: {
        entry: {
          inspiration_id: 12,
          title: 'Forest light',
          summary: 'A compact shooting reference.',
          cover_url: '/static/ai/reference.jpg',
          status: 'draft',
        },
      },
    })

    await wrapper.get('.entry-main').trigger('click')
    await wrapper.get('.entry-edit').trigger('click')

    expect(wrapper.emitted('open')).toHaveLength(1)
    expect(wrapper.emitted('edit')).toHaveLength(1)
    expect(wrapper.get('.entry-edit').attributes('aria-label')).toBe('编辑灵感')
  })

  it('shows generation progress with an accessible status region', () => {
    const wrapper = mount(InspirationQuickEntryCard, {
      props: {
        entry: {
          inspiration_id: 13,
          title: '正在生成灵感',
          status: 'draft',
          generation_status: 'generating',
          total_images: 5,
          completed_images: 2,
          failed_images: 0,
        },
      },
    })

    expect(wrapper.get('[role="status"]').text()).toContain('已完成 2/5')
  })
})
