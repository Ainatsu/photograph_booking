<template>
  <ion-page>
    <DetailHeader :title="isEditMode ? '编辑拍摄需求' : '发布拍摄需求'" :default-href="isEditMode ? '/projects/manage?tab=projects' : '/tabs/discover'" />

    <ion-content class="mobile-publish-content">
      <main v-if="loadingProject" class="mobile-publish-shell edit-loading-shell">
        <section class="edit-loading" role="status">
          <ion-spinner name="crescent" aria-hidden="true" />
          <span>正在读取企划内容…</span>
        </section>
      </main>

      <main v-else-if="loadError" class="mobile-publish-shell edit-loading-shell">
        <StatePanel
          tone="error"
          title="企划无法编辑"
          :description="loadError"
          action-label="重新加载"
          @action="loadProjectForEdit"
        />
      </main>

      <main v-else class="mobile-publish-shell">
        <section class="mobile-publish-intro">
          <span><BriefcaseBusiness :size="22" aria-hidden="true" /></span>
          <div>
            <h1>{{ isEditMode ? '让最新安排与摄影师看到的内容保持一致' : '把需求写清楚，更快收到合适方案' }}</h1>
            <p>{{ isEditMode ? '保存后会立即更新企划详情；草稿和过期企划也可以在这里补充后重新发布。' : '预算、日期和交付要求会帮助摄影师判断档期；发布后可在企划管理中继续修改或关闭。' }}</p>
          </div>
        </section>

        <section v-if="draftRestored && !isEditMode" class="publish-draft-note" role="status">
          <FileClock :size="19" aria-hidden="true" />
          <div>
            <strong>已恢复 {{ draftTime }} 保存的本机草稿</strong>
            <p>文字和选项已恢复，参考图片需要重新选择。</p>
          </div>
        </section>
        <section v-if="agentTask && !isEditMode" class="agent-source-note" role="status">已载入 Agent 整理的信息，可直接在此修改。</section>

        <form class="mobile-publish-form" novalidate @submit.prevent="submitProject(true)">
          <section class="publish-section">
            <header class="publish-section-heading">
              <span>1</span>
              <div><h2>需求概况</h2><p>先让摄影师快速判断是否适合响应。</p></div>
            </header>

            <div class="publish-field">
              <label for="project-title">企划标题 <span>必填</span></label>
              <input id="project-title" v-model.trim="form.title" class="publish-input" maxlength="120" placeholder="例如：周末港岛街拍人像" :disabled="submitting" :aria-invalid="Boolean(errors.title)" @blur="validateRequired('title')" />
              <p v-if="errors.title" class="publish-error" role="alert">{{ errors.title }}</p>
            </div>

            <div class="publish-field-grid">
              <div class="publish-field">
                <label for="project-category">拍摄类型 <span>必填</span></label>
                <select id="project-category" v-model="form.category" class="publish-select" :disabled="submitting">
                  <option value="portrait">人像写真</option>
                  <option value="wedding">婚礼跟拍</option>
                  <option value="family">家庭纪实</option>
                  <option value="commercial">商业拍摄</option>
                  <option value="event">活动记录</option>
                  <option value="product">产品摄影</option>
                  <option value="other">其他</option>
                </select>
              </div>
              <div class="publish-field">
                <label for="project-city">城市 <span>必填</span></label>
                <input id="project-city" v-model.trim="form.city" class="publish-input" maxlength="80" placeholder="例如：香港" :disabled="submitting" :aria-invalid="Boolean(errors.city)" @blur="validateRequired('city')" />
                <p v-if="errors.city" class="publish-error" role="alert">{{ errors.city }}</p>
              </div>
            </div>

            <div class="publish-field">
              <label>拍摄地点 <span>选填，可在地图上选择</span></label>
              <button type="button" class="location-preview pressable" :disabled="submitting" @click="showLocationPicker = true">
                <LocationMap
                  v-if="hasMapCoordinates"
                  :latitude="form.location_latitude ?? undefined"
                  :longitude="form.location_longitude ?? undefined"
                  aria-label="企划地点地图预览"
                />
                <div v-else class="location-preview-empty">
                  <MapPin :size="28" aria-hidden="true" />
                  <span>点击地图选择拍摄地点</span>
                </div>
              </button>
              <div class="location-input-wrap">
                <input
                  v-model.trim="form.location_text"
                  class="publish-input"
                  maxlength="255"
                  :placeholder="hasMapCoordinates ? '可补充更详细的地点说明' : '可搜索选择，或直接输入地点'"
                  :disabled="submitting"
                />
                <button
                  v-if="form.location_text || hasMapCoordinates"
                  type="button"
                  class="location-clear-btn pressable"
                  :disabled="submitting"
                  aria-label="清除地点"
                  @click="clearLocation"
                >
                  <X :size="18" aria-hidden="true" />
                </button>
              </div>
            </div>

            <LocationPickerModal v-model="showLocationPicker" :location="locationPickerValue" :city="form.city" @confirm="onLocationConfirm" />

            <div class="publish-field">
              <label for="project-tags">风格标签 <span>最多 12 个</span></label>
              <TagEditor id="project-tags" v-model="styleTags" input-id="project-tags-input" placeholder="例如：胶片、自然光、复古" :disabled="submitting" @limit="toastMessage = '最多添加 12 个风格标签。'" />
            </div>
          </section>

          <section class="publish-section">
            <header class="publish-section-heading">
              <span>2</span>
              <div><h2>时间与预算</h2><p>日期越明确，档期匹配越准确。</p></div>
            </header>

            <div class="publish-field-grid">
              <div class="publish-field">
                <label for="project-start">拍摄开始 <span>选填</span></label>
                <input id="project-start" v-model="form.shoot_date_start" type="datetime-local" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.shoot_date_start)" />
                <p v-if="errors.shoot_date_start" class="publish-error" role="alert">{{ errors.shoot_date_start }}</p>
              </div>
              <div class="publish-field">
                <label for="project-end">拍摄结束 <span>选填</span></label>
                <input id="project-end" v-model="form.shoot_date_end" type="datetime-local" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.shoot_date_end)" />
                <p v-if="errors.shoot_date_end" class="publish-error" role="alert">{{ errors.shoot_date_end }}</p>
              </div>
            </div>

            <div class="publish-field-grid">
              <div class="publish-field">
                <label for="project-duration">预计时长 <span>分钟</span></label>
                <input id="project-duration" v-model.number="form.duration_minutes" type="number" inputmode="numeric" min="30" step="30" class="publish-input" :disabled="submitting" />
              </div>
              <div class="publish-field">
                <label for="project-expiry">招募截止 <span>选填</span></label>
                <input id="project-expiry" v-model="form.expires_at" type="datetime-local" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.expires_at)" />
                <p v-if="errors.expires_at" class="publish-error" role="alert">{{ errors.expires_at }}</p>
              </div>
            </div>

            <div class="publish-field-grid">
              <div class="publish-field">
                <label for="project-budget-min">预算下限 <span>人民币元</span></label>
                <input id="project-budget-min" v-model.number="form.budget_min" type="number" inputmode="decimal" min="0" step="100" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.budget_min)" />
              </div>
              <div class="publish-field">
                <label for="project-budget-max">预算上限 <span>人民币元</span></label>
                <input id="project-budget-max" v-model.number="form.budget_max" type="number" inputmode="decimal" min="0" step="100" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.budget_max)" />
                <p v-if="errors.budget_max" class="publish-error" role="alert">{{ errors.budget_max }}</p>
              </div>
            </div>
          </section>

          <section class="publish-section">
            <header class="publish-section-heading">
              <span>3</span>
              <div><h2>需求与交付</h2><p>说明人数、用途、氛围和最终要拿到什么。</p></div>
            </header>

            <div class="publish-field">
              <label for="project-description">需求描述 <span>必填</span></label>
              <textarea id="project-description" v-model.trim="form.description" class="publish-textarea" rows="6" maxlength="2000" placeholder="拍摄人数、用途、服装、想要的氛围，以及必须避开的事项" :disabled="submitting" :aria-invalid="Boolean(errors.description)" @blur="validateRequired('description')" />
              <p v-if="errors.description" class="publish-error" role="alert">{{ errors.description }}</p>
              <p class="publish-help">{{ form.description.length }}/2000</p>
            </div>

            <div class="publish-field">
              <label for="project-deliverables">交付要求 <span>选填</span></label>
              <textarea id="project-deliverables" v-model.trim="form.deliverables" class="publish-textarea" rows="4" maxlength="1000" placeholder="例如：精修 30 张、底片全送，交付前先提供预览确认" :disabled="submitting" />
            </div>

            <div class="publish-field">
              <label for="project-visibility">可见范围</label>
              <select id="project-visibility" v-model="form.visibility" class="publish-select" :disabled="submitting">
                <option value="public">公开招募</option>
                <option value="invite_only">仅受邀摄影师可见</option>
              </select>
            </div>
          </section>

          <section class="publish-section">
            <header class="publish-section-heading">
              <span>4</span>
              <div><h2>参考图片</h2><p>选填；最多 18 张，用于说明构图、色调或服装方向。</p></div>
            </header>
            <div v-if="existingReferenceImages.length" class="existing-reference-grid" aria-label="企划当前参考图片">
              <article v-for="(url, index) in existingReferenceImages" :key="url">
                <img :src="resolveMediaUrl(url)" :alt="`当前参考图 ${index + 1}`" loading="lazy" />
                <button
                  type="button"
                  class="pressable"
                  :disabled="submitting"
                  :aria-label="`移除当前参考图 ${index + 1}`"
                  @click="removeExistingReference(index)"
                >
                  <X :size="18" aria-hidden="true" />
                </button>
              </article>
            </div>
            <PublishMediaPicker
              v-model:files="referenceFiles"
              input-id="project-reference-files"
              mode="image"
              :image-limit="remainingImageLimit"
              :hint="isEditMode ? `还可添加 ${remainingImageLimit} 张新图片` : ''"
              :disabled="submitting"
              @error="requestError = $event"
            />
          </section>

          <div v-if="requestError" class="publish-request-error" role="alert">
            <CircleAlert :size="19" aria-hidden="true" />{{ requestError }}
          </div>

          <div v-if="submitting" class="publish-progress" aria-live="polite">
            <div><i :style="{ '--progress': `${uploadProgress}%` }" /></div>
            <span>{{ progressText }}</span>
          </div>
        </form>
      </main>

      <ion-toast :is-open="Boolean(toastMessage)" :message="toastMessage" :duration="2600" position="bottom" @did-dismiss="toastMessage = ''" />
    </ion-content>

    <ion-footer v-if="!loadingProject && !loadError" class="mobile-publish-footer">
      <div class="mobile-publish-actions with-agent" :class="{ two: isEditMode && !canPublishEditedProject }">
        <button type="button" class="pressable" :disabled="submitting || agentPolishing" @click="submitProject(false)">
          <ion-spinner v-if="submitting && submitMode === 'draft'" name="crescent" aria-hidden="true" />
          <Save v-else :size="18" aria-hidden="true" />{{ isEditMode ? '保存修改' : '保存草稿' }}
        </button>
        <PublishAgentPolishButton
          content-type="project"
          :fields="projectPolishFields"
          :disabled="submitting"
          @busy-change="agentPolishing = $event"
          @error="requestError = $event"
          @polished="applyPolishedProject"
        />
        <button v-if="!isEditMode || canPublishEditedProject" type="button" class="pressable" :disabled="submitting || agentPolishing" @click="submitProject(true)">
          <ion-spinner v-if="submitting && submitMode === 'publish'" name="crescent" aria-hidden="true" />
          <Send v-else :size="18" aria-hidden="true" />{{ isEditMode && editingProject?.status === 'expired' ? '保存并重新发布' : '发布企划' }}
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonFooter, IonPage, IonSpinner, IonToast } from '@ionic/vue'
import { BriefcaseBusiness, CircleAlert, FileClock, MapPin, Save, Send, X } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import LocationMap from '@/components/location/LocationMap.vue'
import LocationPickerModal from '@/components/location/LocationPickerModal.vue'
import PublishMediaPicker from '@/components/PublishMediaPicker.vue'
import PublishAgentPolishButton from '@/components/PublishAgentPolishButton.vue'
import StatePanel from '@/components/StatePanel.vue'
import TagEditor from '@/components/TagEditor.vue'
import { getApiErrorMessage } from '@/api/client'
import { useAgentTaskHandoff } from '@/composables/useAgentTaskHandoff'
import { getProjectDetail } from '@/api/discovery'
import { publishProject, updateProject } from '@/api/projects'
import { createProject, uploadProjectImages } from '@/api/publishing'
import { useAuthStore } from '@/stores/auth'
import type { ProjectBrief } from '@/types/discovery'
import type { ProjectUpdatePayload } from '@/types/publishing'
import { resolveMediaUrl } from '@/utils/media'
import {
  clearPublishDraft,
  formatDraftTime,
  readPublishDraft,
  savePublishDraft,
  toLocalDateTimeInput,
  toOptionalIso,
} from '@/utils/publishing'

interface ProjectFormState {
  title: string
  description: string
  deliverables: string
  category: string
  city: string
  location_text: string
  location_name: string
  location_address: string
  location_latitude: number | null
  location_longitude: number | null
  location_place_id: string | null
  location_provider: string | null
  coordinate_system: string | null
  location_precision: string | null
  shoot_date_start: string
  shoot_date_end: string
  duration_minutes: number | ''
  budget_min: number | ''
  budget_max: number | ''
  expires_at: string
  visibility: 'public' | 'invite_only'
  styleTags: string[]
}

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const agentHandoff = useAgentTaskHandoff()
const agentTask = agentHandoff.task
const isEditMode = computed(() => route.name === 'project-edit')
const editingProject = ref<ProjectBrief | null>(null)
const existingReferenceImages = ref<string[]>([])
const remainingImageLimit = computed(() => Math.max(0, 18 - existingReferenceImages.value.length))
const canPublishEditedProject = computed(() => ['draft', 'expired'].includes(editingProject.value?.status || ''))
const loadingProject = ref(isEditMode.value)
const loadError = ref('')
const form = reactive<ProjectFormState>({
  title: '',
  description: '',
  deliverables: '',
  category: 'other',
  city: '',
  location_text: '',
  location_name: '',
  location_address: '',
  location_latitude: null,
  location_longitude: null,
  location_place_id: null,
  location_provider: null,
  coordinate_system: null,
  location_precision: null,
  shoot_date_start: '',
  shoot_date_end: '',
  duration_minutes: 120,
  budget_min: 800,
  budget_max: 1600,
  expires_at: '',
  visibility: 'public',
  styleTags: [],
})
const styleTags = ref<string[]>([])
const referenceFiles = ref<File[]>([])
const errors = reactive<Record<string, string>>({})
const requestError = ref('')
const submitting = ref(false)
const agentPolishing = ref(false)
const submitMode = ref<'draft' | 'publish'>('publish')
const uploadProgress = ref(0)
const progressText = ref('正在准备提交…')
const draftRestored = ref(false)
const draftTime = ref('')
const toastMessage = ref('')
const currentDraftId = ref('')
let draftTimer: number | null = null

const projectPolishFields = computed(() => ({
  title: form.title,
  description: form.description,
  deliverables: form.deliverables,
  city: form.city,
  location_text: form.location_text,
  style_tags: [...styleTags.value],
}))

function applyPolishedProject(fields: Record<string, unknown>, changedCount: number) {
  if (typeof fields.title === 'string') form.title = fields.title
  if (typeof fields.description === 'string') form.description = fields.description
  if (typeof fields.deliverables === 'string') form.deliverables = fields.deliverables
  if (typeof fields.city === 'string') form.city = fields.city
  if (typeof fields.location_text === 'string') form.location_text = fields.location_text
  if (Array.isArray(fields.style_tags)) styleTags.value = fields.style_tags.map(String).slice(0, 12)
  requestError.value = ''
  toastMessage.value = changedCount ? `Agent 已润色 ${changedCount} 项文字内容。` : '当前文字已经很清晰，无需调整。'
}

// 地点选择器
const showLocationPicker = ref(false)
const hasMapCoordinates = computed(() => form.location_latitude != null && form.location_longitude != null && Number.isFinite(form.location_latitude) && Number.isFinite(form.location_longitude))
const locationDisplayName = computed(() => form.location_name || form.location_text || '')
const locationDisplayAddress = computed(() => form.location_address || '')
const locationPickerValue = computed(() => ({
  name: form.location_name,
  address: form.location_address,
  latitude: form.location_latitude,
  longitude: form.location_longitude,
  place_id: form.location_place_id,
  text: form.location_text,
}))

function onLocationConfirm(location: {
  name: string
  address: string
  latitude: number
  longitude: number
  place_id: string | null
  provider: string
  coordinate_system: string
  precision: string
}) {
  form.location_name = location.name
  form.location_address = location.address
  form.location_latitude = location.latitude
  form.location_longitude = location.longitude
  form.location_place_id = location.place_id
  form.location_provider = location.provider
  form.coordinate_system = location.coordinate_system
  form.location_precision = location.precision
  // 选定地点后将名称填入文字框供修改
  form.location_text = location.name || location.address || ''
}

function clearLocation() {
  form.location_text = ''
  form.location_name = ''
  form.location_address = ''
  form.location_latitude = null
  form.location_longitude = null
  form.location_place_id = null
  form.location_provider = null
  form.coordinate_system = null
  form.location_precision = null
}

function projectIdFromRoute() {
  const value = Number(route.params.projectId)
  return Number.isInteger(value) && value > 0 ? value : null
}

function deliverablesText(value: unknown) {
  if (typeof value === 'string') return value
  if (!value) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function hydrateProject(project: ProjectBrief) {
  editingProject.value = project
  Object.assign(form, {
    title: project.title || '',
    description: project.description || '',
    deliverables: deliverablesText(project.deliverables),
    category: project.category || 'other',
    city: project.city || '',
    location_text: project.location_text || '',
    location_name: project.location_name || '',
    location_address: project.location_address || '',
    location_latitude: project.location_latitude ?? null,
    location_longitude: project.location_longitude ?? null,
    location_place_id: project.location_place_id || null,
    location_provider: project.location_provider || null,
    coordinate_system: project.coordinate_system || null,
    location_precision: project.location_precision || null,
    shoot_date_start: toLocalDateTimeInput(project.shoot_date_start),
    shoot_date_end: toLocalDateTimeInput(project.shoot_date_end),
    duration_minutes: project.duration_minutes ?? '',
    budget_min: project.budget_min ?? '',
    budget_max: project.budget_max ?? '',
    expires_at: toLocalDateTimeInput(project.expires_at),
    visibility: project.visibility === 'invite_only' ? 'invite_only' : 'public',
    styleTags: Array.isArray(project.style_tags) ? project.style_tags : [],
  } satisfies ProjectFormState)
  styleTags.value = Array.isArray(project.style_tags) ? [...project.style_tags] : []
  existingReferenceImages.value = Array.isArray(project.reference_images)
    ? project.reference_images.filter(Boolean)
    : []
  referenceFiles.value = []
}

async function loadProjectForEdit() {
  if (!isEditMode.value) return
  const projectId = projectIdFromRoute()
  if (!projectId) {
    loadingProject.value = false
    loadError.value = '企划编号无效，请从“企划与应邀”重新进入。'
    return
  }

  loadingProject.value = true
  loadError.value = ''
  try {
    await auth.initialize()
    const payload = await getProjectDetail(projectId)
    if (!auth.user || payload.project.customer_id !== auth.user.id) {
      loadError.value = '只有企划发布者可以编辑这份拍摄需求。'
      return
    }
    if (!['draft', 'open', 'expired'].includes(payload.project.status)) {
      loadError.value = '这份企划当前已不能编辑，请返回管理页查看详情。'
      return
    }
    hydrateProject(payload.project)
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    loadingProject.value = false
  }
}

function removeExistingReference(index: number) {
  existingReferenceImages.value = existingReferenceImages.value.filter((_, itemIndex) => itemIndex !== index)
}

function validateRequired(field: 'title' | 'city' | 'description') {
  const labels = { title: '请填写企划标题。', city: '请填写拍摄城市。', description: '请填写需求描述。' }
  errors[field] = form[field].trim() ? '' : labels[field]
  return !errors[field]
}

function validateForm(publish = false) {
  Object.keys(errors).forEach((key) => { errors[key] = '' })
  const validRequired = [validateRequired('title'), validateRequired('city'), validateRequired('description')].every(Boolean)
  const start = form.shoot_date_start ? new Date(form.shoot_date_start) : null
  const end = form.shoot_date_end ? new Date(form.shoot_date_end) : null
  const expiry = form.expires_at ? new Date(form.expires_at) : null
  const allowPastValues = isEditMode.value && editingProject.value?.status === 'expired' && !publish
  if (end && !start) errors.shoot_date_start = '填写结束时间前，请先选择开始时间。'
  if (start && end && end <= start) errors.shoot_date_end = '结束时间必须晚于开始时间。'
  if (start && expiry && expiry >= start) errors.expires_at = '招募截止时间必须早于拍摄开始时间。'
  if (!allowPastValues && start && start.getTime() <= Date.now()) errors.shoot_date_start = '拍摄开始时间需要晚于当前时间。'
  if (!allowPastValues && end && end.getTime() <= Date.now()) errors.shoot_date_end = '拍摄结束时间需要晚于当前时间。'
  if (!allowPastValues && expiry && expiry.getTime() <= Date.now()) errors.expires_at = '招募截止时间需要晚于当前时间。'
  if (form.budget_min !== '' && form.budget_max !== '' && Number(form.budget_min) > Number(form.budget_max)) {
    errors.budget_max = '预算上限不能低于预算下限。'
  }
  const firstError = Object.entries(errors).find(([, message]) => message)
  if (firstError) document.getElementById(`project-${firstError[0].replaceAll('_', '-')}`)?.focus()
  return validRequired && !firstError
}

function buildProjectPayload(referenceImages: string[]): ProjectUpdatePayload {
  return {
    title: form.title.trim(),
    description: form.description.trim(),
    category: form.category,
    style_tags: styleTags.value,
    city: form.city.trim(),
    location_text: form.location_text.trim() || null,
    location_name: form.location_name.trim() || null,
    location_address: form.location_address.trim() || null,
    location_latitude: form.location_latitude,
    location_longitude: form.location_longitude,
    location_place_id: form.location_place_id,
    location_provider: form.location_provider,
    coordinate_system: form.coordinate_system,
    location_precision: form.location_precision,
    shoot_date_start: toOptionalIso(form.shoot_date_start),
    shoot_date_end: toOptionalIso(form.shoot_date_end),
    duration_minutes: form.duration_minutes === '' ? null : Number(form.duration_minutes),
    budget_min: form.budget_min === '' ? null : Number(form.budget_min),
    budget_max: form.budget_max === '' ? null : Number(form.budget_max),
    deliverables: form.deliverables.trim() || null,
    reference_images: referenceImages,
    visibility: form.visibility,
    expires_at: toOptionalIso(form.expires_at),
  }
}

async function submitProject(publish: boolean) {
  if (submitting.value || !validateForm(publish)) return
  submitting.value = true
  submitMode.value = publish ? 'publish' : 'draft'
  requestError.value = ''
  uploadProgress.value = referenceFiles.value.length ? 2 : 72
  progressText.value = referenceFiles.value.length ? '正在上传参考图片…' : '正在保存企划…'
  try {
    const uploadedReferenceImages = await uploadProjectImages(referenceFiles.value, (percent) => {
      uploadProgress.value = Math.max(2, Math.round(percent * 0.72))
    })
    const referenceImages = [...existingReferenceImages.value, ...uploadedReferenceImages]
    uploadProgress.value = 82
    progressText.value = publish ? '正在发布企划…' : isEditMode.value ? '正在保存修改…' : '正在保存服务器草稿…'

    let project: ProjectBrief
    if (isEditMode.value) {
      const projectId = projectIdFromRoute()
      if (!projectId) throw new Error('企划编号无效，请返回管理页重试。')
      project = await updateProject(projectId, buildProjectPayload(referenceImages))
      if (publish && project.status !== 'open') project = await publishProject(projectId)
    } else {
      project = await createProject({
        ...buildProjectPayload(referenceImages),
        publish,
      })
    }
    uploadProgress.value = 100
    if (!isEditMode.value) {
      if (currentDraftId.value) clearPublishDraft('project', currentDraftId.value)
      else clearPublishDraft('project')
    }
    if (agentTask.value) await agentHandoff.complete({ project_id: project.id })
    await router.replace({ name: 'project-detail', params: { projectId: project.id } })
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

function restoreDraft() {
  if (isEditMode.value || route.query.agentTaskId) return
  const draftId = route.query.draftId as string | undefined
  const draft = readPublishDraft<ProjectFormState>('project', draftId)
  if (!draft) return
  Object.assign(form, draft.value)
  styleTags.value = Array.isArray(draft.value.styleTags) ? draft.value.styleTags : []
  draftRestored.value = true
  draftTime.value = formatDraftTime(draft.updatedAt)
  currentDraftId.value = draft.id
}

function taskOperation(field: string, value: unknown) {
  const empty = value === '' || value === null || value === undefined || (Array.isArray(value) && !value.length)
  return empty ? { field, op: 'clear' as const } : { field, op: 'set' as const, value }
}

function projectTaskOperations() {
  return [
    taskOperation('title', form.title.trim()),
    taskOperation('description', form.description.trim()),
    taskOperation('deliverables', form.deliverables.trim()),
    taskOperation('category', form.category),
    taskOperation('city', form.city.trim()),
    taskOperation('location_text', form.location_text.trim()),
    taskOperation('shoot_date_start', toOptionalIso(form.shoot_date_start)),
    taskOperation('shoot_date_end', toOptionalIso(form.shoot_date_end)),
    taskOperation('duration_minutes', form.duration_minutes === '' ? null : Number(form.duration_minutes)),
    taskOperation('budget_min', form.budget_min === '' ? null : Number(form.budget_min)),
    taskOperation('budget_max', form.budget_max === '' ? null : Number(form.budget_max)),
    taskOperation('expires_at', toOptionalIso(form.expires_at)),
    taskOperation('visibility', form.visibility),
    taskOperation('style_tags', [...styleTags.value]),
  ]
}

function scheduleDraftSave() {
  if (isEditMode.value) return
  if (draftTimer !== null) window.clearTimeout(draftTimer)
  draftTimer = window.setTimeout(() => {
    if (route.query.agentTaskId) {
      void agentHandoff.saveOperations(projectTaskOperations()).catch((error) => {
        requestError.value = getApiErrorMessage(error)
      })
    } else {
      const id = savePublishDraft('project', { ...form, styleTags: [...styleTags.value] }, currentDraftId.value)
      currentDraftId.value = id
    }
  }, 450)
}

function hydrateAgentProject(fields: Record<string, unknown>) {
  Object.assign(form, {
    title: String(fields.title || ''), description: String(fields.description || ''),
    deliverables: deliverablesText(fields.deliverables), category: String(fields.category || 'other'),
    city: String(fields.city || ''), location_text: String(fields.location_text || ''),
    location_name: String(fields.location_name || ''), location_address: String(fields.location_address || ''),
    location_latitude: typeof fields.location_latitude === 'number' ? fields.location_latitude : null,
    location_longitude: typeof fields.location_longitude === 'number' ? fields.location_longitude : null,
    location_place_id: fields.location_place_id ? String(fields.location_place_id) : null,
    location_provider: fields.location_provider ? String(fields.location_provider) : null,
    coordinate_system: fields.coordinate_system ? String(fields.coordinate_system) : null,
    location_precision: fields.location_precision ? String(fields.location_precision) : null,
    shoot_date_start: fields.shoot_date_start ? toLocalDateTimeInput(String(fields.shoot_date_start)) : '',
    shoot_date_end: fields.shoot_date_end ? toLocalDateTimeInput(String(fields.shoot_date_end)) : '',
    duration_minutes: typeof fields.duration_minutes === 'number' ? fields.duration_minutes : '',
    budget_min: typeof fields.budget_min === 'number' ? fields.budget_min : '',
    budget_max: typeof fields.budget_max === 'number' ? fields.budget_max : '',
    expires_at: fields.expires_at ? toLocalDateTimeInput(String(fields.expires_at)) : '',
    visibility: fields.visibility === 'invite_only' ? 'invite_only' : 'public',
  } satisfies Omit<ProjectFormState, 'styleTags'>)
  styleTags.value = Array.isArray(fields.style_tags) ? fields.style_tags.map(String) : []
}

onMounted(async () => {
  if (isEditMode.value) {
    await loadProjectForEdit()
    return
  }
  const task = await agentHandoff.load('create_project')
  if (task) hydrateAgentProject(task.fields)
  else restoreDraft()
})
watch(() => ({ ...form, styleTags: [...styleTags.value] }), scheduleDraftSave, { deep: true })
onUnmounted(() => { if (draftTimer !== null) window.clearTimeout(draftTimer) })
</script>

<style scoped>
/* 地点选择器 */
.location-preview {
  position: relative;
  display: block;
  width: 100%;
  height: 140px;
  padding: 0;
  overflow: hidden;
  border: 0;
  border-radius: var(--radius-md);
  background: var(--paper);
  box-shadow: var(--neu-inset);
  cursor: pointer;
  text-align: left;
}
.location-preview:disabled { opacity: .55; cursor: not-allowed; }

.location-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  height: 100%;
  color: var(--ink-tertiary);
  background: var(--paper);
  box-shadow: var(--neu-inset);
}

/* 地点说明输入框 + 清除按钮 */
.location-input-wrap {
  position: relative;
  display: block;
}
.location-clear-btn {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-tertiary);
}
.location-clear-btn:active { background: var(--paper); box-shadow: var(--neu-inset); }
.location-clear-btn:disabled { opacity: .35; }
.location-input-wrap .publish-input {
  padding-right: 48px;
}

.edit-loading-shell { display: grid; min-height: 55vh; align-content: center; }
.edit-loading { display: flex; min-height: 180px; align-items: center; justify-content: center; gap: var(--space-3); border: 0; border-radius: var(--radius-lg); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); font-size: var(--text-sm); }
.edit-loading ion-spinner { width: 22px; height: 22px; color: var(--brand); }
.existing-reference-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin-bottom: var(--space-3); }
.existing-reference-grid article { position: relative; overflow: hidden; aspect-ratio: 1 / 1; border: 0; border-radius: var(--radius-md); background: var(--ink); box-shadow: var(--neu-raise); }
.existing-reference-grid img { width: 100%; height: 100%; object-fit: cover; }
.existing-reference-grid button { position: absolute; top: 4px; right: 4px; display: grid; width: 44px; height: 44px; place-items: center; border: 0; border-radius: 50%; background: rgba(26, 26, 26, .68); color: var(--white); }
.existing-reference-grid button:disabled { opacity: .55; }
@media (min-width: 640px) { .existing-reference-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
