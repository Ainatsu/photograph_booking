import type { NotificationRecord } from '@/types/notifications'

export interface MessageContact {
  id: number
  display_name: string
  role: string
  avatar_url?: string | null
  unread_count: number
  last_message?: {
    type: 'message' | 'order_event'
    content?: string | null
    event_type?: string | null
    created_at: string
  } | null
}

export interface MessageReference {
  type: 'package' | 'work' | 'item'
  title: string
  url?: string | null
  cover_url?: string | null
}

export interface MessageRecord {
  id: number
  sender_id: number
  receiver_id: number
  content: string
  order_id?: number | null
  reference?: MessageReference | null
  is_read: boolean
  created_at: string
}

export interface ChatTimelineItem {
  item_type: 'message' | 'order_event'
  id: number | string
  message_id?: number | null
  order_event_id?: number | null
  sender_id?: number | null
  receiver_id?: number | null
  content?: string | null
  order_id?: number | null
  reference?: MessageReference | null
  is_read?: boolean | null
  event_type?: string | null
  status?: string | null
  actor_id?: number | null
  actor_role?: string | null
  actor_name?: string | null
  note?: string | null
  customer_id?: number | null
  photographer_id?: number | null
  package_snapshot?: string | null
  created_at: string
}

export interface SendMessagePayload {
  receiver_id: number
  content: string
  order_id?: number
  reference?: MessageReference
}

export type MessageSocketPayload =
  | { type: 'new_message'; message: ChatTimelineItem }
  | { type: 'order_event'; event: ChatTimelineItem }
  | { type: 'notification'; notification: NotificationRecord }
  | { type: 'pong' }
