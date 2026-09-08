<template>
  <ion-page>
    <DetailHeader title="我的订单" default-href="/tabs/profile" />

    <ion-content class="orders-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新订单" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="orders-shell">
        <section class="orders-intro">
          <span><ClipboardList :size="23" aria-hidden="true" /></span>
          <div>
            <h1>订单进度</h1>
            <p>确认、支付、履约和验收状态都以服务端记录为准。</p>
          </div>
        </section>

        <!-- 订单 / 应邀 切换（仅摄影师） -->
        <SegmentSwitch
          v-if="auth.isPhotographer"
          :model-value="activeModule"
          class="module-segment"
          :items="moduleItems"
          label="当前视图"
          @update:model-value="handleModuleSwitch"
        />

        <template v-if="!auth.isPhotographer || activeModule === 'orders'">

        <div class="filter-strip" role="tablist" aria-label="订单筛选">
          <button
            v-for="item in filters"
            :key="item.value"
            type="button"
            class="filter-button pressable"
            :class="{ active: activeFilter === item.value }"
            role="tab"
            :aria-selected="activeFilter === item.value"
            @click="activeFilter = item.value"
          >
            {{ item.label }}
            <span>{{ item.count }}</span>
          </button>
        </div>

        <FeedSkeleton v-if="loading" :count="4" />
        <StatePanel
          v-else-if="error"
          tone="error"
          title="订单暂时无法加载"
          :description="error"
          action-label="重新加载"
          @action="loadOrders"
        />
        <StatePanel
          v-else-if="!filteredOrders.length"
          :title="activeFilter === 'all' ? '还没有订单' : '这个分类暂时没有订单'"
          :description="activeRole === 'customer' ? '选择摄影方案并提交真实档期后，订单会出现在这里。' : '客户预约并提交后，待处理订单会出现在这里。'"
          :action-label="activeRole === 'customer' ? '去浏览方案' : undefined"
          @action="router.push({ name: 'showcase' })"
        />

        <div v-else class="order-list">
          <article
            v-for="order in filteredOrders"
            :key="order.id"
            class="order-card"
            :class="{ highlighted: createdOrderId === order.id }"
          >
            <header class="order-card-header">
              <div>
                <small>订单 #{{ order.id }}</small>
                <h2>{{ getOrderTitle(order) }}</h2>
              </div>
              <span class="status-badge" :class="order.status">{{ getOrderStatusLabel(order.status) }}</span>
            </header>

            <div class="order-facts">
              <div><UserRound :size="17" aria-hidden="true" /><span>{{ getOrderCounterparty(order, activeRole) }}</span></div>
              <div><CalendarDays :size="17" aria-hidden="true" /><span>{{ formatOrderDate(order.appointment_time) }}</span></div>
              <div><Clock3 :size="17" aria-hidden="true" /><span>{{ formatDuration(order.duration_minutes) }}</span></div>
              <div><WalletCards :size="17" aria-hidden="true" /><span>{{ orderAmount(order) }}</span></div>
            </div>

            <p class="next-step">{{ getOrderNextStep(order, activeRole) }}</p>
            <p v-if="order.notes" class="order-notes">{{ order.notes }}</p>

            <footer class="order-actions">
              <button
                type="button"
                class="secondary detail-button pressable"
                @click="openOrderDetail(order)"
              >
                <FileText :size="17" aria-hidden="true" />
                查看详情
              </button>
              <button
                v-for="action in orderActions(order)"
                :key="action.id"
                type="button"
                class="pressable"
                :class="action.tone"
                :disabled="processingOrderId === order.id"
                @click="runAction(order, action.id)"
              >
                <ion-spinner v-if="processingOrderId === order.id && processingAction === action.id" name="crescent" aria-hidden="true" />
                <component v-else :is="action.icon" :size="17" aria-hidden="true" />
                {{ action.label }}
              </button>
            </footer>
          </article>
        </div>
        </template>

        <template v-if="auth.isPhotographer && activeModule === 'applications'">
          <nav class="filter-strip" role="tablist" aria-label="应邀筛选">
              <button
                v-for="item in applicationFilters"
                :key="item.value"
                type="button"
                class="filter-button pressable"
                :class="{ active: applicationFilter === item.value }"
                role="tab"
                :aria-selected="applicationFilter === item.value"
                @click="applicationFilter = item.value"
              >
                {{ item.label }}
                <span>{{ item.count }}</span>
              </button>
            </nav>

            <FeedSkeleton v-if="applicationsLoading" :count="4" />
            <StatePanel
              v-else-if="applicationsError"
              tone="error"
              title="应邀列表加载失败"
              :description="applicationsError"
              action-label="重新加载"
              @action="loadApplications"
            />
            <StatePanel
              v-else-if="!filteredApplications.length"
              title="还没有提交过应邀"
              description="浏览公开企划，选择与作品风格和档期匹配的需求提交方案。"
              action-label="浏览企划"
              @action="router.push({ name: 'showcase' })"
            />
            <section v-else class="order-list" aria-label="应邀列表">
              <article v-for="application in filteredApplications" :key="application.id" class="order-card">
                <header class="order-card-header">
                  <div>
                    <small>应邀 #{{ application.id }}</small>
                    <h2>{{ application.project?.title || `企划 #${application.project_id}` }}</h2>
                  </div>
                  <span class="status-badge" :class="'application-' + application.status">{{ applicationStatusLabel(application.status) }}</span>
                </header>
                <p class="application-proposal">{{ application.proposal_text }}</p>
                <div class="order-facts">
                  <div><MapPin :size="17" aria-hidden="true" /><span>{{ application.project?.city || '地点待沟通' }}</span></div>
                  <div><WalletCards :size="17" aria-hidden="true" /><span><strong>{{ formatCurrency(application.price_quote) }}</strong></span></div>
                </div>
                <footer class="order-actions">
                  <button type="button" class="secondary detail-button pressable" @click="openApplicationDetail(application)">
                    <FileText :size="17" aria-hidden="true" />
                    查看企划
                  </button>
                  <button
                    v-if="canEditApplication(application)"
                    type="button"
                    class="primary pressable"
                    @click="editApplication(application)"
                  >
                    <ClipboardPenLine :size="17" aria-hidden="true" />修改应邀
                  </button>
                </footer>
              </article>
            </section>
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
  </ion-page>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, ref, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonContent,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
  alertController,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  BadgeCheck,
  CalendarDays,
  Camera,
  CheckCheck,
  CircleX,
  ClipboardList,
  ClipboardPenLine,
  Clock3,
  CreditCard,
  FileText,
  MapPin,
  UserRound,
  WalletCards,
} from 'lucide-vue-next'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SegmentSwitch from '@/components/SegmentSwitch.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  acceptOrder,
  confirmMockPayment,
  confirmOrder,
  createOrderPayment,
  getCustomerOrders,
  getPhotographerOrders,
  rejectOrder,
  startOrder,
} from '@/api/orders'
import { getMyProjectApplications } from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import type { OrderItem } from '@/types/orders'
import type { ProjectApplication } from '@/types/discovery'
import { formatCurrency, formatDuration } from '@/utils/format'
import {
  canAcceptOrderDelivery,
  canStartOrderService,
  formatOrderDate,
  getOrderCounterparty,
  getOrderNextStep,
  getOrderStatusLabel,
  getOrderTitle,
  isActiveOrder,
  isCompletedOrder,
} from '@/utils/order'
import { applicationStatusLabel } from '@/utils/project'
import { canEditProjectApplication } from '@/utils/project'

type OrderRole = 'customer' | 'photographer'
type FilterValue = 'all' | 'active' | 'completed' | 'cancelled'
type ActionId = 'confirm' | 'reject' | 'pay' | 'start' | 'accept'

interface OrderAction {
  id: ActionId
  label: string
  tone: 'primary' | 'secondary' | 'danger'
  icon: Component
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activeRole = ref<OrderRole>('customer')
const activeFilter = ref<FilterValue>('all')
const orders = ref<OrderItem[]>([])
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')
const processingOrderId = ref<number | null>(null)
const processingAction = ref<ActionId | null>(null)
let ordersRequestId = 0

// 应邀模块
const activeModule = ref<'orders' | 'applications'>('orders')
const moduleItems = computed(() => [
  { label: `订单·${activeRole.value === 'customer' ? '客户' : '摄影师'}`, value: 'orders' as const },
  { label: '应邀', value: 'applications' as const },
])

function handleModuleSwitch(value: string) {
  if (value === 'orders' && activeModule.value === 'orders') {
    activeRole.value = activeRole.value === 'customer' ? 'photographer' : 'customer'
  } else {
    activeModule.value = value as 'orders' | 'applications'
  }
}
const applications = ref<ProjectApplication[]>([])
const applicationsLoading = ref(false)
const applicationsError = ref('')
const applicationFilter = ref<string>('all')
let applicationsRequestId = 0
const applicationFilters = computed(() => [
  { label: '全部', value: 'all', count: applications.value.length },
  { label: '已提交', value: 'submitted', count: applications.value.filter((a) => a.status === 'submitted').length },
  { label: '已选中', value: 'selected', count: applications.value.filter((a) => a.status === 'selected').length },
  { label: '未通过', value: 'rejected', count: applications.value.filter((a) => a.status === 'rejected').length },
])
const filteredApplications = computed(() => {
  if (applicationFilter.value === 'all') return applications.value
  return applications.value.filter((a) => a.status === applicationFilter.value)
})

const createdOrderId = computed(() => Number(route.query.created || 0))
const filters = computed(() => [
  { label: '全部', value: 'all' as const, count: orders.value.length },
  { label: '进行中', value: 'active' as const, count: orders.value.filter(isActiveOrder).length },
  { label: '已完成', value: 'completed' as const, count: orders.value.filter(isCompletedOrder).length },
  { label: '已取消', value: 'cancelled' as const, count: orders.value.filter((order) => order.status === 'cancelled').length },
])
const filteredOrders = computed(() => {
  if (activeFilter.value === 'active') return orders.value.filter(isActiveOrder)
  if (activeFilter.value === 'completed') return orders.value.filter(isCompletedOrder)
  if (activeFilter.value === 'cancelled') return orders.value.filter((order) => order.status === 'cancelled')
  return orders.value
})

function orderAmount(order: OrderItem) {
  const amount = Number(order.final_price ?? order.package_price)
  return Number.isFinite(amount) && amount > 0 ? formatCurrency(amount) : '金额见订单快照'
}

function orderActions(order: OrderItem): OrderAction[] {
  if (order.active_reschedule_request || order.after_sales_status === 'dispute_open') return []
  if (activeRole.value === 'photographer' && order.status === 'pending') {
    return [
      { id: 'reject', label: '拒绝', tone: 'danger', icon: markRaw(CircleX) },
      { id: 'confirm', label: '确认预约', tone: 'primary', icon: markRaw(BadgeCheck) },
    ]
  }
  if (activeRole.value === 'customer' && (
    order.status === 'awaiting_customer_payment'
    || (order.status === 'confirmed' && order.payment_status === 'deposit_paid')
  )) {
    return [{
      id: 'pay',
      label: order.payment_status === 'deposit_paid' ? '支付尾款' : '完成演示支付',
      tone: 'primary',
      icon: markRaw(CreditCard),
    }]
  }
  if (activeRole.value === 'photographer' && canStartOrderService(order)) {
    return [{ id: 'start', label: '开始服务', tone: 'primary', icon: markRaw(Camera) }]
  }
  if (activeRole.value === 'customer' && canAcceptOrderDelivery(order)) {
    return [{ id: 'accept', label: '确认验收', tone: 'primary', icon: markRaw(CheckCheck) }]
  }
  return []
}

async function confirmDialog(header: string, message: string, confirmText = '确认') {
  const alert = await alertController.create({
    header,
    message,
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: confirmText, role: 'confirm' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'confirm'
}

async function promptRejectReason() {
  const alert = await alertController.create({
    header: '拒绝预约',
    message: '请说明原因，客户会在订单中看到。',
    inputs: [{ name: 'reason', type: 'textarea', placeholder: '例如：该时间已有拍摄安排', attributes: { maxlength: 500 } }],
    buttons: [
      { text: '取消', role: 'cancel' },
      { text: '确认拒绝', role: 'confirm' },
    ],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'confirm') return ''
  return String(result.data?.values?.reason || '').trim()
}

async function loadOrders() {
  const requestId = ++ordersRequestId
  loading.value = true
  error.value = ''
  try {
    const result = activeRole.value === 'customer'
      ? await getCustomerOrders({ limit: 100 })
      : await getPhotographerOrders({ limit: 100 })
    if (requestId !== ordersRequestId) return
    orders.value = result
  } catch (loadError) {
    if (requestId !== ordersRequestId) return
    error.value = getApiErrorMessage(loadError)
  } finally {
    if (requestId === ordersRequestId) loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  if (activeModule.value === 'orders') {
    await loadOrders()
  } else {
    await loadApplications()
  }
  event.target.complete()
}

async function runAction(order: OrderItem, action: ActionId) {
  let reason = ''
  if (action === 'confirm' && !(await confirmDialog('确认预约', '确认后客户需要完成支付，档期将在支付后正式锁定。'))) return
  if (action === 'reject') {
    reason = await promptRejectReason()
    if (!reason) {
      toastMessage.value = '请填写拒绝原因。'
      return
    }
  }
  if (action === 'pay' && !(await confirmDialog('演示支付', '这是本地演示支付，不会产生真实扣款。', '确认支付'))) return
  if (action === 'start' && !(await confirmDialog('开始服务', '确认将订单标记为履约中？'))) return
  if (action === 'accept' && !(await confirmDialog('确认验收', '验收后订单将完成，请先确认交付内容无误。'))) return

  processingOrderId.value = order.id
  processingAction.value = action
  try {
    if (action === 'confirm') await confirmOrder(order.id)
    if (action === 'reject') await rejectOrder(order.id, reason)
    if (action === 'pay') {
      const storageKey = `mobile-payment-idempotency:${order.id}:${order.payment_status || 'unpaid'}`
      let idempotencyKey = localStorage.getItem(storageKey)
      if (!idempotencyKey) {
        idempotencyKey = `mobile-payment-${order.id}-${Date.now()}-${Math.random().toString(16).slice(2)}`
        localStorage.setItem(storageKey, idempotencyKey)
      }
      const payment = await createOrderPayment(order.id, idempotencyKey)
      await confirmMockPayment(payment)
      localStorage.removeItem(storageKey)
    }
    if (action === 'start') await startOrder(order.id)
    if (action === 'accept') await acceptOrder(order.id)
    toastMessage.value = {
      confirm: '预约已确认，等待客户支付。',
      reject: '预约已拒绝。',
      pay: '演示支付成功，档期已锁定。',
      start: '订单已进入履约中。',
      accept: '交付已验收，订单完成。',
    }[action]
    await loadOrders()
  } catch (actionError) {
    toastMessage.value = getApiErrorMessage(actionError)
  } finally {
    processingOrderId.value = null
    processingAction.value = null
  }
}

function openOrderDetail(order: OrderItem) {
  router.push({ name: 'order-detail', params: { orderId: order.id } })
}

async function loadApplications() {
  const requestId = ++applicationsRequestId
  applicationsLoading.value = true
  applicationsError.value = ''
  try {
    const result = await getMyProjectApplications()
    if (requestId !== applicationsRequestId) return
    applications.value = result
  } catch (loadError) {
    if (requestId !== applicationsRequestId) return
    applicationsError.value = getApiErrorMessage(loadError)
  } finally {
    if (requestId === applicationsRequestId) applicationsLoading.value = false
  }
}

function openApplicationDetail(application: ProjectApplication) {
  router.push({ name: 'project-detail', params: { projectId: application.project_id } })
}

function editApplication(application: ProjectApplication) {
  router.push({
    name: 'project-apply',
    params: { projectId: application.project_id },
    query: { edit: String(application.id) },
  })
}

function canEditApplication(application: ProjectApplication): boolean {
  return canEditProjectApplication(application)
}

watch(activeModule, (next) => {
  if (next === 'applications' && !applications.value.length && !applicationsLoading.value) {
    void loadApplications()
  }
})

watch(activeRole, () => {
  activeFilter.value = 'all'
  void loadOrders()
})

onMounted(async () => {
  await auth.initialize()
  const requestedRole = String(route.query.role || '')
  activeRole.value = requestedRole === 'photographer' && auth.isPhotographer ? 'photographer' : 'customer'
  await loadOrders()
  if (createdOrderId.value) {
    toastMessage.value = `预约已提交，订单 #${createdOrderId.value} 正在等待摄影师确认。`
  }
})
</script>

<style scoped>
.orders-content { --background: var(--paper); }
.orders-shell { width: min(100%, var(--content-max)); min-height: 100%; margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.orders-intro { display: flex; gap: var(--space-3); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise); }
.orders-intro > span { display: grid; width: 46px; height: 46px; flex: 0 0 auto; place-items: center; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.orders-intro h1 { margin: 1px 0 4px; font-family: var(--font-serif); font-size: var(--text-lg); }
.orders-intro p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.module-segment { margin-top: var(--space-4); }
.application-proposal { margin: var(--space-3) 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.filter-strip { display: flex; gap: var(--space-2); margin: var(--space-4) calc(var(--space-4) * -1); padding: 0 var(--space-4) 3px; overflow-x: auto; }
.filter-button { display: inline-flex; min-height: 40px; flex: 0 0 auto; align-items: center; gap: 6px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-pill); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink-secondary); font-size: var(--text-sm); font-weight: 650; }
.filter-button span { min-width: 19px; padding: 1px 5px; border-radius: var(--radius-pill); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-tertiary); font-size: var(--text-2xs); }
.filter-button.active { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); border: 0; }
.filter-button.active span { background: rgba(255,255,255,.18); color: var(--white); }
.order-list { display: grid; gap: var(--space-4); }
.order-card { padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.order-card.highlighted { border-color: var(--brand); box-shadow: 0 0 0 3px var(--focus-ring); }
.order-card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.order-card-header small { color: var(--ink-tertiary); font-size: var(--text-2xs); font-variant-numeric: tabular-nums; }
.order-card-header h2 { margin: 4px 0 0; font-family: var(--font-serif); font-size: var(--text-base); line-height: 1.45; }
.status-badge { display: inline-flex; min-height: 29px; flex: 0 0 auto; align-items: center; padding: 4px 9px; border-radius: var(--radius-pill); background: var(--brand-soft); color: var(--brand); font-size: var(--text-2xs); font-weight: 750; }
.status-badge.awaiting_customer_payment { background: var(--warning-soft); color: var(--warning); }
.status-badge.cancelled { background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-secondary); }
.status-badge.delivered { background: var(--brand-soft); color: var(--brand); }
.order-facts { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-2); margin-top: var(--space-4); padding: var(--space-3); border-radius: var(--radius-md); background: var(--paper); }
.order-facts div { display: flex; min-width: 0; align-items: center; gap: 6px; color: var(--brand); }
.order-facts span { overflow: hidden; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }
.next-step { margin: var(--space-3) 0 0; color: var(--ink); font-size: var(--text-sm); font-weight: 650; line-height: 1.55; }
.order-notes { margin: var(--space-2) 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.6; }
.order-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--divider); }
.order-actions button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 6px; padding: 0 var(--space-4); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: 750; }
.order-actions button.primary { border: 0; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
.order-actions button.secondary { border: 0; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
.order-actions button.danger { border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--danger); }
.order-actions .detail-button { margin-right: auto; }
.order-actions button:disabled { opacity: .55; }
.order-actions ion-spinner { width: 18px; height: 18px; }
</style>
