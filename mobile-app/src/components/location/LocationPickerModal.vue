<template>
  <ion-modal
    :is-open="modelValue"
    :can-dismiss="true"
    @did-dismiss="$emit('update:modelValue', false)"
  >
    <ion-header>
      <ion-toolbar>
        <ion-title>选择拍摄地点</ion-title>
        <ion-buttons slot="end">
          <ion-button @click="$emit('update:modelValue', false)">关闭</ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>
    <ion-content class="picker-content">
      <div class="picker-layout">
        <div class="picker-toolbar">
          <label for="location-search">搜索地点或地址</label>
          <div class="search-row">
            <input
              id="location-search"
              ref="searchInput"
              v-model="query"
              class="publish-input"
              placeholder="例如：西九文化区、香港大学"
              @keyup.enter="searchPlaces"
            />
            <button type="button" class="picker-btn pressable" :disabled="searching" @click="searchPlaces">
              <ion-spinner v-if="searching" name="crescent" aria-hidden="true" />
              <Search v-else :size="18" aria-hidden="true" />
              <span>搜索</span>
            </button>
          </div>
          <button type="button" class="picker-btn secondary pressable" :disabled="locating" @click="useCurrentLocation">
            <ion-spinner v-if="locating" name="crescent" aria-hidden="true" />
            <Navigation v-else :size="18" aria-hidden="true" />
            <span>{{ locating ? '定位中...' : '当前位置' }}</span>
          </button>
          <p class="helper-text">也可以直接点击地图或拖动标记调整位置。</p>
        </div>

        <div v-if="results.length" class="search-results" aria-label="地点搜索结果">
          <button v-for="item in results" :key="item.place_id" type="button" class="pressable" @click="chooseResult(item)">
            <strong>{{ item.name }}</strong>
            <span>{{ item.display_name }}</span>
          </button>
        </div>

        <div class="picker-map">
          <LocationMap
            :latitude="draft.latitude ?? undefined"
            :longitude="draft.longitude ?? undefined"
            interactive
            draggable
            aria-label="点击选择企划地点"
            @select="chooseCoordinates"
          />
        </div>

        <div class="selected-location" aria-live="polite">
          <MapPin :size="20" aria-hidden="true" />
          <div>
            <strong>{{ draft.name || '尚未选择地点' }}</strong>
            <span>{{ draft.address || (draft.latitude != null ? `${draft.latitude.toFixed(6)}, ${draft.longitude?.toFixed(6)}` : '请搜索或点击地图') }}</span>
          </div>
        </div>
      </div>
    </ion-content>

    <ion-footer>
      <div class="picker-footer">
        <button
          type="button"
          class="pressable confirm-btn"
          :disabled="draft.latitude == null || draft.longitude == null"
          @click="confirm"
        >
          确认地点
        </button>
      </div>
    </ion-footer>
  </ion-modal>
</template>

<script setup lang="ts">
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { IonButton, IonButtons, IonContent, IonFooter, IonHeader, IonModal, IonSpinner, IonTitle, IonToolbar } from '@ionic/vue'
import { MapPin, Navigation, Search } from 'lucide-vue-next'
import LocationMap from './LocationMap.vue'

interface PlaceResult {
  place_id: number
  name: string
  display_name: string
  lat: string
  lon: string
}

interface LocationDraft {
  name: string
  address: string
  latitude: number | null
  longitude: number | null
  place_id: string | null
}

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  location: { type: Object as () => Record<string, unknown>, default: () => ({}) },
  city: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const query = ref('')
const results = ref<PlaceResult[]>([])
const searching = ref(false)
const locating = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)
const draft = reactive<LocationDraft>({ name: '', address: '', latitude: null, longitude: null, place_id: null })

const hydrateDraft = () => {
  draft.name = (props.location?.name || props.location?.location_name || '') as string
  draft.address = (props.location?.address || props.location?.location_address || props.location?.text || '') as string
  const lat = props.location?.latitude ?? props.location?.location_latitude
  const lng = props.location?.longitude ?? props.location?.location_longitude
  draft.latitude = lat != null && Number.isFinite(Number(lat)) ? Number(lat) : null
  draft.longitude = lng != null && Number.isFinite(Number(lng)) ? Number(lng) : null
  draft.place_id = (props.location?.place_id as string) || null
}

watch(() => props.modelValue, (val) => { if (val) hydrateDraft() })
watch(() => props.modelValue, async (val) => {
  if (val) { await nextTick(); searchInput.value?.focus() }
})

const searchPlaces = async () => {
  const keyword = [query.value.trim(), props.city].filter(Boolean).join(', ')
  if (!keyword) return
  searching.value = true
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&addressdetails=1&q=${encodeURIComponent(keyword)}`,
      { headers: { 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7' } },
    )
    if (!response.ok) throw new Error('search failed')
    results.value = (await response.json()).map((item: any) => ({
      ...item,
      name: item.name || item.display_name.split(',')[0],
    }))
  } catch {
    results.value = []
  } finally {
    searching.value = false
  }
}

const chooseResult = (item: PlaceResult) => {
  draft.name = item.name
  draft.address = item.display_name
  draft.latitude = Number(item.lat)
  draft.longitude = Number(item.lon)
  draft.place_id = String(item.place_id)
  results.value = []
}

const reverseGeocode = async () => {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${draft.latitude}&lon=${draft.longitude}&zoom=18`,
      { headers: { 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.7' } },
    )
    if (!response.ok) return
    const data = await response.json()
    draft.name = data.name || data.display_name?.split(',')[0] || '地图选点'
    draft.address = data.display_name || ''
    draft.place_id = data.place_id ? String(data.place_id) : null
  } catch { /* 反向地理编码失败时保留坐标 */ }
}

const chooseCoordinates = async ({ latitude, longitude }: { latitude: number; longitude: number }) => {
  draft.latitude = latitude
  draft.longitude = longitude
  draft.name = '正在识别地点...'
  draft.address = ''
  await reverseGeocode()
}

const useCurrentLocation = () => {
  if (!navigator.geolocation) return
  locating.value = true
  navigator.geolocation.getCurrentPosition(
    async (position) => {
      await chooseCoordinates({ latitude: position.coords.latitude, longitude: position.coords.longitude })
      locating.value = false
    },
    () => { locating.value = false },
    { enableHighAccuracy: true, timeout: 10000 },
  )
}

const confirm = () => {
  emit('confirm', {
    name: draft.name,
    address: draft.address,
    latitude: draft.latitude,
    longitude: draft.longitude,
    place_id: draft.place_id,
    provider: 'openstreetmap',
    coordinate_system: 'WGS84',
    precision: 'exact',
  })
  emit('update:modelValue', false)
}
</script>

<style scoped>
.picker-content { --background: var(--paper); }
.picker-layout { display: grid; gap: var(--space-4); padding: var(--space-4); }

.picker-toolbar { display: grid; gap: var(--space-2); }
.picker-toolbar label { color: var(--ink); font-weight: 700; font-size: var(--text-sm); }

.search-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2); }

.picker-btn {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
  font-weight: 700;
}
.picker-btn:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); opacity: .72; }
.picker-btn.secondary { border-color: var(--border); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink); }
.picker-btn ion-spinner { width: 18px; height: 18px; }

.helper-text { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.55; }

.search-results { display: grid; max-height: 190px; overflow-y: auto; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.search-results button {
  display: grid;
  gap: 3px;
  padding: 12px 14px;
  border: 0;
  border-bottom: 1px solid var(--neu-light);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--ink);
  text-align: left;
}
.search-results button:last-child { border-bottom: 0; }
.search-results button:hover, .search-results button:focus-visible { background: var(--brand-soft); }
.search-results span { color: var(--ink-secondary); font-size: var(--text-xs); display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }

.picker-map { height: min(52vh, 360px); min-height: 240px; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); overflow: hidden; }

.selected-location {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}
.selected-location div { display: grid; gap: 4px; min-width: 0; }
.selected-location span { color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.5; word-break: break-all; }

.picker-footer { padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom)); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); background: var(--paper); }

.confirm-btn {
  display: flex;
  width: 100%;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
  font-weight: 750;
}
.confirm-btn:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }
</style>
