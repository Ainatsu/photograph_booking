<template>
  <div class="finance-page">
    <div class="page-head">
      <div>
        <h3>财务记录</h3>
        <p>平台人民币支付、退款和结算流水。</p>
      </div>
      <el-button :loading="loading" @click="fetchRecords">刷新</el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-change="fetchRecords">
      <el-tab-pane label="支付记录" name="payments" />
      <el-tab-pane label="退款记录" name="refunds" />
      <el-tab-pane label="结算记录" name="settlements" />
    </el-tabs>

    <el-table v-if="activeTab === 'payments'" :data="records" v-loading="loading" stripe>
      <el-table-column prop="payment_no" label="支付单号" min-width="210" />
      <el-table-column prop="order_id" label="订单" width="80" />
      <el-table-column label="用途" width="90"><template #default="{ row }">{{ purposeLabel(row.purpose) }}</template></el-table-column>
      <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatCny(row.amount) }}</template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="{ row }">{{ paymentStatusLabel(row.status) }}</template></el-table-column>
      <el-table-column prop="provider_transaction_id" label="第三方流水" min-width="190" />
      <el-table-column label="创建时间" width="180"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
    </el-table>

    <el-table v-else-if="activeTab === 'refunds'" :data="records" v-loading="loading" stripe>
      <el-table-column prop="refund_no" label="退款单号" min-width="210" />
      <el-table-column prop="order_id" label="订单" width="80" />
      <el-table-column label="退款金额" width="120"><template #default="{ row }">{{ formatCny(row.amount) }}</template></el-table-column>
      <el-table-column prop="responsibility_party" label="责任方" width="100" />
      <el-table-column prop="reason" label="原因" min-width="180" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="完成时间" width="180"><template #default="{ row }">{{ formatTime(row.completed_at) }}</template></el-table-column>
    </el-table>

    <el-table v-else :data="records" v-loading="loading" stripe>
      <el-table-column prop="settlement_no" label="结算单号" min-width="210" />
      <el-table-column prop="order_id" label="订单" width="80" />
      <el-table-column prop="photographer_id" label="摄影师" width="90" />
      <el-table-column label="担保总额" width="120"><template #default="{ row }">{{ formatCny(row.gross_amount) }}</template></el-table-column>
      <el-table-column label="平台服务费" width="120"><template #default="{ row }">{{ formatCny(row.platform_fee_amount) }}</template></el-table-column>
      <el-table-column label="摄影师结算" width="120"><template #default="{ row }">{{ formatCny(row.net_amount) }}</template></el-table-column>
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="结算时间" width="180"><template #default="{ row }">{{ formatTime(row.settled_at) }}</template></el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../utils/api'

const activeTab = ref('payments')
const records = ref([])
const loading = ref(false)

const fetchRecords = async () => {
  loading.value = true
  try {
    const { data } = await api.get(`/finance/${activeTab.value}`)
    records.value = data
  } finally {
    loading.value = false
  }
}

const formatCny = value => `¥${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN') : '-'
const purposeLabel = purpose => ({ full: '全款', deposit: '定金', balance: '尾款' }[purpose] || purpose)
const paymentStatusLabel = status => ({ pending: '待支付', succeeded: '支付成功', failed: '支付失败', expired: '已超时', partially_refunded: '部分退款', refunded: '已退款' }[status] || status)

onMounted(fetchRecords)
</script>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

h3 {
  margin: 0;
  color: #1a1a1a;
  font-size: 22px;
}

p {
  margin: 6px 0 0;
  color: #6b6560;
}

:deep(.el-table) {
  --el-table-border-color: #d9d3cb;
  --el-table-header-bg-color: #faf7f2;
  border-radius: 6px;
}
</style>
