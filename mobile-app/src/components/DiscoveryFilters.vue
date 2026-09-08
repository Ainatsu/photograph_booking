<template>
  <section class="filters-card">
    <form
      v-if="isFormVisible"
      id="discovery-filter-form"
      class="filters-form"
      @submit.prevent="handleApply"
    >
      <div class="filter-grid">
        <label>
          <span>城市</span>
          <input
            v-model.trim="city"
            type="search"
            autocomplete="address-level2"
            placeholder="例如：香港、深圳"
          />
        </label>
        <label>
          <span>风格</span>
          <input
            v-model.trim="styleFilter"
            type="search"
            autocomplete="off"
            placeholder="例如：日系、纪实"
          />
        </label>
        <template v-if="showBudget">
          <label>
            <span>最低预算</span>
            <input
              :value="budgetMin ?? ''"
              type="number"
              inputmode="numeric"
              min="0"
              step="100"
              placeholder="不限"
              @input="budgetMin = optionalNumber($event)"
            />
          </label>
          <label>
            <span>最高预算</span>
            <input
              :value="budgetMax ?? ''"
              type="number"
              inputmode="numeric"
              min="0"
              step="100"
              placeholder="不限"
              @input="budgetMax = optionalNumber($event)"
            />
          </label>
        </template>
      </div>

      <p v-if="error" class="filter-error" role="alert">{{ error }}</p>

      <div class="filter-actions">
        <button
          type="button"
          class="secondary-button pressable"
          :disabled="!activeCount"
          @click="handleReset"
        >
          清除条件
        </button>
        <button type="submit" class="primary-button pressable">应用筛选</button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    showBudget?: boolean
    error?: string
    /** 外部控制显隐；不传时使用内部 expanded 状态（兼容旧调用方） */
    visible?: boolean | null
  }>(),
  {
    showBudget: true,
    error: '',
    visible: null,
  },
)

const emit = defineEmits<{
  apply: []
  reset: []
}>()

const city = defineModel<string>('city', { default: '' })
const styleFilter = defineModel<string>('styleFilter', { default: '' })
const budgetMin = defineModel<number | null>('budgetMin', { default: null })
const budgetMax = defineModel<number | null>('budgetMax', { default: null })
const expanded = ref(false)

const isFormVisible = computed(() => {
  // 外部控制优先
  if (props.visible !== null) return props.visible
  return expanded.value
})

const activeCount = computed(() => [
  city.value.trim(),
  styleFilter.value.trim(),
  budgetMin.value,
  budgetMax.value,
].filter((value) => value !== '' && value !== null && value !== undefined).length)

function handleApply() {
  emit('apply')
}

function handleReset() {
  city.value = ''
  styleFilter.value = ''
  budgetMin.value = null
  budgetMax.value = null
  emit('reset')
}

function optionalNumber(event: Event) {
  const value = (event.target as HTMLInputElement).value
  return value === '' ? null : Number(value)
}
</script>

<style scoped>
.filters-card {
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.filters-form {
  padding: var(--space-4);
  border-top: 1px solid var(--divider);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

label {
  display: grid;
  gap: 6px;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  font-weight: 650;
}

input {
  width: 100%;
  min-width: 0;
  min-height: var(--touch-target);
  padding: 0 var(--space-3);
  border: 0;
  border-radius: var(--radius-md);
  outline: 0;
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--ink);
  font-size: var(--text-base);
}

input:focus {
  box-shadow: var(--neu-inset-deep), 0 0 0 2px var(--focus-ring);
}

input::placeholder {
  color: var(--ink-tertiary);
}

.filter-error {
  margin: var(--space-3) 0 0;
  color: var(--danger);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.filter-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.filter-actions button {
  min-height: var(--touch-target);
  border-radius: var(--radius-md);
  font-weight: 700;
}

.secondary-button {
  border: 0;
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--ink-secondary);
}

.secondary-button:disabled {
  opacity: 0.45;
}

.primary-button {
  border: 0;
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
}

@media (max-width: 359px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
