<template>
  <div ref="detailPageRef" class="work-detail-page">
    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="10" animated />
    </div>

    <template v-else-if="work">
      <div
        class="detail-layout fade-in"
        :style="work.media_type === 'video' ? null : getDetailLayoutStyle(getFullUrl(currentImage), currentImageKey)"
      >
        <button class="back-btn-circle" @click="goBack" title="返回" aria-label="返回">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <!-- 媒体区域 -->
        <div
          class="gallery-section"
          :class="{ 'is-video': work.media_type === 'video' }"
          :style="work.media_type === 'video' ? null : getDetailImageStyle(getFullUrl(currentImage), currentImageKey)"
        >
          <!-- 视频播放器 -->
          <div v-if="work.media_type === 'video'" class="main-video">
            <VideoPlayer
              :src="getVideoPlaybackUrl(work)"
              :poster="getFullUrl(work.thumbnail_url || '')"
              class="detail-video"
            />
          </div>
          <!-- 图片查看器 -->
          <div v-else ref="imageHostRef" class="main-image" @click="openPreview(currentImageIndex)">
            <div
              class="main-image-frame"
              :style="getDetailImageStyle(getFullUrl(currentImage), currentImageKey)"
            >
              <el-image :src="getFullUrl(currentImage)" fit="cover" class="main-img" />
            </div>
          </div>
          <div class="thumb-strip" v-if="currentWorkImages.length > 1">
            <div
              v-for="(image, idx) in currentWorkImages"
              :key="`${image}-${idx}`"
              class="thumb-item"
              :class="{ active: currentImageIndex === idx }"
              @click.stop="currentImageIndex = idx"
            >
              <el-image :src="getFullUrl(getWorkThumbnail(idx) || image)" fit="cover" class="thumb-img" />
            </div>
          </div>
        </div>

        <!-- 详情区域 -->
        <div
          ref="infoSectionRef"
          class="info-section"
          :style="work.media_type === 'video' ? null : getDetailLayoutStyle(getFullUrl(currentImage), currentImageKey)"
        >
          <div class="photographer-section" v-if="work.user_id">
            <div class="photographer-actions">
            <button class="photographer-card" type="button" @click="goPhotographer">
              <el-avatar :size="48" :src="getFullUrl(work.user_avatar_url)" class="photographer-avatar">
                {{ (work.user_display_name || '?')[0] }}
              </el-avatar>
              <div class="photographer-info">
                <span class="photographer-name">{{ work.user_display_name || '未知摄影师' }}</span>
                <span class="photographer-link">查看主页 &rarr;</span>
              </div>
            </button>
            <button class="photographer-message-btn" type="button" @click="goMessage">
              <el-icon><ChatLineRound /></el-icon>
              <span>私信</span>
            </button>
            </div>
          </div>

          <h1 class="work-title" v-if="work.title">{{ work.title }}</h1>

          <div class="work-tag" v-if="getWorkTags(work).length">
            <el-tag v-for="tag in getWorkTags(work)" :key="tag" size="default">{{ tag }}</el-tag>
          </div>

          <p v-if="work.description" class="work-desc">{{ work.description }}</p>

          <div class="divider" />

          <CommentsPanel
            v-if="work.id"
            ref="commentsRef"
            target-type="portfolio"
            :target-id="work.id"
            hide-composer
            @count-change="commentCount = $event"
          />

          <div class="action-row">
            <template v-if="!showCommentInput">
              <button class="action-btn like-action" :class="{ active: likeState.liked }" @click="toggleLike" :disabled="likeLoading">
                <Heart class="action-icon" :size="20" :fill="likeState.liked ? 'currentColor' : 'none'" aria-hidden="true" />
                <span>点赞 {{ likeState.count }}</span>
              </button>
              <button class="action-btn comment-action" @click="toggleCommentInput">
                <el-icon class="action-el-icon"><ChatLineRound /></el-icon>
                <span>评论 {{ commentCount }}</span>
              </button>
              <button class="action-btn fav-action" :class="{ active: favState }" @click="toggleFavorite" :disabled="favLoading">
                <Star class="action-icon" :size="20" :fill="favState ? 'currentColor' : 'none'" aria-hidden="true" />
                <span>{{ favState ? '已收藏' : '收藏' }}</span>
              </button>
            </template>
            <div v-else class="comment-input-row">
              <el-input
                ref="commentInputRef"
                v-model="commentDraft"
                type="textarea"
                :rows="1"
                resize="none"
                maxlength="500"
                placeholder="写下你的想法..."
                class="comment-inline-input"
              />
              <div class="comment-input-actions">
                <el-button type="primary" :loading="commentSubmitting" @click="submitComment" class="comment-submit-btn">发布</el-button>
                <el-button @click="cancelComment" class="comment-cancel-btn">取消</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-else description="作品不存在" />

    <teleport to="body">
      <div v-if="previewVisible && currentWorkImages.length" class="lightbox-mask" @click="previewVisible = false">
        <div class="lightbox-arrow lightbox-prev" v-if="previewIndex > 0" @click.stop="previewIndex--">&lsaquo;</div>
        <div class="lightbox-arrow lightbox-next" v-if="previewIndex < currentWorkImages.length - 1" @click.stop="previewIndex++">&rsaquo;</div>
        <div class="lightbox-counter" v-if="currentWorkImages.length > 1">{{ previewIndex + 1 }} / {{ currentWorkImages.length }}</div>
        <img :src="getFullUrl(currentWorkImages[previewIndex])" alt="" class="lightbox-img" @click.stop />
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Heart, MessageSquare as ChatLineRound, Star } from 'lucide-vue-next'
import { getWorkDetail } from '../api/photographer'
import { createComment } from '@/api/comment'
import { useLikeStore } from '@/stores/like'
import { useFavoriteStore } from '@/stores/favorite'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { useDetailImageFrame } from '@/composables/useDetailImageFrame'
import CommentsPanel from '@/components/CommentsPanel.vue'
import VideoPlayer from '@/components/VideoPlayer.vue'
import { getVideoStreamUrl } from '@/utils/imagePreview'

const route = useRoute()
const router = useRouter()
const likeStore = useLikeStore()
const favStore = useFavoriteStore()
const { getSteppedDetailOrPreload } = useImageAspectRatio()
const { detailPageRef, imageHostRef, infoSectionRef, getFrameStyle, getLayoutStyle } = useDetailImageFrame()

const work = ref(null)
const loading = ref(false)
const likeLoading = ref(false)
const favLoading = ref(false)
const previewVisible = ref(false)
const previewIndex = ref(0)
const currentImageIndex = ref(0)
const commentCount = ref(0)
const commentsRef = ref(null)
const showCommentInput = ref(false)
const commentDraft = ref('')
const commentSubmitting = ref(false)
const commentInputRef = ref(null)
const SCROLL_LOCK_CLASS = 'detail-scroll-lock'

const likeState = computed(() => {
  if (!work.value || !work.value.id) return { liked: false, count: 0 }
  return likeStore.get('portfolio', work.value.id)
})

const favState = computed(() => {
  if (!work.value || !work.value.id) return false
  return favStore.get(work.value.id)
})

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getWorkImages = (item) => {
  if (Array.isArray(item?.images) && item.images.length) {
    return item.images.filter(Boolean)
  }
  return item?.url ? [item.url] : []
}

const currentWorkImages = computed(() => getWorkImages(work.value))

const currentImage = computed(() => {
  return currentWorkImages.value[currentImageIndex.value] || currentWorkImages.value[0] || ''
})

const currentImageKey = computed(() => {
  return `${work.value?.id || currentImage.value}:${currentImageIndex.value}`
})

const getWorkThumbnail = (index) => {
  if (!work.value) return ''
  const thumbnails = Array.isArray(work.value.thumbnail_urls) ? work.value.thumbnail_urls : []
  if (thumbnails[index]) return thumbnails[index]
  if (index === 0) return work.value.thumbnail_url || ''
  return ''
}

const openPreview = (index = currentImageIndex.value) => {
  previewIndex.value = index
  previewVisible.value = true
}

const getVideoPlaybackUrl = (work) => {
  return getVideoStreamUrl(work)
  // 优先使用压缩版本
}

const getWorkTags = (item) => {
  if (Array.isArray(item?.tags)) return item.tags
  return (item?.tag || '')
    .split(/[,\uFF0C\u3001\n]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
}

const getDetailImageRatio = (url, key) => {
  return getSteppedDetailOrPreload(url, key)
}

const getDetailImageStyle = (url, key) => {
  return getFrameStyle(getDetailImageRatio(url, key))
}

const getDetailLayoutStyle = (url, key) => {
  return getLayoutStyle(getDetailImageRatio(url, key))
}

const fetchWork = async () => {
  const workId = String(route.params.workId || '')
  if (!workId) return

  loading.value = true
  try {
    const res = await getWorkDetail(workId)
    work.value = res.data
    if (work.value && work.value.id) {
      likeStore.loadMany('portfolio', [work.value.id]).catch(() => {})
      favStore.loadMany([work.value.id])
    }
  } finally {
    loading.value = false
  }
}

const toggleLike = async () => {
  if (likeLoading.value || !work.value || !work.value.id) return
  likeLoading.value = true
  try {
    await likeStore.toggle('portfolio', work.value.id)
  } finally {
    likeLoading.value = false
  }
}

const toggleFavorite = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再收藏作品')
    router.push('/login')
    return
  }
  if (favLoading.value || !work.value || !work.value.id) return
  favLoading.value = true
  try {
    await favStore.toggle(work.value.id, work.value.user_id, {
      url: work.value.url,
      images: work.value.images,
      title: work.value.title,
      tag: work.value.tag,
      description: work.value.description,
      thumbnail_url: work.value.thumbnail_url,
      thumbnail_urls: work.value.thumbnail_urls,
      media_type: work.value.media_type,
    })
  } finally {
    favLoading.value = false
  }
}

const toggleCommentInput = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再评论')
    router.push('/login')
    return
  }
  showCommentInput.value = true
  await nextTick()
  commentInputRef.value?.focus?.()
}

const submitComment = async () => {
  const content = commentDraft.value.trim()
  if (!content) {
    ElMessage.warning('请输入评论内容')
    return
  }
  if (commentSubmitting.value || !work.value?.id) return
  commentSubmitting.value = true
  try {
    await createComment('portfolio', work.value.id, content)
    commentDraft.value = ''
    showCommentInput.value = false
    commentCount.value++
    ElMessage.success('评论已发布')
  } finally {
    commentSubmitting.value = false
  }
}

const cancelComment = () => {
  commentDraft.value = ''
  showCommentInput.value = false
}

const goBack = () => {
  const from = history.state?.from
  if (from) {
    if (window.history.length > 1) {
      router.back()
    } else {
      router.replace(from)
    }
    return
  }
  router.replace('/works')
}

const goPhotographer = () => {
  if (work.value && work.value.user_id) {
    router.push(`/photographer/${work.value.user_id}`)
  }
}

const getCurrentUserId = () => {
  const token = localStorage.getItem('token')
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return Number(payload.sub)
  } catch {
    return null
  }
}

const goMessage = () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再私信')
    router.push('/login')
    return
  }
  if (!work.value?.user_id) return
  if (Number(work.value.user_id) === getCurrentUserId()) {
    ElMessage.warning('不能给自己发送私信')
    return
  }
  const workTitle = work.value.title || work.value.tag || '这个作品'
  const coverUrl = work.value.media_type === 'video'
    ? (work.value.thumbnail_url || '')
    : (getWorkThumbnail(0) || currentWorkImages.value[0] || work.value.url || '')
  router.push({
    path: '/messages',
    query: {
      to: work.value.user_id,
      introType: 'work',
      introTitle: workTitle,
      introUrl: `/work/${work.value.id}`,
      introCoverUrl: coverUrl,
      introText: `你好，我刚刚看到你的作品「${workTitle}」，想了解一下这组拍摄的风格和预约方式。`,
    },
  })
}

const handleKeydown = (e) => {
  if (e.key === 'Escape') {
    previewVisible.value = false
    return
  }
  if (!previewVisible.value || !currentWorkImages.value.length) return
  if (e.key === 'ArrowLeft' && previewIndex.value > 0) {
    previewIndex.value--
  } else if (e.key === 'ArrowRight' && previewIndex.value < currentWorkImages.value.length - 1) {
    previewIndex.value++
  }
}

watch(work, () => {
  currentImageIndex.value = 0
  previewIndex.value = 0
})

onMounted(() => {
  document.documentElement.classList.add(SCROLL_LOCK_CLASS)
  document.body.classList.add(SCROLL_LOCK_CLASS)
  fetchWork()
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.documentElement.classList.remove(SCROLL_LOCK_CLASS)
  document.body.classList.remove(SCROLL_LOCK_CLASS)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
:global(html.detail-scroll-lock),
:global(body.detail-scroll-lock) {
  overflow: hidden;
  overscroll-behavior: none;
}

.work-detail-page {
  --detail-page-padding: 20px;
  --detail-back-gutter: 52px;
  --detail-layout-gap: 20px;
  --detail-info-width: clamp(400px, 25vw, 480px);
  --detail-content-offset-top: clamp(32px, 5vh, 64px);
  --detail-card-height: min(720px, calc(100vh - 76px - (var(--detail-page-padding) * 2) - var(--detail-content-offset-top)));
  box-sizing: border-box;
  height: calc(100vh - 76px);
  max-width: 1920px;
  margin: 0 auto;
  padding: var(--detail-page-padding);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--color-paper);
  color: var(--color-ink);
}

/* 圆形返回按钮 */
.back-btn-circle {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 10;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  background: var(--color-ink);
  color: var(--color-paper);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  transition: background 0.2s, border-color 0.2s;
  padding: 0;
  line-height: 1;
}
.back-btn-circle:hover {
  background: var(--color-ink-secondary);
  border-color: var(--color-ink-secondary);
}

.loading-wrap {
  padding: 40px 0;
}

/* 渐入动画 */
.fade-in {
  animation: fadeIn 0.35s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.detail-layout {
  box-sizing: border-box;
  display: flex;
  gap: var(--detail-layout-gap);
  align-items: stretch;
  min-height: 0;
  flex: 0 0 auto;
  position: relative;
  padding-left: var(--detail-back-gutter);
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
}

/* 媒体区域 */
.gallery-section {
  box-sizing: border-box;
  flex: 0 0 auto;
  background: var(--color-paper);
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  position: relative;
  border: var(--border-default);
  border-radius: var(--radius-md);
}
.gallery-section.is-video {
  flex: 1 1 0;
}
.main-video {
  width: 100%;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.detail-video {
  width: 100%;
  border-radius: var(--radius-md);
}
.main-image {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  background: var(--color-paper);
  cursor: zoom-in;
}
.main-image-frame {
  box-sizing: border-box;
  flex: 0 0 auto;
  overflow: hidden;
  background: var(--color-paper);
}
.main-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb-strip {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  overflow-x: auto;
  background: transparent;
  border-top: 1px solid var(--color-border-light);
}
.thumb-item {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  flex-shrink: 0;
  transition: border-color 0.2s;
}
.thumb-item.active {
  border-color: var(--color-brand);
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 详情区域 */
.info-section {
  box-sizing: border-box;
  width: var(--detail-info-width);
  flex-shrink: 0;
  padding: var(--space-8) 28px;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  max-height: calc(100vh - 120px);
}

@media (min-width: 861px) {
  .work-detail-page {
    --detail-card-height: min(
      720px,
      calc(100vh - 76px - (var(--detail-page-padding) * 2) - var(--detail-content-offset-top))
    );
    padding-top: calc(var(--detail-page-padding) + var(--detail-content-offset-top));
  }

  .detail-layout {
    align-items: center;
    height: var(--detail-card-height);
  }

  .gallery-section {
    height: 100%;
    width: fit-content;
  }

  .main-image {
    flex: 0 0 auto;
    width: auto;
    height: 100%;
  }

  .main-image-frame {
    max-width: 100%;
  }

  .thumb-strip {
    position: absolute;
    left: var(--space-3);
    right: var(--space-3);
    bottom: var(--space-3);
    z-index: 2;
    border: 0;
    border-radius: 0;
    background: transparent;
    backdrop-filter: none;
  }

  .info-section {
    height: var(--detail-card-height);
    max-height: none;
  }
}

.work-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin: 0 0 var(--space-3);
  line-height: 1.3;
  color: var(--color-ink);
}

.work-tag {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}
.work-tag :deep(.el-tag) {
  background: var(--color-brand-light);
  color: var(--color-brand);
  border-color: var(--color-brand-light);
}

.divider {
  height: 1px;
  background: var(--color-divider);
  margin: var(--space-3) 0;
}

.work-desc {
  font-size: var(--text-sm);
  color: var(--color-ink-secondary);
  line-height: 1.8;
  margin: 0;
}

/* 评论输入行 */
.comment-input-row {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.comment-inline-input :deep(.el-textarea__inner) {
  font-size: var(--text-sm);
  line-height: 1.5;
  min-height: 36px;
}
.comment-input-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
.comment-submit-btn {
  height: 36px;
}
.comment-cancel-btn {
  height: 36px;
}

/* 摄影师区域 */
.info-section > .photographer-section {
  margin-bottom: 22px;
}
.photographer-actions {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 10px;
  align-items: stretch;
}
.photographer-card {
  appearance: none;
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: var(--space-3) 14px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color 0.2s, background 0.2s;
}
.photographer-card:hover {
  border-color: var(--color-ink-secondary);
}
.photographer-message-btn {
  appearance: none;
  min-width: 0;
  border: 1px solid var(--color-brand);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-brand);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 600;
  transition: background 0.2s, border-color 0.2s;
}
.photographer-message-btn:hover {
  background: var(--color-brand-light);
}
.photographer-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.photographer-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.photographer-link {
  font-size: var(--text-xs);
  color: var(--color-brand);
  margin-top: 2px;
}

/* 操作按钮区 */
.action-row {
  flex-shrink: 0;
  position: sticky;
  bottom: 0;
  z-index: 1;
  margin-top: auto;
  padding-top: 28px;
  background: var(--color-paper-light);
  display: flex;
  gap: var(--space-3);
}
.action-btn {
  flex: 1;
  min-width: 0;
  height: 48px;
  font-size: var(--text-sm);
  font-weight: 600;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-ink-secondary);
  background: transparent;
  color: var(--color-ink);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  white-space: nowrap;
  transition: border-color 0.2s, background 0.2s;
  user-select: none;
}
.action-btn:hover {
  border-color: var(--color-ink);
}
.action-btn:disabled {
  pointer-events: none;
  opacity: 0.7;
}
.action-icon {
  font-size: 18px;
  line-height: 1;
}
.action-el-icon {
  font-size: 18px;
}
.like-action.active {
  background: var(--color-brand);
  color: #fff;
  border-color: var(--color-brand);
}
.fav-action.active {
  background: #8B6914;
  color: #fff;
  border-color: #8B6914;
}

/* 响应式 */
@media (max-width: 860px) {
  .work-detail-page {
    height: calc(100vh - 76px);
    overflow-y: auto;
  }

  .detail-layout {
    flex-direction: column;
    flex: 0 0 auto;
  }
  .gallery-section {
    width: 100%;
  }
  .info-section {
    width: 100%;
    max-height: none;
    padding: var(--space-6) 20px;
  }
  .action-row {
    position: static;
    margin-top: 28px;
    padding-top: 0;
  }
}

@media (max-width: 480px) {
  .work-detail-page {
    padding: var(--space-3);
  }
  .work-title {
    font-size: var(--text-xl);
  }
  .info-section {
    padding: 18px 14px;
  }
  .thumb-item {
    width: 48px;
    height: 48px;
  }
}

/* 全屏图片预览 */
.lightbox-mask {
  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0, 0, 0, 0.9); z-index: 3000;
  display: flex; align-items: center; justify-content: center;
}
.lightbox-arrow {
  position: absolute; top: 50%; transform: translateY(-50%);
  font-size: 60px; color: #fff; cursor: pointer; line-height: 1;
  opacity: 0.7; transition: opacity 0.2s; z-index: 10;
  user-select: none; padding: 20px;
}
.lightbox-arrow:hover { opacity: 1; }
.lightbox-prev { left: 0; }
.lightbox-next { right: 0; }
.lightbox-counter {
  position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%);
  color: #fff; font-size: 14px; opacity: 0.7; z-index: 10;
}
.lightbox-img {
  display: block;
  width: auto;
  height: auto;
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
}
</style>
