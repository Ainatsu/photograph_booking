<template>
  <ion-page>
    <DetailHeader title="通知中心" default-href="/tabs/messages">
      <template #action>
        <button
          type="button"
          class="header-action pressable"
          :disabled="notifications.unreadCount === 0 || markingAll"
          aria-label="全部标记为已读"
          @click="markAllRead"
        >
          <ion-spinner v-if="markingAll" name="crescent" aria-hidden="true" />
          <CheckCheck v-else :size="21" aria-hidden="true" />
        </button>
      </template>
    </DetailHeader>

    <ion-content class="notification-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新通知" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="notification-shell">
        <section class="notification-intro">
          <span class="intro-icon"><BellRing :size="25" aria-hidden="true" /></span>
          <div>
            <p>Notification center</p>
            <h1>订单与企划的重要进展</h1>
            <small>确认、付款、交付、争议和应邀结果会实时同步到这里。</small>
          </div>
          <span class="unread-stat" aria-live="polite">
            <strong>{{ notifications.unreadCount }}</strong>
            <small>待查看</small>
          </span>
        </section>

        <SegmentSwitch v-model="activeFilter" :items="segments" label="通知状态筛选" />

        <div class="list-heading">
          <div>
            <h2>{{ activeFilter === 'unread' ? '未读通知' : '全部通知' }}</h2>
            <p>{{ listSummary }}</p>
          </div>
          <button
            v-if="notifications.unreadCount"
            type="button"
            class="read-all-copy pressable"
            :disabled="markingAll"
            @click="markAllRead"
          >
            全部已读
          </button>
        </div>

        <section v-if="initialLoading" class="notification-skeleton-list" aria-label="正在加载通知" aria-busy="true">
          <article v-for="index in 5" :key="index" class="notification-skeleton">
            <span class="skeleton icon-skeleton" />
            <span class="skeleton-copy">
              <i class="skeleton line short" />
              <i class="skeleton line wide" />
              <i class="skeleton line medium" />
            </span>
          </article>
        </section>

        <StatePanel
          v-else-if="error && !notifications.items.length"
          tone="error"
          title="通知暂时无法加载"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <StatePanel
          v-else-if="!visibleNotifications.length"
          :title="activeFilter === 'unread' ? '通知都已读完' : '暂时没有通知'"
          :description="activeFilter === 'unread'
            ? '新的订单、企划与交付提醒到达后，会自动出现在这里。'
            : '完成预约或发布企划后，重要业务进展会保留在这里。'"
          :action-label="activeFilter === 'unread' ? '查看全部' : '查看我的订单'"
          @action="handleEmptyAction"
        />

        <section v-else class="notification-list" aria-live="polite" aria-label="通知列表">
          <button
            v-for="item in visibleNotifications"
            :key="item.id"
            type="button"
            class="notification-card pressable"
            :class="[{ unread: !item.is_read }, getNotificationCategory(item.notification_type)]"
            :disabled="openingId !== null"
            :aria-label="notificationAriaLabel(item)"
            @click="openNotification(item)"
          >
            <span class="notification-icon" aria-hidden="true">
              <BriefcaseBusiness v-if="getNotificationCategory(item.notification_type) === 'project'" :size="21" />
              <WalletCards v-else-if="getNotificationCategory(item.notification_type) === 'payment'" :size="21" />
              <Images v-else-if="getNotificationCategory(item.notification_type) === 'delivery'" :size="21" />
              <ShieldAlert v-else-if="getNotificationCategory(item.notification_type) === 'safety'" :size="21" />
              <CalendarCheck2 v-else :size="21" />
            </span>

            <span class="notification-copy">
              <span class="notification-meta">
                <span class="category-label">{{ getNotificationCategoryLabel(item.notification_type) }}</span>
                <span v-if="!item.is_read" class="unread-label"><i aria-hidden="true" />未读</span>
                <time :datetime="item.created_at">{{ formatNotificationTime(item.created_at) }}</time>
              </span>
              <strong>{{ item.title }}</strong>
              <span class="notification-content-copy">{{ item.content }}</span>
            </span>

            <span class="notification-action" aria-hidden="true">
              <ion-spinner v-if="openingId === item.id" name="crescent" />
              <ChevronRight v-else-if="getNotificationTarget(item)" :size="20" />
              <Check v-else :size="19" />
            </span>
          </button>
        </section>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2800"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  onIonViewWillEnter,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  BellRing,
  BriefcaseBusiness,
  CalendarCheck2,
  Check,
  CheckCheck,
  ChevronRight,
  Images,
  ShieldAlert,
  WalletCards,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { useNotificationStore } from '@/stores/notifications'
import type { NotificationRecord } from '@/types/notifications'
import {
  formatNotificationTime,
  getNotificationCategory,
  getNotificationCategoryLabel,
  getNotificationTarget,
} from '@/utils/notification'

type NotificationFilter = 'all' | 'unread'

const router = useRouter()
const notifications = useNotificationStore()
const activeFilter = ref<NotificationFilter>('all')
const error = ref('')
const toastMessage = ref('')
const markingAll = ref(false)
const openingId = ref<number | null>(null)

const initialLoading = computed(() => notifications.loading && !notifications.loaded)
const visibleNotifications = computed(() => activeFilter.value === 'unread'
  ? notifications.items.filter((item) => !item.is_read)
  : notifications.items)
const segments = computed(() => [
  { label: '全部', value: 'all', count: notifications.items.length },
  { label: '未读', value: 'unread', count: notifications.unreadCount },
])
const listSummary = computed(() => {
  if (activeFilter.value === 'unread') {
    return notifications.unreadCount ? `${notifications.unreadCount} 条提醒等待处理` : '没有待处理提醒'
  }
  return notifications.items.length ? `最近 ${notifications.items.length} 条业务提醒` : '业务提醒会按时间倒序排列'
})

async function load() {
  error.value = ''
  try {
    await notifications.refresh()
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
    if (notifications.items.length) toastMessage.value = `刷新失败：${error.value}`
  }
}

async function refresh(event: RefresherCustomEvent) {
  await load()
  event.target.complete()
}

async function markAllRead() {
  if (!notifications.unreadCount || markingAll.value) return
  markingAll.value = true
  try {
    await notifications.markAllRead()
    toastMessage.value = '全部通知已标记为已读'
  } catch (markError) {
    toastMessage.value = getApiErrorMessage(markError)
  } finally {
    markingAll.value = false
  }
}

async function openNotification(item: NotificationRecord) {
  if (openingId.value !== null) return
  openingId.value = item.id
  try {
    if (!item.is_read) {
      try {
        await notifications.markRead(item.id)
      } catch (markError) {
        toastMessage.value = `已打开详情，但未读状态更新失败：${getApiErrorMessage(markError)}`
      }
    }

    const target = getNotificationTarget(item)
    if (target) await router.push(target)
    else toastMessage.value = item.is_read ? '这条通知没有关联详情' : '通知已标记为已读'
  } finally {
    openingId.value = null
  }
}

function handleEmptyAction() {
  if (activeFilter.value === 'unread') activeFilter.value = 'all'
  else void router.push({ name: 'orders' })
}

function notificationAriaLabel(item: NotificationRecord): string {
  const state = item.is_read ? '已读' : '未读'
  const action = getNotificationTarget(item) ? '，点击查看详情' : '，点击标记已读'
  return `${state}通知：${item.title}。${item.content}${action}`
}

onIonViewWillEnter(() => {
  void load()
})
</script>

<style scoped>
.notification-content { --background: var(--paper); }
.notification-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.header-action { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--brand); }
.header-action:disabled { color: var(--ink-tertiary); opacity: .42; }
.header-action ion-spinner { width: 20px; height: 20px; }

.notification-intro { display: grid; grid-template-columns: 48px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.intro-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: var(--radius-md); background: var(--brand-soft); color: var(--brand); }
.notification-intro p { margin: 0 0 3px; color: var(--brand); font-size: var(--text-2xs); font-weight: 750; letter-spacing: .13em; text-transform: uppercase; }
.notification-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); line-height: 1.35; }
.notification-intro div small { display: block; margin-top: 5px; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.55; }
.unread-stat { display: grid; min-width: 54px; justify-items: center; gap: 1px; padding-left: var(--space-3); border-left: 1px solid var(--divider); }
.unread-stat strong { color: var(--brand); font-size: var(--text-xl); font-variant-numeric: tabular-nums; line-height: 1; }
.unread-stat small { color: var(--ink-tertiary); font-size: var(--text-2xs); }

.list-heading { display: flex; min-height: 64px; align-items: end; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-3); }
.list-heading h2 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.list-heading p { margin: 4px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); }
.read-all-copy { min-height: var(--touch-target); padding: 0 var(--space-2); border: 0; background: transparent; color: var(--brand); font-size: var(--text-xs); font-weight: 750; }
.read-all-copy:disabled { opacity: .45; }

.notification-list, .notification-skeleton-list { display: grid; gap: var(--space-3); }
.notification-card { display: grid; grid-template-columns: 44px minmax(0, 1fr) 28px; width: 100%; min-height: 108px; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); text-align: left; }
.notification-card.unread { border-left: 4px solid var(--brand); background: var(--brand-soft); }
.notification-card:disabled { opacity: .72; }
.notification-icon { display: grid; width: 44px; height: 44px; place-items: center; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); }
.payment .notification-icon { background: var(--warning-soft); color: var(--warning); }
.safety .notification-icon { background: var(--danger-soft); color: var(--danger); }
.delivery .notification-icon { background: var(--brand-soft); }
.unread .notification-icon { background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }

.notification-copy { display: grid; min-width: 0; gap: 6px; }
.notification-meta { display: flex; min-width: 0; align-items: center; gap: 7px; color: var(--ink-tertiary); font-size: var(--text-2xs); }
.notification-meta time { margin-left: auto; white-space: nowrap; }
.category-label { color: var(--brand); font-weight: 750; }
.unread-label { display: inline-flex; align-items: center; gap: 4px; color: var(--brand); font-weight: 750; }
.unread-label i { width: 6px; height: 6px; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); }
.notification-copy > strong { font-size: var(--text-sm); line-height: 1.45; }
.notification-content-copy { color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; overflow-wrap: anywhere; }
.notification-action { display: grid; width: 28px; height: 44px; place-items: center; color: var(--ink-tertiary); }
.notification-action ion-spinner { width: 19px; height: 19px; color: var(--brand); }

.notification-skeleton { display: grid; grid-template-columns: 44px minmax(0, 1fr); min-height: 108px; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.skeleton { display: block; background: var(--paper-deep); animation: notification-pulse 1.2s ease-in-out infinite alternate; }
.icon-skeleton { width: 44px; height: 44px; border-radius: var(--radius-md); }
.skeleton-copy { display: grid; gap: 9px; }
.line { height: 11px; border-radius: var(--radius-pill); }
.line.short { width: 34%; }
.line.medium { width: 68%; }
.line.wide { width: 88%; }

@keyframes notification-pulse { from { opacity: .58; } to { opacity: 1; } }

@media (max-width: 420px) {
  .notification-intro { grid-template-columns: 48px minmax(0, 1fr); }
  .unread-stat { grid-column: 1 / -1; grid-template-columns: auto auto; min-height: 42px; align-items: center; justify-content: center; gap: 6px; padding: var(--space-2) 0 0; border-top: 1px solid var(--divider); border-left: 0; }
  .unread-stat strong { font-size: var(--text-lg); }
  .notification-meta { flex-wrap: wrap; }
  .notification-meta time { width: 100%; margin-left: 0; }
}
</style>
