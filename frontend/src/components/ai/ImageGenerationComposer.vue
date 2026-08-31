<template>
  <section class="generation-composer" aria-label="图片创作模式">
    <div class="mode-row" role="group" aria-label="选择对话模式">
      <button type="button" :class="{ active: !modelValue.mode }" :aria-pressed="!modelValue.mode" :disabled="disabled" @click="setMode(null)"><MessageCircle aria-hidden="true" /><span>普通对话</span></button>
      <button type="button" :class="{ active: modelValue.mode === 'text_to_image' }" :aria-pressed="modelValue.mode === 'text_to_image'" :disabled="disabled" @click="setMode('text_to_image')"><WandSparkles aria-hidden="true" /><span>文生图</span></button>
      <button type="button" :class="{ active: modelValue.mode === 'image_to_image' }" :aria-pressed="modelValue.mode === 'image_to_image'" :disabled="disabled" @click="setMode('image_to_image')"><Images aria-hidden="true" /><span>以图生图</span></button>
    </div>

    <div v-if="modelValue.mode" class="mode-detail">
      <div class="mode-summary">
        <span>{{ modelValue.mode === 'image_to_image' ? '上传一张参考图，并描述需要保留和修改的内容' : '描述想要生成的场景、人物、光线和风格' }}</span>
        <button type="button" class="settings-toggle" :aria-expanded="settingsOpen" :disabled="disabled" @click="settingsOpen = !settingsOpen"><Settings2 aria-hidden="true" /><span>生成设置</span><ChevronDown :class="{ rotated: settingsOpen }" aria-hidden="true" /></button>
      </div>

      <div v-if="settingsOpen" class="settings-panel">
        <label><span>宽高比</span><select :value="modelValue.aspect_ratio" :disabled="disabled" @change="update('aspect_ratio', $event.target.value)"><option v-for="ratio in ratios" :key="ratio" :value="ratio">{{ ratio }}</option></select></label>
        <label><span>数量</span><select :value="modelValue.count" :disabled="disabled" @change="update('count', Number($event.target.value))"><option :value="1">1 张</option><option :value="2">2 张</option></select></label>
        <label><span>质量</span><select :value="modelValue.quality" :disabled="disabled" @change="update('quality', $event.target.value)"><option value="standard">标准</option><option value="high">高</option></select></label>
        <label v-if="modelValue.mode === 'image_to_image'" class="strength-field"><span>修改强度 {{ Number(modelValue.strength).toFixed(2) }}</span><input type="range" min="0.1" max="1" step="0.05" :value="modelValue.strength" :disabled="disabled" @input="update('strength', Number($event.target.value))" /></label>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { ChevronDown, Images, MessageCircle, Settings2, WandSparkles } from 'lucide-vue-next'

const props = defineProps({
  modelValue: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'mode-change'])
const settingsOpen = ref(false)
const ratios = ['1:1', '3:4', '4:3', '9:16', '16:9']

function setMode(mode) {
  const nextMode = props.modelValue.mode === mode ? null : mode
  emit('update:modelValue', { ...props.modelValue, mode: nextMode })
  emit('mode-change', nextMode)
  if (!nextMode) settingsOpen.value = false
}

function update(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<style scoped>
.generation-composer { padding: 8px 12px 2px; background: var(--color-paper); }.mode-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }.mode-row button,.settings-toggle { display: inline-flex; min-height: 44px; align-items: center; justify-content: center; gap: 6px; padding: 0 10px; border: var(--border-default); border-radius: var(--radius-sm); background: var(--color-paper-light); color: var(--color-ink-secondary); cursor: pointer; font: inherit; font-size: calc(var(--text-xs) * 1rem); transition: background-color 180ms ease, border-color 180ms ease, color 180ms ease; }.mode-row button svg,.settings-toggle svg { width: 17px; height: 17px; flex: 0 0 auto; }.mode-row button.active { border-color: var(--color-brand); background: var(--color-brand-light); color: var(--color-brand); font-weight: 700; }.mode-row button:focus-visible,.settings-toggle:focus-visible,select:focus-visible,input:focus-visible { outline: 2px solid var(--color-focus-ring); outline-offset: 2px; }.mode-row button:disabled,.settings-toggle:disabled { cursor: not-allowed; opacity: .55; }
.mode-detail { margin-top: 8px; padding: 8px 10px; border: var(--border-default); border-radius: var(--radius-sm); background: var(--color-paper-light); }.mode-summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--color-ink-secondary); font-size: calc(var(--text-xs) * 1rem); line-height: 1.5; }.settings-toggle { min-width: 126px; flex: 0 0 auto; border: 0; background: transparent; color: var(--color-brand); }.settings-toggle svg:last-child { transition: transform 180ms ease; }.settings-toggle svg.rotated { transform: rotate(180deg); }
.settings-panel { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--color-divider); }.settings-panel label { display: grid; gap: 5px; min-width: 0; color: var(--color-ink-tertiary); font-size: calc(var(--text-xs) * 1rem); }.settings-panel select { width: 100%; min-height: 44px; padding: 0 9px; border: var(--border-default); border-radius: var(--radius-sm); background: var(--color-paper); color: var(--color-ink); font: inherit; }.strength-field { grid-column: 1 / -1; }.strength-field input { width: 100%; min-height: 32px; accent-color: var(--color-brand); }
@media (max-width: 520px) { .mode-row { grid-template-columns: 1fr; }.mode-summary { align-items: flex-start; flex-direction: column; }.settings-toggle { justify-content: flex-start; min-width: 0; padding: 0; }.settings-panel { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .mode-row button,.settings-toggle,.settings-toggle svg:last-child { transition: none; } }
</style>
