<template>
  <span class="avatar" :style="{ width: `${size}px`, height: `${size}px` }" aria-hidden="true">
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
  }>(),
  { src: '', name: '', size: 32 },
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
  border-radius: 50%;
  background: var(--brand-soft);
  box-shadow: var(--neu-raise-sm);
  color: var(--brand);
  font-size: 0.82em;
  font-weight: 750;
}

img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
