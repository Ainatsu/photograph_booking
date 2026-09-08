<template>
  <ion-page>
    <ion-tabs>
      <ion-router-outlet />

      <ion-tab-bar slot="bottom" class="app-tab-bar">
        <ion-tab-button tab="discover" href="/tabs/discover">
          <Compass :size="22" aria-hidden="true" />
          <ion-label>发现</ion-label>
        </ion-tab-button>

        <ion-tab-button tab="showcase" href="/tabs/showcase">
          <Store :size="22" aria-hidden="true" />
          <ion-label>橱窗</ion-label>
        </ion-tab-button>

        <ion-tab-button class="publish-tab" aria-label="发布" @click="openPublishSheet" @keydown.enter="openPublishSheet">
          <span class="publish-orb" aria-hidden="true">
            <Plus :size="22" :stroke-width="2.4" />
          </span>
        </ion-tab-button>

        <ion-tab-button
          tab="messages"
          href="/tabs/messages"
          :aria-label="inboxUnreadCount ? `消息，共 ${inboxUnreadCount} 条未读内容` : '消息'"
        >
          <span class="tab-icon-wrap">
            <MessageCircle :size="22" aria-hidden="true" />
            <ion-badge v-if="inboxUnreadCount" class="message-badge">
              {{ inboxUnreadCount > 99 ? '99+' : inboxUnreadCount }}
            </ion-badge>
          </span>
          <ion-label>消息</ion-label>
        </ion-tab-button>

        <ion-tab-button tab="profile" href="/tabs/profile">
          <UserRound :size="22" aria-hidden="true" />
          <ion-label>我的</ion-label>
        </ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>

    <PublishActionSheet v-model="showPublishSheet" />
  </ion-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  IonBadge,
  IonLabel,
  IonPage,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
} from '@ionic/vue'
import { Compass, MessageCircle, Plus, Store, UserRound } from 'lucide-vue-next'
import PublishActionSheet from '@/components/PublishActionSheet.vue'
import { useMessageStore } from '@/stores/messages'
import { useNotificationStore } from '@/stores/notifications'
import { tapHaptic } from '@/utils/haptics'

const messages = useMessageStore()
const notifications = useNotificationStore()
const inboxUnreadCount = computed(() => messages.unreadCount + notifications.unreadCount)
const showPublishSheet = ref(false)

function openPublishSheet() {
  tapHaptic()
  showPublishSheet.value = true
}
</script>

<style scoped>
.app-tab-bar {
  contain: none;
  position: absolute;
  right: var(--space-3);
  bottom: max(var(--bottom-nav-offset), env(safe-area-inset-bottom));
  left: var(--space-3);
  width: auto;
  height: var(--bottom-nav-height);
  padding: var(--space-1);
  overflow: visible;
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  background: var(--material-thick);
  box-shadow: var(--shadow-2);
  backdrop-filter: var(--material-blur);
  -webkit-backdrop-filter: var(--material-blur);
}

ion-tab-button {
  --color: var(--ink-tertiary);
  --color-selected: var(--brand);
  --padding-bottom: 4px;
  --padding-top: 4px;
  --background-focused: transparent;
  --border-radius: calc(var(--radius-xl) - var(--space-1));
  min-width: 0;
  font-size: var(--text-2xs);
  letter-spacing: 0;
}

ion-tab-button::part(native) {
  overflow: visible;
}

ion-tab-button ion-label {
  margin-top: 3px;
  font-weight: 500;
}

ion-tab-button.tab-selected ion-label { font-weight: 650; }

.publish-tab {
  --color: var(--brand);
  --color-selected: var(--brand-strong);
  overflow: visible;
}

.publish-tab::part(native) {
  justify-content: center;
}

.publish-orb {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: var(--brand);
  color: var(--white);
  box-shadow: var(--glow-brand);
  transition: filter var(--motion-fast) ease-out, transform var(--motion-normal) var(--spring-ui);
}

.publish-tab:active .publish-orb {
  filter: brightness(0.92);
  transform: scale(0.92);
}

.tab-icon-wrap {
  position: relative;
  display: grid;
  place-items: center;
}

.message-badge {
  position: absolute;
  top: -8px;
  left: 14px;
  min-width: 19px;
  height: 19px;
  padding: 0 4px;
  --background: var(--danger);
  --color: var(--white);
  border: 2px solid var(--material-thick);
  border-radius: var(--radius-pill);
  font-size: 9px;
  font-weight: 800;
  line-height: 15px;
}

@media (prefers-reduced-transparency: reduce) {
  .app-tab-bar { backdrop-filter: none; -webkit-backdrop-filter: none; }
}

@media (min-width: 768px) {
  .app-tab-bar {
    right: auto;
    left: 50%;
    width: min(620px, calc(100% - var(--space-12)));
    transform: translateX(-50%);
  }
}
</style>
