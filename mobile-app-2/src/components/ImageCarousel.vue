<template>
  <div class="image-carousel" :style="containerStyle" @touchstart="onTouchStart" @touchmove="onTouchMove" @touchend="onTouchEnd">
    <div v-if="loadingRatio" class="carousel-skeleton" />

    <template v-else>
      <div class="carousel-track" :style="trackStyle">
        <div v-for="(url, index) in images" :key="index" class="carousel-slide">
          <img :src="url" :alt="`${altPrefix} ${index + 1}`" draggable="false" />
        </div>
      </div>

      <span v-if="images.length > 1" class="carousel-counter">{{ currentIndex + 1 }}/{{ images.length }}</span>

      <template v-if="images.length > 1">
        <button v-if="currentIndex > 0" class="carousel-arrow carousel-prev pressable" aria-label="上一张" @click.stop="prev">
          <ChevronLeft :size="20" />
        </button>
        <button v-if="currentIndex < images.length - 1" class="carousel-arrow carousel-next pressable" aria-label="下一张" @click.stop="next">
          <ChevronRight :size="20" />
        </button>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  images: string[]
  altPrefix?: string
}>(), {
  altPrefix: '图片',
})

const currentIndex = ref(0)
const loadingRatio = ref(true)
const containerAspect = ref('4 / 5')
const dragging = ref(false)
const dragOffset = ref(0)
const touchStartX = ref(0)

const containerStyle = computed(() => ({
  aspectRatio: containerAspect.value,
}))

const trackStyle = computed(() => {
  const base = -(currentIndex.value * 100)
  const offsetPercent = dragging.value && imagesCount.value > 1
    ? (dragOffset.value / (typeof document !== 'undefined' ? document.documentElement.clientWidth : 375)) * 100
    : 0
  return {
    transform: `translateX(${base + offsetPercent}%)`,
    transition: dragging.value ? 'none' : 'transform 0.3s ease',
  }
})

const imagesCount = computed(() => props.images.length)

/** 按首图比例定容器高度，夹在 9/16 – 16/9 之间，避免极端长图撑破首屏 */
function loadFirstImageRatio() {
  loadingRatio.value = true
  const url = props.images[0]
  if (!url) {
    loadingRatio.value = false
    return
  }
  const img = new Image()
  img.onload = () => {
    const ratio = img.naturalWidth / img.naturalHeight
    const minRatio = 9 / 16
    const maxRatio = 16 / 9
    if (ratio > maxRatio) {
      containerAspect.value = '16 / 9'
    } else if (ratio < minRatio) {
      containerAspect.value = '9 / 16'
    } else {
      containerAspect.value = `${img.naturalWidth} / ${img.naturalHeight}`
    }
    loadingRatio.value = false
  }
  img.onerror = () => {
    loadingRatio.value = false
  }
  img.src = url
}

function onTouchStart(event: TouchEvent) {
  if (imagesCount.value <= 1) return
  touchStartX.value = event.touches[0].clientX
  dragging.value = true
  dragOffset.value = 0
}

function onTouchMove(event: TouchEvent) {
  if (!dragging.value) return
  dragOffset.value = event.touches[0].clientX - touchStartX.value
}

function onTouchEnd() {
  if (!dragging.value) return
  dragging.value = false
  const threshold = 50
  if (dragOffset.value < -threshold && currentIndex.value < imagesCount.value - 1) {
    currentIndex.value++
  } else if (dragOffset.value > threshold && currentIndex.value > 0) {
    currentIndex.value--
  }
  dragOffset.value = 0
}

function prev() {
  if (currentIndex.value > 0) currentIndex.value--
}

function next() {
  if (currentIndex.value < imagesCount.value - 1) currentIndex.value++
}

watch(() => props.images, () => {
  currentIndex.value = 0
  loadFirstImageRatio()
}, { immediate: false })

onMounted(() => loadFirstImageRatio())
</script>

<style scoped>
/* 通栏图铺满首屏宽度，角标与浮钮压在图上 */
.image-carousel {
  position: relative;
  overflow: hidden;
  background: var(--surface-secondary);
  user-select: none;
  -webkit-user-select: none;
}

.carousel-skeleton {
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    var(--surface-secondary) 25%,
    var(--surface-tertiary) 50%,
    var(--surface-secondary) 75%
  );
  background-size: 200% 100%;
  animation: carousel-shimmer 1.4s infinite;
}

@keyframes carousel-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.carousel-track {
  display: flex;
  height: 100%;
  will-change: transform;
}

.carousel-slide {
  flex: 0 0 100%;
  height: 100%;
}

.carousel-slide img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* 计数角标：与 WorkCard 的图上角标同一套配色 */
.carousel-counter {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  padding: 3px 9px;
  border-radius: var(--radius-pill);
  background: var(--surface-overlay);
  color: var(--on-overlay);
  font-size: var(--text-xs);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.5;
  pointer-events: none;
}

.carousel-arrow {
  position: absolute;
  top: 50%;
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  transform: translateY(-50%);
  border: 0;
  border-radius: var(--radius-pill);
  background: var(--surface-overlay);
  color: var(--on-overlay);
}

.carousel-prev { left: var(--space-2); }
.carousel-next { right: var(--space-2); }

/* 减少动态效果时骨架不做流动 */
@media (prefers-reduced-motion: reduce) {
  .carousel-skeleton { animation: none; }
}
</style>
