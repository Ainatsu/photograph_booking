/**
 * api-modules.spec.js — API 接口模块单元测试
 * 测试：photographer.js, order.js, message.js 接口调用
 */
import { describe, it, expect, vi, beforeAll } from 'vitest'

// Mock API
vi.mock('../../utils/api', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import api from '../../utils/api'

describe('API Modules - Photographer', () => {
  let photographerAPI
  beforeAll(async () => {
    photographerAPI = await import('../../api/photographer')
  })

  it('getPhotographerList calls GET with params', () => {
    photographerAPI.getPhotographerList({ skip: 0, limit: 10 })
    expect(api.get).toHaveBeenCalledWith('/photographers/profiles', { params: { skip: 0, limit: 10 } })
  })

  it('getPhotographerDetail calls GET with userId', () => {
    photographerAPI.getPhotographerDetail(5)
    expect(api.get).toHaveBeenCalledWith('/photographers/profile/5', { skipErrorHandler: true })
  })

  it('getAllWorks calls GET with params', () => {
    photographerAPI.getAllWorks({ skip: 10, limit: 20 })
    expect(api.get).toHaveBeenCalledWith('/photographers/works', { params: { skip: 10, limit: 20 } })
  })

  it('getAllPackages calls GET', () => {
    photographerAPI.getAllPackages()
    expect(api.get).toHaveBeenCalledWith('/photographers/packages')
  })

  it('getPhotographerAvailableSlots calls GET with booking params', () => {
    const params = { start_date: '2026-07-20', days: 14, duration_minutes: 120 }
    photographerAPI.getPhotographerAvailableSlots(5, params)
    expect(api.get).toHaveBeenCalledWith('/photographers/5/available-slots', { params })
  })
})

describe('API Modules - Order', () => {
  let orderAPI
  beforeAll(async () => {
    orderAPI = await import('../../api/order')
  })

  it('createOrder calls POST', () => {
    const data = { package_id: 'package-1', photographer_id: 1, appointment_date: '2026-07-02', notes: 'test' }
    orderAPI.createOrder(data)
    expect(api.post).toHaveBeenCalledWith('/orders/', data)
  })

  it('getMyCustomerOrders calls GET with params', () => {
    orderAPI.getMyCustomerOrders({ status: 'pending' })
    expect(api.get).toHaveBeenCalledWith('/orders/my-customer', { params: { status: 'pending' } })
  })

  it('getMyPhotographerOrders calls GET', () => {
    orderAPI.getMyPhotographerOrders()
    expect(api.get).toHaveBeenCalledWith('/orders/my-photographer', { params: {} })
  })

  it('confirmOrder calls PUT', () => {
    orderAPI.confirmOrder(42)
    expect(api.put).toHaveBeenCalledWith('/orders/42/confirm')
  })

  it('startOrder calls PUT', () => {
    orderAPI.startOrder(42)
    expect(api.put).toHaveBeenCalledWith('/orders/42/start')
  })

  it('getOrderDetail calls GET', () => {
    orderAPI.getOrderDetail(42)
    expect(api.get).toHaveBeenCalledWith('/orders/42/detail')
  })

  it('createOrderPayment calls POST with idempotency key', () => {
    orderAPI.createOrderPayment(42, 'payment-key-42')
    expect(api.post).toHaveBeenCalledWith('/payments/orders/42', { idempotency_key: 'payment-key-42' })
  })

  it('confirmMockPayment calls POST', () => {
    orderAPI.confirmMockPayment(9, 'provider-9')
    expect(api.post).toHaveBeenCalledWith('/payments/9/mock-confirm', { provider_transaction_id: 'provider-9' })
  })

  it('rejectOrder calls PUT', () => {
    orderAPI.rejectOrder(42, '档期已满')
    expect(api.put).toHaveBeenCalledWith('/orders/42/reject', { rejection_reason: '档期已满' })
  })

  it('requestReschedule calls PUT', () => {
    const data = { appointment_date: '2026-07-02', reason: '临时有事' }
    orderAPI.requestReschedule(42, data)
    expect(api.put).toHaveBeenCalledWith('/orders/42/reschedule/request', data)
  })

  it('confirmReschedule calls PUT', () => {
    orderAPI.confirmReschedule(42)
    expect(api.put).toHaveBeenCalledWith('/orders/42/reschedule/confirm')
  })

  it('cancelOrder calls PUT', () => {
    orderAPI.cancelOrder(42, '行程变化')
    expect(api.put).toHaveBeenCalledWith('/orders/42/cancel', { cancel_reason: '行程变化' })
  })

  it('acceptOrder calls PUT', () => {
    orderAPI.acceptOrder(42)
    expect(api.put).toHaveBeenCalledWith('/orders/42/accept')
  })

  it('requestDeliveryRevision posts multipart form data', () => {
    const formData = new FormData()
    formData.append('instructions', '调整色温')
    orderAPI.requestDeliveryRevision(42, formData)
    expect(api.post).toHaveBeenCalledWith('/orders/42/revision', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  })

  it('acknowledgeDeliveryRevision calls PUT with expected time', () => {
    orderAPI.acknowledgeDeliveryRevision(42, 7, '2026-07-20T12:00:00')
    expect(api.put).toHaveBeenCalledWith('/orders/42/revision/7/acknowledge', {
      expected_redelivery_at: '2026-07-20T12:00:00',
    })
  })

  it('reviewOrder calls PUT', () => {
    const review = { rating: 8, review_text: '不错' }
    orderAPI.reviewOrder(42, review)
    expect(api.put).toHaveBeenCalledWith('/orders/42/review', review)
  })

  it('getPhotographerStats calls GET', () => {
    orderAPI.getPhotographerStats()
    expect(api.get).toHaveBeenCalledWith('/orders/stats')
  })

  it('getPhotographerDashboard calls GET', () => {
    orderAPI.getPhotographerDashboard()
    expect(api.get).toHaveBeenCalledWith('/orders/dashboard', { params: {} })
  })

  it('getPhotographerDashboard calls GET with params', () => {
    orderAPI.getPhotographerDashboard({ range: '7d' })
    expect(api.get).toHaveBeenCalledWith('/orders/dashboard', { params: { range: '7d' } })
  })

  it('getPublicPhotographerDashboard calls GET', () => {
    orderAPI.getPublicPhotographerDashboard(5)
    expect(api.get).toHaveBeenCalledWith('/orders/dashboard/public/5')
  })
})

describe('API Modules - Analytics', () => {
  let analyticsAPI
  beforeAll(async () => {
    analyticsAPI = await import('../../api/analytics')
  })

  it('trackAnalyticsEvent calls POST without global error handling', () => {
    const payload = {
      user_id: 2,
      event_type: 'profile_view',
      target_type: 'photographer',
      target_id: '2',
    }
    analyticsAPI.trackAnalyticsEvent(payload)
    expect(api.post).toHaveBeenCalledWith('/analytics/events', payload, { skipErrorHandler: true })
  })
})

describe('API Modules - Message', () => {
  let messageAPI
  beforeAll(async () => {
    messageAPI = await import('../../api/message')
  })

  it('getContacts calls GET', () => {
    messageAPI.getContacts()
    expect(api.get).toHaveBeenCalledWith('/messages/contacts')
  })

  it('getContact calls GET with userId', () => {
    messageAPI.getContact(3)
    expect(api.get).toHaveBeenCalledWith('/messages/contact/3')
  })

  it('getConversation calls GET with userId and params', () => {
    messageAPI.getConversation(3, { skip: 0, limit: 50 })
    expect(api.get).toHaveBeenCalledWith('/messages/conversation/3', { params: { skip: 0, limit: 50 } })
  })

  it('sendMessage calls POST', () => {
    const data = { sender_id: 1, content: 'Hello' }
    messageAPI.sendMessage(data)
    expect(api.post).toHaveBeenCalledWith('/messages/', data)
  })

  it('getUnreadCount calls GET', () => {
    messageAPI.getUnreadCount()
    expect(api.get).toHaveBeenCalledWith('/messages/unread-count')
  })

  it('markRead calls PUT', () => {
    messageAPI.markRead(5)
    expect(api.put).toHaveBeenCalledWith('/messages/read/5')
  })
})

describe('API Modules - Notification', () => {
  let notificationAPI
  beforeAll(async () => {
    notificationAPI = await import('../../api/notification')
  })

  it('getNotifications calls GET with filters', () => {
    notificationAPI.getNotifications({ unread_only: true })
    expect(api.get).toHaveBeenCalledWith('/notifications/', { params: { unread_only: true } })
  })

  it('getNotificationUnreadCount calls GET', () => {
    notificationAPI.getNotificationUnreadCount()
    expect(api.get).toHaveBeenCalledWith('/notifications/unread-count')
  })

  it('markNotificationRead calls PUT', () => {
    notificationAPI.markNotificationRead(9)
    expect(api.put).toHaveBeenCalledWith('/notifications/9/read')
  })

  it('markAllNotificationsRead calls PUT', () => {
    notificationAPI.markAllNotificationsRead()
    expect(api.put).toHaveBeenCalledWith('/notifications/read-all')
  })
})

describe('API Modules - AI Assistant', () => {
  let aiAPI
  beforeAll(async () => {
    aiAPI = await import('../../api/ai')
  })

  it('createAIConversation calls POST', () => {
    aiAPI.createAIConversation({ title: 'AI 咨询' })
    expect(api.post).toHaveBeenCalledWith('/ai/conversations', { title: 'AI 咨询' })
  })

  it('getAIConversations calls GET with params', () => {
    aiAPI.getAIConversations({ skip: 0, limit: 20 })
    expect(api.get).toHaveBeenCalledWith('/ai/conversations', { params: { skip: 0, limit: 20 } })
  })

  it('getAIMessages calls GET with conversationId and params', () => {
    aiAPI.getAIMessages(7, { limit: 50 })
    expect(api.get).toHaveBeenCalledWith('/ai/conversations/7/messages', { params: { limit: 50 } })
  })

  it('sendAIMessage calls POST with extended timeout', () => {
    const data = { content: 'Hello AI' }
    aiAPI.sendAIMessage(7, data)
    expect(api.post).toHaveBeenCalledWith('/ai/conversations/7/messages', data, { timeout: 70000 })
  })
})
