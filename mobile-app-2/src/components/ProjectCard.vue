<template>
  <article class="project-card">
    <button type="button" class="card-button pressable" @click="$emit('open', project)">
      <div class="top-row">
        <div class="top-info">
          <h3>{{ project.title }}</h3>
          <p>{{ project.description }}</p>
          <ul v-if="badges.length" class="tag-row">
            <li v-for="badge in badges" :key="badge.label" class="tag" :class="badge.tone">
              {{ badge.label }}
            </li>
          </ul>
        </div>
        <div v-if="firstRefImage" class="media">
          <img :src="firstRefImage" :alt="project.title" loading="lazy" />
        </div>
        <MediaPlaceholder v-else class="media placeholder" />
      </div>

      <div class="meta-row">
        <span class="who">
          <span class="customer">
            <AvatarImage
              :src="project.customer_avatar_url"
              :name="project.customer_name"
              :size="20"
              shape="rounded"
            />
            <span class="customer-name">{{ project.customer_name || '客户' }}</span>
          </span>
          <span class="location"><MapPin :size="12" aria-hidden="true" />{{ displayLocation }}</span>
        </span>

        <span class="amount">
          <strong class="price">{{ formatProjectBudget(project) }}</strong>
          <span v-if="deadlineText" class="deadline">{{ deadlineText }}截稿</span>
        </span>
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
import { formatProjectBudget, formatShortDate } from '@/utils/format'

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

/**
 * 参考图这里是「实名认证 / 信誉优良」这类资质徽章，但 ProjectBrief 没有对应字段。
 * 只用真实数据：风格标签走品牌色，应征人数走中性色。
 */
const badges = computed(() => {
  const items = (props.project.style_tags || []).slice(0, 2).map((label) => ({ label, tone: 'brand' }))
  const count = props.project.application_count
  if (count) items.push({ label: `已有 ${count} 位应征`, tone: 'neutral' })
  return items
})

const deadlineText = computed(() => {
  const value = props.project.expires_at
  if (!value) return ''
  const formatted = formatShortDate(value)
  return formatted === '时间待沟通' ? '' : `${formatted} `
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
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
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

/* 左文右图：参考图里企划列表行的基本形态 */
.top-row {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3);
}

.top-info {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 6px;
  align-content: start;
}

h3 {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  font-size: var(--text-base);
  font-weight: 700;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0;
  margin: 2px 0 0;
  list-style: none;
}

.tag {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  padding: 0 8px;
  border-radius: var(--radius-pill);
  font-size: var(--text-xs);
  font-weight: 700;
}

.tag.brand {
  background: var(--brand-soft);
  color: var(--brand);
}

.tag.neutral {
  background: var(--surface-secondary);
  color: var(--ink-secondary);
}

.media {
  width: 96px;
  flex: 0 0 auto;
  overflow: hidden;
  aspect-ratio: 1 / 1;
  border-radius: var(--radius-sm);
  background: var(--surface-secondary);
}

.media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.meta-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  margin: 0 var(--space-3);
  padding: var(--space-2) 0 var(--space-3);
  border-top: 1px solid var(--border);
}

.who,
.customer,
.location,
.amount,
.deadline {
  display: flex;
  align-items: center;
}

.who {
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.customer {
  min-width: 0;
  gap: 6px;
}

.customer-name {
  overflow: hidden;
  color: var(--ink-secondary);
  font-size: var(--text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.location {
  gap: 3px;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.amount {
  flex: 0 0 auto;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

/*
 * 预算用橙色，20px + 800 —— 达到「大字号」门槛才允许用 3.78:1 的 --price。
 * 小字场合（如上面 11px 的元信息）不得使用 --price。
 */
.price {
  color: var(--price);
  font-size: var(--text-lg);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.deadline {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}
</style>
