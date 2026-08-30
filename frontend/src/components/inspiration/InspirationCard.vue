<template>
  <article class="card" tabindex="0" @click="open" @keydown.enter="open">
    <div class="cover">
      <img v-if="item.cover_url" :src="item.cover_url" :alt="`${item.title}封面`" width="480" height="320" loading="lazy" />
      <ImageIcon v-else :size="32" aria-hidden="true" />
      <span class="status">{{ item.status === 'draft' ? '草稿' : '已保存' }}</span>
    </div>
    <div class="body">
      <div class="meta"><span v-if="item.location_name"><MapPin :size="15" />{{ item.location_name }}</span><time>{{ formatDate(item.updated_at) }}</time></div>
      <h2>{{ item.title }}</h2>
      <p>{{ item.summary || textPreview || '还没有摘要，打开继续补充你的想法。' }}</p>
      <div v-if="item.tags?.length" class="tags"><span v-for="tag in item.tags.slice(0, 4)" :key="tag">{{ tag }}</span></div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Image as ImageIcon, MapPin } from 'lucide-vue-next'
const props = defineProps({ item: { type:Object, required:true } })
const router = useRouter()
const open = () => router.push(`/inspirations/${props.item.id}`)
const textPreview = computed(() => props.item.content?.find(block => block.text)?.text || '')
const formatDate = value => value ? new Intl.DateTimeFormat('zh-CN',{month:'short',day:'numeric'}).format(new Date(value)) : ''
</script>

<style scoped>
.card { overflow:hidden; border:var(--border-default); border-radius:var(--radius-lg); background:var(--color-paper-light); cursor:pointer; transition:border-color 180ms ease,transform 180ms ease; }
.card:hover,.card:focus-visible{border-color:var(--color-brand);transform:translateY(-2px)}
.cover{position:relative;display:grid;place-items:center;aspect-ratio:3/2;background:var(--color-brand-light);color:var(--color-brand)}
.cover img{width:100%;height:100%;object-fit:cover}.status{position:absolute;top:12px;right:12px;padding:4px 9px;background:rgba(255,253,249,.94);border:var(--border-default);font-size:12px;font-weight:700}
.body{padding:18px}.meta{display:flex;justify-content:space-between;gap:12px;color:var(--color-ink-tertiary);font-size:var(--text-xs)}.meta span{display:flex;align-items:center;gap:4px;color:var(--color-brand)}
h2{margin:10px 0 6px;font-size:var(--text-xl);line-height:1.35}p{margin:0;color:var(--color-ink-secondary);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}.tags span{padding:3px 8px;background:var(--color-paper);color:var(--color-ink-secondary);font-size:12px}
</style>
