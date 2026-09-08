<template>
  <article class="work-card">
    <button type="button" class="card-button pressable" @click="$emit('open', work)">
      <div class="media" :style="{ aspectRatio }">
        <img
          v-if="preview && !imageFailed"
          :src="preview"
          :alt="work.title || '摄影作品'"
          loading="lazy"
          @error="imageFailed = true"
        />
        <MediaPlaceholder v-else />
        <span v-if="work.media_type === 'video'" class="video-badge">
          <Play :size="13" fill="currentColor" aria-hidden="true" />
          视频
        </span>
      </div>

      <div class="body">
        <h3>{{ work.title || work.tag || '未命名作品' }}</h3>
        <div class="author-row">
          <span class="author">
            <AvatarImage :src="work.user_avatar_url" :name="work.user_display_name" :size="25" />
            <span>{{ work.user_display_name || '摄影创作者' }}</span>
          </span>
          <span class="like-count">
            <Heart :size="14" aria-hidden="true" />
            <span>{{ work.like_count ?? 0 }}</span>
          </span>
        </div>
      </div>
    </button>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Heart, Play } from 'lucide-vue-next'
import AvatarImage from './AvatarImage.vue'
import MediaPlaceholder from './MediaPlaceholder.vue'
import type { WorkItem } from '@/types/discovery'
import { getWorkPreviewUrl } from '@/utils/media'

const props = defineProps<{
  work: WorkItem
}>()

defineEmits<{
  open: [work: WorkItem]
}>()

const imageFailed = ref(false)
const preview = computed(() => getWorkPreviewUrl(props.work))

const aspectRatio = ref('1/1')

function preloadImage(url: string): Promise<number> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img.naturalWidth / img.naturalHeight)
    img.onerror = () => resolve(1)
    img.src = url
  })
}

function computeClampedRatio(raw: number): string {
  if (raw > 4 / 3) return '4/3'
  if (raw < 3 / 4) return '3/4'
  return '1/1'
}

watch(preview, async (url) => {
  imageFailed.value = false
  if (!url) return
  aspectRatio.value = '1/1'
  const raw = await preloadImage(url)
  aspectRatio.value = computeClampedRatio(raw)
}, { immediate: true })
</script>

<style scoped>
.work-card {
  display: inline-block;
  width: 100%;
  margin: 0 0 var(--space-3);
  break-inside: avoid;
}

.card-button {
  width: 100%;
  overflow: hidden;
  padding: 0;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: inherit;
  text-align: left;
}

.card-button:active {
  border-color: var(--brand);
}

.media {
  position: relative;
  overflow: hidden;
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.video-badge {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 7px;
  border-radius: var(--radius-pill);
  background: rgba(26, 26, 26, 0.74);
  color: var(--white);
  font-size: var(--text-2xs);
  font-weight: 650;
}

.body {
  padding: 10px;
}

h3 {
  display: -webkit-box;
  margin: 0 0 9px;
  overflow: hidden;
  font-size: var(--text-sm);
  font-weight: 700;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.author-row,
.author {
  display: flex;
  align-items: center;
}

.author-row {
  justify-content: space-between;
  gap: var(--space-2);
  color: var(--ink-tertiary);
}

.author {
  min-width: 0;
  gap: 6px;
}

.author > span:last-child {
  overflow: hidden;
  color: var(--ink-secondary);
  font-size: var(--text-2xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.like-count {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: var(--ink-tertiary);
  font-size: var(--text-2xs);
  white-space: nowrap;
}
</style>
