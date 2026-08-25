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
        <span v-if="offer.city" class="location-pill">
          <MapPin :size="12" aria-hidden="true" />
          {{ offer.city }}
        </span>
      </div>

      <div class="body">
        <h3>{{ getPackageName(offer) }}</h3>
        <div class="meta-row">
          <span class="author">
            <AvatarImage :src="offer.photographer_avatar" :name="offer.photographer_name" :size="25" />
            <span>{{ offer.photographer_name || '摄影师' }}</span>
          </span>
          <div class="price-duration">
            <strong>{{ formatCurrency(offer.price) }}</strong>
          </div>
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
import { formatCurrency, getPackageName } from '@/utils/format'
import { getPackagePreviewUrl } from '@/utils/media'

const props = defineProps<{
  offer: PackageOffer
}>()

defineEmits<{
  open: [offer: PackageOffer]
}>()

const imageFailed = ref(false)
const preview = computed(() => getPackagePreviewUrl(props.offer))

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
.package-card {
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

.location-pill {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: calc(100% - 16px);
  padding: 4px 7px;
  border-radius: var(--radius-pill);
  background: rgba(26, 26, 26, 0.76);
  color: var(--white);
  font-size: 10px;
}

.body {
  padding: 10px;
}

h3 {
  display: -webkit-box;
  margin: 0 0 6px;
  overflow: hidden;
  font-size: var(--text-sm);
  font-weight: 700;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--neu-light);
  box-shadow: inset 0 1px 0 var(--neu-shade-soft);
}

.author {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
  color: var(--ink-secondary);
  font-size: 11px;
}

.author > span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.price-duration strong {
  color: var(--brand);
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

</style>
