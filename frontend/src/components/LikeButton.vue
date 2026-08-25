<template>
  <button
    class="like-btn"
    :class="{ liked: localLiked, animating }"
    :disabled="loading"
    :title="localLiked ? '取消点赞' : '点赞'"
    :aria-label="localLiked ? '取消点赞' : '点赞'"
    @click="handleClick"
  >
    <Heart
      class="like-icon"
      :size="20"
      :fill="localLiked ? 'currentColor' : 'none'"
      aria-hidden="true"
    />
    <span class="like-count">{{ localCount }}</span>
  </button>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Heart } from 'lucide-vue-next'
import { useLikeStore } from '@/stores/like'

const props = defineProps({
  targetType: { type: String, required: true },
  targetId: { type: String, required: true },
  liked: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
})

const emit = defineEmits(['update'])

const router = useRouter()
const likeStore = useLikeStore()
const localLiked = computed(() => likeStore.get(props.targetType, props.targetId).liked)
const localCount = computed(() => likeStore.get(props.targetType, props.targetId).count)
const loading = ref(false)
const animating = ref(false)

const handleClick = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再点赞')
    router.push('/login')
    return
  }

  if (loading.value) return

  loading.value = true
  animating.value = true
  setTimeout(() => {
    animating.value = false
  }, 150)

  try {
    const next = await likeStore.toggle(props.targetType, props.targetId)
    emit('update', next)
  } catch {
    emit('update', {
      liked: localLiked.value,
      count: localCount.value,
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.like-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 14px;
  color: var(--color-ink-tertiary);
  transition: color 0.15s ease;
  user-select: none;
  min-height: 32px;
}

.like-btn:hover {
  color: #C53030;
}

.like-btn.liked {
  color: #C53030;
}

.like-btn.animating {
  /* subtle pulse without layout shift */
}

.like-btn:disabled {
  pointer-events: none;
  opacity: 0.6;
}

.like-icon {
  flex-shrink: 0;
}

.like-count {
  font-size: 13px;
}
</style>
