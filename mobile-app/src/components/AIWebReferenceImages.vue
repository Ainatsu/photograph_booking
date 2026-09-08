<template>
  <section v-if="items.length" class="web-reference" aria-label="联网搜索参考图片">
    <div class="web-reference-grid">
      <a v-for="(item, index) in items" :key="`${item.image_url}-${index}`" class="web-reference-image-link" :href="item.source_url" target="_blank" rel="noopener noreferrer" :aria-label="`打开来源网页：${item.title || item.domain || '网页来源'}`">
        <img :src="item.image_url" :alt="item.alt || item.title || '网页参考图片'" loading="lazy" />
      </a>
    </div>
    <div class="web-reference-sources" :class="{ 'is-expanded': expanded }">
      <button v-if="!expanded" type="button" class="web-reference-source-toggle" aria-label="展开全部网页来源" @click="expanded = true">
        <span class="web-reference-url">{{ items[0].source_url }}</span>
        <span v-if="items.length > 1" class="web-reference-more">+{{ items.length - 1 }} 个来源</span>
      </button>
      <template v-else>
        <a v-for="(item, index) in items" :key="`source-${item.source_url}-${index}`" class="web-reference-url web-reference-url-link" :href="item.source_url" target="_blank" rel="noopener noreferrer">{{ item.source_url }}</a>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ items: Array<{ image_url: string; source_url: string; title?: string; alt?: string; domain?: string }> }>()
const expanded = ref(false)
</script>

<style scoped>
.web-reference { width: 100%; margin-top: 10px; }
.web-reference-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.web-reference-image-link { display: block; min-width: 44px; aspect-ratio: 4 / 3; overflow: hidden; border-radius: var(--radius-sm); background: var(--paper-deep); box-shadow: var(--neu-inset); transition: opacity var(--motion-fast) ease-out, transform var(--motion-fast) ease-out; }
.web-reference-image-link:active { opacity: .78; transform: scale(.98); }
.web-reference-image-link img { width: 100%; height: 100%; object-fit: cover; }
.web-reference-sources { margin-top: 6px; color: var(--ink-tertiary); font-size: var(--text-2xs); line-height: 1.45; opacity: .72; }
.web-reference-source-toggle { display: flex; align-items: center; gap: 6px; width: 100%; min-height: 32px; padding: 4px 0; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; }
.web-reference-url { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.web-reference-more { flex-shrink: 0; color: var(--ink-secondary); }
.web-reference-url-link { display: block; min-height: 24px; padding: 3px 0; color: inherit; text-decoration: none; }
.web-reference-url-link:active, .web-reference-source-toggle:active { color: var(--brand); }
@media (prefers-reduced-motion: reduce) { .web-reference-image-link { transition: none; } }
</style>
