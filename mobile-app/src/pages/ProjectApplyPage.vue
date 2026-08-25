<template>
  <ion-page>
    <DetailHeader title="响应拍摄企划" :default-href="`/projects/${route.params.projectId}`" />

    <ion-content class="mobile-publish-content">
      <main class="mobile-publish-shell">
        <FeedSkeleton v-if="loading" :count="3" />
        <StatePanel
          v-else-if="loadError"
          tone="error"
          title="应邀表单加载失败"
          :description="loadError"
          action-label="重新加载"
          @action="load"
        />
        <StatePanel
          v-else-if="blockedReason"
          :title="blockedTitle"
          :description="blockedReason"
          action-label="返回企划详情"
          @action="goProjectDetail"
        />

        <template v-else-if="project">
          <section class="mobile-publish-intro">
            <span><Send :size="22" aria-hidden="true" /></span>
            <div>
              <h1>{{ project.title }}</h1>
              <p>{{ formatProjectBudget(project) }} · {{ project.city }}。说明你的执行方式、报价和可交付内容。</p>
            </div>
          </section>

          <section v-if="myApplication" class="application-status-note" :class="myApplication.status">
            <CircleCheckBig v-if="myApplication.status === 'selected'" :size="20" aria-hidden="true" />
            <FileClock v-else :size="20" aria-hidden="true" />
            <div>
              <strong>当前状态：{{ applicationStatusLabel(myApplication.status) }}</strong>
              <p>{{ applicationStatusDescription }}</p>
            </div>
          </section>
          <section v-if="agentTask && !myApplication" class="agent-source-note" role="status">已载入 Agent 整理的申请信息，可直接在此修改。</section>

          <form class="mobile-publish-form" novalidate @submit.prevent="submitApplication">
            <section class="publish-section">
              <header class="publish-section-heading">
                <span>1</span>
                <div><h2>方案与报价</h2><p>报价被选中后会写入订单快照。</p></div>
              </header>

              <div v-if="availablePackages.length" class="publish-field">
                <label for="application-package">关联我的摄影方案 <span>选填</span></label>
                <select id="application-package" v-model="selectedPackageId" class="publish-select" :disabled="submitting" @change="applySelectedPackage">
                  <option value="">不关联标准方案</option>
                  <option v-for="offer in availablePackages" :key="offer.id" :value="offer.id">
                    {{ packageOptionLabel(offer) }}
                  </option>
                </select>
              </div>

              <div class="publish-field">
                <label for="application-package-snapshot">方案摘要 <span>选填</span></label>
                <input id="application-package-snapshot" v-model.trim="form.package_snapshot" class="publish-input" maxlength="500" placeholder="例如：城市人像半日方案，含精修 30 张" :disabled="submitting" />
              </div>

              <div class="publish-field">
                <label for="application-price">本次报价 <span>人民币元，必填</span></label>
                <input id="application-price" v-model.number="form.price_quote" type="number" inputmode="decimal" min="1" step="100" class="publish-input" :disabled="submitting" :aria-invalid="Boolean(errors.price_quote)" />
                <p v-if="errors.price_quote" class="publish-error" role="alert">{{ errors.price_quote }}</p>
              </div>
            </section>

            <section class="publish-section">
              <header class="publish-section-heading">
                <span>2</span>
                <div><h2>执行说明</h2><p>结合档期、场景、拍摄流程和交付方式提出可执行方案。</p></div>
              </header>

              <div class="publish-field">
                <label for="application-proposal">方案说明 <span>必填</span></label>
                <textarea id="application-proposal" v-model.trim="form.proposal_text" class="publish-textarea" rows="8" maxlength="2400" placeholder="说明你的拍摄思路、现场流程、预计成片、交付时间和与需求匹配的经验" :disabled="submitting" :aria-invalid="Boolean(errors.proposal_text)" @blur="validateProposal" />
                <p v-if="errors.proposal_text" class="publish-error" role="alert">{{ errors.proposal_text }}</p>
                <p class="publish-help">{{ form.proposal_text.length }}/2400</p>
              </div>

              <div class="publish-field">
                <label for="application-revision-note">条款事项 <span>选填</span></label>
                <textarea id="application-revision-note" v-model.trim="form.revision_note" class="publish-textarea" rows="5" maxlength="1200" placeholder="补充交通费用、版权范围、取消改期或超时拍摄规则" :disabled="submitting" />
              </div>
            </section>

            <section class="publish-section">
              <header class="publish-section-heading">
                <span>3</span>
                <div><h2>相关作品</h2><p>选填；最多 8 张，用实际成片证明风格和执行能力。</p></div>
              </header>

              <div v-if="existingPortfolioRefs.length" class="existing-reference-grid">
                <article v-for="(item, index) in existingPortfolioRefs" :key="`${item.url}-${index}`">
                  <img :src="resolveMediaUrl(item.thumbnail_url || item.url)" :alt="item.title || `已提交作品 ${index + 1}`" />
                  <button type="button" class="remove-reference pressable" :disabled="submitting" :aria-label="`移除已提交作品 ${index + 1}`" @click="removeExistingReference(index)">
                    <X :size="18" aria-hidden="true" />
                  </button>
                </article>
              </div>

              <PublishMediaPicker
                v-if="remainingImageSlots > 0"
                v-model:files="portfolioFiles"
                input-id="application-portfolio-files"
                mode="image"
                :image-limit="remainingImageSlots"
                :disabled="submitting"
                :hint="`还可添加 ${remainingImageSlots} 张；支持 JPG、PNG、WebP，单张最大 10 MB`"
                @error="requestError = $event"
              />
              <p v-else class="publish-help">已达到 8 张上限；移除现有图片后可重新选择。</p>
            </section>

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

      <ion-toast :is-open="Boolean(toastMessage)" :message="toastMessage" :duration="2600" position="bottom" @did-dismiss="toastMessage = ''" />
    </ion-content>

    <ion-footer v-if="project && !blockedReason && !loading" class="mobile-publish-footer">
      <div class="mobile-publish-actions" :class="{ single: !canWithdraw }">
        <button v-if="canWithdraw" type="button" class="withdraw-button pressable" :disabled="submitting" @click="withdrawApplication">
          <Undo2 :size="18" aria-hidden="true" />撤回应邀
        </button>
        <button type="button" class="pressable" :disabled="submitting" @click="submitApplication">
          <ion-spinner v-if="submitting" name="crescent" aria-hidden="true" />
          <Send v-else :size="18" aria-hidden="true" />{{ isUpdating ? '更新应邀方案' : '提交应邀方案' }}
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonFooter, IonPage, IonSpinner, IonToast, alertController } from '@ionic/vue'
import { CircleAlert, CircleCheckBig, FileClock, Send, Undo2, X } from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import PublishMediaPicker from '@/components/PublishMediaPicker.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { useAgentTaskHandoff } from '@/composables/useAgentTaskHandoff'
import { getPhotographerDetail, getProjectDetail } from '@/api/discovery'
import { uploadProjectImages } from '@/api/publishing'
import { applyToProject, updateMyProjectApplication, withdrawMyProjectApplication } from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import type {
  PackageOffer,
  ProjectApplication,
  ProjectBrief,
  ProjectPortfolioReference,
} from '@/types/discovery'
import { formatCurrency, formatDuration, formatProjectBudget, getPackageName } from '@/utils/format'
import { resolveMediaUrl } from '@/utils/media'

interface ApplicationFormState {
  proposal_text: string
  price_quote: number | ''
  package_snapshot: string
  revision_note: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const agentHandoff = useAgentTaskHandoff()
const agentTask = agentHandoff.task
const project = ref<ProjectBrief | null>(null)
const myApplication = ref<ProjectApplication | null>(null)
const availablePackages = ref<PackageOffer[]>([])
const selectedPackageId = ref('')
const existingPortfolioRefs = ref<ProjectPortfolioReference[]>([])
const portfolioFiles = ref<File[]>([])
const form = reactive<ApplicationFormState>({ proposal_text: '', price_quote: '', package_snapshot: '', revision_note: '' })
const errors = reactive<Record<string, string>>({})
const loading = ref(true)
const loadError = ref('')
const requestError = ref('')
const toastMessage = ref('')
const submitting = ref(false)
const uploadProgress = ref(0)
const progressText = ref('正在准备提交…')
let agentSyncTimer: number | null = null

const isOwner = computed(() => Boolean(project.value && auth.user?.id === project.value.customer_id))
const isUpdating = computed(() => myApplication.value?.status === 'submitted')
const canWithdraw = computed(() => isUpdating.value && project.value?.status === 'open')
const remainingImageSlots = computed(() => Math.max(0, 8 - existingPortfolioRefs.value.length))
const blockedTitle = computed(() => {
  if (!auth.isPhotographer) return '需要摄影师身份'
  if (isOwner.value) return '不能响应自己的企划'
  if (myApplication.value?.status === 'selected') return '你的方案已被选中'
  return '企划当前不可响应'
})
const blockedReason = computed(() => {
  if (!auth.isPhotographer) return '只有已认证摄影师账号可以提交应邀方案；客户账号可继续发布和管理自己的企划。'
  if (isOwner.value) return '这是你自己发布的企划，可返回详情查看摄影师响应。'
  if (myApplication.value?.status === 'selected') return '客户已经选定你的方案，后续安排请进入生成的订单查看。'
  if (project.value?.status !== 'open') return '这个企划已经截止、关闭或转为订单，不能再提交或修改方案。'
  return ''
})
const applicationStatusDescription = computed(() => ({
  submitted: '客户尚未作出选择，你可以继续修改或撤回方案。',
  selected: '客户已选定你的方案，企划会转为一笔待确认订单。',
  rejected: '客户选择了其他方案；若企划仍开放，可重新提交更新后的方案。',
  withdrawn: '方案已撤回；若企划仍开放，可以重新提交。',
}[myApplication.value?.status || ''] || '可根据当前企划状态继续处理。'))

function validateProposal() {
  errors.proposal_text = form.proposal_text.trim() ? '' : '请填写可执行的方案说明。'
  return !errors.proposal_text
}

function validateForm() {
  Object.keys(errors).forEach((key) => { errors[key] = '' })
  validateProposal()
  if (form.price_quote === '' || Number(form.price_quote) <= 0) errors.price_quote = '报价必须大于 0 元。'
  const firstError = Object.entries(errors).find(([, message]) => message)
  if (firstError) document.getElementById(`application-${firstError[0].replaceAll('_', '-')}`)?.focus()
  return !firstError
}

function hydrateApplication(application: ProjectApplication | null) {
  if (!application) return
  form.proposal_text = application.proposal_text || ''
  form.price_quote = application.price_quote || ''
  form.package_snapshot = application.package_snapshot || ''
  form.revision_note = application.revision_note || ''
  existingPortfolioRefs.value = Array.isArray(application.portfolio_refs)
    ? application.portfolio_refs.filter((item) => Boolean(item?.url)).slice(0, 8)
    : []
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    await auth.initialize()
    const payload = await getProjectDetail(Number(route.params.projectId))
    project.value = payload.project
    myApplication.value = payload.my_application || null
    hydrateApplication(myApplication.value)
    if (!myApplication.value) {
      const task = await agentHandoff.load('project_application')
      if (task) {
        form.proposal_text = String(task.fields.proposal_text || '')
        form.price_quote = typeof task.fields.price_quote === 'number' ? task.fields.price_quote : ''
        form.package_snapshot = String(task.fields.package_snapshot || '')
        form.revision_note = String(task.fields.revision_note || '')
      }
    }
    if (auth.isPhotographer && auth.user) {
      try {
        const profile = await getPhotographerDetail(auth.user.id)
        availablePackages.value = profile.packages || []
      } catch {
        availablePackages.value = []
      }
    }
  } catch (error) {
    loadError.value = getApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

function applySelectedPackage() {
  const offer = availablePackages.value.find((item) => String(item.id) === selectedPackageId.value)
  if (!offer) return
  form.package_snapshot = `${getPackageName(offer)} · ${formatCurrency(offer.price)} · ${formatDuration(offer.duration)}`
  form.price_quote = Number(offer.price)
}

function taskOperation(field: string, value: unknown) {
  const empty = value === '' || value === null || value === undefined || (Array.isArray(value) && !value.length)
  return empty ? { field, op: 'clear' as const } : { field, op: 'set' as const, value }
}

function scheduleAgentSync() {
  if (!route.query.agentTaskId || myApplication.value) return
  if (agentSyncTimer !== null) window.clearTimeout(agentSyncTimer)
  agentSyncTimer = window.setTimeout(() => {
    void agentHandoff.saveOperations([
      taskOperation('proposal_text', form.proposal_text.trim()),
      taskOperation('price_quote', form.price_quote === '' ? null : Number(form.price_quote)),
      taskOperation('package_snapshot', form.package_snapshot.trim()),
      taskOperation('revision_note', form.revision_note.trim()),
    ]).catch((error) => {
      requestError.value = getApiErrorMessage(error)
    })
  }, 450)
}

function packageOptionLabel(offer: PackageOffer) {
  return `${getPackageName(offer)} · ${formatCurrency(offer.price)}`
}

function removeExistingReference(index: number) {
  existingPortfolioRefs.value = existingPortfolioRefs.value.filter((_, itemIndex) => itemIndex !== index)
}

async function submitApplication() {
  if (!project.value || submitting.value || blockedReason.value || !validateForm()) return
  submitting.value = true
  requestError.value = ''
  uploadProgress.value = portfolioFiles.value.length ? 2 : 76
  progressText.value = portfolioFiles.value.length ? '正在上传相关作品…' : '正在提交应邀方案…'
  try {
    const uploadedUrls = await uploadProjectImages(portfolioFiles.value, (percent) => {
      uploadProgress.value = Math.round(percent * 0.72)
    })
    uploadProgress.value = 82
    progressText.value = isUpdating.value ? '正在更新应邀方案…' : '正在提交应邀方案…'
    const payload = {
      proposal_text: form.proposal_text.trim(),
      price_quote: Number(form.price_quote),
      package_snapshot: form.package_snapshot.trim() || null,
      portfolio_refs: [
        ...existingPortfolioRefs.value,
        ...uploadedUrls.map((url) => ({ url })),
      ],
      revision_note: form.revision_note.trim() || null,
    }
    if (isUpdating.value) await updateMyProjectApplication(project.value.id, payload)
    else await applyToProject(project.value.id, payload)
    uploadProgress.value = 100
    if (agentTask.value) await agentHandoff.complete({ project_id: project.value.id })
    await router.replace({
      name: 'project-detail',
      params: { projectId: project.value.id },
      query: { application: isUpdating.value ? 'updated' : 'submitted' },
    })
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

async function withdrawApplication() {
  if (!project.value || !canWithdraw.value || submitting.value) return
  const alert = await alertController.create({
    header: '撤回应邀方案',
    message: '撤回后客户将无法选定当前方案；只要企划仍开放，你还可以重新提交。',
    buttons: [{ text: '取消', role: 'cancel' }, { text: '确认撤回', role: 'destructive' }],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'destructive') return
  submitting.value = true
  try {
    await withdrawMyProjectApplication(project.value.id)
    await router.replace({
      name: 'project-detail',
      params: { projectId: project.value.id },
      query: { application: 'withdrawn' },
    })
  } catch (error) {
    requestError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

function applicationStatusLabel(status: string) {
  return ({ submitted: '已提交', selected: '已选中', rejected: '未选中', withdrawn: '已撤回' }[status] || status)
}

function goProjectDetail() {
  void router.replace({ name: 'project-detail', params: { projectId: route.params.projectId } })
}

onMounted(() => void load())
watch(() => ({ ...form }), scheduleAgentSync, { deep: true })
onUnmounted(() => { if (agentSyncTimer !== null) window.clearTimeout(agentSyncTimer) })
</script>

<style scoped>
.application-status-note { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-4); border-left: 3px solid var(--brand); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
.application-status-note.selected { border-left-color: var(--brand); color: var(--brand); }
.application-status-note svg { flex: 0 0 auto; }
.application-status-note strong { display: block; color: var(--ink); font-size: var(--text-sm); }
.application-status-note p { margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.existing-reference-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.existing-reference-grid article { position: relative; overflow: hidden; aspect-ratio: 1 / 1; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.existing-reference-grid img { width: 100%; height: 100%; object-fit: cover; }
.remove-reference { position: absolute; top: 4px; right: 4px; display: grid; width: 44px; height: 44px; place-items: center; border: 0; border-radius: 50%; background: rgba(26, 26, 26, .68); color: var(--white); }
.mobile-publish-actions.single { grid-template-columns: 1fr; }
.mobile-publish-actions .withdraw-button { border-color: rgba(163, 59, 50, .38); color: var(--danger); }
</style>
