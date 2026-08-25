<template>
  <div class="photographer-detail" v-loading="loading">
    <template v-if="profile">
      <div
        class="hero-section"
        :class="profile?.user_bio ? `bio-height-${bioHeightMode}` : 'bio-height-min'"
        :style="{ backgroundImage: profile.background_url ? `url(${getFullUrl(profile.background_url)})` : undefined }"
      >
        <div class="hero-overlay" v-if="profile.background_url"></div>
        <div class="hero-content">
          <div class="hero-avatar-wrap">
            <el-avatar :size="100" :src="getFullUrl(profile.user_avatar_url)" class="hero-avatar">
              {{ (profile.user_display_name || '?')[0] }}
            </el-avatar>
            <el-tooltip v-if="profile.user_role === 'photographer'" content="已认证摄影师" placement="top">
              <span class="verified-badge" aria-label="已认证摄影师">
                <el-icon><Check /></el-icon>
              </span>
            </el-tooltip>
          </div>
          <div class="hero-info">
            <div class="hero-name-row">
              <span class="hero-name">{{ profile.user_display_name || '摄影师' }}</span>
            </div>
            <div class="hero-identity">
              <span v-if="profile.username">@{{ profile.username }}</span>
              <a v-if="profile.public_email" :href="`mailto:${profile.public_email}`" class="public-email">
                {{ profile.public_email }}
              </a>
            </div>
            <div class="hero-bio">
              <template v-if="bioParagraphs.length">
                <p v-for="(para, idx) in bioParagraphs" :key="idx">{{ para }}</p>
              </template>
              <p v-else>暂无简介</p>
              <template v-if="profile.styles?.length">
                <el-tag
                  v-for="tag in profile.styles"
                  :key="tag"
                  size="small"
                  class="style-tag"
                >
                  {{ tag }}
                </el-tag>
              </template>
            </div>
            <FollowCounts
              :following-count="followCounts.following_count"
              :follower-count="followCounts.follower_count"
              :clickable="false"
            />
          </div>
          <div class="hero-actions">
            <el-button type="success" size="large" class="hero-action-btn" @click="goToMessages">
              {{ profile.user_role === 'photographer' ? '邀请' : '发消息' }}
            </el-button>
            <FollowButton
              v-if="profile.user_id"
              :user-id="profile.user_id"
              size="large"
              class="hero-action-btn"
              @toggled="onFollowToggled"
            />
          </div>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="作品" name="works">
          <div class="works-grid">
            <div class="work-card" v-for="work in (profile.portfolio || [])" :key="work.id || work.url" @click="goWorkDetail(work)">
              <div class="work-card-media" :style="{ aspectRatio: getWorkPreviewRatio(work) }">
                <video
                  v-if="shouldUseVideoElementPreview(work)"
                  :src="getVideoStreamUrl(work)"
                  class="work-media work-video"
                  preload="metadata"
                  muted
                  playsinline
                />
                <el-image
                  v-else
                  :src="getWorkPreviewUrl(work)"
                  fit="cover"
                  class="work-media"
                  lazy
                  @error="handleWorkPreviewError(work)"
                />
                <div v-if="work.media_type === 'video'" class="work-video-badge">
                  <el-icon :size="24"><VideoPlay /></el-icon>
                </div>
              </div>
              <div class="work-card-footer">
                <span class="work-card-title">{{ work.title || '' }}</span>
                <span @click.stop>
                <LikeButton
                  v-if="work.id"
                  target-type="portfolio"
                  :target-id="work.id"
                  :liked="likeStore.get('portfolio', work.id).liked"
                  :count="likeStore.get('portfolio', work.id).count"
                  class="row-action-btn"
                />
                </span>
              </div>
            </div>
            <el-empty v-if="!profile.portfolio || !profile.portfolio.length" description="暂无作品" />
          </div>
        </el-tab-pane>

        <el-tab-pane v-if="profile.user_role === 'photographer'" label="方案" name="plans">
          <div class="plans-grid">
            <div class="plan-card" v-for="pkg in (profile.packages || [])" :key="pkg.id || pkg.name" @click="goPackageDetail(pkg)">
              <div
                v-if="getPackageCoverPreviewUrl(pkg)"
                class="plan-card-media"
                :style="{ aspectRatio: getPackagePreviewRatio(pkg) }"
              >
                <el-image
                  :src="getPackageCoverPreviewUrl(pkg)"
                  fit="cover"
                  class="plan-media"
                  lazy
                />
              </div>
              <div class="plan-card-footer">
                <span class="plan-card-name">{{ pkg.name || '' }}</span>
                <span @click.stop>
                <FavoriteButton
                  v-if="pkg.id"
                  target-type="package"
                  :target-id="String(pkg.id)"
                  :photographer-id="profile.user_id || 0"
                  :target-data="pkg"
                  class="row-action-btn"
                />
                </span>
              </div>
            </div>
          </div>
          <el-empty v-if="!profile.packages || !profile.packages.length" description="暂无方案" />
        </el-tab-pane>
        <el-tab-pane v-if="profile.user_role === 'photographer'" label="数据仪表盘" name="stats">
          <PhotographerStats :user-id="profile.user_id" />
        </el-tab-pane>
      </el-tabs>

    </template>

    <el-empty v-if="!loading && !profile" description="摄影师不存在" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Check, Play as VideoPlay } from 'lucide-vue-next'
import { getPhotographerDetail } from '../api/photographer'
import { trackAnalyticsEvent } from '../api/analytics'
import LikeButton from '../components/LikeButton.vue'
import FavoriteButton from '../components/FavoriteButton.vue'
import PhotographerStats from '../components/PhotographerStats.vue'
import FollowButton from '../components/FollowButton.vue'
import FollowCounts from '../components/FollowCounts.vue'
import { useLikeStore } from '@/stores/like'
import { useFavoriteStore } from '@/stores/favorite'
import { useImageAspectRatio } from '@/composables/useImageAspectRatio'
import { getPackagePreviewUrl, getVideoStreamUrl, getWorkPreviewUrl, isVideoWork } from '@/utils/imagePreview'

const route = useRoute()
const router = useRouter()
const likeStore = useLikeStore()
const favStore = useFavoriteStore()
const profile = ref(null)
const loading = ref(false)
const activeTab = ref('works')
const { getOrPreload } = useImageAspectRatio()

const followCounts = reactive({
  following_count: 0,
  follower_count: 0,
})
const failedWorkPreviews = reactive({})

const bioParagraphs = computed(() => {
  if (!profile.value?.user_bio) return []
  return profile.value.user_bio.split('\n\n').filter(p => p.trim())
})
const bioHeightMode = computed(() => {
  const count = bioParagraphs.value.length
  if (count <= 1) return 'min'
  if (count === 2) return 'medium'
  return 'max'
})

const ratioKey = (type, id) => (id ? `${type}:${id}` : '')

const fetchDetail = async () => {
  const userId = route.params.userId
  if (!userId) return

  loading.value = true
  try {
    const res = await getPhotographerDetail(userId)
    profile.value = res.data
    followCounts.following_count = res.data.following_count ?? 0
    followCounts.follower_count = res.data.follower_count ?? 0
    await hydrateLikeState()
    await hydrateFavoriteState()
    trackProfileView()
  } finally {
    loading.value = false
  }
}

const trackProfileView = () => {
  if (!profile.value?.user_id) return
  trackAnalyticsEvent({
    user_id: profile.value.user_id,
    event_type: 'profile_view',
    target_type: 'photographer',
    target_id: String(profile.value.user_id),
    metadata: { source: 'photographer_detail' },
  }).catch(() => {})
}

const trackDashboardEvent = (eventType, targetType, targetId, metadata = {}) => {
  if (!profile.value?.user_id || !targetId) return
  trackAnalyticsEvent({
    user_id: profile.value.user_id,
    event_type: eventType,
    target_type: targetType,
    target_id: String(targetId),
    metadata,
  }).catch(() => {})
}

const hydrateLikeState = async () => {
  const p = profile.value
  if (!p) return

  const portfolioIds = (p.portfolio || []).map((work) => work.id).filter(Boolean)
  const packageIds = (p.packages || []).map((pkg) => pkg.id).filter(Boolean)

  if (portfolioIds.length) {
    await likeStore.loadMany('portfolio', portfolioIds)
  }

  // 方案收藏状态
  if (packageIds.length) {
    await favStore.loadPkgMany(packageIds.map(String))
  }
}

const hydrateFavoriteState = async () => {
  const p = profile.value
  if (!p) return
  const portfolioIds = (p.portfolio || []).map((work) => work.id).filter(Boolean)
  if (portfolioIds.length) {
    await favStore.loadMany(portfolioIds)
  }
}

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getWorkPreviewRatio = (work) => {
  if (shouldUseVideoElementPreview(work)) return '16/9'
  const url = getWorkPreviewUrl(work)
  return getOrPreload(url, ratioKey('portfolio', work?.id || work?.url))
}

const getWorkPreviewFailureKey = (work) => `${work?.id || work?.url || ''}:${work?.thumbnail_url || ''}`

const shouldUseVideoElementPreview = (work) => {
  if (!isVideoWork(work)) return false
  const videoUrl = getVideoStreamUrl(work)
  if (!videoUrl) return false
  const previewUrl = getWorkPreviewUrl(work)
  return !previewUrl || Boolean(failedWorkPreviews[getWorkPreviewFailureKey(work)])
}

const handleWorkPreviewError = (work) => {
  if (!isVideoWork(work)) return
  const key = getWorkPreviewFailureKey(work)
  if (key) failedWorkPreviews[key] = true
}

const getPackageCoverPreviewUrl = (pkg) => getPackagePreviewUrl(pkg)

const getPackagePreviewRatio = (pkg) => {
  const url = getPackageCoverPreviewUrl(pkg)
  return getOrPreload(url, ratioKey('package', pkg?.id || pkg?.name || url))
}

const goToMessages = () => {
  router.push(`/messages?to=${profile.value.user_id}`)
}

const goPackageDetail = (pkg) => {
  trackDashboardEvent('package_detail_click', 'package', pkg?.id, {
    source: 'photographer_detail',
    package_name: pkg?.name || '',
  })
  router.push({
    path: `/package/${pkg.id}`,
    state: { from: router.currentRoute.value.fullPath },
  })
}

const goWorkDetail = (work) => {
  if (work && work.id) {
    trackDashboardEvent('portfolio_view', 'portfolio', work.id, {
      source: 'photographer_detail',
      title: work.title || '',
    })
    router.push({ 
      path: `/work/${work.id}`, 
      state: { from: router.currentRoute.value.fullPath, work: { ...work, user_id: profile.value.user_id, user_display_name: profile.value.user_display_name, user_avatar_url: profile.value.user_avatar_url } } 
    })
  }
}

const onFollowToggled = (result) => {
  if (result.followerCount != null) {
    followCounts.follower_count = result.followerCount
  }
  if (result.followingCount != null) {
    followCounts.following_count = result.followingCount
  }
}

onMounted(fetchDetail)

watch(() => route.params.userId, (newUserId, oldUserId) => {
  if (newUserId && newUserId !== oldUserId) {
    profile.value = null
    activeTab.value = 'works'
    fetchDetail()
  }
})
</script>

<style scoped>
/* ===== Root ===== */
.photographer-detail {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 24px 16px 48px;
  background: var(--color-paper);
  min-height: 100vh;
}

/* ===== Hero Section ===== */
.hero-section {
  position: relative;
  background-color: #1F3F1A;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  border-radius: var(--radius-lg);
  margin-bottom: 32px;
  overflow: hidden;
}

.hero-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1;
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 2;
  display: flex;
  gap: 24px;
  align-items: flex-start;
  padding: 32px 28px 24px;
}

.hero-avatar-wrap {
  flex-shrink: 0;
  position: relative;
  display: inline-flex;
}

.hero-avatar {
  border: 3px solid rgba(255, 255, 255, 0.6);
}

.verified-badge {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  border: 2px solid #fff;
  z-index: 10;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

.hero-name-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.hero-name {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  font-family: var(--font-sans);
}

.hero-identity {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: -2px 0 10px;
  color: rgba(255, 255, 255, 0.78);
  font-size: var(--text-sm);
}

.public-email {
  color: #fff;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.public-email:hover,
.public-email:focus-visible {
  color: var(--color-brand-light);
}

.hero-bio {
  color: rgba(255, 255, 255, 0.85);
  margin: 0 0 12px;
  line-height: var(--leading-relaxed);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
}
.hero-bio p {
  margin: 0 0 6px;
  white-space: pre-wrap;
}
.hero-bio p:last-child {
  margin-bottom: 0;
}

/* 高度自适应：过渡 */
.hero-section {
  transition: min-height 0.45s ease;
}

/* 三种高度模式 - 背景图位置适配 */
.bio-height-min {
  background-position: center 25%;
}
.bio-height-medium {
  background-position: center 40%;
}
.bio-height-max {
  background-position: center 55%;
}

.style-tag {
  margin-left: 6px;
  vertical-align: middle;
}

.hero-section :deep(.follow-counts),
.hero-section :deep(.follow-counts span),
.hero-section :deep(.follow-counts strong) {
  color: rgba(255, 255, 255, 0.85) !important;
}

.hero-actions {
  flex-shrink: 0;
  align-self: flex-start;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 108px;
}

.hero-action-btn {
  width: 100%;
  justify-content: center;
  margin-left: 0;
}

.hero-actions :deep(.el-button) {
  margin-left: 0;
}

/* ===== Tabs ===== */
.detail-tabs :deep(.el-tabs__header) {
  margin: 0 0 24px;
  background: transparent;
  border: none;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
}

.detail-tabs :deep(.el-tabs__nav-wrap) {
  border-bottom: 1px solid var(--color-border);
}

.detail-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.detail-tabs :deep(.el-tabs__nav) {
  border: none;
}

.detail-tabs :deep(.el-tabs__item) {
  height: var(--tap-target-min);
  line-height: var(--tap-target-min);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--color-ink-secondary);
  padding: 0 20px;
  border: none;
  transition: color 0.2s;
  font-family: var(--font-sans);
}

.detail-tabs :deep(.el-tabs__item:hover) {
  color: var(--color-ink);
  background-color: transparent;
  border-radius: 0;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-brand) !important;
  font-weight: 600;
}

.detail-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background-color: var(--color-brand);
}

/* ===== Works Grid ===== */
.works-grid {
  column-count: 4;
  column-gap: 16px;
}

.work-card {
  break-inside: avoid;
  margin-bottom: 16px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  background: var(--color-paper-light);
  border: var(--border-default);
  transition: border-color 0.2s;
}

.work-card:hover {
  border-color: var(--color-brand);
}

.work-card-media {
  overflow: hidden;
  background: var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.work-media {
  width: 100%;
  height: 100%;
  display: block;
}

.work-video {
  object-fit: cover;
  background: #000;
}

.work-video-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  pointer-events: none;
  z-index: 2;
}

.work-video-badge .el-icon {
  margin-left: 1px;
}

.work-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-top: 1px solid var(--color-divider);
}

.work-card-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-ink);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-sans);
}

.row-action-btn {
  margin-left: 8px;
  flex-shrink: 0;
}

/* ===== Plans Grid ===== */
.plans-grid {
  column-count: 4;
  column-gap: 16px;
}

.plan-card {
  break-inside: avoid;
  margin-bottom: 16px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  background: var(--color-paper-light);
  border: var(--border-default);
  transition: border-color 0.2s;
}

.plan-card:hover {
  border-color: var(--color-brand);
}

.plan-card-media {
  overflow: hidden;
  background: var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: center;
}

.plan-media {
  width: 100%;
  height: 100%;
  display: block;
}

.plan-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px;
  border-top: 1px solid var(--color-divider);
}

.plan-card-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-ink);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-sans);
}

/* ===== Element UI Overrides ===== */
.photographer-detail :deep(.el-button--success) {
  background-color: var(--color-brand);
  border-color: var(--color-brand);
}

.photographer-detail :deep(.el-button--success:hover) {
  background-color: var(--color-brand-hover);
  border-color: var(--color-brand-hover);
}

.photographer-detail :deep(.el-tag) {
  background-color: var(--color-brand-light);
  border-color: var(--color-brand);
  color: var(--color-brand);
}

.photographer-detail :deep(.el-empty__description) {
  color: var(--color-ink-secondary);
}

/* ===== Responsive ===== */
@media (max-width: 992px) {
  .works-grid,
  .plans-grid {
    column-count: 3;
  }
}

@media (max-width: 768px) {
  .works-grid,
  .plans-grid {
    column-count: 2;
    column-gap: 12px;
  }

  .hero-content {
    padding: 24px 20px 20px;
  }
}

@media (max-width: 480px) {
  .works-grid,
  .plans-grid {
    column-count: 1;
  }

  .hero-content {
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 24px 16px 20px;
  }

  .hero-actions {
    align-self: center;
    margin-top: 12px;
  }
}
</style>
