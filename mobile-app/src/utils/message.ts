import type { ChatTimelineItem, MessageSocketPayload } from '@/types/messages'
import { isNotificationRecord } from '@/utils/notification'

const statusLabels: Record<string, string> = {
  pending: '待确认',
  awaiting_customer_payment: '待支付',
  confirmed: '已确认',
  in_progress: '履约中',
  delivered: '待验收',
  received: '已验收',
  reviewed: '已评价',
  completed: '已完成',
  cancelled: '已取消',
}

const eventLabels: Record<string, string> = {
  created: '订单已创建',
  awaiting_payment: '等待客户支付',
  payment_succeeded: '订单支付成功',
  confirmed: '摄影师确认预约',
  reschedule_requested: '提交改期申请',
  reschedule_accepted: '改期已确认',
  reschedule_rejected: '改期被拒绝',
  reschedule_countered: '提出新的改期时间',
  reschedule_withdrawn: '撤回改期申请',
  in_progress: '订单开始履约',
  delivery_submitted: '摄影师提交交付',
  delivery_resubmitted: '摄影师重新交付',
  revision_requested: '客户申请修改',
  revision_acknowledged: '摄影师确认返修排期',
  delivery_accepted: '客户确认验收',
  delivery_auto_accepted: '系统自动验收',
  review_submitted: '客户提交评价',
  dispute_opened: '发起平台争议',
  dispute_evidence_added: '补充争议证据',
  dispute_assigned: '平台分配管理员',
  dispute_investigating: '平台开始审核',
  dispute_resolved: '平台完成仲裁',
  cancelled: '订单已取消',
}

const statusTones: Record<string, ChatStatusTone> = {
  pending: 'warning',
  awaiting_customer_payment: 'warning',
  delivered: 'warning',
  confirmed: 'brand',
  in_progress: 'brand',
  received: 'brand',
  reviewed: 'brand',
  completed: 'brand',
  cancelled: 'danger',
}

// 订单快照由后端拼接为「方案标题 - ¥价格/时长分钟」，旧订单可能是自由文本。
const packageSnapshotPattern = /^(.*?)\s*-\s*¥\s*([\d,]+(?:\.\d+)?)\s*\/\s*(\d+)\s*分钟$/

export type ChatStatusTone = 'brand' | 'warning' | 'danger' | 'neutral'

export interface ChatPackageSummary {
  title: string
  price: string
  duration: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isTimelineItem(value: unknown, itemType: ChatTimelineItem['item_type']): value is ChatTimelineItem {
  if (!isRecord(value)) return false
  return value.item_type === itemType
    && (typeof value.id === 'number' || typeof value.id === 'string')
    && typeof value.created_at === 'string'
}

export function parseMessageSocketPayload(value: unknown): MessageSocketPayload | null {
  if (!isRecord(value)) return null
  if (value.type === 'pong') return { type: 'pong' }
  if (value.type === 'new_message' && isTimelineItem(value.message, 'message')) {
    return { type: 'new_message', message: value.message }
  }
  if (value.type === 'order_event' && isTimelineItem(value.event, 'order_event')) {
    return { type: 'order_event', event: value.event }
  }
  if (value.type === 'notification' && isNotificationRecord(value.notification)) {
    return { type: 'notification', notification: value.notification }
  }
  return null
}

export function getChatStatusLabel(status?: string | null): string {
  return statusLabels[status || ''] || status || '状态更新'
}

export function getChatEventTitle(eventType?: string | null): string {
  return eventLabels[eventType || ''] || '订单状态更新'
}

export function getChatStatusTone(status?: string | null): ChatStatusTone {
  return statusTones[status || ''] || 'neutral'
}

export function parseChatPackageSnapshot(snapshot?: string | null): ChatPackageSummary | null {
  const text = (snapshot || '').trim()
  if (!text) return null

  const matched = packageSnapshotPattern.exec(text)
  if (!matched) return { title: text, price: '', duration: '' }
  return {
    title: matched[1].trim() || text,
    price: `¥${matched[2]}`,
    duration: `${matched[3]} 分钟`,
  }
}

export function getChatActorLabel(item: ChatTimelineItem): string {
  if (item.actor_name) return item.actor_name
  return ({ customer: '客户', photographer: '摄影师', admin: '平台管理员', system: '系统' } as Record<string, string>)[item.actor_role || ''] || '系统'
}

export function timelineItemBelongsToContact(
  item: ChatTimelineItem,
  currentUserId: number,
  contactUserId: number,
): boolean {
  if (item.item_type === 'message') {
    return (
      Number(item.sender_id) === currentUserId && Number(item.receiver_id) === contactUserId
    ) || (
      Number(item.sender_id) === contactUserId && Number(item.receiver_id) === currentUserId
    )
  }

  return (
    Number(item.customer_id) === currentUserId && Number(item.photographer_id) === contactUserId
  ) || (
    Number(item.photographer_id) === currentUserId && Number(item.customer_id) === contactUserId
  )
}

export function formatChatTime(value: string, now = new Date()): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const pad = (number: number) => String(number).padStart(2, '0')
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  const sameDate = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()
  if (sameDate) return time

  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const dayDifference = Math.floor((start - target) / 86_400_000)
  if (dayDifference === 1) return `昨天 ${time}`
  if (dayDifference > 1 && dayDifference < 7) {
    return `${['周日', '周一', '周二', '周三', '周四', '周五', '周六'][date.getDay()]} ${time}`
  }
  if (date.getFullYear() === now.getFullYear()) return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${time}`
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${time}`
}

export function shouldShowChatTimeDivider(items: ChatTimelineItem[], index: number): boolean {
  const current = new Date(items[index]?.created_at || '').getTime()
  if (Number.isNaN(current)) return false
  if (index === 0) return true
  const previous = new Date(items[index - 1]?.created_at || '').getTime()
  return Number.isNaN(previous) || current - previous >= 5 * 60 * 1000
}
