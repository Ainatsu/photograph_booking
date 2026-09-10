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
            <AvatarImage
              :src="profile.user_avatar_url"
              :name="displayName"
              :size="44"
              shape="rounded"
            />
            <span class="identity-text">
              <strong>{{ displayName }}</strong>
              <small v-if="profile.location"><MapPin :size="12" aria-hidden="true" />{{ profile.location }}</small>
            </span>
          </span>
          <span class="rating" :aria-label="`评分 ${rating}`">
            <Star :size="14" fill="currentColor" aria-hidden="true" />
            {{ rating }}
          </span>
        </div>

        <!--
          风格标签：参考图在这里放的是「价目表 / 档期空闲」这类状态徽章，
          但 PhotographerProfile 没有对应字段，只有 styles 是真实数据。
          用风格标签填这一行，不臆造状态徽章。
        -->
        <ul v-if="styleTags.length" class="tag-row">
          <li v-for="tag in styleTags" :key="tag" class="tag">{{ tag }}</li>
        </ul>
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
const styleTags = computed(() => (props.profile.styles || []).slice(0, 3))
const previewItems = computed<(WorkItem | undefined)[]>(() => {
  const items = props.profile.portfolio?.slice(0, 3) || []
  return Array.from({ length: 3 }, (_, index) => items[index])
})
</script>

<style scoped>
.photographer-card {
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface-solid);
}

.card-button {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

/* 三列密排，间距只用 2px —— 参考图里这一组缩略图几乎连成一条 */
.preview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 2px;
  border-bottom: 1px solid var(--border);
  background: var(--border);
}

.preview-cell {
  min-width: 0;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  background: var(--surface-secondary);
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

.identity-text {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.identity strong {
  overflow: hidden;
  font-size: var(--text-base);
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.identity small {
  gap: 3px;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

/* 评分用价格橙：小字，所以取 --price-ink（白底 4.98:1） */
.rating {
  flex: 0 0 auto;
  gap: 4px;
  color: var(--price-ink);
  font-size: var(--text-sm);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: 0;
  margin: var(--space-3) 0 0;
  list-style: none;
}

/* 徽章配色取自 DESIGN.md §3.3 的品牌类配对 */
.tag {
  display: inline-flex;
  min-height: 24px;
  align-items: center;
  padding: 0 10px;
  border-radius: var(--radius-pill);
  background: var(--brand-soft);
  color: var(--brand);
  font-size: var(--text-xs);
  font-weight: 700;
}
</style>
