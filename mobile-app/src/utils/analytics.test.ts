import { describe, it, expect, vi, beforeEach } from 'vitest'
import { trackEvent, trackPageView, trackSearch } from './analytics'

describe('analytics', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  
  it('should queue events without throwing', () => {
    expect(() => {
      trackEvent('test_event', { foo: 'bar' })
      trackPageView('TestPage')
      trackSearch('query', 5)
    }).not.toThrow()
  })
})
