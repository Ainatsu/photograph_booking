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
      <span class="label">{{ item.label }}</span>
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
    /** 顶栏内使用的紧凑间距 */
    dense?: boolean
  }>(),
  { label: '内容分类', dense: false },
)

defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<style scoped>
/* 参考图里的分段导航是「文字 + 选中项蓝色下划线」，不用滑块底色。 */
.segment {
  display: flex;
  align-items: stretch;
  gap: var(--space-5);
  overflow-x: auto;
  scrollbar-width: none;
}

.segment::-webkit-scrollbar {
  display: none;
}

.segment.dense {
  gap: var(--space-4);
}

.segment-button {
  position: relative;
  display: inline-flex;
  min-height: var(--touch-target);
  flex: 0 0 auto;
  align-items: center;
  gap: 5px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ink-secondary);
  font-size: var(--text-base);
  font-weight: 600;
  white-space: nowrap;
}

.segment.dense .segment-button {
  font-size: var(--text-sm);
}

/* 选中：字重与颜色同时变化，颜色不是唯一信号 */
.segment-button.active {
  color: var(--ink);
  font-weight: 800;
}

.segment-button.active::after {
  content: '';
  position: absolute;
  bottom: 6px;
  left: 50%;
  width: 20px;
  height: 3px;
  border-radius: var(--radius-pill);
  background: var(--brand);
  transform: translateX(-50%);
}

.count {
  min-width: 18px;
  padding: 1px 5px;
  border-radius: var(--radius-pill);
  background: var(--surface-secondary);
  color: var(--ink-secondary);
  font-size: var(--text-2xs);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.segment-button.active .count {
  background: var(--brand-soft);
  color: var(--brand);
}
</style>
