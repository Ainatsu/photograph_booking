<template>
  <article class="photographer-card">
    <button type="button" class="card-button pressable" @click="$emit('open', profile)">
      <div class="preview-grid">
        <div v-for="(item, index) in previewItems" :key="item?.id || index" class="preview-cell">
          <img
            v-if="item && getWorkPreviewUrl(item)"
            :src="getWorkPreviewUrl(item)"
            :alt="item.title || `${displayName}的作品`"
            loading="lazy"
          />
          <MediaPlaceholder v-else />
        </div>
      </div>

      <div class="body">
        <div class="identity-row">
          <span class="identity">
            <AvatarImage :src="profile.user_avatar_url" :name="displayName" :size="44" />
            <span>
              <strong>{{ displayName }}</strong>
              <small v-if="profile.location"><MapPin :size="12" />{{ profile.location }}</small>
            </span>
          </span>
          <span class="rating" :aria-label="`评分 ${rating}`">
            <Star :size="14" fill="currentColor" aria-hidden="true" />
            {{ rating }}
          </span>
        </div>
      </div>
    </button>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MapPin, Star } from 'lucide-vue-next'
import AvatarImage from './AvatarImage.vue'
import MediaPlaceholder from './MediaPlaceholder.vue'
import type { PhotographerProfile, WorkItem } from '@/types/discovery'
import { getWorkPreviewUrl } from '@/utils/media'

const props = defineProps<{
  profile: PhotographerProfile
}>()

defineEmits<{
  open: [profile: PhotographerProfile]
}>()

const displayName = computed(() => props.profile.user_display_name || '摄影师')
const rating = computed(() => Number(props.profile.avg_rating || 0).toFixed(1))
const previewItems = computed<(WorkItem | undefined)[]>(() => {
  const items = props.profile.portfolio?.slice(0, 3) || []
  return Array.from({ length: 3 }, (_, index) => items[index])
})
</script>

<style scoped>
.photographer-card {
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-lg);
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

.preview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 2px;
  background: var(--divider);
}

.preview-cell {
  min-width: 0;
  overflow: hidden;
  aspect-ratio: 1 / 1;
}

.preview-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.body {
  padding: var(--space-4);
}

.identity-row,
.identity,
.identity small,
.rating {
  display: flex;
  align-items: center;
}

.identity-row {
  justify-content: space-between;
  gap: var(--space-3);
}

.identity {
  min-width: 0;
  gap: var(--space-3);
}

.identity > span:last-child {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.identity strong {
  overflow: hidden;
  font-size: var(--text-base);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity small {
  gap: 3px;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.rating {
  gap: 4px;
  color: var(--warning);
  font-size: var(--text-sm);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

</style>
