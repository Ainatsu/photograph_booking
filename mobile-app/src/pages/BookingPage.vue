<template>
  <ion-page>
    <DetailHeader title="预约摄影" default-href="/tabs/showcase" />

    <ion-content class="booking-content">
      <main class="booking-shell">
        <FeedSkeleton v-if="loadingProfile" :count="3" />
        <StatePanel
          v-else-if="profileError"
          tone="error"
          title="预约信息加载失败"
          :description="profileError"
          action-label="重新加载"
          @action="loadProfile"
        />

        <template v-else-if="profile">
          <section class="booking-intro">
            <AvatarImage :src="profile.user_avatar_url" :name="photographerName" :size="54" />
            <div>
              <small>正在预约</small>
              <h1>{{ photographerName }}</h1>
              <p>{{ profile.location || '具体拍摄地点将在订单中确认' }}</p>
            </div>
          </section>
          <p v-if="agentTask" class="agent-source-note" role="status">已载入 Agent 整理的预约信息；档期仍以实时可预约日期为准。</p>

          <section class="form-section">
            <div class="section-heading">
              <span>1</span>
              <div>
                <h2>选择摄影方案</h2>
                <p>{{ isFromPackageDetail ? '已从方案详情中选定' : '价格和交付内容会写入订单快照' }}</p>
              </div>
            </div>

            <StatePanel
              v-if="!packages.length"
              title="这位摄影师暂时没有可预约方案"
              description="返回摄影师主页发起咨询，或选择其他已上架方案的摄影师。"
            />
            <div v-else-if="isFromPackageDetail && activePackage" class="package-locked">
              <div class="package-locked-card">
                <span>
                  <strong>{{ getPackageName(activePackage) }}</strong>
                  <small>{{ formatDuration(activePackage.duration) }} · {{ activePackage.image_count ? `精修 ${activePackage.image_count} 张` : '交付内容详谈' }}</small>
                </span>
                <em>{{ formatCurrency(activePackage.price) }}</em>
              </div>
              <p class="package-locked-hint">已选定方案，如需更换请返回方案详情重新选择。</p>
            </div>
            <div v-else class="package-options" role="radiogroup" aria-label="摄影方案">
              <button
                v-for="offer in packages"
                :key="offer.id"
                type="button"
                class="package-option pressable"
                :class="{ selected: selectedPackageId === String(offer.id) }"
                role="radio"
                :aria-checked="selectedPackageId === String(offer.id)"
                @click="selectedPackageId = String(offer.id)"
              >
                <span>
                  <strong>{{ getPackageName(offer) }}</strong>
                  <small>{{ formatDuration(offer.duration) }} · {{ offer.image_count ? `精修 ${offer.image_count} 张` : '交付内容详谈' }}</small>
                </span>
                <em>{{ formatCurrency(offer.price) }}</em>
              </button>
            </div>
          </section>

          <section class="form-section">
            <div class="section-heading">
              <span>2</span>
              <div><h2>选择真实档期</h2><p>系统会避开已有订单和摄影师忙碌时间</p></div>
            </div>

            <FeedSkeleton v-if="loadingAvailability" :count="2" />
            <StatePanel
              v-else-if="availabilityError"
              tone="error"
              title="档期暂时无法加载"
              :description="availabilityError"
              action-label="重新加载"
              @action="loadAvailability"
            />
            <template v-else-if="availability">
              <div class="availability-meta">
                <span><Clock3 :size="15" />需提前 {{ availability.advance_notice_hours }} 小时</span>
                <span><TimerReset :size="15" />预留 {{ availability.buffer_minutes }} 分钟缓冲</span>
              </div>

              <div class="date-strip" role="radiogroup" aria-label="可预约日期">
                <button
                  v-for="day in availability.days"
                  :key="day.date"
                  type="button"
                  class="date-option pressable"
                  :class="{ selected: selectedDate === day.date }"
                  :disabled="!day.bookable"
                  role="radio"
                  :aria-checked="selectedDate === day.date"
                  @click="selectDate(day.date)"
                >
                  <small>{{ day.weekday }}</small>
                  <strong>{{ formatDateChip(day.date) }}</strong>
                  <em>{{ day.bookable ? '可预约' : '已满' }}</em>
                </button>
              </div>

              <p v-if="selectedDay?.bookable" class="slot-hint">该日期可预约，不需要选择具体时刻。</p>
              <p v-else class="slot-hint">请先选择一个仍有空档的日期。</p>
            </template>
          </section>

          <section class="form-section">
            <div class="section-heading">
              <span>3</span>
              <div><h2>补充拍摄需求</h2><p>选填；可说明人数、风格、地点和特殊要求</p></div>
            </div>
            <label class="sr-only" for="booking-notes">拍摄需求备注</label>
            <textarea
              id="booking-notes"
              v-model.trim="notes"
              class="notes-field"
              rows="5"
              maxlength="500"
              placeholder="例如：两人情侣写真，希望在傍晚拍摄，偏自然纪实风格。"
            />
            <span class="character-count">{{ notes.length }}/500</span>
          </section>

          <section class="order-summary">
            <ShieldCheck :size="20" aria-hidden="true" />
            <div>
              <strong>提交后先由摄影师确认</strong>
              <p>摄影师确认后进入演示支付环节；支付完成才会正式锁定档期。</p>
            </div>
          </section>

          <div v-if="submitError" class="submit-error" role="alert">
            <CircleAlert :size="18" aria-hidden="true" />
            <span>{{ submitError }}</span>
          </div>
        </template>

        <section v-else-if="agentTask" class="booking-task-editor">
          <div class="booking-task-editor-heading">
            <CalendarCheck2 :size="22" aria-hidden="true" />
            <div>
              <small>正在完善预约</small>
              <h1>先补充预约信息</h1>
            </div>
          </div>
          <p class="booking-task-editor-description">
            目前还没有选定摄影师或方案。已收集的信息会保留在任务中，你可以先编辑日期和备注，再返回聊天选择可预约的方案。
          </p>
          <label class="task-editor-field">
            <span>预约日期</span>
            <input
              v-model="taskAppointmentDate"
              type="date"
              @change="persistTaskField('appointment_date', taskAppointmentDate)"
            />
          </label>
          <label class="task-editor-field">
            <span>备注</span>
            <textarea
              v-model="taskNotes"
              rows="5"
              maxlength="500"
              @change="persistTaskField('notes', taskNotes)"
            />
          </label>
          <button type="button" class="task-editor-chat-button pressable" @click="router.push({ name: 'ai-assistant' })">
            返回聊天选择摄影师和方案
          </button>
        </section>
      </main>
    </ion-content>

    <DetailActionBar
      v-if="profile && packages.length"
      primary-label="提交预约"
      :primary-disabled="!canSubmit"
      :primary-loading="submitting"
      @primary="submitOrder"
    >
      <template #primary-icon><CalendarCheck2 :size="18" aria-hidden="true" /></template>
    </DetailActionBar>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IonContent, IonPage } from '@ionic/vue'
import { CalendarCheck2, CircleAlert, Clock3, ShieldCheck, TimerReset } from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailActionBar from '@/components/DetailActionBar.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import { useAgentTaskHandoff } from '@/composables/useAgentTaskHandoff'
import { getPhotographerDetail } from '@/api/discovery'
import { createOrder as createOrderRequest, getAvailableSlots } from '@/api/orders'
import { trackRecommendationEvents, type RecommendationEvent } from '@/api/recommendations'
import type { PackageOffer, PhotographerProfile } from '@/types/discovery'
import type { AvailabilityDay, AvailabilityResponse } from '@/types/orders'
import { formatCurrency, formatDuration, getPackageName } from '@/utils/format'
import { isPackageActive } from '@/utils/package'

const route = useRoute()
const router = useRouter()
const agentHandoff = useAgentTaskHandoff()
const agentTask = agentHandoff.task
const profile = ref<PhotographerProfile | null>(null)
const loadingProfile = ref(true)
const profileError = ref('')
const selectedPackageId = ref('')
const availability = ref<AvailabilityResponse | null>(null)
const loadingAvailability = ref(false)
const availabilityError = ref('')
const selectedDate = ref('')
const notes = ref('')
const desiredAppointmentDate = ref('')
const taskAppointmentDate = ref('')
const taskNotes = ref('')
const submitting = ref(false)
const submitError = ref('')
let availabilityRequestId = 0
let taskNotesTimer: number | null = null
const trackedJointEvents = new Set<string>()

const packages = computed<PackageOffer[]>(() => (profile.value?.packages || []).filter(isPackageActive))
const photographerName = computed(() => profile.value?.user_display_name || '摄影师')
const activePackage = computed(() => packages.value.find((offer) => String(offer.id) === selectedPackageId.value) || null)
const selectedDay = computed<AvailabilityDay | null>(() => (
  availability.value?.days.find((day) => day.date === selectedDate.value) || null
))
const isFromPackageDetail = computed(() => route.query.locked === '1')
const canSubmit = computed(() => Boolean(activePackage.value && selectedDate.value) && !submitting.value)
const jointRecommendation = computed(() => {
  const recommendationId = String(route.query.recommendationId || '')
  if (!recommendationId) return null
  return {
    recommendationId,
    algorithmVersion: String(route.query.algorithmVersion || ''),
    position: Math.max(0, Number(route.query.recommendationPosition || 0)),
  }
})

function trackJointOnce(key: string, event: RecommendationEvent) {
  if (trackedJointEvents.has(key)) return
  trackedJointEvents.add(key)
  void trackRecommendationEvents([event])
}

function jointEvent(eventType: string, metadata?: Record<string, unknown>): RecommendationEvent | null {
  const context = jointRecommendation.value
  const packageId = selectedPackageId.value || String(route.query.packageId || '')
  const photographerId = Number(route.params.userId)
  if (!context || !packageId || !photographerId) return null
  return {
    event_type: eventType, target_type: 'package', target_id: packageId,
    owner_user_id: photographerId, recommendation_id: context.recommendationId,
    algorithm_version: context.algorithmVersion, position: context.position,
    scene: 'ai_joint_booking', metadata,
  }
}

function formatDateChip(value: string) {
  const date = new Date(`${value}T00:00:00`)
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric' }).format(date)
}

function selectDate(value: string) {
  selectedDate.value = value
  if (route.query.agentTaskId) {
    void agentHandoff.saveOperations([
      { field: 'appointment_date', op: 'set', value },
    ]).catch((error) => {
      submitError.value = getApiErrorMessage(error)
    })
  }
  const event = jointEvent('joint_rec_select_date', { date: value })
  if (event) trackJointOnce(`date:${jointRecommendation.value?.recommendationId}:${value}`, event)
}

async function loadProfile() {
  loadingProfile.value = true
  profileError.value = ''
  const photographerId = Number(route.params.userId)
  if (!Number.isInteger(photographerId) || photographerId <= 0) {
    profile.value = null
    loadingProfile.value = false
    return
  }
  try {
    profile.value = await getPhotographerDetail(photographerId)
    const requestedPackageId = String(route.query.packageId || '')
    selectedPackageId.value = packages.value.some((offer) => String(offer.id) === requestedPackageId)
      ? requestedPackageId
      : String(packages.value[0]?.id || '')
  } catch (error) {
    profileError.value = getApiErrorMessage(error)
  } finally {
    loadingProfile.value = false
  }
}

async function loadAvailability() {
  const requestId = ++availabilityRequestId
  const offer = activePackage.value
  const photographerId = Number(route.params.userId)
  availability.value = null
  selectedDate.value = ''
  availabilityError.value = ''
  loadingAvailability.value = false
  if (!offer || !photographerId) return

  loadingAvailability.value = true
  try {
    const result = await getAvailableSlots(photographerId, {
      days: 45,
      duration_minutes: Number(offer.duration || 120),
      buffer_minutes: Number(offer.buffer_minutes || 30),
    })
    if (requestId !== availabilityRequestId) return
    availability.value = result
    const requestedDay = result.days.find((day) => day.date === desiredAppointmentDate.value && day.bookable)
    selectedDate.value = requestedDay?.date || result.days.find((day) => day.bookable)?.date || ''
  } catch (error) {
    if (requestId !== availabilityRequestId) return
    availabilityError.value = getApiErrorMessage(error)
  } finally {
    if (requestId === availabilityRequestId) loadingAvailability.value = false
  }
}

async function submitOrder() {
  const offer = activePackage.value
  if (!offer || !selectedDate.value || !profile.value || submitting.value) return

  submitError.value = ''
  submitting.value = true
  try {
    const order = await createOrderRequest({
      package_id: String(offer.id),
      photographer_id: profile.value.user_id,
      appointment_date: selectedDate.value,
      notes: notes.value || undefined,
    })
    if (agentTask.value) await agentHandoff.complete({ order_id: order.id })
    const successEvent = jointEvent('joint_rec_booking_success', { order_id: order.id })
    if (successEvent) trackJointOnce(`success:${jointRecommendation.value?.recommendationId}:${order.id}`, successEvent)
    await router.replace({ name: 'orders', query: { created: String(order.id) } })
  } catch (error) {
    submitError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

async function persistTaskField(field: 'appointment_date' | 'notes', value: string) {
  if (!agentTask.value) return
  try {
    const normalized = value.trim()
    await agentHandoff.saveOperations([
      normalized
        ? { field, op: 'set', value: normalized }
        : { field, op: 'clear' },
    ])
  } catch (error) {
    submitError.value = getApiErrorMessage(error)
  }
}

watch(selectedPackageId, () => void loadAvailability())
watch(notes, (value) => {
  if (!route.query.agentTaskId) return
  if (taskNotesTimer !== null) window.clearTimeout(taskNotesTimer)
  taskNotesTimer = window.setTimeout(() => void persistTaskField('notes', value), 450)
})
onMounted(async () => {
  const startEvent = jointEvent('joint_rec_booking_start')
  if (startEvent) trackJointOnce(`start:${jointRecommendation.value?.recommendationId}`, startEvent)
  await loadProfile()
  const task = await agentHandoff.load('create_booking')
  if (task) {
    taskAppointmentDate.value = String(task.fields.appointment_date || '')
    taskNotes.value = String(task.fields.notes || '')
    notes.value = String(task.fields.notes || '')
    desiredAppointmentDate.value = String(task.fields.appointment_date || '')
    const packageId = String(task.target.package_id || task.fields.package_id || '')
    if (packageId && packages.value.some((offer) => String(offer.id) === packageId)) selectedPackageId.value = packageId
    await loadAvailability()
  }
})
onUnmounted(() => { if (taskNotesTimer !== null) window.clearTimeout(taskNotesTimer) })
</script>

<style scoped>
.booking-content { --background: var(--paper); }
.booking-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.booking-intro { display: grid; grid-template-columns: 54px minmax(0, 1fr); align-items: center; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.booking-intro small { color: var(--brand); font-size: 11px; font-weight: 750; }
.booking-intro h1 { margin: 2px 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.booking-intro p { margin: 0; color: var(--ink-tertiary); font-size: var(--text-xs); }
.form-section { margin-top: var(--space-6); }
.section-heading { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: var(--space-3); align-items: start; margin-bottom: var(--space-3); }
.section-heading > span { display: grid; width: 32px; height: 32px; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); font-size: var(--text-sm); font-weight: 750; }
.section-heading h2 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.section-heading p { margin: 3px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }
.package-options { display: grid; gap: var(--space-3); }
.package-option { display: grid; grid-template-columns: minmax(0, 1fr) auto; width: 100%; min-height: 76px; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink); text-align: left; }
.package-option.selected { border-color: var(--brand); background: var(--paper); box-shadow: var(--neu-inset); border: 0; }
.package-option span { display: grid; gap: 5px; min-width: 0; }
.package-option strong { font-size: var(--text-sm); }
.package-option small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.45; }
.package-option em { color: var(--brand); font-size: var(--text-base); font-style: normal; font-weight: 800; font-variant-numeric: tabular-nums; }
.package-locked-card { display: grid; grid-template-columns: minmax(0, 1fr) auto; min-height: 76px; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.package-locked-card span { display: grid; gap: 5px; min-width: 0; }
.package-locked-card strong { font-size: var(--text-sm); }
.package-locked-card small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.45; }
.package-locked-card em { color: var(--brand); font-size: var(--text-base); font-style: normal; font-weight: 800; font-variant-numeric: tabular-nums; }
.package-locked-hint { margin: var(--space-2) 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); }
.availability-meta { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.availability-meta span { display: inline-flex; min-height: 32px; align-items: center; gap: 5px; padding: 4px 9px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-xs); }
.date-strip { display: flex; gap: var(--space-2); margin-inline: calc(var(--space-4) * -1); padding: 2px var(--space-4) var(--space-3); overflow-x: auto; scroll-snap-type: x proximity; }
.date-option { display: grid; min-width: 78px; min-height: 82px; place-items: center; align-content: center; gap: 3px; scroll-snap-align: start; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink); }
.date-option small { color: var(--ink-tertiary); font-size: 11px; }
.date-option strong { font-size: var(--text-sm); }
.date-option em { color: var(--brand); font-size: 11px; font-style: normal; }
.date-option.selected { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); border: 0; }
.date-option.selected small, .date-option.selected em { color: var(--white); }
.date-option:disabled { opacity: .42; }
.slot-hint { margin: var(--space-3) 0 0; padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-tertiary); font-size: var(--text-sm); text-align: center; }
.notes-field { width: 100%; min-height: 132px; padding: var(--space-3) var(--space-4); resize: vertical; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); line-height: 1.65; outline: none; }
.notes-field:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }
.character-count { display: block; margin-top: 5px; color: var(--ink-tertiary); font-size: var(--text-xs); text-align: right; font-variant-numeric: tabular-nums; }
.order-summary { display: flex; gap: var(--space-3); margin-top: var(--space-6); padding: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise); color: var(--brand); }
.order-summary strong { color: var(--ink); font-size: var(--text-sm); }
.order-summary p { margin: 4px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.submit-error { display: flex; gap: var(--space-2); margin-top: var(--space-4); padding: var(--space-3); border: 1px solid rgba(163, 59, 50, .25); border-radius: var(--radius-md); background: #fbefed; color: var(--danger); font-size: var(--text-sm); line-height: 1.55; }
.submit-error svg { flex: 0 0 auto; }
.booking-task-editor { display: grid; gap: var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.booking-task-editor-heading { display: flex; align-items: center; gap: var(--space-3); color: var(--brand); }
.booking-task-editor-heading small { color: var(--brand); font-size: var(--text-xs); font-weight: 750; }
.booking-task-editor-heading h1 { margin: 2px 0 0; color: var(--ink); font-family: var(--font-serif); font-size: var(--text-lg); }
.booking-task-editor-description { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; }
.task-editor-field { display: grid; gap: 6px; color: var(--ink-secondary); font-size: var(--text-sm); font-weight: 650; }
.task-editor-field input, .task-editor-field textarea { width: 100%; min-height: var(--touch-target); padding: 10px 12px; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font: inherit; font-weight: 400; outline: none; }
.task-editor-field textarea { min-height: 132px; resize: vertical; line-height: 1.6; }
.task-editor-field input:focus, .task-editor-field textarea:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, .26); }
.task-editor-chat-button { min-height: var(--touch-target); padding: 10px 14px; border: 0; border-radius: var(--radius-sm); background: var(--neu-surface-brand); color: var(--white); font: inherit; font-size: var(--text-sm); font-weight: 700; }
</style>
