import { describe, expect, it } from 'vitest'
import { findChinaRegion, findCountryCode, formatRegionValue } from '../regionOptions'

describe('regionOptions', () => {
  it('识别旧城市值并补全中国大陆省市', () => {
    expect(findCountryCode('深圳')).toBe('CN')
    expect(findChinaRegion('深圳')).toEqual(['广东省', '深圳市'])
    expect(findChinaRegion('上海市浦东新区')).toEqual(['上海市', '上海市'])
  })

  it('格式化国内和海外地区', () => {
    expect(formatRegionValue('CN', ['广东省', '深圳市'])).toBe('中国大陆 · 广东省 · 深圳市')
    expect(formatRegionValue('JP')).toBe('日本')
  })

  it('将港澳台作为单独国家或地区选项识别', () => {
    expect(findCountryCode('香港')).toBe('HK')
    expect(formatRegionValue('HK')).toBe('中国香港')
  })
})
