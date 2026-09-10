<template>
  <div class="media-placeholder" aria-hidden="true">
    <Image :size="24" />
    <span>暂无预览</span>
  </div>
</template>

<script setup lang="ts">
import { Image } from 'lucide-vue-next'
</script>

<style scoped>
/* 中性灰，不用品牌色——占位块不该在画廊里抢注意力 */
.media-placeholder {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  align-content: center;
  gap: 6px;
  background: var(--surface-secondary);
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}
</style>
