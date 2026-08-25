import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AIShootContextCard from './AIShootContextCard.vue'

const success = {
  schema_version: 'shoot_context_v1',
  status: 'success' as const,
  place: { name: '香港石澳泳滩', address: '香港, 石澳', latitude: 22.23, longitude: 114.25 },
  weather: {
    forecast_date: '2026-08-08', provider: 'open_meteo', updated_at: '2026-08-03T12:00:00Z',
    hourly: [{ time: '16:00', temperature_c: 30, precipitation_probability: 20, wind_kph: 18 }],
  },
  sunlight: { sunrise: '05:55', sunset: '18:58', golden_hour_start: '18:13', golden_hour_end: '18:58', blue_hour_end: '19:25' },
  recommendations: [{ code: 'golden_hour', severity: 'info' as const, title: '适合户外人像', detail: '日落前是柔和光线窗口' }],
}

describe('AIShootContextCard', () => {
  it('renders success weather and sunlight fields', () => {
    const wrapper = mount(AIShootContextCard, {
      props: { context: success },
      global: { stubs: { LocationMap: true } },
    })
    expect(wrapper.text()).toContain('香港石澳泳滩')
    expect(wrapper.text()).toContain('16:00')
    expect(wrapper.text()).toContain('18:13-18:58')
    expect(wrapper.text()).toContain('适合户外人像')
  })

  it('explains ambiguous and failed states', () => {
    const ambiguous = mount(AIShootContextCard, {
      props: {
        context: {
          schema_version: 'shoot_context_v1', status: 'ambiguous', place: null,
          place_candidates: [{ name: '石澳泳滩', latitude: 22.23, longitude: 114.25 }],
        },
      },
      global: { stubs: { LocationMap: true } },
    })
    expect(ambiguous.text()).toContain('请确认拍摄地点')

    const failed = mount(AIShootContextCard, {
      props: { context: { schema_version: 'shoot_context_v1', status: 'failed', place: null } },
      global: { stubs: { LocationMap: true } },
    })
    expect(failed.text()).toContain('暂时无法获取拍摄环境')
  })

  it('emits the selected place candidate from an accessible button', async () => {
    const candidate = {
      name: '成都', address: '成都, 成都市, 四川, 中国', latitude: 30.66667, longitude: 104.06667,
    }
    const wrapper = mount(AIShootContextCard, {
      props: {
        context: {
          schema_version: 'shoot_context_v1', status: 'ambiguous', place: null,
          place_candidates: [candidate],
        },
      },
      global: { stubs: { LocationMap: true } },
    })

    const button = wrapper.get('button[aria-label="选择地点：成都, 成都市, 四川, 中国"]')
    await button.trigger('click')

    expect(wrapper.emitted('select-candidate')?.[0]).toEqual([candidate])
  })
})
