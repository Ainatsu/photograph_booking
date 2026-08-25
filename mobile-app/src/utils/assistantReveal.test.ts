import { describe, expect, it } from 'vitest'
import { buildAssistantRevealSchedule } from './assistantReveal'

describe('buildAssistantRevealSchedule', () => {
  it('uses cumulative delays so bubble callbacks stay ordered', () => {
    const steps = buildAssistantRevealSchedule([
      '第一段',
      '第二段内容比较长，因此单段延迟更长',
      '第三段',
      '第四段内容',
    ])

    expect(steps.map((step) => step.visibleCount)).toEqual([2, 3, 4])
    expect(steps[1].delayMs).toBeGreaterThan(steps[0].delayMs)
    expect(steps[2].delayMs).toBeGreaterThan(steps[1].delayMs)
  })

  it('reveals all remaining bubbles in the final capped step', () => {
    const segments = Array.from({ length: 8 }, () => '这是一段长度足够产生明显延迟的回复内容。')
    const steps = buildAssistantRevealSchedule(segments, 500)

    expect(steps.at(-1)).toEqual({ visibleCount: segments.length, delayMs: 500 })
    expect(steps.every((step) => step.delayMs <= 500)).toBe(true)
  })

  it('does not schedule a single bubble', () => {
    expect(buildAssistantRevealSchedule(['完整回复'])).toEqual([])
  })
})
