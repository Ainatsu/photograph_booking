import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('./client', () => ({ default: api }))

import { getRecommendedPackages } from './recommendations'

describe('joint package recommendation API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('serializes structured filters without losing the response contract', async () => {
    const response = { recommendation_id: 'rec-1', algorithm_version: 'package_rec_v2_joint_availability', fallback_level: 0, relaxations: [], no_result: true, feature_enabled: true, observability: {}, items: [] }
    api.get.mockResolvedValue({ data: response })
    await expect(getRecommendedPackages({ city: '成都', styles: ['日系', '人像'], shoot_date: '2026-08-08', time_start: '14:00', time_end: '18:00', require_exact_availability: true })).resolves.toBe(response)
    expect(api.get).toHaveBeenCalledWith('/recommendations/packages', { params: expect.objectContaining({ city: '成都', styles: '日系,人像', shoot_date: '2026-08-08', require_exact_availability: true }) })
  })
})
