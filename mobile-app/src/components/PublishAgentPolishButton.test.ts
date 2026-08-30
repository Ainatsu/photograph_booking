import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PublishAgentPolishButton from './PublishAgentPolishButton.vue'

const polishPublishFields = vi.fn()

vi.mock('@/api/ai', () => ({
  polishPublishFields: (...args: unknown[]) => polishPublishFields(...args),
}))

describe('PublishAgentPolishButton', () => {
  beforeEach(() => {
    polishPublishFields.mockReset()
  })

  it('sends text fields and emits the polished result', async () => {
    let resolveRequest: ((value: { fields: Record<string, unknown>; polished_field_count: number }) => void) | undefined
    polishPublishFields.mockReturnValue(new Promise((resolve) => {
      resolveRequest = resolve
    }))
    const polishedResult = {
      fields: { title: '润色后的标题', tags: ['人像'] },
      polished_field_count: 2,
    }
    const fields = { title: '原始标题', tags: ['人像'] }
    const wrapper = mount(PublishAgentPolishButton, {
      props: { contentType: 'work', fields },
    })

    await wrapper.get('button').trigger('click')
    expect(wrapper.get('button').attributes('aria-busy')).toBe('true')
    resolveRequest?.(polishedResult)
    await flushPromises()

    expect(polishPublishFields).toHaveBeenCalledWith('work', fields)
    expect(wrapper.emitted('busy-change')).toEqual([[true], [false]])
    expect(wrapper.emitted('polished')?.[0]).toEqual([
      { title: '润色后的标题', tags: ['人像'] },
      2,
    ])
  })
})
