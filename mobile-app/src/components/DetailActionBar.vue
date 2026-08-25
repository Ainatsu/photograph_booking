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
.action-footer { background: var(--paper); }

.action-bar {
  display: grid;
  grid-template-columns: minmax(112px, 0.72fr) minmax(0, 1.28fr);
  gap: var(--space-3);
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom));
  border-top: 1px solid var(--neu-light);
  box-shadow: inset 0 1px 0 var(--neu-shade-soft);
  background: var(--paper);
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
  border-radius: var(--radius-md);
  font-weight: 700;
}

.secondary-button {
  border: 0;
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--brand);
}

.primary-button {
  border: 0;
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
}

.primary-button:active { background: var(--neu-surface-brand); box-shadow: var(--neu-inset-brand); }

.primary-button:disabled,
.secondary-button:disabled {
  background: var(--paper-deep);
  box-shadow: none;
  color: var(--ink-tertiary);
  opacity: .75;
}

.primary-button ion-spinner,
.secondary-button ion-spinner {
  width: 20px;
  height: 20px;
}
</style>
