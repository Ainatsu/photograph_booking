<template>
  <ion-page>
      <AppTopBar left-label="返回" @left-action="goBack" :show-search="false">
        <template #left>
          <ChevronLeft :size="22" aria-hidden="true" />
        </template>
      </AppTopBar>

    <ion-content ref="ionContentRef" class="page-content" @ionScroll="onIonScroll">
      <main class="page-shell">

        <FeedSkeleton v-if="loading" :count="4" />

        <template v-else>
          <section v-if="messages.length === 0 && !sending && !pageContext" class="welcome-card">
            <div class="welcome-icon"><Bot :size="36" aria-hidden="true" /></div>
            <h2>我是小龟J，你的 AI 摄影助手</h2>
            <p>我可以帮你解答摄影相关的疑问、提供创意建议、分析作品风格等。有什么可以帮你的吗？</p>
          </section>

          <section v-if="messages.length" ref="messageListRef" class="message-list" aria-label="对话记录">
            <article
              v-for="(msg, index) in messages"
              :key="msg.id || index"
              class="message-row"
              :class="{ 'message-user': msg.role === 'user', 'message-ai': msg.role === 'assistant' }"
            >
              <div class="message-content">
                <div v-if="msg.attachments && msg.attachments.length" class="attachment-grid">
                  <img
                    v-for="(att, imgIdx) in msg.attachments"
                    :key="imgIdx"
                    :src="resolveMediaUrl(attachmentUrl(att))"
                    alt="附带图片"
                    class="attachment-thumb"
                    loading="lazy"
                    @click="previewImage(attachmentUrl(att))"
                  />
                </div>
                <AIPageContextCard
                  v-if="msg.role === 'user' && getMessagePageContext(msg)"
                  :context="getMessagePageContext(msg)!"
                  clickable
                  class="message-context-card"
                  @open-source="openSource(getMessagePageContext(msg)!)"
                />
                <!-- AI：分段气泡栈 -->
                <template v-if="msg.role === 'assistant'">
                  <div class="assistant-bubble-stack" aria-live="polite" aria-atomic="false">
                    <TransitionGroup name="assistant-bubble" tag="div" class="assistant-bubble-list">
                      <div
                        v-for="(segment, segIdx) in visibleSegments(msg)"
                        :key="`${msg.id}-seg-${segIdx}`"
                        class="message-bubble"
                      >
                        <p class="message-text">{{ segment }}</p>
                      </div>
                    </TransitionGroup>
                  </div>
                  <!-- 推荐面板 -->
                  <template v-if="isAssistantRevealComplete(msg)">
                    <!-- 等文字流式展示完成后再插入结构化卡片，避免消息高度持续跳动。 -->
                    <AIWebReferenceImages
                      v-if="msg.metadata?.web_reference_images?.items?.length"
                      :items="msg.metadata.web_reference_images.items"
                    />
                    <AIShootContextCard
                      v-if="msg.metadata?.shoot_context"
                      :context="msg.metadata.shoot_context"
                      :disabled="sending"
                      class="shoot-context-message-card"
                      @select-candidate="selectShootContextCandidate($event, msg)"
                    />
                    <InspirationQuickEntryCard
                      v-if="inspirationEntry(msg)"
                      :entry="inspirationEntry(msg)!"
                      @open="openInspiration(inspirationEntry(msg)!.inspiration_id)"
                      @edit="editInspiration(inspirationEntry(msg)!.inspiration_id)"
                    />
                    <div v-if="hasReferences(msg.metadata?.references)" class="references-wrap">
                      <div class="references-header">
                        <Sparkles :size="16" aria-hidden="true" />
                        <span>推荐</span>
                      </div>
                      <div v-if="jointPackages(msg.metadata?.references).length" class="joint-package-list">
                        <div v-if="jointRecommendation(msg)?.relaxations?.length" class="joint-status" role="status">
                          <AlertCircle :size="17" aria-hidden="true" />
                          <div>
                            <strong>已为你调整条件</strong>
                            <p v-for="item in jointRecommendation(msg)?.relaxations" :key="item.code">{{ item.label }}</p>
                          </div>
                        </div>
                        <JointRecommendationFilters
                          :slots="msg.metadata?.task_state?.slots"
                          :disabled="sending"
                          @apply="applyJointFilters($event, msg)"
                        />
                        <BookablePackageCard
                          v-for="pkg in jointPackages(msg.metadata?.references)"
                          :key="'bookable-' + pkg.id"
                          :item="pkg"
                          @details="goRefPackage($event, msg)"
                          @select-time="goBookPackage($event, msg)"
                          @refresh="refreshJointRecommendations"
                        />
                      </div>
                      <div class="ref-grid">
                        <button
                          v-for="p in (msg.metadata?.references?.photographers || [])"
                          :key="'p-' + (p.user_id || p.id || p.name)"
                          type="button"
                          class="ref-card pressable"
                          @click="goRefPhotographer(p)"
                        >
                          <span class="ref-card-media">
                            <img
                              v-if="p.user_avatar_url || p.avatar_url"
                              :src="resolveMediaUrl(p.user_avatar_url || p.avatar_url)"
                              :alt="p.user_display_name || p.name"
                            />
                            <span v-else class="ref-card-fallback">{{ (p.user_display_name || p.name || '?')[0] }}</span>
                          </span>
                          <span class="ref-card-label">{{ p.user_display_name || p.name }}</span>
                        </button>
                        <button
                          v-for="w in (msg.metadata?.references?.portfolio_items || [])"
                          :key="'w-' + (w.id || w.title)"
                          type="button"
                          class="ref-card pressable"
                          @click="goRefWork(w)"
                        >
                          <span class="ref-card-media">
                            <img
                              v-if="w.thumbnail_url || w.url"
                              :src="resolveMediaUrl(w.thumbnail_url || w.url)"
                              :alt="w.title"
                            />
                            <span v-else class="ref-card-fallback">{{ (w.title || '?')[0] }}</span>
                          </span>
                          <span class="ref-card-label">{{ w.title }}</span>
                        </button>
                        <button
                          v-for="pkg in legacyPackages(msg.metadata?.references)"
                          :key="'pkg-' + (pkg.id || pkg.package_name || pkg.name)"
                          type="button"
                          class="ref-card pressable"
                          @click="goRefPackage(pkg)"
                        >
                          <span class="ref-card-media">
                            <img
                              v-if="getPackageCover(pkg)"
                              :src="resolveMediaUrl(getPackageCover(pkg))"
                              :alt="pkg.package_name || pkg.name"
                            />
                            <span v-else class="ref-card-fallback">{{ (pkg.package_name || pkg.name || '¥')[0] }}</span>
                          </span>
                          <span class="ref-card-label">{{ pkg.package_name || pkg.name }}</span>
                        </button>
                        <button
                          v-for="proj in (msg.metadata?.references?.projects || [])"
                          :key="'proj-' + (proj.id || proj.title)"
                          type="button"
                          class="ref-card pressable project-ref-card"
                          @click="goRefProject(proj)"
                        >
                          <span class="ref-card-media project-ref-media">
                            <MediaPlaceholder v-if="!proj.reference_images?.[0]" class="ref-card-fallback" />
                            <img
                              v-else
                              :src="resolveMediaUrl(proj.reference_images[0])"
                              :alt="proj.title"
                            />
                          </span>
                          <span class="ref-card-details">
                            <span class="ref-card-label">{{ proj.title }}</span>
                            <span v-if="proj.city" class="ref-card-sub">{{ proj.city }}</span>
                            <span v-if="proj.match_reason" class="ref-card-reason">{{ proj.match_reason }}</span>
                          </span>
                        </button>
                      </div>
                    </div>
                    <div v-if="jointRecommendation(msg)?.no_result" class="joint-empty" role="status">
                      <AlertCircle :size="22" aria-hidden="true" />
                      <div>
                        <strong>暂时没有真实可预约的匹配方案</strong>
                        <p>系统已按顺序尝试风格、距离、同日其他时间、前后 3 天和可接受的轻微预算浮动；固定日期和严格预算不会被自动放宽。</p>
                      </div>
                      <JointRecommendationFilters
                        :slots="msg.metadata?.task_state?.slots"
                        :disabled="sending"
                        @apply="applyJointFilters($event, msg)"
                      />
                    </div>
                    <!-- 时间戳：AI 回复完成时显示 -->
                    <time class="message-time">{{ formatTime(msg.created_at) }}</time>
                  </template>
                </template>
                <!-- 用户消息：保持原有样式 -->
                <template v-else>
                  <div class="message-bubble">
                    <p v-for="(paragraph, pIdx) in splitParagraphs(msg.content)" :key="pIdx" class="message-text">
                      {{ paragraph }}
                    </p>
                  </div>
                  <time class="message-time">{{ formatTime(msg.created_at) }}</time>
                </template>
              </div>
            </article>

            <div v-if="sending && !activeRevealMessageId" class="message-row message-ai">
              <div class="message-content">
                <div class="message-bubble typing-indicator">
                  <span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>
                </div>
              </div>
            </div>
          </section>
        </template>
      </main>
    </ion-content>

    <div class="bottom-dock">
      <div v-if="activeTask" class="task-dock" aria-live="polite">
        <AgentTaskSummaryCard
          :task="activeTask"
          :busy="taskActionBusy"
          @cancel="cancelActiveTask"
          @edit="editActiveTask"
          @continue="continueActiveTask"
          @commit="commitActiveTask"
        />
      </div>

        <div class="input-bar-shell">
        <div v-if="pageContext" class="pending-context-wrap">
          <AIPageContextCard
            :context="pageContext"
            removable
            @remove="pageContext = null"
          />
        </div>

        <div v-if="uploadedImages.length" class="image-preview-list">
          <div v-for="(img, idx) in uploadedImages" :key="idx" class="image-preview-item">
            <img :src="img.thumbUrl || img.url" alt="已选图片" class="image-preview-thumb" />
            <button type="button" class="image-remove-btn pressable" aria-label="移除图片" @click="removeUploadedImage(idx)">
              <X :size="14" aria-hidden="true" />
            </button>
          </div>
        </div>

        <form class="input-bar" @submit.prevent="submitMessage">
          <div class="composer-heading">
            <span class="composer-kicker">小龟J Agent</span>
            <span class="composer-hint">选择 Agent 能力或联网工具</span>
          </div>
          <div v-if="selectedAgent" class="agent-brief-card">
            <div class="agent-brief-title">
              <span class="agent-brief-icon"><component :is="selectedAgent.icon" :size="16" aria-hidden="true" /></span>
              <strong>{{ selectedAgent.label }}</strong>
              <button type="button" class="agent-clear-btn pressable" aria-label="取消选择能力" @click="clearAgentSelection"><X :size="15" /></button>
            </div>
            <div class="agent-field-grid">
              <label v-for="field in selectedAgent.fields" :key="field.key" class="agent-field" :class="{ 'agent-field--wide': field.wide }">
                <span>{{ field.label }}</span>
                <input v-model="agentForm[field.key]" :type="field.type || 'text'" :placeholder="field.placeholder" :disabled="sending" />
              </label>
            </div>
          </div>
          <div class="composer-controls">
            <button
              type="button"
              class="attach-button pressable"
              aria-label="上传图片"
              :disabled="sending"
              @click="triggerFileInput"
            >
              <Paperclip :size="20" aria-hidden="true" />
            </button>
            <input
              ref="fileInputRef"
              type="file"
              accept="image/*"
              multiple
              class="sr-only"
              @change="handleFileSelect"
            />
            <label for="ai-message-draft" class="sr-only">输入消息</label>
            <textarea
              id="ai-message-draft"
              ref="messageInputRef"
              v-model="draft"
              rows="1"
              maxlength="2000"
              :placeholder="inputPlaceholder"
              :disabled="sending"
              @keydown.enter.prevent="submitMessage"
            />
            <button
              type="submit"
              class="send-button pressable"
              :class="{ 'send-button--revealing': !!activeRevealMessageId }"
              aria-label="发送"
              :disabled="sending || !hasComposerContent"
            >
              <template v-if="activeRevealMessageId">
                <RotateCw :size="20" class="spin-icon" aria-hidden="true" />
              </template>
              <ion-spinner v-else-if="sending" name="crescent" aria-hidden="true" />
              <ArrowUp v-else :size="20" aria-hidden="true" />
            </button>
          </div>
          <div class="agent-capability-shell">
            <button
              v-if="capabilityOverflow"
              type="button"
              class="capability-nav pressable"
              aria-label="向左查看更多 Agent 能力"
              :disabled="!canScrollCapabilitiesLeft"
              @click="scrollCapabilities(-1)"
            >
              <ChevronLeft :size="18" aria-hidden="true" />
            </button>
            <div
              ref="capabilityScrollerRef"
              class="agent-capability-row"
              role="list"
              aria-label="Agent 能力"
              @scroll="updateCapabilityScrollState"
            >
              <button
                type="button"
                class="agent-capability pressable"
                :class="{ 'agent-capability--active': webSearchEnabled }"
                :aria-pressed="webSearchEnabled"
                :disabled="sending"
                @click="toggleWebSearch"
              >
                <Globe2 :size="17" aria-hidden="true" />
                <span>联网搜索</span>
              </button>
              <button
                v-for="agent in agentCapabilities"
                :key="agent.key"
                type="button"
                class="agent-capability pressable"
                :class="{ 'agent-capability--active': selectedAgent?.key === agent.key }"
                :aria-pressed="selectedAgent?.key === agent.key"
                :disabled="sending"
                @click="selectAgent(agent)"
              >
                <component :is="agent.icon" :size="17" aria-hidden="true" />
                <span>{{ agent.label }}</span>
              </button>
            </div>
            <button
              v-if="capabilityOverflow"
              type="button"
              class="capability-nav pressable"
              aria-label="向右查看更多 Agent 能力"
              :disabled="!canScrollCapabilitiesRight"
              @click="scrollCapabilities(1)"
            >
              <ChevronRight :size="18" aria-hidden="true" />
            </button>
          </div>
        </form>
      </div>
    </div>

    <ion-toast
      :is-open="Boolean(toastMessage)"
      :message="toastMessage"
      :duration="3000"
      position="bottom"
      @did-dismiss="toastMessage = ''"
    />
  </ion-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage, IonSpinner, IonToast, alertController } from '@ionic/vue'
import { AlertCircle, ArrowUp, Bot, CalendarPlus, ChevronLeft, ChevronRight, Clock, FilePlus2, Globe2, Images, MapPin, PackagePlus, Paperclip, RotateCw, Send, Sparkles, X } from 'lucide-vue-next'
import AIPageContextCard from '@/components/AIPageContextCard.vue'
import AIShootContextCard from '@/components/AIShootContextCard.vue'
import AIWebReferenceImages from '@/components/AIWebReferenceImages.vue'
import BookablePackageCard from '@/components/BookablePackageCard.vue'
import JointRecommendationFilters from '@/components/JointRecommendationFilters.vue'
import AgentTaskSummaryCard from '@/components/AgentTaskSummaryCard.vue'
import InspirationQuickEntryCard, { type InspirationQuickEntry } from '@/components/InspirationQuickEntryCard.vue'
import AppTopBar from '@/components/AppTopBar.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import MediaPlaceholder from '@/components/MediaPlaceholder.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  createAIConversation,
  getAIConversations,
  getAIMessages,
  sendAIMessage,
  uploadAIImage,
  type AIMessage,
  type AIChatResponse,
  type AIPageContext,
  type AIConversation,
  type AIShootContextPlace,
} from '@/api/ai'
import { cancelAgentTask, commitAgentTask, getActiveAgentTask, openAgentTask } from '@/api/agentTasks'
import { useAuthStore } from '@/stores/auth'
import { resolveMediaUrl } from '@/utils/media'
import { segmentAssistantReply } from '@/utils/aiMessageSegments'
import { buildAssistantRevealSchedule } from '@/utils/assistantReveal'
import { consumeAIPageContext, getSourceRoute } from '@/utils/aiPageContext'
import type { AgentTask } from '@/types/agentTask'
import { getAgentTaskRoute } from '@/utils/agentTaskRoutes'
import { trackRecommendationEvents, type BookablePackageRecommendation, type RecommendationEvent } from '@/api/recommendations'

const AI_CONVERSATION_KEY = 'ai_active_conversation_id'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const messages = ref<AIMessage[]>([])
const draft = ref('')
const sending = ref(false)
const loading = ref(true)
const toastMessage = ref('')
const conversation = ref<AIConversation | null>(null)
const uploadedImages = ref<{ url: string; thumbUrl?: string; file: File }[]>([])
const messageListRef = ref<HTMLElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const messageInputRef = ref<HTMLTextAreaElement | null>(null)
const capabilityScrollerRef = ref<HTMLElement | null>(null)
const capabilityOverflow = ref(false)
const canScrollCapabilitiesLeft = ref(false)
const canScrollCapabilitiesRight = ref(false)
let capabilityResizeObserver: ResizeObserver | null = null
const pageContext = ref<AIPageContext | null>(null)
const activeTask = ref<AgentTask | null>(null)
const taskActionBusy = ref(false)
const trackedJointEvents = new Set<string>()

interface AgentCapabilityField {
  key: string
  label: string
  placeholder: string
  type?: string
  wide?: boolean
}

interface AgentCapability {
  key: AgentTask['task_type']
  label: string
  icon: Component
  fields: AgentCapabilityField[]
}

const agentCapabilities: AgentCapability[] = [
  {
    key: 'create_inspiration',
    label: '创作灵感',
    icon: Sparkles,
    fields: [],
  },
  {
    key: 'create_project',
    label: '发布企划',
    icon: FilePlus2,
    fields: [
      { key: 'title', label: '企划标题', placeholder: '例如：香港街拍招募', wide: true },
      { key: 'city', label: '拍摄城市', placeholder: '香港' },
      { key: 'shoot_date', label: '拍摄日期', placeholder: '', type: 'date' },
      { key: 'budget', label: '预算', placeholder: '例如：1500-2500' },
    ],
  },
  {
    key: 'publish_package',
    label: '发布方案',
    icon: PackagePlus,
    fields: [
      { key: 'name', label: '方案名称', placeholder: '例如：城市人像轻旅拍', wide: true },
      { key: 'price', label: '价格', placeholder: '例如：1280', type: 'number' },
      { key: 'duration', label: '拍摄时长', placeholder: '例如：120 分钟' },
      { key: 'city', label: '服务城市', placeholder: '香港' },
    ],
  },
  {
    key: 'publish_work',
    label: '发布作品',
    icon: Images,
    fields: [
      { key: 'title', label: '作品标题', placeholder: '给这组作品起个名字', wide: true },
      { key: 'tags', label: '风格标签', placeholder: '胶片、街拍、纪实', wide: true },
    ],
  },
  {
    key: 'project_application',
    label: '申请企划',
    icon: Send,
    fields: [
      { key: 'project', label: '目标企划', placeholder: '输入企划名称或链接', wide: true },
      { key: 'price_quote', label: '报价', placeholder: '例如：1800', type: 'number' },
      { key: 'proposal', label: '应邀说明', placeholder: '简述你的拍摄方案', wide: true },
    ],
  },
  {
    key: 'create_booking',
    label: '预约拍摄',
    icon: CalendarPlus,
    fields: [
      { key: 'target', label: '摄影师或方案', placeholder: '输入名称', wide: true },
      { key: 'appointment_date', label: '预约日期', placeholder: '', type: 'date', wide: true },
      { key: 'notes', label: '拍摄备注', placeholder: '地点、人数或特殊要求', wide: true },
    ],
  },
]

const selectedAgent = ref<AgentCapability | null>(null)
const agentForm = reactive<Record<string, string>>({})
const webSearchEnabled = ref(false)

// ── 渐进显示状态 ──
const visibleSegmentCounts = reactive<Record<string, number>>({})
const activeRevealMessageId = ref<string | null>(null)
const revealTimers = new Set<ReturnType<typeof setTimeout>>()
const segmentCache = new Map<string, string[]>()
const ionContentRef = ref<any>(null)
const isUserNearBottom = ref(true)

watch(activeTask, async (task, previousTask) => {
  if (!task || task === previousTask || !messages.value.length) return
  // The dock is outside ion-content, so re-align after it mounts.
  await nextTick()
  await scrollToBottom(false)
})

watch(
  () => route.query.context,
  (contextKey) => {
    pageContext.value = typeof contextKey === 'string'
      ? consumeAIPageContext(contextKey)
      : null
  },
  { immediate: true },
)

const inputPlaceholder = computed(() => {
  if (activeTask.value?.summary.next_question) return activeTask.value.summary.next_question
  if (selectedAgent.value?.key === 'create_inspiration') return '上传参考图，并补充想要的风格或拍摄方向'
  if (selectedAgent.value) return `补充${selectedAgent.value.label}的需求，Agent 会继续引导你`
  if (webSearchEnabled.value) return '输入需要联网查找的最新信息…'
  if (pageContext.value?.title) {
    const title = pageContext.value.title
    return `围绕「${title.length > 20 ? title.slice(0, 20) + '…' : title}」问小龟J`
  }
  return '给小龟J发送消息…'
})

const hasComposerContent = computed(() => Boolean(
  draft.value.trim()
  || uploadedImages.value.length
  || (selectedAgent.value && Object.values(agentForm).some((value) => value.trim())),
))

function selectAgent(agent: AgentCapability) {
  if (selectedAgent.value?.key === agent.key) {
    clearAgentSelection()
    return
  }
  webSearchEnabled.value = false
  selectedAgent.value = agent
  Object.keys(agentForm).forEach((key) => delete agentForm[key])
  void nextTick(() => {
    if (agent.key === 'create_inspiration' && !uploadedImages.value.length) triggerFileInput()
    else messageInputRef.value?.focus()
  })
}

function toggleWebSearch() {
  webSearchEnabled.value = !webSearchEnabled.value
  if (webSearchEnabled.value) clearAgentSelection()
  void nextTick(() => messageInputRef.value?.focus())
}

function clearAgentSelection() {
  selectedAgent.value = null
  Object.keys(agentForm).forEach((key) => delete agentForm[key])
}

function structuredAgentMessage(): string {
  if (webSearchEnabled.value) {
    const query = draft.value.trim()
    return query
      ? `请联网搜索并仅根据最新公开网页资料回答：${query}\n请附上来源，并明确区分网页事实与推断。`
      : '请结合我上传的图片进行联网搜索，查找相关的最新公开资料，并附上来源。'
  }
  if (!selectedAgent.value) return draft.value.trim()
  if (selectedAgent.value.key === 'create_inspiration') {
    const reference = draft.value.trim()
    return reference
      ? `请根据我上传的参考图片创建灵感。补充说明：${reference}`
      : '请根据我上传的参考图片创建灵感'
  }
  const details = selectedAgent.value.fields
    .map((field) => ({ label: field.label, value: agentForm[field.key]?.trim() }))
    .filter((item) => item.value)
  const lines = [`我想让 Agent 帮我${selectedAgent.value.label}。`]
  if (details.length) {
    lines.push('已填写信息：', ...details.map((item) => `- ${item.label}：${item.value}`))
  }
  if (draft.value.trim()) lines.push(`补充说明：${draft.value.trim()}`)
  lines.push('请根据以上信息创建结构化任务，并继续询问尚缺的必要信息。')
  return lines.join('\n')
}

function updateCapabilityScrollState() {
  const scroller = capabilityScrollerRef.value
  if (!scroller) return
  const maxScrollLeft = Math.max(0, scroller.scrollWidth - scroller.clientWidth)
  capabilityOverflow.value = maxScrollLeft > 1
  canScrollCapabilitiesLeft.value = scroller.scrollLeft > 1
  canScrollCapabilitiesRight.value = scroller.scrollLeft < maxScrollLeft - 1
}

function scrollCapabilities(direction: number) {
  const scroller = capabilityScrollerRef.value
  if (!scroller) return
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  scroller.scrollBy({
    left: direction * Math.max(180, scroller.clientWidth * 0.72),
    behavior: reduceMotion ? 'auto' : 'smooth',
  })
}

type MessageAttachment = string | { type: string; url: string; mime_type?: string }

function attachmentUrl(att: MessageAttachment): string {
  return typeof att === 'string' ? att : att.url
}

function getMessagePageContext(msg: AIMessage): AIPageContext | null {
  if (msg.metadata?.page_context) {
    return msg.metadata.page_context as AIPageContext
  }
  return msg.page_context || null
}

function openSource(ctx: AIPageContext) {
  const source = getSourceRoute(ctx)
  if (source) {
    void router.push(source)
  }
}

async function cancelActiveTask() {
  if (!activeTask.value || !conversation.value || taskActionBusy.value) return
  if (activeTask.value.summary.collected_count) {
    const alert = await alertController.create({
      header: '取消当前任务',
      message: '只会丢弃 Agent 整理的任务，不会删除已发布内容。',
      buttons: [{ text: '继续聊天', role: 'cancel' }, { text: '确认取消', role: 'destructive' }],
    })
    await alert.present()
    const result = await alert.onDidDismiss()
    if (result.role !== 'destructive') return
  }
  taskActionBusy.value = true
  try {
    await cancelAgentTask(conversation.value.id, activeTask.value.task_id)
    activeTask.value = null
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    taskActionBusy.value = false
  }
}

async function continueActiveTask() {
  if (!activeTask.value || taskActionBusy.value) return
  await nextTick()
  messageInputRef.value?.focus()
}

async function editActiveTask() {
  if (!activeTask.value || !conversation.value || taskActionBusy.value) return
  const target = getAgentTaskRoute(activeTask.value)
  if (!target) {
    toastMessage.value = '任务信息还不完整，暂时无法打开专门页面。请继续聊天补充目标信息。'
    return
  }
  taskActionBusy.value = true
  try {
    await openAgentTask(conversation.value.id, activeTask.value.task_id)
    await router.push(target)
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    taskActionBusy.value = false
  }
}

async function commitActiveTask() {
  if (!activeTask.value || !conversation.value || taskActionBusy.value || !activeTask.value.summary.can_commit) return
  taskActionBusy.value = true
  try {
    const response = await commitAgentTask(
      conversation.value.id,
      activeTask.value.task_id,
      activeTask.value.revision,
    )
    activeTask.value = response.task.status === 'completed' ? null : response.task
    await appendAssistantMessage(response.assistant_message as AIMessage)
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
    activeTask.value = await getActiveAgentTask(conversation.value.id)
  } finally {
    taskActionBusy.value = false
  }
}

async function selectShootContextCandidate(candidate: AIShootContextPlace, msg: AIMessage) {
  if (!conversation.value || sending.value) return
  const sourceMessageId = Number(msg.id)
  if (!Number.isInteger(sourceMessageId) || !Number.isFinite(candidate.latitude) || !Number.isFinite(candidate.longitude)) {
    toastMessage.value = '地点候选已失效，请重新查询天气'
    return
  }

  sending.value = true
  try {
    const result = await sendAIMessage(conversation.value.id, {
      content: `选择地点：${candidate.address || candidate.name}`,
      shoot_context_selection: {
        source_message_id: sourceMessageId,
        latitude: candidate.latitude,
        longitude: candidate.longitude,
      },
    })
    await appendChatResult(result)
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    sending.value = false
  }
}

// ── 渐进显示 — 可见分段 ──
function visibleSegments(msg: AIMessage): string[] {
  let segments = segmentCache.get(msg.id)
  if (!segments) {
    segments = segmentAssistantReply(msg.content)
    segmentCache.set(msg.id, segments)
  }
  const count = visibleSegmentCounts[msg.id]
  // count 不存在（历史消息）或 >= 总段数时显示全部
  if (count === undefined || count >= segments.length) return segments
  return segments.slice(0, count)
}

function isAssistantRevealComplete(msg: AIMessage): boolean {
  if (msg.role !== 'assistant') return true
  const segments = segmentAssistantReply(msg.content)
  const count = visibleSegmentCounts[msg.id]
  return count === undefined || count >= segments.length
}

// ── 滚动位置追踪 ──
function onIonScroll(ev: CustomEvent) {
  const detail = ev.detail as any
  if (detail && typeof detail.scrollHeight === 'number') {
    const threshold = 96
    isUserNearBottom.value = (detail.scrollHeight - detail.scrollTop - detail.clientHeight) <= threshold
  }
}

async function scrollToBottomIfNear() {
  if (!isUserNearBottom.value) return
  await scrollToBottom()
}

// ── 清除渐进显示状态 ──
function clearRevealState() {
  for (const timer of revealTimers) {
    clearTimeout(timer)
  }
  revealTimers.clear()
  activeRevealMessageId.value = null
}

// ── 统一入口：追加助手消息并渐进显示 ──
function appendAssistantMessage(message: AIMessage, animate = true): Promise<void> {
  const segments = segmentAssistantReply(message.content)
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const noAnimation = !animate || reduceMotion || segments.length <= 1

  if (noAnimation) {
    // 一次性显示完整消息
    messages.value.push(message)
    trackJointMessage(message)
    void nextTick(() => scrollToBottomIfNear())
    return Promise.resolve()
  }

  // 动画模式
  activeRevealMessageId.value = message.id
  visibleSegmentCounts[message.id] = 1
  messages.value.push(message)
  trackJointMessage(message)

  return new Promise<void>((resolve) => {
    const schedule = buildAssistantRevealSchedule(segments)
    schedule.forEach((step, index) => {
      const timer = setTimeout(() => {
        revealTimers.delete(timer)
        visibleSegmentCounts[message.id] = Math.max(
          visibleSegmentCounts[message.id] || 0,
          step.visibleCount,
        )
        void nextTick(() => scrollToBottomIfNear())

        if (index === schedule.length - 1) {
          activeRevealMessageId.value = null
          resolve()
        }
      }, step.delayMs)
      revealTimers.add(timer)
    })
  })
}

async function appendChatResult(result: AIChatResponse) {
  activeTask.value = result.active_task
  messages.value.push(result.user_message)
  await appendAssistantMessage(result.assistant_message)
}

function splitParagraphs(text: string): string[] {
  return text.split(/\n+/).filter(Boolean)
}

function formatTime(iso: string): string {
  try {
    const date = new Date(iso)
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  } catch {
    return ''
  }
}

function goBack() {
  // pageContext is set only when we arrived via router.push from a source page,
  // so router.back() naturally returns to it. Using router.push(source) here would
  // add a new history entry and cause a navigation loop:
  // work-detail → ai-assistant → work-detail → ai-assistant → ...
  void router.back()
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files
  if (!files || !files.length) return

  for (const file of Array.from(files)) {
    const thumbUrl = URL.createObjectURL(file)
    try {
      const result = await uploadAIImage(file)
      uploadedImages.value.push({ url: result.url, thumbUrl, file })
      toastMessage.value = '图片已上传'
    } catch (error) {
      toastMessage.value = getApiErrorMessage(error)
      URL.revokeObjectURL(thumbUrl)
    }
  }

  target.value = ''
}

function removeUploadedImage(index: number) {
  const removed = uploadedImages.value[index]
  if (removed?.thumbUrl) URL.revokeObjectURL(removed.thumbUrl)
  uploadedImages.value.splice(index, 1)
}

function previewImage(url: string) {
  window.open(resolveMediaUrl(url), '_blank')
}

function hasReferences(refs: any): boolean {
  if (!refs) return false
  return !!(
    refs.photographers?.length ||
    refs.portfolio_items?.length ||
    refs.packages?.length ||
    refs.projects?.length
  )
}

function getPackageCover(pkg: any): string {
  if (pkg.samples && Array.isArray(pkg.samples) && pkg.samples.length) return pkg.samples[0]
  return ''
}

function isBookablePackage(pkg: any): pkg is BookablePackageRecommendation {
  return Boolean(pkg?.availability || pkg?.match?.overall_score !== undefined || pkg?.distance_confidence)
}

function jointPackages(refs: any): BookablePackageRecommendation[] {
  return (refs?.packages || []).filter(isBookablePackage)
}

function jointRecommendation(msg: AIMessage): any | null {
  return msg.metadata?.joint_recommendation || null
}

function trackJointOnce(key: string, event: RecommendationEvent) {
  if (trackedJointEvents.has(key)) return
  trackedJointEvents.add(key)
  void trackRecommendationEvents([event])
}

function trackJointMessage(msg: AIMessage) {
  const context = jointRecommendation(msg)
  if (!context?.recommendation_id) return
  const packages = jointPackages(msg.metadata?.references)
  if (context.no_result) {
    trackJointOnce(`no-result:${context.recommendation_id}`, {
      event_type: 'joint_rec_no_result', target_type: 'recommendation', target_id: context.recommendation_id,
      recommendation_id: context.recommendation_id, algorithm_version: context.algorithm_version,
      scene: 'ai_joint_booking', metadata: { fallback_level: context.fallback_level || 0 },
    })
    return
  }
  const events: RecommendationEvent[] = []
  packages.forEach((pkg, position) => {
    const key = `impression:${context.recommendation_id}:${pkg.id}:${position}`
    if (trackedJointEvents.has(key)) return
    trackedJointEvents.add(key)
    events.push({
      event_type: 'joint_rec_impression', target_type: 'package', target_id: pkg.id,
      owner_user_id: pkg.photographer_id, position, scene: 'ai_joint_booking',
      recommendation_id: context.recommendation_id, algorithm_version: context.algorithm_version,
      metadata: { fallback_level: context.fallback_level || 0 },
    })
  })
  if (events.length) void trackRecommendationEvents(events)
}

function legacyPackages(refs: any): any[] {
  return (refs?.packages || []).filter((pkg: any) => !isBookablePackage(pkg))
}

function goRefPhotographer(p: any) {
  const id = p.user_id || p.id
  if (id) router.push({ name: 'photographer-detail', params: { userId: String(id) } })
}

function goRefWork(w: any) {
  const id = w.id
  if (id) router.push({ name: 'work-detail', params: { workId: String(id) } })
}

function goRefPackage(pkg: any, msg?: AIMessage) {
  const id = pkg.id
  const context = msg ? jointRecommendation(msg) : null
  if (id && context?.recommendation_id) {
    trackJointOnce(`open:${context.recommendation_id}:${id}`, {
      event_type: 'joint_rec_open', target_type: 'package', target_id: id,
      owner_user_id: pkg.photographer_id, recommendation_id: context.recommendation_id,
      algorithm_version: context.algorithm_version, scene: 'ai_joint_booking',
    })
  }
  if (id) router.push({ name: 'package-detail', params: { packageId: String(id) } })
}

function goBookPackage(pkg: BookablePackageRecommendation, msg: AIMessage) {
  if (!pkg.photographer_id || !pkg.id) return
  const context = jointRecommendation(msg)
  void router.push({
    name: 'booking',
    params: { userId: String(pkg.photographer_id) },
    query: {
      packageId: String(pkg.id), locked: '1',
      recommendationId: context?.recommendation_id,
      algorithmVersion: context?.algorithm_version,
      recommendationPosition: String(jointPackages(msg.metadata?.references).findIndex((item) => item.id === pkg.id)),
    },
  })
}

function filterMessage(filters: Record<string, any>): string {
  const parts = ['调整推荐条件']
  if (filters.budget_max) parts.push(`预算不超过${filters.budget_max}元`)
  if (filters.max_distance_km) parts.push(`${filters.max_distance_km}公里内`)
  if (filters.styles?.length) parts.push(`${filters.styles.join('、')}风格`)
  parts.push(filters.require_exact_availability ? '只看确定有档期' : '允许未确认档期')
  const sortLabels: Record<string, string> = { nearest: '按最近排序', lowest_price: '按价格低排序', earliest_available: '按最早可约排序', best_match: '按综合匹配排序' }
  parts.push(sortLabels[filters.sort_mode] || sortLabels.best_match)
  return parts.join('，')
}

async function applyJointFilters(filters: Record<string, any>, msg?: AIMessage) {
  if (!conversation.value || sending.value) return
  const context = msg ? jointRecommendation(msg) : null
  if (context?.recommendation_id) {
    void trackRecommendationEvents([{
      event_type: 'joint_rec_filter_change', target_type: 'recommendation', target_id: context.recommendation_id,
      recommendation_id: context.recommendation_id, algorithm_version: context.algorithm_version,
      scene: 'ai_joint_booking', metadata: { filters },
    }])
  }
  sending.value = true
  try {
    const result = await sendAIMessage(conversation.value.id, { content: filterMessage(filters) })
    await appendChatResult(result)
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    sending.value = false
  }
}

async function refreshJointRecommendations() {
  if (!conversation.value || sending.value) return
  sending.value = true
  try {
    const result = await sendAIMessage(conversation.value.id, { content: '刷新档期，保持当前推荐条件' })
    await appendChatResult(result)
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  } finally {
    sending.value = false
  }
}

function goRefProject(proj: any) {
  const id = proj.id
  if (id) router.push({ name: 'project-detail', params: { projectId: String(id) } })
}

async function initConversation() {
  try {
    const savedId = localStorage.getItem(AI_CONVERSATION_KEY)
    if (savedId) {
      const conversations = await getAIConversations({ skip: 0, limit: 20 })
      const existing = conversations.find((c) => c.id === savedId)
      if (existing) {
        conversation.value = existing
        return
      }
    }

    const conversations = await getAIConversations({ skip: 0, limit: 1 })
    if (conversations.length > 0) {
      conversation.value = conversations[0]
      localStorage.setItem(AI_CONVERSATION_KEY, conversations[0].id)
    } else {
      const newConv = await createAIConversation()
      conversation.value = newConv
      localStorage.setItem(AI_CONVERSATION_KEY, newConv.id)
    }
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
    throw error
  }
}

async function loadMessages() {
  if (!conversation.value) return
  try {
    const msgs = await getAIMessages(conversation.value.id, { skip: 0, limit: 200 })
    messages.value = msgs
    activeTask.value = await getActiveAgentTask(conversation.value.id)
    msgs.forEach(trackJointMessage)
  } catch (error) {
    toastMessage.value = getApiErrorMessage(error)
  }
}

async function submitMessage() {
  const content = structuredAgentMessage()
  if (!content && !uploadedImages.value.length) return
  if (!conversation.value || sending.value) return

  sending.value = true
  const attachments = uploadedImages.value.map((img) => ({
    type: 'image' as const,
    url: img.url,
    mime_type: img.file.type || 'image/jpeg',
  }))
  const prevImages = [...uploadedImages.value]
  const ctx = pageContext.value
  const previousAgent = selectedAgent.value
  const previousAgentForm = { ...agentForm }
  const previousWebSearchEnabled = webSearchEnabled.value

  // Optimistically clear input
  draft.value = ''
  uploadedImages.value = []
  pageContext.value = null
  clearAgentSelection()
  webSearchEnabled.value = false

  // Build an optimistic user message so it appears in the chat immediately
  const optimisticMsg: AIMessage = {
    id: 'pending-' + Date.now(),
    conversation_id: conversation.value.id,
    role: 'user',
    content,
    ...(attachments.length ? { attachments: attachments as AIMessage['attachments'] } : {}),
    ...(ctx ? { page_context: ctx } : {}),
    created_at: new Date().toISOString(),
  }
  messages.value.push(optimisticMsg)
  await scrollToBottom()

  try {
    const result = await sendAIMessage(conversation.value.id, {
      content,
      ...(attachments.length ? { attachments } : {}),
      ...(ctx ? { page_context: ctx } : {}),
    })
    // Replace optimistic message with real server response
    const idx = messages.value.indexOf(optimisticMsg)
    if (idx !== -1) {
      messages.value.splice(idx, 1, result.user_message)
    }
    activeTask.value = result.active_task
    await appendAssistantMessage(result.assistant_message)
  } catch (error) {
    // Remove optimistic message on failure
    const idx = messages.value.indexOf(optimisticMsg)
    if (idx !== -1) messages.value.splice(idx, 1)
    toastMessage.value = getApiErrorMessage(error)
    uploadedImages.value = prevImages
    pageContext.value = ctx
    selectedAgent.value = previousAgent
    Object.assign(agentForm, previousAgentForm)
    webSearchEnabled.value = previousWebSearchEnabled
  } finally {
    sending.value = false
  }
}

async function scrollToBottom(smooth = true) {
  await nextTick()
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  messageListRef.value?.lastElementChild?.scrollIntoView({
    behavior: smooth && !reduceMotion ? 'smooth' : 'auto',
    block: 'end',
  })
}

function inspirationEntry(msg: AIMessage): InspirationQuickEntry | null {
  const entry = msg.metadata?.inspiration_flow?.entry
  if (!entry || !Number(entry.inspiration_id) || !String(entry.title || '').trim()) return null
  return entry as InspirationQuickEntry
}

function openInspiration(inspirationId: number) {
  void router.push({ name: 'inspiration-detail', params: { inspirationId: String(inspirationId) } })
}

function editInspiration(inspirationId: number) {
  void router.push({ name: 'inspiration-edit', params: { inspirationId: String(inspirationId) } })
}

onMounted(async () => {
  await nextTick()
  updateCapabilityScrollState()
  if (typeof ResizeObserver !== 'undefined' && capabilityScrollerRef.value) {
    capabilityResizeObserver = new ResizeObserver(updateCapabilityScrollState)
    capabilityResizeObserver.observe(capabilityScrollerRef.value)
  }

  await auth.initialize()

  try {
    await initConversation()
    await loadMessages()
  } catch {
    // Error already shown via toast
  } finally {
    loading.value = false
    await nextTick()
    await scrollToBottom(false)
  }
})

// ── 页面卸载时清理计时器 ──
onBeforeUnmount(() => {
  capabilityResizeObserver?.disconnect()
  clearRevealState()
})
</script>

<style scoped>
/* 输入栏现在在 ion-content 外部，无需底部间距 */

.page-content {
  min-height: 0;
  --offset-top: 0px;
  --padding-top: 0px;
  --padding-bottom: 0px;
  overscroll-behavior-y: contain;
}

.page-content::part(scroll) {
  overscroll-behavior-y: contain;
}

.welcome-card {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
  margin-top: var(--space-8);
  padding: var(--space-8) var(--space-4);
  text-align: center;
}

.welcome-icon {
  display: grid;
  width: 72px;
  height: 72px;
  place-items: center;
  border-radius: 50%;
  background: var(--brand-soft);
  color: var(--brand);
}

.welcome-card h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--text-lg);
}

.welcome-card p {
  max-width: 320px;
  margin: 0;
  color: var(--ink-secondary);
  font-size: var(--text-sm);
  line-height: 1.65;
}

.message-list {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4) 0 var(--space-6);
}

.message-row {
  display: flex;
}

.message-user {
  justify-content: flex-end;
}

.message-ai {
  justify-content: flex-start;
}

.message-content {
  display: grid;
  max-width: 84%;
  gap: 5px;
}

.message-user .message-content {
  justify-items: end;
}

.message-ai .message-content {
  justify-items: start;
}

.message-bubble {
  width: fit-content;
  max-width: 100%;
  padding: 10px 14px;
  font-size: var(--text-sm);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-user .message-bubble {
  border-radius: var(--radius-md) var(--radius-md) 4px var(--radius-md);
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
}

.message-ai .message-bubble {
  border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 4px;
  background: var(--surface-solid);
  box-shadow: var(--neu-inset);
  color: var(--ink);
}

.message-text {
  margin: 0;
}

.message-text + .message-text {
  margin-top: 8px;
}

.message-time {
  color: var(--ink-tertiary);
  font-size: 10px;
}

.attachment-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.attachment-thumb {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  cursor: pointer;
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 18px;
}

.typing-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-tertiary);
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

.pending-context-wrap {
  display: grid;
  grid-template-columns: minmax(0, 140px);
  margin-bottom: var(--space-2);
}

.message-context-card {
  width: 130px;
  margin-bottom: 6px;
}

/* ── AI 分段气泡栈 ── */
.assistant-bubble-stack {
  width: 100%;
}

.assistant-bubble-list {
  display: grid;
  justify-items: start;
  gap: 6px;
}

.assistant-bubble-enter-active {
  transition: opacity 180ms ease-out, transform 180ms ease-out;
}

.assistant-bubble-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

@media (prefers-reduced-motion: reduce) {
  .assistant-bubble-enter-active {
    transition: none;
  }

  .typing-dot {
    animation: none;
  }
}

.bottom-dock {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  width: min(100%, var(--content-max));
  margin: 0 auto;
  background: var(--paper);
}

.task-dock {
  max-height: min(42vh, 360px);
  overflow-y: auto;
  padding: var(--space-2) var(--space-3) 0;
  border-top: 1px solid var(--neu-light);
  background: var(--paper);
  overscroll-behavior: contain;
}

.task-dock :deep(.agent-task-summary) {
  margin-top: 0;
}

.input-bar-shell {
  flex-shrink: 0;
  width: 100%;
  margin: 0;
  padding: var(--space-2) var(--space-3) calc(var(--space-3) + env(safe-area-inset-bottom));
  background: var(--paper);
}

.image-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.image-preview-item {
  position: relative;
  width: 64px;
  height: 64px;
}

.image-preview-thumb {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-sm);
  object-fit: cover;
}

.image-remove-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  display: grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border: 2px solid var(--paper);
  border-radius: 50%;
  background: var(--danger);
  color: var(--white);
}

.input-bar {
  display: grid;
  gap: 10px;
  padding: 16px 14px 12px;
  border: 1px solid color-mix(in srgb, var(--brand) 16%, var(--divider));
  border-radius: 24px;
  background: var(--surface-solid);
  box-shadow: 0 8px 28px rgba(45, 90, 39, 0.08);
}

.composer-heading { display: flex; align-items: center; gap: 8px; padding: 0 2px; }
.composer-kicker { color: var(--ink); font-size: 13px; font-weight: 700; }
.composer-hint { color: var(--ink-tertiary); font-size: 11px; }
.agent-capability-shell { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 4px; min-width: 0; }
.agent-capability-row { display: flex; min-width: 0; gap: 8px; overflow-x: auto; padding: 1px 2px 3px; scroll-behavior: smooth; scrollbar-width: none; }
.agent-capability-row::-webkit-scrollbar { display: none; }
.agent-capability { display: inline-flex; align-items: center; gap: 6px; min-height: 44px; flex: 0 0 auto; padding: 9px 13px; border: 1px solid var(--divider); border-radius: 999px; background: var(--paper); color: var(--ink-secondary); font: inherit; font-size: 12px; white-space: nowrap; transition: color .18s, border-color .18s, background .18s, transform .18s; }
.agent-capability--active { border-color: var(--brand); background: var(--brand-soft); color: var(--brand); }
.agent-capability:active { transform: scale(.97); }
.capability-nav { display: grid; width: 44px; height: 44px; place-items: center; padding: 0; border: 1px solid var(--divider); border-radius: 50%; background: var(--paper); color: var(--brand); }
.capability-nav:disabled { opacity: .38; }
.agent-capability:focus-visible, .capability-nav:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
.agent-brief-card { padding: 10px 11px; border: 1px solid color-mix(in srgb, var(--brand) 20%, var(--divider)); border-radius: 16px; background: color-mix(in srgb, var(--brand-soft) 45%, var(--surface-solid)); }
.agent-brief-title { display: flex; align-items: center; gap: 7px; color: var(--ink); font-size: 13px; }
.agent-brief-icon { display: grid; width: 26px; height: 26px; place-items: center; border-radius: 8px; background: var(--brand); color: #fff; }
.agent-clear-btn { display: grid; width: 44px; height: 44px; margin: -7px -7px -7px auto; place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--ink-tertiary); }
.agent-field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
.agent-field { display: grid; gap: 4px; min-width: 0; }
.agent-field--wide { grid-column: 1 / -1; }
.agent-field > span { color: var(--ink-secondary); font-size: 11px; }
.agent-field input { width: 100%; min-height: 44px; padding: 10px; border: 1px solid var(--divider); border-radius: 10px; background: var(--surface-solid); color: var(--ink); font: inherit; font-size: 16px; outline: none; }
.agent-field input:focus { border-color: var(--brand); box-shadow: 0 0 0 2px color-mix(in srgb, var(--brand) 18%, transparent); }
.composer-controls { display: grid; grid-template-columns: 44px minmax(0, 1fr) 44px; align-items: end; gap: 8px; }

.attach-button {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--ink-tertiary);
}

.attach-button:active { background: var(--paper); box-shadow: var(--neu-inset); }

.input-bar textarea {
  width: 100%;
  min-height: 44px;
  max-height: 112px;
  padding: 10px 12px;
  resize: vertical;
  border: 0;
  border-radius: 14px;
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--ink);
  font-size: var(--text-base);
  line-height: 1.45;
  outline: none;
}

.input-bar textarea:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }

.send-button {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
}

.send-button:disabled {
  background: var(--paper-deep);
  box-shadow: none;
  color: var(--ink-tertiary);
  opacity: 0.75;
}

.send-button ion-spinner {
  width: 20px;
  height: 20px;
}

/* ── 旋转箭头动画（Agent 输出中） ── */
.send-button--revealing {
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: var(--white);
  border: 0;
}

.send-button--revealing:disabled {
  opacity: 0.75;
}

.spin-icon {
  animation: spin-icon 1s linear infinite;
}

@keyframes spin-icon {
  to { transform: rotate(360deg); }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (min-width: 680px) {
  .message-content {
    max-width: 70%;
  }
}

/* ── 推荐面板 ── */
.references-wrap {
  width: 100%;
  margin-top: 8px;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.references-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
  background: transparent;
  color: var(--brand);
  font-weight: 600;
  font-size: var(--text-xs);
}

.shoot-context-message-card {
  margin-top: 8px;
}

.joint-package-list {
  display: grid;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.joint-status,
.joint-empty {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise-sm);
  color: var(--ink-secondary);
}

.joint-status { border-color: var(--warning); background: var(--paper); box-shadow: var(--neu-inset); }
.joint-status > svg { color: var(--warning); }
.joint-empty { width: 100%; margin-top: var(--space-3); }
.joint-empty > svg { color: var(--ink-tertiary); }
.joint-status strong,
.joint-empty strong { display: block; color: var(--ink); font-size: var(--text-sm); }
.joint-status p,
.joint-empty p { margin: 4px 0 0; font-size: var(--text-xs); line-height: 1.6; }
.joint-empty > :last-child { grid-column: 1 / -1; }

.ref-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}

.ref-card {
  display: grid;
  grid-template-rows: 1fr auto;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: var(--neu-surface);
  box-shadow: var(--neu-raise);
  overflow: hidden;
  cursor: pointer;
  text-align: left;
  color: inherit;
  font: inherit;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.ref-card:active {
  border-color: var(--brand);
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

.ref-card-media {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

.ref-card-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ref-card-fallback {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  justify-content: center;
  color: var(--ink-tertiary);
  font-size: var(--text-lg);
  font-weight: 700;
}

.ref-card-label {
  display: block;
  padding: 5px 7px;
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 企划引用卡片 ── */
.project-ref-card {
  grid-column: 1 / -1;
  grid-template-rows: auto;
  grid-template-columns: 64px 1fr;
  gap: 0;
}

.project-ref-media {
  width: 64px;
  aspect-ratio: 1 / 1;
}

.ref-card-details {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  padding: 6px 8px;
  overflow: hidden;
}

.ref-card-details .ref-card-label {
  padding: 0;
  font-size: var(--text-sm);
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.ref-card-sub {
  display: block;
  color: var(--ink-tertiary);
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-card-reason {
  display: block;
  color: var(--brand);
  font-size: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 任务卡片 ── */
.task-card {
  width: 100%;
  margin-top: 6px;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--neu-surface);
  overflow: hidden;
  box-shadow: var(--neu-raise);
}

.legacy-task-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  margin-top: 6px;
  padding: 10px 14px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  background: var(--paper);
  color: var(--ink-secondary);
  font-size: var(--text-xs);
}

.legacy-task-summary strong { color: var(--ink); }

.task-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--divider, #e8e3da);
  background: var(--brand-soft, rgba(45, 90, 39, 0.06));
}

.task-card-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.task-type-icon {
  color: var(--brand);
  flex-shrink: 0;
}

.task-type-label {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--ink);
}

.task-status-badge {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  background: var(--brand-soft);
  color: var(--brand);
}

.task-status-badge.status--completed {
  background: #e8f5e9;
  color: #2e7d32;
}

.task-status-badge.status--failed {
  background: #ffebee;
  color: #c62828;
}

.task-status-badge.status--cancelled {
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--ink-tertiary);
}

.task-status-badge.status--awaiting_confirmation {
  background: #fff3e0;
  color: #e65100;
}

/* ── 卡片内容区 ── */
.task-card-body {
  padding: 12px 14px;
}

/* ── 已填槽位网格 ── */
.slot-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;
}

.slot-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.slot-label {
  font-size: 11px;
  color: var(--ink-tertiary);
  text-transform: none;
  letter-spacing: 0.01em;
}

.slot-value {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
  word-break: break-word;
  line-height: 1.4;
}

/* ── 缺失槽位区域 ── */
.missing-slots-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--divider, #e8e3da);
}

.missing-slots-header {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 10px;
  color: var(--warning, #8B6914);
  font-size: var(--text-xs);
  font-weight: 600;
}

.missing-slots-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.missing-slot-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.missing-slot-label {
  font-size: var(--text-xs);
  color: var(--ink-secondary);
  font-weight: 500;
}

.missing-slot-input-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.slot-input {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 0;
  border-radius: var(--radius-sm, 4px);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  color: var(--ink);
  font-size: var(--text-sm);
  font-family: inherit;
  outline: none;
  transition: box-shadow 0.15s;
}

.slot-input:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }

.slot-input::placeholder {
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.slot-send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border: 0;
  border-radius: 50%;
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: #fff;
  cursor: pointer;
  transition: opacity 0.15s, box-shadow var(--motion-fast) ease;
}

.slot-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── 卡片底部操作 ── */
.task-card-footer {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--divider, #e8e3da);
  background: var(--paper-deep, #f5f2ed);
}

.task-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  flex: 1;
  padding: 9px 12px;
  border: 0;
  border-radius: var(--radius-sm, 4px);
  font-size: var(--text-sm);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: opacity 0.15s, background 0.15s;
}

.task-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.task-action-confirm {
  background: var(--neu-surface-brand);
  box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade);
  color: #fff;
}

.task-action-confirm:active:not(:disabled) {
  opacity: 0.85;
}

.task-action-cancel {
  background: var(--paper);
  color: var(--ink-tertiary);
  border: 1px solid var(--border, #d9d3cb);
}

.task-action-cancel:active:not(:disabled) { background: var(--paper-deep); box-shadow: none; }

/* ── 客户端操作按钮 ── */
.legacy-client-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  color: var(--ink-tertiary);
  font-size: var(--text-xs);
}

.legacy-client-actions span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--divider);
  border-radius: var(--radius-md);
  background: var(--paper);
}
</style>
