<template>
  <div class="page-container">
    <header class="page-header">
      <button class="back-btn" type="button" @click="router.back()">
        <span aria-hidden="true">&lt;</span>
        <span>返回</span>
      </button>
      <h1 class="page-title">{{ isEditMode ? '编辑拍摄企划' : '发布拍摄企划' }}</h1>
    </header>

    <section class="media-section">
      <div class="section-head">
        <span class="media-label">{{ referenceCount }}/{{ MAX_REFERENCE_COUNT }}</span>
      </div>

      <div class="media-rail-wrap">
        <div ref="mediaRailRef" class="media-rail" @wheel.prevent="handleMediaWheel">
          <div v-for="(item, index) in previewItems" :key="item.id" class="media-card preview-card">
            <img :src="item.url" alt="" class="preview-media" />
            <button class="media-remove-btn" type="button" title="移除" aria-label="移除参考图" @click="removeReference(index)">
              <el-icon><Close /></el-icon>
            </button>
            <span class="media-index">{{ index + 1 }}</span>
          </div>

          <el-upload
            v-if="canAddMore"
            ref="refUploadRef"
            v-model:file-list="refFileList"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleRefChange"
            :on-remove="handleRefRemove"
            :on-exceed="handleExceed"
            :limit="MAX_REFERENCE_COUNT"
            accept="image/*"
            multiple
            class="add-upload"
          >
            <button class="media-card media-add-card" type="button">
              <el-icon><Plus /></el-icon>
              <span>添加参考图</span>
            </button>
          </el-upload>
        </div>
      </div>
    </section>

    <el-form ref="formRef" :model="form" :rules="rules" class="project-form">
      <section class="form-section">
        <div class="form-field">
          <label class="form-label" for="project-title">标题</label>
          <el-form-item prop="title">
            <el-input id="project-title" v-model="form.title" maxlength="120" show-word-limit placeholder="例如：周末港岛街拍人像" size="large" />
          </el-form-item>
        </div>

        <div class="form-field">
          <label class="form-label" for="project-city">城市</label>
          <el-form-item prop="city">
            <el-input id="project-city" v-model="form.city" placeholder="例如：香港" size="large" />
          </el-form-item>
        </div>

        <div class="form-field location-form-field">
          <span class="form-label">地点</span>
          <el-form-item>
            <ProjectLocationField v-model="locationValue" :city="form.city" />
          </el-form-item>
        </div>

        <div class="form-row">
          <div class="form-field form-field-compact">
            <label class="form-label">开始时间</label>
            <el-form-item>
              <el-date-picker v-model="form.shoot_date_start" type="datetime" placeholder="可选" size="large" />
            </el-form-item>
          </div>

          <div class="form-field form-field-compact">
            <label class="form-label">结束时间</label>
            <el-form-item>
              <el-date-picker v-model="form.shoot_date_end" type="datetime" placeholder="可选" size="large" />
            </el-form-item>
          </div>
        </div>

        <div class="form-row">
          <div class="form-field form-field-compact">
            <label class="form-label" for="project-duration">服务时长</label>
            <el-form-item>
              <el-input-number id="project-duration" v-model="form.duration_minutes" :min="30" :step="30" size="large" />
            </el-form-item>
          </div>

          <div class="form-field form-field-compact">
            <label class="form-label">招募截止</label>
            <el-form-item>
              <el-date-picker v-model="form.expires_at" type="datetime" placeholder="可选" size="large" />
            </el-form-item>
          </div>
        </div>

        <div class="form-row">
          <div class="form-field form-field-compact">
            <label class="form-label" for="project-budget-min">预算下限</label>
            <el-form-item>
              <el-input-number id="project-budget-min" v-model="form.budget_min" :min="0" :step="100" size="large" />
            </el-form-item>
          </div>

          <div class="form-field form-field-compact">
            <label class="form-label" for="project-budget-max">预算上限</label>
            <el-form-item>
              <el-input-number id="project-budget-max" v-model="form.budget_max" :min="0" :step="100" size="large" />
            </el-form-item>
          </div>
        </div>

        <div class="form-field">
          <label class="form-label">风格类型</label>
          <el-form-item>
            <TagInput v-model="styleTags" placeholder="输入风格后按回车，例如：胶片、自然光、复古" />
          </el-form-item>
        </div>

        <div class="form-field">
          <label class="form-label" for="project-description">需求描述</label>
          <el-form-item prop="description">
            <el-input
              id="project-description"
              v-model="form.description"
              type="textarea"
              :rows="5"
              maxlength="2000"
              show-word-limit
              resize="none"
              placeholder="拍摄人数、用途、服装、想要的氛围、必须避开的事项"
            />
          </el-form-item>
        </div>

        <div class="form-field">
          <label class="form-label" for="project-deliverables">交付要求</label>
          <el-form-item>
            <el-input
              id="project-deliverables"
              v-model="form.deliverables"
              type="textarea"
              :rows="3"
              maxlength="1000"
              show-word-limit
              resize="none"
              placeholder="例如：精修 30 张，底片全送；需要 1 条 30 秒短视频；交付前先给预览确认"
            />
          </el-form-item>
        </div>
      </section>

      <section class="form-actions-panel">
        <div class="form-actions-row">
          <el-button v-if="!isEditMode || projectStatus !== 'open'" size="large" class="btn-secondary" :icon="FolderAdd" @click="submit(false)" :loading="submitting">{{ isEditMode ? '保存修改' : '保存草稿' }}</el-button>
          <el-button size="large" type="primary" class="btn-primary" :icon="Check" @click="submit(true)" :loading="submitting">{{ primaryActionLabel }}</el-button>
        </div>
      </section>
    </el-form>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, FolderPlus as FolderAdd, Plus, X as Close } from 'lucide-vue-next'
import TagInput from '../components/TagInput.vue'
import ProjectLocationField from '../components/location/ProjectLocationField.vue'
import { createProject, getProjectDetail, publishProject, updateProject } from '../api/project'
import api from '../utils/api'

const route = useRoute()
const router = useRouter()
const formRef = ref(null)
const submitting = ref(false)
const styleTags = ref([])
const refFileList = ref([])
const refUploadRef = ref(null)
const mediaRailRef = ref(null)
const previewItems = ref([])
const existingRefUrls = ref([])
const uploadedRefUrls = ref([])
const MAX_REFERENCE_COUNT = 18
const isEditMode = computed(() => Boolean(route.params.projectId))
const projectId = computed(() => Number(route.params.projectId))
const projectStatus = ref('')
const primaryActionLabel = computed(() => {
  if (!isEditMode.value) return '发布企划'
  if (projectStatus.value === 'open') return '保存修改'
  if (projectStatus.value === 'expired') return '重新发布'
  return '发布企划'
})

const form = reactive({
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
})

const locationValue = computed({
  get: () => ({
    text: form.location_text,
    name: form.location_name,
    address: form.location_address,
    latitude: form.location_latitude == null ? null : Number(form.location_latitude),
    longitude: form.location_longitude == null ? null : Number(form.location_longitude),
    place_id: form.location_place_id,
    provider: form.location_provider,
    coordinate_system: form.coordinate_system,
    precision: form.location_precision,
  }),
  set: (location) => {
    form.location_text = location.text || ''
    form.location_name = location.name || ''
    form.location_address = location.address || ''
    form.location_latitude = location.latitude ?? null
    form.location_longitude = location.longitude ?? null
    form.location_place_id = location.place_id || null
    form.location_provider = location.provider || null
    form.coordinate_system = location.coordinate_system || null
    form.location_precision = location.precision || null
  },
})

const rules = {
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  city: [{ required: true, message: '请填写城市', trigger: 'blur' }],
  description: [{ required: true, message: '请填写需求描述', trigger: 'blur' }],
}

const referenceCount = computed(() => existingRefUrls.value.length + refFileList.value.length)
const canAddMore = computed(() => referenceCount.value < MAX_REFERENCE_COUNT)

const getFileKey = (file, index) => `${file.name}-${file.size}-${file.lastModified || 0}-${index}`

const revokePreviewItems = () => {
  previewItems.value.forEach((item) => {
    if (item.isObjectUrl && item.url) URL.revokeObjectURL(item.url)
  })
}

const syncPreviewItems = () => {
  revokePreviewItems()
  const existingItems = existingRefUrls.value.map((url, index) => ({
    id: `existing-${index}-${url}`,
    name: url,
    url,
    isObjectUrl: false,
  }))
  const uploadItems = refFileList.value
    .map((item) => item.raw)
    .filter(Boolean)
    .map((file, index) => ({
      id: getFileKey(file, index),
      name: file.name,
      url: URL.createObjectURL(file),
      isObjectUrl: true,
    }))
  previewItems.value = [...existingItems, ...uploadItems]
}

const handleRefChange = (_uploadFile, uploadFiles) => {
  const remaining = Math.max(MAX_REFERENCE_COUNT - existingRefUrls.value.length, 0)
  refFileList.value = uploadFiles.slice(0, remaining)
  syncPreviewItems()
}

const handleRefRemove = (_uploadFile, uploadFiles) => {
  refFileList.value = uploadFiles
  syncPreviewItems()
}

const removeReference = (index) => {
  if (index < existingRefUrls.value.length) {
    existingRefUrls.value = existingRefUrls.value.filter((_, itemIndex) => itemIndex !== index)
  } else {
    const uploadIndex = index - existingRefUrls.value.length
    refFileList.value = refFileList.value.filter((_, itemIndex) => itemIndex !== uploadIndex)
  }
  syncPreviewItems()
}

const handleExceed = () => {
  ElMessage.warning(`最多上传 ${MAX_REFERENCE_COUNT} 张参考图`)
}

const handleMediaWheel = (event) => {
  if (!mediaRailRef.value) return
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  mediaRailRef.value.scrollLeft += delta
}

const toIso = (value) => {
  if (!value) return null
  return value instanceof Date ? value.toISOString() : value
}

const buildPayload = (publish) => ({
  ...form,
  shoot_date_start: toIso(form.shoot_date_start),
  shoot_date_end: toIso(form.shoot_date_end),
  expires_at: toIso(form.expires_at),
  style_tags: styleTags.value,
  deliverables: form.deliverables.trim() || null,
  publish,
  reference_images: [...existingRefUrls.value, ...uploadedRefUrls.value],
})

const toDateValue = (value) => value ? new Date(value) : ''

const compactAIText = (value, maxLength = 500) => {
  if (!value) return ''
  return String(value).replace(/\s+/g, ' ').trim().slice(0, maxLength)
}

const formatAIBudget = () => {
  if (form.budget_min && form.budget_max) return `¥${form.budget_min} - ¥${form.budget_max}`
  if (form.budget_min) return `¥${form.budget_min} 起`
  if (form.budget_max) return `¥${form.budget_max} 内`
  return ''
}

const emitAIProjectDraftContext = () => {
  const detail = {
    routePath: route.fullPath,
    quickPrompts: ['帮我优化需求', '检查预算和时间是否清晰', '把企划描述写得更吸引摄影师'],
    context: {
      route_name: route.name || '',
      route_path: route.fullPath,
      resource_type: 'project_draft',
      resource_id: isEditMode.value ? String(projectId.value) : '',
      title: compactAIText(form.title || (isEditMode.value ? '正在编辑拍摄企划' : '正在发布拍摄企划'), 120),
      description: compactAIText(form.description),
      styles: styleTags.value,
      city: compactAIText(form.city, 80),
      location: compactAIText(form.location_text, 120),
      budget_label: formatAIBudget(),
      date_label: compactAIText(form.shoot_date_start),
      duration: form.duration_minutes,
      current_object: {
        deliverables: compactAIText(form.deliverables),
        reference_image_count: referenceCount.value,
        expires_at: compactAIText(form.expires_at),
      },
      search_text: compactAIText([
        form.title,
        form.description,
        form.deliverables,
        form.city,
        form.location_text,
        styleTags.value.join(' '),
        formatAIBudget(),
      ].filter(Boolean).join(' '), 1400),
    },
  }
  window.__aiPageContext = detail
  window.dispatchEvent(new CustomEvent('ai-context:update', { detail }))
}

const hydrateForm = (project) => {
  projectStatus.value = project.status || ''
  form.title = project.title || ''
  form.description = project.description || ''
  form.deliverables = typeof project.deliverables === 'string' ? project.deliverables : ''
  form.category = project.category || 'other'
  form.city = project.city || ''
  form.location_text = project.location_text || ''
  form.location_name = project.location_name || ''
  form.location_address = project.location_address || ''
  form.location_latitude = project.location_latitude == null ? null : Number(project.location_latitude)
  form.location_longitude = project.location_longitude == null ? null : Number(project.location_longitude)
  form.location_place_id = project.location_place_id || null
  form.location_provider = project.location_provider || null
  form.coordinate_system = project.coordinate_system || null
  form.location_precision = project.location_precision || null
  form.shoot_date_start = toDateValue(project.shoot_date_start)
  form.shoot_date_end = toDateValue(project.shoot_date_end)
  form.duration_minutes = project.duration_minutes || 120
  form.budget_min = project.budget_min ?? 800
  form.budget_max = project.budget_max ?? 1600
  form.expires_at = toDateValue(project.expires_at)
  form.visibility = project.visibility || 'public'
  styleTags.value = project.style_tags || []
  existingRefUrls.value = project.reference_images || []
  syncPreviewItems()
}

const fetchProjectForEdit = async () => {
  if (!isEditMode.value) return
  submitting.value = true
  try {
    const res = await getProjectDetail(projectId.value)
    hydrateForm(res.data.project)
  } finally {
    submitting.value = false
  }
}

const submit = async (publish) => {
  await formRef.value?.validate()
  if (form.budget_min && form.budget_max && form.budget_min > form.budget_max) {
    ElMessage.warning('预算下限不能高于预算上限')
    return
  }
  if (form.expires_at && form.shoot_date_start && new Date(form.expires_at) >= new Date(form.shoot_date_start)) {
    ElMessage.warning('招募截止时间必须早于拍摄开始时间')
    return
  }

  submitting.value = true
  try {
    uploadedRefUrls.value = []
    // 先上传参考图
    const files = refFileList.value.filter(f => f.raw)
    if (files.length > 0) {
      const fd = new FormData()
      files.forEach(f => fd.append('files', f.raw))
      const uploadRes = await api.post('/projects/upload-images', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      uploadedRefUrls.value = uploadRes.data.urls
    }

    const payload = buildPayload(publish)
    let res
    let didPublish = false
    if (isEditMode.value) {
      const updatePayload = { ...payload }
      delete updatePayload.publish
      res = await updateProject(projectId.value, updatePayload)
      const needsPublish = publish && ['draft', 'expired'].includes(projectStatus.value)
      if (needsPublish) {
        res = await publishProject(projectId.value)
        didPublish = true
      }
      projectStatus.value = res.data.status || projectStatus.value
    } else {
      res = await createProject(payload)
    }
    const successMessage = isEditMode.value
      ? (didPublish ? '企划已发布' : '企划已更新')
      : (publish ? '企划已发布' : '草稿已保存')
    ElMessage.success(successMessage)
    router.push(`/projects/${res.data.id}`)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  // 两种角色都可发布企划
  fetchProjectForEdit()
  emitAIProjectDraftContext()
})

onUnmounted(() => {
  revokePreviewItems()
  if (window.__aiPageContext?.routePath === route.fullPath) {
    window.__aiPageContext = null
  }
})

watch(
  () => [
    form.title,
    form.description,
    form.deliverables,
    form.city,
    form.location_text,
    form.location_latitude,
    form.location_longitude,
    form.shoot_date_start,
    form.duration_minutes,
    form.budget_min,
    form.budget_max,
    form.expires_at,
    styleTags.value.join('|'),
    referenceCount.value,
  ],
  emitAIProjectDraftContext,
)
</script>

<style scoped>
.page-container {
  box-sizing: border-box;
  width: min(1120px, calc(100vw - 48px));
  margin: 28px auto 56px;
  color: var(--color-ink);
  font-family: var(--font-sans);
}

.page-header {
  display: flex;
  align-items: center;
  gap: 28px;
  margin-bottom: 26px;
}

.back-btn {
  appearance: none;
  border: 0;
  background: transparent;
  color: var(--color-ink-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: inherit;
  font-size: 15px;
  padding: var(--space-2) 0;
  transition: color 0.2s;
}

.back-btn:hover {
  color: var(--color-brand);
}

.page-title {
  font-size: var(--text-4xl);
  line-height: 1.2;
  font-weight: 800;
  margin: 0;
}

.form-section,
.form-actions-panel {
  box-sizing: border-box;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.media-section {
  padding: 4px 0 8px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-4);
  margin-bottom: 10px;
}

.media-label {
  font-size: var(--text-sm);
  color: var(--color-ink-secondary);
  white-space: nowrap;
}

.media-rail-wrap {
  position: relative;
  overflow: hidden;
}

.media-rail-wrap::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 88px;
  pointer-events: none;
  background: linear-gradient(90deg, rgba(250, 247, 242, 0), var(--color-paper) 82%);
}

.media-rail {
  width: 100%;
  display: flex;
  gap: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 88px 8px 2px;
  scroll-behavior: smooth;
  scrollbar-width: thin;
}

.media-card {
  position: relative;
  flex: 0 0 auto;
  width: clamp(112px, 13vw, 148px);
  aspect-ratio: 1 / 1;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-paper);
  border: var(--border-default);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.media-remove-btn {
  appearance: none;
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  color: var(--color-paper-light);
  background: rgba(26, 26, 26, 0.52);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}

.media-remove-btn:hover {
  background: var(--color-danger);
}

.media-index {
  position: absolute;
  left: var(--space-2);
  bottom: var(--space-2);
  min-width: 26px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(26, 26, 26, 0.52);
  color: var(--color-paper-light);
  font-size: var(--text-xs);
  line-height: 22px;
  text-align: center;
}

.add-upload {
  flex: 0 0 auto;
}

.media-add-card {
  appearance: none;
  cursor: pointer;
  color: var(--color-brand);
  border: 1px dashed var(--color-border);
  background: var(--color-paper-light);
  flex-direction: column;
  gap: var(--space-2);
  font-size: 0.875rem;
  font-weight: 600;
  transition: border-color 0.2s, background 0.2s;
}

.media-add-card .el-icon {
  font-size: 28px;
}

.media-add-card:hover {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}

.form-section {
  margin-top: var(--space-2);
  padding: 28px;
  display: grid;
  gap: 22px;
}

.form-field {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.form-field-compact {
  grid-template-columns: 92px minmax(0, 1fr);
}

.form-label {
  padding-top: 9px;
  color: var(--color-ink-secondary);
  font-size: 15px;
  font-weight: 600;
}

.project-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.location-form-field :deep(.el-form-item__content) {
  display: block;
}

.project-form :deep(.el-date-editor.el-input),
.project-form :deep(.el-input-number),
.project-form :deep(.el-input-number .el-input__wrapper) {
  width: 100%;
}

.form-actions-panel {
  margin-top: 18px;
  padding: 22px 28px;
}

.form-actions-row {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.btn-primary {
  min-width: 160px;
  font-weight: 700;
}

.btn-secondary {
  min-width: 140px;
}

@media (max-width: 700px) {
  .page-container {
    width: min(100% - 24px, 1120px);
    margin-top: 18px;
  }

  .page-header {
    gap: var(--space-4);
  }

  .page-title {
    font-size: 26px;
  }

  .media-section,
  .form-section,
  .form-actions-panel {
    padding: 18px;
  }

  .media-section {
    padding-left: 0;
    padding-right: 0;
  }

  .media-card {
    width: 108px;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  .form-field,
  .form-field-compact {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }

  .form-label {
    padding-top: 0;
  }

  .form-actions-row {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
</style>
