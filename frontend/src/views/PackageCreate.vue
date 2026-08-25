<template>
  <div class="package-create-page">
    <header class="page-header">
      <button class="back-btn" type="button" @click="goBack">
        <span aria-hidden="true">&lt;</span>
        <span>返回</span>
      </button>
      <h1 class="page-title">发布新方案</h1>
    </header>

    <section class="media-panel">
      <div class="panel-head">
        <span class="media-count">{{ sampleFiles.length }}/{{ MAX_SAMPLE_COUNT }}</span>
      </div>

      <div class="media-strip-wrap">
        <div ref="mediaRailRef" class="media-strip" @wheel.prevent="handleMediaWheel">
          <div v-for="(item, index) in previewItems" :key="item.id" class="media-card preview-card">
            <img :src="item.url" alt="" class="preview-media" />
            <button class="remove-card-btn" type="button" title="移除" aria-label="移除样片" @click="removeSample(index)">
              <el-icon><Close /></el-icon>
            </button>
            <span class="card-index">{{ index + 1 }}</span>
          </div>

          <el-upload
            v-if="canAddMore"
            ref="uploadRef"
            v-model:file-list="sampleFiles"
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleSampleChange"
            :on-remove="handleSampleRemove"
            :on-exceed="handleExceed"
            :limit="MAX_SAMPLE_COUNT"
            accept="image/*"
            multiple
            class="add-upload"
          >
            <button class="media-card add-card" type="button">
              <el-icon><Plus /></el-icon>
              <span>添加示例图</span>
            </button>
          </el-upload>
        </div>
      </div>
    </section>

    <section class="info-panel" v-loading="submitting">
      <div class="field-block">
        <label class="field-label" for="package-name">方案名称</label>
        <el-input id="package-name" v-model="form.name" placeholder="如：个人写真" size="large" />
      </div>

      <div class="field-grid">
        <div class="field-block compact-field">
          <label class="field-label" for="package-price">价格（人民币元）</label>
          <el-input-number id="package-price" v-model="form.price" :min="0" :step="100" size="large" />
        </div>

        <div class="field-block compact-field">
          <label class="field-label" for="package-duration">拍摄时长</label>
          <el-input-number id="package-duration" v-model="form.duration" :min="30" :step="30" size="large" />
        </div>
      </div>

      <div class="field-block">
        <label class="field-label">风格领域</label>
        <TagInput v-model="form.styleTags" placeholder="输入风格领域后按回车添加，如：复古" />
      </div>

      <div class="field-block">
        <label class="field-label" for="package-city">所在城市</label>
        <el-input id="package-city" v-model="form.city" placeholder="留空表示不限制城市" clearable size="large" />
      </div>

      <div class="field-block">
        <label class="field-label" for="package-description">方案描述</label>
        <div>
          <el-input
            id="package-description"
            v-model="form.description"
            type="textarea"
            :rows="9"
            resize="none"
            :placeholder="DESCRIPTION_PLACEHOLDER"
          />
          <span class="field-hint">请将服务细节直接写入方案描述，方便用户一次读懂方案内容。</span>
        </div>
      </div>

      <div class="field-grid">
        <div class="field-block compact-field">
          <label class="field-label">付款方式</label>
          <el-select v-model="form.paymentMode" size="large">
            <el-option label="全款支付" value="full" />
            <el-option label="定金 + 尾款" value="deposit_balance" />
          </el-select>
        </div>
        <div v-if="form.paymentMode === 'deposit_balance'" class="field-block compact-field">
          <label class="field-label">定金比例</label>
          <el-input-number v-model="form.depositRatePercent" :min="10" :max="90" :step="5" size="large" />
          <span class="field-hint">当前为 {{ form.depositRatePercent }}%，尾款须在开始服务前付清。</span>
        </div>
      </div>

      <div class="field-block license-row">
        <label class="field-label">商业使用授权</label>
        <el-switch v-model="form.commercialLicense" />
      </div>

      <div class="field-block">
        <label class="field-label" for="package-terms-rules">条款规则</label>
        <div>
          <el-input
            id="package-terms-rules"
            v-model="form.termsRules"
            type="textarea"
            :rows="6"
            resize="none"
            :placeholder="TERMS_RULES_PLACEHOLDER"
          />
          <span class="field-hint">请按提示补充完整规则，发布后会与方案一起展示给用户。</span>
        </div>
      </div>
    </section>

    <section class="action-panel">
      <div class="action-row">
        <el-button
          type="primary"
          size="large"
          class="publish-btn"
          :loading="submitting"
          @click="submitForm"
        >
          {{ submitting ? '提交中...' : '发布方案' }}
        </el-button>
        <el-button size="large" class="placeholder-btn" :disabled="submitting" @click="goBack">
          取消
        </el-button>
      </div>
    </section>

    <el-alert
      v-if="submitResult"
      :title="submitResult"
      :type="submitOk ? 'success' : 'error'"
      show-icon
      closable
      class="result-alert"
    />
  </div>
</template>

<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, X as Close } from 'lucide-vue-next'
import api from '../utils/api'
import TagInput from '@/components/TagInput.vue'

defineOptions({ name: 'PackageCreate' })

const router = useRouter()
const submitting = ref(false)
const submitResult = ref('')
const submitOk = ref(false)
const uploadRef = ref(null)
const mediaRailRef = ref(null)
const sampleFiles = ref([])
const previewItems = ref([])
const MAX_SAMPLE_COUNT = 18
const DESCRIPTION_PLACEHOLDER = '请介绍方案，并补充以下信息：服务地区、包含内容、原片精修数量、交付天数、交付格式'
const TERMS_RULES_PLACEHOLDER = '请填写条款规则：\n版权条款：说明著作权和客户使用范围。\n取消政策：说明不同阶段取消时的处理规则。\n改期政策：说明改期次数、响应期限等规则。'

const form = reactive({
  name: '',
  price: 699,
  duration: 120,
  styleTags: [],
  city: '',
  description: '',
  commercialLicense: false,
  termsRules: '',
  paymentMode: 'full',
  depositRatePercent: 30,
})

const canAddMore = computed(() => sampleFiles.value.length < MAX_SAMPLE_COUNT)

const getFileKey = (file, index) => `${file.name}-${file.size}-${file.lastModified || 0}-${index}`

const revokePreviewItems = () => {
  previewItems.value.forEach((item) => {
    if (item.url) URL.revokeObjectURL(item.url)
  })
}

const syncPreviewItems = () => {
  revokePreviewItems()
  previewItems.value = sampleFiles.value
    .map((item) => item.raw)
    .filter(Boolean)
    .map((file, index) => ({
      id: getFileKey(file, index),
      name: file.name,
      url: URL.createObjectURL(file),
    }))
}

const handleSampleChange = (_file, fileList) => {
  sampleFiles.value = fileList.slice(0, MAX_SAMPLE_COUNT)
  syncPreviewItems()
}

const handleSampleRemove = (_file, fileList) => {
  sampleFiles.value = fileList
  syncPreviewItems()
}

const removeSample = (index) => {
  sampleFiles.value = sampleFiles.value.filter((_, itemIndex) => itemIndex !== index)
  syncPreviewItems()
}

const handleExceed = () => {
  submitResult.value = ''
  ElMessage.warning(`最多上传 ${MAX_SAMPLE_COUNT} 张示例图`)
}

const handleMediaWheel = (event) => {
  if (!mediaRailRef.value) return
  const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY
  mediaRailRef.value.scrollLeft += delta
}

const goBack = () => {
  router.back()
}

const submitForm = async () => {
  if (!form.name) {
    submitResult.value = '请输入方案名称'
    submitOk.value = false
    return
  }
  if (!form.price && form.price !== 0) {
    submitResult.value = '请设定价格'
    submitOk.value = false
    return
  }

  submitting.value = true
  submitResult.value = ''
  try {
    const meRes = await api.get('/users/me', { skipErrorHandler: true })
    const userId = meRes.data.id
    const profileRes = await api.get(`/photographers/profile/${userId}`, { skipErrorHandler: true })
    const existingPackages = profileRes.data.packages || []

    // 上传示例图
    let sampleUrls = []
    let sampleThumbnailUrls = []
    const newFiles = sampleFiles.value.filter(f => f.raw)
    if (newFiles.length) {
      const fd = new FormData()
      newFiles.forEach(f => fd.append('files', f.raw))
      const uploadRes = await api.post('/photographers/package-samples/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      sampleUrls = uploadRes.data.urls || []
      sampleThumbnailUrls = (uploadRes.data.thumbnail_urls && uploadRes.data.thumbnail_urls.length)
        ? uploadRes.data.thumbnail_urls
        : sampleUrls
    }

    const newPkg = {
      name: form.name,
      price: form.price,
      duration: form.duration,
      description: form.description,
      styles: form.styleTags,
      city: form.city || '',
      samples: sampleUrls,
      sample_thumbnails: sampleThumbnailUrls,
      commercial_license: form.commercialLicense,
      terms_rules: form.termsRules || null,
      is_active: true,
      payment_mode: form.paymentMode,
      deposit_rate: form.depositRatePercent / 100,
      fulfillment_mode: 'single_delivery',
    }

    await api.post('/photographers/profile', {
      packages: [...existingPackages, newPkg],
    })

    submitOk.value = true
    submitResult.value = '方案发布成功！'
    setTimeout(() => router.push('/my-packages'), 1500)
  } catch (e) {
    submitOk.value = false
    submitResult.value = e.response?.data?.detail || '发布失败，请重试'
  } finally {
    submitting.value = false
  }
}

onUnmounted(() => {
  revokePreviewItems()
})
</script>

<style scoped>
.package-create-page {
  box-sizing: border-box;
  width: min(1120px, calc(100vw - 48px));
  margin: 28px auto 56px;
  color: var(--color-ink);
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
  color: var(--color-ink-tertiary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font: inherit;
  font-size: calc(var(--text-base) * 1rem);
  padding: var(--space-2) 0;
  transition: color 0.15s;
}

.back-btn:hover {
  color: var(--color-brand);
}

.page-title {
  font-size: calc(var(--text-3xl) * 1rem);
  line-height: 1.2;
  font-weight: 800;
  margin: 0;
  color: var(--color-ink);
}

.field-hint {
  display: block;
  margin-top: 6px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.info-panel,
.action-panel {
  box-sizing: border-box;
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.media-panel {
  padding: var(--space-1) 0 var(--space-2);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-4);
  margin-bottom: 10px;
}

.media-count {
  font-size: calc(var(--text-sm) * 1rem);
  color: var(--color-ink-tertiary);
  white-space: nowrap;
}

.media-strip-wrap {
  position: relative;
  overflow: hidden;
}

.media-strip {
  width: 100%;
  display: flex;
  gap: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 12px var(--space-2) 2px;
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
  background: var(--color-paper-light);
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

.remove-card-btn {
  appearance: none;
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  color: var(--color-paper);
  background: rgba(26, 26, 26, 0.62);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s;
}

.remove-card-btn:hover {
  background: var(--color-danger);
}

.card-index {
  position: absolute;
  left: var(--space-2);
  bottom: var(--space-2);
  min-width: 26px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(26, 26, 26, 0.62);
  color: var(--color-paper);
  font-size: calc(var(--text-xs) * 1rem);
  line-height: 22px;
  text-align: center;
}

.add-upload {
  flex: 0 0 auto;
}

.add-card {
  appearance: none;
  cursor: pointer;
  color: var(--color-brand);
  border: 1px dashed var(--color-border);
  background: var(--color-paper-light);
  flex-direction: column;
  gap: var(--space-2);
  font-size: calc(var(--text-sm) * 1rem);
  font-weight: 600;
  transition: border-color 0.15s, background 0.15s;
}

.add-card .el-icon {
  font-size: 28px;
}

.add-card:hover {
  background: var(--color-brand-light);
  border-color: var(--color-brand);
}

.info-panel {
  margin-top: var(--space-2);
  padding: 28px;
  display: grid;
  gap: 22px;
}

.field-block {
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}

.compact-field {
  grid-template-columns: 82px minmax(0, 1fr);
}

.field-label {
  padding-top: 9px;
  color: var(--color-ink-secondary);
  font-size: calc(var(--text-base) * 1rem);
  font-weight: 600;
}

.compact-field :deep(.el-input-number),
.compact-field :deep(.el-input-number .el-input__wrapper) {
  width: 100%;
}

.action-panel {
  margin-top: 18px;
  padding: 22px 28px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.publish-btn {
  min-width: 160px;
  font-weight: 700;
}

.placeholder-btn {
  min-width: 120px;
}

.form-hint {
  margin-left: var(--space-2);
  color: var(--color-ink-tertiary);
  font-size: calc(var(--text-sm) * 1rem);
}

.result-alert {
  margin-top: var(--space-4);
}

@media (max-width: 920px) {
  .field-grid {
    grid-template-columns: 1fr;
  }

  .compact-field {
    grid-template-columns: 92px minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .package-create-page {
    width: min(100% - 24px, 1120px);
    margin-top: 18px;
  }

  .page-header {
    gap: var(--space-4);
  }

  .page-title {
    font-size: calc(var(--text-2xl) * 1rem);
  }

  .media-panel,
  .info-panel,
  .action-panel {
    padding: 18px;
  }

  .media-panel {
    padding-left: 0;
    padding-right: 0;
  }

  .media-card {
    width: 108px;
  }

  .field-block,
  .compact-field {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }

  .field-label {
    padding-top: 0;
  }

  .action-row {
    align-items: stretch;
    flex-direction: column;
  }

  .publish-btn,
  .placeholder-btn {
    width: 100%;
  }
}
</style>
