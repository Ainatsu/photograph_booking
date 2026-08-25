<template>
  <div class="messages-page">
    <div class="chat-container">
      <div class="contact-panel">
        <div class="panel-header">联系人</div>
        <div class="contact-list" v-loading="loadingContacts">
          <div
            v-for="c in contacts"
            :key="c.id"
            class="contact-item"
            :class="{ active: selectedContact?.id === c.id }"
            @click="selectContact(c)"
          >
            <el-badge
              :value="c.unread_count"
              :max="99"
              :hidden="!hasUnread(c)"
              class="contact-badge"
            >
              <el-avatar :size="40" :src="getContactAvatar(c)">
                {{ c.display_name?.[0] || '?' }}
              </el-avatar>
            </el-badge>
            <div class="contact-info">
              <div class="contact-name">{{ c.display_name }}</div>
              <div class="contact-role">{{ c.role === 'photographer' ? '摄影师' : '客户' }}</div>
            </div>
          </div>
          <el-empty v-if="!loadingContacts && !contacts.length" description="暂无消息" />
        </div>
      </div>

      <div class="chat-panel">
        <template v-if="selectedContact">
          <div class="chat-header">
            <span>{{ selectedContact.display_name }}</span>
          </div>
          <div v-if="orderContext" class="order-context-bar">
            <div>
              <span>订单沟通</span>
              <strong>订单 #{{ orderContext.id }} · {{ orderContext.title }}</strong>
            </div>
            <el-button text @click="goOrderDetail(orderContext.id)">查看订单</el-button>
          </div>
          <div class="chat-messages" ref="msgContainer">
            <div
              v-for="(msg, index) in messages"
              :key="timelineKey(msg)"
              class="timeline-item"
            >
              <div v-if="shouldShowTimeDivider(msg, index)" class="timeline-time">
                {{ formatTime(msg.created_at) }}
              </div>
              <div :class="isOrderEvent(msg) ? 'order-event-row' : { 'message-row': true, mine: msg.sender_id === myUserId }">
                <div
                  v-if="isOrderEvent(msg)"
                  class="order-event-card"
                  :class="`tone-${statusTone(msg.status)}`"
                >
                  <div class="order-event-eyebrow">
                    <span>订单动态</span>
                    <time :datetime="msg.created_at">{{ formatTime(msg.created_at) }}</time>
                  </div>
                  <div class="order-event-headline">
                    <strong class="order-event-title">{{ eventTitle(msg) }}</strong>
                    <span class="order-event-status">
                      <i class="order-event-dot" aria-hidden="true"></i>
                      <small>当前状态</small>
                      <b>{{ statusLabel(msg.status) }}</b>
                    </span>
                  </div>
                  <dl class="order-event-facts">
                    <div>
                      <dt>订单编号</dt>
                      <dd>{{ msg.order_id ? `#${msg.order_id}` : '暂未生成' }}</dd>
                    </div>
                    <div>
                      <dt>拍摄方案</dt>
                      <dd>{{ packageSummary(msg)?.title || '以订单详情为准' }}</dd>
                    </div>
                    <div>
                      <dt>订单金额</dt>
                      <dd>{{ packageSummary(msg)?.price || '以订单详情为准' }}</dd>
                    </div>
                    <div>
                      <dt>服务时长</dt>
                      <dd>{{ packageSummary(msg)?.duration || '以订单详情为准' }}</dd>
                    </div>
                  </dl>
                  <div v-if="msg.note" class="order-event-note">
                    <small>备注</small>
                    {{ msg.note }}
                  </div>
                  <div class="order-event-footer">
                    <span>由 {{ actorLabel(msg) }} 操作</span>
                    <el-button v-if="msg.order_id" text size="small" @click="goOrderDetail(msg.order_id)">
                      查看订单
                    </el-button>
                  </div>
                </div>
                <div v-else class="message-stack">
                  <button
                    v-if="msg.reference"
                    type="button"
                    class="message-reference-card"
                    @click.stop="openMessageReference(msg.reference)"
                  >
                    <img
                      v-if="msg.reference.cover_url && !msg.reference.cover_failed"
                      class="message-reference-cover"
                      :src="getFullUrl(msg.reference.cover_url)"
                      :alt="msg.reference.title || messageReferenceLabel(msg.reference.type)"
                      @error="markReferenceCoverFailed(msg.reference)"
                    />
                    <span v-else class="message-reference-cover message-reference-cover-placeholder">
                      {{ messageReferenceShortLabel(msg.reference.type) }}
                    </span>
                    <span class="message-reference-body">
                      <span class="message-reference-type">{{ messageReferenceLabel(msg.reference.type) }}</span>
                      <strong class="message-reference-title">{{ msg.reference.title }}</strong>
                    </span>
                  </button>
                  <div class="message-bubble">
                    <div class="message-text">{{ msg.content }}</div>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="!messages.length" class="no-messages">暂无消息，发送第一条吧</div>
          </div>
          <div class="chat-input">
            <div v-if="chatIntro" class="chat-intro-card">
              <div class="chat-intro-copy">
                <span>{{ chatIntroLabel }}</span>
                <strong>{{ chatIntro.title }}</strong>
                <small>{{ chatIntro.text }}</small>
              </div>
              <div class="chat-intro-actions">
                <el-button text size="small" @click="openIntroSource">查看</el-button>
                <el-button text size="small" @click="clearChatIntro">移除</el-button>
              </div>
            </div>
            <el-input
              v-model="inputText"
              placeholder="输入消息..."
              @keyup.enter="handleSend"
              :disabled="sending"
            >
              <template #append>
                <el-button @click="handleSend" :loading="sending">发送</el-button>
              </template>
            </el-input>
          </div>
        </template>
        <div v-else class="no-contact">选择一个联系人来开始聊天</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getContact, getContacts, getConversation, sendMessage as apiSendMessage, markRead } from '../api/message'
import { getOrderStatusTone, parseOrderPackageSnapshot } from '../utils/orderEventCard'

const route = useRoute()
const router = useRouter()

const contacts = ref([])
const selectedContact = ref(null)
const messages = ref([])
const inputText = ref('')
const loadingContacts = ref(false)
const sending = ref(false)
const msgContainer = ref(null)
const myUserId = ref(null)
const chatIntro = ref(null)
const appliedIntroKey = ref('')
const orderContext = computed(() => {
  const id = Number(queryValue(route.query.orderId) || 0)
  if (!id) return null
  return {
    id,
    title: queryValue(route.query.orderTitle) || '摄影服务订单',
  }
})

const statusLabels = {
  pending: '待确认',
  awaiting_customer_payment: '待支付',
  confirmed: '已确认',
  reschedule_requested: '改期待确认',
  in_progress: '拍摄中',
  delivered: '待接收',
  received: '待评价',
  reviewed: '已完成',
  completed: '已完成',
  cancelled: '已取消'
}

const eventLabels = {
  created: '订单已创建',
  confirmed: '订单已确认',
  reschedule_requested: '客户申请改期',
  reschedule_confirmed: '改期已确认',
  in_progress: '订单开始拍摄',
  delivered: '作品已交付',
  received: '客户已接收',
  reviewed: '客户已评价',
  completed: '订单已完成',
  cancelled: '订单已拒绝'
}

const roleLabels = {
  customer: '客户',
  photographer: '摄影师',
  system: '系统'
}

const introLabels = {
  package: '正在咨询方案',
  work: '正在咨询作品',
  project: '正在沟通企划'
}

const messageReferenceLabels = {
  package: '引用方案',
  work: '引用作品',
  project: '引用企划',
  item: '引用内容'
}

const messageReferenceShortLabels = {
  package: '方案',
  work: '作品',
  project: '企划',
  item: '引用'
}

const chatIntroLabel = computed(() => introLabels[chatIntro.value?.type] || '正在咨询')

const TIME_DIVIDER_INTERVAL = 5 * 60 * 1000
const WEEKDAY_LABELS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

let ws = null
let wsReconnectTimer = null
let heartbeatTimer = null
let reconnectDelay = 3000
let missedPongs = 0

const parseMyUserId = () => {
  const t = localStorage.getItem('token')
  if (!t) return
  try {
    const payload = JSON.parse(atob(t.split('.')[1]))
    myUserId.value = parseInt(payload.sub)
  } catch {}
}

const fetchContacts = async () => {
  loadingContacts.value = true
  try {
    const res = await getContacts()
    contacts.value = res.data
  } finally {
    loadingContacts.value = false
  }
}

const selectContact = async (contact, options = {}) => {
  if (!options.keepIntro) {
    clearChatIntro()
  }
  if (!options.keepOrderContext && orderContext.value) {
    router.replace({ path: '/messages', query: { to: contact.id } })
  }
  selectedContact.value = contact
  messages.value = []
  try {
    const res = await getConversation(contact.id, orderContext.value ? { order_id: orderContext.value.id } : {})
    messages.value = res.data
  } catch {}
  markRead(contact.id)
    .then(() => updateContactUnread(contact.id, 0))
    .catch(() => {})
  await nextTick()
  scrollToBottom()
}

const selectContactFromQuery = async (toId) => {
  const contactId = parseInt(toId, 10)
  if (!contactId || contactId === myUserId.value) return

  let target = contacts.value.find(c => Number(c.id) === contactId)
  if (!target) {
    try {
      const res = await getContact(contactId)
      target = res.data
      contacts.value = [target, ...contacts.value.filter(c => Number(c.id) !== contactId)]
    } catch {
      return
    }
  }

  await selectContact(target, { keepIntro: true, keepOrderContext: true })
  applyChatIntroFromQuery()
}

const queryValue = (value) => Array.isArray(value) ? value[0] : value

const buildChatIntroFromQuery = () => {
  const targetId = queryValue(route.query.to)
  const introText = queryValue(route.query.introText)
  if (!targetId || !introText) return null
  return {
    key: [
      targetId,
      queryValue(route.query.introType) || '',
      queryValue(route.query.introTitle) || '',
      queryValue(route.query.introUrl) || '',
      queryValue(route.query.introCoverUrl) || '',
      introText,
    ].join('|'),
    type: queryValue(route.query.introType) || 'item',
    title: queryValue(route.query.introTitle) || '刚刚浏览的内容',
    url: queryValue(route.query.introUrl) || '',
    cover_url: queryValue(route.query.introCoverUrl) || '',
    text: introText,
  }
}

const applyChatIntroFromQuery = () => {
  const intro = buildChatIntroFromQuery()
  if (!intro) {
    clearChatIntro()
    return
  }
  if (!selectedContact.value) return
  if (Number(queryValue(route.query.to)) !== Number(selectedContact.value.id)) return
  if (appliedIntroKey.value === intro.key) return

  const previousIntroText = chatIntro.value?.text || ''
  chatIntro.value = intro
  appliedIntroKey.value = intro.key
  if (!inputText.value.trim() || inputText.value === previousIntroText) {
    inputText.value = intro.text
  }
}

const clearChatIntro = () => {
  const currentIntroText = chatIntro.value?.text || ''
  chatIntro.value = null
  appliedIntroKey.value = ''
  if (inputText.value === currentIntroText) {
    inputText.value = ''
  }
}

const openIntroSource = () => {
  if (chatIntro.value?.url) {
    router.push(chatIntro.value.url)
  }
}

const buildMessageReference = () => {
  if (!chatIntro.value) return null
  const title = String(chatIntro.value.title || '').trim()
  if (!title) return null
  const type = ['package', 'work', 'project'].includes(chatIntro.value.type) ? chatIntro.value.type : 'item'
  const url = String(chatIntro.value.url || '').trim()
  const coverUrl = String(chatIntro.value.cover_url || '').trim()
  return {
    type,
    title,
    ...(url ? { url } : {}),
    ...(coverUrl ? { cover_url: coverUrl } : {})
  }
}

const messageReferenceLabel = (type) => messageReferenceLabels[type] || messageReferenceLabels.item

const messageReferenceShortLabel = (type) => messageReferenceShortLabels[type] || messageReferenceShortLabels.item

const markReferenceCoverFailed = (reference) => {
  if (reference) {
    reference.cover_failed = true
  }
}

const openMessageReference = (reference) => {
  if (reference?.url) {
    router.push(reference.url)
  }
}

const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text || !selectedContact.value) return
  sending.value = true
  try {
    const reference = buildMessageReference()
    await apiSendMessage({
      receiver_id: selectedContact.value.id,
      content: text,
      ...(orderContext.value ? { order_id: orderContext.value.id } : {}),
      ...(reference ? { reference } : {})
    })
    inputText.value = ''
    chatIntro.value = null
    appliedIntroKey.value = ''
    await reloadMessages()
  } catch {
  } finally {
    sending.value = false
  }
}

const reloadMessages = async () => {
  if (!selectedContact.value) return
  try {
    const res = await getConversation(
      selectedContact.value.id,
      orderContext.value ? { order_id: orderContext.value.id } : {},
    )
    messages.value = res.data
  } catch {}
  await nextTick()
  scrollToBottom()
}

const scrollToBottom = () => {
  if (msgContainer.value) {
    msgContainer.value.scrollTop = msgContainer.value.scrollHeight
  }
}

const getFullUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return url
}

const getContactAvatar = (c) => {
  return getFullUrl(c.avatar_url)
}

const hasUnread = (contact) => Number(contact?.unread_count || 0) > 0

const timelineKey = (msg) => `${msg.item_type || 'message'}-${msg.id}`

const updateContactUnread = (contactId, unreadCount) => {
  const target = contacts.value.find(c => Number(c.id) === Number(contactId))
  if (target) target.unread_count = unreadCount
  if (selectedContact.value && Number(selectedContact.value.id) === Number(contactId)) {
    selectedContact.value.unread_count = unreadCount
  }
}

const getTimelineTimestamp = (item) => {
  const time = new Date(item?.created_at).getTime()
  return Number.isNaN(time) ? null : time
}

const shouldShowTimeDivider = (msg, index) => {
  const current = getTimelineTimestamp(msg)
  if (current === null) return false
  if (index === 0) return true

  const previous = getTimelineTimestamp(messages.value[index - 1])
  if (previous === null) return true
  return current - previous >= TIME_DIVIDER_INTERVAL
}

const isSameDate = (a, b) => (
  a.getFullYear() === b.getFullYear() &&
  a.getMonth() === b.getMonth() &&
  a.getDate() === b.getDate()
)

const startOfDate = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate())

const formatTime = (t) => {
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return ''

  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const timeText = `${pad(d.getHours())}:${pad(d.getMinutes())}`

  if (isSameDate(d, now)) return timeText

  const dayDiff = Math.floor((startOfDate(now) - startOfDate(d)) / (24 * 60 * 60 * 1000))
  if (dayDiff === 1) return `昨天 ${timeText}`
  if (dayDiff > 1 && dayDiff < 7) return `${WEEKDAY_LABELS[d.getDay()]} ${timeText}`
  if (d.getFullYear() === now.getFullYear()) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${timeText}`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${timeText}`
}

const isOrderEvent = (msg) => msg?.item_type === 'order_event'

const statusLabel = (status) => statusLabels[status] || status || '状态更新'

const eventTitle = (msg) => eventLabels[msg.event_type] || '订单状态更新'

const actorLabel = (msg) => msg.actor_name || roleLabels[msg.actor_role] || '系统'

const statusTone = (status) => getOrderStatusTone(status)

const packageSummary = (msg) => parseOrderPackageSnapshot(msg.package_snapshot)

const timelineTime = (item) => {
  return getTimelineTimestamp(item) ?? 0
}

const appendTimelineItem = (item) => {
  if (!item?.id || messages.value.some(existing => existing.id === item.id && existing.item_type === item.item_type)) return
  messages.value.push(item)
  messages.value.sort((a, b) => timelineTime(a) - timelineTime(b))
  nextTick(() => scrollToBottom())
}

const messageBelongsToSelectedContact = (msg) => {
  if (!selectedContact.value) return false
  const selectedId = Number(selectedContact.value.id)
  const currentId = Number(myUserId.value)
  return (
    (Number(msg.sender_id) === selectedId && Number(msg.receiver_id) === currentId) ||
    (Number(msg.sender_id) === currentId && Number(msg.receiver_id) === selectedId)
  )
}

const orderEventBelongsToSelectedContact = (event) => {
  if (!selectedContact.value) return false
  const selectedId = Number(selectedContact.value.id)
  const currentId = Number(myUserId.value)
  return (
    (Number(event.customer_id) === currentId && Number(event.photographer_id) === selectedId) ||
    (Number(event.photographer_id) === currentId && Number(event.customer_id) === selectedId)
  )
}

const goOrderDetail = (orderId) => {
  if (!orderId) return
  router.push(`/orders/${orderId}`)
}

const connectWS = () => {
  const token = localStorage.getItem('token')
  if (!token) return
  try {
    clearInterval(heartbeatTimer)
    missedPongs = 0

    ws = new WebSocket(`ws://${window.location.host}/ws?token=${token}`)

    ws.onopen = () => {
      reconnectDelay = 3000
      heartbeatTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
          missedPongs++
          if (missedPongs >= 3) {
            ws.close()
          }
        }
      }, 30000)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'pong') {
        missedPongs = 0
        return
      }

      if (data.type === 'new_message') {
        const msg = data.message
        const isCurrentConversation = messageBelongsToSelectedContact(msg)
        if (isCurrentConversation) {
          appendTimelineItem({
            item_type: 'message',
            id: msg.id,
            message_id: msg.message_id || msg.id,
            sender_id: msg.sender_id,
            receiver_id: msg.receiver_id,
            content: msg.content,
            order_id: msg.order_id,
            reference: msg.reference,
            is_read: msg.is_read,
            created_at: msg.created_at
          })
        }
        if (msg.sender_id !== myUserId.value) {
          if (isCurrentConversation) {
            markRead(msg.sender_id)
              .then(() => updateContactUnread(msg.sender_id, 0))
              .catch(() => {})
          } else {
            fetchContacts()
          }
        }
      }

      if (data.type === 'order_event') {
        const orderEvent = data.event
        const isCurrentConversation = orderEventBelongsToSelectedContact(orderEvent)
        if (isCurrentConversation) {
          appendTimelineItem(orderEvent)
          const contactId = Number(orderEvent.customer_id) === Number(myUserId.value)
            ? orderEvent.photographer_id
            : orderEvent.customer_id
          markRead(contactId)
            .then(() => updateContactUnread(contactId, 0))
            .catch(() => {})
        } else {
          fetchContacts()
        }
      }
    }

    ws.onclose = () => {
      clearInterval(heartbeatTimer)
      reconnectDelay = Math.min(reconnectDelay * 2, 60000)
      wsReconnectTimer = setTimeout(connectWS, reconnectDelay)
    }

    ws.onerror = () => {
      ws?.close()
    }
  } catch {}
}

const handleRouteQuery = async () => {
  const toId = queryValue(route.query.to)
  if (!toId) {
    clearChatIntro()
    return
  }
  await selectContactFromQuery(toId)
}

onMounted(async () => {
  document.documentElement.style.overflow = 'hidden'
  document.body.style.overflow = 'hidden'

  parseMyUserId()
  await fetchContacts()
  connectWS()

  await handleRouteQuery()
})

watch(
  () => [
    route.query.to,
    route.query.introType,
    route.query.introTitle,
    route.query.introUrl,
    route.query.introCoverUrl,
    route.query.introText,
    route.query.orderId,
    route.query.orderTitle,
  ],
  () => {
    handleRouteQuery()
  }
)

onUnmounted(() => {
  document.documentElement.style.overflow = ''
  document.body.style.overflow = ''

  if (ws) {
    ws.onclose = null
    ws.close()
  }
  clearTimeout(wsReconnectTimer)
  clearInterval(heartbeatTimer)
})
</script>

<style scoped>
.messages-page {
  max-width: 1000px;
  margin: 16px auto 0;
  height: min(640px, calc(100dvh - 210px));
  min-height: 380px;
  padding: 0 16px 8px;
  box-sizing: border-box;
  overflow: hidden;
}

.chat-container {
  display: flex;
  height: 100%;
  min-height: 0;
  border: var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-paper-light);
}

.contact-panel {
  width: 260px;
  border-right: 1px solid var(--color-divider);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel-header {
  padding: 10px 16px;
  font-weight: bold;
  font-size: 15px;
  border-bottom: 1px solid var(--color-divider);
  color: var(--color-ink);
}

.contact-list {
  flex: 1;
  overflow-y: auto;
}

.contact-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.contact-item:hover {
  background: var(--color-paper);
}

.contact-item.active {
  background: var(--color-brand-light);
}

.contact-badge {
  flex-shrink: 0;
  margin-right: 12px;
}

.contact-info {
  min-width: 0;
  flex: 1;
}

.contact-name {
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-ink);
}

.contact-role {
  font-size: var(--text-xs);
  color: var(--color-ink-secondary);
  margin-top: 2px;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chat-header {
  padding: 10px 16px;
  font-weight: bold;
  font-size: 15px;
  border-bottom: 1px solid var(--color-divider);
  color: var(--color-ink);
}

.order-context-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-divider);
  background: var(--color-brand-light);
}

.order-context-bar > div {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.order-context-bar span {
  color: var(--color-brand);
  font-size: var(--text-xs);
  font-weight: 600;
}

.order-context-bar strong {
  overflow: hidden;
  color: var(--color-ink);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 14px;
  background: var(--color-paper);
}

.timeline-item {
  margin-bottom: 16px;
}

.timeline-time {
  display: flex;
  justify-content: center;
  margin: 2px 0 8px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 18px;
}

.message-row {
  display: flex;
}

.message-row.mine {
  justify-content: flex-end;
}

.order-event-row {
  display: flex;
  justify-content: center;
}

.order-event-card {
  width: min(520px, 100%);
  overflow: hidden;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.order-event-eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 14px;
  border-bottom: 1px solid var(--color-divider);
  background: var(--color-paper);
}

.order-event-eyebrow span {
  color: var(--color-brand);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.order-event-eyebrow time {
  color: var(--color-ink-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.order-event-headline {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px 12px;
  padding: 12px 14px;
}

.order-event-title {
  min-width: 0;
  color: var(--color-ink);
  font-size: 16px;
  font-weight: 600;
  line-height: 1.45;
}

.order-event-status {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 6px;
}

.order-event-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--color-ink-tertiary);
}

.order-event-status small {
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
}

.order-event-status b {
  font-size: var(--text-xs);
  font-weight: 700;
}

.tone-brand .order-event-dot { background: var(--color-brand); }
.tone-brand .order-event-status b { color: var(--color-brand); }
.tone-warning .order-event-dot { background: var(--color-warning); }
.tone-warning .order-event-status b { color: var(--color-warning); }
.tone-danger .order-event-dot { background: var(--color-danger); }
.tone-danger .order-event-status b { color: var(--color-danger); }

.order-event-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 0;
  border-top: 1px solid var(--color-divider);
}

.order-event-facts > div {
  display: grid;
  align-content: center;
  gap: 3px;
  min-height: 56px;
  padding: 8px 14px;
}

.order-event-facts > div:nth-child(odd) {
  border-right: 1px solid var(--color-divider);
}

.order-event-facts > div:nth-child(-n + 2) {
  border-bottom: 1px solid var(--color-divider);
}

.order-event-facts dt {
  color: var(--color-ink-secondary);
  font-size: 12px;
}

.order-event-facts dd {
  margin: 0;
  overflow: hidden;
  color: var(--color-ink);
  font-size: var(--text-sm);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.order-event-note {
  display: grid;
  gap: 3px;
  padding: 12px 14px;
  border-top: 1px solid var(--color-divider);
  color: var(--color-ink);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  word-break: break-word;
}

.order-event-note small {
  color: var(--color-ink-secondary);
  font-size: 12px;
  font-weight: 700;
}

.order-event-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 40px;
  padding: 4px 14px 4px 14px;
  border-top: 1px solid var(--color-divider);
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
}

.message-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 65%;
  gap: 6px;
}

.message-row.mine .message-stack {
  align-items: flex-end;
}

.message-bubble {
  max-width: 100%;
  width: fit-content;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  border: var(--border-default);
}

.message-row.mine .message-bubble {
  background: var(--color-brand-light);
  color: var(--color-ink);
  border-color: var(--color-brand-light);
}

.message-reference-card {
  display: flex;
  width: min(320px, 100%);
  min-height: 86px;
  padding: 0;
  overflow: hidden;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  text-align: left;
  cursor: pointer;
}

.message-reference-cover {
  width: 108px;
  aspect-ratio: 4 / 3;
  flex-shrink: 0;
  object-fit: cover;
  background: var(--color-paper);
}

.message-reference-cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-brand);
  font-size: var(--text-sm);
  font-weight: 600;
}

.message-reference-body {
  display: grid;
  min-width: 0;
  align-content: center;
  gap: 5px;
  padding: 10px 12px;
}

.message-reference-type {
  color: var(--color-brand);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.3;
}

.message-reference-title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.message-reference-card:hover {
  border-color: var(--color-brand);
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.no-messages {
  text-align: center;
  color: var(--color-ink-tertiary);
  margin-top: 40px;
}

.chat-input {
  padding: 8px 12px;
  border-top: 1px solid var(--color-divider);
}

.chat-intro-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  padding: 10px 12px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-brand-light);
}

.chat-intro-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.chat-intro-copy span {
  color: var(--color-brand);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.3;
}

.chat-intro-copy strong {
  overflow: hidden;
  color: var(--color-ink);
  font-size: 14px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-intro-copy small {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.chat-intro-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
}

.no-contact {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-tertiary);
  font-size: 15px;
}

@media (max-width: 640px) {
  .message-stack {
    max-width: 82%;
  }

  .message-reference-card {
    width: min(300px, 100%);
  }

  .message-reference-cover {
    width: 96px;
  }

  .chat-intro-card {
    align-items: stretch;
    flex-direction: column;
  }

  .chat-intro-actions {
    justify-content: flex-end;
  }
}
</style>
