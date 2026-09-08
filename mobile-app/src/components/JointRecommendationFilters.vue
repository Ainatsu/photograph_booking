<template>
  <form class="filters" @submit.prevent="submit">
    <div class="filters__heading">
      <div><SlidersHorizontal :size="17" aria-hidden="true" /><strong>调整筛选</strong></div>
      <button type="button" class="text-button" @click="expanded = !expanded" :aria-expanded="expanded">{{ expanded ? '收起' : '修改' }}</button>
    </div>
    <div v-if="expanded" class="filters__body">
      <label>排序
        <select v-model="form.sort_mode">
          <option value="best_match">综合</option><option value="nearest">距离</option><option value="lowest_price">价格</option><option value="earliest_available">最早可约</option>
        </select>
      </label>
      <label>预算上限
        <input v-model.number="form.budget_max" type="number" min="0" inputmode="decimal" placeholder="不限" />
      </label>
      <label>最大距离
        <select v-model.number="form.max_distance_km">
          <option :value="undefined">不限</option><option :value="5">5 km</option><option :value="10">10 km</option><option :value="20">20 km</option><option :value="40">40 km</option>
        </select>
      </label>
      <label>风格
        <input v-model="styleText" type="text" placeholder="日系、人像" />
      </label>
      <label class="toggle"><input v-model="form.require_exact_availability" type="checkbox" /><span>只看确定有档期</span></label>
      <button type="submit" class="apply" :disabled="disabled">{{ disabled ? '更新中…' : '应用筛选' }}</button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { SlidersHorizontal } from 'lucide-vue-next'

const props = defineProps<{ slots?: Record<string, any>; disabled?: boolean }>()
const emit = defineEmits<{ apply: [filters: Record<string, any>] }>()
const expanded = ref(false)
const styleText = ref('')
const form = reactive({ sort_mode: 'best_match', budget_max: undefined as number | undefined, max_distance_km: undefined as number | undefined, require_exact_availability: true })

watch(() => props.slots, (slots) => {
  form.sort_mode = slots?.sort_mode || 'best_match'
  form.budget_max = slots?.budget_max
  form.max_distance_km = slots?.max_distance_km
  form.require_exact_availability = slots?.availability_required !== false
  const styles = slots?.styles || slots?.style || []
  styleText.value = Array.isArray(styles) ? styles.join('、') : String(styles || '')
}, { immediate: true })

function submit() {
  const styles = styleText.value.split(/[，,、\s]+/).map((value) => value.trim()).filter(Boolean)
  emit('apply', { ...form, styles })
}
</script>

<style scoped>
.filters { display: grid; gap: var(--space-3); padding: var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.filters__heading, .filters__heading > div { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.filters__heading strong { font-size: var(--text-sm); }
.text-button { min-height: 44px; padding: 0 var(--space-3); border: 0; background: transparent; color: var(--brand); font-weight: 700; }
.filters__body { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--divider); }
label { display: grid; gap: 6px; color: var(--ink-secondary); font-size: var(--text-xs); }
input, select { width: 100%; min-height: 44px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font: inherit; font-size: var(--text-sm); }
input:focus-visible, select:focus-visible, button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.toggle { display: flex; min-height: 44px; grid-column: 1 / -1; align-items: center; gap: var(--space-2); }
.toggle input { width: 20px; min-height: 20px; accent-color: var(--brand); }
.apply { min-height: var(--touch-target); grid-column: 1 / -1; border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font: inherit; font-weight: 750; }
.apply:disabled { opacity: .5; }
@media (max-width: 390px) { .filters__body { grid-template-columns: 1fr; } .toggle, .apply { grid-column: 1; } }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>
