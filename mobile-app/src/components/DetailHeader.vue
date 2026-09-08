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
  --background: var(--d-material);
  --border-color: var(--d-divider);
  --color: var(--d-ink);
  border-bottom: 0.5px solid var(--d-divider);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

ion-title {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.2px;
}

ion-back-button {
  --color: var(--d-ink);
  --icon-font-size: 23px;
  min-width: var(--touch-target);
  min-height: var(--touch-target);
}
</style>
