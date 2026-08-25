<template>
  <ion-app>
    <ion-router-outlet />
  </ion-app>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { IonApp, IonRouterOutlet } from '@ionic/vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useMessageStore } from '@/stores/messages'
import { useNotificationStore } from '@/stores/notifications'
import { trackPageView } from '@/utils/analytics'

const router = useRouter()
const auth = useAuthStore()
const messages = useMessageStore()
const notifications = useNotificationStore()

void auth.initialize()

watch(
  () => auth.token,
  (token) => {
    if (token) {
      messages.connect(token)
      void notifications.refreshUnread().catch(() => undefined)
    } else {
      messages.disconnect()
      notifications.reset()
    }
  },
  { immediate: true },
)

router.afterEach((to) => {
  const pageName = (to.name as string) || String(to.path)
  trackPageView(pageName)
})
</script>
