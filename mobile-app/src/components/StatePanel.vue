<template>
  <section class="state-panel" :class="tone" role="status">
    <div class="state-icon" aria-hidden="true">
      <WifiOff v-if="tone === 'error'" :size="25" />
      <SearchX v-else :size="25" />
    </div>
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
    <button v-if="actionLabel" type="button" class="state-action pressable" @click="$emit('action')">
      <RefreshCw v-if="tone === 'error'" :size="17" aria-hidden="true" />
      {{ actionLabel }}
    </button>
  </section>
</template>

<script setup lang="ts">
import { RefreshCw, SearchX, WifiOff } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    title: string
    description: string
    tone?: 'empty' | 'error'
    actionLabel?: string
  }>(),
  {
    tone: 'empty',
    actionLabel: '',
  },
)

defineEmits<{
  action: []
}>()
</script>

<style scoped>
.state-panel {
  display: grid;
  min-height: 250px;
  place-items: center;
  align-content: center;
  padding: var(--space-8) var(--space-5);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  text-align: center;
}

.state-icon {
  display: grid;
  width: 52px;
  height: 52px;
  margin-bottom: var(--space-3);
  place-items: center;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
}

.error .state-icon {
  background: #f4e6e3;
  color: var(--danger);
}

h2 {
  margin: 0 0 var(--space-2);
  font-family: var(--font-serif);
  font-size: var(--text-lg);
}

p {
  max-width: 280px;
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.65;
}

.state-action {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-5);
  padding: 0 var(--space-5);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
  font-weight: 650;
}

.state-action:active { background: var(--neu-surface-brand); box-shadow: var(--neu-inset-brand); }
</style>
