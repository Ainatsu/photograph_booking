<template>
  <div class="location-field">
    <button type="button" class="map-preview" aria-haspopup="dialog" :aria-expanded="dialogVisible" @click="dialogVisible = true">
      <LocationMap :latitude="value.latitude" :longitude="value.longitude" aria-label="企划地点地图预览" />
      <span class="location-overlay">
        <MapPin :size="20" aria-hidden="true" />
        <span>
          <strong>{{ value.name || value.text || '点击地图选择拍摄地点' }}</strong>
          <small>{{ value.address || '可搜索地标、点击地图或使用当前位置' }}</small>
        </span>
        <ChevronRight :size="20" aria-hidden="true" />
      </span>
    </button>
    <div class="fallback-row">
      <el-input :model-value="value.text" maxlength="255" placeholder="也可以补充地点说明，例如：海边或室内棚拍" @update:model-value="updateText" />
      <el-button v-if="value.text || value.latitude != null" @click="clearLocation">清除</el-button>
    </div>
    <LocationPickerDialog v-model="dialogVisible" :location="value" :city="city" @confirm="confirmLocation" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ChevronRight, MapPin } from 'lucide-vue-next'
import LocationMap from './LocationMap.vue'
import LocationPickerDialog from './LocationPickerDialog.vue'

const props = defineProps({ modelValue: { type: Object, default: () => ({}) }, city: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue'])
const dialogVisible = ref(false)
const value = computed(() => ({ text: '', name: '', address: '', latitude: null, longitude: null, ...props.modelValue }))
const updateText = (text) => emit('update:modelValue', { ...value.value, text })
const confirmLocation = (location) => emit('update:modelValue', { ...location, text: location.name || location.address })
const clearLocation = () => emit('update:modelValue', { text: '', name: '', address: '', latitude: null, longitude: null, place_id: null, provider: null, coordinate_system: null, precision: null })
</script>

<style scoped>
.location-field { display: grid; gap: var(--space-2); min-width: 0; }
.map-preview { position: relative; display: block; width: 100%; height: 150px; padding: 0; overflow: hidden; border: var(--border-default); border-radius: var(--radius-md); background: var(--color-paper); cursor: pointer; text-align: left; }
.map-preview:focus-visible { outline: 2px solid var(--color-focus-ring); outline-offset: 2px; }
.location-overlay { position: absolute; left: var(--space-2); right: var(--space-2); bottom: var(--space-2); min-height: 52px; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: var(--space-2); padding: var(--space-2) 10px; border: var(--border-default); border-radius: var(--radius-md); background: rgba(255, 253, 249, 0.9); color: var(--color-ink); }
.location-overlay > span { display: grid; gap: 2px; min-width: 0; }
.location-overlay strong, .location-overlay small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.location-overlay small { color: var(--color-ink-secondary); }
.fallback-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2); }
@media (max-width: 600px) { .map-preview { height: 140px; } .fallback-row { grid-template-columns: 1fr; } }
</style>
