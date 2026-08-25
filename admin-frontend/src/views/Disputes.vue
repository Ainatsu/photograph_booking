<template>
  <div class="disputes-page">
    <div class="page-head">
      <div>
        <h3>争议与平台仲裁</h3>
        <p>审核双方证据，冻结期间不会自动验收或结算。所有管理员操作均写入审计日志。</p>
      </div>
      <el-button :loading="loading" @click="fetchDisputes">刷新</el-button>
    </div>

    <div class="filters" aria-label="争议状态筛选">
      <el-select v-model="statusFilter" placeholder="全部状态" clearable @change="fetchDisputes">
        <el-option label="待分配" value="open" />
        <el-option label="已分配" value="assigned" />
        <el-option label="审核中" value="investigating" />
        <el-option label="已仲裁" value="resolved" />
      </el-select>
    </div>

    <el-table :data="disputes" v-loading="loading" stripe>
      <el-table-column prop="dispute_no" label="争议编号" min-width="210" />
      <el-table-column prop="order_id" label="订单" width="80" />
      <el-table-column label="发起方" width="110">
        <template #default="{ row }">{{ roleLabel(row.opened_by_role) }} · {{ row.opener_name || row.opened_by }}</template>
      </el-table-column>
      <el-table-column label="争议类型" min-width="150">
        <template #default="{ row }">{{ reasonLabel(row.reason_code) }}</template>
      </el-table-column>
      <el-table-column label="诉求" width="120">
        <template #default="{ row }">{{ resolutionLabel(row.requested_resolution) }}</template>
      </el-table-column>
      <el-table-column label="担保余额" width="120">
        <template #default="{ row }">{{ formatCny(row.available_escrow_amount) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" effect="plain">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }"><el-button link type="primary" @click="openDetail(row.id)">查看处理</el-button></template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="showDetail" title="争议审核" size="min(760px, 92vw)" @closed="detail = null">
      <div v-if="detail" v-loading="detailLoading" class="detail-content">
        <section class="detail-card overview-card">
          <div class="card-head">
            <div><strong>{{ detail.dispute.dispute_no }}</strong><span>订单 #{{ detail.order.id }}</span></div>
            <el-tag :type="statusType(detail.dispute.status)" effect="plain">{{ statusLabel(detail.dispute.status) }}</el-tag>
          </div>
          <p>{{ detail.dispute.description }}</p>
          <dl class="summary-grid">
            <div><dt>订单状态</dt><dd>{{ orderStatusLabel(detail.order.status) }}</dd></div>
            <div><dt>支付状态</dt><dd>{{ paymentStatusLabel(detail.order.payment_status) }}</dd></div>
            <div><dt>可退担保余额</dt><dd>{{ formatCny(detail.dispute.available_escrow_amount) }}</dd></div>
            <div><dt>负责管理员</dt><dd>{{ detail.dispute.assigned_admin_name || '未分配' }}</dd></div>
          </dl>
        </section>

        <section class="detail-card">
          <h4>双方证据</h4>
          <el-empty v-if="!detail.dispute.evidence.length" description="尚未提交证据" />
          <article v-for="item in detail.dispute.evidence" :key="item.id" class="evidence-item">
            <div><strong>{{ roleLabel(item.submitter_role) }} · {{ item.submitter_name || item.submitted_by }}</strong><span>{{ formatTime(item.created_at) }}</span></div>
            <p v-if="item.description">{{ item.description }}</p>
            <a v-if="item.file_url" :href="item.file_url" target="_blank" rel="noopener noreferrer">查看附件：{{ item.file_name || '证据文件' }}</a>
            <span v-if="item.reference_type">订单记录：{{ item.reference_type }} #{{ item.reference_id }}</span>
          </article>
        </section>

        <section class="detail-card context-card">
          <h4>平台可核查订单记录</h4>
          <div class="context-grid">
            <div><strong>{{ detail.context.order_events?.length || 0 }}</strong><span>订单事件</span></div>
            <div><strong>{{ detail.context.deliveries?.length || 0 }}</strong><span>交付版本</span></div>
            <div><strong>{{ detail.context.payments?.length || 0 }}</strong><span>支付记录</span></div>
            <div><strong>{{ detail.context.refunds?.length || 0 }}</strong><span>历史退款</span></div>
          </div>
        </section>

        <section class="detail-card">
          <h4>管理员审计日志</h4>
          <el-timeline v-if="detail.audit_logs.length">
            <el-timeline-item v-for="item in detail.audit_logs" :key="item.id" :timestamp="formatTime(item.created_at)">
              <strong>{{ auditActionLabel(item.action) }}</strong>
              <p>{{ item.admin_name || `管理员 #${item.admin_id}` }}{{ item.note ? `：${item.note}` : '' }}</p>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无管理员操作" />
        </section>

        <div v-if="isActive(detail.dispute.status)" class="action-bar">
          <el-button :loading="actionLoading" @click="assignToMe">分配给我</el-button>
          <el-button type="primary" plain :loading="actionLoading" @click="startInvestigating">开始审核</el-button>
          <el-button type="primary" :disabled="actionLoading" @click="showResolveDialog = true">作出仲裁</el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="showResolveDialog" title="作出争议仲裁" width="560px" @closed="resetResolutionForm">
      <el-alert title="仲裁会同时更新订单售后状态、退款或结算记录、订单事件和管理员审计日志。" type="warning" :closable="false" show-icon />
      <el-form label-position="top" class="resolution-form">
        <el-form-item label="仲裁结果" required>
          <el-select v-model="resolutionForm.resolution" style="width: 100%" placeholder="选择仲裁结果">
            <el-option label="继续履约" value="continue_fulfillment" />
            <el-option label="部分退款后继续履约" value="partial_refund" />
            <el-option label="全额退款并终止订单" value="full_refund" />
            <el-option label="确认履约并直接结算" value="release_settlement" />
            <el-option label="其他处理并恢复履约" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="resolutionForm.resolution === 'partial_refund'" label="退款金额（人民币）" required>
          <el-input-number v-model="resolutionForm.refund_amount" :min="0.01" :max="maxRefundAmount" :precision="2" :step="10" style="width: 100%" />
          <div class="field-help">当前可退上限：{{ formatCny(maxRefundAmount) }}</div>
        </el-form-item>
        <el-form-item label="仲裁依据与处理说明" required>
          <el-input v-model="resolutionForm.resolution_note" type="textarea" :rows="6" maxlength="3000" show-word-limit placeholder="说明采信的证据、责任判断、退款或继续履约安排。该说明会进入订单事件记录。" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showResolveDialog = false">返回</el-button>
        <el-button type="primary" :loading="resolving" @click="submitResolution">确认仲裁</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../utils/api'

const disputes = ref([])
const loading = ref(false)
const statusFilter = ref('')
const showDetail = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const actionLoading = ref(false)
const showResolveDialog = ref(false)
const resolving = ref(false)
const resolutionForm = reactive({ resolution: '', refund_amount: 0, resolution_note: '' })

const maxRefundAmount = computed(() => Number(detail.value?.dispute?.available_escrow_amount || 0))

const fetchDisputes = async () => {
  loading.value = true
  try {
    const { data } = await api.get('/disputes', { params: statusFilter.value ? { status_value: statusFilter.value } : {} })
    disputes.value = data
  } finally { loading.value = false }
}

const openDetail = async (id) => {
  showDetail.value = true
  detailLoading.value = true
  try {
    const { data } = await api.get(`/disputes/${id}`)
    detail.value = data
  } finally { detailLoading.value = false }
}

const refreshDetail = async () => {
  if (!detail.value) return
  await openDetail(detail.value.dispute.id)
  await fetchDisputes()
}

const assignToMe = async () => {
  actionLoading.value = true
  try {
    await api.put(`/disputes/${detail.value.dispute.id}/assign`, {})
    ElMessage.success('争议已分配给当前管理员')
    await refreshDetail()
  } finally { actionLoading.value = false }
}

const startInvestigating = async () => {
  actionLoading.value = true
  try {
    await api.put(`/disputes/${detail.value.dispute.id}/investigate`, { note: '管理员开始核查双方证据与订单记录。' })
    ElMessage.success('已进入证据审核阶段')
    await refreshDetail()
  } finally { actionLoading.value = false }
}

const resetResolutionForm = () => {
  resolutionForm.resolution = ''
  resolutionForm.refund_amount = 0
  resolutionForm.resolution_note = ''
}

const submitResolution = async () => {
  if (!resolutionForm.resolution || !resolutionForm.resolution_note.trim()) {
    ElMessage.warning('请选择仲裁结果并填写处理说明')
    return
  }
  if (resolutionForm.resolution === 'partial_refund' && (!resolutionForm.refund_amount || resolutionForm.refund_amount >= maxRefundAmount.value)) {
    ElMessage.warning('部分退款必须大于 0 且小于当前可退担保余额')
    return
  }
  const amountText = resolutionForm.resolution === 'partial_refund'
    ? `，将退款 ${formatCny(resolutionForm.refund_amount)}`
    : resolutionForm.resolution === 'full_refund'
      ? `，将退款全部担保余额 ${formatCny(maxRefundAmount.value)}`
      : ''
  try {
    await ElMessageBox.confirm(`确认提交“${resolutionLabel(resolutionForm.resolution)}”仲裁${amountText}？提交后不可重复修改。`, '最终仲裁确认', {
      type: 'warning', confirmButtonText: '确认执行', cancelButtonText: '返回检查',
    })
  } catch { return }
  resolving.value = true
  try {
    await api.put(`/disputes/${detail.value.dispute.id}/resolve`, {
      resolution: resolutionForm.resolution,
      resolution_note: resolutionForm.resolution_note.trim(),
      refund_amount: resolutionForm.resolution === 'partial_refund' ? resolutionForm.refund_amount : null,
    })
    ElMessage.success('仲裁已执行，资金与订单状态已同步更新')
    showResolveDialog.value = false
    await refreshDetail()
  } finally { resolving.value = false }
}

const isActive = status => ['open', 'assigned', 'investigating'].includes(status)
const roleLabel = value => ({ customer: '客户', photographer: '摄影师', admin: '管理员' }[value] || value)
const reasonLabel = value => ({ quality_issue: '交付质量或内容不符', delivery_delay: '未按约定时间履约', service_failure: '服务无法继续', cooperation_issue: '对方配合问题', customer_cooperation: '客户配合问题', acceptance_delay: '验收延迟', other: '其他争议' }[value] || value)
const resolutionLabel = value => ({ continue_fulfillment: '继续履约', partial_refund: '部分退款', full_refund: '全额退款', release_settlement: '直接结算', other: '其他处理' }[value] || value)
const statusLabel = value => ({ open: '待分配', assigned: '已分配', investigating: '审核中', resolved: '已仲裁', cancelled: '已关闭' }[value] || value)
const statusType = value => ({ open: 'warning', assigned: 'warning', investigating: 'primary', resolved: 'success', cancelled: 'info' }[value] || 'info')
const orderStatusLabel = value => ({ confirmed: '已确认', in_progress: '履约中', delivered: '待验收', completed: '已完成', cancelled: '已取消' }[value] || value)
const paymentStatusLabel = value => ({ unpaid: '待支付', paid_in_escrow: '担保中', partially_refunded: '已部分退款', refunded: '已全额退款', settled: '已结算' }[value] || value)
const auditActionLabel = value => ({ dispute_assigned: '分配争议', dispute_investigating: '开始证据审核', dispute_resolved: '作出最终仲裁' }[value] || value)
const formatCny = value => `¥${Number(value || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN') : '-'

onMounted(fetchDisputes)
</script>

<style scoped>
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
h3 { margin: 0; color: #1a1a1a; font-size: 22px; }
h4 { margin: 0 0 14px; color: #1a1a1a; }
p { color: #6b6560; line-height: 1.6; }
.page-head p { margin: 6px 0 0; }
.filters { display: flex; margin-bottom: 14px; }
.filters .el-select { width: 180px; }
:deep(.el-table) { --el-table-border-color: #d9d3cb; --el-table-header-bg-color: #faf7f2; border-radius: 6px; }
.detail-content { display: grid; gap: 16px; padding-bottom: 88px; }
.detail-card { padding: 18px; border: 1px solid #d9d3cb; border-radius: 8px; background: #fffdf9; }
.card-head, .evidence-item > div { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.card-head > div { display: grid; gap: 5px; }
.card-head span, .evidence-item span, .field-help { color: #6b6560; font-size: 13px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 14px 0 0; }
.summary-grid > div { padding: 12px; background: #faf7f2; border-radius: 6px; }
.summary-grid dt { color: #6b6560; font-size: 13px; }
.summary-grid dd { margin: 6px 0 0; color: #1a1a1a; font-weight: 700; font-variant-numeric: tabular-nums; }
.evidence-item { padding: 12px 0; border-top: 1px solid #e8e2da; }
.evidence-item p { margin: 8px 0; white-space: pre-wrap; }
.evidence-item a { color: #2d5a27; text-decoration: underline; text-underline-offset: 3px; }
.context-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.context-grid div { display: grid; gap: 5px; padding: 14px; background: #faf7f2; border-radius: 6px; text-align: center; }
.context-grid strong { font-size: 22px; color: #2d5a27; }
.context-grid span { color: #6b6560; font-size: 13px; }
.action-bar { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: 10px; padding: 14px 0; background: rgba(255, 253, 249, 0.96); border-top: 1px solid #d9d3cb; }
.resolution-form { margin-top: 16px; }
.field-help { margin-top: 6px; }
@media (max-width: 720px) { .summary-grid, .context-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .page-head { align-items: stretch; flex-direction: column; } }
</style>
