import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ImageGenerationComposer from './ImageGenerationComposer.vue'

const value = () => ({
  mode: null,
  aspect_ratio: '1:1',
  count: 1,
  quality: 'standard',
  strength: 0.65,
})

describe('ImageGenerationComposer', () => {
  it('emits a structured generation mode instead of changing message text', async () => {
    const wrapper = mount(ImageGenerationComposer, { props: { modelValue: value() } })

    await wrapper.findAll('.mode-row button')[1].trigger('click')

    expect(wrapper.emitted('update:modelValue')[0][0]).toMatchObject({ mode: 'text_to_image' })
    expect(wrapper.emitted('mode-change')[0]).toEqual(['text_to_image'])
  })

  it('exposes progressive settings only while a generation mode is active', async () => {
    const wrapper = mount(ImageGenerationComposer, {
      props: { modelValue: { ...value(), mode: 'image_to_image' } },
    })

    expect(wrapper.find('.settings-panel').exists()).toBe(false)
    await wrapper.get('.settings-toggle').trigger('click')

    expect(wrapper.get('.settings-panel').text()).toContain('修改强度')
    expect(wrapper.findAll('select')).toHaveLength(3)
  })
})
