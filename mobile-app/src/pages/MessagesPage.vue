<template>
  <ion-page>
    <ion-content class="page-content" :fullscreen="true">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新消息" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="page-shell messages-shell">

        <div class="message-shortcuts">
          <button type="button" class="shortcut pressable" @click="router.push({ name: 'notifications' })">
            <span>
              <BellRing :size="21" aria-hidden="true" />
              <em v-if="notifications.unreadCount" class="shortcut-badge" :aria-label="`${notifications.unreadCount} 条未读通知`">
                {{ notifications.unreadCount > 99 ? '99+' : notifications.unreadCount }}
              </em>
            </span>
            <strong>通知中心</strong>
            <small>订单、企划与平台提醒</small>
          </button>
          <button type="button" class="shortcut pressable" @click="router.push({ name: 'orders' })">
            <span><ClipboardCheck :size="21" aria-hidden="true" /></span>
            <strong>订单动态</strong>
            <small>付款、档期与交付</small>
          </button>
        </div>

        <div class="section-title-row">
          <div>
            <h2>最近会话</h2>
            <p>{{ unreadSummary }}</p>
          </div>
        </div>

        <FeedSkeleton v-if="loading" :count="4" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="消息暂时无法加载"
          :description="error"
          action-label="重新加载"
          @action="load"
        />
        <StatePanel
          v-else-if="!sortedContacts.length"
          title="还没有会话"
          description="在作品、摄影师、方案或订单详情页发起咨询后，对话会出现在这里。"
          action-label="去发现摄影师"
          @action="router.push({ name: 'discover' })"
        />

        <section v-else class="contact-list" aria-label="最近会话">
          <button
            v-for="contact in sortedContacts"
            :key="contact.id"
            type="button"
            class="contact-card pressable"
            @click="openContact(contact.id)"
          >
            <span class="avatar-wrap">
              <AvatarImage :src="contact.avatar_url" :name="contact.display_name" :size="52" />
              <span v-if="contact.unread_count" class="unread-badge" :aria-label="`${contact.unread_count} 条未读消息`">
                {{ contact.unread_count > 99 ? '99+' : contact.unread_count }}
              </span>
            </span>
            <span class="contact-copy">
              <span class="contact-heading">
                <strong>{{ contact.display_name }}</strong>
                <small>{{ contact.role === 'photographer' ? '摄影师' : '客户' }}</small>
              </span>
              <span>{{ contactLastMessage(contact) }}</span>
            </span>
            <ChevronRight :size="20" aria-hidden="true" />
          </button>
        </section>

        <section class="safety-note">
          <ShieldCheck :size="20" aria-hidden="true" />
          <div>
            <strong>建议保留站内沟通</strong>
            <p>重要需求、价格、改期与交付约定应留在订单和会话内，方便双方核对和平台处理争议。</p>
          </div>
        </section>
      </main>

    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  BellRing,
  ChevronRight,
  ClipboardCheck,
  RefreshCw,
  ShieldCheck,
} from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import type { MessageContact } from '@/types/messages'
import { useAuthStore } from '@/stores/auth'
import { useMessageStore } from '@/stores/messages'
import { useNotificationStore } from '@/stores/notifications'
import { getChatEventTitle } from '@/utils/message'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const messages = useMessageStore()
const notifications = useNotificationStore()
const loading = ref(true)
const error = ref('')

const sortedContacts = computed(() => [...messages.contacts].sort((left, right) => (
  Number(right.unread_count || 0) - Number(left.unread_count || 0)
  || left.display_name.localeCompare(right.display_name, 'zh-CN')
)))
const unreadSummary = computed(() => messages.unreadCount
  ? `${messages.unreadCount} 条消息或订单动态待查看`
  : '咨询、订单状态和交付沟通集中在这里')

function contactLastMessage(contact: MessageContact): string {
  if (!contact.last_message) return '查看会话与订单沟通记录'
  if (contact.last_message.type === 'order_event') {
    return getChatEventTitle(contact.last_message.event_type)
  }
  return contact.last_message.content || '查看会话与订单沟通记录'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await auth.initialize()
    await Promise.all([messages.refreshContacts(), messages.refreshUnread()])
    await notifications.refreshUnread().catch(() => undefined)
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  event.target.complete()
}

function openContact(userId: number) {
  router.push({ name: 'conversation', params: { userId } })
}

function forwardConversationQuery() {
  const userId = Number(route.query.to || 0)
  if (!Number.isInteger(userId) || userId <= 0) return false
  const query = Object.fromEntries(Object.entries(route.query).filter(([key]) => key !== 'to'))
  void router.replace({ name: 'conversation', params: { userId }, query })
  return true
}

onMounted(async () => {
  if (forwardConversationQuery()) return
  await load()
})
</script>

<style scoped>
.messages-shell { padding-top: max(var(--space-4), env(safe-area-inset-top)); }
.message-shortcuts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.shortcut { display: grid; min-height: 132px; align-content: center; justify-items: start; gap: 6px; padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); text-align: left; }
.shortcut > span { position: relative; display: grid; width: 42px; height: 42px; margin-bottom: var(--space-2); place-items: center; border-radius: var(--radius-md); background: var(--brand-soft); color: var(--brand); }
.shortcut-badge { position: absolute; top: -7px; right: -9px; display: grid; min-width: 22px; height: 22px; place-items: center; padding: 0 5px; border: 2px solid var(--paper); border-radius: var(--radius-pill); background: var(--danger); color: var(--white); font-size: var(--text-2xs); font-style: normal; font-weight: 800; font-variant-numeric: tabular-nums; }
.shortcut strong { font-size: var(--text-sm); }
.shortcut small { color: var(--ink-tertiary); font-size: var(--text-xs); }

.contact-list { display: grid; gap: var(--space-3); }
.contact-card { display: grid; grid-template-columns: 52px minmax(0, 1fr) 24px; min-height: 78px; align-items: center; gap: var(--space-3); width: 100%; padding: var(--space-3); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); text-align: left; }
.avatar-wrap { position: relative; display: block; width: 52px; height: 52px; }
.unread-badge { position: absolute; top: -6px; right: -7px; display: grid; min-width: 22px; height: 22px; place-items: center; padding: 0 5px; border: 2px solid var(--paper); border-radius: var(--radius-pill); background: var(--danger); color: var(--white); font-size: var(--text-2xs); font-weight: 800; font-variant-numeric: tabular-nums; }
.contact-copy { display: grid; min-width: 0; gap: 6px; }
.contact-heading { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.contact-heading strong { overflow: hidden; font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.contact-heading small { flex: 0 0 auto; color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.contact-copy > span:last-child { overflow: hidden; color: var(--ink-tertiary); font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.contact-card > svg { color: var(--ink-tertiary); }

.safety-note { display: flex; gap: var(--space-3); margin-top: var(--space-5); padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--brand); }
.safety-note strong { display: block; margin-bottom: 4px; color: var(--ink); font-size: var(--text-sm); }
.safety-note p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }

@media (min-width: 768px) {
  .messages-shell { padding-top: max(var(--space-6), env(safe-area-inset-top)); }
}
</style>
