<template>
  <main class="notifications-page">
    <div class="page-head">
      <div>
        <h2>通知中心</h2>
        <p>企划应邀、订单、交付和售后提醒都会保留在这里。</p>
      </div>
      <el-button :disabled="!notifications.some(item => !item.is_read)" :loading="markingAll" @click="readAll">
        全部标为已读
      </el-button>
    </div>

    <div v-loading="loading" class="notification-list" aria-live="polite">
      <button
        v-for="item in notifications"
        :key="item.id"
        type="button"
        class="notification-card"
        :class="{ unread: !item.is_read }"
        @click="openNotification(item)"
      >
        <span class="state-label">{{ item.is_read ? '已读' : '未读' }}</span>
        <div>
          <strong>{{ item.title }}</strong>
          <p>{{ item.content }}</p>
          <small>{{ formatTime(item.created_at) }}</small>
        </div>
        <span class="action-copy">查看详情</span>
      </button>
      <el-empty v-if="!loading && !notifications.length" description="暂无通知，新的待办提醒会出现在这里" />
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getNotifications, markAllNotificationsRead, markNotificationRead } from '@/api/notification'

const router = useRouter()
const notifications = ref([])
const loading = ref(false)
const markingAll = ref(false)

const fetchNotifications = async () => {
  loading.value = true
  try {
    const { data } = await getNotifications()
    notifications.value = data
  } finally { loading.value = false }
}

const openNotification = async item => {
  if (!item.is_read) {
    await markNotificationRead(item.id)
    item.is_read = true
  }
  if (item.action_url) router.push(item.action_url)
}

const readAll = async () => {
  markingAll.value = true
  try {
    await markAllNotificationsRead()
    notifications.value.forEach(item => { item.is_read = true })
  } finally { markingAll.value = false }
}

const formatTime = value => new Date(value).toLocaleString('zh-CN')
onMounted(fetchNotifications)
</script>

<style scoped>
.notifications-page { max-width: 860px; margin: 0 auto; padding: 28px 16px 48px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
h2 { margin: 0; color: var(--color-ink); }
.page-head p { margin: 6px 0 0; color: var(--color-ink-secondary); }
.notification-list { display: grid; gap: 10px; min-height: 180px; }
.notification-card { width: 100%; min-height: 76px; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 14px; padding: 14px 16px; border: var(--border-default); border-radius: var(--radius-md); background: var(--color-paper-light); color: var(--color-ink); text-align: left; cursor: pointer; }
.notification-card.unread { border-left: 4px solid var(--color-brand); background: var(--color-brand-light); }
.state-label { color: var(--color-ink-tertiary); font-size: var(--text-xs); }
.notification-card strong { font-size: 15px; }
.notification-card p { margin: 5px 0; color: var(--color-ink-secondary); line-height: 1.55; }
.notification-card small { color: var(--color-ink-tertiary); }
.action-copy { color: var(--color-brand); font-weight: 600; white-space: nowrap; }
@media (max-width: 560px) { .page-head { flex-direction: column; } .notification-card { grid-template-columns: 1fr; } .state-label { order: -1; } }
</style>
