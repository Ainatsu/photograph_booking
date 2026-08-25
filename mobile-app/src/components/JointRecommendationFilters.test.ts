import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import JointRecommendationFilters from './JointRecommendationFilters.vue'

describe('JointRecommendationFilters', () => {
  it('emits normalized structured filters', async () => {
    const wrapper = mount(JointRecommendationFilters, { props: { slots: { budget_max: 1500, style: ['日系'] } } })
    await wrapper.get('.text-button').trigger('click')
    const selects = wrapper.findAll('select')
    await selects[0].setValue('nearest')
    await wrapper.get('input[type="text"]').setValue('日系、人像')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('apply')?.[0]?.[0]).toMatchObject({ sort_mode: 'nearest', budget_max: 1500, styles: ['日系', '人像'] })
  })
})
