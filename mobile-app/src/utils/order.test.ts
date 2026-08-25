import { describe, expect, it } from 'vitest'
import {
  canAcceptOrderDelivery,
  canStartOrderService,
  getOrderProgressIndex,
  getOrderCounterparty,
  getOrderNextStep,
  getOrderStatusLabel,
  hasAvailableOrderRevision,
  isActiveOrder,
  isCompletedOrder,
  isOrderScheduleManageable,
} from './order'
import type { OrderItem } from '@/types/orders'

const order: OrderItem = {
  id: 10,
  customer_id: 1,
  photographer_id: 2,
  customer_name: '客户甲',
  photographer_name: '摄影师乙',
  package_snapshot: '城市写真',
  appointment_time: '2026-08-01T10:00:00Z',
  duration_minutes: 120,
  status: 'pending',
  created_at: '2026-07-23T10:00:00Z',
}

describe('mobile order presentation helpers', () => {
  it('maps order statuses and counterparties', () => {
    expect(getOrderStatusLabel('pending')).toBe('待摄影师确认')
    expect(getOrderCounterparty(order, 'customer')).toBe('摄影师乙')
    expect(getOrderCounterparty(order, 'photographer')).toBe('客户甲')
  })

  it('classifies active and completed orders', () => {
    expect(isActiveOrder(order)).toBe(true)
    expect(isCompletedOrder({ ...order, status: 'completed' })).toBe(true)
  })

  it('returns role-aware next steps', () => {
    expect(getOrderNextStep(order, 'customer')).toContain('等待摄影师')
    expect(getOrderNextStep(order, 'photographer')).toContain('确认或拒绝')
    expect(getOrderNextStep({ ...order, status: 'received' }, 'customer')).toContain('提交评价')
    expect(getOrderNextStep({
      ...order,
      status: 'delivered',
      after_sales_status: 'revision_requested',
    }, 'photographer')).toContain('重新交付')
    expect(getOrderNextStep({
      ...order,
      status: 'in_progress',
      after_sales_status: 'dispute_open',
    }, 'customer')).toContain('争议')
  })

  it('maps order progress and schedule-management states', () => {
    expect(getOrderProgressIndex('delivered')).toBe(4)
    expect(getOrderProgressIndex('completed')).toBe(5)
    expect(getOrderProgressIndex('cancelled')).toBe(-1)
    expect(isOrderScheduleManageable(order)).toBe(true)
    expect(isOrderScheduleManageable({ ...order, status: 'in_progress' })).toBe(false)
  })

  it('enforces payment, acceptance, and free-revision gates', () => {
    expect(canStartOrderService({ ...order, status: 'confirmed', final_price: 800, payment_status: 'deposit_paid' })).toBe(false)
    expect(canStartOrderService({ ...order, status: 'confirmed', final_price: 800, payment_status: 'paid_in_escrow' })).toBe(true)
    expect(canStartOrderService({ ...order, status: 'confirmed', final_price: 800, payment_status: 'paid_in_escrow', after_sales_status: 'dispute_open' })).toBe(false)
    expect(canAcceptOrderDelivery({ ...order, status: 'delivered', after_sales_status: 'revision_requested' })).toBe(false)
    expect(canAcceptOrderDelivery({ ...order, status: 'delivered', after_sales_status: 'none' })).toBe(true)
    expect(hasAvailableOrderRevision({ ...order, included_revision_count: 2, revision_used_count: 1 })).toBe(true)
    expect(hasAvailableOrderRevision({ ...order, included_revision_count: 2, revision_used_count: 2 })).toBe(false)
  })
})
