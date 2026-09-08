<template>
  <article class="bookable-card">
    <header class="bookable-card__header">
      <div class="photographer">
        <img v-if="item.photographer_avatar" :src="resolveMediaUrl(item.photographer_avatar)" :alt="`${item.photographer_name || '摄影师'}头像`" />
        <span v-else aria-hidden="true">{{ (item.photographer_name || '摄')[0] }}</span>
        <div>
          <strong>{{ item.photographer_name || '摄影师' }}</strong>
          <small><MapPin :size="13" aria-hidden="true" />{{ item.distance_label || '同城，距离未知' }}</small>
        </div>
      </div>
      <b>¥{{ formatPrice(item.price) }}</b>
    </header>

    <div class="bookable-card__body">
      <h3>{{ item.package_name }}</h3>
      <p class="duration"><Clock3 :size="14" aria-hidden="true" />约 {{ item.duration }} 分钟</p>
      <div v-if="item.styles?.length" class="tags" aria-label="风格标签">
        <span v-for="style in item.styles.slice(0, 3)" :key="style">{{ style }}</span>
      </div>
      <p v-if="snapshotExpired" class="warning"><AlertTriangle :size="14" aria-hidden="true" />档期快照已过期，需要刷新</p>
      <p v-else-if="firstSlot" class="availability"><CalendarCheck2 :size="15" aria-hidden="true" />最近可约：{{ firstSlot.date || firstSlot.label }}</p>
      <p v-else class="availability availability--unknown"><CalendarX2 :size="15" aria-hidden="true" />暂未返回匹配日期</p>
      <p v-if="primaryReason" class="reason">{{ primaryReason }}</p>
      <p v-for="warning in item.warnings || []" :key="warning" class="warning"><AlertTriangle :size="14" aria-hidden="true" />{{ warning }}</p>
    </div>

    <footer class="bookable-card__actions">
      <button type="button" class="secondary" @click="$emit('details', item)">查看详情</button>
      <button type="button" class="primary" @click="primaryAction">{{ snapshotExpired ? '刷新档期' : '选择日期' }}</button>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, CalendarCheck2, CalendarX2, Clock3, MapPin } from 'lucide-vue-next'
import type { BookablePackageRecommendation } from '@/api/recommendations'
import { resolveMediaUrl } from '@/utils/media'

const props = defineProps<{ item: BookablePackageRecommendation }>()
const emit = defineEmits<{ details: [item: BookablePackageRecommendation]; 'select-time': [item: BookablePackageRecommendation]; refresh: [item: BookablePackageRecommendation] }>()

const firstSlot = computed(() => props.item.availability?.matching_slots?.[0] || null)
const primaryReason = computed(() => props.item.recommendation_reasons?.[0] || '')
const snapshotExpired = computed(() => Boolean(props.item.availability?.snapshot_expires_at && new Date(props.item.availability.snapshot_expires_at).getTime() <= Date.now()))
const formatPrice = (value: number) => Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
function primaryAction() {
  if (snapshotExpired.value) emit('refresh', props.item)
  else emit('select-time', props.item)
}
</script>

<style scoped>
.bookable-card { display: grid; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--ink); }
.bookable-card__header, .bookable-card__actions { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.photographer { display: flex; min-width: 0; align-items: center; gap: var(--space-3); }
.photographer > img, .photographer > span { display: grid; width: 40px; height: 40px; flex: 0 0 40px; place-items: center; border-radius: 50%; background: var(--brand-soft); color: var(--brand); object-fit: cover; font-weight: 750; }
.photographer div { display: grid; min-width: 0; gap: 2px; }
.photographer strong { overflow: hidden; font-size: var(--text-sm); text-overflow: ellipsis; white-space: nowrap; }
.photographer small { display: flex; align-items: center; gap: 4px; color: var(--ink-secondary); font-size: var(--text-xs); }
.bookable-card__header > b { color: var(--brand); font-size: var(--text-lg); font-variant-numeric: tabular-nums; }
.bookable-card__body { display: grid; gap: var(--space-2); }
h3, p { margin: 0; }
h3 { font-family: var(--font-serif); font-size: var(--text-base); line-height: 1.45; }
.duration, .availability, .warning { display: flex; align-items: center; gap: 6px; font-size: var(--text-xs); }
.duration { color: var(--ink-secondary); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tags span { padding: 4px 8px; border-radius: var(--radius-sm); background: var(--brand-soft); color: var(--brand-strong); font-size: var(--text-xs); }
.availability { color: var(--brand-strong); font-weight: 650; }
.availability--unknown { color: var(--ink-secondary); }
.reason { color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.55; }
.warning { color: var(--warning); }
.bookable-card__actions { padding-top: var(--space-2); border-top: 1px solid var(--divider); }
button { min-width: 0; min-height: var(--touch-target); flex: 1; border-radius: var(--radius-md); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; transition: background-color var(--motion-fast), border-color var(--motion-fast), color var(--motion-fast); }
button:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.secondary { border: 0; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink); }
.primary { border: 0; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
@media (prefers-reduced-motion: reduce) { button { transition: none; } }
</style>
