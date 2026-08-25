import { describe, expect, it } from 'vitest'
import { getOrderStatusTone, parseOrderPackageSnapshot } from '../orderEventCard'

describe('order event card helpers', () => {
  it('groups order statuses into tones so colour is never the only signal', () => {
    expect(getOrderStatusTone('confirmed')).toBe('brand')
    expect(getOrderStatusTone('reschedule_requested')).toBe('warning')
    expect(getOrderStatusTone('cancelled')).toBe('danger')
    expect(getOrderStatusTone('unknown_status')).toBe('neutral')
    expect(getOrderStatusTone(undefined)).toBe('neutral')
  })

  it('splits the order package snapshot into readable facts', () => {
    expect(parseOrderPackageSnapshot('个人写真 - ¥699/120分钟')).toEqual({
      title: '个人写真',
      price: '¥699',
      duration: '120 分钟'
    })
    expect(parseOrderPackageSnapshot('婚纱跟拍 - ¥12,800.50/480分钟')).toEqual({
      title: '婚纱跟拍',
      price: '¥12,800.50',
      duration: '480 分钟'
    })
    expect(parseOrderPackageSnapshot('线下沟通后定制的旅拍需求')).toEqual({
      title: '线下沟通后定制的旅拍需求',
      price: '',
      duration: ''
    })
    expect(parseOrderPackageSnapshot('   ')).toBeNull()
    expect(parseOrderPackageSnapshot(null)).toBeNull()
  })
})
