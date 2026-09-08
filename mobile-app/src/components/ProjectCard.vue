<template>
  <article class="project-card">
    <button type="button" class="card-button pressable" @click="$emit('open', project)">
      <div class="top-row">
        <div class="top-info">
          <h3>{{ project.title }}</h3>
          <p>{{ project.description }}</p>
        </div>
        <div v-if="firstRefImage" class="media" :style="{ aspectRatio: '1/1' }">
          <img :src="firstRefImage" :alt="project.title" loading="lazy" />
        </div>
        <MediaPlaceholder v-else class="media placeholder" />
      </div>

      <div class="meta-row">
        <span class="meta-item customer">
          <AvatarImage :src="project.customer_avatar_url" :name="project.customer_name" :size="25" />
          <span>{{ project.customer_name || '客户' }}</span>
        </span>
        <span class="meta-item location"><MapPin :size="14" />{{ displayLocation }}</span>
        <strong class="meta-item budget">{{ formatProjectBudget(project) }}</strong>
      </div>
    </button>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MapPin } from 'lucide-vue-next'
import AvatarImage from './AvatarImage.vue'
import MediaPlaceholder from './MediaPlaceholder.vue'
import type { ProjectBrief } from '@/types/discovery'
import { formatProjectBudget } from '@/utils/format'

const props = defineProps<{
  project: ProjectBrief
}>()

defineEmits<{
  open: [project: ProjectBrief]
}>()

const firstRefImage = computed(() => {
  const images = props.project.reference_images
  return images?.length ? images[0] : null
})

const displayLocation = computed(() => {
  const { city, location_name, location_text } = props.project
  const detail = location_name || location_text
  if (city && detail) return `${city} · ${detail}`
  if (city) return city
  return detail || '地点待沟通'
})
</script>

<style scoped>
.project-card {
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
}

.card-button {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.card-button:active {
  border-color: var(--brand);
}

.top-row {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-4);
}

.top-info {
  flex: 1;
  min-width: 0;
}

h3 {
  margin: 0 0 var(--space-2);
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  line-height: 1.45;
}

p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.65;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.media {
  width: 140px;
  flex: 0 0 auto;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.media.placeholder {
  min-height: 110px;
}

.meta-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  align-items: center;
  gap: var(--space-2);
  margin: 0 var(--space-4);
  padding: var(--space-3) 0 var(--space-4);
  border-top: 1px solid var(--divider);
}

.meta-item {
  display: flex;
  align-items: center;
  min-width: 0;
}

.customer {
  gap: 6px;
  color: var(--ink-secondary);
  font-size: var(--text-2xs);
}

.customer > span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.location {
  justify-content: center;
  gap: 3px;
  color: var(--ink-tertiary);
  font-size: var(--text-2xs);
}

.budget {
  justify-content: flex-end;
  color: var(--brand);
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
</style>
