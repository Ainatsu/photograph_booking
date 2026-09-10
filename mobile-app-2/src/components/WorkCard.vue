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
          <Play :size="12" fill="currentColor" aria-hidden="true" />
          视频
        </span>
        <span class="like-badge">
          <Heart :size="13" fill="currentColor" aria-hidden="true" />
          <span>{{ work.like_count ?? 0 }}</span>
        </span>
      </div>

      <div class="body">
        <h3>{{ work.title || work.tag || '未命名作品' }}</h3>
        <div class="author-row">
          <AvatarImage
            :src="work.user_avatar_url"
            :name="work.user_display_name"
            :size="20"
            shape="rounded"
          />
          <span class="author-name">{{ work.user_display_name || '摄影创作者' }}</span>
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

/**
 * 按原图比例取值，但夹在 3/4 – 4/3 之间：
 * 极端的竖图或横图会让瀑布流落差失控。
 */
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
  /* 瀑布流列间距由父级 column-gap 控制，这里只留纵向间距 */
  margin: 0 0 var(--space-2);
  break-inside: avoid;
}

/* 描边卡片，不用阴影（DESIGN.md §6） */
.card-button {
  display: block;
  width: 100%;
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
  color: inherit;
  text-align: left;
}

.card-button:active {
  border-color: var(--brand);
}

.media {
  position: relative;
  overflow: hidden;
  border-bottom: 1px solid var(--border);
  background: var(--surface-secondary);
}

.media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 角标压在图上，用统一的遮罩色保证在任何照片上都能读 */
.video-badge,
.like-badge {
  position: absolute;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border-radius: var(--radius-pill);
  background: var(--surface-overlay);
  color: var(--on-overlay);
  font-size: var(--text-xs);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.video-badge {
  top: var(--space-2);
  left: var(--space-2);
}

.like-badge {
  right: var(--space-2);
  bottom: var(--space-2);
}

.body {
  display: grid;
  gap: 6px;
  padding: 8px 10px 10px;
}

h3 {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  font-size: var(--text-sm);
  font-weight: 700;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.author-row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
}

.author-name {
  overflow: hidden;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
