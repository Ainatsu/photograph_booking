import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getNotifications,
  getNotificationUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notifications'
import type { NotificationRecord } from '@/types/notifications'
import { mergeNotificationRecords } from '@/utils/notification'

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationRecord[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)
  const loaded = ref(false)

  let requestId = 0
  let revision = 0

  async function refresh() {
    const currentRequestId = ++requestId
    const startingRevision = revision
    loading.value = true
    try {
      const [nextItems, nextUnreadCount] = await Promise.all([
        getNotifications({ limit: 100 }),
        getNotificationUnreadCount(),
      ])
      if (currentRequestId !== requestId) return

      items.value = startingRevision === revision
        ? mergeNotificationRecords(nextItems)
        : mergeNotificationRecords(nextItems, items.value)
      unreadCount.value = startingRevision === revision
        ? nextUnreadCount
        : Math.max(unreadCount.value, items.value.filter((item) => !item.is_read).length)
      loaded.value = true
    } finally {
      if (currentRequestId === requestId) loading.value = false
    }
  }

  async function refreshUnread() {
    const startingRevision = revision
    const nextCount = await getNotificationUnreadCount()
    if (startingRevision === revision) unreadCount.value = nextCount
    else unreadCount.value = Math.max(unreadCount.value, items.value.filter((item) => !item.is_read).length)
  }

  function receive(item: NotificationRecord) {
    const existing = items.value.find((record) => record.id === item.id)
    if (!existing && !item.is_read) unreadCount.value += 1
    if (existing?.is_read && !item.is_read) unreadCount.value += 1
    if (existing && !existing.is_read && item.is_read) unreadCount.value = Math.max(0, unreadCount.value - 1)
    items.value = mergeNotificationRecords(items.value, [item])
    revision += 1
  }

  async function markRead(notificationId: number) {
    await markNotificationRead(notificationId)
    const target = items.value.find((item) => item.id === notificationId)
    if (!target || target.is_read) return
    target.is_read = true
    target.read_at = new Date().toISOString()
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    revision += 1
  }

  async function markAllRead() {
    await markAllNotificationsRead()
    const readAt = new Date().toISOString()
    items.value.forEach((item) => {
      item.is_read = true
      item.read_at ||= readAt
    })
    unreadCount.value = 0
    revision += 1
  }

  function reset() {
    requestId += 1
    revision += 1
    items.value = []
    unreadCount.value = 0
    loading.value = false
    loaded.value = false
  }

  return {
    items,
    unreadCount,
    loading,
    loaded,
    refresh,
    refreshUnread,
    receive,
    markRead,
    markAllRead,
    reset,
  }
})
