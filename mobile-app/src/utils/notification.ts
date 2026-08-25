import type { RouteLocationRaw } from 'vue-router'
import type { NotificationRecord } from '@/types/notifications'

export type NotificationCategory = 'project' | 'payment' | 'delivery' | 'safety' | 'booking'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function positiveInteger(value: unknown): number | null {
  const number = Number(value || 0)
  return Number.isInteger(number) && number > 0 ? number : null
}

export function isNotificationRecord(value: unknown): value is NotificationRecord {
  if (!isRecord(value)) return false
  return positiveInteger(value.id) !== null
    && typeof value.notification_type === 'string'
    && typeof value.title === 'string'
    && typeof value.content === 'string'
    && typeof value.is_read === 'boolean'
    && typeof value.created_at === 'string'
}

export function getNotificationCategory(type: string): NotificationCategory {
  if (type.startsWith('project_')) return 'project'
  if (type.includes('payment') || type.includes('settlement')) return 'payment'
  if (type.includes('delivery') || type.includes('revision')) return 'delivery'
  if (
    type.includes('dispute')
    || type.includes('cancel')
    || type.includes('expired')
    || type.includes('rejected')
  ) return 'safety'
  return 'booking'
}

export function getNotificationCategoryLabel(type: string): string {
  return ({
    project: '企划',
    payment: '付款',
    delivery: '交付',
    safety: '处理',
    booking: '预约',
  } as Record<NotificationCategory, string>)[getNotificationCategory(type)]
}

export function getNotificationTarget(item: NotificationRecord): RouteLocationRaw | null {
  const orderId = positiveInteger(item.order_id)
  if (orderId) return { name: 'order-detail', params: { orderId } }

  const projectId = positiveInteger(item.project_id)
  if (projectId) return { name: 'project-detail', params: { projectId } }

  const actionUrl = String(item.action_url || '').trim()
  const match = actionUrl.match(/^\/(orders|projects)\/(\d+)(?:[/?#]|$)/)
  if (!match) return null
  const resourceId = positiveInteger(match[2])
  if (!resourceId) return null
  return match[1] === 'orders'
    ? { name: 'order-detail', params: { orderId: resourceId } }
    : { name: 'project-detail', params: { projectId: resourceId } }
}

export function formatNotificationTime(value: string, now = new Date()): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'

  const pad = (number: number) => String(number).padStart(2, '0')
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  const targetDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const currentDate = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const dayDifference = Math.floor((currentDate - targetDate) / 86_400_000)

  if (dayDifference === 0) return `今天 ${time}`
  if (dayDifference === 1) return `昨天 ${time}`
  if (date.getFullYear() === now.getFullYear()) {
    return `${date.getMonth() + 1}月${date.getDate()}日 ${time}`
  }
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 ${time}`
}

export function mergeNotificationRecords(
  ...collections: NotificationRecord[][]
): NotificationRecord[] {
  const records = new Map<number, NotificationRecord>()
  collections.forEach((collection) => {
    collection.forEach((item) => records.set(item.id, item))
  })
  return [...records.values()].sort((left, right) => {
    const timeDifference = new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    return timeDifference || right.id - left.id
  })
}
