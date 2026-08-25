<template>
  <section ref="panelRef" class="comments-panel" :class="{ 'hide-composer': hideComposer }">
    <div class="comments-header">
      <h3 class="section-title">评论</h3>
      <span class="comment-total">{{ total }}</span>
    </div>

    <div v-if="!hideComposer" class="comment-composer">
      <el-input
        ref="inputRef"
        v-model="draft"
        type="textarea"
        :rows="3"
        resize="none"
        maxlength="500"
        show-word-limit
        placeholder="写下你的想法"
        class="comment-input"
      />
      <div class="composer-actions">
        <el-button type="primary" size="small" :loading="submitting" @click="submitComment">
          发表评论
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="comment-loading">
      <el-skeleton :rows="2" animated />
    </div>

    <div v-else-if="!comments.length" class="comment-empty">
      暂无评论
    </div>

    <div v-else class="comment-list">
      <article v-for="comment in comments" :key="comment.id" class="comment-item">
        <el-avatar :size="32" :src="getFullUrl(comment.user_avatar_url)" class="comment-avatar">
          {{ getInitial(comment.user_display_name) }}
        </el-avatar>
        <div class="comment-body">
          <div class="comment-meta">
            <span class="comment-name">{{ comment.user_display_name || '用户' }}</span>
            <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
          </div>
          <p class="comment-content">{{ comment.content }}</p>
        </div>
      </article>
    </div>

    <el-button
      v-if="comments.length < total"
      text
      class="load-more"
      :loading="loadingMore"
      @click="loadMore"
    >
      查看更多
    </el-button>
  </section>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createComment, getComments } from '@/api/comment'

const props = defineProps({
  targetType: { type: String, required: true },
  targetId: { type: String, required: true },
  hideComposer: { type: Boolean, default: false },
})

const emit = defineEmits(['count-change'])

const router = useRouter()
const panelRef = ref(null)
const inputRef = ref(null)
const comments = ref([])
const total = ref(0)
const draft = ref('')
const loading = ref(false)
const loadingMore = ref(false)
const submitting = ref(false)
const PAGE_SIZE = 20

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getInitial = (name) => {
  return String(name || '?').slice(0, 1)
}

const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const updateTotal = (nextTotal) => {
  total.value = Math.max(0, Number(nextTotal || 0))
  emit('count-change', total.value)
}

const fetchComments = async ({ append = false } = {}) => {
  if (!props.targetType || !props.targetId) return
  const skip = append ? comments.value.length : 0

  if (append) {
    loadingMore.value = true
  } else {
    loading.value = true
  }

  try {
    const { data } = await getComments(props.targetType, props.targetId, skip, PAGE_SIZE)
    const nextItems = data.items || []
    comments.value = append ? [...comments.value, ...nextItems] : nextItems
    updateTotal(data.total)
  } catch {
    if (!append) {
      comments.value = []
      updateTotal(0)
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

const loadMore = () => {
  if (loadingMore.value || comments.value.length >= total.value) return
  fetchComments({ append: true })
}

const submitComment = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再评论')
    router.push('/login')
    return
  }

  const content = draft.value.trim()
  if (!content) {
    ElMessage.warning('请输入评论内容')
    return
  }
  if (submitting.value) return

  submitting.value = true
  try {
    const { data } = await createComment(props.targetType, props.targetId, content)
    comments.value = [data, ...comments.value]
    draft.value = ''
    updateTotal(total.value + 1)
    ElMessage.success('评论已发布')
  } finally {
    submitting.value = false
  }
}

const focusComposer = async () => {
  await nextTick()
  panelRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  window.setTimeout(() => {
    inputRef.value?.focus?.()
  }, 240)
}

watch(
  () => [props.targetType, props.targetId],
  () => {
    comments.value = []
    updateTotal(0)
    fetchComments()
  },
  { immediate: true },
)

defineExpose({ focusComposer })
</script>

<style scoped>
.comments-panel {
  flex: 0 0 auto;
  border-top: 1px solid var(--color-divider);
  margin-top: 20px;
  padding-top: 20px;
}
.comments-panel.hide-composer {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.comments-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.comment-total {
  min-width: 28px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-size: 12px;
  text-align: center;
}

.comment-composer {
  margin-bottom: 16px;
}

.comment-input :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.6;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.comment-loading {
  padding: 6px 0 12px;
}

.comment-empty {
  color: var(--color-ink-tertiary);
  font-size: 13px;
  line-height: 1.8;
  padding: 6px 0 2px;
}

.comment-list {
  display: flex;
  flex-direction: column;
}

.comment-item {
  display: flex;
  gap: 10px;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-divider);
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-avatar {
  flex: 0 0 auto;
}

.comment-body {
  min-width: 0;
  flex: 1;
}

.comment-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.comment-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-ink);
  font-size: 13px;
  font-weight: 600;
}

.comment-time {
  flex: 0 0 auto;
  color: var(--color-ink-tertiary);
  font-size: 12px;
}

.comment-content {
  color: var(--color-ink-secondary);
  font-size: 13px;
  line-height: 1.7;
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.load-more {
  width: 100%;
  margin-top: 4px;
}
</style>
