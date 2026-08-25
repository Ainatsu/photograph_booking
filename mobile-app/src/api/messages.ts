import api from './client'
import type {
  ChatTimelineItem,
  MessageContact,
  MessageRecord,
  SendMessagePayload,
} from '@/types/messages'

export async function getMessageContacts(): Promise<MessageContact[]> {
  const { data } = await api.get<MessageContact[]>('/messages/contacts')
  return data
}

export async function getMessageContact(userId: number): Promise<MessageContact> {
  const { data } = await api.get<MessageContact>(`/messages/contact/${userId}`)
  return data
}

export async function getConversation(
  userId: number,
  params: { skip?: number; limit?: number; order_id?: number } = {},
): Promise<ChatTimelineItem[]> {
  const { data } = await api.get<ChatTimelineItem[]>(`/messages/conversation/${userId}`, { params })
  return data
}

export async function sendMessage(payload: SendMessagePayload): Promise<MessageRecord> {
  const { data } = await api.post<MessageRecord>('/messages/', payload)
  return data
}

export async function getMessageUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>('/messages/unread-count')
  return Number(data.count || 0)
}

export async function markMessagesRead(userId: number): Promise<void> {
  await api.put(`/messages/read/${userId}`)
}

export function buildMessageSocketUrl(token: string): string {
  const configuredApiBase = String(import.meta.env.VITE_API_BASE_URL || '').trim()
  let url: URL

  if (/^https?:\/\//i.test(configuredApiBase)) {
    url = new URL(configuredApiBase)
    url.pathname = '/ws'
    url.search = ''
    url.hash = ''
  } else {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    url = new URL(`${protocol}//${window.location.host}/ws`)
  }

  url.protocol = ['https:', 'wss:'].includes(url.protocol) ? 'wss:' : 'ws:'
  url.searchParams.set('token', token)
  return url.toString()
}
