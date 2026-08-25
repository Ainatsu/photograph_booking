import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AIPageContextCard from './AIPageContextCard.vue'

const context = {
  route_name: 'work-detail',
  route_path: '/works/work-1',
  resource_type: 'portfolio_item' as const,
  resource_id: 'work-1',
  title: '海边日落人像',
  current_object: {},
}

describe('AIPageContextCard', () => {
  it('shows the referenced resource and lets the user cancel it', async () => {
    const wrapper = mount(AIPageContextCard, {
      props: { context, removable: true },
    })

    expect(wrapper.text()).toContain('引用作品')
    expect(wrapper.text()).toContain('海边日落人像')

    const removeButton = wrapper.get('button[aria-label="取消引用"]')
    await removeButton.trigger('click')

    expect(wrapper.emitted('remove')).toHaveLength(1)
  })
})
