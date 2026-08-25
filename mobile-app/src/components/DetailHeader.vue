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
  --border-color: transparent;
  --color: var(--ink);
  backdrop-filter: var(--material-blur);
  -webkit-backdrop-filter: var(--material-blur);
}

ion-title {
  font-size: var(--text-base);
  font-weight: 650;
}

ion-back-button {
  --color: var(--ink);
  --icon-font-size: 23px;
  min-width: var(--touch-target);
  min-height: var(--touch-target);
}
</style>
