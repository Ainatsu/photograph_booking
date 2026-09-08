<template>
  <ion-page>
    <DetailHeader title="摄影方案" default-href="/tabs/showcase">
      <template #action>
        <DetailAgentAction
          aria-label="引用当前方案询问 Agent"
          :disabled="agentDisabled"
          @open="openAgent"
        />
        <button v-if="isOwner" type="button" class="header-action pressable" aria-label="编辑摄影方案" @click="goEdit">
          <FilePenLine :size="20" aria-hidden="true" />
        </button>
      </template>
    </DetailHeader>

    <ion-content class="detail-content">
      <main class="detail-shell">
        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="方案加载失败"
          :description="error"
          action-label="重新加载"
          @action="load"
        />

        <template v-else-if="offer">
          <ImageCarousel
            v-if="sampleUrls.length"
            :images="sampleUrls"
            :alt-prefix="getPackageName(offer)"
          />
          <section v-else class="cover-placeholder-wrap">
            <MediaPlaceholder />
          </section>

          <section class="summary-section">
            <div v-if="offer.styles?.length" class="tag-list">
              <span v-for="style in offer.styles" :key="style" class="tag">{{ style }}</span>
            </div>
            <h1>{{ getPackageName(offer) }}</h1>
            <div class="price-row">
              <strong>{{ formatCurrency(offer.price) }}</strong>
              <span>起</span>
            </div>
            <p>{{ offer.description || '摄影师暂未补充详细介绍，可在预约备注中说明具体拍摄需求。' }}</p>
          </section>

          <section class="facts-grid">
            <div>
              <Clock3 :size="19" aria-hidden="true" />
              <span>拍摄时长</span>
              <strong>{{ formatDuration(offer.duration) }}</strong>
            </div>
            <div>
              <Images :size="19" aria-hidden="true" />
              <span>精修数量</span>
              <strong>{{ offer.image_count ? `${offer.image_count} 张` : '具体沟通' }}</strong>
            </div>
            <div>
              <MapPin :size="19" aria-hidden="true" />
              <span>服务地点</span>
              <strong>{{ offer.service_location || offer.city || '不限' }}</strong>
            </div>
            <div>
              <PackageCheck :size="19" aria-hidden="true" />
              <span>交付周期</span>
              <strong>{{ offer.delivery_days ? `${offer.delivery_days} 天` : '具体沟通' }}</strong>
            </div>
          </section>

          <button type="button" class="photographer-card pressable" @click="goPhotographer">
            <AvatarImage :src="offer.photographer_avatar" :name="offer.photographer_name" :size="52" />
            <span>
              <small>方案提供者</small>
              <strong>{{ offer.photographer_name || '摄影师' }}</strong>
              <em>{{ offer.photographer_location || offer.city || '查看主页与更多作品' }}</em>
            </span>
            <ChevronRight :size="20" aria-hidden="true" />
          </button>

          <section class="booking-note">
            <ShieldCheck :size="20" aria-hidden="true" />
            <p>提交预约前请再次确认档期、地点、交付标准、版权范围与改期规则，最终以订单快照为准。</p>
          </section>

          <div class="comments-section">
            <EngagementPanel
              compact
              :key="commentRefreshKey"
              target-type="package"
              :target-id="offer.id"
              @message="toastMessage = $event"
            />
          </div>

        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2500"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <ion-footer v-if="offer && !loading" class="work-footer">
      <div v-if="commentMode" class="comment-backdrop" @click="exitCommentMode" />
      <div v-if="!commentMode" class="bottom-bar">
        <button
          type="button"
          class="bar-action"
          :class="{ active: favorited }"
          :aria-label="favorited ? '取消收藏方案' : '收藏方案'"
          :aria-pressed="favorited"
          :disabled="favoriteLoading"
          @click="toggleFavorite"
        >
          <ion-spinner v-if="favoriteLoading" name="crescent" aria-hidden="true" />
          <Bookmark v-else :size="25" :fill="favorited ? 'currentColor' : 'none'" aria-hidden="true" />
        </button>

        <button
          type="button"
          class="bar-action"
          aria-label="咨询方案"
          @click="goConversation"
        >
          <MessageSquareText :size="25" aria-hidden="true" />
        </button>

        <button type="button" class="primary-button pressable" @click="goBooking">
          <CalendarPlus :size="18" aria-hidden="true" />
          选择档期预约
        </button>

        <div class="comment-trigger" @click="enterCommentMode">
          <MessageCircle :size="25" aria-hidden="true" />
          <span class="comment-placeholder">评论…</span>
        </div>
      </div>
      <div v-else class="comment-bar" @click.stop>
        <input
          ref="commentInputRef"
          v-model="commentDraft"
          class="comment-input"
          type="text"
          placeholder="聊聊你感兴趣的拍摄…"
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
import {
  Bookmark,
  CalendarPlus,
  ChevronRight,
  Clock3,
  FilePenLine,
  Images,
  MapPin,
  MessageCircle,
  MessageSquareText,
  PackageCheck,
  Send,
  ShieldCheck,
} from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailAgentAction from '@/components/DetailAgentAction.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import EngagementPanel from '@/components/EngagementPanel.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import ImageCarousel from '@/components/ImageCarousel.vue'
import MediaPlaceholder from '@/components/MediaPlaceholder.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPackageDetail } from '@/api/discovery'
import { createComment } from '@/api/engagement'
import { getPackageFavoriteStatus, togglePackageFavorite } from '@/api/social'
import { useAuthStore } from '@/stores/auth'
import type { PackageOffer } from '@/types/discovery'
import { formatCurrency, formatDuration, getPackageName } from '@/utils/format'
import { getPackagePreviewUrl, resolveMediaUrl } from '@/utils/media'
import { buildPackagePageContext, stageAIPageContext } from '@/utils/aiPageContext'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const offer = ref<PackageOffer | null>(null)
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')
const favorited = ref(false)
const favoriteLoading = ref(false)
const commentMode = ref(false)
const commentDraft = ref('')
const submittingComment = ref(false)
const commentInputRef = ref<HTMLInputElement | null>(null)
const commentRefreshKey = ref(0)

const coverUrl = computed(() => (offer.value ? getPackagePreviewUrl(offer.value) : ''))
const sampleUrls = computed(() =>
  (offer.value?.samples || []).filter(Boolean).map(resolveMediaUrl),
)

const agentDisabled = computed(() => loading.value || !!error.value || !offer.value)
const isOwner = computed(() => Boolean(
  offer.value?.photographer_id && auth.user?.id === offer.value.photographer_id,
))

function openAgent() {
  if (!offer.value) return
  const context = buildPackagePageContext(offer.value, route)
  const handoffKey = stageAIPageContext(context)
  void router.push({ name: 'ai-assistant', query: { context: handoffKey } })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    await auth.initialize()
    const packageId = String(route.params.packageId)
    const [detail, favoriteStatus] = await Promise.all([
      getPackageDetail(packageId),
      getPackageFavoriteStatus(packageId).catch(() => false),
    ])
    offer.value = detail
    favorited.value = favoriteStatus
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function refreshFavoriteStatus() {
  if (!offer.value) return
  favorited.value = await getPackageFavoriteStatus(offer.value.id).catch(() => false)
}

async function toggleFavorite() {
  if (!offer.value || favoriteLoading.value) return
  if (!auth.isAuthenticated) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  if (!offer.value.photographer_id) {
    toastMessage.value = '方案缺少摄影师信息，暂时无法收藏。'
    return
  }
  favoriteLoading.value = true
  try {
    favorited.value = await togglePackageFavorite(offer.value, offer.value.photographer_id)
    toastMessage.value = favorited.value ? '方案已加入收藏' : '已取消方案收藏'
  } catch (favoriteError) {
    toastMessage.value = getApiErrorMessage(favoriteError)
  } finally {
    favoriteLoading.value = false
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
  if (!offer.value || submittingComment.value || !commentDraft.value.trim()) return
  submittingComment.value = true
  try {
    await createComment('package', offer.value.id, commentDraft.value.trim())
    toastMessage.value = '评论已发布'
    commentRefreshKey.value++
    exitCommentMode()
  } catch (commentError) {
    toastMessage.value = getApiErrorMessage(commentError)
  } finally {
    submittingComment.value = false
  }
}

function goPhotographer() {
  if (offer.value?.photographer_id) {
    router.push({ name: 'photographer-detail', params: { userId: offer.value.photographer_id } })
  }
}

function goEdit() {
  if (!offer.value || !isOwner.value) return
  void router.push({ name: 'package-edit', params: { packageId: offer.value.id } })
}

function goBooking() {
  if (!offer.value?.photographer_id) return
  router.push({
    name: 'booking',
    params: { userId: offer.value.photographer_id },
    query: { packageId: offer.value.id, locked: '1' },
  })
}

function goConversation() {
  if (!offer.value?.photographer_id) return
  const title = getPackageName(offer.value)
  void router.push({
    name: 'conversation',
    params: { userId: offer.value.photographer_id },
    query: {
      introType: 'package',
      introTitle: title,
      introUrl: `/packages/${offer.value.id}`,
      ...(coverUrl.value ? { introCoverUrl: coverUrl.value } : {}),
      introText: `你好，我想咨询「${title}」的档期和服务细节。`,
    },
  })
}

watch(() => auth.token, () => void refreshFavoriteStatus())
onMounted(() => void load())
</script>

<style scoped>
.detail-content { --background: var(--paper); }
.detail-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding-bottom: var(--space-8); }
.header-action { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; background: transparent; color: var(--ink); }

/* ── Bottom Bar ── */

.work-footer { background: var(--paper); }

.comment-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: transparent;
}

.bottom-bar {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: auto auto auto 1fr;
  align-items: center;
  gap: var(--space-2);
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding: calc(var(--space-2) + 3px) var(--space-4) calc(var(--space-2) + 3px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--divider);
  background: var(--paper);
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
  color: var(--ink-secondary);
}

.bar-action.active {
  color: var(--brand);
}

.bar-action:disabled {
  color: var(--ink-tertiary);
  opacity: 0.6;
}

.bar-action ion-spinner {
  width: 24px;
  height: 24px;
}

.primary-button {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0 var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
  font-weight: 700;
}

.primary-button:active { background: var(--neu-surface-brand); box-shadow: var(--neu-inset-brand); }

.primary-button:disabled {
  background: var(--paper-deep);
  box-shadow: none;
  color: var(--ink-tertiary);
  opacity: .75;
}

.comment-trigger {
  display: flex;
  min-height: 48px;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: 0 var(--space-3);
  border: 0;
  border-radius: var(--radius-pill);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--ink-tertiary);
  cursor: text;
  font-size: var(--text-base);
}

.comment-placeholder {
  font-size: var(--text-base);
  white-space: nowrap;
}

.comment-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: min(100%, var(--content-max));
  margin: 0 auto;
  padding: calc(var(--space-2) + 3px) var(--space-4) calc(var(--space-2) + 3px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--divider);
  background: var(--paper);
}

.comment-input {
  flex: 1;
  min-width: 0;
  min-height: 48px;
  padding: 0 var(--space-3);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--ink);
  font-size: var(--text-base);
  outline: none;
}

.comment-input:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px var(--focus-ring); }

.comment-input:disabled {
  opacity: 0.6;
}

.send-button {
  display: inline-flex;
  min-width: 44px;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  padding: 0 var(--space-3);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: var(--shadow-1);
  color: var(--white);
}

.send-button:disabled {
  background: var(--paper-deep);
  box-shadow: none;
  color: var(--ink-tertiary);
}

.send-button ion-spinner {
  width: 22px;
  height: 22px;
}

.cover-placeholder-wrap {
  aspect-ratio: 16 / 10;
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.summary-section { padding: var(--space-5) var(--space-4); border-bottom: 1px solid var(--divider); }
.summary-section h1 { margin: var(--space-3) 0 4px; font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.45; }
.summary-section > p { margin: var(--space-3) 0 0; color: var(--ink-secondary); font-size: var(--text-base); line-height: 1.75; white-space: pre-wrap; }

.price-row { display: flex; align-items: baseline; gap: 4px; }
.price-row strong { color: var(--brand); font-size: var(--text-xl); font-variant-numeric: tabular-nums; }
.price-row span { color: var(--ink-tertiary); font-size: var(--text-xs); }

.facts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-2);
  margin: var(--space-4);
}

.facts-grid div { display: grid; min-height: 112px; align-content: center; gap: 5px; padding: var(--space-4); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); }
.facts-grid span { color: var(--ink-tertiary); font-size: var(--text-xs); }
.facts-grid strong { color: var(--ink); font-size: var(--text-sm); line-height: 1.45; }

.photographer-card {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 24px;
  width: calc(100% - 32px);
  align-items: center;
  gap: var(--space-3);
  margin: var(--space-5) var(--space-4);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  color: var(--ink);
  text-align: left;
}

.photographer-card > span { display: grid; gap: 3px; min-width: 0; }
.photographer-card small { color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.photographer-card strong { font-size: var(--text-base); }
.photographer-card em { overflow: hidden; color: var(--ink-tertiary); font-size: var(--text-xs); font-style: normal; text-overflow: ellipsis; white-space: nowrap; }

.booking-note { display: flex; gap: var(--space-3); margin: 0 var(--space-4) var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--brand); }
.booking-note p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.comments-section { padding: 0 var(--space-4) var(--space-8); }
</style>
