import { beforeEach, describe, expect, it, vi } from 'vitest'

const trackRecommendationEvents = vi.hoisted(() => vi.fn())
vi.mock('@/api/recommendations', () => ({ trackRecommendationEvents }))

import { trackClick, trackImpression } from './recommendationEvents'

describe('recommendation event tracking', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends integer entity ids as strings so the batch endpoint accepts them', () => {
    trackClick('project', 11, { position: 0, scene: 'showcase', ownerUserId: 7 })
    expect(trackRecommendationEvents).toHaveBeenCalledWith([{
      event_type: 'project_click',
      target_type: 'shoot_project',
      target_id: '11',
      owner_user_id: 7,
      position: 0,
      scene: 'showcase',
    }])
  })

  it('keeps the web target_type convention for project impressions', () => {
    trackImpression('project', 11, { position: 2, scene: 'showcase' })
    expect(trackRecommendationEvents).toHaveBeenCalledWith([expect.objectContaining({
      event_type: 'project_impression',
      target_type: 'shoot_project',
      target_id: '11',
      position: 2,
    })])
  })

  it('passes through entities that have no target_type alias', () => {
    trackClick('package', 'pkg-1', { scene: 'showcase' })
    expect(trackRecommendationEvents).toHaveBeenCalledWith([expect.objectContaining({
      event_type: 'package_click',
      target_type: 'package',
      target_id: 'pkg-1',
    })])
  })
})
