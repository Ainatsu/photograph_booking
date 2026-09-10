import api from './client'
import type {
  NotificationListParams,
  NotificationMutationResult,
  NotificationRecord,
} from '@/types/notifications'

export async function getNotifications(
  params: NotificationListParams = {},
): Promise<NotificationRecord[]> {
  const { data } = await api.get<NotificationRecord[]>('/notifications/', { params })
  return data
}

export async function getNotificationUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>('/notifications/unread-count')
  return Number(data.count || 0)
}

export async function markNotificationRead(notificationId: number): Promise<number> {
  const { data } = await api.put<NotificationMutationResult>(`/notifications/${notificationId}/read`)
  return Number(data.updated || 0)
}

export async function markAllNotificationsRead(): Promise<number> {
  const { data } = await api.put<NotificationMutationResult>('/notifications/read-all')
  return Number(data.updated || 0)
}
