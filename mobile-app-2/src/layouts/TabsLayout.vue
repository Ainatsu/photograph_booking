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

        <!-- 第三个不是页面而是动作面板；用 button 语义，不伪装成可导航的 Tab -->
        <ion-tab-button
          class="publish-tab"
          aria-label="发布"
          @click="openPublishSheet"
          @keydown.enter="openPublishSheet"
        >
          <span class="publish-orb" aria-hidden="true">
            <Plus :size="22" :stroke-width="2.4" />
          </span>
        </ion-tab-button>

        <ion-tab-button
          tab="messages"
          href="/tabs/messages"
          :aria-label="unreadCount ? `消息，共 ${unreadCount} 条未读内容` : '消息'"
        >
          <span class="tab-icon-wrap">
            <MessageCircle :size="22" aria-hidden="true" />
            <ion-badge v-if="unreadCount" class="message-badge">
              {{ unreadCount > 99 ? '99+' : unreadCount }}
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
import { ref } from 'vue'
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

const showPublishSheet = ref(false)

/** TODO(负责人): 未读角标接消息 store 后改为读真实计数，见 PAGES.md §9 第 8 步。 */
const unreadCount = ref(0)

function openPublishSheet() {
  showPublishSheet.value = true
}
</script>

<style scoped>
/* 底部 Tab 栏用材料浮在内容之上，恰好五个入口，见 DESIGN.md §7 与 PAGES.md §3 */
.app-tab-bar {
  --background: var(--material-regular);
  --border: 0;
  height: calc(var(--bottom-nav-height) + env(safe-area-inset-bottom));
  padding-bottom: env(safe-area-inset-bottom);
  border-top: 1px solid var(--border);
}

ion-tab-button {
  --color: var(--ink-secondary);
  --color-selected: var(--brand);
  min-height: var(--touch-target);
  font-size: var(--text-xs);
}

.publish-orb {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: var(--radius-pill);
  background: var(--brand);
  color: var(--on-brand);
}

.tab-icon-wrap {
  position: relative;
  display: grid;
  place-items: center;
}

.message-badge {
  --background: var(--danger);
  position: absolute;
  top: -6px;
  left: 12px;
  min-width: 18px;
  padding: 0 5px;
  border-radius: var(--radius-pill);
  font-size: var(--text-2xs);
  font-variant-numeric: tabular-nums;
}
</style>
