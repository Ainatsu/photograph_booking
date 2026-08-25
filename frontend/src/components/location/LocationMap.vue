<template>
  <div class="map-shell" :class="{ 'is-interactive': interactive }">
    <div ref="mapHost" class="map-host" :aria-label="ariaLabel"></div>
    <div v-if="loading" class="map-state">地图加载中…</div>
    <div v-else-if="error" class="map-state map-error" role="alert">
      <span>地图加载失败</span>
      <button type="button" @click="initializeMap">重试</button>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  latitude: { type: Number, default: null },
  longitude: { type: Number, default: null },
  interactive: { type: Boolean, default: false },
  draggable: { type: Boolean, default: false },
  zoom: { type: Number, default: 14 },
  ariaLabel: { type: String, default: '地点地图' },
})

const emit = defineEmits(['select'])
const mapHost = ref(null)
const loading = ref(true)
const error = ref(false)
let map = null
let marker = null
let maplibregl = null

const DEFAULT_CENTER = [114.1694, 22.3193]
const hasCoordinates = () => Number.isFinite(props.latitude) && Number.isFinite(props.longitude)
const currentCenter = () => hasCoordinates() ? [props.longitude, props.latitude] : DEFAULT_CENTER

const emitPosition = (lngLat) => {
  emit('select', { latitude: lngLat.lat, longitude: lngLat.lng })
}

const updateMarker = () => {
  if (!map || !maplibregl || !hasCoordinates()) return
  const position = [props.longitude, props.latitude]
  if (!marker) {
    marker = new maplibregl.Marker({ color: '#2D5A27', draggable: props.draggable })
      .setLngLat(position)
      .addTo(map)
    if (props.draggable) marker.on('dragend', () => emitPosition(marker.getLngLat()))
  } else {
    marker.setLngLat(position)
  }
  map.easeTo({ center: position, zoom: Math.max(map.getZoom(), props.zoom), duration: 250 })
}

const initializeMap = async () => {
  if (!mapHost.value || map) return
  loading.value = true
  error.value = false
  try {
    const module = await import('maplibre-gl')
    await import('maplibre-gl/dist/maplibre-gl.css')
    maplibregl = module.default
    map = new maplibregl.Map({
      container: mapHost.value,
      center: currentCenter(),
      zoom: hasCoordinates() ? props.zoom : 10,
      interactive: props.interactive,
      attributionControl: true,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
      },
    })
    map.on('load', () => {
      loading.value = false
      updateMarker()
      map.resize()
    })
    map.on('error', () => {
      if (!map?.loaded()) error.value = true
      loading.value = false
    })
    if (props.interactive) {
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
      map.on('click', (event) => emitPosition(event.lngLat))
    }
  } catch {
    loading.value = false
    error.value = true
  }
}

watch(() => [props.latitude, props.longitude], async () => {
  await nextTick()
  updateMarker()
})

onMounted(initializeMap)
onBeforeUnmount(() => {
  marker?.remove()
  map?.remove()
  marker = null
  map = null
})
</script>

<style scoped>
.map-shell { position: relative; width: 100%; height: 100%; min-height: 160px; background: var(--color-paper); overflow: hidden; }
.map-host { width: 100%; height: 100%; min-height: inherit; }
.map-state { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; gap: var(--space-3); background: var(--color-paper); color: var(--color-ink-secondary); }
.map-error button { min-height: 44px; padding: 0 var(--space-4); border: var(--border-default); border-radius: var(--radius-md); background: var(--color-paper-light); color: var(--color-ink); cursor: pointer; }
.is-interactive { cursor: crosshair; }
</style>
