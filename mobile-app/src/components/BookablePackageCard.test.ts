import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BookablePackageCard from './BookablePackageCard.vue'

const item = {
  id: 'pkg-1', package_name: '日系城市人像', price: 1299, duration: 120, styles: ['日系', '自然光'], samples: [],
  photographer_id: 12, photographer_name: '林川', distance_km: 4.2, distance_label: '约 4.2 km', distance_confidence: 'exact',
  availability: { date: '2026-08-08', timezone: 'Asia/Hong_Kong', matching_slots: [{ start_at: '2026-08-08T14:00:00+08:00', end_at: '2026-08-08T16:00:00+08:00', label: '14:00–16:00' }], snapshot_expires_at: '2099-08-01T00:00:00+08:00' },
  match: { overall_score: 0.88 }, recommendation_reasons: ['风格标签与你的需求匹配'], warnings: [],
}

describe('BookablePackageCard', () => {
  it('shows comparison fields and emits both actions', async () => {
    const wrapper = mount(BookablePackageCard, { props: { item } })
    expect(wrapper.text()).toContain('日系城市人像')
    expect(wrapper.text()).toContain('约 4.2 km')
    expect(wrapper.text()).toContain('14:00–16:00')
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    expect(wrapper.emitted('details')?.[0]?.[0]).toEqual(item)
    expect(wrapper.emitted('select-time')?.[0]?.[0]).toEqual(item)
  })

  it('switches the primary action to refresh when the snapshot has expired', async () => {
    const expired = {
      ...item,
      availability: { ...item.availability, snapshot_expires_at: '2020-01-01T00:00:00+08:00' },
    }
    const wrapper = mount(BookablePackageCard, { props: { item: expired } })
    const primary = wrapper.findAll('button')[1]
    expect(primary.text()).toBe('刷新档期')
    await primary.trigger('click')
    expect(wrapper.emitted('refresh')?.[0]?.[0]).toEqual(expired)
    expect(wrapper.emitted('select-time')).toBeUndefined()
  })
})
