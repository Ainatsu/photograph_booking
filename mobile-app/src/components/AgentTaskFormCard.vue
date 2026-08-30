<template>
  <section class="agent-form-card" :aria-busy="busy || uploading">
    <header class="form-card-header">
      <div>
        <span class="form-card-kicker">Agent 任务</span>
        <h3>{{ taskTypeLabel(card.task_type) }}</h3>
      </div>
      <span class="form-card-status" :class="`status--${card.status}`">{{ statusLabel(card.status) }}</span>
    </header>

    <div v-if="card.status === 'published'" class="result-banner" role="status">
      <CheckCircle2 :size="17" aria-hidden="true" />
      <span>已完成，业务结果已保存。</span>
    </div>
    <div v-if="card.status === 'draft_unavailable'" class="notice-banner" role="status">
      <Info :size="17" aria-hidden="true" />
      <span>草稿箱暂未开放，内容仍保留在这张卡片中。</span>
    </div>
    <div v-if="card.field_errors?._form" class="error-summary" role="alert">
      <CircleAlert :size="17" aria-hidden="true" />
      <span>{{ card.field_errors._form }}</span>
    </div>

    <form class="form-card-body" @submit.prevent="submit('publish')">
      <fieldset :disabled="busy || uploading || !isEditable">
        <legend class="sr-only">{{ taskTypeLabel(card.task_type) }}字段</legend>
        <div class="field-grid">
          <label v-for="field in visibleFields" :key="field.key" class="form-field" :class="{ 'field-wide': field.type === 'textarea' }">
            <span class="field-label">{{ field.label }}<b v-if="field.required" aria-hidden="true"> *</b></span>
            <textarea
              v-if="field.type === 'textarea'"
              :value="displayValue(field.key)"
              :maxlength="field.max"
              rows="3"
              @input="setField(field.key, eventValue($event))"
            />
            <select
              v-else-if="field.type === 'select'"
              :value="displayValue(field.key)"
              @change="setField(field.key, eventValue($event))"
            >
              <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
            <input
              v-else
              :type="field.type === 'tags' ? 'text' : field.type"
              :min="field.min"
              :max="field.max"
              :value="displayValue(field.key)"
              @input="setField(field.key, eventValue($event))"
            />
            <small v-if="field.help" class="field-help">{{ field.help }}</small>
            <span v-if="card.field_errors?.[field.key]" class="field-error" role="alert">{{ card.field_errors[field.key] }}</span>
          </label>
        </div>

        <div v-if="supportsMedia" class="media-field">
          <div class="field-label">{{ mediaLabel }}</div>
          <div class="media-list">
            <span v-for="url in mediaRefs" :key="url" class="media-chip">{{ mediaName(url) }}</span>
          </div>
          <label class="media-picker pressable">
            <ImagePlus :size="17" aria-hidden="true" />
            <span>{{ uploading ? '正在上传…' : '添加图片' }}</span>
            <input type="file" accept="image/*" multiple @change="uploadMedia" />
          </label>
        </div>

        <div v-if="card.task_type === 'create_booking' && hasBookingTarget" class="availability-field">
          <div class="field-heading">
            <span class="field-label">可预约日期</span>
            <span v-if="loadingAvailability" class="field-help">正在加载</span>
          </div>
          <div v-if="availabilityError" class="field-error" role="alert">{{ availabilityError }}</div>
          <div v-else class="date-list">
            <button
              v-for="day in availableDays"
              :key="day.date"
              type="button"
              class="date-option pressable"
              :class="{ selected: form.appointment_date === day.date }"
              :disabled="!day.bookable"
              @click="setField('appointment_date', day.date)"
            >
              <strong>{{ formatDateLabel(day) }}</strong>
              <small>{{ day.bookable ? '可预约' : day.unavailable_reason || '暂不可约' }}</small>
            </button>
          </div>
          <p v-if="!loadingAvailability && !availableDays.some((day) => day.bookable)" class="field-help">当前没有可预约日期，请稍后重试。</p>
        </div>
      </fieldset>

      <div class="form-card-footer">
        <button v-if="isEditable" type="submit" class="action-primary pressable" :disabled="busy || uploading">
          <LoaderCircle v-if="busy" :size="17" class="spin" aria-hidden="true" />
          <CheckCircle2 v-else :size="17" aria-hidden="true" />
          {{ busy ? '提交中…' : primaryActionLabel(card.task_type) }}
        </button>
        <button v-if="isEditable && card.actions.includes('save_draft')" type="button" class="action-secondary pressable" :disabled="busy || uploading" @click="submit('save_draft')">
          <Save :size="17" aria-hidden="true" />
          保存草稿
        </button>
        <button v-if="isEditable" type="button" class="action-danger pressable" :disabled="busy || uploading" @click="cancel">
          <X :size="17" aria-hidden="true" />
          取消{{ card.task_type === 'create_booking' ? '预约' : '发布' }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { CircleAlert, CheckCircle2, ImagePlus, Info, LoaderCircle, Save, X } from 'lucide-vue-next'
import { getApiErrorMessage } from '@/api/client'
import { getAvailableSlots } from '@/api/orders'
import { uploadAIImage } from '@/api/ai'
import type { AvailabilityDay } from '@/types/orders'
import {
  agentFormDefinitions,
  primaryActionLabel,
  taskTypeLabel,
  toAgentFormData,
  type AgentFormCard,
  type AgentTaskAction,
} from '@/types/agentForm'

const props = defineProps<{ card: AgentFormCard; busy?: boolean }>()
const emit = defineEmits<{ submit: [payload: { action: AgentTaskAction; form_data: Record<string, unknown>; media_refs: string[] }]; }>()

const form = reactive<Record<string, any>>({ ...props.card.initial_fields })
const mediaRefs = ref<string[]>([...(props.card.media?.existing || [])])
const uploading = ref(false)
const loadingAvailability = ref(false)
const availabilityError = ref('')
const availableDays = ref<AvailabilityDay[]>([])
const isEditable = computed(() => ['editing', 'invalid', 'draft_unavailable'].includes(props.card.status))
const visibleFields = computed(() => agentFormDefinitions[props.card.task_type])
const supportsMedia = computed(() => ['create_project', 'publish_package', 'publish_work'].includes(props.card.task_type))
const mediaLabel = computed(() => props.card.task_type === 'publish_work' ? '作品媒体' : props.card.task_type === 'publish_package' ? '方案样片' : '参考图')
const hasBookingTarget = computed(() => Boolean(form.package_id && form.photographer_id))

function statusLabel(status: string) {
  return ({ editing: '编辑中', submitting: '提交中', invalid: '需要修改', draft_unavailable: '草稿箱暂未开放', published: '已完成', cancelled: '已取消', failed: '提交失败' } as Record<string, string>)[status] || status
}

function displayValue(key: string) {
  const value = form[key]
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'string' && (key === 'shoot_date_start' || key === 'shoot_date_end')) return value.slice(0, 16)
  return value ?? ''
}

function setField(key: string, value: string) {
  form[key] = value
}

function eventValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value
}

function formatDateLabel(day: AvailabilityDay) {
  const date = new Date(`${day.date}T00:00:00`)
  return Number.isNaN(date.getTime())
    ? day.date
    : date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', weekday: 'short' })
}

function mediaName(url: string) {
  return url.split('/').pop() || '已上传图片'
}

async function uploadMedia(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files || [])
  if (!files.length) return
  uploading.value = true
  try {
    for (const file of files) {
      const uploaded = await uploadAIImage(file)
      mediaRefs.value.push(uploaded.url)
    }
    if (props.card.task_type === 'create_project') form.reference_images = [...mediaRefs.value]
    if (props.card.task_type === 'publish_package') form.samples = [...mediaRefs.value]
    if (props.card.task_type === 'publish_work') form.media_refs = [...mediaRefs.value]
  } catch (error) {
    availabilityError.value = getApiErrorMessage(error)
  } finally {
    uploading.value = false
    ;(event.target as HTMLInputElement).value = ''
  }
}

function submit(action: AgentTaskAction) {
  const data = toAgentFormData(props.card.task_type, { ...form })
  if (props.card.task_type === 'create_project') data.reference_images = [...mediaRefs.value]
  if (props.card.task_type === 'publish_package') {
    data.samples = [...mediaRefs.value]
    data.sample_thumbnails = [...mediaRefs.value]
  }
  if (props.card.task_type === 'publish_work') data.media_refs = [...mediaRefs.value]
  emit('submit', { action, form_data: data, media_refs: [...mediaRefs.value] })
}

function cancel() {
  if (Object.values(form).some((value) => value !== '' && value !== null && value !== undefined && !(Array.isArray(value) && !value.length))) {
    if (!window.confirm('确定取消当前任务吗？')) return
  }
  submit('cancel')
}

async function loadAvailability() {
  if (props.card.task_type !== 'create_booking' || !hasBookingTarget.value) return
  loadingAvailability.value = true
  availabilityError.value = ''
  try {
    const result = await getAvailableSlots(Number(form.photographer_id), { days: 45, duration_minutes: Number(form.duration_minutes || 120), buffer_minutes: 30 })
    availableDays.value = result.days
  } catch (error) {
    availabilityError.value = getApiErrorMessage(error)
  } finally {
    loadingAvailability.value = false
  }
}

watch(() => [form.package_id, form.photographer_id, form.duration_minutes], () => void loadAvailability())
onMounted(() => void loadAvailability())
</script>

<style scoped>
.agent-form-card { width: 100%; overflow: hidden; border: 1px solid var(--divider); border-radius: var(--radius-md); background: var(--surface-solid); box-shadow: var(--neu-raise); }
.form-card-header, .form-card-footer { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) var(--space-4); }
.form-card-header { border-bottom: 1px solid var(--divider); background: var(--brand-soft); }
.form-card-kicker { color: var(--brand); font-size: var(--text-xs); font-weight: 700; }
.form-card-header h3 { margin: 2px 0 0; color: var(--ink); font-size: var(--text-base); }
.form-card-status { flex-shrink: 0; padding: 5px 9px; border-radius: var(--radius-pill); background: var(--paper); color: var(--ink-secondary); font-size: var(--text-xs); }
.status--published { color: var(--success, #276749); }.status--invalid, .status--failed { color: var(--danger); }.status--cancelled { color: var(--ink-tertiary); }
.form-card-body { padding: var(--space-4); }
.field-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.form-field, .media-field, .availability-field { display: grid; gap: 6px; min-width: 0; }
.field-wide { grid-column: 1 / -1; }
.field-label { color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 700; }
.field-label b { color: var(--danger); }
.form-field input, .form-field textarea, .form-field select { width: 100%; min-height: var(--touch-target); padding: 9px 11px; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: var(--paper); color: var(--ink); font: inherit; font-size: var(--text-sm); outline: none; }
.form-field textarea { min-height: 92px; resize: vertical; line-height: 1.5; }
.form-field input:focus, .form-field textarea:focus, .form-field select:focus { border-color: var(--brand); box-shadow: 0 0 0 2px var(--brand-soft); }
.field-help { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.45; }.field-error { color: var(--danger); font-size: var(--text-xs); }
.media-field, .availability-field { margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid var(--divider); }
.media-list { display: flex; flex-wrap: wrap; gap: 6px; }.media-chip { max-width: 100%; overflow: hidden; padding: 5px 8px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--ink-secondary); font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.media-picker { display: inline-flex; width: fit-content; min-height: var(--touch-target); align-items: center; gap: 7px; padding: 8px 12px; border: 1px solid var(--divider); border-radius: var(--radius-sm); color: var(--brand); font-size: var(--text-sm); cursor: pointer; }.media-picker input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.field-heading { display: flex; justify-content: space-between; }.date-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }.date-option { display: grid; min-height: var(--touch-target); gap: 3px; justify-items: start; padding: 9px 12px; border: 1px solid var(--divider); border-radius: var(--radius-sm); background: var(--paper); color: var(--ink-secondary); text-align: left; }.date-option strong { color: var(--ink); font-size: var(--text-sm); }.date-option small { color: var(--ink-tertiary); font-size: var(--text-xs); }.date-option.selected { border-color: var(--brand); background: var(--brand-soft); }.date-option.selected strong, .date-option.selected small { color: var(--brand); }.date-option:disabled { cursor: not-allowed; opacity: .55; }
.result-banner, .notice-banner, .error-summary { display: flex; align-items: flex-start; gap: 8px; padding: 10px var(--space-4); font-size: var(--text-sm); line-height: 1.5; }.result-banner { color: var(--success, #276749); background: color-mix(in srgb, var(--success, #276749) 10%, transparent); }.notice-banner { color: var(--warning); background: color-mix(in srgb, var(--warning) 10%, transparent); }.error-summary { color: var(--danger); background: color-mix(in srgb, var(--danger) 9%, transparent); }
.form-card-footer { flex-wrap: wrap; justify-content: flex-end; border-top: 1px solid var(--divider); background: var(--paper-deep); }.form-card-footer button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 7px; padding: 9px 12px; border: 0; border-radius: var(--radius-sm); font: inherit; font-size: var(--text-sm); font-weight: 700; cursor: pointer; }.form-card-footer button:disabled { cursor: not-allowed; opacity: .55; }.action-primary { background: var(--neu-surface-brand); color: var(--white); }.action-secondary { background: var(--paper); color: var(--brand); }.action-danger { background: transparent; color: var(--danger); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }.spin { animation: spin 800ms linear infinite; }@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 520px) { .field-grid { grid-template-columns: 1fr; }.field-wide { grid-column: auto; }.form-card-footer button { flex: 1 1 calc(50% - 8px); }.action-danger { flex-basis: 100%; } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
</style>
