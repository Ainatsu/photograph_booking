import { describe, expect, it } from 'vitest'
import type { PhotographerProfile } from '@/types/discovery'
import { formatResidencyLabel, getProfilePackages, getProfileWorks } from './photographerProfile'

const profile: PhotographerProfile = {
  id: 7,
  user_id: 42,
  user_display_name: '林一',
  user_avatar_url: '/media/avatar.jpg',
  location: '上海',
  portfolio: [
    { id: 'work-1', title: '海边写真' },
    { id: '', title: '缺少编号的旧作品' },
  ],
  packages: [
    { id: 'pkg-1', name: '人像基础', price: 699, is_active: true },
    { id: 'pkg-2', name: '已下架方案', price: 899, is_active: false },
    { id: '', name: '旧方案', price: 499 },
  ],
}

describe('photographer profile content helpers', () => {
  it('fills in author info and falls back to an index id for legacy works', () => {
    const works = getProfileWorks(profile)

    expect(works.map((work) => work.id)).toEqual(['work-1', 'portfolio-1'])
    expect(works[0]).toMatchObject({
      user_id: 42,
      user_display_name: '林一',
      user_avatar_url: '/media/avatar.jpg',
    })
  })

  it('keeps only active packages and fills in photographer info', () => {
    const packages = getProfilePackages(profile)

    expect(packages.map((offer) => offer.id)).toEqual(['pkg-1', 'package-1'])
    expect(packages[0]).toMatchObject({
      photographer_id: 42,
      photographer_name: '林一',
      photographer_avatar: '/media/avatar.jpg',
      photographer_location: '上海',
    })
  })

  it('returns empty lists when the profile or its content is missing', () => {
    expect(getProfileWorks(null)).toEqual([])
    expect(getProfilePackages(undefined)).toEqual([])
    expect(getProfileWorks({ ...profile, portfolio: null })).toEqual([])
    expect(getProfilePackages({ ...profile, packages: null })).toEqual([])
  })
})

describe('formatResidencyLabel', () => {
  it('keeps only the most detailed level of a hierarchical location', () => {
    expect(formatResidencyLabel('中国-四川-成都')).toBe('成都')
    expect(formatResidencyLabel('中国 / 广东省 / 深圳市 / 南山区')).toBe('南山区')
    expect(formatResidencyLabel('中国、香港、中环')).toBe('中环')
    expect(formatResidencyLabel('中国 四川 成都')).toBe('成都')
  })

  it('keeps single-level values untouched', () => {
    expect(formatResidencyLabel('香港中环')).toBe('香港中环')
    expect(formatResidencyLabel('  上海市  ')).toBe('上海市')
    expect(formatResidencyLabel('Los Angeles')).toBe('Los Angeles')
  })

  it('returns an empty string when nothing is set', () => {
    expect(formatResidencyLabel('')).toBe('')
    expect(formatResidencyLabel(null)).toBe('')
    expect(formatResidencyLabel(undefined)).toBe('')
    expect(formatResidencyLabel(' -- ')).toBe('')
  })
})
