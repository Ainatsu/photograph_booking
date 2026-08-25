<template>
  <div class="page-container" v-loading="loading">
    <header class="page-header">
      <button class="back-btn" type="button" @click="goBack">
        <span aria-hidden="true">&lt;</span>
        <span>返回</span>
      </button>
      <div>
        <h1 class="page-title">{{ myApplication ? '更新应邀方案' : '提交应邀方案' }}</h1>
        <p class="page-subtitle" v-if="project">{{ project.title }}</p>
      </div>
    </header>

    <section class="media-section">
      <div class="section-head">
        <span class="media-label">{{ previewItems.length }}/{{ MAX_PORTFOLIO_COUNT }}</span>
      </div>

      <div class="media-rail-wrap">
        <div ref="mediaRailRef" class="media-rail" @wheel.prevent="handleMediaWheel">
          <div v-for="(item, index) in previewItems" :key="item.id" class="media-card preview-card">
            <img :src="item.url" alt="" class="preview-media" />
            <button class="media-remove-btn" type="button" title="移除" aria-label="移除作品" @click="removePortfolio(index)">
              <el-icon><Close /></el-icon>
            </button>
            <span class="media-index">{{ index + 1 }}</span>
          </div>

          <el-upload
            v-if="canAddMore"
            ref="portfolioUploadRef"
            v-model:file-list="portfolioFileList"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handlePortfolioChange"
            :on-remove="handlePortfolioRemove"
            :on-exceed="handleExceed"
            :limit="MAX_PORTFOLIO_COUNT"
            accept="image/*"
            multiple
            class="add-upload"
          >
            <button class="media-card media-add-card" type="button">
              <el-icon><Plus /></el-icon>
              <span>添加示例图</span>
            </button>
          </el-upload>
        </div>
      </div>
    </section>

    <section v-if="portfolioLibrary.length" class="portfolio-library">
      <div class="library-header">
        <div>
          <h2 class="library-title">从个人作品集选择</h2>
          <p class="library-hint">选择能体现本次企划风格的作品，也可以继续上传新的示例图。</p>
        </div>
        <span class="media-label">已选 {{ existingPortfolioRefs.length }}/{{ MAX_PORTFOLIO_COUNT }}</span>
      </div>
      <div class="library-grid">
        <button
          v-for="item in portfolioLibrary"
          :key="item.id || item.url"
          type="button"
          class="library-item"
          :class="{ selected: isPortfolioSelected(item) }"
          @click="togglePortfolioSelection(item)"
        >
          <img :src="getFullUrl(item.url)" :alt="item.title || '作品预览'" />
          <span class="library-item-copy">
            <strong>{{ item.title || item.tags?.slice(0, 2).join(' · ') || '未命名作品' }}</strong>
            <small>{{ isPortfolioSelected(item) ? '已选择' : '选择作品' }}</small>
          </span>
        </button>
      </div>
    </section>

    <section class="form-section">
      <div class="form-field">
        <label class="form-label" for="package-selection">方案来源</label>
        <div>
          <el-select
            id="package-selection"
            v-model="form.package_selection"
            size="large"
            class="full-width-control"
            @change="handlePackageSelection"
          >
            <el-option label="自定义方案" :value="CUSTOM_PACKAGE_VALUE" />
            <el-option
              v-for="pkg in availablePackages"
              :key="pkg.id || pkg.name"
              :label="`${pkg.name} · ¥${pkg.price}`"
              :value="pkg.id || pkg.name"
            />
          </el-select>
          <span class="field-hint">选择已有方案会自动带出报价，并将原方案描述和包含内容写入方案说明。</span>
        </div>
      </div>

      <div v-if="selectedPackage" class="package-preview">
        <div class="package-preview-head">
          <div>
            <span class="package-preview-kicker">已选方案</span>
            <strong>{{ selectedPackage.name }}</strong>
          </div>
          <span class="package-preview-price">¥{{ selectedPackage.price }}</span>
        </div>
        <p v-if="selectedPackage.description">{{ selectedPackage.description }}</p>
        <div class="package-preview-meta">
          <span v-if="selectedPackage.city || selectedPackage.service_location">地点：{{ selectedPackage.service_location || selectedPackage.city }}</span>
          <span v-if="selectedPackage.delivery_days">交付：{{ selectedPackage.delivery_days }} 天</span>
          <span v-if="selectedPackage.delivery_formats?.length">格式：{{ selectedPackage.delivery_formats.join('、') }}</span>
          <span>商业授权：{{ selectedPackage.commercial_license ? '包含' : '不包含' }}</span>
        </div>
        <p v-if="selectedPackage.terms_rules" class="package-preview-terms">条款规则：{{ selectedPackage.terms_rules }}</p>
      </div>

      <div class="form-row">
        <div class="form-field form-field-compact">
          <label class="form-label" for="price-quote">报价</label>
          <el-input-number id="price-quote" v-model="form.price_quote" :min="1" :step="100" size="large" />
        </div>

        <div class="form-field form-field-compact">
          <label class="form-label" for="package-name">方案名称</label>
          <el-input
            id="package-name"
            v-model="form.package_snapshot"
            :readonly="Boolean(selectedPackage)"
            placeholder="例如：自然光人像 2 小时方案"
            size="large"
          />
        </div>
      </div>

      <div class="form-field">
        <label class="form-label" for="proposal-text">方案说明</label>
        <el-input
          id="proposal-text"
          v-model="form.proposal_text"
          type="textarea"
          :rows="6"
          resize="none"
          maxlength="2000"
          show-word-limit
          placeholder="说明拍摄思路、执行安排、交付内容等；选择已有方案后会自动带入原方案描述"
        />
        <span class="field-hint">请将底片、精修、视频、交付方式等服务内容一并写在方案说明中。</span>
      </div>

      <div class="form-field">
        <label class="form-label" for="revision-note">条款事项</label>
        <el-input
          id="revision-note"
          v-model="form.revision_note"
          type="textarea"
          :rows="3"
          maxlength="1000"
          show-word-limit
          resize="none"
          placeholder="填写版权授权、取消改期、超时、交通、场地、天气变化等相关条款"
        />
      </div>
    </section>

    <section class="form-actions-panel">
      <div class="project-summary" v-if="project">
        <span>{{ formatBudget(project) }}</span>
        <span>{{ formatProjectLocation(project) }}</span>
        <span>{{ formatDateTime(project.shoot_date_start) }}</span>
        <span>{{ project.duration_minutes ? `${project.duration_minutes} 分钟` : '时长待沟通' }}</span>
      </div>

      <div class="form-actions-row">
        <el-button
          v-if="myApplication?.status === 'submitted'"
          size="large"
          class="btn-secondary"
          :icon="Close"
          :loading="submitting"
          @click="withdrawApplication"
        >
          撤回应邀
        </el-button>
        <el-button
          type="primary"
          size="large"
          class="btn-primary"
          :icon="myApplication ? Edit : Check"
          :loading="submitting"
          @click="submitApplication"
        >
          {{ myApplication ? '更新方案' : '提交应邀' }}
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Pencil as Edit, Plus, X as Close } from 'lucide-vue-next'
import {
  applyProject,
  getProjectDetail,
  updateMyApplication,
  withdrawMyApplication,
} from '../api/project'
import api from '../utils/api'

defineOptions({ name: 'ProjectApply' })

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const project = ref(null)
const myApplication = ref(null)
const mediaRailRef = ref(null)
const portfolioUploadRef = ref(null)
const portfolioFileList = ref([])
const existingPortfolioRefs = ref([])
const previewItems = ref([])
const MAX_PORTFOLIO_COUNT = 18
const CUSTOM_PACKAGE_VALUE = '__custom__'
const photographerProfile = ref(null)

const form = reactive({
  proposal_text: '',
  price_quote: 1000,
  package_snapshot: '',
  package_selection: CUSTOM_PACKAGE_VALUE,
  revision_note: '',
})

const canAddMore = computed(() => previewItems.value.length < MAX_PORTFOLIO_COUNT)
const availablePackages = computed(() => (
  (photographerProfile.value?.packages || []).filter((pkg) => pkg?.name && pkg.is_active !== false)
))
const portfolioLibrary = computed(() => (
  (photographerProfile.value?.portfolio || [])
    .map((item, index) => ({
      ...item,
      id: item.id || `portfolio-${index}`,
      url: item.url || item.images?.[0] || '',
    }))
    .filter((item) => item.url)
))
const selectedPackage = computed(() => availablePackages.value.find(
  (pkg) => String(pkg.id || pkg.name) === String(form.package_selection),
))

const normalizeIncludedItems = (value) => {
  if (Array.isArray(value)) {
    return value
      .map((item) => (typeof item === 'string' ? item : item?.name || item?.description || ''))
      .filter(Boolean)
  }
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

const compactPackageSnapshot = (pkg) => {
  if (!pkg) return form.package_snapshot || null
  return String(pkg.name || '').trim().slice(0, 500) || null
}

const mergeProposalContent = (description, includedItems) => {
  const proposal = String(description || '').trim()
  const items = normalizeIncludedItems(includedItems)
  if (!items.length) return proposal
  const includedText = `包含内容：${items.join('、')}`
  if (proposal.includes(includedText)) return proposal
  return [proposal, includedText].filter(Boolean).join('\n\n')
}

const handlePackageSelection = (value) => {
  if (String(value) === CUSTOM_PACKAGE_VALUE) {
    form.package_snapshot = ''
    return
  }
  const pkg = availablePackages.value.find((item) => String(item.id || item.name) === String(value))
  if (!pkg) {
    form.package_selection = CUSTOM_PACKAGE_VALUE
    return
  }
  form.price_quote = pkg.price || form.price_quote
  form.package_snapshot = compactPackageSnapshot(pkg)
  const packageProposal = mergeProposalContent(pkg.description, pkg.includes)
  if (packageProposal && !form.proposal_text.includes(packageProposal)) {
    form.proposal_text = [form.proposal_text.trim(), packageProposal].filter(Boolean).join('\n\n')
  }
}

const isPortfolioSelected = (item) => existingPortfolioRefs.value.some((ref) => ref?.url === item.url)

const togglePortfolioSelection = (item) => {
  const existingIndex = existingPortfolioRefs.value.findIndex((ref) => ref?.url === item.url)
  if (existingIndex >= 0) {
    existingPortfolioRefs.value = existingPortfolioRefs.value.filter((_, index) => index !== existingIndex)
  } else {
    if (previewItems.value.length >= MAX_PORTFOLIO_COUNT) {
      ElMessage.warning(`最多选择或上传 ${MAX_PORTFOLIO_COUNT} 张作品`)
      return
    }
    existingPortfolioRefs.value = [
      ...existingPortfolioRefs.value,
      { url: item.url, title: item.title || '', tags: item.tags || [] },
    ]
  }
  syncPreviewItems()
}

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const getFileKey = (file, index) => `${file.name}-${file.size}-${file.lastModified || 0}-${index}`

const revokePreviewItems = () => {
  previewItems.value.forEach((item) => {
    if (item.objectUrl) URL.revokeObjectURL(item.url)
  })
}

const syncPreviewItems = () => {
  revokePreviewItems()
  const existingItems = existingPortfolioRefs.value.map((item, index) => ({
    id: `existing-${item.url}-${index}`,
    url: getFullUrl(item.url),
    source: 'existing',
  }))
  const newItems = portfolioFileList.value
    .map((item) => item.raw)
    .filter(Boolean)
    .map((file, index) => ({
      id: getFileKey(file, index),
      url: URL.createObjectURL(file),
      objectUrl: true,
      source: 'new',
    }))
  previewItems.value = [...existingItems, ...newItems].slice(0, MAX_PORTFOLIO_COUNT)
}

const hydrateForm = () => {
  const application = myApplication.value
  if (application) {
    form.proposal_text = mergeProposalContent(application.proposal_text, application.included_items)
    form.price_quote = application.price_quote || 1000
    form.package_snapshot = application.package_snapshot || ''
    form.revision_note = application.revision_note || ''
    existingPortfolioRefs.value = Array.isArray(application.portfolio_refs)
      ? application.portfolio_refs.filter((item) => item?.url)
      : []
    const matchedPackage = availablePackages.value.find((pkg) => (
      application.package_snapshot && (
        application.package_snapshot === pkg.name
        || application.package_snapshot.startsWith(`${pkg.name} ·`)
      )
    ))
    form.package_selection = matchedPackage
      ? String(matchedPackage.id || matchedPackage.name)
      : CUSTOM_PACKAGE_VALUE
    if (matchedPackage) {
      const packageProposal = mergeProposalContent(matchedPackage.description, matchedPackage.includes)
      if (packageProposal && !form.proposal_text.includes(packageProposal)) {
        form.proposal_text = [form.proposal_text.trim(), packageProposal].filter(Boolean).join('\n\n')
      }
    }
  } else {
    form.proposal_text = ''
    form.package_selection = CUSTOM_PACKAGE_VALUE
    form.revision_note = ''
    existingPortfolioRefs.value = []
  }
  portfolioFileList.value = []
  syncPreviewItems()
}

const fetchDetail = async () => {
  loading.value = true
  try {
    const [res, meRes] = await Promise.all([
      getProjectDetail(route.params.projectId),
      api.get('/users/me', { skipErrorHandler: true }),
    ])
    project.value = res.data.project
    myApplication.value = res.data.my_application || null
    try {
      const profileRes = await api.get(`/photographers/profile/${meRes.data.id}`, { skipErrorHandler: true })
      photographerProfile.value = profileRes.data
    } catch {
      photographerProfile.value = null
    }
    hydrateForm()
  } finally {
    loading.value = false
  }
}

const handlePortfolioChange = (_uploadFile, uploadFiles) => {
  const remaining = Math.max(0, MAX_PORTFOLIO_COUNT - existingPortfolioRefs.value.length)
  portfolioFileList.value = uploadFiles.slice(0, remaining)
  syncPreviewItems()
}

const handlePortfolioRemove = (_uploadFile, uploadFiles) => {
  portfolioFileList.value = uploadFiles
  syncPreviewItems()
}

const removePortfolio = (index) => {
  const target = previewItems.value[index]
  if (!target) return
  if (target.source === 'existing') {
    const existingIndex = previewItems.value.slice(0, index).filter((item) => item.source === 'existing').length
    existingPortfolioRefs.value = existingPortfolioRefs.value.filter((_, itemIndex) => itemIndex !== existingIndex)
  } else {
    const newIndex = previewItems.value.slice(0, index).filter((item) => item.source === 'new').length
    portfolioFileList.value = portfolioFileList.value.filter((_, itemIndex) => itemIndex !== newIndex)
  }
  syncPreviewItems()
}

const handleExceed = () => {
  ElMessage.warning(`最多上传 ${MAX_PORTFOLIO_COUNT} 张示例图`)
}

const handleMediaWheel = (event) => {
  if (!mediaRailRef.value) return
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  mediaRailRef.value.scrollLeft += delta
}

const buildApplicationPayload = (uploadedUrls = []) => ({
  proposal_text: form.proposal_text,
  price_quote: form.price_quote,
  package_snapshot: selectedPackage.value ? compactPackageSnapshot(selectedPackage.value) : (form.package_snapshot || null),
  portfolio_refs: [
    ...existingPortfolioRefs.value,
    ...uploadedUrls.map((url) => ({ url })),
  ],
  revision_note: form.revision_note.trim() || null,
})

const submitApplication = async () => {
  if (project.value?.status !== 'open') {
    ElMessage.warning('该企划当前不接受应邀')
    router.push(`/projects/${project.value?.id || route.params.projectId}`)
    return
  }
  if (!form.proposal_text.trim()) {
    ElMessage.warning('请填写方案说明')
    return
  }
  submitting.value = true
  try {
    let uploadedUrls = []
    const files = portfolioFileList.value.filter((item) => item.raw)
    if (files.length) {
      const fd = new FormData()
      files.forEach((item) => fd.append('files', item.raw))
      const uploadRes = await api.post('/projects/upload-images', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      uploadedUrls = uploadRes.data.urls || []
    }

    if (myApplication.value) {
      await updateMyApplication(project.value.id, buildApplicationPayload(uploadedUrls))
      ElMessage.success('应邀方案已更新')
    } else {
      await applyProject(project.value.id, buildApplicationPayload(uploadedUrls))
      ElMessage.success('应邀方案已提交')
    }
    router.push(`/projects/${project.value.id}`)
  } finally {
    submitting.value = false
  }
}

const withdrawApplication = async () => {
  try {
    await ElMessageBox.confirm('确定撤回这个应邀方案？', '撤回应邀', { type: 'warning' })
  } catch {
    return
  }
  submitting.value = true
  try {
    await withdrawMyApplication(project.value.id)
    ElMessage.info('已撤回应邀')
    router.push(`/projects/${project.value.id}`)
  } finally {
    submitting.value = false
  }
}

const formatBudget = (item) => {
  if (item.budget_min && item.budget_max) return `¥${item.budget_min} - ¥${item.budget_max}`
  if (item.budget_min) return `¥${item.budget_min} 起`
  if (item.budget_max) return `¥${item.budget_max} 内`
  return '预算待沟通'
}

const formatDateTime = (value) => {
  if (!value) return '时间待沟通'
  return new Date(value).toLocaleString()
}

const formatProjectLocation = (item) => {
  const parts = [item?.city, item?.location_text].filter(Boolean)
  return parts.length ? `地点：${parts.join(' · ')}` : '地点待沟通'
}

const goBack = () => {
  if (window.history.length > 1) router.back()
  else if (project.value?.id) router.push(`/projects/${project.value.id}`)
  else router.push('/projects')
}

onMounted(() => {
  fetchDetail()
})

onUnmounted(() => {
  revokePreviewItems()
})
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

.page-subtitle {
  margin: 6px 0 0;
  color: var(--color-ink-secondary);
  font-size: 0.875rem;
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

.portfolio-library {
  margin-top: var(--space-4);
  padding: 20px 22px;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.library-header,
.package-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.library-title {
  margin: 0;
  color: var(--color-ink);
  font-size: var(--text-base);
  font-weight: 700;
}

.library-hint,
.field-hint {
  display: block;
  margin: 6px 0 0;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(108px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.library-item {
  appearance: none;
  position: relative;
  min-width: 0;
  padding: 0;
  overflow: hidden;
  text-align: left;
  color: var(--color-ink);
  background: var(--color-paper);
  border: 2px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.library-item:hover,
.library-item.selected {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.library-item img {
  display: block;
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
}

.library-item-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 8px 8px;
}

.library-item-copy strong {
  overflow: hidden;
  font-size: var(--text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.library-item-copy small {
  color: var(--color-ink-tertiary);
  font-size: 11px;
}

.library-item.selected .library-item-copy small {
  color: var(--color-brand);
  font-weight: 700;
}

.package-preview {
  padding: 16px 18px;
  color: var(--color-ink-secondary);
  background: var(--color-brand-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.package-preview-kicker {
  display: block;
  margin-bottom: 3px;
  color: var(--color-brand);
  font-size: var(--text-xs);
}

.package-preview-head strong {
  color: var(--color-ink);
  font-size: var(--text-base);
}

.package-preview-price {
  color: var(--color-brand);
  font-size: var(--text-sm);
  font-weight: 700;
  white-space: nowrap;
}

.package-preview p {
  margin: var(--space-3) 0 0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.package-preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: var(--space-3);
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.package-preview-terms {
  padding-top: var(--space-3);
  border-top: var(--border-default);
  font-size: var(--text-xs);
}

.full-width-control {
  width: 100%;
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

.form-field-compact :deep(.el-date-editor.el-input),
.form-field-compact :deep(.el-input-number),
.form-field-compact :deep(.el-input-number .el-input__wrapper) {
  width: 100%;
}

.form-actions-panel {
  margin-top: 18px;
  padding: 22px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.project-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) 14px;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
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

@media (max-width: 760px) {
  .page-container {
    width: min(100% - 24px, 1120px);
    margin-top: 18px;
  }

  .page-header {
    align-items: flex-start;
    gap: var(--space-4);
  }

  .page-title {
    font-size: 26px;
  }

  .media-section,
  .portfolio-library,
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

  .library-header,
  .package-preview-head {
    flex-direction: column;
  }

  .package-preview-price {
    white-space: normal;
  }

  .form-field,
  .form-field-compact {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }

  .form-label {
    padding-top: 0;
  }

  .form-actions-panel {
    align-items: stretch;
    flex-direction: column;
  }

  .form-actions-row {
    flex-direction: column-reverse;
  }

  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
</style>
