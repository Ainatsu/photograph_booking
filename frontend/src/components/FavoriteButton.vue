<template>
  <button
    class="fav-btn"
    :class="{ favorited: localFavorited, animating }"
    :disabled="loading"
    :title="localFavorited ? '取消收藏' : isPackage ? '收藏方案' : '收藏作品'"
    :aria-label="localFavorited ? '取消收藏' : isPackage ? '收藏方案' : '收藏作品'"
    @click="handleClick"
  >
    <Star
      :size="24"
      :fill="localFavorited ? 'currentColor' : 'none'"
      aria-hidden="true"
    />
  </button>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Star } from 'lucide-vue-next'
import { useFavoriteStore } from '@/stores/favorite'

const props = defineProps({
  targetType: { type: String, default: 'work' }, // 'work' | 'package'
  targetId: { type: String, required: true },
  photographerId: { type: Number, required: true },
  targetData: { type: Object, default: null },
})

const emit = defineEmits(['update'])

const router = useRouter()
const favStore = useFavoriteStore()
const loading = ref(false)
const animating = ref(false)

const isPackage = computed(() => props.targetType === 'package')

const localFavorited = computed(() =>
  isPackage.value
    ? favStore.getPkg(props.targetId)
    : favStore.get(props.targetId)
)

const handleClick = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再收藏')
    router.push('/login')
    return
  }

  if (loading.value) return

  loading.value = true
  animating.value = true
  setTimeout(() => {
    animating.value = false
  }, 200)

  try {
    let result
    if (isPackage.value) {
      result = await favStore.togglePkg(props.targetId, props.photographerId, props.targetData)
    } else {
      result = await favStore.toggle(props.targetId, props.photographerId, props.targetData)
    }
    emit('update', result)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.fav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: var(--radius-sm);
  color: var(--color-ink-tertiary);
  transition: color 0.15s ease, background-color 0.15s ease;
  user-select: none;
  line-height: 1;
}

.fav-btn:hover {
  color: #8B6914;
  background: transparent;
}

.fav-btn.favorited {
  color: #8B6914;
}

.fav-btn.animating {
  /* subtle indication without layout shift */
}

.fav-btn:disabled {
  pointer-events: none;
  opacity: 0.6;
}
</style>
