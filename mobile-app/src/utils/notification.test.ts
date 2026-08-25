import { describe, expect, it } from 'vitest'
import type { NotificationRecord } from '@/types/notifications'
import {
  formatNotificationTime,
  getNotificationCategory,
  getNotificationTarget,
  isNotificationRecord,
  mergeNotificationRecords,
} from './notification'

const notification: NotificationRecord = {
  id: 8,
  order_id: 21,
  notification_type: 'delivery_submitted',
  title: '摄影师已提交交付',
  content: '订单 #21 已有新文件',
  action_url: '/orders/21',
  is_read: false,
  created_at: '2026-07-23T10:00:00',
}

describe('mobile notification helpers', () => {
  it('validates realtime records and assigns presentation categories', () => {
    expect(isNotificationRecord(notification)).toBe(true)
    expect(isNotificationRecord({ ...notification, title: null })).toBe(false)
    expect(getNotificationCategory('project_application_selected')).toBe('project')
    expect(getNotificationCategory('payment_succeeded')).toBe('payment')
    expect(getNotificationCategory('delivery_resubmitted')).toBe('delivery')
    expect(getNotificationCategory('dispute_opened')).toBe('safety')
  })

  it('builds safe in-app detail destinations', () => {
    expect(getNotificationTarget(notification)).toEqual({
      name: 'order-detail',
      params: { orderId: 21 },
    })
    expect(getNotificationTarget({
      ...notification,
      order_id: null,
      project_id: 13,
      action_url: '/projects/13',
    })).toEqual({
      name: 'project-detail',
      params: { projectId: 13 },
    })
    expect(getNotificationTarget({ ...notification, order_id: null, action_url: 'https://example.com' })).toBeNull()
  })

  it('formats readable times and merges duplicate realtime records', () => {
    const now = new Date('2026-07-23T12:00:00')
    expect(formatNotificationTime(notification.created_at, now)).toBe('今天 10:00')
    const merged = mergeNotificationRecords(
      [notification],
      [{ ...notification, is_read: true }, { ...notification, id: 9, created_at: '2026-07-23T11:00:00' }],
    )
    expect(merged.map((item) => item.id)).toEqual([9, 8])
    expect(merged[1].is_read).toBe(true)
  })
})
