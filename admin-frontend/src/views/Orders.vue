<template>
  <div>
    <h3>订单管理</h3>
    <el-table :data="orders" v-loading="loading" stripe>
      <el-table-column prop="id" label="订单号" width="70" />
      <el-table-column prop="package_snapshot" label="方案" min-width="160" />
      <el-table-column label="成交金额" width="120">
        <template #default="{ row }">{{ formatCny(row.final_price) }}</template>
      </el-table-column>
      <el-table-column label="来源" width="90">
        <template #default="{ row }">{{ sourceLabel(row.source_type) }}</template>
      </el-table-column>
      <el-table-column label="支付状态" width="120">
        <template #default="{ row }">{{ paymentStatusLabel(row.payment_status) }}</template>
      </el-table-column>
      <el-table-column label="预约时间" width="170">
        <template #default="{ row }">{{ new Date(row.appointment_time).toLocaleString() }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="70">
        <template #default="{ row }">{{ row.rating ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button
            v-if="!['cancelled', 'reviewed', 'received', 'completed'].includes(row.status)"
            type="danger" size="small"
            @click="cancelOrder(row.id)"
          >
            取消
          </el-button>
          <span v-else>--</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../utils/api'

const orders = ref([])
const loading = ref(false)

const statusType = (s) => ({ pending: 'warning', awaiting_customer_payment: 'warning', confirmed: 'success', in_progress: 'success', delivered: 'warning', received: 'success', reviewed: 'success', completed: 'success', cancelled: 'info' }[s] || '')
const statusLabel = (s) => ({ pending: '待确认', awaiting_customer_payment: '待支付', confirmed: '已确认', in_progress: '履约中', delivered: '待验收', received: '已完成', reviewed: '已完成', completed: '已完成', cancelled: '已取消' }[s] || s)
const sourceLabel = (source) => ({ package: '固定套餐', project: '定制企划', legacy: '历史订单' }[source] || '订单')
const formatCny = (value) => {
  if (value === null || value === undefined || value === '') return '-'
  const amount = Number(value)
  return Number.isNaN(amount) ? '-' : `¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
const paymentStatusLabel = (status) => ({
  unpaid: '待支付',
  deposit_paid: '已付定金',
  paid_in_escrow: '担保中',
  partially_refunded: '部分退款',
  refunded: '已退款',
  settled: '已结算',
  payment_failed: '支付失败',
}[status] || status || '-')

const fetch = async () => {
  loading.value = true
  try {
    const res = await api.get('/orders')
    orders.value = res.data
  } finally {
    loading.value = false
  }
}

const cancelOrder = async (id) => {
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('请填写管理员取消原因。原因会通知订单双方并写入事件时间线。', '取消订单', {
      type: 'warning',
      inputType: 'textarea',
      inputValidator: value => value?.trim() ? true : '必须填写取消原因',
      confirmButtonText: '确认取消',
      cancelButtonText: '返回',
    })
    reason = value.trim()
  } catch { return }
  try {
    await api.put(`/orders/${id}/cancel`, { reason })
    ElMessage.success('订单已取消并记录审计事件')
    fetch()
  } catch {
    ElMessage.error('取消订单失败，请重试')
  }
}

onMounted(fetch)
</script>

<style scoped>
h3 {
  color: #1A1A1A;
  font-weight: 700;
  margin: 0 0 16px 0;
}

:deep(.el-table) {
  --el-table-border-color: #D9D3CB;
  --el-table-header-bg-color: #FAF7F2;
  --el-table-tr-bg-color: #FFFDF9;
  --el-table-row-hover-bg-color: #EBF2EA;
  font-size: 0.875rem;
}

:deep(.el-table th.el-table__cell) {
  background: #FAF7F2;
  color: #6B6560;
  font-weight: 600;
  border-bottom: 1px solid #D9D3CB;
}

:deep(.el-table .el-table__cell) {
  border-bottom: 1px solid #E8E2DA;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: #FAF7F2;
}

:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: #EBF2EA;
}

:deep(.el-tag--success) {
  background: #EBF2EA;
  border-color: #2D5A27;
  color: #2D5A27;
}

:deep(.el-tag--warning) {
  background: #FDF8ED;
  border-color: #8B6914;
  color: #8B6914;
}

:deep(.el-tag--info) {
  background: #FAF7F2;
  border-color: #D9D3CB;
  color: #6B6560;
}

:deep(.el-button--danger) {
  background: #C53030;
  border-color: #C53030;
}

:deep(.el-button--danger:hover) {
  background: #A02020;
  border-color: #A02020;
}
</style>
