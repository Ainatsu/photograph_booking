import { describe, expect, it } from 'vitest'
import {
  MAX_APPLICATION_PORTFOLIO_ITEMS,
  hydratePhotographerApplicationFields,
  photographerApplicationStatusLabel,
  photographerApplicationSummary,
  portfolioReferencePreview,
  validatePhotographerApplication,
} from './photographerApplication'

describe('photographer application helpers', () => {
  it('validates required fields, backend limits and representative works', () => {
    expect(validatePhotographerApplication({
      profileIntro: '',
      location: '',
      equipment: '',
      styles: [],
    }, 0)).toEqual({
      profileIntro: expect.stringContaining('介绍'),
      location: expect.stringContaining('地区'),
      equipment: expect.stringContaining('设备'),
      styles: expect.stringContaining('风格'),
      portfolio: expect.stringContaining('作品'),
    })

    expect(validatePhotographerApplication({
      profileIntro: '记录真实自然的情绪',
      location: '中国大陆 · 四川省 · 成都市',
      equipment: 'Sony A7 IV + 35mm F1.4',
      styles: ['人像', '纪实'],
    }, 2)).toEqual({ profileIntro: '', location: '', equipment: '', styles: '', portfolio: '' })

    expect(validatePhotographerApplication({
      profileIntro: '介绍',
      location: '成都',
      equipment: '相机',
      styles: ['人像'],
    }, MAX_APPLICATION_PORTFOLIO_ITEMS + 1).portfolio).toContain(String(MAX_APPLICATION_PORTFOLIO_ITEMS))
  })

  it('hydrates resubmission fields without sharing the API style array', () => {
    const application = {
      id: 1,
      user_id: 2,
      status: 'rejected',
      profile_intro: '旧介绍',
      location: '杭州',
      equipment: 'Canon R5',
      styles: ['婚礼'],
      portfolio_refs: [],
    }
    const fields = hydratePhotographerApplicationFields(application)
    fields.styles.push('纪实')

    expect(fields).toMatchObject({ profileIntro: '旧介绍', location: '杭州', equipment: 'Canon R5' })
    expect(application.styles).toEqual(['婚礼'])
  })

  it('maps status copy and safely chooses a work preview', () => {
    expect(photographerApplicationStatusLabel()).toBe('未提交')
    expect(photographerApplicationStatusLabel('pending')).toBe('审核中')
    expect(photographerApplicationSummary('rejected')).toContain('重新提交')
    expect(photographerApplicationSummary(null, true)).toContain('已通过')
    expect(portfolioReferencePreview({
      url: '/original.jpg',
      images: ['/image.jpg'],
      thumbnail_urls: ['/thumb.jpg'],
    })).toBe('/thumb.jpg')
  })
})
