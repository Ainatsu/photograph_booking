<template>
  <ion-footer class="action-footer">
    <div class="action-bar" :class="{ 'has-leading': hasLeading }">
      <slot name="leading" />
      <button
        v-if="secondaryLabel"
        type="button"
        class="secondary-button pressable"
        :disabled="secondaryDisabled || secondaryLoading"
        :aria-busy="secondaryLoading"
        @click="$emit('secondary')"
      >
        <ion-spinner v-if="secondaryLoading" name="crescent" aria-hidden="true" />
        <slot v-else name="secondary-icon" />
        {{ secondaryLoading ? '处理中…' : secondaryLabel }}
      </button>
      <button
        type="button"
        class="primary-button pressable"
        :disabled="primaryDisabled || primaryLoading"
        :aria-busy="primaryLoading"
        @click="$emit('primary')"
      >
        <ion-spinner v-if="primaryLoading" name="crescent" aria-hidden="true" />
        <slot v-else name="primary-icon" />
        {{ primaryLoading ? '处理中…' : primaryLabel }}
      </button>
    </div>
  </ion-footer>
</template>

<script setup lang="ts">
import { IonFooter, IonSpinner } from '@ionic/vue'

defineProps<{
  primaryLabel: string
  secondaryLabel?: string
  secondaryDisabled?: boolean
  secondaryLoading?: boolean
  primaryDisabled?: boolean
  primaryLoading?: boolean
  hasLeading?: boolean
}>()

defineEmits<{
  primary: []
  secondary: []
}>()
</script>

<style scoped>
.action-footer {
  background: var(--surface-solid);
}

/* 次要操作在左、主操作在右且更宽 —— 一屏一个主操作（DESIGN.md §1） */
.action-bar {
  display: grid;
  grid-template-columns: minmax(112px, 0.72fr) minmax(0, 1.28fr);
  gap: var(--space-3);
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom));
  border-top: 1px solid var(--border);
  background: var(--surface-solid);
}

.action-bar.has-leading {
  grid-template-columns: auto minmax(112px, 0.72fr) minmax(0, 1.28fr);
}

.action-bar:has(.primary-button:only-child) {
  grid-template-columns: 1fr;
}

button {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border-radius: var(--radius-pill);
  font-weight: 700;
}

.secondary-button {
  border: 1px solid var(--brand);
  background: var(--surface-solid);
  color: var(--brand);
}

.primary-button {
  border: 0;
  background: var(--brand);
  color: var(--on-brand);
}

/* 禁用态：两种按钮都退成灰底，不再保留主次对比 */
.primary-button:disabled,
.secondary-button:disabled {
  border-color: transparent;
  background: var(--surface-secondary);
  color: var(--ink-tertiary);
}

.primary-button ion-spinner,
.secondary-button ion-spinner {
  width: 20px;
  height: 20px;
}
</style>
