<template>
  <label class="search-field" :class="{ focused }">
    <span class="sr-only">{{ label }}</span>
    <Search :size="19" aria-hidden="true" />
    <input
      :value="modelValue"
      type="search"
      enterkeyhint="search"
      :placeholder="placeholder"
      :aria-label="label"
      @focus="focused = true"
      @blur="focused = false"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keydown.enter.prevent="$emit('submit', modelValue)"
    />
    <button
      v-if="modelValue"
      type="button"
      class="clear-button"
      aria-label="清空搜索"
      @click="$emit('update:modelValue', '')"
    >
      <X :size="17" aria-hidden="true" />
    </button>
  </label>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search, X } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    label?: string
  }>(),
  {
    placeholder: '搜索作品、摄影师或风格',
    label: '搜索',
  },
)

defineEmits<{
  'update:modelValue': [value: string]
  submit: [value: string]
}>()

const focused = ref(false)
</script>

<style scoped>
.search-field {
  display: flex;
  width: 100%;
  min-height: var(--touch-target);
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  box-shadow: none;
  color: var(--ink-tertiary);
  transition: box-shadow var(--motion-fast) ease;
}

.search-field.focused {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--focus-ring);
}

input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  box-shadow: none;
  color: var(--ink);
  font-size: var(--text-base);
}

input::placeholder {
  color: var(--ink-tertiary);
}

input::-webkit-search-cancel-button {
  display: none;
}

.clear-button {
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  flex: 0 0 auto;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-secondary);
}

.clear-button:active { background: var(--surface-tertiary); }
</style>
