<template>
  <div class="segment" :class="{ dense }" role="tablist" :aria-label="label">
    <button
      v-for="item in items"
      :key="item.value"
      type="button"
      role="tab"
      class="segment-button pressable"
      :class="{ active: item.value === modelValue }"
      :aria-selected="item.value === modelValue"
      @click="$emit('update:modelValue', item.value)"
    >
      {{ item.label }}
      <span v-if="item.count !== undefined" class="count">{{ item.count }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
export interface SegmentItem {
  label: string
  value: string
  count?: number
}

withDefaults(
  defineProps<{
    modelValue: string
    items: SegmentItem[]
    label?: string
    /** 顶栏内使用的紧凑高度 */
    dense?: boolean
  }>(),
  { label: '内容分类', dense: false },
)

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped>
/* 容器凹陷成槽，选中项凸起成键帽 */
.segment {
  display: grid;
  grid-auto-columns: 1fr;
  grid-auto-flow: column;
  gap: var(--space-1);
  padding: var(--space-1);
  border: 0;
  border-radius: 9px;
  background: var(--surface-tertiary);
  box-shadow: none;
}

.segment-button {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  font-weight: 550;
  transition: background var(--motion-fast) ease-out, color var(--motion-fast) ease-out, transform var(--motion-normal) var(--spring-ui);
}

.segment.dense {
  padding: 3px;
}

.segment.dense .segment-button {
  min-height: 44px;
  padding: 0 var(--space-2);
}

.segment-button.active {
  background: var(--surface-solid);
  color: var(--ink);
  box-shadow: var(--shadow-1);
}

.count {
  min-width: 18px;
  padding: 1px 5px;
  border-radius: var(--radius-pill);
  background: var(--surface-secondary);
  box-shadow: none;
  color: var(--ink-tertiary);
  font-size: var(--text-2xs);
  font-variant-numeric: tabular-nums;
}

.active .count {
  background: var(--brand-soft);
  color: var(--brand);
}
</style>
