import type { OrderItem } from '@/types/orders'

export const orderStatusLabels: Record<string, string> = {
  pending: '待摄影师确认',
  awaiting_customer_payment: '待支付',
  confirmed: '已确认',
  in_progress: '履约中',
  delivered: '待验收',
  received: '已验收',
  reviewed: '已评价',
  completed: '已完成',
  cancelled: '已取消',
}

export function getOrderStatusLabel(status: string): string {
  return orderStatusLabels[status] || status || '状态未知'
}

export function getOrderTitle(order: OrderItem): string {
  return order.package_name || order.package_snapshot || `订单 #${order.id}`
}

export function getOrderCounterparty(order: OrderItem, role: 'customer' | 'photographer'): string {
  return role === 'customer'
    ? order.photographer_name || `摄影师 #${order.photographer_id}`
    : order.customer_name || `客户 #${order.customer_id}`
}

export function formatOrderDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间待确认'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function isActiveOrder(order: OrderItem): boolean {
  return ['pending', 'awaiting_customer_payment', 'confirmed', 'in_progress', 'delivered'].includes(order.status)
}

export function isCompletedOrder(order: OrderItem): boolean {
  return ['received', 'reviewed', 'completed'].includes(order.status)
}

export function getOrderProgressIndex(status: string): number {
  return ({
    pending: 0,
    awaiting_customer_payment: 1,
    confirmed: 2,
    in_progress: 3,
    delivered: 4,
    received: 5,
    reviewed: 5,
    completed: 5,
  } as Record<string, number>)[status] ?? -1
}

export function isOrderScheduleManageable(order: OrderItem): boolean {
  return ['pending', 'awaiting_customer_payment', 'confirmed'].includes(order.status)
}

export function canStartOrderService(order: OrderItem): boolean {
  return order.status === 'confirmed'
    && order.after_sales_status !== 'dispute_open'
    && (order.final_price == null || order.payment_status === 'paid_in_escrow')
}

export function canAcceptOrderDelivery(order: OrderItem): boolean {
  return order.status === 'delivered' && (order.after_sales_status || 'none') === 'none'
}

export function hasAvailableOrderRevision(order: OrderItem): boolean {
  return Number(order.revision_used_count || 0) < Number(order.included_revision_count || 0)
}

export function getOrderNextStep(order: OrderItem, role: 'customer' | 'photographer'): string {
  if (order.after_sales_status === 'dispute_open') return '平台正在处理争议，履约、验收和资金结算暂时冻结。'
  if (order.active_reschedule_request) return '订单有待处理的改期申请，请进入详情查看。'

  if (role === 'photographer') {
    if (order.status === 'confirmed' && order.payment_status === 'deposit_paid') {
      return '等待客户支付尾款，暂时不能开始服务'
    }
    if (order.status === 'delivered' && order.after_sales_status === 'revision_requested') {
      return '客户已申请修改，请进入详情确认排期并重新交付'
    }
    return {
      pending: '请确认或拒绝这笔预约',
      awaiting_customer_payment: '等待客户完成支付',
      confirmed: '到达约定时间后开始服务',
      in_progress: '拍摄完成后上传交付作品',
      delivered: '等待客户验收',
      completed: '订单已完成',
      cancelled: order.rejection_reason || order.cancellation_reason || '订单已取消',
    }[order.status] || '查看订单最新状态'
  }

  if (order.status === 'confirmed' && order.payment_status === 'deposit_paid') {
    return '请完成尾款支付，支付后摄影师才能开始服务'
  }
  if (order.status === 'delivered' && order.after_sales_status === 'revision_requested') {
    return '修改申请已提交，等待摄影师重新交付'
  }
  return {
    pending: '等待摄影师确认预约',
    awaiting_customer_payment: '请完成演示支付以锁定档期',
    confirmed: '档期已锁定，请按约定时间到场',
    in_progress: '摄影师正在履约和准备交付',
    delivered: '请检查交付内容并确认验收',
    received: '订单已验收，可以在详情中提交评价',
    reviewed: '订单已完成并评价',
    completed: '订单已完成',
    cancelled: order.rejection_reason || order.cancellation_reason || '订单已取消',
  }[order.status] || '查看订单最新状态'
}
