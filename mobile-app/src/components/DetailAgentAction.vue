<template>
  <button
    type="button"
    class="header-action"
    :aria-label="ariaLabel"
    :disabled="disabled"
    @click="$emit('open')"
  >
    <Bot :size="20" aria-hidden="true" />
  </button>
</template>

<script setup lang="ts">
import { Bot } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    ariaLabel?: string
    disabled?: boolean
  }>(),
  { ariaLabel: '询问 Agent', disabled: false },
)

defineEmits<{
  open: []
}>()
</script>

<style scoped>
.header-action {
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  place-items: center;
  border: 0;
  background: transparent;
  color: var(--ink);
}

.header-action:disabled {
  color: var(--ink-tertiary);
  opacity: 0.5;
}
</style>
