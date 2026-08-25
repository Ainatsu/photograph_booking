<template>
  <transition name="btt-fade">
    <div
      v-if="visible"
      class="back-to-top"
      :class="{ 'btt-small': size === 'small' }"
      @click="scrollToTop"
    >
      <el-icon :size="iconSize"><Top /></el-icon>
    </div>
  </transition>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ArrowUp as Top } from 'lucide-vue-next'

const props = defineProps({
  threshold: { type: Number, default: 300 },
  size: { type: String, default: 'default' },
})

const visible = ref(false)
const iconSize = computed(() => props.size === 'small' ? 20 : 24)

const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const onScroll = () => {
  visible.value = window.scrollY > props.threshold
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.back-to-top {
  position: fixed;
  z-index: 999;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  border: var(--border-default);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--color-ink-secondary);
  transition: color 0.15s ease, border-color 0.15s ease, background-color 0.15s ease, opacity 0.25s ease;
  user-select: none;
}
.back-to-top:hover {
  color: var(--color-brand);
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.back-to-top.btt-small {
  width: 36px;
  height: 36px;
}

.btt-fade-enter-active,
.btt-fade-leave-active {
  transition: opacity 0.25s ease;
}
.btt-fade-enter-from,
.btt-fade-leave-to {
  opacity: 0;
}
</style>
