import { describe, expect, it } from 'vitest'
import type { ChatTimelineItem } from '@/types/messages'
import type { NotificationRecord } from '@/types/notifications'
import {
  formatChatTime,
  getChatEventTitle,
  getChatStatusLabel,
  getChatStatusTone,
  parseChatPackageSnapshot,
  parseMessageSocketPayload,
  shouldShowChatTimeDivider,
  timelineItemBelongsToContact,
} from './message'

const message: ChatTimelineItem = {
  item_type: 'message',
  id: 1,
  sender_id: 10,
  receiver_id: 20,
  content: '你好',
  created_at: '2026-07-23T10:00:00',
}

const notification: NotificationRecord = {
  id: 7,
  project_id: 11,
  notification_type: 'project_application_selected',
  title: '你的应邀方案已被选定',
  content: '企划 #11 已生成订单',
  action_url: '/projects/11',
  is_read: false,
  created_at: '2026-07-23T10:00:00',
}

describe('mobile message helpers', () => {
  it('maps order event and status labels', () => {
    expect(getChatEventTitle('dispute_opened')).toBe('发起平台争议')
    expect(getChatStatusLabel('delivered')).toBe('待验收')
  })

  it('matches messages and order events to a contact', () => {
    expect(timelineItemBelongsToContact(message, 10, 20)).toBe(true)
    expect(timelineItemBelongsToContact(message, 10, 30)).toBe(false)
    expect(timelineItemBelongsToContact({
      item_type: 'order_event',
      id: 'event-1',
      customer_id: 10,
      photographer_id: 20,
      created_at: '2026-07-23T10:00:00',
    }, 10, 20)).toBe(true)
  })

  it('accepts known socket payloads and rejects malformed events', () => {
    expect(parseMessageSocketPayload({ type: 'new_message', message })).toEqual({
      type: 'new_message',
      message,
    })
    expect(parseMessageSocketPayload({ type: 'notification', notification })).toEqual({
      type: 'notification',
      notification,
    })
    expect(parseMessageSocketPayload({ type: 'new_message', message: {} })).toBeNull()
    expect(parseMessageSocketPayload({ type: 'notification', notification: {} })).toBeNull()
    expect(parseMessageSocketPayload({ type: 'unknown' })).toBeNull()
  })

  it('groups order statuses into tones so colour is never the only signal', () => {
    expect(getChatStatusTone('confirmed')).toBe('brand')
    expect(getChatStatusTone('awaiting_customer_payment')).toBe('warning')
    expect(getChatStatusTone('cancelled')).toBe('danger')
    expect(getChatStatusTone('unknown_status')).toBe('neutral')
    expect(getChatStatusTone(null)).toBe('neutral')
  })

  it('splits the order package snapshot into readable facts', () => {
    expect(parseChatPackageSnapshot('个人写真 - ¥699/120分钟')).toEqual({
      title: '个人写真',
      price: '¥699',
      duration: '120 分钟',
    })
    expect(parseChatPackageSnapshot('婚纱跟拍 - ¥12,800.50/480分钟')).toEqual({
      title: '婚纱跟拍',
      price: '¥12,800.50',
      duration: '480 分钟',
    })
    expect(parseChatPackageSnapshot('线下沟通后定制的旅拍需求')).toEqual({
      title: '线下沟通后定制的旅拍需求',
      price: '',
      duration: '',
    })
    expect(parseChatPackageSnapshot('   ')).toBeNull()
    expect(parseChatPackageSnapshot(null)).toBeNull()
  })

  it('formats timeline times and five-minute dividers', () => {
    const now = new Date('2026-07-23T12:00:00')
    expect(formatChatTime('2026-07-23T10:00:00', now)).toBe('10:00')
    expect(formatChatTime('2026-07-22T10:00:00', now)).toBe('昨天 10:00')
    expect(shouldShowChatTimeDivider([
      message,
      { ...message, id: 2, created_at: '2026-07-23T10:04:00' },
      { ...message, id: 3, created_at: '2026-07-23T10:10:00' },
    ], 1)).toBe(false)
    expect(shouldShowChatTimeDivider([
      message,
      { ...message, id: 2, created_at: '2026-07-23T10:10:00' },
    ], 1)).toBe(true)
  })
})
