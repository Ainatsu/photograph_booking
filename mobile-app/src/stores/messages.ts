import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  buildMessageSocketUrl,
  getMessageContacts,
  getMessageUnreadCount,
  markMessagesRead,
} from '@/api/messages'
import type { MessageContact, MessageSocketPayload } from '@/types/messages'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notifications'
import { parseMessageSocketPayload } from '@/utils/message'

export const MESSAGE_SOCKET_EVENT = 'messages:socket'

export const useMessageStore = defineStore('messages', () => {
  const auth = useAuthStore()
  const notifications = useNotificationStore()
  const contacts = ref<MessageContact[]>([])
  const unreadCount = ref(0)
  const loadingContacts = ref(false)
  const connected = ref(false)
  const activeContactId = ref<number | null>(null)

  let socket: WebSocket | null = null
  let reconnectTimer: number | null = null
  let heartbeatTimer: number | null = null
  let reconnectDelay = 3000
  let missedPongs = 0
  let manuallyDisconnected = false

  async function refreshContacts() {
    loadingContacts.value = true
    try {
      contacts.value = await getMessageContacts()
    } finally {
      loadingContacts.value = false
    }
  }

  async function refreshUnread() {
    unreadCount.value = await getMessageUnreadCount()
  }

  function setActiveContact(userId: number | null) {
    activeContactId.value = userId
  }

  function clearTimers() {
    if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
    if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)
    reconnectTimer = null
    heartbeatTimer = null
  }

  async function handleIncoming(payload: MessageSocketPayload) {
    window.dispatchEvent(new CustomEvent<MessageSocketPayload>(MESSAGE_SOCKET_EVENT, { detail: payload }))
    if (payload.type === 'pong') {
      missedPongs = 0
      return
    }
    if (payload.type === 'notification') {
      notifications.receive(payload.notification)
      return
    }

    let contactId = 0
    if (payload.type === 'new_message') contactId = Number(payload.message.sender_id || 0)
    if (payload.type === 'order_event') {
      const currentUserId = Number(auth.user?.id || 0)
      contactId = Number(payload.event.customer_id) === currentUserId
        ? Number(payload.event.photographer_id || 0)
        : Number(payload.event.customer_id || 0)
    }

    if (contactId && contactId === activeContactId.value) {
      await markMessagesRead(contactId).catch(() => undefined)
    }
    await Promise.all([
      refreshContacts().catch(() => undefined),
      refreshUnread().catch(() => undefined),
    ])
  }

  function connect(token: string) {
    if (!token || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return
    manuallyDisconnected = false
    clearTimers()

    try {
      socket = new WebSocket(buildMessageSocketUrl(token))
    } catch {
      scheduleReconnect(token)
      return
    }

    socket.onopen = () => {
      connected.value = true
      reconnectDelay = 3000
      missedPongs = 0
      void Promise.all([
        refreshUnread().catch(() => undefined),
        notifications.refreshUnread().catch(() => undefined),
      ])
      heartbeatTimer = window.setInterval(() => {
        if (socket?.readyState !== WebSocket.OPEN) return
        socket.send(JSON.stringify({ type: 'ping' }))
        missedPongs += 1
        if (missedPongs >= 3) socket.close()
      }, 30_000)
    }

    socket.onmessage = (event) => {
      try {
        const payload = parseMessageSocketPayload(JSON.parse(String(event.data)))
        if (payload) void handleIncoming(payload).catch(() => undefined)
      } catch {
        // 忽略无法识别的实时消息，后续刷新仍会从服务端恢复状态。
      }
    }

    socket.onerror = () => socket?.close()
    socket.onclose = () => {
      connected.value = false
      socket = null
      if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
      if (!manuallyDisconnected && localStorage.getItem('token')) scheduleReconnect(token)
    }
  }

  function scheduleReconnect(token: string) {
    if (manuallyDisconnected || reconnectTimer !== null) return
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect(token)
    }, reconnectDelay)
    reconnectDelay = Math.min(reconnectDelay * 2, 60_000)
  }

  function disconnect() {
    manuallyDisconnected = true
    clearTimers()
    if (socket) {
      socket.onclose = null
      socket.close()
      socket = null
    }
    connected.value = false
    activeContactId.value = null
    unreadCount.value = 0
    contacts.value = []
  }

  return {
    contacts,
    unreadCount,
    loadingContacts,
    connected,
    activeContactId,
    refreshContacts,
    refreshUnread,
    setActiveContact,
    connect,
    disconnect,
  }
})
