<template>
  <ion-page>
    <DetailHeader title="摄影师认证" default-href="/tabs/profile">
      <template #action>
        <button
          type="button"
          class="header-action pressable"
          :disabled="loading || submitting"
          aria-label="刷新认证状态"
          @click="refreshApplication"
        >
          <RefreshCw :size="20" aria-hidden="true" />
        </button>
      </template>
    </DetailHeader>

    <ion-content class="mobile-publish-content">
      <main class="mobile-publish-shell application-shell">
        <FeedSkeleton v-if="loading" :count="4" />
        <StatePanel
          v-else-if="loadError"
          tone="error"
          title="认证状态加载失败"
          :description="loadError"
          action-label="重新加载"
          @action="loadApplication"
        />

        <template v-else>
          <section class="mobile-publish-intro">
            <span><Camera :size="22" aria-hidden="true" /></span>
            <div>
              <h1>成为平台认证摄影师</h1>
              <p>提交服务资料和代表作品。审核通过后，可发布摄影方案、响应企划并管理真实档期。</p>
            </div>
          </section>

          <ol class="application-stepper" aria-label="摄影师认证进度">
            <li
              v-for="(stage, index) in stages"
              :key="stage.title"
              :class="stageState(index)"
            >
              <span>
                <Check v-if="stageState(index) === 'complete'" :size="16" aria-hidden="true" />
                <X v-else-if="stageState(index) === 'rejected'" :size="16" aria-hidden="true" />
                <template v-else>{{ index + 1 }}</template>
              </span>
              <div><strong>{{ stage.title }}</strong><small>{{ stage.description }}</small></div>
            </li>
          </ol>

          <section class="status-card" :class="statusTone" aria-live="polite">
            <span class="status-icon" aria-hidden="true">
              <BadgeCheck v-if="isApproved" :size="24" />
              <CircleAlert v-else-if="application?.status === 'rejected'" :size="24" />
              <Clock3 v-else-if="application" :size="24" />
              <FileCheck2 v-else :size="24" />
            </span>
            <div>
              <div class="status-title-row">
                <h2>{{ statusTitle }}</h2>
                <span>{{ statusLabel }}</span>
              </div>
              <p>{{ statusDescription }}</p>
              <small v-if="applicationTimestamp">最近更新：{{ applicationTimestamp }}</small>
            </div>
          </section>

          <section v-if="application?.status === 'rejected' && application.review_note" class="review-note" role="alert">
            <CircleAlert :size="21" aria-hidden="true" />
            <div>
              <strong>审核意见</strong>
              <p>{{ application.review_note }}</p>
            </div>
          </section>

          <section v-if="isApproved" class="approved-panel">
            <div class="approved-seal"><BadgeCheck :size="34" aria-hidden="true" /></div>
            <h2>摄影师能力已经开通</h2>
            <p>你的认证资料已通过审核。现在可以完善服务地区与档期、创建可预约方案，并在企划中提交应邀。</p>
            <div class="approved-actions">
              <button type="button" class="pressable" @click="router.push({ name: 'photographer-settings' })">
                <CalendarRange :size="19" aria-hidden="true" />设置档期与服务
              </button>
              <button type="button" class="pressable" @click="router.push({ name: 'package-management' })">
                <PanelsTopLeft :size="19" aria-hidden="true" />管理摄影方案
              </button>
            </div>
          </section>

          <section v-else-if="application && !showForm" class="submitted-materials">
            <header>
              <div>
                <span>当前审核材料</span>
                <h2>平台正在核对资料与作品</h2>
              </div>
              <button type="button" class="edit-materials pressable" @click="beginEditing">
                <Pencil :size="17" aria-hidden="true" />更新资料
              </button>
            </header>

            <dl class="material-summary">
              <div><dt>服务地区</dt><dd>{{ application.location || '未填写' }}</dd></div>
              <div><dt>设备信息</dt><dd>{{ application.equipment || '未填写' }}</dd></div>
              <div class="wide"><dt>摄影师介绍</dt><dd>{{ application.profile_intro || '未填写' }}</dd></div>
              <div class="wide">
                <dt>风格领域</dt>
                <dd class="summary-tags">
                  <span v-for="style in application.styles" :key="style">{{ style }}</span>
                  <span v-if="!application.styles.length">未填写</span>
                </dd>
              </div>
            </dl>

            <div class="submitted-work-section">
              <strong>代表作品 · {{ existingPortfolio.length }}</strong>
              <div class="submitted-work-grid">
                <article v-for="(reference, index) in existingPortfolio" :key="referenceKey(reference, index)">
                  <img
                    v-if="referencePreview(reference)"
                    :src="referencePreview(reference)"
                    :alt="reference.title || `代表作品 ${index + 1}`"
                  />
                  <span v-else class="work-placeholder"><ImageIcon :size="24" aria-hidden="true" /></span>
                  <small>{{ reference.title || `代表作品 ${index + 1}` }}</small>
                </article>
              </div>
            </div>

            <p class="pending-help">审核期间可以更新资料；重新提交后，平台将以最新版本为准。</p>
          </section>

          <form v-else class="mobile-publish-form" novalidate @submit.prevent="submitApplication">
            <section class="publish-section">
              <header class="publish-section-heading">
                <span>1</span>
                <div><h2>服务与经历</h2><p>让审核人员快速了解你的服务范围和专业准备。</p></div>
              </header>

              <div class="publish-field">
                <label for="application-profile-intro">摄影师介绍 <span>必填，最多 1000 字</span></label>
                <textarea
                  id="application-profile-intro"
                  v-model="form.profileIntro"
                  class="publish-textarea"
                  rows="7"
                  maxlength="1000"
                  placeholder="介绍拍摄经验、擅长题材、服务方式，以及希望合作的项目类型"
                  :disabled="submitting"
                  :aria-invalid="Boolean(errors.profileIntro)"
                  @blur="validateField('profileIntro')"
                />
                <p v-if="errors.profileIntro" class="publish-error" role="alert">{{ errors.profileIntro }}</p>
                <p class="publish-help">{{ form.profileIntro.length }}/1000</p>
              </div>

              <div class="publish-field">
                <label for="application-location">主要服务地区 <span>必填</span></label>
                <input
                  id="application-location"
                  v-model="form.location"
                  class="publish-input"
                  maxlength="255"
                  placeholder="例如：中国大陆 · 四川省 · 成都市"
                  :disabled="submitting"
                  :aria-invalid="Boolean(errors.location)"
                  @blur="validateField('location')"
                />
                <p v-if="errors.location" class="publish-error" role="alert">{{ errors.location }}</p>
              </div>

              <div class="publish-field">
                <label for="application-equipment">设备信息 <span>必填，最多 500 字</span></label>
                <textarea
                  id="application-equipment"
                  v-model="form.equipment"
                  class="publish-textarea equipment-field"
                  rows="4"
                  maxlength="500"
                  placeholder="例如：Sony A7 IV、35mm F1.4、85mm F1.8、双灯系统"
                  :disabled="submitting"
                  :aria-invalid="Boolean(errors.equipment)"
                  @blur="validateField('equipment')"
                />
                <p v-if="errors.equipment" class="publish-error" role="alert">{{ errors.equipment }}</p>
                <p class="publish-help">{{ form.equipment.length }}/500</p>
              </div>
            </section>

            <section class="publish-section">
              <header class="publish-section-heading">
                <span>2</span>
                <div><h2>风格领域</h2><p>使用清晰、可检索的标签描述你稳定输出的风格。</p></div>
              </header>

              <div class="publish-field">
                <label for="application-styles-input">擅长风格 <span>至少 1 个，最多 12 个</span></label>
                <TagEditor
                  :model-value="form.styles"
                  input-id="application-styles-input"
                  placeholder="例如：自然光、人像、婚礼、纪实"
                  :disabled="submitting"
                  @update:model-value="updateStyles"
                  @limit="toastMessage = '最多添加 12 个风格标签。'"
                />
                <p v-if="errors.styles" class="publish-error" role="alert">{{ errors.styles }}</p>
              </div>
            </section>

            <section id="application-portfolio-section" class="publish-section" tabindex="-1">
              <header class="publish-section-heading">
                <span>3</span>
                <div><h2>代表作品</h2><p>至少 1 个，建议选择能体现稳定风格与完成度的真实成片。</p></div>
              </header>

              <div v-if="existingPortfolio.length" class="application-existing-grid">
                <article v-for="(reference, index) in existingPortfolio" :key="referenceKey(reference, index)">
                  <img
                    v-if="referencePreview(reference)"
                    :src="referencePreview(reference)"
                    :alt="reference.title || `已提交作品 ${index + 1}`"
                  />
                  <span v-else class="work-placeholder"><ImageIcon :size="24" aria-hidden="true" /></span>
                  <button
                    type="button"
                    class="remove-application-work pressable"
                    :disabled="submitting"
                    :aria-label="`移除已提交作品 ${index + 1}`"
                    @click="removeExistingReference(index)"
                  >
                    <X :size="18" aria-hidden="true" />
                  </button>
                  <small>{{ reference.title || `代表作品 ${index + 1}` }}</small>
                </article>
              </div>

              <PublishMediaPicker
                v-if="existingPortfolio.length < MAX_APPLICATION_PORTFOLIO_ITEMS"
                v-model:files="portfolioFiles"
                input-id="application-portfolio-files"
                mode="image"
                :image-limit="MAX_APPLICATION_PORTFOLIO_ITEMS"
                :existing-count="existingPortfolio.length"
                :disabled="submitting"
                :hint="`总计最多 ${MAX_APPLICATION_PORTFOLIO_ITEMS} 个；支持 JPG、PNG、WebP，单张最大 10 MB`"
                @error="handlePickerError"
              />
              <p v-else class="publish-help">已达到 {{ MAX_APPLICATION_PORTFOLIO_ITEMS }} 个上限；移除现有作品后可重新选择。</p>
              <p v-if="errors.portfolio" class="publish-error" role="alert">{{ errors.portfolio }}</p>
              <p class="publish-help">已保留 {{ existingPortfolio.length }} 个，新选择 {{ portfolioFiles.length }} 张。</p>
            </section>

            <div class="application-consent">
              <ShieldCheck :size="20" aria-hidden="true" />
              <p>提交即表示以上资料和作品由你本人提供或已取得展示授权。审核通过后，介绍、地区、设备、风格和作品会同步到摄影师档案。</p>
            </div>

            <div v-if="requestError" class="publish-request-error" role="alert">
              <CircleAlert :size="19" aria-hidden="true" />{{ requestError }}
            </div>
            <div v-if="submitting" class="publish-progress" aria-live="polite">
              <div><i :style="{ '--progress': `${uploadProgress}%` }" /></div>
              <span>{{ progressText }}</span>
            </div>
          </form>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="2800"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <ion-footer v-if="showFooter" class="mobile-publish-footer">
      <div class="mobile-publish-actions" :class="{ single: !application || application.status === 'rejected' }">
        <button
          v-if="application && application.status !== 'rejected'"
          type="button"
          class="pressable"
          :disabled="submitting"
          @click="cancelEditing"
        >
          <RotateCcw :size="18" aria-hidden="true" />取消修改
        </button>
        <button type="button" class="pressable" :disabled="submitting" @click="submitApplication">
          <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
          <Send v-else :size="18" aria-hidden="true" />{{ submitLabel }}
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import {
  IonContent,
  IonFooter,
  IonPage,
  IonSpinner,
  IonToast,
  alertController,
  onIonViewWillEnter,
} from '@ionic/vue'
import {
  BadgeCheck,
  CalendarRange,
  Camera,
  Check,
  CircleAlert,
  Clock3,
  FileCheck2,
  Image as ImageIcon,
  PanelsTopLeft,
  Pencil,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldCheck,
  X,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PublishMediaPicker from '@/components/PublishMediaPicker.vue'
import StatePanel from '@/components/StatePanel.vue'
import TagEditor from '@/components/TagEditor.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  getMyPhotographerApplication,
  submitMyPhotographerApplication,
  uploadPhotographerApplicationWorks,
} from '@/api/photographerApplications'
import { useAuthStore } from '@/stores/auth'
import type {
  PhotographerApplication,
  PhotographerApplicationFormFields,
  PhotographerPortfolioReference,
} from '@/types/photographerApplication'
import {
  MAX_APPLICATION_PORTFOLIO_ITEMS,
  emptyPhotographerApplicationErrors,
  hydratePhotographerApplicationFields,
  normalizePortfolioReferences,
  photographerApplicationStatusLabel,
  portfolioReferencePreview,
  validateApplicationEquipment,
  validateApplicationIntro,
  validateApplicationLocation,
  validateApplicationPortfolio,
  validateApplicationStyles,
  validatePhotographerApplication,
} from '@/utils/photographerApplication'
import { resolveMediaUrl } from '@/utils/media'

type ApplicationField = keyof ReturnType<typeof emptyPhotographerApplicationErrors>

const router = useRouter()
const auth = useAuthStore()
const application = ref<PhotographerApplication | null>(null)
const form = reactive<PhotographerApplicationFormFields>(hydratePhotographerApplicationFields(null))
const errors = reactive(emptyPhotographerApplicationErrors())
const existingPortfolio = ref<PhotographerPortfolioReference[]>([])
const portfolioFiles = ref<File[]>([])
const loading = ref(true)
const loadError = ref('')
const requestError = ref('')
const toastMessage = ref('')
const submitting = ref(false)
const editMode = ref(true)
const uploadProgress = ref(0)
const progressText = ref('正在准备提交…')
const initialSignature = ref('')

const stages = [
  { title: '提交资料', description: '服务信息与代表作品' },
  { title: '平台审核', description: '核对真实性与完整度' },
  { title: '开通能力', description: '方案、档期与应邀' },
]

const isApproved = computed(() => auth.isPhotographer || application.value?.status === 'approved')
const showForm = computed(() => !isApproved.value && (
  !application.value || application.value.status === 'rejected' || editMode.value
))
const showFooter = computed(() => showForm.value && !loading.value && !loadError.value)
const statusLabel = computed(() => photographerApplicationStatusLabel(isApproved.value ? 'approved' : application.value?.status))
const statusTone = computed(() => {
  if (isApproved.value) return 'approved'
  if (application.value?.status === 'rejected') return 'rejected'
  if (application.value) return 'pending'
  return 'draft'
})
const statusTitle = computed(() => {
  if (isApproved.value) return '认证已通过'
  if (application.value?.status === 'rejected') return '申请需要修改'
  if (application.value) return '资料正在审核中'
  return '尚未提交认证申请'
})
const statusDescription = computed(() => {
  if (isApproved.value) return '平台已开通摄影师角色和经营能力，可以继续完善服务资料。'
  if (application.value?.status === 'rejected') return '请根据审核意见修改资料或作品，重新提交后会再次进入审核。'
  if (application.value) return '平台将核对资料与代表作品。更新申请后，审核会以最新内容为准。'
  return '完成下方资料并提交后，可在这里持续查看审核状态。'
})
const submitLabel = computed(() => {
  if (application.value?.status === 'rejected') return '重新提交认证'
  if (application.value) return '更新审核资料'
  return '提交认证申请'
})
const applicationTimestamp = computed(() => formatDateTime(
  application.value?.updated_at || application.value?.created_at,
))
const currentSignature = computed(() => JSON.stringify({
  profileIntro: form.profileIntro,
  location: form.location,
  equipment: form.equipment,
  styles: form.styles,
  portfolio: existingPortfolio.value,
  files: portfolioFiles.value.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
}))
const isDirty = computed(() => showForm.value && Boolean(initialSignature.value) && currentSignature.value !== initialSignature.value)

function stageState(index: number): 'complete' | 'current' | 'rejected' | 'upcoming' {
  if (isApproved.value) return 'complete'
  if (application.value?.status === 'rejected') {
    if (index === 0) return 'complete'
    return index === 1 ? 'rejected' : 'upcoming'
  }
  if (application.value) {
    if (index === 0) return 'complete'
    return index === 1 ? 'current' : 'upcoming'
  }
  return index === 0 ? 'current' : 'upcoming'
}

function formatDateTime(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function clearErrors() {
  Object.assign(errors, emptyPhotographerApplicationErrors())
}

function markClean() {
  initialSignature.value = currentSignature.value
}

function hydrateApplication(nextApplication: PhotographerApplication | null) {
  const fields = hydratePhotographerApplicationFields(nextApplication)
  form.profileIntro = fields.profileIntro
  form.location = fields.location
  form.equipment = fields.equipment
  form.styles = fields.styles
  existingPortfolio.value = normalizePortfolioReferences(nextApplication?.portfolio_refs)
  portfolioFiles.value = []
  requestError.value = ''
  clearErrors()
  markClean()
}

async function loadApplication() {
  loading.value = true
  loadError.value = ''
  try {
    await auth.initialize()
    const payload = await getMyPhotographerApplication()
    application.value = payload
    editMode.value = !payload || payload.status === 'rejected'
    hydrateApplication(payload)
    if (payload?.status === 'approved' && !auth.isPhotographer) {
      await auth.loadCurrentUser().catch(() => undefined)
    }
  } catch (error) {
    if (auth.isPhotographer) {
      application.value = null
      editMode.value = false
      hydrateApplication(null)
    } else {
      loadError.value = getApiErrorMessage(error)
    }
  } finally {
    loading.value = false
  }
}

async function refreshApplication() {
  if (isDirty.value && !(await confirmDiscard('刷新会丢失当前未提交的修改。'))) return
  await loadApplication()
}

function beginEditing() {
  editMode.value = true
  hydrateApplication(application.value)
}

async function cancelEditing() {
  if (isDirty.value && !(await confirmDiscard('取消后，本次修改和新选择的图片不会保留。'))) return
  hydrateApplication(application.value)
  editMode.value = false
}

async function confirmDiscard(message: string): Promise<boolean> {
  const alert = await alertController.create({
    header: '放弃未保存修改？',
    message,
    buttons: [
      { text: '继续编辑', role: 'cancel' },
      { text: '放弃修改', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'destructive'
}

function updateStyles(value: string[]) {
  form.styles = value
  if (errors.styles) errors.styles = validateApplicationStyles(value)
}

function validateField(field: ApplicationField): boolean {
  if (field === 'profileIntro') errors.profileIntro = validateApplicationIntro(form.profileIntro)
  if (field === 'location') errors.location = validateApplicationLocation(form.location)
  if (field === 'equipment') errors.equipment = validateApplicationEquipment(form.equipment)
  if (field === 'styles') errors.styles = validateApplicationStyles(form.styles)
  if (field === 'portfolio') {
    errors.portfolio = validateApplicationPortfolio(existingPortfolio.value.length + portfolioFiles.value.length)
  }
  return !errors[field]
}

function validateForm(): boolean {
  Object.assign(
    errors,
    validatePhotographerApplication(
      form,
      existingPortfolio.value.length + portfolioFiles.value.length,
    ),
  )
  const fieldOrder: Array<[ApplicationField, string]> = [
    ['profileIntro', 'application-profile-intro'],
    ['location', 'application-location'],
    ['equipment', 'application-equipment'],
    ['styles', 'application-styles-input'],
    ['portfolio', 'application-portfolio-section'],
  ]
  const firstError = fieldOrder.find(([field]) => Boolean(errors[field]))
  if (firstError) document.getElementById(firstError[1])?.focus()
  return !firstError
}

function handlePickerError(message: string) {
  requestError.value = message
  errors.portfolio = validateApplicationPortfolio(existingPortfolio.value.length + portfolioFiles.value.length)
}

function removeExistingReference(index: number) {
  existingPortfolio.value = existingPortfolio.value.filter((_, itemIndex) => itemIndex !== index)
  if (errors.portfolio) validateField('portfolio')
}

function referencePreview(reference: PhotographerPortfolioReference): string {
  return resolveMediaUrl(portfolioReferencePreview(reference))
}

function referenceKey(reference: PhotographerPortfolioReference, index: number): string {
  return String(reference.id || reference.url || `${reference.title || 'work'}-${index}`)
}

async function confirmPendingUpdate(): Promise<boolean> {
  if (application.value?.status !== 'pending') return true
  const alert = await alertController.create({
    header: '更新审核资料',
    message: '提交后平台将以最新资料和作品继续审核。确认替换当前审核版本吗？',
    buttons: [
      { text: '继续编辑', role: 'cancel' },
      { text: '确认更新', role: 'confirm' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'confirm'
}

async function submitApplication() {
  if (submitting.value || !validateForm() || !(await confirmPendingUpdate())) return
  submitting.value = true
  requestError.value = ''
  uploadProgress.value = portfolioFiles.value.length ? 2 : 76
  progressText.value = portfolioFiles.value.length ? '正在上传代表作品…' : '正在提交认证资料…'

  try {
    if (portfolioFiles.value.length) {
      const uploaded = await uploadPhotographerApplicationWorks(
        portfolioFiles.value,
        { description: form.profileIntro.trim(), tags: form.styles },
        (percent) => {
          uploadProgress.value = Math.max(2, Math.round(percent * 0.72))
        },
      )
      existingPortfolio.value = [...existingPortfolio.value, ...uploaded]
      portfolioFiles.value = []
    }

    uploadProgress.value = 84
    progressText.value = application.value ? '正在更新认证申请…' : '正在提交认证申请…'
    const submitted = await submitMyPhotographerApplication({
      profile_intro: form.profileIntro.trim(),
      location: form.location.trim(),
      equipment: form.equipment.trim(),
      styles: [...form.styles],
      portfolio_refs: [...existingPortfolio.value],
    })
    uploadProgress.value = 100
    application.value = submitted
    editMode.value = false
    hydrateApplication(submitted)
    toastMessage.value = '认证申请已提交，请留意审核状态。'
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!isDirty.value && !submitting.value) return
  event.preventDefault()
  event.returnValue = ''
}

onBeforeRouteLeave(async () => {
  if (submitting.value) {
    toastMessage.value = '认证资料正在提交，请稍候。'
    return false
  }
  if (!isDirty.value) return true
  return confirmDiscard('离开后，本次修改和新选择的图片不会保留。')
})

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onIonViewWillEnter(() => {
  void loadApplication()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.header-action { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; border-radius: 50%; background: transparent; color: var(--ink); }
.header-action:disabled { color: var(--ink-tertiary); opacity: .6; }
.application-shell { gap: var(--space-4); }
.application-stepper { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); list-style: none; }
.application-stepper li { position: relative; display: grid; justify-items: center; gap: var(--space-2); min-width: 0; color: var(--ink-tertiary); text-align: center; }
.application-stepper li::after { position: absolute; top: 17px; left: calc(50% + 23px); width: calc(100% - 46px); height: 1px; background: var(--divider); content: ''; }
.application-stepper li:last-child::after { display: none; }
.application-stepper li > span { z-index: 1; display: grid; width: 34px; height: 34px; place-items: center; border: 0; border-radius: 50%; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); font-size: var(--text-xs); font-weight: 800; }
.application-stepper li > div { display: grid; gap: 3px; min-width: 0; }
.application-stepper strong { color: inherit; font-size: var(--text-xs); }
.application-stepper small { color: var(--ink-tertiary); font-size: 11px; line-height: 1.35; }
.application-stepper .complete, .application-stepper .current { color: var(--brand); }
.application-stepper .complete > span { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); border: 0; }
.application-stepper .complete::after { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); }
.application-stepper .current > span { border-color: var(--brand); background: var(--brand-soft); }
.application-stepper .rejected { color: var(--danger); }
.application-stepper .rejected > span { border-color: var(--danger); background: #fbefed; }
.status-card { display: grid; grid-template-columns: 48px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 0; border-left-width: 4px; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.status-card.draft { border-left-color: var(--ink-tertiary); }
.status-card.pending { border-left-color: var(--warning); }
.status-card.rejected { border-left-color: var(--danger); }
.status-card.approved { border-left-color: var(--brand); }
.status-icon { display: grid; width: 44px; height: 44px; place-items: center; border-radius: 50%; background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); }
.pending .status-icon { background: #f6ecdc; color: var(--warning); }
.rejected .status-icon { background: #fbefed; color: var(--danger); }
.approved .status-icon { background: var(--brand-soft); color: var(--brand); }
.status-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.status-title-row h2 { margin: 1px 0 4px; font-family: var(--font-serif); font-size: var(--text-lg); }
.status-title-row > span { flex: 0 0 auto; padding: 4px 9px; border-radius: var(--radius-pill); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); font-size: 11px; font-weight: 800; }
.pending .status-title-row > span { background: #f6ecdc; color: var(--warning); }
.rejected .status-title-row > span { background: #fbefed; color: var(--danger); }
.approved .status-title-row > span { background: var(--brand-soft); color: var(--brand); }
.status-card p { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.6; }
.status-card small { display: block; margin-top: 6px; color: var(--ink-tertiary); font-size: 11px; }
.review-note { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-4); border: 1px solid rgba(163, 59, 50, .3); border-radius: var(--radius-md); background: #fbefed; color: var(--danger); }
.review-note svg { flex: 0 0 auto; }
.review-note strong { color: var(--ink); font-size: var(--text-sm); }
.review-note p { margin: 5px 0 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; white-space: pre-wrap; }
.approved-panel { display: grid; justify-items: center; padding: var(--space-8) var(--space-5); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); text-align: center; }
.approved-seal { display: grid; width: 68px; height: 68px; margin-bottom: var(--space-4); place-items: center; border-radius: 50%; background: var(--brand-soft); color: var(--brand); }
.approved-panel h2 { margin: 0 0 var(--space-2); font-family: var(--font-serif); font-size: var(--text-xl); }
.approved-panel > p { max-width: 500px; margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.7; }
.approved-actions { display: grid; width: 100%; gap: var(--space-3); margin-top: var(--space-6); }
.approved-actions button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); font-weight: 750; }
.approved-actions button:last-child { background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
.submitted-materials { display: grid; gap: var(--space-5); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.submitted-materials > header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); }
.submitted-materials header span { color: var(--brand); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.submitted-materials header h2 { margin: 4px 0 0; font-size: var(--text-base); }
.edit-materials { display: inline-flex; min-height: var(--touch-target); flex: 0 0 auto; align-items: center; gap: 6px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); font-size: var(--text-xs); font-weight: 750; }
.material-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); margin: 0; }
.material-summary > div { min-width: 0; }
.material-summary .wide { grid-column: 1 / -1; }
.material-summary dt { color: var(--ink-tertiary); font-size: var(--text-xs); }
.material-summary dd { margin: 5px 0 0; color: var(--ink); font-size: var(--text-sm); line-height: 1.65; white-space: pre-wrap; }
.summary-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.summary-tags span { display: inline-flex; min-height: 28px; align-items: center; padding: 3px 9px; border: 0; border-radius: var(--radius-pill); background: var(--brand-soft); box-shadow: var(--neu-raise-sm); font-size: var(--text-xs); }
.submitted-work-section { display: grid; gap: var(--space-3); }
.submitted-work-section > strong { font-size: var(--text-sm); }
.submitted-work-grid, .application-existing-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.submitted-work-grid article, .application-existing-grid article { position: relative; min-width: 0; overflow: hidden; aspect-ratio: 1 / 1; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.submitted-work-grid img, .application-existing-grid img { width: 100%; height: 100%; object-fit: cover; }
.submitted-work-grid small, .application-existing-grid small { position: absolute; right: 0; bottom: 0; left: 0; overflow: hidden; padding: 24px 8px 7px; background: linear-gradient(transparent, rgba(26, 26, 26, .76)); color: var(--white); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.work-placeholder { display: grid; width: 100%; height: 100%; place-items: center; color: var(--ink-tertiary); }
.pending-help { margin: 0; padding: var(--space-3); border-left: 3px solid var(--warning); background: #f8f0e4; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.equipment-field { min-height: 106px; }
.application-existing-grid { margin-bottom: var(--space-3); }
.remove-application-work { position: absolute; top: 4px; right: 4px; display: grid; width: 48px; height: 48px; place-items: center; border: 0; border-radius: 50%; background: rgba(26, 26, 26, .7); color: var(--white); }
.remove-application-work:disabled { opacity: .6; }
.application-consent { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-4); border-left: 3px solid var(--brand); background: var(--brand-soft); color: var(--brand); }
.application-consent svg { flex: 0 0 auto; }
.application-consent p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.mobile-publish-actions.single { grid-template-columns: 1fr; }
@media (min-width: 640px) {
  .approved-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .submitted-work-grid, .application-existing-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 390px) {
  .application-stepper { padding-inline: var(--space-2); }
  .application-stepper small { display: none; }
  .submitted-materials > header { display: grid; }
  .edit-materials { width: 100%; justify-content: center; }
  .material-summary { grid-template-columns: 1fr; }
  .material-summary .wide { grid-column: auto; }
}
</style>
