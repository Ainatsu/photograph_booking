import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ProjectLocationField from '../location/ProjectLocationField.vue'

vi.mock('lucide-vue-next', () => ({
  ChevronRight: { template: '<span />' },
  MapPin: { template: '<span />' },
}))

describe('ProjectLocationField', () => {
  const mountField = (modelValue = {}) => mount(ProjectLocationField, {
    props: { modelValue, city: '香港' },
    global: {
      stubs: {
        LocationMap: { template: '<div class="map-stub" />' },
        LocationPickerDialog: {
          template: '<button class="confirm-stub" @click="$emit(\'confirm\', { name: \'中环街市\', address: \'香港中环\', latitude: 22.284, longitude: 114.154, provider: \'openstreetmap\', coordinate_system: \'WGS84\', precision: \'exact\' })">确认</button>',
          emits: ['confirm', 'update:modelValue'],
        },
        'el-input': {
          props: ['modelValue'],
          template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
      },
    },
  })

  it('emits a structured location after confirmation', async () => {
    const wrapper = mountField()
    await wrapper.find('.confirm-stub').trigger('click')
    const value = wrapper.emitted('update:modelValue')[0][0]
    expect(value).toMatchObject({ text: '中环街市', latitude: 22.284, longitude: 114.154, coordinate_system: 'WGS84' })
  })

  it('keeps free-form location text as a fallback', async () => {
    const wrapper = mountField({ text: '' })
    await wrapper.find('input').setValue('海边或室内棚拍')
    expect(wrapper.emitted('update:modelValue')[0][0].text).toBe('海边或室内棚拍')
  })
})
