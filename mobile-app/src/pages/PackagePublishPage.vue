<template>
  <ion-page>
    <DetailHeader :title="isEditMode ? '编辑摄影方案' : '创建摄影方案'" :default-href="isEditMode ? '/packages/manage' : '/tabs/discover'" />

    <ion-content class="mobile-publish-content">
      <main class="mobile-publish-shell">
        <StatePanel
          v-if="auth.initialized && !auth.isPhotographer"
          title="需要摄影师身份"
          description="摄影方案会进入预约和支付流程，目前仅通过摄影师认证的账号可以创建和管理。"
          action-label="返回我的"
          @action="router.replace({ name: 'profile' })"
        />

        <FeedSkeleton v-else-if="isEditMode && editLoading" :count="3" />
        <StatePanel
          v-else-if="isEditMode && editError"
          tone="error"
          title="方案无法编辑"
          :description="editError"
          action-label="重新加载"
          @action="loadPackageForEdit"
        />

        <template v-else>
          <section class="mobile-publish-intro">
            <span>
              <FilePenLine v-if="isEditMode" :size="22" aria-hidden="true" />
              <PackagePlus v-else :size="22" aria-hidden="true" />
            </span>
            <div>
              <h1>{{ isEditMode ? '更新方案内容与服务边界' : '把价格、交付和规则一次说清' }}</h1>
              <p>{{ isEditMode ? '保存后会同步更新公开展示；上下架状态仍由方案管理页控制。' : '方案发布后会直接出现在橱窗和摄影师主页，客户可以据此选择档期。' }}</p>
            </div>
          </section>

        <section v-if="!isEditMode && draftRestored" class="publish-draft-note" role="status">
            <FileClock :size="19" aria-hidden="true" />
            <div><strong>已恢复 {{ draftTime }} 保存的本机草稿</strong><p>方案文字已恢复，样片需要重新选择。</p></div>
        </section>
        <section v-if="agentTask && !isEditMode" class="agent-source-note" role="status">已载入 Agent 整理的信息，可直接在此修改。</section>

          <form class="mobile-publish-form" novalidate @submit.prevent="submitPackage">
            <section class="publish-section">
              <header class="publish-section-heading"><span>1</span><div><h2>方案概况</h2><p>名称、价格和时长会优先展示给客户。</p></div></header>
              <div class="publish-field">
                <label for="package-name">方案名称 <span>必填</span></label>
                <input id="package-name" v-model.trim="form.name" class="publish-input" maxlength="120" placeholder="例如：个人写真半日方案" :disabled="submitting" :aria-invalid="Boolean(errors.name)" @blur="validateRequired('name')" />
                <p v-if="errors.name" class="publish-error" role="alert">{{ errors.name }}</p>
              </div>
              <div class="publish-field-grid">
                <div class="publish-field">
                  <label for="package-price">价格 <span>人民币元</span></label>
                  <input id="package-price" v-model.number="form.price" type="number" inputmode="decimal" min="0" step="100" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.price)" />
                  <p v-if="errors.price" class="publish-error" role="alert">{{ errors.price }}</p>
                </div>
                <div class="publish-field">
                  <label for="package-duration">拍摄时长 <span>分钟</span></label>
                  <input id="package-duration" v-model.number="form.duration" type="number" inputmode="numeric" min="30" step="30" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.duration)" />
                  <p v-if="errors.duration" class="publish-error" role="alert">{{ errors.duration }}</p>
                </div>
              </div>
              <div class="publish-field-grid">
                <div class="publish-field"><label for="package-city">服务城市 <span>选填</span></label><input id="package-city" v-model.trim="form.city" class="publish-input" maxlength="80" placeholder="留空表示不限城市" :disabled="submitting" /></div>
                <div class="publish-field"><label for="package-location">服务地点或范围 <span>选填</span></label><input id="package-location" v-model.trim="form.service_location" class="publish-input" maxlength="160" placeholder="例如：港岛及九龙" :disabled="submitting" /></div>
              </div>
              <div class="publish-field"><label for="package-styles">风格领域 <span>最多 12 个</span></label><TagEditor v-model="styles" input-id="package-styles" placeholder="例如：复古、人像、婚礼" :disabled="submitting" @limit="toastMessage = '最多添加 12 个风格标签。'" /></div>
              <div class="publish-field">
                <label for="package-description">方案描述 <span>选填</span></label>
                <textarea id="package-description" v-model.trim="form.description" class="publish-textarea" rows="6" maxlength="1600" placeholder="介绍适合人群、拍摄流程、服装场景、包含服务和交付标准" :disabled="submitting" />
              </div>
            </section>

            <section class="publish-section">
              <header class="publish-section-heading"><span>2</span><div><h2>交付内容</h2><p>结构化信息会进入订单快照，减少后续争议。</p></div></header>
              <div class="publish-field-grid">
                <div class="publish-field"><label for="package-original-count">交付原片 <span>张</span></label><input id="package-original-count" v-model.number="form.original_image_count" type="number" inputmode="numeric" min="0" class="publish-input" :disabled="submitting" /></div>
                <div class="publish-field"><label for="package-retouched-count">精修数量 <span>张</span></label><input id="package-retouched-count" v-model.number="form.retouched_image_count" type="number" inputmode="numeric" min="0" class="publish-input" :disabled="submitting" /></div>
              </div>
              <div class="publish-field-grid">
                <div class="publish-field"><label for="package-delivery-days">交付周期 <span>天</span></label><input id="package-delivery-days" v-model.number="form.delivery_days" type="number" inputmode="numeric" min="0" class="publish-input" :disabled="submitting" /></div>
                <div class="publish-field"><label for="package-revisions">免费修改 <span>次</span></label><input id="package-revisions" v-model.number="form.included_revision_count" type="number" inputmode="numeric" min="0" class="publish-input" :disabled="submitting" /></div>
              </div>
              <div class="publish-field">
                <label for="package-formats">交付格式 <span>至少一项</span></label>
                <TagEditor v-model="deliveryFormats" input-id="package-formats" placeholder="例如：JPG、PNG" :max-tags="8" :disabled="submitting" @limit="toastMessage = '最多添加 8 种交付格式。'" />
                <p v-if="errors.deliveryFormats" class="publish-error" role="alert">{{ errors.deliveryFormats }}</p>
              </div>
            </section>

            <section class="publish-section">
              <header class="publish-section-heading"><span>3</span><div><h2>支付与规则</h2><p>发布前确认付款方式、授权范围及取消改期约定。</p></div></header>
              <div class="publish-field-grid">
                <div class="publish-field"><label for="package-payment-mode">付款方式</label><select id="package-payment-mode" v-model="form.payment_mode" class="publish-select" :disabled="submitting"><option value="full">全款支付</option><option value="deposit_balance">定金 + 尾款</option></select></div>
                <div v-if="form.payment_mode === 'deposit_balance'" class="publish-field">
                  <label for="package-deposit-rate">定金比例 <span>%</span></label>
                  <input id="package-deposit-rate" v-model.number="form.deposit_rate_percent" type="number" inputmode="numeric" min="10" max="90" step="5" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.deposit_rate_percent)" />
                  <p v-if="errors.deposit_rate_percent" class="publish-error" role="alert">{{ errors.deposit_rate_percent }}</p>
                </div>
              </div>
              <label class="publish-check-row" for="package-commercial-license"><span><strong>包含商业使用授权</strong><small class="publish-help">允许客户将成片用于商业宣传</small></span><input id="package-commercial-license" v-model="form.commercial_license" type="checkbox" :disabled="submitting" /></label>
              <div class="publish-field"><label for="package-terms">条款规则 <span>建议填写</span></label><textarea id="package-terms" v-model.trim="form.terms_rules" class="publish-textarea" rows="7" maxlength="2400" placeholder="分别说明版权与使用范围、取消政策、改期次数和响应期限" :disabled="submitting" /></div>
            </section>

            <section class="publish-section">
              <header class="publish-section-heading"><span>4</span><div><h2>方案样片</h2><p>选填；第一张会作为方案封面，最多 18 张。</p></div></header>
              <div v-if="existingSamples.length" class="existing-media-grid" aria-label="现有方案样片">
                <article v-for="(sample, index) in existingSamples" :key="`${sample.url}-${index}`" class="existing-media-card">
                  <img :src="resolveMediaUrl(sample.thumbnailUrl || sample.url)" :alt="`现有方案样片 ${index + 1}`" loading="lazy" />
                  <button type="button" class="remove-existing-media pressable" :disabled="submitting" :aria-label="`移除现有样片 ${index + 1}`" @click="removeExistingSample(index)">
                    <X :size="18" aria-hidden="true" />
                  </button>
                  <span>{{ index + 1 }}</span>
                </article>
              </div>
              <p v-if="existingSamples.length" class="existing-media-help">现有样片会排在新上传图片之前；移除后需保存修改才会生效。</p>
              <PublishMediaPicker
                v-model:files="sampleFiles"
                input-id="package-sample-files"
                mode="image"
                :existing-count="existingSamples.length"
                :disabled="submitting"
                @error="requestError = $event"
              />
            </section>

            <div v-if="requestError" class="publish-request-error" role="alert"><CircleAlert :size="19" aria-hidden="true" />{{ requestError }}</div>
            <div v-if="submitting" class="publish-progress" aria-live="polite"><div><i :style="{ '--progress': `${uploadProgress}%` }" /></div><span>{{ progressText }}</span></div>
          </form>
        </template>
      </main>
      <ion-toast :is-open="Boolean(toastMessage)" :message="toastMessage" :duration="2600" position="bottom" @did-dismiss="toastMessage = ''" />
    </ion-content>

    <ion-footer v-if="(!auth.initialized || auth.isPhotographer) && (!isEditMode || (!editLoading && !editError))" class="mobile-publish-footer">
      <div class="mobile-publish-actions with-agent">
        <button type="button" class="pressable" :disabled="submitting || agentPolishing || editLoading || Boolean(editError)" @click="isEditMode ? cancelEdit() : saveDraftNow()">
          <ArrowLeft v-if="isEditMode" :size="18" aria-hidden="true" />
          <Save v-else :size="18" aria-hidden="true" />
          {{ isEditMode ? '取消编辑' : '保存本机' }}
        </button>
        <PublishAgentPolishButton
          content-type="package"
          :fields="packagePolishFields"
          :disabled="submitting || editLoading || Boolean(editError)"
          @busy-change="agentPolishing = $event"
          @error="requestError = $event"
          @polished="applyPolishedPackage"
        />
        <button type="button" class="pressable" :disabled="submitting || agentPolishing || editLoading || Boolean(editError)" @click="submitPackage">
          <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
          <Save v-else-if="isEditMode" :size="18" aria-hidden="true" />
          <PackageCheck v-else :size="18" aria-hidden="true" />
          {{ isEditMode ? '保存修改' : '发布方案' }}
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonFooter, IonPage, IonSpinner, IonToast } from '@ionic/vue'
import {
  ArrowLeft,
  CircleAlert,
  FileClock,
  FilePenLine,
  PackageCheck,
  PackagePlus,
  Save,
  X,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PublishMediaPicker from '@/components/PublishMediaPicker.vue'
import PublishAgentPolishButton from '@/components/PublishAgentPolishButton.vue'
import StatePanel from '@/components/StatePanel.vue'
import TagEditor from '@/components/TagEditor.vue'
import { getApiErrorMessage } from '@/api/client'
import { useAgentTaskHandoff } from '@/composables/useAgentTaskHandoff'
import { getPhotographerPackageProfile, updatePhotographerPackage } from '@/api/packages'
import { createPhotographerPackage, uploadPackageSamples } from '@/api/publishing'
import { useAuthStore } from '@/stores/auth'
import type { PackageOffer } from '@/types/discovery'
import type { PackageCreatePayload } from '@/types/publishing'
import { resolveMediaUrl } from '@/utils/media'
import { clearPublishDraft, formatDraftTime, readPublishDraft, savePublishDraft } from '@/utils/publishing'

interface PackageFormState {
  name: string
  price: number | ''
  duration: number | ''
  city: string
  service_location: string
  description: string
  original_image_count: number | ''
  retouched_image_count: number | ''
  delivery_days: number | ''
  included_revision_count: number | ''
  payment_mode: 'full' | 'deposit_balance'
  deposit_rate_percent: number | ''
  commercial_license: boolean
  terms_rules: string
  styles: string[]
  includes: string[]
  deliveryFormats: string[]
}

interface ExistingSample {
  url: string
  thumbnailUrl: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const agentHandoff = useAgentTaskHandoff()
const agentTask = agentHandoff.task
const isEditMode = computed(() => route.name === 'package-edit')
const packageId = computed(() => String(route.params.packageId || ''))
const form = reactive<PackageFormState>({ name: '', price: 699, duration: 120, city: '', service_location: '', description: '', original_image_count: 0, retouched_image_count: 30, delivery_days: 7, included_revision_count: 1, payment_mode: 'full', deposit_rate_percent: 30, commercial_license: false, terms_rules: '', styles: [], includes: [], deliveryFormats: ['JPG'] })
const styles = ref<string[]>([])
const includes = ref<string[]>([])
const deliveryFormats = ref<string[]>(['JPG'])
const existingSamples = ref<ExistingSample[]>([])
const sampleFiles = ref<File[]>([])
const editingOffer = ref<PackageOffer | null>(null)
const editLoading = ref(isEditMode.value)
const editError = ref('')
const errors = reactive<Record<string, string>>({})
const requestError = ref('')
const submitting = ref(false)
const agentPolishing = ref(false)
const uploadProgress = ref(0)
const progressText = ref('正在准备发布…')
const draftRestored = ref(false)
const draftTime = ref('')
const toastMessage = ref('')
const currentDraftId = ref('')
let draftTimer: number | null = null

const packagePolishFields = computed(() => ({
  name: form.name,
  city: form.city,
  service_location: form.service_location,
  description: form.description,
  styles: [...styles.value],
  includes: [...includes.value],
  delivery_formats: [...deliveryFormats.value],
  terms_rules: form.terms_rules,
}))

function applyPolishedPackage(fields: Record<string, unknown>, changedCount: number) {
  if (typeof fields.name === 'string') form.name = fields.name
  if (typeof fields.city === 'string') form.city = fields.city
  if (typeof fields.service_location === 'string') form.service_location = fields.service_location
  if (typeof fields.description === 'string') form.description = fields.description
  if (typeof fields.terms_rules === 'string') form.terms_rules = fields.terms_rules
  if (Array.isArray(fields.styles)) styles.value = fields.styles.map(String).slice(0, 12)
  if (Array.isArray(fields.includes)) includes.value = fields.includes.map(String).slice(0, 20)
  if (Array.isArray(fields.delivery_formats)) deliveryFormats.value = fields.delivery_formats.map(String).slice(0, 8)
  requestError.value = ''
  toastMessage.value = changedCount ? `Agent 已润色 ${changedCount} 项文字内容。` : '当前文字已经很清晰，无需调整。'
}

function validateRequired(field: 'name') {
  errors[field] = form[field].trim() ? '' : '请填写方案名称。'
  return !errors[field]
}

function validateForm() {
  Object.keys(errors).forEach((key) => { errors[key] = '' })
  validateRequired('name')
  if (form.price === '' || Number(form.price) < 0) errors.price = '价格不能小于 0。'
  if (form.duration === '' || Number(form.duration) < 30) errors.duration = '拍摄时长至少为 30 分钟。'
  if (!deliveryFormats.value.length) errors.deliveryFormats = '请至少填写一种交付格式。'
  if (form.payment_mode === 'deposit_balance' && (form.deposit_rate_percent === '' || Number(form.deposit_rate_percent) < 10 || Number(form.deposit_rate_percent) > 90)) {
    errors.deposit_rate_percent = '定金比例需要在 10% 到 90% 之间。'
  }
  const firstError = Object.entries(errors).find(([, message]) => message)
  const fieldIds: Record<string, string> = {
    deliveryFormats: 'package-formats',
    deposit_rate_percent: 'package-deposit-rate',
  }
  if (firstError) document.getElementById(fieldIds[firstError[0]] || `package-${firstError[0].replaceAll('_', '-')}`)?.focus()
  return !firstError
}

function hydrateForm(offer: PackageOffer) {
  Object.assign(form, {
    name: offer.name || offer.package_name || '',
    price: Number(offer.price ?? 0),
    duration: Number(offer.duration ?? 120),
    city: offer.city || '',
    service_location: offer.service_location || '',
    description: offer.description || '',
    original_image_count: Number(offer.original_image_count ?? 0),
    retouched_image_count: Number(offer.retouched_image_count ?? offer.image_count ?? 0),
    delivery_days: Number(offer.delivery_days ?? 7),
    included_revision_count: Number(offer.included_revision_count ?? 0),
    payment_mode: offer.payment_mode === 'deposit_balance' ? 'deposit_balance' : 'full',
    deposit_rate_percent: Math.round(Number(offer.deposit_rate ?? .3) * 100),
    commercial_license: Boolean(offer.commercial_license),
    terms_rules: offer.terms_rules || '',
  })
  styles.value = [...(offer.styles || [])]
  includes.value = [...(offer.includes || [])]
  deliveryFormats.value = offer.delivery_formats?.length ? [...offer.delivery_formats] : ['JPG']
  existingSamples.value = (offer.samples || [])
    .map((url, index) => ({ url, thumbnailUrl: offer.sample_thumbnails?.[index] || '' }))
    .filter((sample) => Boolean(sample.url))
  sampleFiles.value = []
}

async function loadPackageForEdit() {
  if (!isEditMode.value) return
  editLoading.value = true
  editError.value = ''
  requestError.value = ''
  try {
    await auth.initialize()
    if (!auth.user || !auth.isPhotographer) return
    const profile = await getPhotographerPackageProfile(auth.user.id)
    const offer = (profile?.packages || []).find((item) => String(item.id) === packageId.value)
    if (!offer) throw new Error('方案不存在或不属于当前摄影师账号。')
    editingOffer.value = offer
    hydrateForm(offer)
  } catch (error) {
    editingOffer.value = null
    editError.value = getApiErrorMessage(error)
  } finally {
    editLoading.value = false
  }
}

function buildPayload(sampleUrls: string[], sampleThumbnailUrls: string[]): PackageCreatePayload {
  const retouchedCount = form.retouched_image_count === '' ? 0 : Number(form.retouched_image_count)
  return {
    name: form.name.trim(),
    price: Number(form.price),
    duration: Number(form.duration),
    description: form.description.trim(),
    includes: [...includes.value],
    styles: [...styles.value],
    city: form.city.trim(),
    service_location: form.service_location.trim(),
    samples: sampleUrls,
    sample_thumbnails: sampleThumbnailUrls,
    original_image_count: form.original_image_count === '' ? 0 : Number(form.original_image_count),
    retouched_image_count: retouchedCount,
    image_count: retouchedCount,
    delivery_formats: [...deliveryFormats.value],
    included_revision_count: form.included_revision_count === '' ? 0 : Number(form.included_revision_count),
    delivery_days: form.delivery_days === '' ? 7 : Number(form.delivery_days),
    commercial_license: form.commercial_license,
    terms_rules: form.terms_rules.trim() || null,
    is_active: isEditMode.value ? editingOffer.value?.is_active !== false : true,
    payment_mode: form.payment_mode,
    deposit_rate: form.payment_mode === 'deposit_balance' ? Number(form.deposit_rate_percent || 30) / 100 : .3,
    fulfillment_mode: 'single_delivery',
  }
}

async function submitPackage() {
  if (submitting.value || !validateForm()) return
  await auth.initialize()
  if (!auth.user || !auth.isPhotographer) {
    requestError.value = '当前账号不是摄影师，无法保存方案。'
    return
  }
  if (isEditMode.value && !editingOffer.value) {
    requestError.value = '方案尚未成功加载，请重新进入编辑页。'
    return
  }

  submitting.value = true
  requestError.value = ''
  uploadProgress.value = sampleFiles.value.length ? 2 : 74
  progressText.value = sampleFiles.value.length
    ? '正在上传方案样片…'
    : isEditMode.value ? '正在保存方案修改…' : '正在发布方案…'
  try {
    const sampleResult = await uploadPackageSamples(sampleFiles.value, (percent) => {
      uploadProgress.value = Math.round(percent * .72)
    })
    const existingUrls = existingSamples.value.map((sample) => sample.url)
    const existingThumbnailUrls = existingSamples.value.map((sample) => sample.thumbnailUrl || sample.url)
    const payload = buildPayload(
      [...existingUrls, ...sampleResult.urls],
      [...existingThumbnailUrls, ...sampleResult.thumbnailUrls],
    )

    uploadProgress.value = 82
    progressText.value = '正在保存方案和订单规则…'
    if (isEditMode.value) {
      await updatePhotographerPackage(auth.user.id, packageId.value, payload)
      uploadProgress.value = 100
      await router.replace({
        name: 'package-management',
        query: { status: payload.is_active ? 'active' : 'inactive', saved: '1' },
      })
      return
    }

    const result = await createPhotographerPackage(auth.user.id, payload)
    uploadProgress.value = 100
    if (currentDraftId.value) clearPublishDraft('package', currentDraftId.value)
    if (agentTask.value) await agentHandoff.complete({ package_id: result.package?.id })
    if (result.package?.id) await router.replace({ name: 'package-detail', params: { packageId: result.package.id } })
    else await router.replace({ name: 'photographer-detail', params: { userId: auth.user.id } })
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

function removeExistingSample(index: number) {
  existingSamples.value = existingSamples.value.filter((_, sampleIndex) => sampleIndex !== index)
}

function cancelEdit() {
  void router.replace({ name: 'package-management' })
}

function draftSnapshot(): PackageFormState {
  return { ...form, styles: [...styles.value], includes: [...includes.value], deliveryFormats: [...deliveryFormats.value] }
}

function saveDraftNow() {
  if (isEditMode.value) return
  const id = savePublishDraft('package', draftSnapshot(), currentDraftId.value)
  currentDraftId.value = id
  toastMessage.value = `本机草稿已保存（${formatDraftTime(new Date().toISOString())}）`
}

function restoreDraft() {
  if (route.query.agentTaskId) return
  const draftId = route.query.draftId as string | undefined
  const draft = readPublishDraft<PackageFormState>('package', draftId)
  if (!draft) return
  Object.assign(form, draft.value)
  styles.value = Array.isArray(draft.value.styles) ? draft.value.styles : []
  includes.value = Array.isArray(draft.value.includes) ? draft.value.includes : []
  deliveryFormats.value = Array.isArray(draft.value.deliveryFormats) && draft.value.deliveryFormats.length ? draft.value.deliveryFormats : ['JPG']
  draftRestored.value = true
  draftTime.value = formatDraftTime(draft.updatedAt)
  currentDraftId.value = draft.id
}

function taskOperation(field: string, value: unknown) {
  const empty = value === '' || value === null || value === undefined || (Array.isArray(value) && !value.length)
  return empty ? { field, op: 'clear' as const } : { field, op: 'set' as const, value }
}

function packageTaskOperations() {
  return [
    taskOperation('name', form.name.trim()),
    taskOperation('price', form.price === '' ? null : Number(form.price)),
    taskOperation('duration', form.duration === '' ? null : Number(form.duration)),
    taskOperation('city', form.city.trim()),
    taskOperation('service_location', form.service_location.trim()),
    taskOperation('description', form.description.trim()),
    taskOperation('styles', [...styles.value]),
    taskOperation('includes', [...includes.value]),
    taskOperation('original_image_count', form.original_image_count === '' ? null : Number(form.original_image_count)),
    taskOperation('retouched_image_count', form.retouched_image_count === '' ? null : Number(form.retouched_image_count)),
    taskOperation('delivery_days', form.delivery_days === '' ? null : Number(form.delivery_days)),
    taskOperation('included_revision_count', form.included_revision_count === '' ? null : Number(form.included_revision_count)),
    taskOperation('delivery_formats', [...deliveryFormats.value]),
    taskOperation('payment_mode', form.payment_mode),
    taskOperation('deposit_rate', form.payment_mode === 'deposit_balance' ? Number(form.deposit_rate_percent || 30) / 100 : null),
    taskOperation('commercial_license', form.commercial_license),
    taskOperation('terms_rules', form.terms_rules.trim()),
  ]
}

function scheduleDraftSave() {
  if (isEditMode.value) return
  if (draftTimer !== null) window.clearTimeout(draftTimer)
  draftTimer = window.setTimeout(() => {
    if (route.query.agentTaskId) {
      void agentHandoff.saveOperations(packageTaskOperations()).catch((error) => {
        requestError.value = getApiErrorMessage(error)
      })
    } else {
      const id = savePublishDraft('package', draftSnapshot(), currentDraftId.value)
      currentDraftId.value = id
    }
  }, 450)
}

function hydrateAgentPackage(fields: Record<string, unknown>) {
  Object.assign(form, {
    name: String(fields.name || fields.package_name || ''),
    price: typeof fields.price === 'number' ? fields.price : '',
    duration: typeof fields.duration === 'number' ? fields.duration : '',
    city: String(fields.city || ''), service_location: String(fields.service_location || ''),
    description: String(fields.description || ''),
    original_image_count: typeof fields.original_image_count === 'number' ? fields.original_image_count : 0,
    retouched_image_count: typeof fields.retouched_image_count === 'number' ? fields.retouched_image_count : 0,
    delivery_days: typeof fields.delivery_days === 'number' ? fields.delivery_days : 7,
    included_revision_count: typeof fields.included_revision_count === 'number' ? fields.included_revision_count : 0,
    payment_mode: fields.payment_mode === 'deposit_balance' ? 'deposit_balance' : 'full',
    deposit_rate_percent: typeof fields.deposit_rate === 'number' ? Math.round(fields.deposit_rate <= 1 ? fields.deposit_rate * 100 : fields.deposit_rate) : 30,
    commercial_license: Boolean(fields.commercial_license), terms_rules: String(fields.terms_rules || ''),
  })
  styles.value = Array.isArray(fields.styles) ? fields.styles.map(String) : []
  includes.value = Array.isArray(fields.includes) ? fields.includes.map(String) : []
  deliveryFormats.value = Array.isArray(fields.delivery_formats) && fields.delivery_formats.length ? fields.delivery_formats.map(String) : ['JPG']
}

onMounted(async () => {
  const task = await agentHandoff.load('publish_package')
  if (task) hydrateAgentPackage(task.fields)
  else if (!isEditMode.value) restoreDraft()
  await auth.initialize()
  if (isEditMode.value && auth.isPhotographer) await loadPackageForEdit()
})
watch(() => draftSnapshot(), scheduleDraftSave, { deep: true })
onUnmounted(() => { if (draftTimer !== null) window.clearTimeout(draftTimer) })
</script>
