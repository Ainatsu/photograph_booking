import { describe, expect, it } from 'vitest'
import { favoritePackageToOffer, favoriteWorkToWork, likedWorkToWork } from './social'

describe('mobile social snapshot helpers', () => {
  it('hydrates a favorite work with current photographer metadata', () => {
    expect(favoriteWorkToWork({
      work_id: 'work-1',
      photographer_id: 8,
      photographer_name: '林摄影',
      photographer_avatar: '/avatar.jpg',
      work_data: { title: '海边人像', url: '/work.jpg' },
    })).toMatchObject({
      id: 'work-1',
      photographer_id: 8,
      user_id: 8,
      user_display_name: '林摄影',
      user_avatar_url: '/avatar.jpg',
      title: '海边人像',
    })
  })

  it('hydrates a favorite package and supplies a safe numeric price', () => {
    expect(favoritePackageToOffer({
      package_id: 'package-1',
      photographer_id: 9,
      photographer_name: '周摄影',
      package_data: { package_name: '城市写真' },
    })).toMatchObject({
      id: 'package-1',
      price: 0,
      photographer_id: 9,
      photographer_name: '周摄影',
      package_name: '城市写真',
    })
  })

  it('hydrates a liked work with the same stable snapshot rules', () => {
    expect(likedWorkToWork({
      work_id: 'liked-work-1',
      photographer_id: 12,
      photographer_name: '何摄影',
      work_data: { title: '夜景人像' },
    })).toMatchObject({
      id: 'liked-work-1',
      photographer_id: 12,
      user_id: 12,
      user_display_name: '何摄影',
      title: '夜景人像',
    })
  })
})
