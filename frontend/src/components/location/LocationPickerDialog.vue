<template>
  <el-dialog v-model="visible" title="选择拍摄地点" width="min(920px, calc(100vw - 32px))" class="location-dialog" destroy-on-close @opened="focusSearch">
    <div class="picker-layout">
      <div class="picker-toolbar">
        <label for="location-search">搜索地点或地址</label>
        <div class="search-row">
          <el-input id="location-search" ref="searchInput" v-model="query" clearable placeholder="例如：西九文化区、香港大学" @keyup.enter="searchPlaces" />
          <el-button type="primary" :loading="searching" @click="searchPlaces">搜索</el-button>
          <el-button :loading="locating" @click="useCurrentLocation">当前位置</el-button>
        </div>
        <p class="helper-text">也可以直接点击地图或拖动标记调整位置。</p>
      </div>

      <div v-if="results.length" class="search-results" aria-label="地点搜索结果">
        <button v-for="item in results" :key="item.place_id" type="button" @click="chooseResult(item)">
          <strong>{{ item.name }}</strong>
          <span>{{ item.display_name }}</span>
        </button>
      </div>

      <div class="picker-map">
        <LocationMap :latitude="draft.latitude" :longitude="draft.longitude" interactive draggable aria-label="点击选择企划地点" @select="chooseCoordinates" />
      </div>

      <div class="selected-location" aria-live="polite">
        <MapPin :size="20" aria-hidden="true" />
        <div>
          <strong>{{ draft.name || '尚未选择地点' }}</strong>
          <span>{{ draft.address || (draft.latitude != null ? `${draft.latitude.toFixed(6)}, ${draft.longitude.toFixed(6)}` : '请搜索或点击地图') }}</span>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="draft.latitude == null || draft.longitude == null" @click="confirm">确认地点</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MapPin } from 'lucide-vue-next'
import LocationMap from './LocationMap.vue'

const props = defineProps({ modelValue: { type: Boolean, default: false }, location: { type: Object, default: () => ({}) }, city: { type: String, default: '' } })
const emit = defineEmits(['update:modelValue', 'confirm'])
const visible = ref(false)
const query = ref('')
const results = ref([])
const searching = ref(false)
const locating = ref(false)
const searchInput = ref(null)
const draft = reactive({ name: '', address: '', latitude: null, longitude: null, place_id: null })

const hydrateDraft = () => {
  draft.name = props.location?.name || props.location?.location_name || ''
  draft.address = props.location?.address || props.location?.location_address || props.location?.text || ''
  draft.latitude = props.location?.latitude != null && Number.isFinite(Number(props.location.latitude)) ? Number(props.location.latitude) : null
  draft.longitude = props.location?.longitude != null && Number.isFinite(Number(props.location.longitude)) ? Number(props.location.longitude) : null
  draft.place_id = props.location?.place_id || null
}

watch(() => props.modelValue, (value) => { visible.value = value; if (value) hydrateDraft() }, { immediate: true })
watch(visible, (value) => emit('update:modelValue', value))

const focusSearch = () => nextTick(() => searchInput.value?.focus?.())

const searchPlaces = async () => {
  const keyword = [query.value.trim(), props.city].filter(Boolean).join(', ')
  if (!keyword) return
  searching.value = true
  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&addressdetails=1&q=${encodeURIComponent(keyword)}`, { headers: { 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7' } })
    if (!response.ok) throw new Error('search failed')
    results.value = (await response.json()).map(item => ({ ...item, name: item.name || item.display_name.split(',')[0] }))
    if (!results.value.length) ElMessage.info('没有找到匹配地点，请尝试更具体的关键词')
  } catch {
    ElMessage.error('地点搜索失败，请稍后重试或直接点击地图')
  } finally { searching.value = false }
}

const chooseResult = (item) => {
  draft.name = item.name
  draft.address = item.display_name
  draft.latitude = Number(item.lat)
  draft.longitude = Number(item.lon)
  draft.place_id = String(item.place_id)
  results.value = []
}

const reverseGeocode = async () => {
  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${draft.latitude}&lon=${draft.longitude}&zoom=18`, { headers: { 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7' } })
    if (!response.ok) return
    const data = await response.json()
    draft.name = data.name || data.display_name?.split(',')[0] || '地图选点'
    draft.address = data.display_name || ''
    draft.place_id = data.place_id ? String(data.place_id) : null
  } catch { /* coordinates remain usable when reverse geocoding is unavailable */ }
}

const chooseCoordinates = async ({ latitude, longitude }) => {
  draft.latitude = latitude
  draft.longitude = longitude
  draft.name = '正在识别地点…'
  draft.address = ''
  await reverseGeocode()
}

const useCurrentLocation = () => {
  if (!navigator.geolocation) return ElMessage.warning('当前浏览器不支持定位')
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    async position => { await chooseCoordinates({ latitude: position.coords.latitude, longitude: position.coords.longitude }); locating.value = false },
    () => { locating.value = false; ElMessage.error('无法获取当前位置，请检查浏览器定位权限') },
    { enableHighAccuracy: true, timeout: 10000 },
  )
}

const confirm = () => {
  emit('confirm', { name: draft.name, address: draft.address, latitude: draft.latitude, longitude: draft.longitude, place_id: draft.place_id, provider: 'openstreetmap', coordinate_system: 'WGS84', precision: 'exact' })
  visible.value = false
}
</script>

<style scoped>
.picker-layout { display: grid; gap: var(--space-4); }
.picker-toolbar { display: grid; gap: var(--space-2); }
.picker-toolbar label { color: var(--color-ink); font-weight: 700; }
.search-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: var(--space-2); }
.helper-text { margin: 0; color: var(--color-ink-secondary); font-size: var(--text-sm); }
.search-results { display: grid; max-height: 190px; overflow-y: auto; border: var(--border-default); }
.search-results button { display: grid; gap: 3px; padding: 12px 14px; border: 0; border-bottom: 1px solid var(--color-divider); background: var(--color-paper-light); color: var(--color-ink); text-align: left; cursor: pointer; }
.search-results button:hover, .search-results button:focus-visible { background: var(--color-brand-light); outline: 2px solid var(--color-focus-ring); outline-offset: -2px; }
.search-results span { color: var(--color-ink-secondary); font-size: var(--text-sm); }
.picker-map { height: min(52vh, 470px); min-height: 320px; border: var(--border-default); border-radius: var(--radius-md); overflow: hidden; }
.selected-location { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3); border: var(--border-default); background: var(--color-paper-light); }
.selected-location div { display: grid; gap: 4px; }
.selected-location span { color: var(--color-ink-secondary); font-size: var(--text-sm); }
@media (max-width: 600px) { .search-row { grid-template-columns: 1fr 1fr; } .search-row :deep(.el-input) { grid-column: 1 / -1; } .picker-map { min-height: 44vh; } }
</style>

<style>
@media (max-width: 600px) {
  .location-dialog {
    width: 100% !important;
    height: 100dvh;
    margin: 0;
    display: flex;
    flex-direction: column;
    border-radius: 0;
  }

  .location-dialog .el-dialog__body {
    flex: 1;
    overflow-y: auto;
  }

  .location-dialog .el-dialog__footer {
    padding-bottom: max(var(--space-4), env(safe-area-inset-bottom));
  }
}
</style>
