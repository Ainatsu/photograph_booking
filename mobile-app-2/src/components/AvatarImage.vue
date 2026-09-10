<template>
  <span
    class="avatar"
    :class="`shape-${shape}`"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <img v-if="source && !failed" :src="source" alt="" @error="failed = true" />
    <span v-else>{{ initials }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { resolveMediaUrl } from '@/utils/media'

const props = withDefaults(
  defineProps<{
    src?: string | null
    name?: string | null
    size?: number
    /**
     * 圆形用于详情页、点评、摄影师主页头部；
     * 圆角方形用于列表里的作者行（发现 / 橱窗 / 搜索），与参考图一致。
     */
    shape?: 'circle' | 'rounded'
  }>(),
  { src: '', name: '', size: 32, shape: 'circle' },
)

const failed = ref(false)
const source = computed(() => resolveMediaUrl(props.src))
const initials = computed(() => (props.name || '约').trim().slice(0, 1).toUpperCase())

watch(source, () => {
  failed.value = false
})
</script>

<style scoped>
.avatar {
  display: inline-grid;
  flex: 0 0 auto;
  overflow: hidden;
  place-items: center;
  border: 0;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 0.82em;
  font-weight: 750;
}

.shape-circle {
  border-radius: 50%;
}

.shape-rounded {
  border-radius: var(--radius-sm);
}

img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
