import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElInputTag } from 'element-plus/es/components/input-tag/index.mjs'
import { defineComponent, ref } from 'vue'
import RegionSelector from '../RegionSelector.vue'
import TagInput from '../TagInput.vue'

describe('shared form inputs', () => {
  it('keeps created tags inside the input control', async () => {
    const Host = defineComponent({
      components: { TagInput },
      setup() {
        const tags = ref(['人像'])
        return { tags }
      },
      template: '<TagInput v-model="tags" placeholder="输入风格后按回车添加" />',
    })
    const wrapper = mount(Host, {
      global: { components: { ElInputTag } },
    })

    const inputControl = wrapper.find('.el-input-tag')
    expect(inputControl.findAll('.el-tag')).toHaveLength(1)

    const input = inputControl.find('input')
    await input.setValue('日系')
    await input.trigger('keydown', { code: 'Enter', key: 'Enter' })

    expect(wrapper.vm.tags).toEqual(['人像', '日系'])
    expect(inputControl.findAll('.el-tag')).toHaveLength(2)
    expect(wrapper.find('.tag-input-tags').exists()).toBe(false)
  })

  it('deduplicates tags created from the shared input', async () => {
    const wrapper = mount(TagInput, {
      props: { modelValue: ['日系'] },
      global: { components: { ElInputTag } },
    })

    await wrapper.find('input').setValue('日系')
    await wrapper.find('input').trigger('keydown', { code: 'Enter', key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual(['日系'])
  })

  it('does not render a duplicate region tag after selection', () => {
    const wrapper = mount(RegionSelector, {
      props: { modelValue: '中国大陆 · 四川省 · 成都市' },
      global: {
        stubs: {
          'el-select': { template: '<div class="el-select"><slot /></div>' },
          'el-option': { template: '<span class="el-option" />' },
          'el-cascader': { template: '<div class="el-cascader" />' },
          'el-tag': { template: '<span class="el-tag"><slot /></span>' },
        },
      },
    })

    expect(wrapper.find('.region-selector').exists()).toBe(true)
    expect(wrapper.find('.el-tag').exists()).toBe(false)
  })
})
