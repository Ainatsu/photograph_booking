<template>
  <div class="page">
    <h2 class="page-title">预约拍摄</h2>

    <!-- 摄影师信息 -->
    <div class="section-card" v-loading="loadingProfile">
      <div class="section-header">
        <span>摄影师：{{ profile?.user_display_name || '加载中...' }}</span>
      </div>
      <div class="section-body">{{ profile?.bio || '暂无简介' }}</div>
    </div>

    <!-- 选择方案 -->
    <div class="section-card">
      <div class="section-header"><span>选择方案</span></div>
      <div class="section-body">
        <template v-if="isPackageLocked">
          <div class="locked-package">
            <span class="locked-name">{{ selectedPkg?.name }}</span>
            <span class="locked-price">¥{{ selectedPkg?.price }} / {{ selectedPkg?.duration }}分钟</span>
          </div>
        </template>
        <template v-else>
          <el-radio-group v-model="selectedPackageIndex" v-if="packages.length">
            <el-radio
              v-for="(pkg, idx) in packages"
              :key="pkg.id || idx"
              :value="idx"
              border
              style="margin-right: 12px; margin-bottom: 12px;"
            >
              {{ pkg.name }} - ¥{{ pkg.price }} / {{ pkg.duration }}分钟
            </el-radio>
          </el-radio-group>
          <el-empty v-else description="该摄影师暂无方案" />
        </template>
      </div>
    </div>

    <!-- 选择时间 -->
    <div class="section-card">
      <div class="section-header"><span>选择时间</span></div>
      <div class="section-body">
        <div v-if="availability" class="availability-meta">
          <span>时区：{{ availability.timezone }}</span>
          <span>需提前 {{ availability.advance_notice_hours }} 小时预约</span>
          <span>档期间预留 {{ availability.buffer_minutes }} 分钟缓冲</span>
        </div>
        <div class="availability-days" v-loading="loadingAvailability">
          <button
            v-for="day in availability?.days || []"
            :key="day.date"
            type="button"
            class="day-option"
            :class="{ active: selectedDate === day.date }"
            :disabled="!day.slots.length"
            @click="selectDate(day.date)"
          >
            <strong>{{ formatSlotDate(day.date) }}</strong>
            <span>{{ day.weekday }}</span>
            <small>{{ day.slots.length ? '可预约' : (day.unavailable_reason || '暂无档期') }}</small>
          </button>
        </div>
        <div v-if="selectedDay?.slots?.length" class="booking-date-hint">该日期可预约</div>
        <div v-if="false" class="slot-options" aria-label="可预约时间">
          <button
            v-for="slot in selectedDay.slots"
            :key="slot.start_at"
            type="button"
            class="slot-option"
            :class="{ active: selectedSlot?.start_at === slot.start_at }"
            @click="selectedSlot = slot"
          >
            {{ slot.label }}
          </button>
        </div>
        <el-empty v-else-if="!loadingAvailability" description="当前日期范围暂无可容纳该套餐的档期，请联系摄影师或稍后再看" />
      </div>
    </div>

    <!-- 拍摄需求 -->
    <div class="section-card">
      <div class="section-header"><span>拍摄需求（选填）</span></div>
      <div class="section-body">
        <el-input
          v-model="notes"
          type="textarea"
          :rows="4"
          placeholder="请输入您的拍摄需求，如风格偏好、拍摄地点等"
        />
      </div>
    </div>

    <el-button
      type="primary"
      size="large"
      @click="submitOrder"
      :loading="submitting"
      :disabled="!canSubmit"
    >
      提交预约
    </el-button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPhotographerAvailableSlots, getPhotographerDetail } from '../api/photographer'
import { createOrder } from '../api/order'

const route = useRoute()
const router = useRouter()

const profile = ref(null)
const loadingProfile = ref(false)
const packages = computed(() => profile.value?.packages || [])

// 检查是否从方案页携带了指定套餐（支持 index 或 name）
const isPackageLocked = computed(() => route.query.packageId !== undefined || route.query.package !== undefined || route.query.packageName !== undefined)
const lockedPackageIndex = computed(() => {
  if (route.query.packageId !== undefined) {
    return packages.value.findIndex(p => String(p.id) === String(route.query.packageId))
  }
  if (route.query.package !== undefined) {
    return parseInt(route.query.package)
  }
  if (route.query.packageName) {
    return packages.value.findIndex(p => p.name === route.query.packageName)
  }
  return -1
})
const selectedPkg = computed(() => {
  if (isPackageLocked.value && lockedPackageIndex.value >= 0) {
    return packages.value[lockedPackageIndex.value] || null
  }
  return null
})

const selectedPackageIndex = ref(-1)
const availability = ref(null)
const loadingAvailability = ref(false)
const selectedDate = ref('')
const selectedSlot = ref(null)
const notes = ref('')
const submitting = ref(false)
const activePackage = computed(() => (
  isPackageLocked.value ? selectedPkg.value : packages.value[selectedPackageIndex.value]
))
const selectedDay = computed(() => (
  availability.value?.days?.find(day => day.date === selectedDate.value) || null
))

const canSubmit = computed(() => {
    const hasPackage = isPackageLocked.value ? !!selectedPkg.value : selectedPackageIndex.value >= 0
    return hasPackage && !!selectedSlot.value
})

const formatSlotDate = value => new Date(`${value}T00:00:00`).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
const selectDate = value => {
  selectedDate.value = value
  selectedSlot.value = selectedDay.value?.slots?.[0] || null
}

const fetchAvailability = async () => {
  const pkg = activePackage.value
  const userId = route.params.userId
  if (!pkg || !userId) {
    availability.value = null
    return
  }
  loadingAvailability.value = true
  selectedDate.value = ''
  selectedSlot.value = null
  try {
    const { data } = await getPhotographerAvailableSlots(userId, {
      days: 365,
      duration_minutes: Number(pkg.duration || 120),
      buffer_minutes: Number(pkg.buffer_minutes || 30),
    })
    availability.value = data
    selectedDate.value = data.days?.find(day => day.slots?.length)?.date || ''
    selectedSlot.value = data.days?.find(day => day.date === selectedDate.value)?.slots?.[0] || null
  } finally {
    loadingAvailability.value = false
  }
}

const fetchProfile = async () => {
    const userId = route.params.userId
    if (!userId) return
    loadingProfile.value = true
    try {
        const res = await getPhotographerDetail(userId)
        profile.value = res.data
        await fetchAvailability()
    } finally {
        loadingProfile.value = false
    }
}

const submitOrder = async () => {
    const pkg = isPackageLocked.value
      ? selectedPkg.value
      : packages.value[selectedPackageIndex.value]

    if (!pkg) {
        ElMessage.warning('请选择一个方案')
        return
    }
    if (!selectedSlot.value) {
        ElMessage.warning('请选择一个真实可用档期')
        return
    }

    submitting.value = true
    try {
        const isoTime = new Date(selectedSlot.value.start_at).toISOString()
        const res = await createOrder({
            package_id: pkg.id,
            photographer_id: profile.value.user_id,
            appointment_time: isoTime,
            notes: notes.value || undefined
        })
        ElMessage.success('预约提交成功，等待摄影师确认')
        const orderId = res?.data?.id
        router.push(orderId ? `/orders/${orderId}` : '/profile?tab=orders')
    } catch {
    } finally {
        submitting.value = false
    }
}

onMounted(fetchProfile)
watch(selectedPackageIndex, fetchAvailability)
</script>

<style scoped>
.page {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 var(--space-4) var(--space-8);
}

.page-title {
  font-family: var(--font-sans);
  font-size: var(--text-xl);
  color: var(--color-ink);
  margin: var(--space-6) 0 var(--space-6);
  font-weight: 700;
}

/* ── Section card (replaces el-card) ── */
.section-card {
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
  overflow: hidden;
}

.section-header {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-divider);
  font-family: var(--font-sans);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-ink);
}

.section-body {
  padding: var(--space-4);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  color: var(--color-ink-secondary);
  line-height: 1.6;
}

/* ── Locked package display ── */
.locked-package {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}

.locked-name {
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--color-ink);
  font-family: var(--font-sans);
}

.locked-price {
  font-size: var(--text-sm);
  color: var(--color-ink);
  font-family: var(--font-sans);
}

/* ── Submit button ── */
.page > .el-button--primary {
  background: var(--color-brand);
  border-color: var(--color-brand);
  font-family: var(--font-sans);
}

.page > .el-button--primary:hover {
  background: var(--color-brand-hover);
  border-color: var(--color-brand-hover);
}

.page > .el-button--primary:active {
  background: var(--color-brand-active);
  border-color: var(--color-brand-active);
}
.availability-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 14px;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
}

.availability-days {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
  gap: 8px;
}

.day-option,
.slot-option {
  min-height: 44px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-ink);
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease;
}

.day-option {
  display: grid;
  gap: 3px;
  padding: 10px;
  text-align: left;
}

.day-option span,
.day-option small {
  color: var(--color-ink-secondary);
}

.day-option.active,
.slot-option.active {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.day-option:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.slot-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.slot-option {
  padding: 8px 14px;
}

</style>
