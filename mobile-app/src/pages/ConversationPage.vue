<template>
  <ion-page>
    <DetailHeader :title="contact?.display_name || '站内会话'" default-href="/tabs/messages">
      <template v-if="orderContext" #action>
        <button type="button" class="header-action pressable" aria-label="查看关联订单" @click="openOrder(orderContext.id)">
          <ReceiptText :size="20" aria-hidden="true" />
        </button>
      </template>
    </DetailHeader>

    <ion-content class="conversation-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新会话" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="conversation-shell">
        <FeedSkeleton v-if="loading" :count="5" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="会话暂时无法加载"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="contact">
          <button v-if="orderContext" type="button" class="order-context pressable" @click="openOrder(orderContext.id)">
            <span><ReceiptText :size="20" aria-hidden="true" /></span>
            <span>
              <small>订单沟通</small>
              <strong>订单 #{{ orderContext.id }} · {{ orderContext.title }}</strong>
            </span>
            <ChevronRight :size="20" aria-hidden="true" />
          </button>

          <div v-if="!messageStore.connected" class="connection-note" role="status">
            <WifiOff :size="16" aria-hidden="true" />
            实时连接正在恢复，仍可发送消息和手动刷新。
          </div>

          <section v-if="timeline.length" class="timeline" aria-label="会话记录">
            <article v-for="(item, index) in timeline" :key="timelineKey(item)" class="timeline-item">
              <div v-if="shouldShowChatTimeDivider(timeline, index)" class="time-divider">
                {{ formatChatTime(item.created_at) }}
              </div>

              <component
                :is="item.order_id ? 'button' : 'div'"
                v-if="item.item_type === 'order_event'"
                :type="item.order_id ? 'button' : undefined"
                class="order-event-card"
                :class="[`tone-${getChatStatusTone(item.status)}`, { pressable: Boolean(item.order_id) }]"
                :aria-label="orderEventLabel(item)"
                @click="item.order_id && openOrder(item.order_id)"
              >
                <span class="event-eyebrow">
                  <span><ReceiptText :size="15" aria-hidden="true" />订单动态</span>
                  <time :datetime="item.created_at">{{ formatChatTime(item.created_at) }}</time>
                </span>

                <strong class="event-title">{{ getChatEventTitle(item.event_type) }}</strong>

                <span class="event-status">
                  <span class="status-dot" aria-hidden="true" />
                  <small>当前状态</small>
                  <strong>{{ getChatStatusLabel(item.status) }}</strong>
                </span>

                <span class="event-facts">
                  <span>
                    <small>订单编号</small>
                    <strong>{{ item.order_id ? `#${item.order_id}` : '暂未生成' }}</strong>
                  </span>
                  <span>
                    <small>拍摄方案</small>
                    <strong>{{ orderEventPackage(item)?.title || '以订单详情为准' }}</strong>
                  </span>
                  <span>
                    <small>订单金额</small>
                    <strong>{{ orderEventPackage(item)?.price || '以订单详情为准' }}</strong>
                  </span>
                  <span>
                    <small>服务时长</small>
                    <strong>{{ orderEventPackage(item)?.duration || '以订单详情为准' }}</strong>
                  </span>
                </span>

                <span v-if="item.note" class="event-note">
                  <small>备注</small>
                  {{ item.note }}
                </span>

                <span class="event-footer">
                  <span>由 {{ getChatActorLabel(item) }} 操作</span>
                  <span v-if="item.order_id" class="event-cta">查看订单 <ChevronRight :size="15" aria-hidden="true" /></span>
                </span>
              </component>

              <div v-else class="message-row" :class="{ mine: isMine(item) }">
                <div class="message-stack">
                  <button
                    v-if="item.reference"
                    type="button"
                    class="reference-card pressable"
                    :disabled="!item.reference.url"
                    @click="openReference(item.reference.url)"
                  >
                    <img
                      v-if="item.reference.cover_url"
                      :src="resolveMediaUrl(item.reference.cover_url)"
                      :alt="item.reference.title"
                      loading="lazy"
                    />
                    <span v-else class="reference-placeholder"><Images :size="22" aria-hidden="true" /></span>
                    <span>
                      <small>{{ referenceLabel(item.reference.type) }}</small>
                      <strong>{{ item.reference.title }}</strong>
                    </span>
                  </button>
                  <p class="message-bubble">{{ item.content }}</p>
                </div>
              </div>
            </article>
            <span ref="timelineEnd" aria-hidden="true" />
          </section>

          <StatePanel
            v-else
            title="发送第一条消息"
            description="请围绕需求、价格、时间和交付标准进行沟通，重要约定最终以订单快照为准。"
          />
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="3000"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <ion-footer v-if="contact && !loading && !error" class="composer-footer">
      <div class="composer-shell">
        <div v-if="intro" class="intro-card">
          <span>
            <small>{{ referenceLabel(intro.type) }}</small>
            <strong>{{ intro.title }}</strong>
          </span>
          <button type="button" class="intro-remove pressable" aria-label="移除引用内容" @click="clearIntro">
            <X :size="18" aria-hidden="true" />
          </button>
        </div>
        <form class="composer" @submit.prevent="submitMessage">
          <label for="message-draft" class="sr-only">输入消息</label>
          <textarea
            id="message-draft"
            v-model="draft"
            rows="1"
            maxlength="2000"
            placeholder="输入消息…"
            :disabled="sending"
          />
          <button
            type="submit"
            class="send-button pressable"
            aria-label="发送消息"
            :disabled="sending || !draft.trim()"
            :aria-busy="sending"
          >
            <ion-spinner v-if="sending" name="crescent" aria-hidden="true" />
            <Send v-else :size="20" aria-hidden="true" />
          </button>
        </form>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonFooter,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  ChevronRight,
  Images,
  ReceiptText,
  Send,
  WifiOff,
  X,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  getConversation,
  getMessageContact,
  markMessagesRead,
  sendMessage,
} from '@/api/messages'
import { useAuthStore } from '@/stores/auth'
import { MESSAGE_SOCKET_EVENT, useMessageStore } from '@/stores/messages'
import type {
  ChatTimelineItem,
  MessageContact,
  MessageReference,
  MessageSocketPayload,
} from '@/types/messages'
import {
  formatChatTime,
  getChatActorLabel,
  getChatEventTitle,
  getChatStatusLabel,
  getChatStatusTone,
  parseChatPackageSnapshot,
  shouldShowChatTimeDivider,
  timelineItemBelongsToContact,
} from '@/utils/message'
import { resolveMediaUrl } from '@/utils/media'

interface ChatIntro extends MessageReference {
  text?: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const messageStore = useMessageStore()
const contact = ref<MessageContact | null>(null)
const timeline = ref<ChatTimelineItem[]>([])
const loading = ref(true)
const error = ref('')
const draft = ref('')
const sending = ref(false)
const toastMessage = ref('')
const timelineEnd = ref<HTMLElement | null>(null)
const intro = ref<ChatIntro | null>(null)
let loadRequestId = 0

const contactUserId = computed(() => Number(route.params.userId || 0))
const currentUserId = computed(() => Number(auth.user?.id || 0))
const orderContext = computed(() => {
  const id = Number(route.query.orderId || 0)
  if (!Number.isInteger(id) || id <= 0) return null
  return { id, title: String(route.query.orderTitle || '摄影服务订单') }
})

function queryText(key: string) {
  const value = route.query[key]
  return Array.isArray(value) ? String(value[0] || '') : String(value || '')
}

function readIntroFromRoute(): ChatIntro | null {
  const text = queryText('introText').trim()
  const title = queryText('introTitle').trim()
  if (!text && !title) return null
  const requestedType = queryText('introType')
  const type: MessageReference['type'] = requestedType === 'package' || requestedType === 'work'
    ? requestedType
    : 'item'
  return {
    type,
    title: title || '正在咨询的内容',
    url: queryText('introUrl') || undefined,
    cover_url: queryText('introCoverUrl') || undefined,
    text,
  }
}

function orderEventPackage(item: ChatTimelineItem) {
  return parseChatPackageSnapshot(item.package_snapshot)
}

function orderEventLabel(item: ChatTimelineItem) {
  const order = item.order_id ? `订单 #${item.order_id}` : '订单'
  const suffix = item.order_id ? '，点击查看订单详情' : ''
  return `${order}动态：${getChatEventTitle(item.event_type)}，当前状态${getChatStatusLabel(item.status)}${suffix}`
}

async function load() {
  const requestId = ++loadRequestId
  loading.value = true
  error.value = ''
  if (!Number.isInteger(contactUserId.value) || contactUserId.value <= 0) {
    error.value = '联系人编号无效。'
    loading.value = false
    return
  }

  try {
    await auth.initialize()
    if (contactUserId.value === currentUserId.value) throw new Error('不能给自己发送消息。')
    const params = { limit: 200, ...(orderContext.value ? { order_id: orderContext.value.id } : {}) }
    const [contactResult, timelineResult] = await Promise.all([
      getMessageContact(contactUserId.value),
      getConversation(contactUserId.value, params),
    ])
    if (requestId !== loadRequestId) return
    contact.value = contactResult
    timeline.value = timelineResult
    messageStore.setActiveContact(contactUserId.value)
    await markMessagesRead(contactUserId.value).catch(() => undefined)
    await Promise.all([
      messageStore.refreshContacts().catch(() => undefined),
      messageStore.refreshUnread().catch(() => undefined),
    ])
  } catch (loadError) {
    if (requestId !== loadRequestId) return
    error.value = getApiErrorMessage(loadError)
  } finally {
    if (requestId === loadRequestId) {
      loading.value = false
      if (!error.value) void scrollToBottom(false)
    }
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  event.target.complete()
}

function timelineKey(item: ChatTimelineItem) {
  return `${item.item_type}-${item.id}`
}

function isMine(item: ChatTimelineItem) {
  return Number(item.sender_id) === currentUserId.value
}

function referenceLabel(type: MessageReference['type']) {
  return ({ package: '引用摄影方案', work: '引用摄影作品', item: '引用内容' })[type]
}

function normalizeReferenceUrl(value: string) {
  return value
    .replace(/^\/work\//, '/works/')
    .replace(/^\/photographer\//, '/photographers/')
    .replace(/^\/package\//, '/packages/')
    .replace(/^\/project\//, '/projects/')
}

function openReference(value?: string | null) {
  if (value) void router.push(normalizeReferenceUrl(value))
}

function openOrder(orderId: number) {
  void router.push({ name: 'order-detail', params: { orderId } })
}

function appendTimelineItem(item: ChatTimelineItem) {
  if (timeline.value.some((existing) => existing.item_type === item.item_type && String(existing.id) === String(item.id))) return
  timeline.value.push(item)
  timeline.value.sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime())
  void scrollToBottom()
}

async function scrollToBottom(smooth = true) {
  await nextTick()
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  timelineEnd.value?.scrollIntoView({ behavior: smooth && !reduceMotion ? 'smooth' : 'auto', block: 'end' })
}

function clearIntro() {
  const introText = intro.value?.text || ''
  intro.value = null
  if (draft.value === introText) draft.value = ''
  const introKeys = new Set(['introType', 'introTitle', 'introUrl', 'introCoverUrl', 'introText'])
  const query = Object.fromEntries(Object.entries(route.query).filter(([key]) => !introKeys.has(key)))
  void router.replace({ query })
}

async function submitMessage() {
  const content = draft.value.trim()
  if (!content || !contact.value || sending.value) return
  sending.value = true
  try {
    const record = await sendMessage({
      receiver_id: contact.value.id,
      content,
      ...(orderContext.value ? { order_id: orderContext.value.id } : {}),
      ...(intro.value ? {
        reference: {
          type: intro.value.type,
          title: intro.value.title,
          ...(intro.value.url ? { url: intro.value.url } : {}),
          ...(intro.value.cover_url ? { cover_url: intro.value.cover_url } : {}),
        },
      } : {}),
    })
    appendTimelineItem({ item_type: 'message', ...record })
    draft.value = ''
    if (intro.value) clearIntro()
    await messageStore.refreshContacts().catch(() => undefined)
  } catch (sendError) {
    toastMessage.value = getApiErrorMessage(sendError)
  } finally {
    sending.value = false
  }
}

function handleSocketEvent(event: Event) {
  const payload = (event as CustomEvent<MessageSocketPayload>).detail
  const item = payload.type === 'new_message'
    ? payload.message
    : payload.type === 'order_event'
      ? payload.event
      : null
  if (!item || !timelineItemBelongsToContact(item, currentUserId.value, contactUserId.value)) return
  if (orderContext.value && Number(item.order_id) !== orderContext.value.id) return
  appendTimelineItem(item)
}

watch(contactUserId, () => void load())

onMounted(() => {
  intro.value = readIntroFromRoute()
  if (intro.value?.text) draft.value = intro.value.text
  window.addEventListener(MESSAGE_SOCKET_EVENT, handleSocketEvent)
  void load()
})

onUnmounted(() => {
  window.removeEventListener(MESSAGE_SOCKET_EVENT, handleSocketEvent)
  if (messageStore.activeContactId === contactUserId.value) messageStore.setActiveContact(null)
})
</script>

<style scoped>
.conversation-content { --background: var(--paper); }
.conversation-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-6); }
.header-action { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; background: transparent; color: var(--ink); }

.order-context { display: grid; grid-template-columns: 42px minmax(0, 1fr) 22px; width: 100%; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); padding: var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--brand-soft); box-shadow: var(--neu-raise); color: var(--ink); text-align: left; }
.order-context > span:first-child { display: grid; width: 42px; height: 42px; place-items: center; border-radius: var(--radius-sm); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--brand); }
.order-context > span:nth-child(2) { display: grid; min-width: 0; gap: 3px; }
.order-context small { color: var(--brand); font-size: 11px; font-weight: 750; }
.order-context strong { overflow: hidden; font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.order-context > svg { color: var(--brand); }
.connection-note { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-4); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.5; }

.timeline { display: grid; gap: var(--space-4); }
.timeline-item { display: grid; gap: var(--space-2); }
.time-divider { color: var(--ink-tertiary); font-size: 11px; text-align: center; }
.message-row { display: flex; justify-content: flex-start; }
.message-row.mine { justify-content: flex-end; }
.message-stack { display: grid; max-width: 84%; justify-items: start; gap: 6px; }
.message-row.mine .message-stack { justify-items: end; }
.message-bubble { width: fit-content; max-width: 100%; margin: 0; padding: 10px 13px; border: 0; border-radius: 4px var(--radius-md) var(--radius-md) var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink); font-size: var(--text-sm); line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.message-row.mine .message-bubble { border-color: var(--brand-soft); border-radius: var(--radius-md) 4px var(--radius-md) var(--radius-md); background: var(--brand-soft); }

.reference-card { display: grid; grid-template-columns: 76px minmax(0, 1fr); width: min(300px, 100%); min-height: 76px; overflow: hidden; padding: 0; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); text-align: left; }
.reference-card img, .reference-placeholder { width: 76px; height: 76px; object-fit: cover; }
.reference-placeholder { display: grid; place-items: center; background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); }
.reference-card > span:last-child { display: grid; min-width: 0; align-content: center; gap: 4px; padding: var(--space-2) var(--space-3); }
.reference-card small { color: var(--brand); font-size: 11px; font-weight: 700; }
.reference-card strong { display: -webkit-box; overflow: hidden; font-size: var(--text-xs); line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.reference-card:disabled { opacity: 1; }

.order-event-card { display: grid; width: min(100%, 540px); justify-self: center; padding: 0; overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); font-family: inherit; text-align: left; }
.event-eyebrow { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-2) var(--space-3); border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); background: var(--paper); }
.event-eyebrow > span { display: inline-flex; align-items: center; gap: 6px; color: var(--brand); font-size: 11px; font-weight: 800; letter-spacing: .08em; }
.event-eyebrow time { color: var(--ink-secondary); font-size: 11px; font-variant-numeric: tabular-nums; }
.event-title { padding: var(--space-3) var(--space-3) 0; font-family: var(--font-serif); font-size: var(--text-base); line-height: 1.45; }
.event-status { display: flex; align-items: center; gap: 6px; padding: 6px var(--space-3) var(--space-3); }
.event-status .status-dot { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; background: var(--ink-tertiary); }
.event-status small { color: var(--ink-secondary); font-size: var(--text-xs); }
.event-status strong { font-size: var(--text-xs); font-weight: 800; }
.tone-brand .status-dot { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); }
.tone-brand .event-status strong { color: var(--brand); }
.tone-warning .status-dot { background: var(--warning); }
.tone-warning .event-status strong { color: var(--warning); }
.tone-danger .status-dot { background: var(--danger); }
.tone-danger .event-status strong { color: var(--danger); }
.event-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); }
.event-facts > span { display: grid; min-height: 56px; align-content: center; gap: 3px; padding: var(--space-2) var(--space-3); }
.event-facts > span:nth-child(odd) { border-right: 1px solid var(--neu-light); box-shadow: 1px 0 0 var(--neu-shade-soft); }
.event-facts > span:nth-child(-n + 2) { border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); }
.event-facts small { color: var(--ink-secondary); font-size: 11px; }
.event-facts strong { overflow: hidden; font-size: var(--text-xs); font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }
.event-note { display: grid; gap: 3px; padding: var(--space-3); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); color: var(--ink); font-size: var(--text-xs); line-height: 1.65; word-break: break-word; }
.event-note small { color: var(--ink-secondary); font-size: 11px; font-weight: 800; }
.event-footer { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); min-height: 44px; padding: var(--space-2) var(--space-3); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); background: var(--paper); color: var(--ink-secondary); font-size: var(--text-xs); }
.event-cta { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 2px; color: var(--brand); font-weight: 800; }

.composer-footer { background: var(--paper); }
.composer-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-2) var(--space-3) calc(var(--space-2) + env(safe-area-inset-bottom)); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); background: var(--paper); }
.intro-card { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); padding: var(--space-2) var(--space-3); border-radius: var(--radius-sm); background: var(--brand-soft); }
.intro-card > span { display: grid; min-width: 0; gap: 2px; }
.intro-card small { color: var(--brand); font-size: 10px; font-weight: 750; }
.intro-card strong { overflow: hidden; font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.intro-remove { display: grid; width: 40px; height: 40px; flex: 0 0 auto; place-items: center; border: 0; border-radius: var(--radius-sm); background: transparent; color: var(--ink-secondary); }
.composer { display: grid; grid-template-columns: minmax(0, 1fr) 48px; align-items: end; gap: var(--space-2); }
.composer textarea { width: 100%; min-height: 48px; max-height: 112px; padding: 12px; resize: vertical; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); line-height: 1.45; outline: none; }
.composer textarea:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }
.send-button { display: grid; width: 48px; height: 48px; place-items: center; border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.send-button:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); opacity: .75; }
.send-button ion-spinner { width: 20px; height: 20px; }

@media (min-width: 680px) {
  .message-stack { max-width: 70%; }
}
</style>
