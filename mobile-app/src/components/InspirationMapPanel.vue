<template>
  <section class="map-panel">
    <SearchField v-model="query" label="搜索地图中的灵感" placeholder="搜索地点" @submit="load" />
    <div class="map-wrap"><div ref="host" class="map-host" aria-label="灵感地图"></div><div v-if="loading" class="map-overlay">地图加载中…</div><StatePanel v-else-if="error" tone="error" title="地图加载失败" description="请检查网络后重试。" action-label="重新加载" @action="initialize" /></div>
    <section v-if="selected" class="selected-place"><div class="place-heading"><MapPin :size="20" aria-hidden="true"/><div><h2>{{ selected.name }}</h2><p>{{ selected.count }} 条灵感</p></div><button type="button" aria-label="关闭地点灵感" @click="selected = null"><X :size="20"/></button></div><div class="place-cards"><InspirationCard v-for="item in selected.items" :key="item.id" :item="item" @open="id => $emit('open-detail', id)" /></div></section><StatePanel v-else title="在地图上找到灵感" description="点击地图上的地点标记，查看这个地方保存过的画面。" />
  </section>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { MapPin, X } from 'lucide-vue-next'
import SearchField from '@/components/SearchField.vue'
import StatePanel from '@/components/StatePanel.vue'
import InspirationCard from '@/components/InspirationCard.vue'
import { getInspirationMap, getInspirations } from '@/api/inspirations'
import type { Inspiration, InspirationMapPoint } from '@/types/inspiration'
import { resolveMediaUrl } from '@/utils/media'

defineEmits<{ 'open-detail': [id: number] }>()
const host = ref<HTMLElement | null>(null), query = ref(''), loading = ref(true), error = ref(false), selected = ref<(InspirationMapPoint & { items: Inspiration[] }) | null>(null)
let map: any = null, maplibregl: any = null, markers: any[] = []
function clearMarkers() { markers.forEach((marker) => marker.remove()); markers = [] }
function createMarkerElement(point: InspirationMapPoint) {
  const el = document.createElement('button')
  const earliest = point.preview[0]
  const cover = resolveMediaUrl(earliest?.cover_url)
  el.type = 'button'
  el.className = 'map-marker'
  el.setAttribute('aria-label', `${point.name}，显示最早创建的灵感${earliest ? `“${earliest.title}”` : ''}，共${point.count}条`)
  const placeholder = document.createElement('span')
  placeholder.className = 'map-marker-placeholder'
  placeholder.textContent = earliest?.title?.trim().slice(0, 1) || '灵'
  el.appendChild(placeholder)
  if (cover) {
    const image = document.createElement('img')
    image.className = 'map-marker-cover'
    image.src = cover
    image.alt = ''
    image.addEventListener('error', () => image.remove(), { once: true })
    el.appendChild(image)
  }
  if (point.count > 1) {
    const badge = document.createElement('span')
    badge.className = 'map-marker-count'
    badge.textContent = `+${point.count - 1}`
    el.appendChild(badge)
  }
  el.addEventListener('click', () => selectPoint(point))
  return el
}
async function load() { if (!map) return; try { const points = await getInspirationMap(query.value || undefined); clearMarkers(); points.forEach((point) => { const el = createMarkerElement(point); markers.push(new maplibregl.Marker({ element: el }).setLngLat([point.longitude, point.latitude]).addTo(map)) }) } catch { error.value = true } }
async function selectPoint(point: InspirationMapPoint) { selected.value = { ...point, items: [] }; try { selected.value.items = await getInspirations({ query: point.name, limit: 100 }) } catch { selected.value.items = point.preview as Inspiration[] } }
async function initialize() { if (!host.value || map) return; loading.value = true; error.value = false; try { const module = await import('maplibre-gl'); await import('maplibre-gl/dist/maplibre-gl.css'); maplibregl = (module as any).default || module; map = new maplibregl.Map({ container: host.value, center: [114.1694, 22.3193], zoom: 10, style: { version: 8, sources: { osm: { type: 'raster', tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], tileSize: 256, attribution: '© OpenStreetMap contributors' } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] } }); map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right'); map.on('load', async () => { loading.value = false; await load() }) } catch { loading.value = false; error.value = true } }
onMounted(() => { void nextTick(initialize) }); onBeforeUnmount(() => { clearMarkers(); map?.remove() })
</script>

<style scoped>
.map-panel { display: grid; gap: var(--space-3); }.map-wrap { position: relative; height: 48dvh; min-height: 330px; overflow: hidden; border-radius: var(--radius-lg); background: var(--paper); box-shadow: var(--neu-inset); }.map-host { width: 100%; height: 100%; }.map-overlay { position: absolute; inset: 0; display: grid; place-items: center; background: var(--paper); color: var(--ink-secondary); }:global(.map-marker){position:relative;width:58px;height:58px;overflow:visible;padding:0;border:3px solid var(--surface-solid);border-radius:14px;background:var(--brand-soft);box-shadow:var(--shadow-2);color:var(--brand);cursor:pointer;font-size:var(--text-lg);font-weight:800;touch-action:manipulation}:global(.map-marker-placeholder){display:grid;width:100%;height:100%;place-items:center;overflow:hidden;border-radius:11px}:global(.map-marker-cover){position:absolute;inset:0;width:100%;height:100%;border-radius:11px;object-fit:cover}:global(.map-marker-count){position:absolute;z-index:2;top:-10px;right:-12px;display:grid;min-width:28px;height:28px;place-items:center;padding:0 6px;border:2px solid var(--surface-solid);border-radius:var(--radius-pill);background:var(--brand);box-shadow:var(--shadow-1);color:var(--white);font-size:11px;font-weight:850;line-height:1}.selected-place { display: grid; gap: var(--space-3); padding: var(--space-4); border-radius: var(--radius-lg); background: var(--surface-solid); box-shadow: var(--shadow-2); }.place-heading { display: flex; align-items: center; gap: var(--space-2); color: var(--brand); }.place-heading div { flex: 1; min-width: 0; }.place-heading h2,.place-heading p { margin: 0; }.place-heading h2 { color: var(--ink); font-size: var(--text-lg); }.place-heading p { color: var(--ink-secondary); font-size: var(--text-xs); }.place-heading button { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; border-radius: 50%; background: var(--surface-secondary); color: var(--ink-secondary); }.place-cards { display: grid; gap: var(--space-3); max-height: 420px; overflow-y: auto; }
</style>
