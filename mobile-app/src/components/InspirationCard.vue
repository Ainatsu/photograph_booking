<template>
  <article class="inspiration-card">
    <button type="button" class="card-main pressable" @click="$emit('open', item.id)">
    <div class="card-cover">
      <img v-if="previewUrl" :src="previewUrl" :alt="`${item.title}封面`" loading="lazy" />
      <ImageIcon v-else :size="28" aria-hidden="true" />
      <span>{{ item.status === 'draft' ? '草稿' : '已保存' }}</span>
    </div>
    <div class="card-copy">
      <div class="card-meta">
        <span v-if="item.location_name"><MapPin :size="14" aria-hidden="true" />{{ item.location_name }}</span>
        <time>{{ formattedDate }}</time>
      </div>
      <strong>{{ item.title }}</strong>
      <p>{{ item.summary || textPreview || '继续补充这条灵感的画面与想法。' }}</p>
      <div v-if="item.tags?.length" class="card-tags">
        <span v-for="tag in item.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
      </div>
    </div>
    </button>
    <div v-if="showActions" class="card-actions" aria-label="灵感快捷操作">
      <button type="button" class="card-action" aria-label="编辑灵感" @click.stop="$emit('edit', item.id)"><Pencil :size="18" aria-hidden="true" /></button>
      <button type="button" class="card-action delete" aria-label="删除灵感" @click.stop="$emit('delete', item.id)"><Trash2 :size="18" aria-hidden="true" /></button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Image as ImageIcon, MapPin, Pencil, Trash2 } from 'lucide-vue-next'
import type { Inspiration } from '@/types/inspiration'
import { resolveMediaUrl } from '@/utils/media'

const props = withDefaults(defineProps<{ item: Inspiration; showActions?: boolean }>(), { showActions: false })
defineEmits<{ open: [id: number]; edit: [id: number]; delete: [id: number] }>()

const textPreview = computed(() => props.item.content?.find((block) => block.text)?.text || '')
const previewUrl = computed(() => {
  const cover = props.item.cover_url || props.item.content?.find((block) => block.type === 'image' && (block.thumb_url || block.url))
  return resolveMediaUrl(typeof cover === 'string' ? cover : cover?.thumb_url || cover?.url)
})
const formattedDate = computed(() => new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric' }).format(new Date(props.item.updated_at)))
</script>

<style scoped>
.inspiration-card { display: grid; grid-template-columns: minmax(0, 1fr) auto; width: 100%; min-height: 148px; overflow: hidden; border-radius: var(--radius-lg); background: var(--surface-solid); box-shadow: var(--shadow-1); color: var(--ink); text-align: left; }
.card-main { display: grid; grid-template-columns: 116px minmax(0, 1fr); min-width: 0; padding: 0; border: 0; background: transparent; color: inherit; text-align: left; }
.card-cover { position: relative; display: grid; min-height: 148px; place-items: center; overflow: hidden; background: var(--brand-soft); color: var(--brand); }
.card-cover img { width: 100%; height: 100%; object-fit: cover; }
.card-cover > span { position: absolute; top: 9px; left: 9px; min-height: 24px; padding: 3px 8px; border-radius: var(--radius-pill); background: var(--material-thick); color: var(--ink); font-size: var(--text-2xs); font-weight: 750; backdrop-filter: var(--material-blur); }
.card-copy { display: grid; align-content: center; gap: 6px; min-width: 0; padding: var(--space-3); }
.card-meta { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); color: var(--ink-tertiary); font-size: var(--text-2xs); }
.card-meta span { display: flex; min-width: 0; align-items: center; gap: 3px; overflow: hidden; color: var(--brand); text-overflow: ellipsis; white-space: nowrap; }
.card-copy > strong { overflow: hidden; font-size: var(--text-base); line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.card-copy > p { display: -webkit-box; overflow: hidden; margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.card-tags { display: flex; gap: 5px; overflow: hidden; }
.card-tags span { flex: 0 0 auto; padding: 2px 7px; border-radius: var(--radius-pill); background: var(--surface-secondary); color: var(--ink-secondary); font-size: var(--text-2xs); }
.card-actions { display: grid; width: 48px; grid-template-rows: 1fr 1fr; border-left: 1px solid var(--border); background: var(--surface-secondary); }
.card-action { display: grid; min-width: 48px; min-height: 48px; place-items: center; border: 0; background: transparent; color: var(--brand); cursor: pointer; touch-action: manipulation; }
.card-action + .card-action { border-top: 1px solid var(--border); }
.card-action.delete { color: var(--danger); }
.card-action:active { background: var(--brand-soft); }
@media (max-width: 380px) { .card-main { grid-template-columns: 100px minmax(0, 1fr); } }
</style>
