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
.media-placeholder {
  display: grid;
  width: 100%;
  height: 100%;
  place-items: center;
  align-content: center;
  gap: 6px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: var(--text-2xs);
}
</style>
