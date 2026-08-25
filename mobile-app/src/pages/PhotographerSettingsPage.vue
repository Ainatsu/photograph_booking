<template>
  <ion-page>
    <DetailHeader title="档期与服务" default-href="/tabs/profile" />

    <ion-content class="settings-content">
      <ion-refresher v-if="auth.isPhotographer" slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="settings-shell">
        <StatePanel
          v-if="auth.initialized && !auth.isPhotographer"
          title="需要摄影师身份"
          description="只有通过摄影师认证的账号可以配置服务能力和可预约档期。"
          action-label="返回我的"
          @action="router.replace({ name: 'profile' })"
        />

        <template v-else>
          <section class="settings-intro">
            <span><CalendarClock :size="24" aria-hidden="true" /></span>
            <div>
              <p>Availability workspace</p>
              <h1>让客户只看到真正可约的时间</h1>
              <small>默认每天可约；只需标记忙碌日期，并设置器材风格、提前预约时间与每日接单上限。常驻地请在「资料与账号」中设置。</small>
            </div>
          </section>

          <SegmentSwitch
            :model-value="activeSection"
            :items="sectionItems"
            label="摄影师设置分类"
            @update:model-value="setSection"
          />

          <FeedSkeleton v-if="loading" :count="3" />
          <StatePanel
            v-else-if="error"
            tone="error"
            title="摄影师设置加载失败"
            :description="error"
            action-label="重新加载"
            @action="loadSettings"
          />

          <template v-else>
            <form v-if="activeSection === 'service'" class="settings-form" novalidate @submit.prevent="saveSettings">
              <section class="settings-card">
                <header class="card-heading">
                  <span><MapPin :size="20" aria-hidden="true" /></span>
                  <div><h2>服务能力</h2><p>这些信息会展示在摄影师主页，并参与企划匹配。</p></div>
                </header>

                <div class="settings-field">
                  <label for="service-equipment">器材与服务能力 <span>选填</span></label>
                  <textarea id="service-equipment" v-model.trim="form.equipment" class="settings-textarea" maxlength="500" rows="5" placeholder="例如：Sony A7M4、双机位、棚拍灯光与基础造型协作" :disabled="saving" />
                </div>

                <div class="settings-field">
                  <label for="service-styles">擅长风格 <span>最多 12 个</span></label>
                  <TagEditor v-model="styles" input-id="service-styles" placeholder="例如：人像、婚礼、复古" :disabled="saving" @limit="toastMessage = '最多添加 12 个风格标签。'" />
                </div>
              </section>

              <section class="settings-card">
                <header class="card-heading">
                  <span><SlidersHorizontal :size="20" aria-hidden="true" /></span>
                  <div><h2>预约规则</h2><p>规则会直接影响客户能看到的真实时间段。</p></div>
                </header>

                <div class="field-grid">
                  <div class="settings-field">
                    <label for="advance-notice">最少提前预约 <span>小时</span></label>
                    <input id="advance-notice" v-model.number="form.advance_notice" type="number" inputmode="numeric" min="0" max="720" step="1" class="settings-input" :disabled="saving" :aria-invalid="Boolean(errors.advance_notice)" />
                    <p v-if="errors.advance_notice" class="settings-error" role="alert">{{ errors.advance_notice }}</p>
                  </div>
                  <div class="settings-field">
                    <label for="max-daily-bookings">每日最大接单量 <span>单</span></label>
                    <input id="max-daily-bookings" v-model.number="form.max_daily_bookings" type="number" inputmode="numeric" min="1" max="20" step="1" class="settings-input" :disabled="saving" :aria-invalid="Boolean(errors.max_daily_bookings)" />
                    <p v-if="errors.max_daily_bookings" class="settings-error" role="alert">{{ errors.max_daily_bookings }}</p>
                  </div>
                </div>

                <div class="settings-field">
                  <label for="max-booking-date">最远可预约日期 <span>未来 365 天内</span></label>
                  <input id="max-booking-date" v-model="form.max_booking_date" type="date" class="settings-input" :min="todayKey" :max="maxAllowedDateKey" :disabled="saving" :aria-invalid="Boolean(errors.max_booking_date)" />
                  <p v-if="errors.max_booking_date" class="settings-error" role="alert">{{ errors.max_booking_date }}</p>
                </div>

                <div class="rule-summary" aria-live="polite">
                  <Clock3 :size="19" aria-hidden="true" />
                  <p>客户需至少提前 <strong>{{ normalizedAdvanceNotice }}</strong> 小时预约，每天最多接受 <strong>{{ normalizedDailyLimit }}</strong> 笔新订单。</p>
                </div>
              </section>
            </form>

            <div v-else class="calendar-workspace">
              <section class="calendar-card">
                <header class="month-toolbar">
                  <button type="button" class="month-button pressable" aria-label="查看上个月" :disabled="!canGoPreviousMonth || saving" @click="shiftMonth(-1)">
                    <ChevronLeft :size="20" aria-hidden="true" />
                  </button>
                  <div><small>档期日历</small><h2>{{ monthLabel }}</h2></div>
                  <button type="button" class="month-button pressable" aria-label="查看下个月" :disabled="!canGoNextMonth || saving" @click="shiftMonth(1)">
                    <ChevronRight :size="20" aria-hidden="true" />
                  </button>
                </header>

                <div class="month-stats" aria-label="本月档期统计">
                  <span><small>可约</small><strong>{{ monthStats.free }}</strong></span>
                  <span class="busy"><small>忙碌</small><strong>{{ monthStats.busy }}</strong></span>
                  <span><small>已选</small><strong>{{ monthStats.selected }}</strong></span>
                </div>

                <SegmentSwitch
                  :model-value="selectionMode"
                  :items="selectionModeItems"
                  label="档期选择方式"
                  @update:model-value="setSelectionMode"
                />

                <div class="calendar-legend">
                  <span><i class="free" />默认可约</span>
                  <span><i class="busy" />已标忙碌</span>
                  <small>{{ selectionMode === 'range' ? '依次选择开始和结束日期' : '选择一天后在下方编辑' }}</small>
                </div>

                <div class="calendar-grid" role="grid" :aria-label="monthLabel">
                  <div v-for="weekday in weekdays" :key="weekday" class="weekday" role="columnheader">{{ weekday }}</div>
                  <template v-for="cell in calendarCells" :key="cell.key">
                    <div v-if="cell.isBlank" class="date-cell blank" aria-hidden="true" />
                    <button
                      v-else
                      type="button"
                      role="gridcell"
                      class="date-cell pressable"
                      :class="{
                        busy: cell.status === 'busy',
                        today: cell.isToday,
                        selected: cell.isSelected,
                        'range-edge': cell.isRangeStart || cell.isRangeEnd,
                        'in-range': cell.isInRange,
                      }"
                      :disabled="cell.disabled || saving"
                      :aria-label="calendarCellLabel(cell)"
                      :aria-selected="Boolean(cell.isSelected || cell.isInRange)"
                      @click="selectCalendarCell(cell)"
                    >
                      <span>{{ cell.day }}</span>
                      <small>{{ cell.status === 'busy' ? '忙' : '可' }}</small>
                      <i v-if="cell.location" aria-label="已设置所在地" />
                    </button>
                  </template>
                </div>
              </section>

              <section v-if="selectionMode === 'single'" class="settings-card day-editor">
                <header class="card-heading">
                  <span><CalendarDays :size="20" aria-hidden="true" /></span>
                  <div><h2>{{ selectedDateLabel || '选择一个日期' }}</h2><p>{{ selectedDateWeekday || '点击上方日期后设置状态与所在地。' }}</p></div>
                </header>

                <template v-if="selectedDate">
                  <fieldset class="status-fieldset">
                    <legend>当天状态</legend>
                    <div class="status-toggle" role="radiogroup" aria-label="当天档期状态">
                      <button type="button" role="radio" class="pressable" :class="{ active: dayForm.status === 'free' }" :aria-checked="dayForm.status === 'free'" :disabled="saving" @click="dayForm.status = 'free'">可约</button>
                      <button type="button" role="radio" class="pressable danger" :class="{ active: dayForm.status === 'busy' }" :aria-checked="dayForm.status === 'busy'" :disabled="saving" @click="dayForm.status = 'busy'">忙碌</button>
                    </div>
                  </fieldset>
                  <div class="settings-field">
                    <label for="day-location">当天所在地 <span>选填</span></label>
                    <input id="day-location" v-model.trim="dayForm.location" class="settings-input" maxlength="60" placeholder="例如：澳门 / 深圳" :disabled="saving" />
                  </div>
                  <div class="editor-actions">
                    <button type="button" class="primary pressable" :disabled="saving" @click="applyDayForm">更新这一天</button>
                    <button type="button" class="pressable" :disabled="saving" @click="clearSelectedDay">恢复默认</button>
                  </div>
                </template>
                <p v-else class="editor-empty">尚未选择日期。本平台默认每天可约，因此只需标记无法接单的日期。</p>
              </section>

              <section v-else class="settings-card range-editor">
                <header class="card-heading">
                  <span><CalendarRange :size="20" aria-hidden="true" /></span>
                  <div><h2>{{ rangeLabel || '选择日期区间' }}</h2><p>{{ selectedRangeKeys.length ? `已选择 ${selectedRangeKeys.length} 天` : '先点击开始日期，再点击结束日期。' }}</p></div>
                </header>

                <fieldset class="status-fieldset">
                  <legend>批量设置状态</legend>
                  <div class="status-toggle" role="radiogroup" aria-label="区间档期状态">
                    <button type="button" role="radio" class="pressable" :class="{ active: rangeForm.status === 'free' }" :aria-checked="rangeForm.status === 'free'" :disabled="saving" @click="rangeForm.status = 'free'">可约</button>
                    <button type="button" role="radio" class="pressable danger" :class="{ active: rangeForm.status === 'busy' }" :aria-checked="rangeForm.status === 'busy'" :disabled="saving" @click="rangeForm.status = 'busy'">忙碌</button>
                  </div>
                </fieldset>

                <label class="location-check" for="range-apply-location">
                  <span><strong>同步所在地</strong><small>关闭时保留每一天原有所在地</small></span>
                  <input id="range-apply-location" v-model="rangeForm.applyLocation" type="checkbox" :disabled="saving" />
                </label>
                <div v-if="rangeForm.applyLocation" class="settings-field">
                  <label for="range-location">区间所在地 <span>选填</span></label>
                  <input id="range-location" v-model.trim="rangeForm.location" class="settings-input" maxlength="60" placeholder="例如：香港" :disabled="saving" />
                </div>
                <div class="editor-actions">
                  <button type="button" class="primary pressable" :disabled="!selectedRangeKeys.length || saving" @click="applyRangeForm">应用到所选日期</button>
                  <button type="button" class="pressable" :disabled="!rangeStart || saving" @click="resetRange">取消选择</button>
                </div>
              </section>

              <section class="settings-card quick-card">
                <header class="card-heading">
                  <span><Gauge :size="20" aria-hidden="true" /></span>
                  <div><h2>快捷排期</h2><p>批量修改后仍需点击底部“保存设置”。</p></div>
                </header>
                <div class="quick-grid">
                  <button type="button" class="pressable" :disabled="saving" @click="applyQuickAction('weekdays-busy')">本月周中忙碌</button>
                  <button type="button" class="pressable" :disabled="saving" @click="applyQuickAction('weekends-busy')">本月周末忙碌</button>
                  <button type="button" class="pressable" :disabled="!canGoNextMonth || saving" @click="applyQuickAction('next-month-busy')">下个月全忙</button>
                  <button type="button" class="danger pressable" :disabled="saving" @click="applyQuickAction('clear-month')">清除本月忙碌</button>
                </div>
              </section>
            </div>

            <div v-if="requestError" class="settings-request-error" role="alert">
              <CircleAlert :size="19" aria-hidden="true" />{{ requestError }}
            </div>
            <div v-if="hasUnsavedChanges" class="unsaved-note" role="status">
              <RotateCcw :size="18" aria-hidden="true" />尚有未保存修改，离开页面前会再次确认。
            </div>
          </template>
        </template>
      </main>

      <ion-toast :is-open="Boolean(toastMessage)" :message="toastMessage" :duration="2800" position="bottom" @did-dismiss="toastMessage = ''" />
    </ion-content>

    <ion-footer v-if="auth.isPhotographer && !loading && !error" class="settings-footer">
      <div class="settings-footer-actions">
        <button type="button" class="pressable" :disabled="saving" @click="confirmReload">
          <RotateCcw :size="18" aria-hidden="true" />重新载入
        </button>
        <button type="button" class="primary pressable" :disabled="saving || !hasUnsavedChanges" @click="saveSettings">
          <ion-spinner v-if="saving" name="crescent" aria-hidden="true" />
          <Save v-else :size="18" aria-hidden="true" />保存设置
        </button>
      </div>
    </ion-footer>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonFooter,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  alertController,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  Gauge,
  MapPin,
  RotateCcw,
  Save,
  SlidersHorizontal,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SegmentSwitch, { type SegmentItem } from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import TagEditor from '@/components/TagEditor.vue'
import { getApiErrorMessage } from '@/api/client'
import { getPhotographerSettings, savePhotographerSettings } from '@/api/availability'
import { useAuthStore } from '@/stores/auth'
import type { AvailabilityStatus } from '@/types/discovery'
import {
  MAX_AVAILABILITY_DAYS,
  addDays,
  addMonths,
  buildAvailabilityCalendar,
  buildAvailabilityExceptions,
  dateRangeKeys,
  getAvailabilityDay,
  hydrateAvailabilityDays,
  monthDateKeys,
  parseDateKey,
  setAvailabilityDay,
  startOfLocalDay,
  toDateKey,
  type AvailabilityCalendarCell,
  type AvailabilityDayMap,
} from '@/utils/availability'

type SettingsSection = 'service' | 'calendar'
type SelectionMode = 'single' | 'range'
type QuickAction = 'weekdays-busy' | 'weekends-busy' | 'next-month-busy' | 'clear-month'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const today = startOfLocalDay()
const todayKey = toDateKey(today)
const maxAllowedDateKey = toDateKey(addDays(today, MAX_AVAILABILITY_DAYS))
const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const activeSection = ref<SettingsSection>(route.query.tab === 'calendar' ? 'calendar' : 'service')
const loading = ref(true)
const error = ref('')
const saving = ref(false)
const requestError = ref('')
const toastMessage = ref('')
const hydrating = ref(false)
const serviceDirty = ref(false)
const availabilityDirty = ref(false)
const form = reactive({
  equipment: '',
  advance_notice: 24 as number | '',
  max_daily_bookings: 5 as number | '',
  max_booking_date: maxAllowedDateKey,
})
const styles = ref<string[]>([])
const errors = reactive<Record<string, string>>({})
const availabilityDays = ref<AvailabilityDayMap>({})
const currentMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))
const selectionMode = ref<SelectionMode>('single')
const selectedDate = ref('')
const rangeStart = ref('')
const rangeEnd = ref('')
const dayForm = reactive<{ status: AvailabilityStatus; location: string }>({ status: 'free', location: '' })
const rangeForm = reactive<{ status: AvailabilityStatus; applyLocation: boolean; location: string }>({ status: 'busy', applyLocation: false, location: '' })

const sectionItems = computed<SegmentItem[]>(() => [
  { label: '服务能力', value: 'service' },
  { label: '档期日历', value: 'calendar', count: busyDayCount.value },
])
const selectionModeItems: SegmentItem[] = [
  { label: '单日设置', value: 'single' },
  { label: '区间批量', value: 'range' },
]
const normalizedAdvanceNotice = computed(() => Number(form.advance_notice || 0))
const normalizedDailyLimit = computed(() => Number(form.max_daily_bookings || 0))
const hasUnsavedChanges = computed(() => serviceDirty.value || availabilityDirty.value)
const busyDayCount = computed(() => Object.values(availabilityDays.value).filter((entry) => entry.status === 'busy').length)
const currentMonthStart = computed(() => new Date(today.getFullYear(), today.getMonth(), 1))
const maxMonthStart = computed(() => {
  const maxDate = addDays(today, MAX_AVAILABILITY_DAYS)
  return new Date(maxDate.getFullYear(), maxDate.getMonth(), 1)
})
const canGoPreviousMonth = computed(() => currentMonth.value > currentMonthStart.value)
const canGoNextMonth = computed(() => currentMonth.value < maxMonthStart.value)
const monthLabel = computed(() => `${currentMonth.value.getFullYear()}年${currentMonth.value.getMonth() + 1}月`)
const selectedRangeKeys = computed(() => {
  if (!rangeStart.value) return []
  return dateRangeKeys(rangeStart.value, rangeEnd.value || rangeStart.value, today)
})
const selectedKeys = computed(() => selectionMode.value === 'single'
  ? (selectedDate.value ? [selectedDate.value] : [])
  : selectedRangeKeys.value)
const calendarCells = computed(() => buildAvailabilityCalendar(currentMonth.value, availabilityDays.value, {
  today,
  selectedKeys: selectedKeys.value,
  rangeStart: rangeStart.value,
  rangeEnd: rangeEnd.value,
}))
const monthStats = computed(() => {
  const cells = calendarCells.value.filter((cell) => !cell.isBlank && !cell.disabled)
  return {
    free: cells.filter((cell) => cell.status === 'free').length,
    busy: cells.filter((cell) => cell.status === 'busy').length,
    selected: selectedKeys.value.length,
  }
})
const selectedDateLabel = computed(() => formatDateLabel(selectedDate.value))
const selectedDateWeekday = computed(() => formatWeekdayLabel(selectedDate.value))
const rangeLabel = computed(() => {
  const keys = selectedRangeKeys.value
  if (!keys.length) return ''
  if (keys.length === 1) return formatDateLabel(keys[0])
  return `${formatDateLabel(keys[0])} – ${formatDateLabel(keys[keys.length - 1])}`
})

function setSection(value: string) {
  activeSection.value = value === 'calendar' ? 'calendar' : 'service'
  void router.replace({ query: { ...route.query, tab: activeSection.value === 'calendar' ? 'calendar' : undefined } })
}

function setSelectionMode(value: string) {
  selectionMode.value = value === 'range' ? 'range' : 'single'
  selectedDate.value = ''
  resetRange()
}

function formatDateLabel(dateKey: string) {
  const date = parseDateKey(dateKey)
  if (!date) return ''
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }).format(date)
}

function formatWeekdayLabel(dateKey: string) {
  const date = parseDateKey(dateKey)
  if (!date) return ''
  return new Intl.DateTimeFormat('zh-CN', { weekday: 'long' }).format(date)
}

function calendarCellLabel(cell: AvailabilityCalendarCell) {
  const dateLabel = formatDateLabel(cell.key)
  const state = cell.status === 'busy' ? '忙碌' : '可约'
  return `${dateLabel}，${state}${cell.location ? `，所在地 ${cell.location}` : ''}`
}

function syncDayForm(dateKey: string) {
  const current = getAvailabilityDay(availabilityDays.value, dateKey)
  dayForm.status = current.status
  dayForm.location = current.location || ''
}

function selectCalendarCell(cell: AvailabilityCalendarCell) {
  if (cell.isBlank || cell.disabled) return
  if (selectionMode.value === 'range') {
    if (!rangeStart.value || rangeEnd.value) {
      rangeStart.value = cell.key
      rangeEnd.value = ''
    } else {
      rangeEnd.value = cell.key
    }
    return
  }
  selectedDate.value = cell.key
  syncDayForm(cell.key)
}

function applyDayForm() {
  if (!selectedDate.value) return
  availabilityDays.value = setAvailabilityDay(
    availabilityDays.value,
    selectedDate.value,
    dayForm.status,
    dayForm.location,
    today,
  )
  availabilityDirty.value = true
  syncDayForm(selectedDate.value)
  toastMessage.value = '已更新当天档期，保存后生效'
}

function clearSelectedDay() {
  if (!selectedDate.value) return
  availabilityDays.value = setAvailabilityDay(availabilityDays.value, selectedDate.value, 'free', '', today)
  availabilityDirty.value = true
  syncDayForm(selectedDate.value)
  toastMessage.value = '已恢复为默认可约，保存后生效'
}

function applyRangeForm() {
  const keys = selectedRangeKeys.value
  if (!keys.length) return
  let next = availabilityDays.value
  for (const key of keys) {
    const location = rangeForm.applyLocation
      ? rangeForm.location
      : (getAvailabilityDay(next, key).location || '')
    next = setAvailabilityDay(next, key, rangeForm.status, location, today)
  }
  availabilityDays.value = next
  availabilityDirty.value = true
  toastMessage.value = `已更新 ${keys.length} 天档期，保存后生效`
  resetRange()
}

function resetRange() {
  rangeStart.value = ''
  rangeEnd.value = ''
  rangeForm.applyLocation = false
  rangeForm.location = ''
}

function shiftMonth(months: number) {
  const next = addMonths(currentMonth.value, months)
  if (next < currentMonthStart.value || next > maxMonthStart.value) return
  currentMonth.value = next
  selectedDate.value = ''
  resetRange()
}

function applyQuickAction(action: QuickAction) {
  let keys: string[] = []
  if (action === 'next-month-busy') {
    const nextMonth = addMonths(currentMonth.value, 1)
    if (nextMonth > maxMonthStart.value) return
    currentMonth.value = nextMonth
    keys = monthDateKeys(nextMonth, () => true, today)
  } else if (action === 'weekdays-busy') {
    keys = monthDateKeys(currentMonth.value, (date) => date.getDay() >= 1 && date.getDay() <= 5, today)
  } else if (action === 'weekends-busy') {
    keys = monthDateKeys(currentMonth.value, (date) => date.getDay() === 0 || date.getDay() === 6, today)
  } else {
    keys = monthDateKeys(currentMonth.value, () => true, today)
  }

  let next = availabilityDays.value
  for (const key of keys) {
    const current = getAvailabilityDay(next, key)
    next = action === 'clear-month'
      ? setAvailabilityDay(next, key, 'free', current.location || '', today)
      : setAvailabilityDay(next, key, 'busy', current.location || '', today)
  }
  availabilityDays.value = next
  availabilityDirty.value = true
  selectedDate.value = ''
  resetRange()
  toastMessage.value = action === 'clear-month'
    ? '已清除本月忙碌标记，保存后生效'
    : `已批量更新 ${keys.length} 天，保存后生效`
}

function validateSettings() {
  Object.keys(errors).forEach((key) => { errors[key] = '' })
  const notice = Number(form.advance_notice)
  const daily = Number(form.max_daily_bookings)
  const maxDate = parseDateKey(form.max_booking_date)
  if (form.advance_notice === '' || !Number.isInteger(notice) || notice < 0 || notice > 720) {
    errors.advance_notice = '请输入 0–720 之间的整数小时。'
  }
  if (form.max_daily_bookings === '' || !Number.isInteger(daily) || daily < 1 || daily > 20) {
    errors.max_daily_bookings = '请输入 1–20 之间的每日接单量。'
  }
  if (!maxDate || maxDate < today || maxDate > addDays(today, MAX_AVAILABILITY_DAYS)) {
    errors.max_booking_date = '请选择未来 365 天内的日期。'
  }
  const firstError = Object.keys(errors).find((key) => errors[key])
  if (firstError) {
    activeSection.value = 'service'
    requestError.value = errors[firstError]
    document.getElementById(firstError.replaceAll('_', '-'))?.focus()
  }
  return !firstError
}

function hydrateSettings(profile: Awaited<ReturnType<typeof getPhotographerSettings>>) {
  hydrating.value = true
  form.equipment = profile?.equipment || ''
  form.advance_notice = Number(profile?.advance_notice ?? 24)
  form.max_daily_bookings = Number(profile?.max_daily_bookings ?? 5)
  form.max_booking_date = profile?.max_booking_date || maxAllowedDateKey
  styles.value = [...(profile?.styles || [])]
  availabilityDays.value = hydrateAvailabilityDays(profile?.availability_exceptions, today)
  selectedDate.value = ''
  resetRange()
  serviceDirty.value = false
  availabilityDirty.value = false
  hydrating.value = false
}

async function loadSettings() {
  if (!auth.user || !auth.isPhotographer) return
  loading.value = true
  error.value = ''
  requestError.value = ''
  try {
    const profile = await getPhotographerSettings(auth.user.id)
    hydrateSettings(profile)
  } catch (loadError) {
    error.value = getApiErrorMessage(loadError)
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  if (!auth.user || saving.value || !hasUnsavedChanges.value || !validateSettings()) return
  saving.value = true
  requestError.value = ''
  try {
    const profile = await savePhotographerSettings({
      equipment: form.equipment.trim(),
      styles: [...styles.value],
      available_hours: [],
      availability_exceptions: buildAvailabilityExceptions(availabilityDays.value, today),
      advance_notice: Number(form.advance_notice),
      max_daily_bookings: Number(form.max_daily_bookings),
      max_booking_date: form.max_booking_date,
    })
    hydrateSettings(profile)
    toastMessage.value = '档期与服务设置已保存'
  } catch (saveError) {
    requestError.value = getApiErrorMessage(saveError)
  } finally {
    saving.value = false
  }
}

async function confirmDiscardChanges() {
  if (!hasUnsavedChanges.value) return true
  const alert = await alertController.create({
    header: '放弃未保存修改？',
    message: '服务能力或档期日历中还有未保存内容，放弃后无法恢复。',
    buttons: [
      { text: '继续编辑', role: 'cancel' },
      { text: '放弃修改', role: 'destructive' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'destructive'
}

async function confirmReload() {
  if (!await confirmDiscardChanges()) return
  await loadSettings()
}

async function refresh(event: RefresherCustomEvent) {
  if (await confirmDiscardChanges()) await loadSettings()
  await event.target.complete()
}

watch(
  [
    () => form.equipment,
    () => form.advance_notice,
    () => form.max_daily_bookings,
    () => form.max_booking_date,
    styles,
  ],
  () => { if (!hydrating.value) serviceDirty.value = true },
  { deep: true, flush: 'sync' },
)

onBeforeRouteLeave(async () => confirmDiscardChanges())
onMounted(async () => {
  await auth.initialize()
  if (auth.isPhotographer) await loadSettings()
  else loading.value = false
})
</script>

<style scoped>
.settings-content { --background: var(--paper); --padding-bottom: calc(96px + env(safe-area-inset-bottom)); }
.settings-shell { display: grid; width: min(100%, 720px); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); gap: var(--space-5); }
.settings-intro { display: grid; grid-template-columns: 46px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.settings-intro > span { display: grid; width: 46px; height: 46px; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.settings-intro p { margin: 0 0 3px; color: var(--brand); font-size: 10px; font-weight: 850; letter-spacing: .12em; text-transform: uppercase; }
.settings-intro h1 { margin: 0; font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.35; }
.settings-intro small { display: block; margin-top: 6px; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.settings-form, .calendar-workspace { display: grid; gap: var(--space-5); }
.settings-card, .calendar-card { display: grid; gap: var(--space-4); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.card-heading { display: grid; grid-template-columns: 38px minmax(0, 1fr); align-items: center; gap: var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--neu-light); box-shadow: 0 1px 0 var(--neu-shade-soft); }
.card-heading > span { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 50%; background: var(--brand-soft); color: var(--brand); }
.card-heading h2 { margin: 0; font-size: var(--text-base); }
.card-heading p { margin: 3px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.55; }
.settings-field { display: grid; gap: 7px; }
.settings-field label, .status-fieldset legend { color: var(--ink); font-size: var(--text-sm); font-weight: 750; }
.settings-field label span { color: var(--ink-tertiary); font-size: var(--text-xs); font-weight: 500; }
.settings-field > small { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }
.settings-input, .settings-textarea { width: 100%; min-height: var(--touch-target); padding: 0 var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); outline: none; }
.settings-textarea { min-height: 120px; padding-block: var(--space-3); line-height: 1.65; resize: vertical; }
.settings-input:focus, .settings-textarea:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px rgba(45, 90, 39, 0.26); }
.settings-input[aria-invalid="true"] { border-color: var(--danger); }
.settings-input:disabled, .settings-textarea:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); }
.settings-error { margin: 0; color: var(--danger); font-size: var(--text-xs); line-height: 1.5; }
.field-grid { display: grid; gap: var(--space-4); }
.rule-summary { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3); border-left: 3px solid var(--brand); background: var(--brand-soft); color: var(--brand); }
.rule-summary p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.rule-summary strong { color: var(--ink); font-variant-numeric: tabular-nums; }
.month-toolbar { display: grid; grid-template-columns: 48px minmax(0, 1fr) 48px; align-items: center; gap: var(--space-2); text-align: center; }
.month-toolbar small { color: var(--ink-tertiary); font-size: 11px; }
.month-toolbar h2 { margin: 2px 0 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.month-button { display: grid; width: 48px; height: 48px; place-items: center; border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); }
.month-button:disabled { color: var(--ink-tertiary); opacity: .45; }
.month-stats { display: grid; grid-template-columns: repeat(3, 1fr); overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.month-stats span { display: grid; min-height: 58px; place-items: center; align-content: center; gap: 2px; border-right: 1px solid var(--neu-light); box-shadow: 1px 0 0 var(--neu-shade-soft); background: var(--paper); }
.month-stats span:last-child { border-right: 0; }
.month-stats small { color: var(--ink-tertiary); font-size: 10px; }
.month-stats strong { color: var(--brand); font-size: var(--text-base); font-variant-numeric: tabular-nums; }
.month-stats .busy strong { color: var(--danger); }
.calendar-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; color: var(--ink-secondary); font-size: 11px; }
.calendar-legend span { display: inline-flex; align-items: center; gap: 5px; }
.calendar-legend i { width: 9px; height: 9px; border: 0; border-radius: 50%; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.calendar-legend i.busy { border-color: var(--danger); background: rgba(163, 59, 50, .15); }
.calendar-legend small { width: 100%; color: var(--ink-tertiary); font-size: 11px; }
.calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 3px; }
.weekday { display: grid; min-height: 28px; place-items: center; color: var(--ink-tertiary); font-size: 10px; font-weight: 750; }
.date-cell { position: relative; display: grid; min-width: 0; min-height: 52px; place-items: center; align-content: center; gap: 2px; padding: 3px 1px; border: 0; border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); }
.date-cell > span { font-size: var(--text-xs); font-weight: 800; font-variant-numeric: tabular-nums; }
.date-cell > small { color: var(--brand); font-size: 9px; font-weight: 800; }
.date-cell > i { position: absolute; top: 3px; right: 3px; width: 5px; height: 5px; border-radius: 50%; background: var(--warning); }
.date-cell.busy { border-color: rgba(163, 59, 50, .25); background: #fbefed; }
.date-cell.busy > small { color: var(--danger); }
.date-cell.today { box-shadow: inset 0 0 0 1px var(--brand); }
.date-cell.selected, .date-cell.range-edge { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); border: 0; }
.date-cell.selected > small, .date-cell.range-edge > small { color: var(--white); }
.date-cell.in-range:not(.range-edge) { border-color: var(--brand); background: var(--brand-soft); }
.date-cell:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); opacity: .42; }
.date-cell.blank { border-color: transparent; background: transparent; }
.status-fieldset { min-width: 0; margin: 0; padding: 0; border: 0; background: var(--paper); box-shadow: var(--neu-inset); }
.status-fieldset legend { margin-bottom: 7px; }
.status-toggle { display: grid; grid-template-columns: repeat(2, 1fr); overflow: hidden; border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.status-toggle button { min-height: var(--touch-target); border: 0; border-right: 1px solid var(--neu-light); box-shadow: 1px 0 0 var(--neu-shade-soft); background: var(--paper); color: var(--ink-secondary); font-weight: 750; }
.status-toggle button:last-child { border-right: 0; }
.status-toggle button.active { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.status-toggle button.danger.active { background: var(--danger); }
.editor-actions { display: grid; grid-template-columns: 1.25fr 1fr; gap: var(--space-3); }
.editor-actions button, .quick-grid button { min-height: var(--touch-target); padding: 0 var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); font-size: var(--text-xs); font-weight: 750; }
.editor-actions button.primary { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); border: 0; }
.editor-actions button:disabled { color: var(--ink-tertiary); opacity: .5; }
.editor-empty { margin: 0; color: var(--ink-tertiary); font-size: var(--text-sm); line-height: 1.65; }
.location-check { display: flex; min-height: var(--touch-target); align-items: center; justify-content: space-between; gap: var(--space-4); }
.location-check > span { display: grid; gap: 3px; }
.location-check strong { font-size: var(--text-sm); }
.location-check small { color: var(--ink-tertiary); font-size: var(--text-xs); }
.location-check input { width: 22px; height: 22px; accent-color: var(--brand); }
.quick-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-2); }
.quick-grid button.danger { color: var(--danger); }
.settings-request-error, .unsaved-note { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-3); border-radius: var(--radius-md); font-size: var(--text-sm); line-height: 1.55; }
.settings-request-error { border: 1px solid rgba(163, 59, 50, .28); background: #fbefed; color: var(--danger); }
.unsaved-note { border-left: 3px solid var(--warning); background: #f8f2df; color: var(--ink-secondary); }
.settings-request-error svg, .unsaved-note svg { flex: 0 0 auto; margin-top: 1px; }
.settings-footer { background: var(--paper); }
.settings-footer-actions { display: grid; grid-template-columns: minmax(112px, .72fr) minmax(0, 1.28fr); gap: var(--space-3); width: min(100%, 720px); margin: 0 auto; padding: var(--space-3) var(--space-4) calc(var(--space-3) + env(safe-area-inset-bottom)); border-top: 1px solid var(--neu-light); box-shadow: inset 0 1px 0 var(--neu-shade-soft); background: var(--paper); }
.settings-footer-actions button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); font-weight: 750; }
.settings-footer-actions button.primary { background: var(--neu-surface-brand); box-shadow: -4px -4px 10px var(--neu-light), 4px 4px 12px var(--neu-shade); color: var(--white); }
.settings-footer-actions button:disabled { background: var(--paper-deep); box-shadow: none; color: var(--ink-tertiary); opacity: .68; }
.settings-footer-actions ion-spinner { width: 20px; height: 20px; }
@media (min-width: 640px) {
  .field-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .calendar-card { padding: var(--space-5); }
  .date-cell { min-height: 64px; }
}
</style>
