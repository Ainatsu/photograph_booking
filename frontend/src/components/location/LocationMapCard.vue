<template>
  <section class="location-card" aria-labelledby="project-location-title">
    <div class="location-card-head">
      <MapPin :size="19" aria-hidden="true" />
      <h2 id="project-location-title">拍摄地点</h2>
    </div>
    <div v-if="hasCoordinates" class="location-card-map">
      <LocationMap :latitude="Number(location.location_latitude)" :longitude="Number(location.location_longitude)" aria-label="企划拍摄地点地图" />
    </div>
    <div class="location-card-copy">
      <strong>{{ location.location_name || location.location_text || location.city }}</strong>
      <span v-if="location.location_address">{{ location.location_address }}</span>
      <a v-if="hasCoordinates" :href="externalMapUrl" target="_blank" rel="noopener noreferrer">在地图中查看</a>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { MapPin } from 'lucide-vue-next'
import LocationMap from './LocationMap.vue'
const props = defineProps({ location: { type: Object, required: true } })
const hasCoordinates = computed(() => props.location.location_latitude != null && props.location.location_longitude != null && Number.isFinite(Number(props.location.location_latitude)) && Number.isFinite(Number(props.location.location_longitude)))
const externalMapUrl = computed(() => `https://www.openstreetmap.org/?mlat=${props.location.location_latitude}&mlon=${props.location.location_longitude}#map=17/${props.location.location_latitude}/${props.location.location_longitude}`)
</script>

<style scoped>
.location-card { display: grid; gap: var(--space-3); padding: var(--space-4); border: var(--border-default); border-radius: var(--radius-md); background: var(--color-paper-light); }
.location-card-head { display: flex; align-items: center; gap: var(--space-2); color: var(--color-brand); }
.location-card-head h2 { margin: 0; color: var(--color-ink); font-size: var(--text-base); }
.location-card-map { height: 176px; overflow: hidden; border: var(--border-default); border-radius: var(--radius-sm); }
.location-card-copy { display: grid; gap: 4px; }
.location-card-copy span { color: var(--color-ink-secondary); font-size: var(--text-sm); line-height: 1.5; }
.location-card-copy a { width: fit-content; margin-top: 4px; color: var(--color-brand); font-weight: 700; text-decoration: none; }
.location-card-copy a:hover { text-decoration: underline; }
</style>
