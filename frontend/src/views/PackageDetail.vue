<template>
  <div ref="detailPageRef" class="package-detail-page">
    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="10" animated />
    </div>

    <template v-else-if="pkg">
      <div
        class="detail-layout fade-in"
        :style="currentImage ? getDetailLayoutStyle(getFullUrl(currentImage), currentImage) : null"
      >
        <button class="back-btn-circle" @click="goBack" title="返回" aria-label="返回">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <!-- 图片区域 -->
        <div
          class="gallery-section"
          :style="currentImage ? getDetailImageStyle(getFullUrl(currentImage), currentImage) : null"
        >
          <div ref="imageHostRef" class="main-image" v-if="currentImage" @click="previewVisible = true; previewIndex = currentImageIndex">
            <div
              class="main-image-frame"
              :style="getDetailImageStyle(getFullUrl(currentImage), currentImage)"
            >
              <el-image :src="getFullUrl(currentImage)" fit="cover" class="main-img" />
            </div>
          </div>
          <div class="thumb-strip" v-if="pkg.samples && pkg.samples.length > 1">
            <div
              v-for="(sample, idx) in pkg.samples"
              :key="idx"
              class="thumb-item"
              :class="{ active: currentImageIndex === idx }"
              @click="currentImageIndex = idx"
            >
              <el-image :src="getFullUrl(sample)" fit="cover" class="thumb-img" />
            </div>
          </div>
        </div>

        <!-- 详情区域 -->
        <div
          ref="infoSectionRef"
          class="info-section"
          :style="currentImage ? getDetailLayoutStyle(getFullUrl(currentImage), currentImage) : null"
        >
          <div class="photographer-section" v-if="pkg.photographer_id">
            <div class="photographer-actions">
            <button class="photographer-card" type="button" @click="goPhotographer">
              <el-avatar :size="48" :src="getFullUrl(pkg.photographer_avatar)" class="photographer-avatar">
                {{ (pkg.photographer_name || '?')[0] }}
              </el-avatar>
              <div class="photographer-info">
                <span class="photographer-name">{{ pkg.photographer_name || '未知摄影师' }}</span>
                <span class="photographer-link">查看主页 &rarr;</span>
              </div>
            </button>
            <button class="photographer-message-btn" type="button" @click="goMessage">
              <el-icon><ChatLineRound /></el-icon>
              <span>私信</span>
            </button>
            </div>
          </div>

          <h1 class="pkg-name">{{ pkg.package_name }}</h1>

          <div class="price-row">
            <span class="pkg-price">&yen;{{ pkg.price }}</span>
            <span class="pkg-duration" v-if="pkg.duration"> / {{ pkg.duration }}分钟</span>
          </div>

          <div class="pkg-meta" v-if="pkg.city">
            <span class="city-tag">{{ pkg.city }}</span>
          </div>

          <p v-if="pkg.description" class="pkg-desc">{{ pkg.description }}</p>

          <div class="pkg-styles" v-if="pkg.styles && pkg.styles.length">
            <div class="styles-list">
              <span
                v-for="(item, idx) in pkg.styles"
                :key="idx"
                class="style-hashtag"
              >#{{ item }}</span>
            </div>
          </div>

          <div class="contract-preview">
            <h2 class="section-title">套餐交付条款</h2>
            <div class="term-grid">
              <div class="term-item">
                <span>商业授权</span>
                <strong>{{ pkg.commercial_license ? '包含' : '不包含' }}</strong>
              </div>
              <div class="term-item">
                <span>付款方式</span>
                <strong>{{ pkg.payment_mode === 'deposit_balance' ? `定金 ${Math.round((pkg.deposit_rate || 0.3) * 100)}% + 尾款` : '全款支付' }}</strong>
              </div>
            </div>
            <div v-if="termsRulesText" class="term-clause">
              <span>条款规则</span>
              <p>{{ termsRulesText }}</p>
            </div>
          </div>

          <div class="divider" />

          <CommentsPanel
            v-if="pkg.id"
            ref="commentsRef"
            target-type="package"
            :target-id="String(pkg.id)"
            hide-composer
            @count-change="commentCount = $event"
          />

          <div class="action-row">
            <template v-if="!showCommentInput">
              <el-button type="primary" size="large" class="cta-btn" @click="goBooking">
                预约方案
              </el-button>
              <button class="action-btn comment-action" @click="toggleCommentInput">
                <el-icon class="action-el-icon"><ChatLineRound /></el-icon>
                <span>评论 {{ commentCount }}</span>
              </button>
              <button class="action-btn pkg-fav-action" :class="{ active: pkgFavorited }" @click="toggleFav" :disabled="favLoading">
                <Star class="action-icon" :size="20" :fill="pkgFavorited ? 'currentColor' : 'none'" aria-hidden="true" />
                <span>{{ pkgFavorited ? '已收藏' : '收藏方案' }}</span>
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

    <el-empty v-else description="方案不存在" />

    <teleport to="body">
      <div v-if="previewVisible && pkg?.samples?.length" class="lightbox-mask" @click="previewVisible = false">
        <div class="lightbox-arrow lightbox-prev" v-if="previewIndex > 0" @click.stop="previewIndex--">&lsaquo;</div>
        <div class="lightbox-arrow lightbox-next" v-if="previewIndex < (pkg.samples?.length || 1) - 1" @click.stop="previewIndex++">&rsaquo;</div>
        <div class="lightbox-counter" v-if="pkg.samples.length > 1">{{ previewIndex + 1 }} / {{ pkg.samples.length }}</div>
        <img :src="getFullUrl(pkg.samples[previewIndex])" alt="" class="lightbox-img" @click.stop />
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, MessageSquare as ChatLineRound, Star } from 'lucide-vue-next'
import { getPackageDetail } from '../api/photographer'
import { trackAnalyticsEvent } from '../api/analytics'
import { createComment } from '@/api/comment'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { useDetailImageFrame } from '@/composables/useDetailImageFrame'
import { useFavoriteStore } from '@/stores/favorite'
import CommentsPanel from '@/components/CommentsPanel.vue'

const route = useRoute()
const router = useRouter()
const { getSteppedDetailOrPreload } = useImageAspectRatio()
const { detailPageRef, imageHostRef, infoSectionRef, getFrameStyle, getLayoutStyle } = useDetailImageFrame()
const favStore = useFavoriteStore()

const pkg = ref(null)
const loading = ref(false)
const currentImageIndex = ref(0)
const previewVisible = ref(false)
const previewIndex = ref(0)
const favLoading = ref(false)
const commentCount = ref(0)
const commentsRef = ref(null)
const showCommentInput = ref(false)
const commentDraft = ref('')
const commentSubmitting = ref(false)
const commentInputRef = ref(null)
const SCROLL_LOCK_CLASS = 'detail-scroll-lock'

const pkgFavorited = computed(() => {
  if (!pkg.value || !pkg.value.id) return false
  return favStore.getPkg(String(pkg.value.id))
})

const currentImage = computed(() => {
  if (!pkg.value || !pkg.value.samples || !pkg.value.samples.length) return null
  return pkg.value.samples[currentImageIndex.value] || pkg.value.samples[0]
})

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
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

const formatPolicy = (policy) => {
  if (!policy) return ''
  if (typeof policy === 'string') return policy
  if (policy.description) return policy.description
  if (Array.isArray(policy.rules)) return policy.rules.map(item => item?.description).filter(Boolean).join('；')
  if (policy.response_hours) return `需在 ${policy.response_hours} 小时内响应。`
  return ''
}

const termsRulesText = computed(() => {
  if (!pkg.value) return ''
  if (pkg.value.terms_rules) return pkg.value.terms_rules

  const legacyRules = [
    pkg.value.copyright_terms ? `版权条款：${pkg.value.copyright_terms}` : '',
    formatPolicy(pkg.value.cancellation_policy) ? `取消政策：${formatPolicy(pkg.value.cancellation_policy)}` : '',
    formatPolicy(pkg.value.reschedule_policy) ? `改期政策：${formatPolicy(pkg.value.reschedule_policy)}` : '',
  ]
  return legacyRules.filter(Boolean).join('\n')
})

const fetchPackage = async () => {
  const packageId = route.params.packageId
  if (!packageId) return

  loading.value = true
  try {
    const res = await getPackageDetail(packageId)
    pkg.value = res.data
    currentImageIndex.value = 0
    if (pkg.value && pkg.value.id) {
      favStore.loadPkgMany([String(pkg.value.id)])
      trackPackageEvent('package_view')
    }
  } finally {
    loading.value = false
  }
}

const trackPackageEvent = (eventType) => {
  if (!pkg.value?.photographer_id || !pkg.value?.id) return
  trackAnalyticsEvent({
    user_id: pkg.value.photographer_id,
    event_type: eventType,
    target_type: 'package',
    target_id: String(pkg.value.id),
    metadata: {
      source: 'package_detail',
      package_name: pkg.value.package_name || '',
    },
  }).catch(() => {})
}

const toggleFav = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    ElMessage.warning('请先登录后再收藏方案')
    router.push('/login')
    return
  }
  if (favLoading.value || !pkg.value || !pkg.value.id) return
  favLoading.value = true
  try {
    await favStore.togglePkg(
      String(pkg.value.id),
      pkg.value.photographer_id || 0,
      {
        package_name: pkg.value.package_name,
        price: pkg.value.price,
        duration: pkg.value.duration,
        samples: pkg.value.samples?.[0] ? pkg.value.samples[0] : null,
      }
    )
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
  if (commentSubmitting.value || !pkg.value?.id) return
  commentSubmitting.value = true
  try {
    await createComment('package', String(pkg.value.id), content)
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
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push('/packages')
}

const goPhotographer = () => {
  if (pkg.value && pkg.value.photographer_id) {
    router.push(`/photographer/${pkg.value.photographer_id}`)
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
  if (!pkg.value?.photographer_id) return
  if (Number(pkg.value.photographer_id) === getCurrentUserId()) {
    ElMessage.warning('不能给自己发送私信')
    return
  }
  const packageName = pkg.value.package_name || '这个方案'
  const coverUrl = pkg.value.samples?.[0] || ''
  router.push({
    path: '/messages',
    query: {
      to: pkg.value.photographer_id,
      introType: 'package',
      introTitle: packageName,
      introUrl: `/package/${pkg.value.id}`,
      introCoverUrl: coverUrl,
      introText: `你好，我刚刚看到你的方案「${packageName}」，想了解一下拍摄安排和细节。`,
    },
  })
}

const goBooking = () => {
  if (pkg.value && pkg.value.photographer_id) {
    trackPackageEvent('booking_started')
    router.push({
      path: `/booking/${pkg.value.photographer_id}`,
      query: { packageId: pkg.value.id },
    })
  }
}

onMounted(() => {
  document.documentElement.classList.add(SCROLL_LOCK_CLASS)
  document.body.classList.add(SCROLL_LOCK_CLASS)
  fetchPackage()
  document.addEventListener('keydown', handleKeydown)
})
onUnmounted(() => {
  document.documentElement.classList.remove(SCROLL_LOCK_CLASS)
  document.body.classList.remove(SCROLL_LOCK_CLASS)
  document.removeEventListener('keydown', handleKeydown)
})

// 键盘左右切换
const handleKeydown = (e) => {
  if (!previewVisible.value || !pkg.value?.samples?.length) return
  if (e.key === 'ArrowLeft' && previewIndex.value > 0) {
    previewIndex.value--
  } else if (e.key === 'ArrowRight' && previewIndex.value < pkg.value.samples.length - 1) {
    previewIndex.value++
  } else if (e.key === 'Escape') {
    previewVisible.value = false
  }
}
</script>

<style scoped>
:global(html.detail-scroll-lock),
:global(body.detail-scroll-lock) {
  overflow: hidden;
  overscroll-behavior: none;
}

.package-detail-page {
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
}

@media (min-width: 861px) {
  .package-detail-page {
    overflow: hidden;
    padding-top: calc(var(--detail-page-padding) + var(--detail-content-offset-top));
  }
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
  border: var(--border-default);
  background: var(--color-paper-light);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 18px;
  color: var(--color-ink);
  transition: border-color 0.15s;
  box-shadow: var(--shadow-flyout);
  padding: 0;
  line-height: 1;
}
.back-btn-circle:hover {
  border-color: var(--color-brand);
  color: var(--color-brand);
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

/* 图片区域 */
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
  border-top: 0;
}
.thumb-item {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  flex-shrink: 0;
  transition: border-color 0.15s;
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
  .package-detail-page {
    --detail-card-height: min(
      720px,
      calc(100vh - 76px - (var(--detail-page-padding) * 2) - var(--detail-content-offset-top))
    );
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
  }

  .info-section {
    height: var(--detail-card-height);
    max-height: none;
  }
}

.pkg-name {
  font-size: calc(var(--text-2xl) * 1rem);
  font-weight: 700;
  margin: 0 0 var(--space-3);
  line-height: 1.3;
  color: var(--color-ink);
}

.price-row {
  margin-bottom: var(--space-2);
}
.pkg-price {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-brand);
}
.pkg-duration {
  font-size: calc(var(--text-base) * 1rem);
  color: var(--color-ink-tertiary);
}

.pkg-meta {
  font-size: calc(var(--text-sm) * 1rem);
  color: var(--color-ink-secondary);
  margin-bottom: var(--space-1);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.city-tag {
  display: inline-block;
  padding: 1px var(--space-2);
  font-size: calc(var(--text-xs) * 1rem);
  color: var(--color-brand);
  background: var(--color-brand-light);
  border-radius: var(--radius-md);
  font-weight: 500;
}

.divider {
  height: 1px;
  background: var(--color-divider);
  margin: var(--space-3) 0;
}

.section-title {
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 10px;
}

.pkg-desc {
  font-size: calc(var(--text-sm) * 1rem);
  color: var(--color-ink-secondary);
  line-height: 1.8;
  margin: 0;
}

.contract-preview {
  margin-top: var(--space-4);
}

.term-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.term-item,
.term-wide,
.term-clause {
  padding: 9px 10px;
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.term-wide,
.term-clause {
  margin-bottom: 8px;
}

.term-item span,
.term-wide span,
.term-clause span {
  display: block;
  margin-bottom: 3px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.term-item strong,
.term-wide strong {
  color: var(--color-ink);
  font-size: calc(var(--text-sm) * 1rem);
  line-height: 1.45;
}

.term-clause {
  margin-top: 8px;
}

.term-clause p {
  margin: 0;
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.6;
  white-space: pre-wrap;
}

/* 评论输入行 */
.comment-input-row {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.comment-inline-input :deep(.el-textarea__inner) {
  font-size: calc(var(--text-sm) * 1rem);
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

.styles-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
}
.style-hashtag {
  font-size: calc(var(--text-sm) * 1rem);
  color: var(--color-brand);
  cursor: default;
  white-space: nowrap;
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
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}
.photographer-card:hover {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}
.photographer-message-btn {
  appearance: none;
  min-width: 0;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  color: var(--color-brand);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 600;
  transition: background 0.15s, border-color 0.15s;
}
.photographer-message-btn:hover {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}
.photographer-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.photographer-name {
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
  color: var(--color-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.photographer-link {
  font-size: calc(var(--text-xs) * 1rem);
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
.cta-btn {
  flex: 1;
  min-width: 0;
  height: 48px;
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
  border-radius: var(--radius-md);
  letter-spacing: 1px;
  transition: border-color 0.15s;
}
.cta-btn:hover {
  border-color: var(--color-brand-hover);
}
.action-btn {
  flex: 1;
  min-width: 0;
  height: 48px;
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
  border-radius: var(--radius-md);
  border: var(--border-default);
  background: var(--color-paper);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  white-space: nowrap;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  user-select: none;
  color: var(--color-ink);
}
.action-btn:hover {
  border-color: var(--color-ink-secondary);
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
.comment-action {
  color: var(--color-brand);
  border-color: var(--color-brand);
}
.comment-action:hover {
  background: var(--color-brand-light);
}
.pkg-fav-action {
  color: var(--color-warning);
  border-color: var(--color-warning);
}
.pkg-fav-action:hover {
  background: #FFF8E6;
}
.pkg-fav-action.active {
  background: var(--color-warning);
  color: var(--color-paper-light);
}

/* 响应式 */
@media (max-width: 860px) {
  .package-detail-page {
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
    padding: var(--space-6) var(--space-6);
  }
  .action-row {
    position: static;
    margin-top: 28px;
    padding-top: 0;
  }
}

@media (max-width: 480px) {
  .package-detail-page {
    padding: var(--space-3);
  }
  .pkg-name {
    font-size: calc(var(--text-xl) * 1rem);
  }
  .pkg-price {
    font-size: calc(var(--text-2xl) * 1rem);
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
.lightbox-close {
  position: absolute; top: var(--space-4); right: var(--space-6); z-index: 10;
  font-size: 40px; color: #fff; cursor: pointer; line-height: 1;
  opacity: 0.8; transition: opacity 0.15s;
}
.lightbox-close:hover { opacity: 1; }
.lightbox-arrow {
  position: absolute; top: 50%; transform: translateY(-50%);
  font-size: 60px; color: #fff; cursor: pointer; line-height: 1;
  opacity: 0.7; transition: opacity 0.15s; z-index: 10;
  user-select: none; padding: 20px;
}
.lightbox-arrow:hover { opacity: 1; }
.lightbox-prev { left: 0; }
.lightbox-next { right: 0; }
.lightbox-counter {
  position: absolute; bottom: var(--space-6); left: 50%; transform: translateX(-50%);
  color: #fff; font-size: calc(var(--text-sm) * 1rem); opacity: 0.7; z-index: 10;
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
