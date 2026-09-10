<template>
  <ion-header class="detail-header">
    <ion-toolbar>
      <ion-buttons slot="start">
        <ion-back-button :default-href="defaultHref" text="" aria-label="返回上一页" />
      </ion-buttons>
      <ion-title>{{ title }}</ion-title>
      <ion-buttons v-if="$slots.action" slot="end">
        <slot name="action" />
      </ion-buttons>
    </ion-toolbar>
  </ion-header>
</template>

<script setup lang="ts">
import { IonBackButton, IonButtons, IonHeader, IonTitle, IonToolbar } from '@ionic/vue'

withDefaults(
  defineProps<{
    title: string
    defaultHref?: string
  }>(),
  { defaultHref: '/tabs/discover' },
)
</script>

<style scoped>
.detail-header {
  box-shadow: none;
}

ion-toolbar {
  --min-height: 56px;
  --background: var(--material-regular);
  --border-color: var(--border);
  --color: var(--ink);
  border-bottom: 1px solid var(--border);
}

ion-title {
  /* 导航标题固定 17px / 600，中文不做负字间距，见 DESIGN.md §4 */
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0;
}

ion-back-button {
  --color: var(--ink);
  --icon-font-size: 23px;
  min-width: var(--touch-target);
  min-height: var(--touch-target);
}
</style>
