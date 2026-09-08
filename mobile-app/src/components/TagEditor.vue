<template>
  <div class="tag-editor">
    <div v-if="modelValue.length" class="tag-editor-list" aria-label="已添加标签">
      <span v-for="tag in modelValue" :key="tag" class="tag-editor-chip">
        <span>{{ tag }}</span>
        <button
          type="button"
          class="tag-remove pressable"
          :disabled="disabled"
          :aria-label="`移除标签 ${tag}`"
          @click="removeTag(tag)"
        >
          <X :size="16" aria-hidden="true" />
        </button>
      </span>
    </div>
    <div class="tag-input-row">
      <input
        :id="inputId"
        v-model="inputValue"
        type="text"
        class="tag-input"
        :placeholder="placeholder"
        :disabled="disabled || modelValue.length >= maxTags"
        maxlength="60"
        @keydown="handleKeydown"
        @blur="commit"
      />
      <span>{{ modelValue.length }}/{{ maxTags }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { X } from 'lucide-vue-next'
import { normalizeTags } from '@/utils/publishing'

const props = withDefaults(defineProps<{
  modelValue: string[]
  inputId: string
  placeholder?: string
  maxTags?: number
  disabled?: boolean
}>(), {
  placeholder: '输入后按回车添加',
  maxTags: 12,
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  limit: []
}>()

const inputValue = ref('')

function commit() {
  const next = normalizeTags([...props.modelValue, inputValue.value], props.maxTags)
  if (inputValue.value.trim() && next.length === props.modelValue.length) emit('limit')
  emit('update:modelValue', next)
  inputValue.value = ''
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',' || event.key === '，') {
    event.preventDefault()
    commit()
  }
}

function removeTag(tag: string) {
  emit('update:modelValue', props.modelValue.filter((item) => item !== tag))
}
</script>

<style scoped>
.tag-editor { display: grid; gap: var(--space-2); }
.tag-editor-list { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.tag-editor-chip { display: inline-flex; min-height: var(--touch-target); align-items: center; gap: 2px; padding-left: 12px; border: 0; border-radius: var(--radius-pill); background: var(--brand-soft); box-shadow: var(--neu-raise-sm); color: var(--ink); font-size: var(--text-xs); font-weight: 700; }
.tag-remove { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--brand); }
.tag-input-row { position: relative; }
.tag-input { width: 100%; min-height: var(--touch-target); padding: 0 62px 0 var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); outline: none; }
.tag-input:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px var(--focus-ring); }
.tag-input:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }
.tag-input-row > span { position: absolute; top: 50%; right: var(--space-3); color: var(--ink-tertiary); font-size: var(--text-2xs); transform: translateY(-50%); }
</style>
