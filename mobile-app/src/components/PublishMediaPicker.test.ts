import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PublishMediaPicker from './PublishMediaPicker.vue'

describe('PublishMediaPicker', () => {
  it('respects remaining image slots when existing media already uses the limit', async () => {
    const wrapper = mount(PublishMediaPicker, {
      props: {
        files: [],
        inputId: 'portfolio-files',
        mode: 'image',
        imageLimit: 3,
        existingCount: 2,
      },
    })
    const input = wrapper.get('input[type="file"]')
    const candidates = [
      new File(['first'], 'first.jpg', { type: 'image/jpeg' }),
      new File(['second'], 'second.jpg', { type: 'image/jpeg' }),
    ]
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: candidates,
    })

    await input.trigger('change')

    const emittedFiles = wrapper.emitted('update:files')?.[0]?.[0] as File[]
    expect(emittedFiles).toEqual([candidates[0]])
    expect(wrapper.emitted('error')?.[0]?.[0]).toContain('最多选择 1 个文件')
  })
})
