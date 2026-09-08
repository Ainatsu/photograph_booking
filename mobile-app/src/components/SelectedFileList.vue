<template>
  <ul v-if="files.length" class="selected-file-list" aria-label="已选择的文件">
    <li v-for="(file, index) in files" :key="`${file.name}-${file.size}-${index}`">
      <span class="file-icon" aria-hidden="true">
        <FileText :size="20" />
      </span>
      <span class="file-copy">
        <strong>{{ file.name }}</strong>
        <small>{{ formatFileSize(file.size) }}</small>
      </span>
      <button
        type="button"
        class="remove-button pressable"
        :aria-label="`移除 ${file.name}`"
        @click="emit('remove', index)"
      >
        <X :size="19" aria-hidden="true" />
      </button>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { FileText, X } from 'lucide-vue-next'

defineProps<{
  files: File[]
}>()

const emit = defineEmits<{
  remove: [index: number]
}>()

function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB']
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** unitIndex
  return `${value >= 10 || unitIndex === 0 ? Math.round(value) : value.toFixed(1)} ${units[unitIndex]}`
}
</script>

<style scoped>
.selected-file-list {
  display: grid;
  gap: var(--space-2);
  margin: var(--space-2) 0 0;
  padding: 0;
  list-style: none;
}

.selected-file-list li {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 48px;
  min-height: 58px;
  align-items: center;
  gap: var(--space-2);
  padding: 5px;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.file-icon {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--brand-soft);
  color: var(--brand);
}

.file-copy {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.file-copy strong {
  overflow: hidden;
  color: var(--ink);
  font-size: var(--text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-copy small {
  color: var(--ink-tertiary);
  font-size: var(--text-2xs);
}

.remove-button {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--danger);
}

.remove-button:focus-visible {
  outline: 3px solid var(--focus-ring);
  outline-offset: 1px;
}
</style>
