<template>
  <el-button
    :type="isFollowing ? 'default' : 'primary'"
    :size="size"
    :loading="loading"
    :disabled="disabled"
    @click.stop="handleToggle"
    class="follow-btn"
  >
    {{ isFollowing ? '取消关注' : '关注' }}
  </el-button>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useFollowStore } from '@/stores/follow'

const props = defineProps({
  userId: { type: Number, required: true },
  disabled: { type: Boolean, default: false },
  size: { type: String, default: 'default' },
})

const emit = defineEmits(['toggled'])
const store = useFollowStore()
const loading = ref(false)

const isFollowing = computed(() => store.isFollowing(props.userId))

const handleToggle = async () => {
  loading.value = true
  try {
    const result = await store.toggle(props.userId)
    emit('toggled', result)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  store.loadStatus(props.userId)
})
</script>
