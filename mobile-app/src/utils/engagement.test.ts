import { describe, expect, it } from 'vitest'
import { formatEngagementTime } from './engagement'

describe('mobile engagement helpers', () => {
  const now = new Date('2026-07-23T12:00:00+08:00')

  it('formats recent interaction time for compact mobile metadata', () => {
    expect(formatEngagementTime('2026-07-23T11:59:30+08:00', now)).toBe('刚刚')
    expect(formatEngagementTime('2026-07-23T11:42:00+08:00', now)).toBe('18 分钟前')
    expect(formatEngagementTime('2026-07-23T08:00:00+08:00', now)).toBe('4 小时前')
  })

  it('falls back to a short calendar date for older comments', () => {
    expect(formatEngagementTime('2026-07-18T08:00:00+08:00', now)).toContain('7月18日')
    expect(formatEngagementTime('invalid', now)).toBe('')
  })
})
