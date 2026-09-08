<template>
  <ion-page>
    <DetailHeader title="作品详情" default-href="/tabs/discover">
      <template #action>
        <DetailAgentAction
          aria-label="引用当前作品询问 Agent"
          :disabled="agentDisabled"
          @open="openAgent"
        />
        <button v-if="isOwner" type="button" class="header-action pressable" aria-label="编辑作品" @click="goEdit">
          <FilePenLine :size="20" aria-hidden="true" />
        </button>
        <button v-if="!isOwner" type="button" class="header-action" aria-label="咨询作品" @click="goConversation">
          <MessageCircle :size="20" aria-hidden="true" />
        </button>
        <button type="button" class="header-action" aria-label="分享作品" @click="shareWork">
          <Share2 :size="20" aria-hidden="true" />
        </button>
      </template>
    </DetailHeader>

    <ion-content class="detail-content">
      <main class="detail-shell">
        <FeedSkeleton v-if="loading" :count="2" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="作品加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="work">
          <section class="media-stack">
            <template v-if="work.media_type === 'video' && videoUrl">
              <video :src="videoUrl" :poster="previewUrl" controls playsinline preload="metadata">
                当前设备暂不支持视频播放。
              </video>
            </template>
            <ImageCarousel
              v-else-if="mediaUrls.length"
              :images="mediaUrls"
              :alt-prefix="work.title || '摄影作品'"
            />
            <div v-else class="work-placeholder"><MediaPlaceholder /></div>
          </section>

          <section class="work-copy">
            <h1>{{ work.title || work.tag || '未命名作品' }}</h1>
            <p v-if="work.description">{{ work.description }}</p>
            <p v-else class="muted">摄影师暂未补充这组作品的创作说明。</p>
            <div v-if="work.tags?.length" class="tag-list">
              <span v-for="tag in work.tags" :key="tag" class="tag">{{ tag }}</span>
            </div>
          </section>

          <button type="button" class="author-row pressable" @click="goPhotographer">
            <AvatarImage :src="work.user_avatar_url" :name="work.user_display_name" :size="36" />
            <span class="author-copy">
              <strong>{{ work.user_display_name || '摄影师' }}</strong>
              <span>{{ work.user_bio || '进入主页查看完整作品与可预约方案' }}</span>
            </span>
            <ChevronRight :size="18" aria-hidden="true" />
          </button>

          <EngagementPanel
            compact
            target-type="portfolio"
            :target-id="work.id"
            @message="toastMessage = $event"
          />
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2400"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <ion-footer v-if="work && !loading" class="work-footer">
      <div v-if="commentMode" class="comment-backdrop" @click="exitCommentMode" />
      <div v-if="!commentMode" class="bottom-bar">
        <button
          type="button"
          class="bar-action"
          :class="{ active: likeSummary.liked }"
          :aria-label="likeSummary.liked ? '取消点赞' : '点赞'"
          :aria-pressed="likeSummary.liked"
          :disabled="likeLoading"
          @click="handleLike"
        >
          <ion-spinner v-if="likeLoading" name="crescent" aria-hidden="true" />
          <Heart v-else :size="24" :fill="likeSummary.liked ? 'currentColor' : 'none'" aria-hidden="true" />
          <span v-if="likeSummary.count" class="count">{{ likeSummary.count }}</span>
        </button>

        <button
          type="button"
          class="bar-action"
          :class="{ active: favorited }"
          :aria-label="favorited ? '取消收藏' : '收藏'"
          :aria-pressed="favorited"
          :disabled="favoriteLoading"
          @click="toggleFavorite"
        >
          <ion-spinner v-if="favoriteLoading" name="crescent" aria-hidden="true" />
          <Bookmark v-else :size="24" :fill="favorited ? 'currentColor' : 'none'" aria-hidden="true" />
        </button>

        <div class="comment-trigger" @click="enterCommentMode">
          <MessageCircle :size="20" aria-hidden="true" />
          <span class="comment-placeholder">评论…</span>
        </div>
      </div>

      <div v-else class="comment-bar" @click.stop>
        <input
          ref="commentInputRef"
          v-model="commentDraft"
          class="comment-input"
          type="text"
          placeholder="聊聊你喜欢的画面…"
          maxlength="500"
          :disabled="submittingComment"
        />
        <button
          type="button"
          class="send-button"
          :disabled="submittingComment || !commentDraft.trim()"
          @click="submitComment"
        >
          <ion-spinner v-if="submittingComment" name="crescent" aria-hidden="true" />
          <Send v-else :size="22" aria-hidden="true" />
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonFooter, IonPage, IonSpinner, IonToast } from '@ionic/vue'
import { Bookmark, ChevronRight, FilePenLine, Heart, MessageCircle, Send, Share2 } from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailAgentAction from '@/components/DetailAgentAction.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import EngagementPanel from '@/components/EngagementPanel.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import ImageCarousel from '@/components/ImageCarousel.vue'
import MediaPlaceholder from '@/components/MediaPlaceholder.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getWorkDetail } from '@/api/discovery'
import { createComment, getLikeSummary, toggleLike } from '@/api/engagement'
import { getWorkFavoriteStatus, toggleWorkFavorite } from '@/api/social'
import { useAuthStore } from '@/stores/auth'
import type { WorkItem } from '@/types/discovery'
import type { LikeSummary } from '@/types/engagement'
import { getWorkMediaUrls, getWorkPreviewUrl, resolveMediaUrl } from '@/utils/media'
import { buildWorkPageContext, stageAIPageContext } from '@/utils/aiPageContext'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const work = ref<WorkItem | null>(null)
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')
const favorited = ref(false)
const favoriteLoading = ref(false)
const likeSummary = ref<LikeSummary>({ liked: false, count: 0 })
const likeLoading = ref(false)
const commentMode = ref(false)
const commentDraft = ref('')
const submittingComment = ref(false)
const commentInputRef = ref<HTMLInputElement | null>(null)

const mediaUrls = computed(() => (work.value ? getWorkMediaUrls(work.value) : []))
const previewUrl = computed(() => (work.value ? getWorkPreviewUrl(work.value) : ''))
const videoUrl = computed(() =>
  work.value ? resolveMediaUrl(work.value.compressed_url || work.value.url) : '',
)

const agentDisabled = computed(() => loading.value || !!error.value || !work.value)
const isOwner = computed(() => Boolean(
  work.value
  && auth.user?.id === (work.value.photographer_id || work.value.user_id),
))

function openAgent() {
  if (!work.value) return
  const context = buildWorkPageContext(work.value, route)
  const handoffKey = stageAIPageContext(context)
  void router.push({ name: 'ai-assistant', query: { context: handoffKey } })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await auth.initialize()
    const workId = String(route.params.workId)
    const [detail, favoriteStatus, like] = await Promise.all([
      getWorkDetail(workId),
      getWorkFavoriteStatus(workId).catch(() => false),
      getLikeSummary('portfolio', workId).catch(() => ({ liked: false, count: 0 })),
    ])
    work.value = detail
    favorited.value = favoriteStatus
    likeSummary.value = like
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refreshFavoriteStatus() {
  if (!work.value) return
  favorited.value = await getWorkFavoriteStatus(work.value.id).catch(() => false)
}

async function refreshLikeStatus() {
  if (!work.value) return
  likeSummary.value = await getLikeSummary('portfolio', work.value.id).catch(() => ({ liked: false, count: 0 }))
}

async function toggleFavorite() {
  if (!work.value || favoriteLoading.value) return
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  const photographerId = work.value.photographer_id || work.value.user_id
  if (!photographerId) {
    toastMessage.value = '作品缺少摄影师信息，暂时无法收藏。'
    return
  }
  favoriteLoading.value = true
  try {
    favorited.value = await toggleWorkFavorite(work.value, photographerId)
    toastMessage.value = favorited.value ? '作品已加入收藏' : '已取消作品收藏'
  } catch (favoriteError) {
    toastMessage.value = getApiErrorMessage(favoriteError)
  } finally {
    favoriteLoading.value = false
  }
}

async function handleLike() {
  if (!work.value || likeLoading.value) return
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  likeLoading.value = true
  try {
    likeSummary.value = await toggleLike('portfolio', work.value.id)
    toastMessage.value = likeSummary.value.liked ? '已点赞' : '已取消点赞'
  } catch (likeError) {
    toastMessage.value = getApiErrorMessage(likeError)
  } finally {
    likeLoading.value = false
  }
}

function enterCommentMode() {
  if (!auth.isAuthenticated) {
    void router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  commentMode.value = true
  void nextTick(() => commentInputRef.value?.focus())
}

function exitCommentMode() {
  commentMode.value = false
  commentDraft.value = ''
}

async function submitComment() {
  if (!work.value || submittingComment.value || !commentDraft.value.trim()) return
  submittingComment.value = true
  try {
    await createComment('portfolio', work.value.id, commentDraft.value.trim())
    toastMessage.value = '评论已发布'
    exitCommentMode()
  } catch (commentError) {
    toastMessage.value = getApiErrorMessage(commentError)
  } finally {
    submittingComment.value = false
  }
}

function goPhotographer() {
  const userId = work.value?.photographer_id || work.value?.user_id
  if (userId) router.push({ name: 'photographer-detail', params: { userId } })
}

function goEdit() {
  if (!work.value || !isOwner.value) return
  void router.push({ name: 'work-edit', params: { workId: work.value.id } })
}

function goConversation() {
  if (!work.value) return
  const userId = work.value.photographer_id || work.value.user_id
  if (!userId) return
  const title = work.value.title || work.value.tag || '摄影作品'
  void router.push({
    name: 'conversation',
    params: { userId },
    query: {
      introType: 'work',
      introTitle: title,
      introUrl: `/works/${work.value.id}`,
      ...(previewUrl.value ? { introCoverUrl: previewUrl.value } : {}),
      introText: `你好，我很喜欢这组作品，想咨询类似风格的拍摄。`,
    },
  })
}

async function shareWork() {
  const shareData = {
    title: work.value?.title || '摄影作品',
    text: `看看 ${work.value?.user_display_name || '摄影师'} 的这组作品`,
    url: window.location.href,
  }
  try {
    if (navigator.share) await navigator.share(shareData)
    else {
      await navigator.clipboard.writeText(window.location.href)
      toastMessage.value = '作品链接已复制'
    }
  } catch {
    // 用户取消系统分享时不打断浏览。
  }
}

watch(() => auth.token, () => {
  void refreshFavoriteStatus()
  void refreshLikeStatus()
})
onMounted(() => void load())
</script>

<style scoped>
.detail-content {
  --background: var(--d-page);
}

.detail-shell {
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding-bottom: var(--space-10);
}

.header-action {
  display: grid;
  width: var(--touch-target);
  height: var(--touch-target);
  place-items: center;
  border: 0;
  background: transparent;
  color: var(--d-ink);
}

.header-action:disabled { color: var(--d-ink-2); }
.header-action ion-spinner { width: 20px; height: 20px; }

/* ── 媒体：全宽，无圆角无阴影 ── */

.media-stack {
  width: 100%;
  background: var(--d-ink);
}

.media-stack video {
  display: block;
  width: 100%;
  max-height: 78dvh;
  border: 0;
  background: var(--d-ink);
  object-fit: contain;
}

.work-placeholder {
  aspect-ratio: 4 / 5;
  background: var(--d-fill);
}

/* ── 内容区 ── */

.work-copy {
  padding: var(--space-5) var(--d-pad) var(--space-5);
}

.work-copy h1 {
  margin: 0 0 var(--space-2);
  color: var(--d-ink);
  font-size: var(--d-title);
  font-weight: 600;
  letter-spacing: -0.2px;
  line-height: 1.35;
}

.work-copy p {
  margin: 0;
  color: var(--d-ink-2);
  font-size: var(--d-body);
  font-weight: 400;
  line-height: 1.6;
  white-space: pre-wrap;
}

.work-copy .muted {
  color: var(--d-ink-2);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.tag {
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  background: var(--d-fill);
  color: var(--d-ink-2);
  font-size: var(--d-caption);
  line-height: 1.6;
}

/* ── 创作者信息行：无卡片，靠分割线 ── */

.author-row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) 20px;
  width: 100%;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--d-pad);
  border: 0;
  border-top: 1px solid var(--d-divider);
  background: transparent;
  color: var(--d-ink);
  text-align: left;
}

.author-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.author-copy strong {
  font-size: var(--d-body);
  font-weight: 600;
  color: var(--d-ink);
}

.author-copy > span {
  overflow: hidden;
  color: var(--d-ink-2);
  font-size: var(--d-meta);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.author-row > svg {
  color: var(--d-ink-2);
}

/* ── 底部操作栏：毛玻璃 ── */

.work-footer { background: transparent; }

.comment-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: transparent;
}

.bottom-bar,
.comment-bar {
  position: relative;
  z-index: 1;
  display: grid;
  align-items: center;
  gap: var(--space-2);
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding: calc(var(--space-2) + 3px) var(--d-pad) calc(var(--space-2) + 3px + env(safe-area-inset-bottom));
  border-top: 0.5px solid var(--d-divider);
  background: var(--d-material);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.bottom-bar { grid-template-columns: auto auto 1fr; }
.comment-bar { grid-template-columns: 1fr auto; }

.bottom-bar > *,
.comment-bar > * {
  min-width: 0;
}

.bar-action {
  display: inline-flex;
  min-width: var(--touch-target);
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 0 var(--space-2);
  border: 0;
  background: transparent;
  color: var(--d-ink-2);
}

.bar-action.active {
  color: var(--d-accent);
}

.bar-action:disabled {
  color: var(--d-ink-2);
  opacity: 0.6;
}

.bar-action .count {
  font-size: var(--d-meta);
  font-variant-numeric: tabular-nums;
  color: var(--d-ink-2);
}

.bar-action.active .count {
  color: var(--d-accent);
}

.bar-action ion-spinner {
  width: 24px;
  height: 24px;
}

.comment-trigger {
  display: flex;
  min-height: 44px;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-pill);
  background: var(--d-fill);
  color: var(--d-ink-2);
  cursor: text;
}

.comment-placeholder {
  font-size: var(--d-body);
  white-space: nowrap;
}

.comment-input {
  flex: 1;
  min-width: 0;
  min-height: 44px;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-pill);
  background: var(--d-fill);
  color: var(--d-ink);
  font-size: var(--d-body);
  outline: none;
}

.comment-input:focus {
  box-shadow: 0 0 0 2px var(--d-accent);
}

.comment-input:disabled {
  opacity: 0.6;
}

.send-button {
  display: inline-flex;
  width: 44px;
  height: 44px;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--d-accent);
}

.send-button:disabled {
  color: var(--d-ink-2);
  opacity: 0.4;
}

.send-button ion-spinner {
  width: 22px;
  height: 22px;
}

@media (max-width: 390px) {
  .bottom-bar,
  .comment-bar {
    gap: var(--space-1);
    padding-inline: var(--space-4);
  }

  .bar-action {
    min-width: 40px;
    padding-inline: var(--space-1);
  }

  .comment-trigger,
  .comment-input {
    font-size: var(--d-meta);
  }
}
</style>
