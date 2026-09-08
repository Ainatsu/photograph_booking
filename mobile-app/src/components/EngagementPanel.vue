<template>
  <section class="engagement-panel" :aria-labelledby="headingId">
    <div v-if="!compact" class="engagement-actions" aria-label="内容互动">
      <button
        type="button"
        class="engagement-action pressable"
        :class="{ active: likeSummary.liked }"
        :aria-pressed="likeSummary.liked"
        :aria-label="likeSummary.liked ? `取消点赞，当前 ${likeSummary.count} 个赞` : `点赞，当前 ${likeSummary.count} 个赞`"
        :disabled="likeLoading"
        @click="handleLike"
      >
        <ion-spinner v-if="likeLoading" name="crescent" aria-hidden="true" />
        <Heart v-else :size="21" :fill="likeSummary.liked ? 'currentColor' : 'none'" aria-hidden="true" />
        <span>{{ likeSummary.liked ? '已点赞' : '点赞' }}</span>
        <strong>{{ likeSummary.count }}</strong>
      </button>

      <button
        type="button"
        class="engagement-action pressable"
        :aria-label="`查看评论，当前 ${commentTotal} 条`"
        @click="focusComposer"
      >
        <MessageCircle :size="21" aria-hidden="true" />
        <span>评论</span>
        <strong>{{ commentTotal }}</strong>
      </button>
    </div>

    <div class="comments-heading">
      <h2 :id="headingId">评论</h2>
      <span>{{ commentTotal }} 条</span>
    </div>

    <div v-if="!compact && !auth.isAuthenticated" class="guest-composer">
      <div>
        <strong>登录后参与讨论</strong>
        <p>评论会同步到网页端，并保留在你的账号下。</p>
      </div>
      <button type="button" class="login-comment-button pressable" @click="goLogin">
        登录后评论
      </button>
    </div>

    <form v-else-if="!compact" ref="composerRef" class="comment-composer" @submit.prevent="submitComment">
      <label :for="composerId">写下你的想法</label>
      <textarea
        :id="composerId"
        ref="textareaRef"
        v-model="draft"
        rows="4"
        maxlength="500"
        placeholder="聊聊你喜欢的画面、风格或服务细节"
        :disabled="submitting"
        :aria-invalid="Boolean(composerError)"
        :aria-describedby="composerError ? `${composerId}-error` : undefined"
        @input="composerError = ''"
      />
      <div class="composer-footer">
        <span :class="{ warning: draft.length >= 460 }">{{ draft.length }}/500</span>
        <button type="submit" class="submit-comment pressable" :disabled="submitting || !draft.trim()">
          <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
          <Send v-else :size="17" aria-hidden="true" />
          {{ submitting ? '发布中' : '发表评论' }}
        </button>
      </div>
      <p v-if="composerError" :id="`${composerId}-error`" class="composer-error" role="alert">
        {{ composerError }}
      </p>
    </form>

    <div class="comment-list-wrap" aria-live="polite">
      <div v-if="commentsLoading" class="comment-skeleton-list" aria-label="正在加载评论" aria-busy="true">
        <article v-for="index in 2" :key="index" class="comment-skeleton">
          <span />
          <div><i /><i /><i /></div>
        </article>
      </div>

      <div v-else-if="commentsError && !comments.length" class="comments-error" role="alert">
        <p>{{ commentsError }}</p>
        <button type="button" class="retry-comments pressable" @click="loadComments()">重试</button>
      </div>

      <p v-else-if="!comments.length" class="comments-empty">还没有评论，来留下第一条想法吧。</p>

      <div v-else class="comment-list">
        <article v-for="comment in comments" :key="comment.id" class="comment-item">
          <AvatarImage :src="comment.user_avatar_url" :name="comment.user_display_name" :size="36" />
          <div>
            <header>
              <strong>{{ comment.user_display_name || '用户' }}</strong>
              <time v-if="comment.created_at" :datetime="comment.created_at">
                {{ formatEngagementTime(comment.created_at) }}
              </time>
            </header>
            <p>{{ comment.content }}</p>
          </div>
        </article>

        <button
          v-if="comments.length < commentTotal"
          type="button"
          class="load-more-comments pressable"
          :disabled="loadingMore"
          @click="loadComments(true)"
        >
          <ion-spinner v-if="loadingMore" name="crescent" aria-hidden="true" />
          {{ loadingMore ? '加载中' : `查看更多（剩余 ${commentTotal - comments.length} 条）` }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonSpinner } from '@ionic/vue'
import { Heart, MessageCircle, Send } from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import { createComment, getComments, getLikeSummary, toggleLike } from '@/api/engagement'
import { getApiErrorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import type { CommentItem, EngagementTargetType, LikeSummary } from '@/types/engagement'
import { formatEngagementTime } from '@/utils/engagement'

const props = defineProps<{
  targetType: EngagementTargetType
  targetId: string
  compact?: boolean
}>()

const emit = defineEmits<{
  message: [value: string]
}>()

const PAGE_SIZE = 20
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const likeSummary = ref<LikeSummary>({ liked: false, count: 0 })
const likeLoading = ref(false)
const comments = ref<CommentItem[]>([])
const commentTotal = ref(0)
const commentsLoading = ref(true)
const loadingMore = ref(false)
const commentsError = ref('')
const draft = ref('')
const submitting = ref(false)
const composerError = ref('')
const composerRef = ref<HTMLFormElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const safeTargetId = computed(() => props.targetId.replace(/[^a-zA-Z0-9_-]/g, '-'))
const headingId = computed(() => `comments-${props.targetType}-${safeTargetId.value}`)
const composerId = computed(() => `${headingId.value}-composer`)

async function loadLike() {
  try {
    likeSummary.value = await getLikeSummary(props.targetType, props.targetId)
  } catch {
    likeSummary.value = { liked: false, count: 0 }
  }
}

async function loadComments(append = false) {
  if (append) loadingMore.value = true
  else commentsLoading.value = true
  commentsError.value = ''
  try {
    const result = await getComments(
      props.targetType,
      props.targetId,
      append ? comments.value.length : 0,
      PAGE_SIZE,
    )
    comments.value = append ? [...comments.value, ...(result.items || [])] : (result.items || [])
    commentTotal.value = Math.max(0, Number(result.total || comments.value.length))
  } catch (error) {
    commentsError.value = getApiErrorMessage(error)
    if (!append) {
      comments.value = []
      commentTotal.value = 0
    }
  } finally {
    commentsLoading.value = false
    loadingMore.value = false
  }
}

async function handleLike() {
  if (likeLoading.value) return
  if (!auth.isAuthenticated) {
    await goLogin()
    return
  }
  likeLoading.value = true
  try {
    likeSummary.value = await toggleLike(props.targetType, props.targetId)
    emit('message', likeSummary.value.liked ? '已点赞' : '已取消点赞')
  } catch (error) {
    emit('message', getApiErrorMessage(error))
  } finally {
    likeLoading.value = false
  }
}

async function submitComment() {
  const content = draft.value.trim()
  if (!content) {
    composerError.value = '请输入评论内容。'
    return
  }
  if (submitting.value) return
  submitting.value = true
  composerError.value = ''
  try {
    const comment = await createComment(props.targetType, props.targetId, content)
    comments.value = [comment, ...comments.value.filter((item) => item.id !== comment.id)]
    commentTotal.value += 1
    draft.value = ''
    emit('message', '评论已发布')
  } catch (error) {
    composerError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

async function goLogin() {
  await router.push({ name: 'login', query: { redirect: route.fullPath } })
}

async function focusComposer() {
  if (!auth.isAuthenticated) {
    await goLogin()
    return
  }
  await nextTick()
  composerRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  window.setTimeout(() => textareaRef.value?.focus(), 220)
}

watch(
  () => [props.targetType, props.targetId],
  () => {
    comments.value = []
    commentTotal.value = 0
    const tasks = props.compact ? [loadComments()] : [loadLike(), loadComments()]
    void Promise.all(tasks)
  },
  { immediate: true },
)

watch(() => auth.token, () => void loadLike())
</script>

<style scoped>
.engagement-panel {
  margin-top: var(--space-5);
  padding: 0 var(--d-pad) var(--space-2);
  border-top: 1px solid var(--d-divider);
}

.engagement-actions {
  display: flex;
  gap: var(--space-6);
  margin-bottom: var(--space-4);
}

.engagement-action {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--d-ink-2);
  font-size: var(--d-body);
}

.engagement-action strong {
  min-width: 20px;
  color: var(--d-ink);
  font-size: var(--d-meta);
  font-variant-numeric: tabular-nums;
}

.engagement-action.active {
  color: var(--d-accent);
}

.engagement-action.active strong { color: var(--d-accent); }
.engagement-action:disabled { opacity: .62; }
.engagement-action ion-spinner { width: 20px; height: 20px; }

.comments-heading {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin: var(--space-4) 0 var(--space-2);
}

.comments-heading h2 {
  margin: 0;
  color: var(--d-ink);
  font-size: var(--d-title);
  font-weight: 600;
  letter-spacing: -0.2px;
}

.comments-heading > span {
  color: var(--d-ink-2);
  font-size: var(--d-meta);
  font-variant-numeric: tabular-nums;
}

.guest-composer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--d-divider);
}

.guest-composer strong {
  color: var(--d-ink);
  font-size: var(--d-body);
  font-weight: 600;
}

.guest-composer p {
  margin: 3px 0 0;
  color: var(--d-ink-2);
  font-size: var(--d-caption);
  line-height: 1.55;
}

.login-comment-button {
  min-height: 36px;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-pill);
  background: var(--d-accent);
  color: var(--white);
  font-size: var(--d-caption);
  font-weight: 600;
}

.comment-composer { display: grid; gap: var(--space-2); padding: var(--space-3) 0; border-bottom: 1px solid var(--d-divider); }
.comment-composer label { color: var(--d-ink); font-size: var(--d-body); font-weight: 600; }
.comment-composer textarea {
  width: 100%;
  min-height: 112px;
  resize: vertical;
  padding: var(--space-3) var(--space-4);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--d-fill);
  color: var(--d-ink);
  font-size: var(--d-body);
  line-height: 1.6;
}

.comment-composer textarea:focus { box-shadow: 0 0 0 2px var(--d-accent); outline: none; }
.comment-composer textarea:disabled { color: var(--d-ink-2); }

.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.composer-footer > span { color: var(--d-ink-2); font-size: var(--d-caption); font-variant-numeric: tabular-nums; }
.composer-footer > span.warning { color: var(--warning); }
.submit-comment { display: inline-flex; min-width: 112px; min-height: 40px; align-items: center; justify-content: center; gap: 6px; padding: 0 var(--space-4); border: 0; border-radius: var(--radius-pill); background: var(--d-accent); color: var(--white); font-size: var(--d-body); font-weight: 600; }
.submit-comment:disabled { background: var(--d-fill); color: var(--d-ink-2); }
.submit-comment ion-spinner { width: 18px; height: 18px; }
.composer-error { margin: 0; color: var(--danger); font-size: var(--d-caption); line-height: 1.55; }

.comment-list-wrap { min-width: 0; }
.comment-list { display: grid; min-width: 0; }

.comment-item {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: var(--space-3);
  padding: var(--space-4) 0;
  border-bottom: 1px solid var(--d-divider);
}

.comment-item > div { min-width: 0; }
.comment-item header { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
.comment-item header strong { min-width: 0; overflow: hidden; color: var(--d-ink); font-size: var(--d-body); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.comment-item time { flex: 0 0 auto; color: var(--d-ink-2); font-size: var(--d-caption); }
.comment-item p { margin: 4px 0 0; color: var(--d-ink-2); font-size: var(--d-body); line-height: 1.6; overflow-wrap: anywhere; white-space: pre-wrap; }

.comments-empty {
  margin: 0;
  padding: var(--space-6) 0;
  color: var(--d-ink-2);
  font-size: var(--d-body);
  line-height: 1.6;
  text-align: center;
}

.comments-error {
  margin: 0;
  padding: var(--space-5) 0;
  color: var(--danger);
  font-size: var(--d-body);
  line-height: 1.6;
  text-align: center;
}

.comments-error p { margin: 0 0 var(--space-3); color: var(--danger); }

.retry-comments, .load-more-comments {
  min-height: var(--touch-target);
  border: 0;
  background: transparent;
  color: var(--d-accent);
  font-size: var(--d-body);
  font-weight: 500;
}

.retry-comments { padding: 0 var(--space-4); }
.load-more-comments { display: inline-flex; width: 100%; align-items: center; justify-content: center; gap: 7px; margin-top: var(--space-2); }
.load-more-comments:disabled { color: var(--d-ink-2); }
.load-more-comments ion-spinner { width: 18px; height: 18px; }

.comment-skeleton-list { display: grid; }
.comment-skeleton { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4) 0; }
.comment-skeleton > span, .comment-skeleton i { display: block; background: var(--d-fill); animation: engagement-pulse 1.1s ease-in-out infinite alternate; }
.comment-skeleton > span { width: 36px; height: 36px; border-radius: 50%; }
.comment-skeleton div { display: grid; align-content: start; gap: 7px; }
.comment-skeleton i { height: 12px; border-radius: var(--radius-sm); }
.comment-skeleton i:nth-child(1) { width: 36%; }
.comment-skeleton i:nth-child(2) { width: 92%; }
.comment-skeleton i:nth-child(3) { width: 64%; }

@keyframes engagement-pulse { from { opacity: .56; } to { opacity: 1; } }

@media (max-width: 390px) {
  .guest-composer { flex-direction: column; align-items: flex-start; }
  .login-comment-button { width: 100%; }
  .comment-item { gap: var(--space-2); }
  .comment-item header { align-items: flex-start; flex-direction: column; gap: 2px; }
  .comment-item time { line-height: 1.4; }
}
</style>
