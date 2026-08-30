<template>
  <div class="orders-container">
    <h2>我的订单</h2>

    <el-tabs v-model="activeTab" @tab-change="fetchOrders">
      <el-tab-pane label="我预约的" name="customer" v-if="isCustomer" />
      <el-tab-pane label="接到的预约" name="photographer" v-if="isPhotographer" />
    </el-tabs>

    <div class="queue-tabs" aria-label="订单责任筛选">
      <button
        v-for="item in queueOptions"
        :key="item.value"
        type="button"
        :class="{ active: queueFilter === item.value }"
        @click="setQueueFilter(item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <div v-if="activeFilterLabel" class="filter-bar">
      <el-tag type="info">{{ activeFilterLabel }}</el-tag>
      <el-button text size="small" @click="clearFilter">清除筛选</el-button>
    </div>

    <div class="order-card-list" v-loading="loading">
      <article v-for="row in orders" :key="row.id" class="order-card">
        <div class="order-card-main">
          <div class="order-card-heading">
            <span class="order-card-number">订单 #{{ row.id }}</span>
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </div>
          <h3>{{ formatOrderTitle(row.package_snapshot) }}</h3>
          <p v-if="row.notes" class="order-card-note">{{ row.notes }}</p>
          <div class="order-card-facts">
            <div><span>预约日期</span><strong>{{ formatDateOnly(row.appointment_time) }}</strong></div>
            <div><span>下一步</span><strong>{{ orderNextText(row) }}</strong></div>
            <div v-if="activeReschedule(row)"><span>改期日期</span><strong class="pending-reschedule">{{ formatDateOnly(activeReschedule(row).requested_appointment_time) }}</strong></div>
          </div>
        </div>
        <div class="order-card-actions">
          <span v-if="row.action_deadline_at" class="action-deadline" :class="{ overdue: row.overdue_at }">
            {{ row.overdue_at ? '已逾期' : '处理期限' }}：{{ formatDateOnly(row.action_deadline_at) }}
          </span>
          <el-button type="primary" plain @click="goOrderDetail(row)">{{ orderCardActionLabel(row) }}</el-button>
        </div>
      </article>
      <el-empty v-if="!loading && !orders.length" description="暂无订单" />
    </div>

    <el-table v-if="false" :data="orders" v-loading="loading" stripe>
      <el-table-column prop="id" label="订单号" width="80" />
      <el-table-column prop="package_snapshot" label="方案" min-width="200" />
      <el-table-column label="预约日期" width="210">
        <template #default="{ row }">
          <div>{{ new Date(row.appointment_time).toLocaleDateString('zh-CN') }}</div>
          <div v-if="activeReschedule(row)" class="pending-reschedule">
            改期候选：{{ new Date(activeReschedule(row).requested_appointment_time).toLocaleDateString('zh-CN') }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="170">
        <template #default="{ row }">
          <span class="next-step-text">{{ orderNextText(row) }}</span>
          <span v-if="row.action_deadline_at" class="action-deadline" :class="{ overdue: row.overdue_at }">
            {{ row.overdue_at ? '已逾期' : '截止' }}：{{ formatDeadline(row.action_deadline_at) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="340">
        <template #default="{ row }">
          <template v-if="row.after_sales_status === 'dispute_open'">
            <el-button type="warning" plain size="small" @click="goOrderDetail(row)">查看平台处理</el-button>
          </template>
          <template v-else-if="activeTab === 'customer'">
            <template v-if="row.status === 'awaiting_customer_payment' || (row.status === 'confirmed' && row.payment_status === 'deposit_paid')">
              <el-button type="primary" size="small" @click="goOrderDetail(row)">
                {{ row.payment_status === 'deposit_paid' ? '支付尾款' : '去支付' }}
              </el-button>
            </template>
            <template v-else-if="row.status === 'delivered'">
              <el-button type="primary" size="small" :loading="processingId === row.id" @click="handleAccept(row.id)">确认验收</el-button>
              <el-button size="small" @click="goOrderDetail(row)">查看/申请修改</el-button>
            </template>
            <template v-else-if="row.status === 'received'">
              <el-button type="primary" size="small" @click="openViewDelivery(row)">查看作品</el-button>
              <el-button type="success" size="small" @click="openReviewDialog(row)">评价</el-button>
            </template>
            <template v-else-if="row.status === 'reviewed'">
              <el-button type="primary" size="small" @click="openViewDelivery(row)">查看作品</el-button>
              <el-button type="info" size="small" @click="openViewReview(row)">查看评价</el-button>
            </template>
            <template v-else-if="row.status === 'completed'">
              <el-button type="primary" size="small" @click="openViewDelivery(row)">查看作品</el-button>
              <el-button v-if="!row.rating" type="success" size="small" @click="openReviewDialog(row)">评价</el-button>
              <el-button v-else type="info" size="small" @click="openViewReview(row)">查看评价</el-button>
            </template>
            <span v-else>--</span>
          </template>
          <template v-else-if="activeReschedule(row)">
            <el-button type="warning" size="small" @click="goOrderDetail(row)">处理改期</el-button>
          </template>
          <template v-else-if="row.status === 'pending'">
            <el-button type="success" size="small" :loading="processingId === row.id" @click="confirmOrderAction(row.id)">确认</el-button>
            <el-button type="danger" size="small" :disabled="processingId === row.id" @click="rejectOrderAction(row.id)">拒绝</el-button>
          </template>
          <template v-else-if="row.status === 'confirmed'">
            <el-button type="primary" size="small" :loading="processingId === row.id" @click="startOrderAction(row.id)">开始服务</el-button>
          </template>
          <template v-else-if="row.status === 'in_progress'">
            <el-button type="primary" size="small" @click="openDeliveryDialog(row)">交付作品</el-button>
          </template>
          <template v-else-if="row.status === 'delivered'">
            <el-button v-if="row.after_sales_status === 'revision_requested'" type="primary" size="small" @click="openDeliveryDialog(row)">重新交付</el-button>
            <el-button v-else type="primary" size="small" @click="openViewDelivery(row)">查看作品</el-button>
          </template>
          <template v-else-if="row.status === 'reviewed'">
            <el-button type="primary" size="small" @click="openViewDelivery(row)">查看作品</el-button>
            <el-button type="info" size="small" @click="openViewReview(row)">查看评价</el-button>
          </template>
          <template v-else-if="row.status === 'completed'">
            <el-button type="primary" size="small" @click="openViewDelivery(row)">查看作品</el-button>
            <el-button v-if="row.rating" type="info" size="small" @click="openViewReview(row)">查看评价</el-button>
          </template>
          <template v-else>
            <span>--</span>
          </template>
          <el-button size="small" @click="goOrderDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 交付作品弹窗 -->
    <el-dialog v-model="showDeliveryDialog" title="交付作品" width="500px" @closed="resetDeliveryForm">
      <el-form label-width="80px">
        <el-form-item label="上传作品">
          <el-upload
            v-model:file-list="deliveryFiles"
            :auto-upload="false"
            list-type="picture-card"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
        <el-form-item label="交付说明">
          <el-input
            v-model="deliveryDescription"
            type="textarea"
            :rows="3"
            placeholder="如：精修已完成，请查收"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeliveryDialog = false">取消</el-button>
        <el-button type="primary" @click="submitDelivery" :loading="submittingDelivery">确认交付</el-button>
      </template>
    </el-dialog>

    <!-- 查看作品弹窗 -->
    <el-dialog v-model="showViewDialog" title="交付作品" width="700px">
      <div v-if="currentViewOrder?.delivery?.description" class="view-desc">
        {{ currentViewOrder.delivery.description }}
      </div>
      <div class="view-images">
        <el-image
          v-for="(img, i) in (currentViewOrder?.delivery?.images || [])"
          :key="i"
          :src="getFullUrl(img)"
          fit="cover"
          class="delivery-img"
          :preview-src-list="(currentViewOrder?.delivery?.images || []).map(getFullUrl)"
          :initial-index="i"
        />
      </div>
      <el-empty v-if="!currentViewOrder?.delivery?.images?.length" description="暂无交付作品" />
    </el-dialog>

    <el-dialog v-model="showReviewDialog" title="评价订单" width="460px" @closed="resetReviewForm">
      <el-form label-width="80px">
        <el-form-item label="评分">
          <el-rate v-model="reviewRating" :max="10" show-score score-template="{value} 分" />
        </el-form-item>
        <el-form-item label="评价内容">
          <el-input v-model="reviewText" type="textarea" :rows="4" placeholder="分享您的拍摄体验..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingReview" @click="submitReview">提交评价</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showViewReviewDialog" title="客户评价" width="460px">
      <el-rate :model-value="currentReviewOrder?.rating || 0" :max="10" disabled show-score score-template="{value} 分" />
      <div v-if="currentReviewOrder?.review_text" class="view-desc">{{ currentReviewOrder.review_text }}</div>
      <el-empty v-else description="暂无评价文字" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from 'lucide-vue-next'
import { getMyCustomerOrders, getMyPhotographerOrders, confirmOrder, rejectOrder, deliverWorks, acceptOrder, reviewOrder, startOrder } from '../api/order'
import { promptRejectReason } from '@/utils/orderRejectPrompt'
import api from '../utils/api'
import { useProfileMode } from '@/composables/useProfileMode'

const route = useRoute()
const router = useRouter()
const { profileMode, initProfileMode } = useProfileMode()
const activeTab = ref('customer')
const orders = ref([])
const loading = ref(false)
const processingId = ref(null)
const currentUserId = ref(0)
const queueFilter = ref(String(route.query.queue || 'all'))
const queueOptions = [
    { value: 'all', label: '全部' },
    { value: 'my_action', label: '待我处理' },
    { value: 'waiting_other', label: '等待对方' },
    { value: 'active', label: '进行中' },
    { value: 'completed', label: '已完成' },
    { value: 'after_sales', label: '售后中' },
    { value: 'cancelled', label: '已取消' },
]

const validOrderStatuses = new Set([
    'pending',
    'awaiting_customer_payment',
    'confirmed',
    'reschedule_requested',
    'in_progress',
    'delivered',
    'received',
    'reviewed',
    'completed',
    'cancelled',
])
const todoFilters = {
    to_deliver: {
        label: '待交付订单',
        statuses: ['confirmed', 'in_progress'],
    },
    reschedule: {
        label: '待处理改期',
        predicate: order => !!order.active_reschedule_request && Number(order.active_reschedule_request.requested_by) !== currentUserId.value,
    },
}

// ---- 交付作品 ----
const showDeliveryDialog = ref(false)
const submittingDelivery = ref(false)
const deliveryFiles = ref([])
const deliveryDescription = ref('')
const currentDeliverOrder = ref(null)

// ---- 查看作品 ----
const showViewDialog = ref(false)
const currentViewOrder = ref(null)
const showReviewDialog = ref(false)
const submittingReview = ref(false)
const reviewRating = ref(0)
const reviewText = ref('')
const currentReviewOrder = ref(null)
const showViewReviewDialog = ref(false)

const activeReschedule = (order) => order?.active_reschedule_request || null

const openViewDelivery = (order) => {
    currentViewOrder.value = order
    showViewDialog.value = true
}

const getFullUrl = (url) => {
    if (!url) return ''
    if (url.startsWith('http')) return url
    return url
}

const userRole = ref('')
const isCustomer = computed(() => true)
const isPhotographer = computed(() => userRole.value === 'photographer')
const queryStatus = computed(() => {
    const status = String(route.query.status || '')
    return validOrderStatuses.has(status) ? status : ''
})
const queryTodo = computed(() => {
    const todo = String(route.query.todo || '')
    return todoFilters[todo] ? todo : ''
})
const activeFilterLabel = computed(() => {
    if (queryTodo.value) return todoFilters[queryTodo.value].label
    if (queryStatus.value) return statusLabel(queryStatus.value)
    return ''
})

const fetchCurrentUserRole = async () => {
    if (!localStorage.getItem('token')) {
        userRole.value = ''
        return
    }
    try {
        const res = await api.get('/users/me', { skipErrorHandler: true })
        userRole.value = res.data.role || ''
        currentUserId.value = Number(res.data.id || 0)
        initProfileMode({ userId: res.data.id, role: userRole.value })
    } catch {
        userRole.value = ''
    }
}

const fetchOrders = async () => {
    loading.value = true
    try {
        const fn = activeTab.value === 'customer' ? getMyCustomerOrders : getMyPhotographerOrders
        const params = queryStatus.value && !queryTodo.value ? { status: queryStatus.value } : {}
        const res = await fn(params)
        let nextOrders = res.data
        if (queryTodo.value) {
            const filter = todoFilters[queryTodo.value]
            nextOrders = filter.statuses
                ? nextOrders.filter(order => filter.statuses.includes(order.status))
                : nextOrders.filter(filter.predicate)
        }
        const currentRole = activeTab.value === 'customer' ? 'customer' : 'photographer'
        if (queueFilter.value === 'my_action') {
            nextOrders = nextOrders.filter(order => order.action_required_by === currentRole)
        } else if (queueFilter.value === 'waiting_other') {
            nextOrders = nextOrders.filter(order => (
                ['pending', 'awaiting_customer_payment', 'confirmed', 'in_progress', 'delivered'].includes(order.status)
                && order.action_required_by
                && order.action_required_by !== currentRole
            ))
        } else if (queueFilter.value === 'active') {
            nextOrders = nextOrders.filter(order => ['pending', 'awaiting_customer_payment', 'confirmed', 'in_progress', 'delivered'].includes(order.status))
        } else if (queueFilter.value === 'completed') {
            nextOrders = nextOrders.filter(order => ['completed', 'received', 'reviewed'].includes(order.status))
        } else if (queueFilter.value === 'after_sales') {
            nextOrders = nextOrders.filter(order => order.after_sales_status && order.after_sales_status !== 'none')
        } else if (queueFilter.value === 'cancelled') {
            nextOrders = nextOrders.filter(order => order.status === 'cancelled')
        }
        orders.value = nextOrders
    } finally {
        loading.value = false
    }
}

const setQueueFilter = value => {
    queueFilter.value = value
    router.replace({
        path: '/my-orders',
        query: { ...route.query, role: activeTab.value, queue: value === 'all' ? undefined : value },
    })
}

const formatDeadline = value => new Date(value).toLocaleString('zh-CN', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
})
const formatDateOnly = value => value
  ? new Date(value).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  : '-'
const formatOrderTitle = value => String(value || '摄影服务')
  .replace(/\s*\/\s*\d+\s*(?:分钟|minutes?)/gi, '')
  .replace(/\s*时长\s*\d+\s*(?:分钟|小时)/gi, '')
  .trim()
const orderCardActionLabel = row => {
  if (row.after_sales_status === 'dispute_open') return '查看争议处理'
  if (activeReschedule(row)) return '处理改期'
  if (row.status === 'awaiting_customer_payment') return '去支付'
  if (row.status === 'delivered') return activeTab.value === 'customer' ? '验收与查看' : '查看交付'
  return '查看详情'
}

const applyQueryRole = () => {
    const role = route.query.role
    if (role === 'photographer' && isPhotographer.value) {
        activeTab.value = 'photographer'
    } else if (role === 'customer') {
        activeTab.value = 'customer'
    }
}

const clearFilter = () => {
    router.push({
        path: '/my-orders',
        query: { role: activeTab.value },
    })
}

const confirmOrderAction = async (orderId) => {
    try {
        await ElMessageBox.confirm('确认接受此预约？', '确认', { type: 'warning' })
        processingId.value = orderId
        await confirmOrder(orderId)
        ElMessage.success('已确认预约')
        await fetchOrders()
    } catch (error) {
        if (error !== 'cancel') ElMessage.error('确认预约失败，请重试')
    } finally {
        processingId.value = null
    }
}

const rejectOrderAction = async (orderId) => {
    try {
        const reason = await promptRejectReason()
        processingId.value = orderId
        await rejectOrder(orderId, reason)
        ElMessage.info('已拒绝预约')
        await fetchOrders()
    } catch (error) {
        if (error !== 'cancel') ElMessage.error('拒绝预约失败，请重试')
    } finally {
        processingId.value = null
    }
}

const handleAccept = async (id) => {
    try { await ElMessageBox.confirm('确认接收作品？', '接收确认', { type: 'success' }) } catch { return }
    processingId.value = id
    try {
        await acceptOrder(id)
        ElMessage.success('作品已验收，订单已完成')
        await fetchOrders()
    } catch {
        ElMessage.error('接收作品失败，请重试')
    } finally {
        processingId.value = null
    }
}

const startOrderAction = async (id) => {
    try { await ElMessageBox.confirm('确认开始本次服务？', '开始服务', { type: 'warning' }) } catch { return }
    processingId.value = id
    try {
        await startOrder(id)
        ElMessage.success('订单已进入履约中')
        await fetchOrders()
    } catch {
        ElMessage.error('开始服务失败，请重试')
    } finally {
        processingId.value = null
    }
}

const openReviewDialog = (order) => {
    currentReviewOrder.value = order
    reviewRating.value = 0
    reviewText.value = ''
    showReviewDialog.value = true
}

const resetReviewForm = () => {
    reviewRating.value = 0
    reviewText.value = ''
}

const submitReview = async () => {
    if (!reviewRating.value) {
        ElMessage.warning('请给出评分')
        return
    }
    submittingReview.value = true
    try {
        await reviewOrder(currentReviewOrder.value.id, {
            rating: reviewRating.value,
            review_text: reviewText.value || undefined,
        })
        ElMessage.success('评价已提交')
        showReviewDialog.value = false
        await fetchOrders()
    } catch {
        ElMessage.error('评价提交失败，请重试')
    } finally {
        submittingReview.value = false
    }
}

const openViewReview = (order) => {
    currentReviewOrder.value = order
    showViewReviewDialog.value = true
}

// ---- 交付作品 ----
const openDeliveryDialog = (order) => {
    currentDeliverOrder.value = order
    showDeliveryDialog.value = true
}

const resetDeliveryForm = () => {
    deliveryFiles.value = []
    deliveryDescription.value = ''
    currentDeliverOrder.value = null
}

const submitDelivery = async () => {
    if (!deliveryFiles.value.length) {
        ElMessage.warning('请至少上传一张作品')
        return
    }
    submittingDelivery.value = true
    try {
        const formData = new FormData()
        deliveryFiles.value.forEach(file => {
            formData.append('files', file.raw)
        })
        formData.append('description', deliveryDescription.value)
        formData.append('idempotency_key', `delivery-${currentDeliverOrder.value.id}-${Date.now()}-${Math.random().toString(16).slice(2)}`)
        await deliverWorks(currentDeliverOrder.value.id, formData)
        ElMessage.success(currentDeliverOrder.value.after_sales_status === 'revision_requested' ? '新版本已重新交付' : '作品已交付')
        showDeliveryDialog.value = false
        fetchOrders()
    } catch {
    } finally {
        submittingDelivery.value = false
    }
}

const statusType = (status) => {
    const map = { pending: 'warning', awaiting_customer_payment: 'warning', confirmed: 'success', reschedule_requested: 'warning', in_progress: 'success', delivered: '', received: '', reviewed: '', cancelled: 'info', completed: '' }
    return map[status] || ''
}

const statusLabel = (status) => {
    const map = { pending: '待确认', awaiting_customer_payment: '待支付', confirmed: '已确认', reschedule_requested: '改期待确认', in_progress: '拍摄中/待交付', delivered: '待接收', received: '待评价', reviewed: '已完成', completed: '已完成', cancelled: '已取消' }
    return map[status] || status
}

const orderNextText = (order) => {
    const status = order?.status
    if (activeTab.value === 'photographer') {
        return {
            pending: '请确认或拒绝预约',
            awaiting_customer_payment: '等待客户支付，支付成功后订单正式确认',
            confirmed: activeReschedule(order) ? '有待处理的改期申请，请进入详情' : '请开始服务',
            in_progress: '拍摄完成后交付作品',
            delivered: order.after_sales_status === 'revision_requested' ? '请根据修改说明重新交付' : '等待客户验收或申请修改',
            received: '订单已完成，评价可选',
            reviewed: '订单已完成',
            completed: '订单已完成',
            cancelled: order.cancellation_reason || order.rejection_reason ? '已填写取消原因' : '订单已取消',
        }[status] || '查看详情'
    }
    return {
        pending: '等待摄影师确认，可进入详情申请改期或取消',
        awaiting_customer_payment: '请在支付期限内完成付款，超时将释放档期',
        confirmed: activeReschedule(order) ? '改期申请处理中，原档期继续有效' : '可进入详情申请改期或取消',
        in_progress: '等待摄影师交付',
        delivered: order.after_sales_status === 'revision_requested' ? '等待摄影师重新交付' : '请验收或申请修改',
        received: '订单已完成，可选评价',
        reviewed: '订单已完成',
        completed: order.rating ? '订单已完成并评价' : '订单已完成，可选评价',
        cancelled: order.cancellation_reason || order.rejection_reason ? '查看取消原因' : '订单已取消',
    }[status] || '查看详情'
}

const goOrderDetail = (order) => {
    if (order?.id) router.push(`/orders/${order.id}`)
}

onMounted(async () => {
    await fetchCurrentUserRole()
    activeTab.value = profileMode.value === 'customer' ? 'customer' : 'photographer'
    applyQueryRole()
    fetchOrders()
})

watch(() => [route.query.role, route.query.status, route.query.todo, route.query.queue], () => {
    queueFilter.value = String(route.query.queue || 'all')
    applyQueryRole()
    fetchOrders()
})
</script>

<style scoped>
.orders-container {
    max-width: 1200px;
    margin: 20px auto;
    padding: 0 20px;
}

.order-card-list {
  display: grid;
  gap: var(--space-3);
  min-height: 160px;
}

.order-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-6);
  padding: var(--space-5) var(--space-6);
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.order-card-main {
  min-width: 0;
}

.order-card-heading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.order-card-number {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.order-card h3 {
  margin: var(--space-2) 0;
  color: var(--color-ink);
  font-size: var(--text-lg);
  line-height: var(--leading-normal);
}

.order-card-note {
  display: -webkit-box;
  margin: 0 0 var(--space-4);
  overflow: hidden;
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  line-height: var(--leading-normal);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.order-card-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 1fr));
  gap: var(--space-4);
}

.order-card-facts div {
  display: grid;
  gap: var(--space-1);
}

.order-card-facts span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.order-card-facts strong {
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
}

.order-card-actions {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 132px;
}

.order-card-actions .el-button {
  min-width: 116px;
  min-height: var(--tap-target-min);
  margin: 0;
}

h2 {
  color: var(--color-ink);
  font-size: var(--text-3xl);
  margin: 0 0 8px;
}

.filter-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: -4px 0 14px;
}

.pending-reschedule {
    margin-top: 4px;
    color: var(--color-warning);
    font-size: var(--text-xs);
    line-height: 1.4;
}

.next-step-text {
    color: var(--color-ink-secondary);
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
}

.view-desc {
    margin-bottom: 16px;
    padding: 10px 14px;
    background: var(--color-paper);
    border-radius: var(--radius-md);
    font-size: 14px;
    color: var(--color-ink-secondary);
}

.view-images {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

.delivery-img {
    width: 180px;
    height: 180px;
    border-radius: var(--radius-md);
    cursor: pointer;
}

/* el-tabs: clean border-bottom style */
:deep(.el-tabs__header) {
  margin: 0 0 16px;
}
:deep(.el-tabs__nav-wrap::after) {
  background-color: var(--color-divider);
  height: 1px;
}
:deep(.el-tabs__item) {
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  height: var(--tap-target-min);
  line-height: var(--tap-target-min);
}
:deep(.el-tabs__item:hover) {
  color: var(--color-brand);
}
:deep(.el-tabs__item.is-active) {
  color: var(--color-brand);
  font-weight: 600;
}
:deep(.el-tabs__active-bar) {
  background-color: var(--color-brand);
}

/* el-table */
:deep(.el-table) {
  --el-table-border-color: var(--color-border-light);
  --el-table-header-bg-color: var(--color-paper);
  border: var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}
:deep(.el-table th.el-table__cell) {
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  font-weight: 600;
}
:deep(.el-table td.el-table__cell) {
  color: var(--color-ink);
}
:deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--color-paper);
}

/* el-tag status overrides */
:deep(.el-tag--success) {
  background: var(--color-brand);
  border-color: var(--color-brand);
  color: #fff;
}
:deep(.el-tag--warning) {
  background: #fdf6ec;
  border-color: #f1d9a7;
  color: var(--color-warning);
}
:deep(.el-tag--info) {
  background: var(--color-paper);
  border-color: var(--color-border);
  color: var(--color-ink-secondary);
}
:deep(.el-tag--danger) {
  background: #fef0f0;
  border-color: #f3d4d4;
  color: var(--color-danger);
}

/* el-table stripe */
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: var(--color-paper);
}
.queue-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.queue-tabs button {
  min-height: 40px;
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-paper-light);
  color: var(--color-ink-secondary);
  cursor: pointer;
  white-space: nowrap;
}

.queue-tabs button.active {
  border-color: var(--color-brand);
  background: var(--color-brand-light);
  color: var(--color-brand);
  font-weight: 600;
}

.action-deadline {
  display: block;
  margin-top: 5px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.action-deadline.overdue {
  color: var(--color-danger);
  font-weight: 600;
}

@media (max-width: 760px) {
  .order-card {
    grid-template-columns: 1fr;
    padding: var(--space-4);
  }

  .order-card-facts {
    grid-template-columns: 1fr;
  }

  .order-card-actions {
    align-items: stretch;
  }

  .order-card-actions .el-button {
    width: 100%;
  }
}

</style>
