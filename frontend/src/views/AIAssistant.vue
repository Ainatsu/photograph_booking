<template>
  <div class="ai-page" :class="{ 'ai-page-embedded': embedded }">
    <AIConversationSidebar
      v-if="!embedded"
      :conversations="conversations"
      :active-id="conversationId"
      :busy="mutatingConversation || loadingMessages || sending"
      @create="handleCreateConversation"
      @select="handleSelectConversation"
      @rename="handleRenameConversation"
      @archive="handleArchiveConversation"
      @fork="handleForkConversation"
      @search="searchConversations"
    />
    <div class="chat-panel">
      <div class="chat-header">
        <div class="chat-heading">
          <span class="chat-title">{{ activeConversation?.title || '新对话' }}</span>
          <span class="chat-subtitle">{{ contextSubtitle || '小龟J · AI 摄影助手' }}</span>
        </div>
        <el-button
          v-if="embedded"
          :icon="Close"
          circle
          text
          class="close-chat-btn"
          @click="emit('close')"
        />
      </div>

      <div ref="messageContainer" class="message-list" v-loading="loadingMessages">
        <div
          v-for="message in visibleMessages"
          :key="message.id"
          class="message-row"
          :class="{ mine: message.role === 'user' }"
        >
          <el-avatar
            v-if="message.role === 'assistant'"
            :size="32"
            :src="aiAvatar"
            class="message-avatar"
          />
          <div
            class="message-stack"
            :class="{
              'task-message-stack': message.role === 'assistant' && shouldShowTaskCard(message),
              'reference-message-stack': message.role === 'assistant' && hasReferences(message),
            }"
          >
            <button
              v-if="message.role === 'user' && hasPageContext(message)"
              type="button"
              class="message-context-card"
              @click="goPageContext(getPageContext(message))"
            >
              <img
                v-if="getPageContextThumbnail(message)"
                :src="getFullUrl(getPageContextThumbnail(message))"
                alt=""
                class="message-context-cover"
              />
              <span class="message-context-body">
                <span class="message-context-type">{{ getPageContextTypeLabel(message) }}</span>
                <span class="message-context-title">{{ getPageContextTitle(message) }}</span>
              </span>
            </button>
            <div
              class="message-bubble"
              :class="{
                'task-message-bubble': message.role === 'assistant' && shouldShowTaskCard(message),
                'reference-message-bubble': message.role === 'assistant' && hasReferences(message),
                'segmented-message-bubble': message.role === 'assistant' && !getTaskState(message),
              }"
            >
              <div
                v-if="getAttachments(message).length"
                class="message-images"
              >
                <el-image
                  v-for="(att, idx) in getAttachments(message)"
                  :key="idx"
                  :src="getFullUrl(att.url)"
                  fit="cover"
                  class="message-image"
                  :preview-src-list="[getFullUrl(att.url)]"
                />
              </div>
              <template v-if="message.content && !getTaskState(message)">
                <div
                  v-for="(segment, segmentIndex) in getDisplayedMessageSegments(message)"
                  :key="`${message.id}-segment-${segmentIndex}`"
                  class="message-content-card"
                >
                  <div class="message-text">{{ segment }}</div>
                  <div
                    v-if="segmentIndex === getDisplayedMessageSegments(message).length - 1 && !isMessageRevealing(message)"
                    class="message-time"
                  >
                    {{ formatTime(message.created_at) }}
                  </div>
                </div>
              </template>
              <ImageGenerationCard
                v-if="getImageGenerationRef(message)"
                :reference="getImageGenerationRef(message)"
                :prompt="getImageGenerationPrompt(message)"
              />
              <div
                v-if="message.role === 'assistant' && shouldShowTaskCard(message)"
                class="task-card"
              >
              <template v-if="getTaskCard(message).isPublisherEditor">
                <div class="project-editor-header">
                  <div class="task-card-title">{{ getTaskCard(message).title }}</div>
                  <span class="project-save-state" aria-live="polite">
                    {{ getTaskSaveFeedback(getTaskCard(message)) }}
                  </span>
                </div>

                <div class="project-editor-grid">
                  <template
                    v-for="field in getTaskCard(message).fields"
                    :key="field.key"
                  >
                    <template v-if="shouldRenderProjectField(getTaskCard(message), field)">
                      <div v-if="field.sectionLabel" class="project-editor-section">
                        <span>{{ field.sectionLabel }}</span>
                      </div>
                      <div
                        v-if="field.editor === 'datetime' && isTaskDateEditorOpen(getTaskCard(message), field)"
                        :id="getTaskDateEditorId(getTaskCard(message), field)"
                        class="project-date-selection"
                        role="region"
                        :aria-label="`${field.label}日期选择`"
                        @keydown.esc="closeTaskDateEditor(getTaskCard(message), field)"
                      >
                        <div class="project-date-selection-intro">
                          <div>
                            <strong>选择拍摄日期</strong>
                            <span>选择后将自动返回拍摄安排</span>
                          </div>
                          <button
                            type="button"
                            class="project-date-selection-close"
                            aria-label="取消选择日期"
                            @click="closeTaskDateEditor(getTaskCard(message), field)"
                          >
                            <Close />
                          </button>
                        </div>
                        <el-calendar
                          class="project-inline-calendar"
                          :model-value="getTaskDateEditorCursor(getTaskCard(message), field)"
                          @update:model-value="updateTaskDateEditorCursor"
                        >
                          <template #header="{ date, selectDate }">
                            <div class="project-calendar-header">
                              <button type="button" aria-label="上个月" @click="selectDate('prev-month')">
                                <ChevronLeft />
                              </button>
                              <strong>{{ date }}</strong>
                              <button type="button" aria-label="下个月" @click="selectDate('next-month')">
                                <ChevronRight />
                              </button>
                            </div>
                          </template>
                          <template #date-cell="{ data }">
                            <button
                              type="button"
                              class="project-calendar-day"
                              :class="{
                                'is-adjacent': data.type !== 'current-month',
                                'is-selected': isTaskCalendarDaySelected(getTaskCard(message), field, data.day),
                              }"
                              :aria-label="formatTaskCalendarDayAria(data.day)"
                              :aria-pressed="isTaskCalendarDaySelected(getTaskCard(message), field, data.day)"
                              @click.stop="selectTaskCalendarDay(getTaskCard(message), field, data.day)"
                            >
                              {{ getTaskCalendarDayNumber(data.day) }}
                            </button>
                          </template>
                        </el-calendar>
                      </div>
                      <div
                        v-else
                        class="project-editor-field"
                        :class="[`field-${field.sourceKey}`, `span-${field.span || 6}`, { missing: field.missing }]"
                      >
                        <label
                          v-if="!field.hideLabel"
                          class="project-editor-label"
                          :for="`task-field-${getTaskCard(message).key}-${field.key}`"
                        >
                          {{ field.label }}
                          <span v-if="field.optional" class="project-editor-optional">选填</span>
                        </label>
                        <div v-if="field.editor === 'images'" class="project-reference-editor">
                          <button
                            :id="`task-field-${getTaskCard(message).key}-${field.key}`"
                            type="button"
                            class="project-reference-trigger"
                            :disabled="sending"
                            @click="openImagePicker"
                          >
                            <Picture />
                            <span>{{ getTaskImageFieldLabel(getTaskCard(message), field) }}</span>
                          </button>
                        </div>
                        <ProjectLocationField
                          v-else-if="field.editor === 'location'"
                          :model-value="getTaskLocationValue(getTaskCard(message))"
                          :city="getTaskFieldEdit(getTaskCard(message), { sourceKey: 'city' })"
                          @update:model-value="value => setTaskLocationValue(getTaskCard(message), value)"
                        />
                        <div v-else-if="field.editor === 'datetime'" class="project-datetime-editor">
                          <button
                            :id="`task-field-${getTaskCard(message).key}-${field.key}`"
                            type="button"
                            class="project-date-trigger"
                            :class="{ 'is-placeholder': !getTaskDateValue(getTaskCard(message), field) }"
                            :disabled="sending"
                            :aria-expanded="isTaskDateEditorOpen(getTaskCard(message), field)"
                            :aria-controls="getTaskDateEditorId(getTaskCard(message), field)"
                            @click="openTaskDateEditor(getTaskCard(message), field)"
                          >
                            <CalendarDays />
                            <span>{{ getTaskDateDisplay(getTaskCard(message), field) }}</span>
                            <ChevronRight class="project-date-trigger-arrow" />
                          </button>
                          <div class="project-time-control">
                            <label :for="`task-field-${getTaskCard(message).key}-${field.key}-time`">
                              <Clock3 />
                              <span>时间</span>
                            </label>
                            <input
                              :id="`task-field-${getTaskCard(message).key}-${field.key}-time`"
                              type="time"
                              :value="getTaskTimeValue(getTaskCard(message), field)"
                              :disabled="sending"
                              aria-label="拍摄时间"
                              @input="event => setTaskTimeValue(getTaskCard(message), event.target.value)"
                              @change="commitTaskFieldEdit(getTaskCard(message), field)"
                            />
                          </div>
                        </div>
                        <div v-else class="project-editor-input-row">
                          <el-input
                            :id="`task-field-${getTaskCard(message).key}-${field.key}`"
                            :model-value="getTaskEditorValue(getTaskCard(message), field)"
                            :type="getTaskEditorInputType(field)"
                            :rows="getTaskEditorRows(field)"
                            :placeholder="field.placeholder"
                            :min="field.min"
                            :disabled="sending"
                            @update:model-value="value => setTaskEditorValue(getTaskCard(message), field, value)"
                            @blur="commitTaskFieldEdit(getTaskCard(message), field)"
                            @keydown.enter.exact="event => handleTaskEditorEnter(getTaskCard(message), field, event)"
                          />
                          <span v-if="field.unit" class="project-editor-unit">{{ field.unit }}</span>
                        </div>
                        <span v-if="field.helper" class="project-editor-helper">{{ field.helper }}</span>
                      </div>
                    </template>
                  </template>
                </div>

                <div v-if="getTaskFieldError(getTaskCard(message))" class="task-field-error" role="alert">
                  {{ getTaskFieldError(getTaskCard(message)) }}
                </div>

                <div class="project-editor-actions">
                  <el-button
                    size="large"
                    :disabled="sending"
                    :loading="savingTaskDraft"
                    @click="submitPublisherFromCard(getTaskCard(message), 'save_draft')"
                  >
                    {{ getTaskCard(message).taskType === 'publish_package' ? '暂存草稿' : '保存为草稿' }}
                  </el-button>
                  <el-button
                    size="large"
                    type="primary"
                    :icon="Check"
                    :disabled="sending"
                    :loading="publishingTask"
                    @click="submitPublisherFromCard(getTaskCard(message), 'publish')"
                  >
                    {{ getTaskCard(message).taskType === 'publish_package' ? '发布方案' : '发布' }}
                  </el-button>
                </div>
              </template>

              <template v-else>
                <div class="task-card-header">
                  <div>
                    <div class="task-card-kicker">{{ getTaskCard(message).kicker }}</div>
                    <div class="task-card-title">{{ getTaskCard(message).title }}</div>
                  </div>
                  <span class="task-status" :class="`status-${getTaskCard(message).statusTone}`">
                    {{ getTaskCard(message).statusText }}
                  </span>
                </div>
                <div class="task-fields">
                <div
                  v-for="field in getTaskCard(message).fields"
                  :key="field.key"
                  class="task-field"
                  :class="{ missing: field.missing }"
                >
                  <span class="task-field-label">{{ field.label }}</span>
                  <span class="task-field-value">{{ field.value || '待补充' }}</span>
                </div>
                </div>

              <div class="task-actions">
                <el-button
                  v-for="action in getTaskCard(message).actions"
                  :key="`${message.id}-${action.type}`"
                  size="small"
                  :type="action.requires_confirmation ? 'primary' : 'default'"
                  :plain="!action.requires_confirmation"
                  :icon="getSuggestedActionIcon(action)"
                  :disabled="sending"
                  @click="handleSuggestedAction(action)"
                >
                  {{ action.label || '确认' }}
                </el-button>
                <el-button
                  v-if="getTaskCard(message).fallbackConfirmLabel"
                  size="small"
                  type="primary"
                  :icon="Check"
                  :disabled="sending"
                  @click="handleTaskConfirm(getTaskCard(message))"
                >
                  {{ getTaskCard(message).fallbackConfirmLabel }}
                </el-button>
              </div>
              </template>
              </div>
              <div
                v-if="message.role === 'assistant' && hasSuggestedActions(message) && !getTaskState(message)"
                class="suggested-actions"
              >
              <el-button
                v-for="action in getSuggestedActions(message)"
                :key="`${message.id}-${action.type}`"
                size="small"
                type="primary"
                plain
                :icon="getSuggestedActionIcon(action)"
                :disabled="sending"
                @click="handleSuggestedAction(action)"
              >
                {{ action.label || '确认' }}
              </el-button>
              </div>
              <div
                v-if="message.role === 'assistant' && hasClientActions(message)"
                class="client-actions"
                aria-label="继续完成发布"
              >
                <el-button
                  v-for="action in getClientActions(message)"
                  :key="`${message.id}-${action.type}`"
                  size="large"
                  type="primary"
                  :icon="getClientActionIcon(action)"
                  :loading="isClientActionLoading(message, action)"
                  :disabled="sending || isClientActionLoading(message, action) || isClientActionDisabled(action)"
                  :title="getClientActionDisabledReason(action)"
                  @click="handleClientAction(message, action)"
                >
                  {{ action.label || getClientActionFallbackLabel(action) }}
                </el-button>
                <span
                  v-for="action in getClientActions(message).filter(isClientActionDisabled)"
                  :key="`${message.id}-${action.type}-disabled-reason`"
                  class="client-action-disabled-reason"
                  role="status"
                >
                  {{ getClientActionDisabledReason(action) }}
                </span>
              </div>
              <div
                v-if="message.role === 'assistant' && hasReferences(message) && !isMessageRevealing(message)"
                class="reference-panel"
              >
              <div
                v-if="getReferences(message).photographers.length"
                class="reference-section"
              >
                <div class="reference-title">推荐摄影师</div>
                <div class="reference-list photographer-list">
                  <button
                    v-for="profile in getReferences(message).photographers"
                    :key="`photographer-${profile.user_id}`"
                    type="button"
                    class="reference-card photographer-card"
                    @click="goPhotographer(profile.user_id)"
                  >
                    <span class="reference-avatar">
                      <img
                        v-if="profile.user_avatar_url || profile.cover_image_url"
                        :src="getFullUrl(profile.user_avatar_url || profile.cover_image_url)"
                        alt=""
                      />
                      <span v-else>{{ (profile.user_display_name || '?')[0] }}</span>
                    </span>
                    <span class="reference-body">
                      <span class="reference-name">{{ profile.user_display_name || '未知摄影师' }}</span>
                      <span class="reference-meta">{{ profile.location || '位置待补充' }}</span>
                      <span v-if="profile.styles?.length" class="reference-tags">
                        {{ profile.styles.slice(0, 3).join(' / ') }}
                      </span>
                    </span>
                  </button>
                </div>
              </div>

              <div
                v-if="getReferences(message).portfolio_items.length"
                class="reference-section"
              >
                <div class="reference-title">相关作品</div>
                <div class="reference-list work-list">
                  <button
                    v-for="work in getReferences(message).portfolio_items"
                    :key="`work-${work.id || work.url}`"
                    type="button"
                    class="reference-card work-card"
                    @click="goWork(work)"
                  >
                    <img
                      v-if="work.url"
                      :src="getFullUrl(work.url)"
                      alt=""
                      class="reference-cover"
                    />
                    <span class="reference-body">
                      <span class="reference-name">{{ work.title || work.tag || '摄影作品' }}</span>
                      <span class="reference-meta">{{ work.user_display_name || '未知摄影师' }}</span>
                      <span v-if="getReferenceTags(work).length" class="reference-tags">
                        {{ getReferenceTags(work).slice(0, 3).join(' / ') }}
                      </span>
                    </span>
                  </button>
                </div>
              </div>

              <div
                v-if="getReferences(message).packages.length"
                class="reference-section"
              >
                <div class="reference-title">匹配套餐</div>
                <div class="reference-list package-list">
                  <button
                    v-for="pkg in getReferences(message).packages"
                    :key="`package-${pkg.id || pkg.package_name}`"
                    type="button"
                    class="reference-card package-card"
                    @click="goPackage(pkg)"
                  >
                    <img
                      v-if="getPackageCover(pkg)"
                      :src="getFullUrl(getPackageCover(pkg))"
                      alt=""
                      class="reference-cover"
                    />
                    <span class="reference-body">
                      <span class="reference-name">{{ pkg.package_name || '摄影套餐' }}</span>
                      <span class="reference-meta">
                        <span v-if="pkg.price">¥{{ pkg.price }}</span>
                        <span v-if="pkg.duration"> / {{ pkg.duration }}分钟</span>
                      </span>
                      <span class="reference-tags">{{ pkg.photographer_name || '未知摄影师' }}</span>
                    </span>
                  </button>
                </div>
              </div>
              </div>
            </div>
          </div>
          <el-avatar
            v-if="message.role === 'user'"
            :size="32"
            :src="userAvatarUrl"
            class="message-avatar user-avatar"
          >
            {{ userDisplayName[0] || '?' }}
          </el-avatar>
        </div>
        <div v-if="!loadingMessages && !messages.length" class="empty-chat">
          <el-empty description="输入你的拍摄需求，开始咨询小龟J吧" />
        </div>
      </div>

      <div class="chat-input-area">
        <div class="quick-prompt-shell">
          <button
            v-if="quickPromptOverflow"
            type="button"
            class="quick-prompt-nav"
            aria-label="向左查看更多快捷工具"
            :disabled="!canScrollQuickPromptsLeft"
            @click="scrollQuickPrompts(-1)"
          >
            <ChevronLeft aria-hidden="true" />
          </button>
          <div
            ref="quickPromptScroller"
            class="quick-prompts"
            role="list"
            aria-label="快捷工具"
            @scroll="updateQuickPromptScrollState"
          >
            <button
              type="button"
              class="quick-prompt quick-prompt--inspiration"
              :disabled="sending || loadingMessages"
              @click="activateInspirationTool"
            >
              <Sparkles aria-hidden="true" />
              <span>创作灵感</span>
            </button>
            <button
              v-for="prompt in quickPromptList"
              :key="prompt"
              type="button"
              class="quick-prompt"
              :disabled="sending || loadingMessages"
              @click="sendPresetPrompt(prompt)"
            >
              {{ prompt }}
            </button>
          </div>
          <button
            v-if="quickPromptOverflow"
            type="button"
            class="quick-prompt-nav"
            aria-label="向右查看更多快捷工具"
            :disabled="!canScrollQuickPromptsRight"
            @click="scrollQuickPrompts(1)"
          >
            <ChevronRight aria-hidden="true" />
          </button>
        </div>

        <ImageGenerationComposer
          v-model="generationConfig"
          :disabled="sending || loadingMessages"
          @mode-change="handleGenerationModeChange"
        />

        <div v-if="generationValidationMessage" class="generation-validation" role="alert">
          {{ generationValidationMessage }}
        </div>

        <!-- 待发送图片预览 -->
        <div v-if="pendingImages.length" class="pending-images">
          <div
            v-for="(img, idx) in pendingImages"
            :key="idx"
            class="pending-image-item"
          >
            <el-image
              :src="img.previewUrl"
              fit="cover"
              class="pending-thumb"
            />
            <div v-if="img.uploading" class="pending-uploading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <el-button
              v-else
              :icon="Close"
              circle
              size="small"
              class="pending-remove"
              @click="removePendingImage(idx)"
            />
          </div>
        </div>

        <div class="chat-input-row">
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style="display:none"
            @change="handleFileChange"
          />
          <el-tooltip content="添加图片" placement="top">
            <el-button
              :icon="Picture"
              circle
              :disabled="sending"
              class="image-btn"
              @click="openImagePicker"
            />
          </el-tooltip>
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            resize="none"
            maxlength="8000"
            show-word-limit
            :placeholder="inputPlaceholder"
            :disabled="sending"
            @keydown.enter.exact.prevent="handleSend"
          />
          <el-tooltip content="发送" placement="top">
            <el-button
              type="primary"
              :icon="Position"
              :loading="sending"
              :disabled="!canSend"
              circle
              class="send-button"
              @click="handleSend"
            />
          </el-tooltip>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FilePenLine,
  Image as Picture,
  LoaderCircle as Loading,
  Send as Position,
  Sparkles,
  Upload,
  X as Close,
} from 'lucide-vue-next'
import {
  sendAIMessage,
  uploadAIImage,
} from '../api/ai'
import { useAIConversation } from '../composables/useAIConversation'
import api from '../utils/api'
import { compressAIReferenceImage } from '../utils/aiImageCompression'
import { saveWorkDraft } from '../utils/workDrafts'
import aiAvatar from '../../CartleJ.jpg'
import ProjectLocationField from '../components/location/ProjectLocationField.vue'
import ImageGenerationCard from '../components/ai/ImageGenerationCard.vue'
import ImageGenerationComposer from '../components/ai/ImageGenerationComposer.vue'
import AIConversationSidebar from '../components/ai/AIConversationSidebar.vue'

const props = defineProps({
  embedded: {
    type: Boolean,
    default: false,
  },
  pageContext: {
    type: Object,
    default: null,
  },
  quickPrompts: {
    type: Array,
    default: () => [],
  },
  contextLabel: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close'])
const router = useRouter()
const route = useRoute()

const {
  conversationId,
  conversations,
  activeConversation,
  messages,
  loadingMessages,
  mutatingConversation,
  initializeConversation,
  refreshConversations,
  reloadMessages,
  selectConversation,
  createConversation,
  renameConversation,
  archiveConversation,
  forkConversation,
  searchConversations,
  appendMessages,
  toolPolicy,
} = useAIConversation()
const inputText = ref('')
const sending = ref(false)
const messageContainer = ref(null)
const fileInput = ref(null)
const revealedMessageContent = ref({})
const revealTimers = new Set()
const userAvatarUrl = ref('')
const userDisplayName = ref('')
const currentUserId = ref('')
const pendingImages = ref([])
const generationConfig = ref({
  mode: null,
  aspect_ratio: '1:1',
  count: 1,
  quality: 'standard',
  strength: 0.65,
})
const taskFieldEdits = ref({})
const taskFieldErrors = ref({})
const taskSaveFeedback = ref({})
const taskDateEditor = ref(null)

watch(conversationId, (currentId, previousId) => {
  if (previousId) {
    const previousKey = `ai_conversation_draft:${previousId}`
    if (inputText.value) localStorage.setItem(previousKey, inputText.value)
    else localStorage.removeItem(previousKey)
  }
  inputText.value = currentId ? (localStorage.getItem(`ai_conversation_draft:${currentId}`) || '') : ''
})

watch(inputText, (value) => {
  if (!conversationId.value) return
  const key = `ai_conversation_draft:${conversationId.value}`
  if (value) localStorage.setItem(key, value)
  else localStorage.removeItem(key)
})

const syncConversationRoute = async () => {
  if (!conversationId.value) return
  await router.replace({ query: { ...route.query, conversation: String(conversationId.value) } })
}

const handleSelectConversation = async (targetId) => {
  if (sending.value) return
  await selectConversation(targetId)
  await syncConversationRoute()
  await scrollToBottom()
}

const handleCreateConversation = async () => {
  if (sending.value) return
  await createConversation()
  await syncConversationRoute()
}

const handleRenameConversation = async (target) => {
  try {
    const { value } = await ElMessageBox.prompt('输入新的对话名称', '重命名对话', {
      inputValue: target.title || '',
      inputPattern: /\S+/,
      inputErrorMessage: '对话名称不能为空',
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    await renameConversation(target.id, value.trim())
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('重命名失败')
  }
}

const handleArchiveConversation = async (target) => {
  try {
    await ElMessageBox.confirm('消息、任务和会话记忆会保留，可通过 API 恢复。', '归档这个对话？', {
      type: 'warning',
      confirmButtonText: '归档',
      cancelButtonText: '取消',
    })
    await archiveConversation(target.id)
    await syncConversationRoute()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('归档失败')
  }
}

const handleForkConversation = async (target) => {
  try {
    await forkConversation(target.id)
    await syncConversationRoute()
    await scrollToBottom()
  } catch (error) {
    ElMessage.error('创建分支失败')
  }
}
const savingTaskDraft = ref(false)
const publishingTask = ref(false)
const clientActionLoading = ref({})
const quickPromptScroller = ref(null)
const quickPromptOverflow = ref(false)
const canScrollQuickPromptsLeft = ref(false)
const canScrollQuickPromptsRight = ref(false)
let quickPromptResizeObserver = null

const embedded = computed(() => props.embedded)
const normalizedPageContext = computed(() => {
  return props.pageContext && Object.keys(props.pageContext).length
    ? props.pageContext
    : null
})
const quickPromptList = computed(() => props.quickPrompts.filter(Boolean).slice(0, 4))
const contextSubtitle = computed(() => {
  return props.contextLabel || normalizedPageContext.value?.title || ''
})
const inputPlaceholder = computed(() => {
  if (generationConfig.value.mode === 'text_to_image') return '描述想要生成的场景、人物、光线和风格'
  if (generationConfig.value.mode === 'image_to_image') return '描述需要保留和修改的内容'
  if (contextSubtitle.value) return `围绕「${contextSubtitle.value}」问小龟J`
  return '询问小龟J吧！'
})

const TASK_TYPE_CONFIG = {
  create_project: {
    kicker: '发布企划',
    title: '企划发布任务',
    editNoun: '企划',
    confirmLabel: '确认发布企划',
  },
  publish_package: {
    kicker: '发布方案',
    title: '方案发布任务',
    editNoun: '方案',
    confirmLabel: '确认发布方案',
  },
  create_booking: {
    kicker: '预约拍摄',
    title: '预约任务',
    editNoun: '预约',
    confirmLabel: '确认预约',
  },
}

const STATUS_TEXT = {
  awaiting_details: '补充信息',
  awaiting_reference_images: '等待参考图',
  awaiting_package: '筛选套餐',
  awaiting_date: '选择日期',
  awaiting_confirmation: '待确认',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

const STATUS_TONE = {
  awaiting_details: 'warning',
  awaiting_reference_images: 'warning',
  awaiting_package: 'warning',
  awaiting_date: 'warning',
  awaiting_confirmation: 'primary',
  completed: 'success',
  failed: 'danger',
  cancelled: 'muted',
}

const STEP_LABELS = {
  collect_details: '补全信息',
  add_reference_images: '参考图',
  confirm_project: '确认企划',
  create_project: '发布企划',
  confirm_package: '确认套餐',
  publish_package: '发布方案',
  vision_analysis: '分析参考图',
  search_packages: '筛选套餐',
  select_package: '选择套餐',
  select_date: '确定日期',
  confirm_booking: '确认预约',
  create_booking: '创建预约',
}

const TASK_FIELD_CONFIG = {
  create_project: [
    { key: 'title', label: '标题', optional: true, editor: 'text', span: 12, sectionLabel: '基本信息', placeholder: '例如：北京日系个人写真' },
    { key: 'city', label: '拍摄城市', editor: 'text', span: 4, placeholder: '请输入拍摄城市' },
    { key: 'style', label: '拍摄风格', editor: 'text', span: 8, placeholder: '例如：日系、胶片、自然光' },
    { key: 'location_text', label: '拍摄地点', optional: true, editor: 'location', span: 12, sectionLabel: '地点', hideLabel: true, placeholder: '例如：朝阳公园、室内影棚' },
    {
      key: 'shooting_datetime',
      sourceKey: 'date',
      sourceKeys: ['date', 'time'],
      requiredKeys: ['date'],
      label: '拍摄时间',
      editor: 'datetime',
      span: 8,
      sectionKey: 'schedule',
      sectionLabel: '拍摄安排',
      placeholder: '选择拍摄日期和时间',
    },
    { key: 'people_count', label: '拍摄人数', editor: 'number', span: 4, sectionKey: 'schedule', placeholder: '请输入拍摄人数' },
    { key: 'budget_max', label: '预算', format: 'currency', editor: 'number', span: 4, sectionKey: 'schedule', placeholder: '请输入预算金额' },
    { key: 'deliverables', label: '交付要求', optional: true, editor: 'text', span: 8, sectionKey: 'schedule', placeholder: '例如：精修 12 张，一周内交付' },
    { key: 'reference_images', label: '参考图', optional: true, format: 'images', span: 12, sectionLabel: '创作需求' },
    { key: 'description', label: '需求描述', editor: 'textarea', span: 12, placeholder: '描述拍摄用途、希望呈现的画面和特殊要求' },
  ],
  publish_package: [
    {
      key: ['package_name', 'name'],
      sourceKey: 'package_name',
      label: '方案名称',
      editor: 'text',
      span: 8,
      sectionLabel: '基本信息',
      placeholder: '例如：城市漫步胶片写真',
    },
    { key: 'city', label: '服务城市', optional: true, editor: 'text', span: 4, placeholder: '不限城市可留空' },
    {
      key: ['style', 'styles'],
      sourceKey: 'style',
      label: '风格标签',
      optional: true,
      editor: 'list',
      span: 12,
      placeholder: '例如：胶片、街拍、自然光',
      helper: '多个标签请用顿号或逗号分隔',
    },
    {
      key: ['price', 'budget_max'],
      sourceKey: 'price',
      label: '方案价格',
      editor: 'number',
      span: 4,
      sectionLabel: '服务规格',
      placeholder: '请输入价格',
      unit: '元',
      min: 0,
    },
    {
      key: ['duration_minutes', 'duration'],
      sourceKey: 'duration_minutes',
      label: '拍摄时长',
      editor: 'number',
      span: 4,
      placeholder: '请输入时长',
      unit: '分钟',
      min: 1,
    },
    {
      key: 'image_count',
      label: '精修张数',
      editor: 'number',
      span: 4,
      placeholder: '请输入张数',
      unit: '张',
      min: 1,
    },
    {
      key: ['package_includes', 'includes'],
      sourceKey: 'package_includes',
      label: '包含服务',
      optional: true,
      editor: 'textarea-list',
      span: 12,
      placeholder: '例如：底片全送、两套造型、线上选片',
      helper: '逐项填写，用顿号、逗号或换行分隔',
    },
    {
      key: ['package_description', 'description'],
      sourceKey: 'package_description',
      label: '方案简介',
      editor: 'textarea',
      span: 12,
      placeholder: '说明适合人群、拍摄体验、画面特点和交付方式',
    },
    {
      key: ['sample_images', 'samples'],
      sourceKey: 'sample_images',
      label: '展示样片',
      optional: true,
      format: 'images',
      span: 12,
      sectionLabel: '展示内容',
    },
  ],
  create_booking: [
    { key: 'photographer_name', label: '摄影师' },
    { key: ['package_name', 'package_display'], label: '套餐' },
    { key: 'date', label: '日期' },
    { key: 'city', label: '城市', optional: true },
    { key: 'location_text', label: '地点', optional: true },
    { key: 'people_count', label: '人数', optional: true },
    { key: 'budget_max', label: '预算', optional: true, format: 'currency' },
    { key: 'style', label: '风格', optional: true },
  ],
}

const canSend = computed(() => {
  if (sending.value || pendingImages.value.some(item => item.uploading)) return false
  if (generationConfig.value.mode === 'text_to_image') return Boolean(inputText.value.trim() && pendingImages.value.length === 0)
  if (generationConfig.value.mode === 'image_to_image') return Boolean(inputText.value.trim() && pendingImages.value.length === 1 && pendingImages.value[0]?.url)
  return Boolean(inputText.value.trim() || pendingImages.value.length)
})

const generationValidationMessage = computed(() => {
  const mode = generationConfig.value.mode
  if (mode === 'text_to_image' && pendingImages.value.length) return '文生图模式不使用参考图片。请移除图片，或切换到以图生图。'
  if (mode === 'image_to_image' && pendingImages.value.length > 1) return '以图生图第一版只支持一张参考图，请移除多余图片。'
  if (mode === 'image_to_image' && !pendingImages.value.length) return '请上传一张参考图，并填写修改指令。'
  return ''
})

const getTaskState = (message) => {
  return message.metadata?.task_state || null
}

const hasTaskCard = (message) => {
  return Boolean(getTaskCard(message))
}

const shouldShowTaskCard = (message) => {
  if (!hasTaskCard(message)) return false
  const taskType = getTaskState(message)?.task_type
  const latestTaskMessage = [...messages.value]
    .reverse()
    .find(item => getTaskState(item)?.task_type === taskType)
  return latestTaskMessage?.id === message.id
}

const visibleMessages = computed(() => messages.value.filter(message => (
  message.role !== 'assistant' || !getTaskState(message) || shouldShowTaskCard(message) || getImageGenerationRef(message)
)))

const getImageGenerationRef = (message) => message?.metadata?.image_generation || null

const getImageGenerationPrompt = (message) => {
  const index = messages.value.findIndex(item => item.id === message.id)
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    if (messages.value[cursor]?.role === 'user') return messages.value[cursor].content || ''
  }
  return ''
}

const messageRevealKey = (message) => String(message?.id ?? '')

const getDisplayedMessageContent = (message) => {
  const key = messageRevealKey(message)
  return Object.prototype.hasOwnProperty.call(revealedMessageContent.value, key)
    ? revealedMessageContent.value[key]
    : message.content
}

const getDisplayedMessageSegments = (message) => {
  const content = getDisplayedMessageContent(message)
  const paragraphs = String(content || '').split(/\n\s*\n+/).map(item => item.trim()).filter(Boolean)
  return paragraphs.length ? paragraphs : [String(content || '')]
}

const isMessageRevealing = (message) => Object.prototype.hasOwnProperty.call(
  revealedMessageContent.value,
  messageRevealKey(message),
)

const splitResponseSegments = (content) => {
  const text = String(content || '').trim()
  if (!text) return []

  const paragraphs = text.split(/\n\s*\n+/).map(item => item.trim()).filter(Boolean)
  if (paragraphs.length > 1) return paragraphs

  const sentences = text.match(/[^。！？!?\n]+[。！？!?]?/g)?.map(item => item.trim()).filter(Boolean) || []
  if (sentences.length <= 2) return [text]

  const segments = []
  for (let index = 0; index < sentences.length; index += 2) {
    segments.push(sentences.slice(index, index + 2).join(''))
  }
  return segments
}

const startSegmentedReveal = (message) => {
  if (!message?.content || message.role !== 'assistant' || getTaskState(message)) return
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

  const segments = splitResponseSegments(message.content)
  if (segments.length <= 1) return

  const key = messageRevealKey(message)
  revealedMessageContent.value = { ...revealedMessageContent.value, [key]: segments[0] }
  let index = 1

  const revealNext = () => {
    if (index >= segments.length) {
      const next = { ...revealedMessageContent.value }
      delete next[key]
      revealedMessageContent.value = next
      scrollToBottom()
      return
    }

    revealedMessageContent.value = {
      ...revealedMessageContent.value,
      [key]: `${revealedMessageContent.value[key]}\n\n${segments[index]}`,
    }
    index += 1
    scrollToBottom()
    const timer = window.setTimeout(() => {
      revealTimers.delete(timer)
      revealNext()
    }, 320)
    revealTimers.add(timer)
  }

  const timer = window.setTimeout(() => {
    revealTimers.delete(timer)
    revealNext()
  }, 360)
  revealTimers.add(timer)
}

const appendResponseMessages = (userMessage, assistantMessage) => {
  startSegmentedReveal(assistantMessage)
  appendMessages(userMessage, assistantMessage)
  if (!activeConversation.value?.title && userMessage?.content) {
    void refreshConversations()
  }
}

const getTaskCard = (message) => {
  const state = getTaskState(message)
  const taskType = state?.task_type
  const config = TASK_TYPE_CONFIG[taskType]
  if (!state || !config) return null

  const plan = message.metadata?.task_plan || state.task_plan || null
  const values = getTaskValues(message, state)
  const fields = getTaskFields(taskType, values, state.missing_slots || [])
  const steps = getTaskSteps(taskType, state.status, plan)
  const actions = getSuggestedActions(message)
  const canEditDraft = !['completed', 'failed', 'cancelled'].includes(state.status)
  const key = `${message.id}-${taskType}`
  const isPublisherEditor = ['create_project', 'publish_package'].includes(taskType)
    && canEditDraft
    && fields.length > 0
  const progress = getTaskProgress(steps, state.status, fields)

  return {
    key,
    taskType,
    title: config.title,
    kicker: config.kicker,
    editNoun: config.editNoun,
    status: state.status,
    statusText: STATUS_TEXT[state.status] || '进行中',
    statusTone: STATUS_TONE[state.status] || 'primary',
    progress,
    steps,
    fields,
    actions,
    canEditDraft,
    isPublisherEditor,
    fallbackConfirmLabel: state.status === 'awaiting_confirmation' && !actions.length
      ? config.confirmLabel
      : '',
  }
}

const getTaskValues = (message, state) => {
  const projectPayload = message.metadata?.project_draft?.project_payload || {}
  const packagePayload = message.metadata?.package_draft?.package_payload || {}
  const pendingInput = state.pending_action?.input || {}
  return {
    ...(state.slots || {}),
    ...projectPayload,
    ...packagePayload,
    ...pendingInput,
  }
}

const getTaskFields = (taskType, values, missingSlots) => {
  const missingSet = new Set(missingSlots || [])
  return (TASK_FIELD_CONFIG[taskType] || [])
    .map((field) => {
      const keys = Array.isArray(field.key) ? field.key : [field.key]
      const sourceKeys = field.sourceKeys || [field.sourceKey || keys[0]]
      const rawValues = Object.fromEntries(sourceKeys.map(key => [key, values?.[key] ?? '']))
      const rawValue = field.editor === 'datetime'
        ? sourceKeys.map(key => rawValues[key]).filter(value => value !== '').join(' ')
        : firstPresentValue(values, keys)
      const value = rawValue === '待补充' ? '' : rawValue
      const missing = (field.requiredKeys || keys).some(key => missingSet.has(key))
      return {
        key: keys.join('-'),
        sourceKey: field.sourceKey || keys[0],
        sourceKeys,
        label: field.label,
        rawValue: value,
        rawValues,
        value: formatTaskFieldValue(value, field),
        missing,
        optional: field.optional,
        editor: field.editor || (field.format === 'images' ? 'images' : 'text'),
        placeholder: field.placeholder || `请输入${field.label}`,
        span: field.span,
        unit: field.unit,
        min: field.min,
        helper: field.helper,
        sectionKey: field.sectionKey,
        sectionLabel: field.sectionLabel,
        hideLabel: field.hideLabel,
      }
    })
    .filter(field => ['create_project', 'publish_package'].includes(taskType) || field.value || field.missing || !field.optional)
}

const firstPresentValue = (values, keys) => {
  for (const key of keys) {
    const value = values?.[key]
    if (value !== undefined && value !== null && value !== '' && !(Array.isArray(value) && !value.length)) {
      return value
    }
  }
  return ''
}

const formatTaskFieldValue = (value, field) => {
  if (value === undefined || value === null || value === '') return ''
  if (Array.isArray(value)) {
    if (field.format === 'images') return `${value.length} 张`
    return value.join(' / ')
  }
  if (typeof value === 'object') {
    return value.package_name || value.name || value.title || ''
  }
  if (field.format === 'currency') return `¥${value}`
  if (field.suffix) return `${value}${field.suffix}`
  return String(value)
}

const getTaskSteps = (taskType, status, plan) => {
  const planSteps = Array.isArray(plan?.steps) ? plan.steps : []
  if (planSteps.length) {
    return planSteps.map(step => ({
      id: step.id || step.summary,
      label: STEP_LABELS[step.id] || step.summary || step.id || '任务步骤',
      status: step.status || 'pending',
      statusTone: stepStatusTone(step.status),
    }))
  }

  const fallbackSteps = {
    create_project: [
      ['collect_details', ['awaiting_details'].includes(status) ? 'in_progress' : 'completed'],
      ['add_reference_images', status === 'awaiting_reference_images' ? 'in_progress' : stepDoneAfterDetails(status)],
      ['confirm_project', status === 'awaiting_confirmation' ? 'in_progress' : finalStepStatus(status)],
      ['create_project', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending'],
    ],
    publish_package: [
      ['collect_details', ['awaiting_details'].includes(status) ? 'in_progress' : 'completed'],
      ['add_reference_images', status === 'awaiting_reference_images' ? 'in_progress' : stepDoneAfterDetails(status)],
      ['confirm_package', status === 'awaiting_confirmation' ? 'in_progress' : finalStepStatus(status)],
      ['publish_package', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending'],
    ],
    create_booking: [
      ['search_packages', ['awaiting_package'].includes(status) ? 'in_progress' : 'completed'],
      ['select_date', status === 'awaiting_date' ? 'in_progress' : stepDoneAfterDate(status)],
      ['confirm_booking', status === 'awaiting_confirmation' ? 'in_progress' : finalStepStatus(status)],
      ['create_booking', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending'],
    ],
  }[taskType] || []

  return fallbackSteps.map(([id, stepStatus]) => ({
    id,
    label: STEP_LABELS[id] || id,
    status: stepStatus,
    statusTone: stepStatusTone(stepStatus),
  }))
}

const stepDoneAfterDetails = (status) => {
  return ['awaiting_confirmation', 'completed', 'failed'].includes(status) ? 'completed' : 'pending'
}

const stepDoneAfterDate = (status) => {
  return ['awaiting_confirmation', 'completed', 'failed'].includes(status) ? 'completed' : 'pending'
}

const finalStepStatus = (status) => {
  if (status === 'completed') return 'completed'
  if (status === 'failed') return 'failed'
  return 'pending'
}

const stepStatusTone = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'failed' || status === 'blocked') return 'danger'
  if (status === 'in_progress') return 'primary'
  return 'muted'
}

const getTaskProgress = (steps, status, fields) => {
  if (status === 'completed') return 100
  if (status === 'failed' || status === 'cancelled') return 0
  if (steps.length) {
    const completed = steps.filter(step => step.status === 'completed').length
    const inProgress = steps.some(step => step.status === 'in_progress') ? 0.5 : 0
    return Math.round(((completed + inProgress) / steps.length) * 100)
  }
  if (!fields.length) return 0
  const filled = fields.filter(field => field.value && !field.missing).length
  return Math.round((filled / fields.length) * 100)
}

const getTaskFieldSourceEdit = (card, field, sourceKey) => taskFieldEdits.value[card.key]?.[sourceKey]
  ?? getStoredTaskCardValues(card)?.[sourceKey]
  ?? field.rawValues?.[sourceKey]
  ?? (sourceKey === field.sourceKey ? field.rawValue : '')
  ?? ''

const getTaskFieldEdit = (card, field) => getTaskFieldSourceEdit(card, field, field.sourceKey)

const setTaskFieldEdit = (card, field, value) => {
  taskFieldEdits.value = {
    ...taskFieldEdits.value,
    [card.key]: {
      ...(taskFieldEdits.value[card.key] || {}),
      [field.sourceKey]: value,
    },
  }
  taskFieldErrors.value = { ...taskFieldErrors.value, [card.key]: '' }
}

const isTaskListEditor = field => ['list', 'textarea-list'].includes(field.editor)

const parseTaskListValue = (value) => {
  if (Array.isArray(value)) return value.map(item => String(item).trim()).filter(Boolean)
  return String(value || '')
    .split(/[、,，;；\n]+/)
    .map(item => item.trim())
    .filter(Boolean)
}

const getTaskEditorValue = (card, field) => {
  const value = getTaskFieldEdit(card, field)
  return isTaskListEditor(field) && Array.isArray(value) ? value.join('、') : value
}

const setTaskEditorValue = (card, field, value) => {
  setTaskFieldEdit(card, field, value)
}

const getTaskEditorInputType = (field) => {
  if (field.editor === 'textarea-list') return 'textarea'
  if (field.editor === 'list') return 'text'
  return field.editor
}

const getTaskEditorRows = (field) => {
  if (field.editor === 'textarea-list') return 2
  if (field.editor === 'textarea') return 3
  return undefined
}

const handleTaskEditorEnter = (card, field, event) => {
  if (['textarea', 'textarea-list'].includes(field.editor)) return
  event?.preventDefault()
  commitTaskFieldEdit(card, field, event)
}

const padDatePart = value => String(value).padStart(2, '0')

const getTaskDateValue = (card, field) => {
  const date = String(getTaskFieldSourceEdit(card, field, 'date') || '').slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : ''
}

const getTaskTimeValue = (card, field) => {
  const rawTime = String(getTaskFieldSourceEdit(card, field, 'time') || '')
  return rawTime.match(/\d{1,2}:\d{2}/)?.[0]?.padStart(5, '0') || ''
}

const parseTaskDateValue = (value) => {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate())
  }
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return null
  const parsed = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

const formatTaskDateStorage = (value) => {
  const date = parseTaskDateValue(value)
  if (!date) return ''
  return `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}`
}

const setTaskDateValue = (card, value) => {
  taskFieldEdits.value = {
    ...taskFieldEdits.value,
    [card.key]: {
      ...(taskFieldEdits.value[card.key] || {}),
      date: formatTaskDateStorage(value),
    },
  }
  taskFieldErrors.value = { ...taskFieldErrors.value, [card.key]: '' }
}

const setTaskTimeValue = (card, value) => {
  taskFieldEdits.value = {
    ...taskFieldEdits.value,
    [card.key]: {
      ...(taskFieldEdits.value[card.key] || {}),
      time: String(value || ''),
    },
  }
  taskFieldErrors.value = { ...taskFieldErrors.value, [card.key]: '' }
}

const getTaskDateDisplay = (card, field) => {
  const date = parseTaskDateValue(getTaskDateValue(card, field))
  if (!date) return '选择拍摄日期'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(date)
}

const getTaskDateEditorId = (card, field) => `task-date-editor-${card.key}-${field.key}`

const isTaskDateEditorOpen = (card, field = null) => taskDateEditor.value?.cardKey === card.key
  && (!field || taskDateEditor.value.fieldKey === field.key)

const shouldRenderProjectField = (card, field) => !isTaskDateEditorOpen(card)
  || field.sectionKey !== 'schedule'
  || field.editor === 'datetime'

const getTaskDateEditorCursor = (card, field) => {
  if (isTaskDateEditorOpen(card, field) && taskDateEditor.value?.cursor) {
    return taskDateEditor.value.cursor
  }
  return parseTaskDateValue(getTaskDateValue(card, field)) || new Date()
}

const focusTaskDateEditorDay = (card, field) => {
  const panel = document.getElementById(getTaskDateEditorId(card, field))
  panel?.querySelector('.project-calendar-day.is-selected, .project-calendar-day:not(.is-adjacent)')?.focus()
}

const openTaskDateEditor = async (card, field) => {
  taskDateEditor.value = {
    cardKey: card.key,
    fieldKey: field.key,
    cursor: parseTaskDateValue(getTaskDateValue(card, field)) || new Date(),
  }
  await nextTick()
  focusTaskDateEditorDay(card, field)
}

const closeTaskDateEditor = async (card, field, restoreFocus = true) => {
  if (!isTaskDateEditorOpen(card, field)) return
  taskDateEditor.value = null
  if (!restoreFocus) return
  await nextTick()
  document.getElementById(`task-field-${card.key}-${field.key}`)?.focus()
}

const updateTaskDateEditorCursor = (value) => {
  const cursor = parseTaskDateValue(value)
  if (!taskDateEditor.value || !cursor) return
  taskDateEditor.value = { ...taskDateEditor.value, cursor }
}

const selectTaskCalendarDay = (card, field, day) => {
  const date = formatTaskDateStorage(day)
  if (!date) return
  setTaskDateValue(card, date)
  commitTaskFieldEdit(card, field)
  closeTaskDateEditor(card, field)
}

const isTaskCalendarDaySelected = (card, field, day) => getTaskDateValue(card, field) === day

const getTaskCalendarDayNumber = day => Number(String(day).slice(-2))

const formatTaskCalendarDayAria = (day) => {
  const date = parseTaskDateValue(day)
  if (!date) return String(day || '')
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(date)
}

const getTaskLocationValue = (card) => {
  const values = getTaskCardValues(card)
  return {
    text: values.location_text || '',
    name: values.location_name || '',
    address: values.location_address || '',
    latitude: values.location_latitude ?? null,
    longitude: values.location_longitude ?? null,
    place_id: values.location_place_id || null,
    provider: values.location_provider || null,
    coordinate_system: values.coordinate_system || null,
    precision: values.location_precision || null,
  }
}

const setTaskLocationValue = (card, location) => {
  const mapped = {
    location_text: location?.text || '',
    location_name: location?.name || '',
    location_address: location?.address || '',
    location_latitude: location?.latitude ?? null,
    location_longitude: location?.longitude ?? null,
    location_place_id: location?.place_id || null,
    location_provider: location?.provider || null,
    coordinate_system: location?.coordinate_system || null,
    location_precision: location?.precision || null,
  }
  taskFieldEdits.value = { ...taskFieldEdits.value, [card.key]: { ...(taskFieldEdits.value[card.key] || {}), ...mapped } }
  taskFieldErrors.value = { ...taskFieldErrors.value, [card.key]: '' }
  localStorage.setItem(getTaskCardStorageKey(card), JSON.stringify(getTaskCardValues(card)))
}

const getTaskFieldError = (card) => taskFieldErrors.value[card.key] || ''

const getTaskCardStorageKey = (card) => {
  const namespace = card.taskType === 'publish_package' ? 'package' : 'project'
  return `ai-${namespace}-card-${conversationId.value || 'pending'}-${card.key}`
}

const getStoredTaskCardValues = (card) => {
  try {
    return JSON.parse(localStorage.getItem(getTaskCardStorageKey(card)) || 'null')
  } catch {
    return null
  }
}

const getTaskSaveFeedback = (card) => taskSaveFeedback.value[card.key] || '自动保存已开启'

const getTaskImageFieldLabel = (card, field) => {
  const existing = Array.isArray(getTaskFieldEdit(card, field))
    ? getTaskFieldEdit(card, field)
    : []
  const pending = pendingImages.value.map(item => item.url || item.previewUrl).filter(Boolean)
  const total = new Set([...existing, ...pending]).size
  const noun = card.taskType === 'publish_package' ? '样片' : '参考图'
  return total ? `已添加 ${total} 张，点击继续添加` : `点击添加${noun}`
}

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getAttachments = (message) => {
  const meta = message.metadata
  if (!meta) return []
  return meta.attachments || []
}

const getPageContext = (message) => {
  const context = message.metadata?.page_context
  return context && typeof context === 'object' ? context : null
}

const hasPageContext = (message) => Boolean(
  getPageContext(message)?.resource_type && getPageContextTitle(message)
)

const getPageContextTitle = (message) => {
  const context = getPageContext(message)
  return context?.title || context?.package_name || context?.photographer_name || ''
}

const getPageContextTypeLabel = (message) => {
  const labels = {
    portfolio_item: '引用作品',
    package: '引用方案',
    photographer: '引用摄影师',
    project: '引用企划',
  }
  return labels[getPageContext(message)?.resource_type] || '引用当前内容'
}

const getPageContextThumbnail = (message) => {
  return getPageContext(message)?.current_object?.thumbnail_url || ''
}

const goPageContext = (context) => {
  if (!context) return
  if (context.route_path) {
    router.push(context.route_path)
    return
  }
  const routes = {
    portfolio_item: context.resource_id ? `/work/${context.resource_id}` : '',
    package: context.resource_id ? `/package/${context.resource_id}` : '',
    photographer: context.resource_id ? `/photographer/${context.resource_id}` : '',
    project: context.resource_id ? `/projects/${context.resource_id}` : '',
  }
  const target = routes[context.resource_type]
  if (target) router.push(target)
}

const getReferences = (message) => {
  const refs = message.metadata?.references || {}
  return {
    photographers: refs.photographers || [],
    portfolio_items: refs.portfolio_items || [],
    packages: refs.packages || [],
  }
}

const hasReferences = (message) => {
  const refs = getReferences(message)
  return Boolean(
    refs.photographers.length ||
    refs.portfolio_items.length ||
    refs.packages.length
  )
}

const getSuggestedActions = (message) => {
  return Array.isArray(message.metadata?.suggested_actions)
    ? message.metadata.suggested_actions
    : []
}

const hasSuggestedActions = (message) => {
  return getSuggestedActions(message).length > 0
}

const CLIENT_ACTION_TYPES = new Set([
  'open_work_publisher',
  'open_project_application',
])

const getClientActions = (message) => {
  const actions = Array.isArray(message.metadata?.client_actions)
    ? message.metadata.client_actions
    : []
  return actions.filter(action => CLIENT_ACTION_TYPES.has(action?.type))
}

const hasClientActions = (message) => getClientActions(message).length > 0

const getClientActionKey = (message, action) => `${message.id}-${action.type}`

const isClientActionLoading = (message, action) => Boolean(
  clientActionLoading.value[getClientActionKey(message, action)]
)

const getClientActionDisabledReason = (action) => {
  if (action?.disabled_reason) return String(action.disabled_reason)
  if (action?.type === 'open_project_application' && !action.project_id) return '缺少目标企划，暂时无法打开应邀表单'
  return ''
}

const isClientActionDisabled = (action) => Boolean(getClientActionDisabledReason(action))

const getClientActionFallbackLabel = (action) => (
  action?.type === 'open_project_application' ? '填写应邀方案' : '去发布作品'
)

const getClientActionIcon = (action) => (
  action?.type === 'open_project_application' ? FilePenLine : Upload
)

const handleClientAction = async (message, action) => {
  if (sending.value || isClientActionLoading(message, action) || isClientActionDisabled(action)) return

  const key = getClientActionKey(message, action)
  clientActionLoading.value = { ...clientActionLoading.value, [key]: true }
  try {
    if (action.type === 'open_project_application') {
      await router.push({
        name: 'ProjectApply',
        params: { projectId: String(action.project_id) },
      })
      return
    }

    const draft = action.draft && typeof action.draft === 'object' ? action.draft : {}
    const savedDraft = await saveWorkDraft({
      userId: currentUserId.value,
      mediaType: draft.media_kind === 'video' ? 'video' : 'image',
      title: draft.title || '',
      description: draft.description || '',
      tags: Array.isArray(draft.tags) ? draft.tags : [],
      files: [],
      coverFile: null,
    })
    await router.push({ name: 'UploadWork', query: { draftId: savedDraft.id } })
  } catch {
    ElMessage.error(
      action.type === 'open_project_application'
        ? '应邀页面打开失败，请稍后重试'
        : '作品草稿保存失败，请稍后重试',
    )
  } finally {
    clientActionLoading.value = { ...clientActionLoading.value, [key]: false }
  }
}

const isReferenceImageAction = (action) => {
  return ['add_project_reference_images', 'add_package_reference_images'].includes(action?.type)
}

const getSuggestedActionIcon = (action) => {
  return isReferenceImageAction(action) ? Picture : Check
}

const getReferenceTags = (item) => {
  if (Array.isArray(item?.tags)) return item.tags
  return (item?.tag || '')
    .split(/[,\uFF0C\u3001\n]/)
    .map(tag => tag.trim())
    .filter(Boolean)
}

const getPackageCover = (pkg) => {
  return Array.isArray(pkg?.samples) && pkg.samples.length ? pkg.samples[0] : ''
}

const goPhotographer = (userId) => {
  if (userId) router.push(`/photographer/${userId}`)
}

const goWork = (work) => {
  if (work?.id) {
    router.push({
      path: `/work/${work.id}`,
      state: { from: router.currentRoute.value.fullPath, work },
    })
  } else if (work?.user_id) {
    goPhotographer(work.user_id)
  }
}

const goPackage = (pkg) => {
  if (pkg?.id) {
    router.push(`/package/${pkg.id}`)
  } else if (pkg?.photographer_id) {
    router.push({
      path: `/booking/${pkg.photographer_id}`,
      query: { packageName: pkg.package_name },
    })
  }
}

const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

const openImagePicker = () => {
  if (!sending.value) {
    fileInput.value?.click()
  }
}

const initConversation = async () => {
  await initializeConversation()
  const routeConversationId = route.query.conversation
  if (routeConversationId && conversations.value.some(item => String(item.id) === String(routeConversationId))) {
    await selectConversation(routeConversationId)
  }
  await syncConversationRoute()
  await scrollToBottom()
}

const handleFileChange = async (event) => {
  const files = event.target.files
  if (!files || !files.length) return

  for (const file of files) {
    if (generationConfig.value.mode === 'text_to_image') {
      ElMessage.warning('文生图模式不使用参考图片，请切换到以图生图')
      break
    }
    if (generationConfig.value.mode === 'image_to_image' && pendingImages.value.length >= 1) {
      ElMessage.warning('以图生图第一版只支持一张参考图')
      break
    }
    // 限制最多 4 张
    if (pendingImages.value.length >= 4) {
      ElMessage.warning('最多上传 4 张图片')
      break
    }
    let imgEntry = null
    try {
      const uploadFile = await compressAIReferenceImage(file)
      const previewUrl = URL.createObjectURL(uploadFile)
      imgEntry = { file: uploadFile, previewUrl, uploading: true, url: '', mimeType: uploadFile.type, metadata: null }
      pendingImages.value.push(imgEntry)
      const res = await uploadAIImage(uploadFile)
      imgEntry.url = res.data.url
      imgEntry.mimeType = res.data.mime_type || uploadFile.type
      imgEntry.metadata = res.data
      imgEntry.uploading = false
    } catch (error) {
      if (imgEntry?.previewUrl) URL.revokeObjectURL(imgEntry.previewUrl)
      const idx = pendingImages.value.indexOf(imgEntry)
      if (idx >= 0) pendingImages.value.splice(idx, 1)
      const detail = error?.response?.data?.detail
      ElMessage.error(typeof detail === 'object' ? detail.message : (detail || error?.message || '图片上传失败'))
    }
  }
  // 重置 file input 以支持重复选择同一文件
  event.target.value = ''
}

const removePendingImage = (idx) => {
  const img = pendingImages.value[idx]
  if (img && img.previewUrl) URL.revokeObjectURL(img.previewUrl)
  pendingImages.value.splice(idx, 1)
}

const pendingImageAttachment = img => ({
  type: 'image',
  url: img.url,
  mime_type: img.mimeType,
  thumb_url: img.metadata?.thumb_url,
  width: img.metadata?.width,
  height: img.metadata?.height,
  size_bytes: img.metadata?.size_bytes,
  sha256: img.metadata?.sha256,
  original_width: img.metadata?.original_width,
  original_height: img.metadata?.original_height,
  original_size_bytes: img.metadata?.original_size_bytes,
  normalized: img.metadata?.normalized,
})

const buildMessagePayload = (content, attachments = []) => {
  const payload = { content: content || null }
  if (attachments.length) payload.attachments = attachments
  if (normalizedPageContext.value) payload.page_context = normalizedPageContext.value
  return payload
}

const createIdempotencyKey = () => window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`

const buildGenerationRequest = () => {
  const { mode, aspect_ratio, count, quality, strength } = generationConfig.value
  if (!mode) return null
  return {
    mode,
    aspect_ratio,
    count,
    quality,
    ...(mode === 'image_to_image' ? { strength } : {}),
    idempotency_key: createIdempotencyKey(),
  }
}

const handleSend = async () => {
  const content = inputText.value.trim()
  const hasImages = pendingImages.value.some(img => img.url)
  if ((!content && !hasImages) || !conversationId.value || sending.value) return

  if (generationValidationMessage.value || (generationConfig.value.mode && !content)) {
    ElMessage.warning(generationValidationMessage.value || '请填写图片生成描述')
    return
  }

  sending.value = true
  try {
    const attachments = pendingImages.value
      .filter(img => img.url)
      .map(pendingImageAttachment)

    const payload = buildMessagePayload(content, attachments)
    const generationRequest = buildGenerationRequest()
    if (generationRequest) payload.generation_request = generationRequest

    const res = await sendAIMessage(conversationId.value, payload)
    appendResponseMessages(res.data.user_message, res.data.assistant_message)
    inputText.value = ''
    // 清理 pending images
    pendingImages.value.forEach(img => { if (img.previewUrl) URL.revokeObjectURL(img.previewUrl) })
    pendingImages.value = []
    generationConfig.value = { mode: null, aspect_ratio: '1:1', count: 1, quality: 'standard', strength: 0.65 }
    await scrollToBottom()
  } catch {
    ElMessage.warning('消息已尝试发送，AI 回复失败时可稍后重试')
    if (conversationId.value) {
      try {
        await reloadMessages()
      } catch {}
    }
  } finally {
    sending.value = false
  }
}

const sendTaskText = async (content) => {
  if (!conversationId.value || sending.value || !content.trim()) return

  sending.value = true
  try {
    const res = await sendAIMessage(conversationId.value, buildMessagePayload(content.trim()))
    appendResponseMessages(res.data.user_message, res.data.assistant_message)
    await scrollToBottom()
  } catch {
    ElMessage.warning('操作已尝试发送，失败时可稍后重试')
    if (conversationId.value) {
      try {
        await reloadMessages()
      } catch {}
    }
  } finally {
    sending.value = false
  }
}

const isBlankTaskValue = (value) => {
  if (Array.isArray(value)) return !value.some(item => String(item).trim())
  return value === undefined || value === null || String(value).trim() === ''
}

const normalizeTaskFieldValue = (field, value) => {
  if (isTaskListEditor(field)) return parseTaskListValue(value)
  if (field.editor === 'number' && !isBlankTaskValue(value)) {
    const numericValue = Number(value)
    return Number.isFinite(numericValue) ? numericValue : value
  }
  return value
}

const normalizeTaskImageUrls = (value) => {
  const values = Array.isArray(value) ? value : (value ? [value] : [])
  return values.map(item => String(item).trim()).filter(Boolean)
}

const getTaskCardValues = (card) => {
  const values = {
    ...(getStoredTaskCardValues(card) || {}),
    ...(taskFieldEdits.value[card.key] || {}),
  }
  card.fields.forEach((field) => {
    field.sourceKeys.forEach((sourceKey) => {
      const rawValue = getTaskFieldSourceEdit(card, field, sourceKey)
      values[sourceKey] = sourceKey === field.sourceKey
        ? normalizeTaskFieldValue(field, rawValue)
        : rawValue
    })
  })

  const imageField = card.fields.find(field => field.editor === 'images')
  if (imageField) {
    const pendingUrls = pendingImages.value.map(item => item.url).filter(Boolean)
    values[imageField.sourceKey] = [...new Set([
      ...normalizeTaskImageUrls(values[imageField.sourceKey]),
      ...pendingUrls,
    ])]
  }
  return values
}

const commitTaskFieldEdit = (card, field, event) => {
  if (event?.target?.blur) event.target.blur()
  localStorage.setItem(getTaskCardStorageKey(card), JSON.stringify(getTaskCardValues(card)))
  taskSaveFeedback.value = { ...taskSaveFeedback.value, [card.key]: `${field.label}已自动保存` }
  taskFieldErrors.value = { ...taskFieldErrors.value, [card.key]: '' }
}

const isInvalidTaskField = (field, values) => {
  const value = field.editor === 'datetime' ? values.date : values[field.sourceKey]
  if (isBlankTaskValue(value)) return !field.optional && field.editor !== 'images'
  if (field.editor !== 'number') return false
  const numericValue = Number(value)
  return !Number.isFinite(numericValue) || (field.min !== undefined && numericValue < field.min)
}

const submitPublisherFromCard = async (card, action) => {
  const isPublish = action === 'publish'
  const taskValues = getTaskCardValues(card)
  if (isPublish) {
    const invalidFields = card.fields.filter(field => isInvalidTaskField(field, taskValues))
    if (invalidFields.length) {
      taskFieldErrors.value = {
        ...taskFieldErrors.value,
        [card.key]: `发布前请检查：${invalidFields.map(field => field.label).join('、')}`,
      }
      const firstInvalid = invalidFields[0]
      document.getElementById(`task-field-${card.key}-${firstInvalid.key}`)?.focus()
      return
    }
  }

  if (!isPublish && card.taskType === 'publish_package') {
    savingTaskDraft.value = true
    try {
      localStorage.setItem(getTaskCardStorageKey(card), JSON.stringify(taskValues))
      taskSaveFeedback.value = { ...taskSaveFeedback.value, [card.key]: '方案草稿已暂存到本机' }
      taskFieldErrors.value = { ...taskFieldErrors.value, [card.key]: '' }
    } finally {
      savingTaskDraft.value = false
    }
    return
  }

  const attachments = pendingImages.value
    .filter(img => img.url)
    .map(pendingImageAttachment)
  if (!conversationId.value || sending.value) return

  sending.value = true
  savingTaskDraft.value = !isPublish
  publishingTask.value = isPublish
  try {
    localStorage.setItem(getTaskCardStorageKey(card), JSON.stringify(taskValues))
    const isPackage = card.taskType === 'publish_package'
    const payload = buildMessagePayload(isPackage ? '发布方案' : (isPublish ? '发布企划' : '保存为草稿'), attachments)
    const imageField = card.fields.find(field => field.editor === 'images')
    const hasImages = imageField
      ? normalizeTaskImageUrls(taskValues[imageField.sourceKey]).length > 0
      : attachments.length > 0
    payload.task_submission = {
      task_type: card.taskType,
      action,
      slots: taskValues,
      skip_reference_images: !hasImages,
    }
    const res = await sendAIMessage(
      conversationId.value,
      payload,
    )
    appendResponseMessages(res.data.user_message, res.data.assistant_message)
    localStorage.removeItem(getTaskCardStorageKey(card))
    pendingImages.value.forEach(img => { if (img.previewUrl) URL.revokeObjectURL(img.previewUrl) })
    pendingImages.value = []
    await scrollToBottom()
  } catch {
    const noun = card.taskType === 'publish_package' ? '方案' : '企划'
    ElMessage.warning(isPublish ? `${noun}发布失败，请稍后重试` : '草稿保存失败，请稍后重试')
    if (conversationId.value) {
      try { await reloadMessages() } catch {}
    }
  } finally {
    sending.value = false
    savingTaskDraft.value = false
    publishingTask.value = false
  }
}

const handleTaskConfirm = async (card) => {
  const label = card.fallbackConfirmLabel || '确认'
  const mode = toolPolicy.value?.confirmation_mode || 'inline'
  const isHighRisk = ['create_project', 'publish_package', 'publish_work', 'create_booking'].includes(card.taskType)
  if (!isHighRisk || mode === 'inline') {
    await sendTaskText(label)
    return
  }
  const details = (card.fields || [])
    .filter(field => field.value && !field.missing)
    .slice(0, 8)
    .map(field => `${field.label}：${field.value}`)
    .join('<br>')
  try {
    if (mode === 'explicit_text') {
      const { value } = await ElMessageBox.prompt(
        `请核对以下操作：<br>${details || '已填写的任务信息'}<br><br>请输入“确认”继续。`,
        label,
        { dangerouslyUseHTMLString: true, inputPattern: /^确认$/, inputErrorMessage: '请输入“确认”', confirmButtonText: '继续', cancelButtonText: '取消' },
      )
      if (value !== '确认') return
    } else {
      await ElMessageBox.confirm(
        details || '请核对已填写的任务信息。',
        label,
        { dangerouslyUseHTMLString: true, type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '取消' },
      )
    }
    await sendTaskText(label)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('确认操作失败，请稍后重试')
  }
}

const sendPresetPrompt = async (prompt) => {
  const text = String(prompt || '').trim()
  if (!text) return
  inputText.value = text
  await handleSend()
}

const activateInspirationTool = () => {
  if (sending.value || loadingMessages.value) return
  inputText.value = '请根据我上传的参考图片创建灵感'
  openImagePicker()
}

const handleGenerationModeChange = (mode) => {
  if (mode === 'image_to_image' && !pendingImages.value.length) openImagePicker()
  if (mode === 'text_to_image' && pendingImages.value.length) {
    ElMessage.info('请移除现有图片，或切换到以图生图')
  }
}

const updateQuickPromptScrollState = () => {
  const scroller = quickPromptScroller.value
  if (!scroller) return
  const maxScrollLeft = Math.max(0, scroller.scrollWidth - scroller.clientWidth)
  quickPromptOverflow.value = maxScrollLeft > 1
  canScrollQuickPromptsLeft.value = scroller.scrollLeft > 1
  canScrollQuickPromptsRight.value = scroller.scrollLeft < maxScrollLeft - 1
}

const scrollQuickPrompts = (direction) => {
  const scroller = quickPromptScroller.value
  if (!scroller) return
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  scroller.scrollBy({
    left: direction * Math.max(180, scroller.clientWidth * 0.72),
    behavior: reduceMotion ? 'auto' : 'smooth',
  })
}

const handleSuggestedAction = async (action) => {
  if (!conversationId.value || sending.value) return

  if (isReferenceImageAction(action)) {
    openImagePicker()
    ElMessage.info('选择参考图后点击发送，我会把它加入当前草稿')
    return
  }

  sending.value = true
  try {
    const content = action?.label || '确认'
    const res = await sendAIMessage(conversationId.value, buildMessagePayload(content))
    appendResponseMessages(res.data.user_message, res.data.assistant_message)
    await scrollToBottom()
  } catch {
    ElMessage.warning('操作已尝试发送，失败时可稍后重试')
    if (conversationId.value) {
      try {
        await reloadMessages()
      } catch {}
    }
  } finally {
    sending.value = false
  }
}

const fetchUserInfo = async () => {
  try {
    const res = await api.get('/users/me')
    currentUserId.value = res.data.id || ''
    userAvatarUrl.value = res.data.avatar_url || ''
    userDisplayName.value = res.data.display_name || ''
  } catch {}
}

onMounted(async () => {
  await nextTick()
  updateQuickPromptScrollState()
  if (typeof ResizeObserver !== 'undefined' && quickPromptScroller.value) {
    quickPromptResizeObserver = new ResizeObserver(updateQuickPromptScrollState)
    quickPromptResizeObserver.observe(quickPromptScroller.value)
  }

  if (!embedded.value) {
    document.documentElement.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
  }

  if (!localStorage.getItem('token')) {
    router.push('/login')
    return
  }
  fetchUserInfo()
  await initConversation()
})

onUnmounted(() => {
  quickPromptResizeObserver?.disconnect()
  revealTimers.forEach(timer => window.clearTimeout(timer))
  revealTimers.clear()
  if (!embedded.value) {
    document.documentElement.style.overflow = ''
    document.body.style.overflow = ''
  }
})
</script>

<style scoped>
.ai-page {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 840px);
  gap: var(--space-3);
  max-width: 1120px;
  height: min(700px, calc(100dvh - 120px));
  min-height: 430px;
  margin: var(--space-4) auto 0;
  padding: 0 var(--space-4) var(--space-3);
  box-sizing: border-box;
  overflow: hidden;
}

.ai-page-embedded {
  display: block;
  width: 100%;
  max-width: none;
  height: 100%;
  min-height: 0;
  margin: 0;
  padding: 0;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  min-width: 0;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  overflow: hidden;
}

.ai-page-embedded .chat-panel {
  border: 0;
  border-radius: 0;
}

.chat-header {
  height: var(--header-height);
  padding: 0 var(--space-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 1px solid var(--color-divider);
  box-sizing: border-box;
}

.chat-heading {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title {
  color: var(--color-ink);
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
}

.chat-subtitle {
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-chat-btn {
  flex: 0 0 auto;
}

.quick-prompt-shell {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-1);
  padding: 6px var(--space-3) 2px;
  background: var(--color-paper);
}

.quick-prompts {
  display: flex;
  gap: var(--space-2);
  min-width: 0;
  padding: 2px;
  overflow-x: auto;
  scroll-behavior: smooth;
  scrollbar-color: var(--color-divider) transparent;
  scrollbar-width: thin;
}

.quick-prompts::-webkit-scrollbar {
  height: 3px;
}

.quick-prompts::-webkit-scrollbar-track {
  background: transparent;
}

.quick-prompts::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: var(--color-divider);
}

.quick-prompt {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 0 0 auto;
  max-width: 180px;
  min-height: 44px;
  padding: 0 12px;
  border: var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--color-brand-light);
  color: var(--color-brand);
  cursor: pointer;
  font: inherit;
  font-size: calc(var(--text-xs) * 1rem);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s;
}

.quick-prompt svg {
  width: 17px;
  height: 17px;
  flex: 0 0 auto;
}

.quick-prompt--inspiration {
  border-color: color-mix(in srgb, var(--color-brand) 48%, var(--color-divider));
  font-weight: 700;
}

.quick-prompt-nav {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  padding: 0;
  border: var(--border-default);
  border-radius: 50%;
  background: var(--color-paper-light);
  color: var(--color-brand);
  cursor: pointer;
}

.quick-prompt-nav svg {
  width: 18px;
  height: 18px;
}

.quick-prompt-nav:disabled {
  cursor: default;
  opacity: 0.38;
}

.quick-prompt:focus-visible,
.quick-prompt-nav:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.quick-prompt:hover:not(:disabled) {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.quick-prompt:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.empty-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-4);
  background: var(--color-paper-light);
  box-sizing: border-box;
}

.message-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 14px;
}

.message-row.mine {
  justify-content: flex-end;
}

.message-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: min(520px, 72%);
  gap: 6px;
}

.message-row.mine .message-stack {
  align-items: flex-end;
}

.message-avatar {
  flex-shrink: 0;
  margin-right: var(--space-2);
}

.user-avatar {
  margin-right: 0;
  margin-left: var(--space-2);
}

.message-bubble {
  width: fit-content;
  max-width: 100%;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  border: var(--border-default);
  color: var(--color-ink);
}

.reference-message-stack {
  width: min(520px, 72%);
}

.reference-message-bubble {
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
}

.segmented-message-bubble {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: 0;
  border: 0;
  background: transparent;
}

.segmented-message-bubble .message-content-card {
  width: fit-content;
  max-width: 100%;
  padding: 10px 14px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.task-message-stack {
  width: min(780px, calc(100vw - 120px));
  max-width: min(780px, calc(100vw - 120px));
}

.task-message-bubble {
  width: 100%;
  max-width: none;
  padding: 0;
  border: 0;
  background: transparent;
}

.message-row.mine .message-bubble {
  background: var(--color-brand-light);
  color: var(--color-ink);
  border: 1px solid var(--color-border-light);
}

.message-context-card {
  display: flex;
  width: min(320px, 100%);
  min-height: 86px;
  padding: 0;
  align-items: center;
  overflow: hidden;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  text-align: left;
  cursor: pointer;
}

.message-context-card:hover {
  border-color: var(--color-brand);
}

.message-context-cover {
  width: 108px;
  aspect-ratio: 4 / 3;
  flex-shrink: 0;
  object-fit: cover;
  background: var(--color-divider);
}

.message-context-body {
  min-width: 0;
  display: grid;
  align-content: center;
  gap: 5px;
  padding: 10px var(--space-3);
}

.message-context-type {
  color: var(--color-brand);
  font-size: calc(var(--text-xs) * 0.92rem);
  font-weight: 600;
  line-height: 1.3;
}

.message-context-title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-ink);
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 600;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.message-images {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: var(--space-2);
}

.message-image {
  width: 120px;
  height: 120px;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.message-text {
  font-size: calc(var(--text-sm) * 1rem);
  line-height: var(--leading-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.message-time {
  margin-top: var(--space-1);
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 0.92rem);
  text-align: right;
}

.message-row.mine .message-time {
  color: var(--color-ink-secondary);
}

.suggested-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.client-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.client-actions :deep(.el-button) {
  min-height: 44px;
}

.client-action-disabled-reason {
  flex-basis: 100%;
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.5;
}

@media (prefers-reduced-motion: reduce) {
  .client-actions :deep(.el-button) {
    transition: none;
  }
}

.task-card {
  width: 100%;
  margin: 0;
  padding: var(--space-4);
  border: var(--border-default);
  border-radius: var(--radius-lg);
  background: var(--color-paper-light);
  color: var(--color-ink);
}

.project-editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-divider);
}

.project-editor-header .task-card-title {
  font-size: calc(var(--text-lg) * 1rem);
  line-height: 1.35;
}

.project-save-state {
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.5;
}

.project-save-state {
  flex: 0 0 auto;
  color: var(--color-brand);
  text-align: right;
}

.project-editor-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: var(--space-2);
}

.project-editor-section {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 650;
  letter-spacing: 0.02em;
}

.project-editor-section:first-child {
  margin-top: 0;
}

.project-editor-section::after {
  height: 1px;
  flex: 1;
  background: var(--color-divider);
  content: '';
}

.project-editor-field {
  grid-column: span 6;
  min-width: 0;
  padding: var(--space-2) 10px;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
}

.project-editor-field:hover,
.project-editor-field:focus-within {
  border-color: var(--color-brand);
  background: var(--color-paper-light);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brand) 9%, transparent);
}

.project-editor-field.missing:not(:focus-within) {
  border-color: var(--color-warning);
}

.project-editor-field.span-4 { grid-column: span 4; }
.project-editor-field.span-8 { grid-column: span 8; }
.project-editor-field.span-12 { grid-column: 1 / -1; }

.project-editor-label {
  display: block;
  margin-bottom: 1px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  font-weight: 600;
  line-height: 1.4;
}

.project-editor-optional {
  margin-left: 4px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  font-weight: 400;
}

.project-editor-input-row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
}

.project-editor-input-row :deep(.el-input),
.project-editor-input-row :deep(.el-textarea) {
  min-width: 0;
  flex: 1;
}

.project-editor-unit {
  flex: 0 0 auto;
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-sm) * 1rem);
}

.project-editor-helper {
  display: block;
  margin-top: 3px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.45;
}

.project-editor-field :deep(.el-input__wrapper),
.project-editor-field :deep(.el-textarea__inner) {
  min-height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
  color: var(--color-ink);
  font-size: calc(var(--text-base) * 1rem);
}

.project-editor-field :deep(.el-input__wrapper.is-focus),
.project-editor-field :deep(.el-textarea__inner:focus) {
  box-shadow: none;
}

.project-editor-field.field-title :deep(.el-input__inner) {
  font-size: calc(var(--text-lg) * 1rem);
  font-weight: 600;
}

.project-editor-field :deep(.el-textarea__inner) {
  min-height: 62px !important;
  line-height: 1.55;
  resize: none;
}

.project-datetime-editor {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 118px;
  gap: var(--space-2);
}

.project-date-trigger,
.project-time-control {
  min-width: 0;
  min-height: 44px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-paper-light);
}

.project-date-trigger {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 10px;
  color: var(--color-ink);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
}

.project-date-trigger:hover:not(:disabled),
.project-date-trigger:focus-visible {
  border-color: var(--color-brand);
  background: var(--color-paper);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brand) 9%, transparent);
  outline: none;
}

.project-date-trigger:disabled,
.project-time-control:has(input:disabled) {
  cursor: not-allowed;
  opacity: 0.5;
}

.project-date-trigger > svg:first-child,
.project-time-control svg {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  color: var(--color-brand);
}

.project-date-trigger span {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-date-trigger.is-placeholder span {
  color: var(--color-ink-tertiary);
}

.project-date-trigger .project-date-trigger-arrow {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  color: var(--color-ink-tertiary);
}

.project-time-control {
  display: grid;
  grid-template-rows: auto 1fr;
  padding: 5px 9px;
}

.project-time-control label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  font-weight: 600;
  line-height: 1.2;
}

.project-time-control label svg {
  width: 13px;
  height: 13px;
}

.project-time-control input {
  width: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--color-ink);
  font: inherit;
  outline: none;
}

.project-time-control:focus-within {
  border-color: var(--color-brand);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brand) 9%, transparent);
}

.project-date-selection {
  grid-column: 1 / -1;
  min-width: 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--color-brand) 40%, var(--color-border));
  border-radius: var(--radius-md);
  background: var(--color-paper);
  box-shadow: 0 10px 28px color-mix(in srgb, var(--color-ink) 9%, transparent);
}

.project-date-selection-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border-bottom: 1px solid var(--color-divider);
  background: color-mix(in srgb, var(--color-brand) 5%, var(--color-paper));
}

.project-date-selection-intro > div {
  display: grid;
  gap: 2px;
}

.project-date-selection-intro strong {
  color: var(--color-ink);
  font-size: calc(var(--text-base) * 1rem);
}

.project-date-selection-intro span {
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.project-date-selection-close,
.project-calendar-header button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: var(--color-ink-secondary);
  cursor: pointer;
}

.project-date-selection-close {
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  border-radius: var(--radius-sm);
}

.project-date-selection-close:hover,
.project-calendar-header button:hover {
  background: color-mix(in srgb, var(--color-brand) 10%, transparent);
  color: var(--color-brand);
}

.project-date-selection-close:focus-visible,
.project-calendar-header button:focus-visible {
  background: color-mix(in srgb, var(--color-brand) 10%, transparent);
  color: var(--color-brand);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.project-date-selection-close svg,
.project-calendar-header button svg {
  width: 18px;
  height: 18px;
}

.project-inline-calendar {
  --el-calendar-selected-bg-color: transparent;
  background: transparent;
}

.project-inline-calendar :deep(.el-calendar__header) {
  display: block;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-divider);
}

.project-inline-calendar :deep(.el-calendar__body) {
  padding: var(--space-2) var(--space-3) var(--space-3);
}

.project-calendar-header {
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  gap: var(--space-2);
}

.project-calendar-header strong {
  color: var(--color-ink);
  text-align: center;
}

.project-calendar-header button {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
}

.project-inline-calendar :deep(.el-calendar-table thead th) {
  padding: 6px 0;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
  font-weight: 600;
}

.project-inline-calendar :deep(.el-calendar-table td) {
  border: 0;
}

.project-inline-calendar :deep(.el-calendar-table td.is-selected) {
  background: transparent;
}

.project-inline-calendar :deep(.el-calendar-table .el-calendar-day) {
  height: 40px;
  padding: 2px;
}

.project-calendar-day {
  width: 100%;
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-ink-secondary);
  font: inherit;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
}

.project-calendar-day:hover,
.project-calendar-day:focus-visible {
  background: color-mix(in srgb, var(--color-brand) 10%, transparent);
  color: var(--color-brand);
  outline: 2px solid var(--color-focus-ring);
  outline-offset: -2px;
}

.project-calendar-day.is-adjacent {
  color: var(--color-ink-tertiary);
  opacity: 0.55;
}

.project-calendar-day.is-selected {
  background: var(--color-brand);
  color: var(--color-on-brand, #fff);
  font-weight: 700;
}

@media (prefers-reduced-motion: reduce) {
  .project-date-trigger,
  .project-editor-field {
    transition: none;
  }
}

.project-reference-trigger {
  display: flex;
  width: 100%;
  min-height: 60px;
  padding: var(--space-2);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  background: transparent;
  color: var(--color-ink-secondary);
  font: inherit;
  text-align: center;
  cursor: pointer;
}

.project-reference-trigger svg {
  width: 18px;
  height: 18px;
  color: var(--color-brand);
}

.project-reference-trigger:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 3px;
}

.project-editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-divider);
}

.project-editor-actions :deep(.el-button) {
  min-width: 132px;
  min-height: 44px;
}

.task-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.task-card-kicker {
  margin-bottom: 2px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.task-card-title {
  color: var(--color-ink);
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 700;
}

.task-status {
  flex: 0 0 auto;
  padding: 2px var(--space-2);
  border-radius: 999px;
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.5;
  background: var(--color-brand-light);
  color: var(--color-brand);
}

.status-success {
  background: var(--color-brand-light);
  color: var(--color-success);
}

.status-warning {
  background: #FFF8E6;
  color: var(--color-warning);
}

.status-danger {
  background: #FFF0F0;
  color: var(--color-danger);
}

.status-muted {
  background: var(--color-border-light);
  color: var(--color-ink-secondary);
}

.task-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: 10px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.task-progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--color-border-light);
  overflow: hidden;
}

.task-progress-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-brand);
  transition: width 0.2s ease;
}

.task-steps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: 10px;
}

.task-step {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.task-step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-ink-tertiary);
}

.step-success {
  color: var(--color-success);
}

.step-success .task-step-dot {
  background: var(--color-success);
}

.step-primary {
  color: var(--color-brand);
}

.step-primary .task-step-dot {
  background: var(--color-brand);
}

.step-danger {
  color: var(--color-danger);
}

.step-danger .task-step-dot {
  background: var(--color-danger);
}

.task-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.task-field-error {
  margin-top: var(--space-2);
  color: var(--color-danger);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.5;
}

.task-field {
  min-width: 0;
  padding: var(--space-2);
  border: var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--color-paper);
}

.task-field.missing {
  border-color: var(--color-warning);
  background: #FFF8E6;
}

.task-field-label,
.task-section-title {
  display: block;
  margin-bottom: 3px;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.task-field-value {
  display: block;
  min-height: 20px;
  color: var(--color-ink);
  font-size: calc(var(--text-sm) * 1rem);
  line-height: 1.45;
  word-break: break-word;
}

.task-field.missing .task-field-value {
  color: var(--color-warning);
}

.task-draft {
  margin-top: var(--space-3);
}

.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: 10px;
}

.task-actions :deep(.el-button) {
  min-height: 44px;
}

.reference-panel {
  width: 100%;
  margin-top: var(--space-2);
  padding: 0;
}

.reference-section + .reference-section {
  margin-top: var(--space-3);
}

.reference-title {
  margin-bottom: 6px;
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-xs) * 1rem);
  font-weight: 600;
}

.reference-list {
  display: grid;
  gap: var(--space-2);
}

.reference-card {
  width: 100%;
  min-height: 68px;
  padding: var(--space-2);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper);
  box-shadow: var(--shadow-xs);
  color: inherit;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}

.reference-card:hover {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.reference-avatar,
.reference-cover {
  width: 52px;
  height: 52px;
  flex: 0 0 52px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--color-divider);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
}

.reference-avatar img,
.reference-cover {
  object-fit: cover;
}

.reference-avatar img {
  width: 100%;
  height: 100%;
}

.reference-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.reference-name,
.reference-meta,
.reference-tags {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reference-name {
  color: var(--color-ink);
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 600;
}

.reference-meta {
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-xs) * 1rem);
}

.reference-tags {
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-xs) * 1rem);
}

.chat-input-area {
  border-top: 1px solid var(--color-divider);
  background: var(--color-paper);
}

.generation-validation {
  margin: 6px var(--space-3) 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-warning) 10%, var(--color-paper));
  color: var(--color-warning);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 1.5;
}

.pending-images {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) 0;
  flex-wrap: wrap;
}

.pending-image-item {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: var(--border-default);
}

.pending-thumb {
  width: 100%;
  height: 100%;
}

.pending-uploading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 253, 249, 0.7);
  font-size: 20px;
  color: var(--color-brand);
}

.pending-remove {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 18px;
  height: 18px;
  z-index: 1;
}

.chat-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px var(--space-3);
}

.image-btn {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}

.send-button {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}

@media (max-width: 760px) {
  .ai-page {
    height: calc(100dvh - 250px);
    min-height: 0;
    padding: 0 var(--space-2) var(--space-2);
  }

  .ai-page-embedded {
    height: 100%;
    padding: 0;
  }

  .message-list {
    padding: var(--space-3);
  }

  .message-bubble {
    max-width: 86%;
  }

  .reference-message-stack,
  .reference-message-bubble {
    width: 100%;
    max-width: 100%;
  }

  .task-message-stack,
  .task-message-bubble {
    width: 100%;
    max-width: 100%;
  }

  .task-card {
    padding: var(--space-3);
  }

  .project-editor-header {
    align-items: center;
  }

  .project-save-state {
    text-align: right;
  }

  .project-editor-grid {
    grid-template-columns: 1fr;
  }

  .project-editor-field.span-4,
  .project-editor-field.span-8,
  .project-editor-field.span-12 {
    grid-column: 1;
  }

  .project-datetime-editor {
    grid-template-columns: 1fr;
  }

  .project-date-selection-intro {
    padding: var(--space-2) var(--space-3);
  }

  .project-inline-calendar :deep(.el-calendar__body) {
    padding-inline: var(--space-2);
  }

  .project-editor-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .project-editor-actions :deep(.el-button) {
    width: 100%;
    min-width: 0;
    margin: 0;
  }

  .task-fields {
    grid-template-columns: 1fr;
  }

  .task-card-header {
    align-items: stretch;
    flex-direction: column;
  }

  .task-status {
    align-self: flex-start;
  }

  .message-image {
    width: 90px;
    height: 90px;
  }
}
</style>
