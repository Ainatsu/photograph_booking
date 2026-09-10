<template>
  <article class="package-card">
    <button type="button" class="card-button pressable" @click="$emit('open', offer)">
      <div class="media" :style="{ aspectRatio }">
        <img
          v-if="preview && !imageFailed"
          :src="preview"
          :alt="getPackageName(offer)"
          loading="lazy"
          @error="imageFailed = true"
        />
        <MediaPlaceholder v-else />
        <!-- 交付周期角标：参考图这里是「24H 特快」这类时效标记，用真实的 delivery_days 渲染 -->
        <span v-if="deliveryBadge" class="delivery-badge">{{ deliveryBadge }}</span>
        <span v-if="offer.city" class="location-pill">
          <MapPin :size="12" aria-hidden="true" />
          {{ offer.city }}
        </span>
      </div>

      <div class="body">
        <h3>{{ getPackageName(offer) }}</h3>
        <div class="author-row">
          <AvatarImage
            :src="offer.photographer_avatar"
            :name="offer.photographer_name"
            :size="20"
            shape="rounded"
          />
          <span class="author-name">{{ offer.photographer_name || '摄影师' }}</span>
        </div>
        <div class="meta-row">
          <strong class="price">{{ formatCurrency(offer.price) }}</strong>
          <span v-if="durationText" class="duration">{{ durationText }}</span>
        </div>
      </div>
    </button>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { MapPin } from 'lucide-vue-next'
import AvatarImage from './AvatarImage.vue'
import MediaPlaceholder from './MediaPlaceholder.vue'
import type { PackageOffer } from '@/types/discovery'
import { formatCurrency, formatDuration, getPackageName } from '@/utils/format'
import { getPackagePreviewUrl } from '@/utils/media'

const props = defineProps<{
  offer: PackageOffer
}>()

defineEmits<{
  open: [offer: PackageOffer]
}>()

const imageFailed = ref(false)
const preview = computed(() => getPackagePreviewUrl(props.offer))

const deliveryBadge = computed(() => {
  const days = props.offer.delivery_days
  return days ? `${days} 天交付` : ''
})

const durationText = computed(() => (props.offer.duration ? formatDuration(props.offer.duration) : ''))

const aspectRatio = ref('1/1')

function preloadImage(url: string): Promise<number> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img.naturalWidth / img.naturalHeight)
    img.onerror = () => resolve(1)
    img.src = url
  })
}

/** 与 WorkCard 同一套夹取规则，避免瀑布流落差失控 */
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
.package-card {
  display: inline-block;
  width: 100%;
  /* 双列网格里纵向间距由卡片自身留出 */
  margin: 0 0 var(--space-3);
  break-inside: avoid;
}

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

.delivery-badge,
.location-pill {
  position: absolute;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-pill);
  font-size: var(--text-2xs);
  font-weight: 700;
}

/* 时效角标用品牌色实底，和位置角标的深色遮罩区分开 */
.delivery-badge {
  top: var(--space-2);
  left: var(--space-2);
  background: var(--brand);
  color: var(--on-brand);
}

.location-pill {
  right: var(--space-2);
  bottom: var(--space-2);
  max-width: calc(100% - 16px);
  background: var(--surface-overlay);
  color: var(--on-overlay);
}

.body {
  display: grid;
  gap: var(--space-2);
  padding: 10px;
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

.meta-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

/*
 * 价格用橙色，字号 20px + 700 字重 —— 达到 WCAG「大字号」门槛，
 * 才允许用对比度 3.78:1 的 --price（见 DESIGN.md §3.4 约束 1）。
 * 字号降到 20px 以下就必须换成 --price-ink。
 */
.price {
  color: var(--price);
  font-size: var(--text-lg);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.duration {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}
</style>
