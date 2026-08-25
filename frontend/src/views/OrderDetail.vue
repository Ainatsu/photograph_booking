<template>
  <div class="order-detail-page">
    <div class="page-head">
      <el-button text @click="goBack">&larr; 返回</el-button>
      <h2>订单详情</h2>
      <div class="collapse-all-actions">
        <el-button text size="small" @click="setAllCardsCollapsed(true)">全部收起</el-button>
        <el-button text size="small" @click="setAllCardsCollapsed(false)">全部展开</el-button>
      </div>
    </div>

    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="8" animated />
    </div>

    <template v-else-if="order">
      <div class="order-content">
      <section class="summary-panel">
        <div class="summary-main">
          <div class="order-number">订单 #{{ order.id }}</div>
          <h1>{{ order.package_snapshot }}</h1>
          <div class="summary-meta">
            <span>预约时间：{{ formatTime(order.appointment_time) }}</span>
            <span v-if="activeReschedule" class="pending-time">
              改期候选：{{ formatTime(activeReschedule.requested_appointment_time) }}
            </span>
            <span>服务时长：{{ order.duration_minutes }} 分钟</span>
          </div>
          <div v-if="orderNoteSections.length" class="order-note-sections">
            <div v-for="section in orderNoteSections" :key="section.label" class="note-section">
              <div class="note-section-label">{{ section.label }}</div>
              <p class="note-section-content">{{ section.content }}</p>
            </div>
          </div>
          <p v-else-if="order.notes" class="order-notes">{{ order.notes }}</p>
        </div>
        <div class="summary-side">
          <div class="counterpart-identity">
            <el-avatar :size="42" :src="counterpartAvatarUrl" class="customer-avatar">
              {{ counterpartInitial }}
            </el-avatar>
            <div class="customer-info">
              <span>{{ counterpartRoleLabel }}</span>
              <strong>{{ counterpartName }}</strong>
            </div>
          </div>
          <div class="summary-actions">
            <el-tag :type="statusType(order.status)" size="large">{{ statusLabel(order.status) }}</el-tag>
            <el-button type="primary" plain :icon="ChatDotRound" :disabled="!chatTargetId" @click="goOrderChat">
              发消息
            </el-button>
          </div>
        </div>
      </section>

      <section v-if="hasStructuredContract" :class="['contract-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('contract') }]">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('contract')">订单合同快照</strong><span v-else></span><el-button text @click="toggleCard('contract')">{{ isCardCollapsed('contract') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <h3>订单合同快照</h3>
          <span>金额固定为人民币，套餐后续修改不影响本订单</span>
        </div>
        <div class="contract-grid">
          <div class="contract-item price-item">
            <span>成交金额</span>
            <strong>{{ formatCny(order.final_price) }}</strong>
          </div>
          <div class="contract-item">
            <span>订单来源</span>
            <strong>{{ sourceTypeLabel }}</strong>
          </div>
          <div v-if="order.service_location" class="contract-item">
            <span>服务地点</span>
            <strong>{{ order.service_location }}</strong>
          </div>
          <div v-if="order.delivery_due_at" class="contract-item">
            <span>约定交付</span>
            <strong>{{ formatTime(order.delivery_due_at) }}</strong>
          </div>
          <div v-if="order.original_image_count !== null && order.original_image_count !== undefined" class="contract-item">
            <span>原片数量</span>
            <strong>{{ order.original_image_count }} 张</strong>
          </div>
          <div v-if="order.retouched_image_count !== null && order.retouched_image_count !== undefined" class="contract-item">
            <span>精修数量</span>
            <strong>{{ order.retouched_image_count }} 张</strong>
          </div>
          <div v-if="order.delivery_formats?.length" class="contract-item">
            <span>交付格式</span>
            <strong>{{ order.delivery_formats.join('、') }}</strong>
          </div>
          <div v-if="order.included_revision_count !== null && order.included_revision_count !== undefined" class="contract-item">
            <span>免费修改</span>
            <strong>{{ order.included_revision_count }} 次</strong>
          </div>
          <div class="contract-item">
            <span>商业授权</span>
            <strong>{{ order.commercial_license ? '包含' : '不包含' }}</strong>
          </div>
          <div class="contract-item">
            <span>付款方式</span>
            <strong>{{ paymentModeLabel }}</strong>
          </div>
        </div>
        <div v-if="order.copyright_terms" class="contract-clause">
          <span>版权条款</span>
          <p>{{ order.copyright_terms }}</p>
        </div>
        <div v-if="cancellationPolicyText" class="contract-clause">
          <span>取消政策</span>
          <p>{{ cancellationPolicyText }}</p>
        </div>
        <div v-if="reschedulePolicyText" class="contract-clause">
          <span>改期政策</span>
          <p>{{ reschedulePolicyText }}</p>
        </div>
      </section>

      <section v-if="order.final_price !== null && order.final_price !== undefined" :class="['payment-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('payment') }]">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('payment')">支付与平台担保</strong><span v-else></span><el-button text @click="toggleCard('payment')">{{ isCardCollapsed('payment') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <h3>支付与平台担保</h3>
          <span>{{ paymentStatusLabel }}</span>
        </div>
        <div class="payment-summary-grid">
          <div>
            <span>订单金额</span>
            <strong>{{ formatCny(order.final_price) }}</strong>
          </div>
          <div>
            <span>担保中</span>
            <strong>{{ formatCny(order.escrow_amount) }}</strong>
          </div>
          <div>
            <span>已退款</span>
            <strong>{{ formatCny(order.refunded_amount) }}</strong>
          </div>
          <div>
            <span>已结算</span>
            <strong>{{ formatCny(order.settled_amount) }}</strong>
          </div>
        </div>
        <p v-if="order.status === 'awaiting_customer_payment' && order.payment_due_at" class="payment-deadline">
          请在 {{ formatTime(order.payment_due_at) }} 前完成支付，超时后订单将自动关闭并释放档期。
        </p>
        <div v-if="canPayOrder" class="payment-actions">
          <el-button type="primary" size="large" :loading="paying" @click="payOrderAction">
            {{ paymentButtonText }} {{ paymentAmountHint }}
          </el-button>
          <span>支付成功后资金先由平台担保，客户验收后再结算给摄影师。</span>
        </div>
        <div v-if="financialSummary?.payments?.length" class="financial-records">
          <div v-for="payment in financialSummary.payments" :key="payment.id" class="financial-record">
            <span>{{ paymentPurposeLabel(payment.purpose) }} · {{ paymentStatusText(payment.status) }}</span>
            <strong>{{ formatCny(payment.amount) }}</strong>
          </div>
          <div v-for="refund in financialSummary.refunds || []" :key="`refund-${refund.id}`" class="financial-record refund-record">
            <span>退款 · {{ refund.reason || refund.reason_code }}</span>
            <strong>-{{ formatCny(refund.amount) }}</strong>
          </div>
          <div v-if="financialSummary.settlement" class="financial-record settlement-record">
            <span>摄影师结算（已扣平台服务费）</span>
            <strong>{{ formatCny(financialSummary.settlement.net_amount) }}</strong>
          </div>
        </div>
      </section>

      <section v-if="latestDispute" :class="['dispute-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('dispute') }]" aria-labelledby="dispute-panel-title">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('dispute')">平台争议处理</strong><span v-else></span><el-button text @click="toggleCard('dispute')">{{ isCardCollapsed('dispute') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <div>
            <h3 id="dispute-panel-title">{{ activeDispute ? '平台争议处理中' : '平台争议处理结果' }}</h3>
            <span>{{ activeDispute ? '争议期间已暂停自动验收和资金结算' : '仲裁结果、退款和订单状态均已记录' }}</span>
          </div>
          <el-tag :type="disputeStatusType(latestDispute.status)" effect="plain">
            {{ disputeStatusLabel(latestDispute.status) }}
          </el-tag>
        </div>
        <div class="dispute-summary-grid">
          <div><span>争议编号</span><strong>{{ latestDispute.dispute_no }}</strong></div>
          <div><span>发起方</span><strong>{{ actorRoleLabel(latestDispute.opened_by_role) }}</strong></div>
          <div><span>处理诉求</span><strong>{{ resolutionLabel(latestDispute.requested_resolution) }}</strong></div>
          <div><span>负责管理员</span><strong>{{ latestDispute.assigned_admin_name || '等待平台分配' }}</strong></div>
        </div>
        <p class="dispute-description">{{ latestDispute.description }}</p>
        <div v-if="latestDispute.status === 'resolved'" class="resolution-result">
          <strong>平台仲裁：{{ resolutionLabel(latestDispute.resolution) }}</strong>
          <span v-if="Number(latestDispute.refund_amount || 0) > 0">退款 {{ formatCny(latestDispute.refund_amount) }}</span>
          <p>{{ latestDispute.resolution_note }}</p>
        </div>
        <div v-if="latestDispute.evidence?.length" class="evidence-list">
          <article v-for="item in latestDispute.evidence" :key="item.id" class="evidence-item">
            <div>
              <strong>{{ item.submitter_name || actorRoleLabel(item.submitter_role) }}</strong>
              <span>{{ formatTime(item.created_at) }}</span>
            </div>
            <p v-if="item.description">{{ item.description }}</p>
            <a v-if="item.file_url" :href="getFullUrl(item.file_url)" target="_blank" rel="noopener noreferrer">
              查看附件：{{ item.file_name || '证据文件' }}
            </a>
            <span v-if="item.reference_type" class="evidence-reference">
              订单记录：{{ evidenceReferenceLabel(item.reference_type) }} #{{ item.reference_id }}
            </span>
          </article>
        </div>
        <el-button v-if="activeDispute" :disabled="submittingEvidence" @click="showEvidenceDialog = true">补充证据</el-button>
      </section>

      <section v-if="deliveries.length" :class="['delivery-history-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('delivery') }]">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('delivery')">交付与验收</strong><span v-else></span><el-button text @click="toggleCard('delivery')">{{ isCardCollapsed('delivery') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <div>
            <h3>交付与验收</h3>
            <span>所有版本均保留，最新版本不会覆盖历史记录</span>
          </div>
          <el-tag v-if="order.acceptance_deadline_at" type="warning" effect="plain">
            {{ acceptanceDeadlineText }}
          </el-tag>
          <el-tag v-else-if="order.status === 'completed'" type="success" effect="plain">
            {{ order.completion_type === 'automatic' ? '系统自动验收' : '客户已验收' }}
          </el-tag>
        </div>
        <div class="revision-quota">
          <span>免费修改次数</span>
          <strong>{{ order.revision_used_count || 0 }} / {{ order.included_revision_count || 0 }}</strong>
          <span v-if="activeRevision" class="revision-pending">返修处理中，摄影师需重新交付</span>
        </div>
        <div class="delivery-version-list">
          <article v-for="item in deliveries" :key="item.id" class="delivery-version-card">
            <div class="delivery-version-head">
              <div>
                <strong>交付 V{{ item.version }}</strong>
                <span>{{ formatTime(item.created_at) }}</span>
              </div>
              <el-tag :type="deliveryStatusType(item.status)" effect="plain">
                {{ deliveryStatusLabel(item.status) }}
              </el-tag>
            </div>
            <p v-if="item.description">{{ item.description }}</p>
            <div class="delivery-version-meta">
              <span>{{ item.file_count }} 个文件</span>
              <span v-if="item.acceptance_deadline_at">验收截止：{{ formatTime(item.acceptance_deadline_at) }}</span>
            </div>
            <el-button plain @click="openViewDelivery(item)">查看此版本</el-button>
          </article>
        </div>
        <div v-if="revisionRequests.length" class="revision-records">
          <div v-for="item in revisionRequests" :key="item.id" class="revision-record">
            <div>
              <strong>第 {{ item.sequence }} 次修改</strong>
              <el-tag size="small" :type="item.status === 'requested' ? 'warning' : 'success'">
                {{ item.status === 'requested' ? '等待重新交付' : '已完成' }}
              </el-tag>
            </div>
            <p>{{ item.instructions }}</p>
            <span>摄影师响应期限：{{ formatTime(item.response_due_at) }}</span>
            <span v-if="item.expected_redelivery_at">预计重新交付：{{ formatTime(item.expected_redelivery_at) }}</span>
            <el-button
              v-if="item.status === 'requested' && isPhotographer && !item.expected_redelivery_at"
              type="primary"
              plain
              @click="openRevisionScheduleDialog(item)"
            >
              确认返修排期
            </el-button>
          </div>
        </div>
      </section>

      <section v-if="showReschedulePanel" :class="['reschedule-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('reschedule') }]">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('reschedule')">改期申请处理</strong><span v-else></span><el-button text @click="toggleCard('reschedule')">{{ isCardCollapsed('reschedule') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <h3>改期申请处理中</h3>
          <span>{{ rescheduleResponsibilityText }}</span>
        </div>
        <div class="change-grid">
          <div>
            <span>原预约时间</span>
            <strong>{{ formatTime(order.appointment_time) }}</strong>
          </div>
          <div>
            <span>申请改到</span>
            <strong>{{ formatTime(activeReschedule.requested_appointment_time) }}</strong>
          </div>
        </div>
        <p class="change-reason">{{ activeReschedule.reason }}</p>
        <div class="action-row reschedule-actions">
          <template v-if="canRespondReschedule">
            <el-button type="success" :loading="acting" @click="acceptRescheduleAction">接受改期</el-button>
            <el-button type="danger" plain :disabled="acting" @click="rejectRescheduleAction">拒绝改期</el-button>
            <el-button :disabled="acting" @click="openCounterRescheduleDialog">反提时间</el-button>
          </template>
          <el-button v-else-if="canWithdrawReschedule" type="danger" plain :loading="acting" @click="withdrawRescheduleAction">
            撤回申请
          </el-button>
        </div>
      </section>

      <section v-if="showCancellationPanel" :class="['rejection-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('cancellation') }]">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('cancellation')">订单取消信息</strong><span v-else></span><el-button text @click="toggleCard('cancellation')">{{ isCardCollapsed('cancellation') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <h3>{{ cancellationTitle }}</h3>
          <span>{{ cancelledByText }}</span>
        </div>
        <p class="rejection-reason">{{ cancellationReason }}</p>
        <div v-if="isCustomer" class="rejection-actions">
          <el-button type="primary" @click="goRebook">重新选时间</el-button>
          <el-button @click="contactPhotographer">联系摄影师</el-button>
          <el-button @click="browsePackages">看其他方案</el-button>
        </div>
      </section>

      <section :class="['timeline-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('progress') }]">
        <div class="card-collapse-bar"><strong>订单流程</strong><el-button text @click="toggleCard('progress')">{{ isCardCollapsed('progress') ? '展开' : '收起' }}</el-button></div>
        <div class="timeline-step" v-for="step in stepsWithState" :key="step.key" :class="step.state">
          <div class="step-marker">{{ step.index + 1 }}</div>
          <div class="step-body">
            <div class="step-title">{{ step.title }}</div>
            <div class="step-owner">责任方：{{ step.owner }}</div>
            <div class="step-time">{{ step.timeText }}</div>
            <p>{{ step.description }}</p>
          </div>
        </div>
      </section>

      <div class="detail-grid">
        <section :class="['action-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('action') }]">
          <div class="card-collapse-bar"><strong v-if="isCardCollapsed('action')">当前处理</strong><span v-else></span><el-button text @click="toggleCard('action')">{{ isCardCollapsed('action') ? '展开' : '收起' }}</el-button></div>
          <div class="section-head">
            <h3>当前处理</h3>
            <span>{{ currentOwnerText }}</span>
          </div>
          <p class="next-copy">{{ nextActionText }}</p>
          <div v-if="order.action_deadline_at" class="action-deadline-card" :class="{ overdue: order.overdue_at }">
            <strong>{{ order.overdue_at ? '处理已逾期' : '处理截止时间' }}</strong>
            <span>{{ formatTime(order.action_deadline_at) }}</span>
            <small v-if="order.auto_action_code">逾期后：{{ autoActionLabel(order.auto_action_code) }}</small>
          </div>
          <div class="action-row">
            <template v-if="order.status === 'pending' && isPhotographer">
              <el-button type="success" :loading="acting" @click="confirmOrderAction">确认预约</el-button>
              <el-button type="danger" :loading="acting" @click="rejectOrderAction">拒绝预约</el-button>
            </template>
            <template v-else-if="canPayOrder">
              <el-button type="primary" :loading="paying" @click="payOrderAction">{{ paymentButtonText }}</el-button>
            </template>
            <template v-else-if="order.status === 'confirmed' && isPhotographer">
              <el-button type="primary" :loading="acting" @click="startOrderAction">开始拍摄</el-button>
            </template>
            <template v-else-if="canDeliver">
              <el-button type="primary" @click="openDeliveryDialog">
                {{ order.after_sales_status === 'revision_requested' ? '重新交付作品' : '交付作品' }}
              </el-button>
            </template>
            <template v-else-if="activeDispute">
              <el-button @click="showEvidenceDialog = true">补充争议证据</el-button>
            </template>
            <template v-else-if="order.status === 'delivered' && isCustomer">
              <el-button type="primary" :loading="acting" @click="acceptDeliveryAction">确认验收</el-button>
              <el-button plain @click="openViewDelivery()">查看作品</el-button>
              <el-button v-if="canRequestRevision" type="warning" plain @click="openRevisionDialog">申请修改</el-button>
            </template>
            <template v-else-if="order.status === 'completed' && isCustomer">
              <el-button plain @click="openViewDelivery()">查看作品</el-button>
              <el-button v-if="!order.rating" type="primary" @click="openReviewDialog">评价本次服务</el-button>
              <el-button v-else type="info" plain @click="openViewReview">查看评价</el-button>
            </template>
            <template v-else>
              <el-button v-if="hasDelivery" @click="openViewDelivery()">查看作品</el-button>
              <el-button v-if="order.rating" type="info" @click="openViewReview">查看评价</el-button>
            </template>
            <el-button v-if="canRequestReschedule" :loading="acting" @click="openRescheduleDialog">
              {{ rescheduleButtonText }}
            </el-button>
            <el-button v-if="canCancel" type="danger" plain :loading="acting" @click="cancelOrderAction">
              取消订单
            </el-button>
            <el-button v-if="canOpenDispute" type="danger" plain :disabled="acting" @click="showDisputeDialog = true">
              发起争议
            </el-button>
          </div>
        </section>
      </div>

      <section :class="['event-panel', 'collapsible-card', { 'is-collapsed': isCardCollapsed('events') }]">
        <div class="card-collapse-bar"><strong v-if="isCardCollapsed('events')">订单事件</strong><span v-else></span><el-button text @click="toggleCard('events')">{{ isCardCollapsed('events') ? '展开' : '收起' }}</el-button></div>
        <div class="section-head">
          <h3>订单事件</h3>
          <span>关键操作均可追溯</span>
        </div>
        <el-timeline>
          <el-timeline-item
            v-for="item in history"
            :key="item.id || `${item.event_type}-${item.created_at}`"
            :timestamp="formatTime(item.created_at)"
            placement="top"
          >
            <strong>{{ eventTitle(item) }}</strong>
            <div class="event-meta">{{ actorRoleLabel(item.actor_role) }}{{ item.actor_name ? ` · ${item.actor_name}` : '' }}</div>
            <p v-if="item.note" class="event-note">{{ item.note }}</p>
          </el-timeline-item>
        </el-timeline>
      </section>
      </div>
    </template>

    <el-empty v-else description="订单不存在" />

    <el-dialog v-model="showRescheduleDialog" :title="rescheduleDialogTitle" width="500px" @closed="resetRescheduleForm">
      <el-form label-width="90px">
        <el-form-item label="新预约时间">
          <el-date-picker
            v-model="rescheduleTime"
            type="datetime"
            placeholder="选择新的拍摄时间"
            format="YYYY-MM-DD HH:mm"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="改期原因">
          <el-input
            v-model="rescheduleReason"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="请说明候选时间和调整原因，对方接受后才会生效"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRescheduleDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingReschedule" @click="submitReschedule">
          {{ rescheduleSubmitText }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDeliveryDialog" :title="order?.after_sales_status === 'revision_requested' ? '重新交付作品' : '交付作品'" width="520px" @closed="resetDeliveryForm">
      <el-form label-width="80px">
        <el-form-item label="上传作品">
          <el-upload
            v-model:file-list="deliveryFiles"
            :auto-upload="false"
            accept=".jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.tif,.tiff,.zip,.rar,.7z,.psd"
            multiple
          >
            <el-button type="primary" plain><el-icon><Plus /></el-icon>选择交付文件</el-button>
            <template #tip><div class="el-upload__tip">支持 JPG、PNG、WebP、AVIF、HEIC、TIFF、PSD、ZIP、RAR、7Z。</div></template>
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
        <el-button type="primary" :loading="submittingDelivery" @click="submitDelivery">确认交付</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showViewDialog" :title="selectedDelivery ? `交付 V${selectedDelivery.version}` : '交付作品'" width="720px">
      <div v-if="selectedDelivery?.description" class="view-desc">{{ selectedDelivery.description }}</div>
      <div v-if="selectedDelivery?.files?.length" class="delivery-download-list">
        <div v-for="file in selectedDelivery.files" :key="file.id" class="delivery-download-item">
          <div>
            <strong>{{ file.file_name }}</strong>
            <span>{{ formatFileSize(file.file_size) }}</span>
          </div>
          <el-button type="primary" plain :loading="downloadingFileId === file.id" @click="handleDownloadFile(file)">下载</el-button>
        </div>
      </div>
      <div class="view-images">
        <el-image
          v-for="(img, i) in deliveryImages"
          :key="i"
          :src="getFullUrl(img)"
          fit="cover"
          class="delivery-img"
          :preview-src-list="deliveryImages.map(getFullUrl)"
          :initial-index="i"
        />
      </div>
      <el-empty v-if="!deliveryImages.length" description="暂无交付作品" />
    </el-dialog>

    <el-dialog v-model="showRevisionDialog" title="申请修改" width="520px" @closed="resetRevisionForm">
      <el-alert
        :title="`本次申请将使用第 ${(order?.revision_used_count || 0) + 1} / ${order?.included_revision_count || 0} 次免费修改`"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-position="top" class="revision-form">
        <el-form-item label="修改说明" required>
          <el-input
            v-model="revisionInstructions"
            type="textarea"
            :rows="5"
            maxlength="1000"
            show-word-limit
            placeholder="请具体说明需要调整的位置、色彩、构图或修图要求"
          />
        </el-form-item>
        <el-form-item label="参考图片（可选）">
          <el-upload
            v-model:file-list="revisionFiles"
            :auto-upload="false"
            list-type="picture-card"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRevisionDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingRevision" @click="submitRevision">提交修改申请</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRevisionScheduleDialog" title="确认返修排期" width="460px" @closed="resetRevisionScheduleForm">
      <el-form label-position="top">
        <el-form-item label="预计重新交付时间" required>
          <el-date-picker
            v-model="expectedRedeliveryAt"
            type="datetime"
            placeholder="选择预计完成修改的时间"
            format="YYYY-MM-DD HH:mm"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRevisionScheduleDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingRevisionSchedule" @click="submitRevisionSchedule">
          确认排期
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDisputeDialog" title="发起平台争议" width="min(560px, 92vw)" @closed="resetDisputeForm">
      <el-alert
        title="提交后平台将暂停自动验收和资金结算。请先尝试与对方沟通，并如实提交可核验材料。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form label-position="top" class="dispute-form">
        <el-form-item label="争议类型" required>
          <el-select v-model="disputeReasonCode" placeholder="请选择争议类型" style="width: 100%">
            <el-option label="交付质量或内容不符" value="quality_issue" />
            <el-option label="未按约定时间履约" value="delivery_delay" />
            <el-option label="服务无法继续" value="service_failure" />
            <el-option label="对方配合问题" value="cooperation_issue" />
            <el-option label="其他争议" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="希望平台如何处理" required>
          <el-select v-model="disputeRequestedResolution" placeholder="请选择处理诉求" style="width: 100%">
            <el-option label="协调后继续履约" value="continue_fulfillment" />
            <el-option label="部分退款" value="partial_refund" />
            <el-option label="全额退款并终止订单" value="full_refund" />
            <el-option label="其他处理" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="事实说明" required>
          <el-input
            v-model="disputeDescription"
            type="textarea"
            :rows="6"
            maxlength="2000"
            show-word-limit
            placeholder="请按时间顺序说明发生了什么、已沟通情况，以及希望平台核查的关键事实"
          />
        </el-form-item>
        <el-form-item label="初始证据（可选）">
          <el-upload v-model:file-list="disputeFiles" :auto-upload="false" accept="image/*" multiple>
            <el-button>选择文件</el-button>
            <template #tip><div class="el-upload__tip">可上传聊天截图、交付对比和合同约定截图。</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDisputeDialog = false">返回</el-button>
        <el-button type="danger" :loading="submittingDispute" @click="submitDispute">确认发起争议</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEvidenceDialog" title="补充争议证据" width="min(520px, 92vw)" @closed="resetEvidenceForm">
      <el-form label-position="top" class="dispute-form">
        <el-form-item label="证据说明" required>
          <el-input
            v-model="evidenceDescription"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="说明该材料能够证明什么，以及对应的时间或约定"
          />
        </el-form-item>
        <el-form-item label="附件（可选）">
          <el-upload v-model:file-list="evidenceFiles" :auto-upload="false" accept="image/*" multiple>
            <el-button>选择文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEvidenceDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingEvidence" @click="submitEvidence">提交证据</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showReviewDialog" title="评价作品" width="460px" @closed="resetReviewForm">
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
      <div class="review-score">
        <el-rate :model-value="order?.rating || 0" :max="10" disabled show-score score-template="{value} 分" />
      </div>
      <div v-if="order?.review_text" class="review-text-content">{{ order.review_text }}</div>
      <el-empty v-else description="暂无评价文字" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MessageSquare as ChatDotRound, Plus } from 'lucide-vue-next'
import { promptRejectReason } from '@/utils/orderRejectPrompt'
import {
  acceptOrder,
  acceptReschedule,
  cancelOrder,
  confirmOrder,
  counterReschedule,
  deliverWorks,
  downloadDeliveryFile,
  getOrderDetail,
  rejectOrder,
  rejectReschedule,
  requestReschedule,
  reviewOrder,
  startOrder,
  withdrawReschedule,
  createOrderPayment,
  confirmMockPayment,
  getOrderFinancialSummary,
  requestDeliveryRevision,
  acknowledgeDeliveryRevision,
  openOrderDispute,
  addOrderDisputeEvidence,
} from '@/api/order'

const route = useRoute()
const router = useRouter()

const order = ref(null)
const history = ref([])
const loading = ref(false)
const acting = ref(false)
const paying = ref(false)
const financialSummary = ref(null)
const deliveries = ref([])
const revisionRequests = ref([])
const disputes = ref([])
const collapsibleCardKeys = ['action', 'reschedule', 'cancellation', 'progress', 'contract', 'payment', 'delivery', 'dispute', 'events']
const collapsedCards = reactive(Object.fromEntries(collapsibleCardKeys.map(key => [key, false])))
const isCardCollapsed = key => Boolean(collapsedCards[key])
const toggleCard = key => { collapsedCards[key] = !collapsedCards[key] }
const setAllCardsCollapsed = collapsed => {
  collapsibleCardKeys.forEach(key => { collapsedCards[key] = collapsed })
}

const showDeliveryDialog = ref(false)
const submittingDelivery = ref(false)
const deliveryFiles = ref([])
const deliveryDescription = ref('')
const selectedDelivery = ref(null)
const downloadingFileId = ref(null)

const showRevisionDialog = ref(false)
const submittingRevision = ref(false)
const revisionInstructions = ref('')
const revisionFiles = ref([])
const showRevisionScheduleDialog = ref(false)
const submittingRevisionSchedule = ref(false)
const expectedRedeliveryAt = ref(null)
const schedulingRevision = ref(null)

const showDisputeDialog = ref(false)
const submittingDispute = ref(false)
const disputeReasonCode = ref('')
const disputeRequestedResolution = ref('')
const disputeDescription = ref('')
const disputeFiles = ref([])
const showEvidenceDialog = ref(false)
const submittingEvidence = ref(false)
const evidenceDescription = ref('')
const evidenceFiles = ref([])

const showViewDialog = ref(false)
const showReviewDialog = ref(false)
const submittingReview = ref(false)
const reviewRating = ref(0)
const reviewText = ref('')
const showViewReviewDialog = ref(false)

const showRescheduleDialog = ref(false)
const submittingReschedule = ref(false)
const rescheduleTime = ref(null)
const rescheduleReason = ref('')
const rescheduleMode = ref('request')

const tokenPayload = computed(() => {
  const token = localStorage.getItem('token')
  if (!token) return {}
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return {}
  }
})

const userId = computed(() => Number(tokenPayload.value.sub || 0))
const isCustomer = computed(() => Number(order.value?.customer_id) === userId.value)
const isPhotographer = computed(() => Number(order.value?.photographer_id) === userId.value)
const activeReschedule = computed(() => order.value?.active_reschedule_request || null)
const hasDelivery = computed(() => deliveries.value.length > 0 || !!order.value?.delivery?.images?.length)
const imageExtensions = ['jpg', 'jpeg', 'png', 'webp', 'avif', 'heic', 'heif', 'tif', 'tiff']
const isImageDeliveryFile = file => {
  if (file?.file_type?.startsWith('image/')) return true
  const extension = file?.file_name?.split('.').pop()?.toLowerCase()
  return imageExtensions.includes(extension)
}
const deliveryImages = computed(() => (
  selectedDelivery.value?.files?.filter(isImageDeliveryFile).map(file => file.file_url)
  || order.value?.delivery?.images
  || []
))
const activeRevision = computed(() => revisionRequests.value.find(item => item.status === 'requested') || null)
const latestDispute = computed(() => disputes.value[0] || null)
const activeDispute = computed(() => disputes.value.find(item => ['open', 'assigned', 'investigating'].includes(item.status)) || null)
const customerName = computed(() => order.value?.customer_name || `客户 #${order.value?.customer_id || ''}`)
const customerInitial = computed(() => customerName.value?.[0] || '?')
const customerAvatarUrl = computed(() => getFullUrl(order.value?.customer_avatar_url))
const photographerName = computed(() => order.value?.photographer_name || `摄影师 #${order.value?.photographer_id || ''}`)
const photographerInitial = computed(() => photographerName.value?.[0] || '?')
const photographerAvatarUrl = computed(() => getFullUrl(order.value?.photographer_avatar_url))

const counterpartName = computed(() => isCustomer.value ? photographerName.value : customerName.value)
const counterpartInitial = computed(() => isCustomer.value ? photographerInitial.value : customerInitial.value)
const counterpartAvatarUrl = computed(() => isCustomer.value ? photographerAvatarUrl.value : customerAvatarUrl.value)
const counterpartRoleLabel = computed(() => isCustomer.value ? '摄影师' : '客户')
const hasStructuredContract = computed(() => (
  !!order.value?.contract_snapshot
  || order.value?.final_price !== null && order.value?.final_price !== undefined
))
const sourceTypeLabel = computed(() => ({
  package: '固定套餐',
  project: '定制企划',
  legacy: '历史订单',
}[order.value?.source_type] || '订单'))
const paymentModeLabel = computed(() => ({
  full: '全款',
  deposit_balance: '定金 + 尾款',
}[order.value?.payment_mode] || order.value?.payment_mode || '全款'))
const paymentStatusLabel = computed(() => ({
  unpaid: '待支付',
  deposit_paid: '定金已进入平台担保',
  paid_in_escrow: '全款已进入平台担保',
  partially_refunded: '已部分退款',
  refunded: '已全额退款',
  settled: '已完成结算',
  payment_failed: '支付失败或已超时',
}[order.value?.payment_status] || order.value?.payment_status || '待支付'))
const canPayOrder = computed(() => (
  isCustomer.value
  && (
    order.value?.status === 'awaiting_customer_payment'
    || (order.value?.status === 'confirmed' && order.value?.payment_status === 'deposit_paid')
  )
))
const paymentButtonText = computed(() => order.value?.payment_status === 'deposit_paid' ? '支付尾款' : (
  order.value?.payment_mode === 'deposit_balance' ? '支付定金' : '支付全款'
))
const paymentAmountHint = computed(() => {
  const total = Number(order.value?.final_price || 0)
  if (!total) return ''
  if (order.value?.payment_status === 'deposit_paid') {
    return `¥${Math.max(0, total - Number(order.value?.escrow_amount || 0)).toFixed(2)}`
  }
  if (order.value?.payment_mode === 'deposit_balance') {
    return `¥${(total * Number(order.value?.deposit_rate || 0.3)).toFixed(2)}`
  }
  return `¥${total.toFixed(2)}`
})

const formatPolicy = (policy) => {
  if (!policy) return ''
  if (typeof policy === 'string') return policy
  if (policy.description) return policy.description
  if (Array.isArray(policy.rules)) {
    return policy.rules.map(item => item?.description).filter(Boolean).join('；')
  }
  if (policy.response_hours) return `需在 ${policy.response_hours} 小时内响应，原预约时间继续保留。`
  return ''
}

const cancellationPolicyText = computed(() => formatPolicy(order.value?.cancellation_policy_snapshot))
const reschedulePolicyText = computed(() => formatPolicy(order.value?.reschedule_policy_snapshot))

const orderNoteSections = computed(() => {
  const notes = order.value?.notes
  if (!notes) return []
  const sections = []
  const lines = notes.split('\n')
  let currentLabel = ''
  let currentContent = ''
  for (const line of lines) {
    const labelMatch = line.match(/^【(.+?)】/)
    if (labelMatch) {
      if (currentLabel) {
        sections.push({ label: currentLabel, content: currentContent.trim() })
      }
      currentLabel = labelMatch[1]
      currentContent = line.slice(labelMatch[0].length).trim()
    } else {
      currentContent += (currentContent ? '\n' : '') + line
    }
  }
  if (currentLabel) {
    sections.push({ label: currentLabel, content: currentContent.trim() })
  }
  return sections
})

const chatTargetId = computed(() => {
  if (!order.value) return null
  const targetId = isCustomer.value ? order.value.photographer_id : order.value.customer_id
  return Number(targetId) === userId.value ? null : targetId
})
const canDeliver = computed(() => !activeDispute.value && isPhotographer.value && (
  order.value?.status === 'in_progress'
  || (order.value?.status === 'delivered' && order.value?.after_sales_status === 'revision_requested')
))
const canRequestRevision = computed(() => (
  isCustomer.value
  && order.value?.status === 'delivered'
  && order.value?.after_sales_status === 'none'
  && Number(order.value?.revision_used_count || 0) < Number(order.value?.included_revision_count || 0)
))
const canOpenDispute = computed(() => (
  !activeDispute.value
  && ['confirmed', 'in_progress', 'delivered'].includes(order.value?.status)
  && (isCustomer.value || isPhotographer.value)
))
const acceptanceDeadlineText = computed(() => (
  order.value?.acceptance_deadline_at
    ? `请在 ${formatTime(order.value.acceptance_deadline_at)} 前验收，逾期将自动验收`
    : ''
))
const cancellationReason = computed(() => order.value?.cancellation_reason || order.value?.rejection_reason || '')
const showCancellationPanel = computed(() => (
  order.value?.status === 'cancelled' && !!cancellationReason.value
))
const showReschedulePanel = computed(() => (
  !!activeReschedule.value
))
const canRequestReschedule = computed(() => (
  (isCustomer.value || isPhotographer.value)
  && ['pending', 'awaiting_customer_payment', 'confirmed'].includes(order.value?.status)
  && !activeReschedule.value
  && !activeDispute.value
))
const canRespondReschedule = computed(() => (
  !!activeReschedule.value
  && Number(activeReschedule.value.requested_by) !== userId.value
))
const canWithdrawReschedule = computed(() => (
  !!activeReschedule.value
  && Number(activeReschedule.value.requested_by) === userId.value
))
const canCancel = computed(() => {
  if (activeDispute.value) return false
  const status = order.value?.status
  if (isCustomer.value) return ['pending', 'awaiting_customer_payment', 'confirmed'].includes(status)
  if (isPhotographer.value) return ['pending', 'awaiting_customer_payment', 'confirmed'].includes(status)
  return false
})
const rescheduleButtonText = computed(() => '申请改期')
const rescheduleDialogTitle = computed(() => rescheduleMode.value === 'counter' ? '反提改期时间' : '申请改期')
const rescheduleSubmitText = computed(() => rescheduleMode.value === 'counter' ? '提交反提时间' : '提交申请')
const rescheduleResponsibilityText = computed(() => {
  if (!activeReschedule.value) return ''
  return canRespondReschedule.value ? '等待您处理，原档期继续有效' : '等待对方处理，原档期继续有效'
})
const cancellationTitle = computed(() => (
  order.value?.cancelled_by === 'photographer' && order.value?.rejection_reason ? '预约未通过' : '订单已取消'
))
const cancelledByText = computed(() => {
  const label = actorRoleLabel(order.value?.cancelled_by)
  return label ? `${label}已填写原因` : '已填写取消原因'
})

const STEP_DEFS = [
  { key: 'pending', title: '待确认', owner: '摄影师', description: '客户已提交预约，等待摄影师确认或拒绝。' },
  { key: 'awaiting_payment', title: '待支付', owner: '客户', description: '摄影师已接受预约，客户支付后订单正式确认。' },
  { key: 'confirmed', title: '已确认', owner: '摄影师', description: '预约已确认，双方可按约定时间准备拍摄。' },
  { key: 'shooting', title: '拍摄中/待交付', owner: '摄影师', description: '拍摄完成后由摄影师上传并交付作品。' },
  { key: 'delivered', title: '待验收', owner: '客户', description: '客户可确认验收或在免费次数内申请修改。' },
  { key: 'completed', title: '已完成', owner: '双方', description: '客户验收或系统自动验收后完成并结算；评价为可选操作。' },
]

const currentStepIndex = computed(() => {
  const status = order.value?.status
  if (status === 'pending') return 0
  if (status === 'awaiting_customer_payment') return 1
  if (status === 'confirmed') return 2
  if (status === 'in_progress') return 3
  if (status === 'delivered') return 4
  if (['received', 'reviewed', 'completed'].includes(status)) return 5
  return -1
})

const stepsWithState = computed(() => STEP_DEFS.map((step, index) => ({
  ...step,
  index,
  state: order.value?.status === 'cancelled'
    ? 'disabled'
    : index < currentStepIndex.value
      ? 'done'
      : index === currentStepIndex.value
        ? 'current'
        : 'waiting',
  timeText: stepTimeText(step.key),
})))

const currentOwnerText = computed(() => {
  if (!order.value) return ''
  const status = order.value.status
  if (activeDispute.value) return '当前责任方：平台管理员'
  if (activeReschedule.value) return canRespondReschedule.value ? '当前责任方：您' : '当前责任方：对方'
  if (status === 'pending') return '当前责任方：摄影师'
  if (status === 'awaiting_customer_payment') return '当前责任方：客户'
  if (status === 'confirmed' || status === 'in_progress') return '当前责任方：摄影师'
  if (status === 'delivered') return order.value.after_sales_status === 'revision_requested'
    ? '当前责任方：摄影师'
    : '当前责任方：客户'
  if (['received', 'reviewed', 'completed'].includes(status)) return '交易已完成，评价可选'
  if (status === 'cancelled') return '订单已取消'
  return '等待处理'
})

const nextActionText = computed(() => {
  if (!order.value) return ''
  const status = order.value.status
  if (activeDispute.value) return '平台正在核查双方材料。您可以继续补充与订单约定、沟通和交付相关的证据。'
  if (activeReschedule.value) return canRespondReschedule.value
    ? '请接受、拒绝或反提改期时间；处理期间原预约仍然有效。'
    : '改期申请已提交，等待对方处理；处理期间原预约仍然有效。'
  if (status === 'pending') return isPhotographer.value ? '请确认是否接受该预约。' : '等待摄影师确认预约。'
  if (status === 'awaiting_customer_payment') return isCustomer.value
    ? '请在支付期限内完成付款，资金将先进入平台担保。'
    : '等待客户完成支付，支付成功后订单将正式确认。'
  if (status === 'confirmed') return isPhotographer.value ? '到达拍摄阶段时，请将订单标记为拍摄中/待交付。' : '摄影师已确认预约，请按约定时间准备拍摄。'
  if (status === 'in_progress') return isPhotographer.value ? '请在拍摄完成后交付作品。' : '摄影师正在处理本次拍摄，完成后会交付作品。'
  if (status === 'delivered' && order.value.after_sales_status === 'revision_requested') return isPhotographer.value
    ? '客户已申请修改，请根据说明重新交付新版本。'
    : '修改申请已提交，自动验收已暂停，等待摄影师重新交付。'
  if (status === 'delivered') return isCustomer.value
    ? '请在验收期限内查看作品并确认验收；如需调整，可使用合同内免费修改次数。'
    : '等待客户验收；若客户在期限内未操作，系统将自动验收。'
  if (['received', 'reviewed', 'completed'].includes(status)) return order.value.rating
    ? '订单已完成并已评价。'
    : '订单已完成，您仍可选择提交评价。'
  if (status === 'cancelled') return cancellationReason.value
    ? '订单已取消，请查看原因并选择下一步。'
    : '订单已取消，无需继续处理。'
  return '暂无下一步操作。'
})

const fetchDetail = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    router.push({ path: '/login', query: { redirect: route.fullPath } })
    return
  }
  loading.value = true
  try {
    const [{ data }, financialRes] = await Promise.all([
      getOrderDetail(route.params.orderId),
      getOrderFinancialSummary(route.params.orderId).catch(() => ({ data: null })),
    ])
    order.value = data.order
    history.value = data.history || []
    deliveries.value = data.deliveries || []
    revisionRequests.value = data.revision_requests || []
    disputes.value = data.disputes || []
    selectedDelivery.value = deliveries.value[0] || null
    financialSummary.value = financialRes.data
  } catch {
    order.value = null
    history.value = []
    deliveries.value = []
    revisionRequests.value = []
    disputes.value = []
    selectedDelivery.value = null
    financialSummary.value = null
  } finally {
    loading.value = false
  }
}

const confirmOrderAction = async () => {
  try { await ElMessageBox.confirm('确认接受此预约？', '确认预约', { type: 'warning' }) } catch { return }
  acting.value = true
  try {
    await confirmOrder(order.value.id)
    ElMessage.success(order.value?.final_price !== null ? '已接受预约，等待客户支付' : '已确认预约')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const payOrderAction = async () => {
  if (!order.value || paying.value) return
  paying.value = true
  const storageKey = `payment-idempotency:${order.value.id}:${order.value.payment_status || 'unpaid'}`
  let idempotencyKey = localStorage.getItem(storageKey)
  if (!idempotencyKey) {
    idempotencyKey = `web-${order.value.id}-${crypto.randomUUID?.() || Date.now()}`
    localStorage.setItem(storageKey, idempotencyKey)
  }
  try {
    const { data: payment } = await createOrderPayment(order.value.id, idempotencyKey)
    await confirmMockPayment(payment.id, `web-${payment.payment_no}`)
    localStorage.removeItem(storageKey)
    ElMessage.success(`${paymentPurposeLabel(payment.purpose)}支付成功，资金已进入平台担保`)
    await fetchDetail()
  } finally {
    paying.value = false
  }
}

const rejectOrderAction = async () => {
  let reason
  try { reason = await promptRejectReason() } catch { return }
  acting.value = true
  try {
    await rejectOrder(order.value.id, reason)
    ElMessage.info('已拒绝预约')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const openRescheduleDialog = () => {
  rescheduleMode.value = 'request'
  rescheduleTime.value = null
  rescheduleReason.value = ''
  showRescheduleDialog.value = true
}

const openCounterRescheduleDialog = () => {
  rescheduleMode.value = 'counter'
  rescheduleTime.value = null
  rescheduleReason.value = ''
  showRescheduleDialog.value = true
}

const resetRescheduleForm = () => {
  rescheduleTime.value = null
  rescheduleReason.value = ''
  rescheduleMode.value = 'request'
}

const submitReschedule = async () => {
  if (!rescheduleTime.value) {
    ElMessage.warning('请选择新的预约时间')
    return
  }
  const reason = rescheduleReason.value.trim()
  if (!reason) {
    ElMessage.warning('请填写改期原因')
    return
  }
  submittingReschedule.value = true
  try {
    const payload = {
      appointment_time: rescheduleTime.value,
      reason,
    }
    if (rescheduleMode.value === 'counter') {
      await counterReschedule(order.value.id, activeReschedule.value.id, payload)
      ElMessage.success('已提出新的候选时间')
    } else {
      await requestReschedule(order.value.id, payload)
      ElMessage.success('改期申请已提交')
    }
    showRescheduleDialog.value = false
    fetchDetail()
  } finally {
    submittingReschedule.value = false
  }
}

const acceptRescheduleAction = async () => {
  try { await ElMessageBox.confirm('接受后订单将切换到该时间，是否继续？', '接受改期', { type: 'warning' }) } catch { return }
  acting.value = true
  try {
    await acceptReschedule(order.value.id, activeReschedule.value.id)
    ElMessage.success('已确认改期')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const rejectRescheduleAction = async () => {
  let note
  try {
    const { value } = await ElMessageBox.prompt('可填写拒绝原因，原预约时间会继续保留。', '拒绝改期', {
      inputType: 'textarea',
      inputPlaceholder: '如：该时间已有其他安排。',
      confirmButtonText: '确认拒绝',
      cancelButtonText: '取消',
    })
    note = value?.trim() || ''
  } catch { return }
  acting.value = true
  try {
    await rejectReschedule(order.value.id, activeReschedule.value.id, note)
    ElMessage.info('已拒绝改期，原预约保持不变')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const withdrawRescheduleAction = async () => {
  try { await ElMessageBox.confirm('撤回后候选时间将释放，原预约保持不变。', '撤回改期', { type: 'warning' }) } catch { return }
  acting.value = true
  try {
    await withdrawReschedule(order.value.id, activeReschedule.value.id)
    ElMessage.info('改期申请已撤回')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const cancelOrderAction = async () => {
  let reason
  try {
    const { value } = await ElMessageBox.prompt('请填写取消原因，对方会在订单详情中看到。', '取消订单', {
      confirmButtonText: '确认取消',
      cancelButtonText: '再想想',
      inputType: 'textarea',
      inputPlaceholder: '如：行程变化，无法按原时间拍摄。',
      inputValidator: (val) => {
        if (!val || !val.trim()) return '取消订单必须填写原因'
        if (val.trim().length > 500) return '取消原因不能超过 500 字'
        return true
      },
      inputErrorMessage: '取消订单必须填写原因',
      type: 'warning',
    })
    reason = value.trim()
  } catch {
    return
  }

  acting.value = true
  try {
    await cancelOrder(order.value.id, reason)
    ElMessage.info('订单已取消')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const startOrderAction = async () => {
  try { await ElMessageBox.confirm('确认将订单标记为拍摄中/待交付？', '开始拍摄', { type: 'warning' }) } catch { return }
  acting.value = true
  try {
    await startOrder(order.value.id)
    ElMessage.success('订单已进入拍摄中/待交付')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const acceptDeliveryAction = async () => {
  try { await ElMessageBox.confirm('确认验收当前交付版本？验收后订单将完成并结算担保资金。', '确认验收', { type: 'success' }) } catch { return }
  acting.value = true
  try {
    await acceptOrder(order.value.id)
    ElMessage.success('作品已验收，订单已完成')
    fetchDetail()
  } finally {
    acting.value = false
  }
}

const openDeliveryDialog = () => {
  showDeliveryDialog.value = true
}

const resetDeliveryForm = () => {
  deliveryFiles.value = []
  deliveryDescription.value = ''
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
    formData.append('idempotency_key', `delivery-${order.value.id}-${Date.now()}-${Math.random().toString(16).slice(2)}`)
    await deliverWorks(order.value.id, formData)
    ElMessage.success(order.value?.after_sales_status === 'revision_requested' ? '新版本已重新交付' : '作品已交付')
    showDeliveryDialog.value = false
    fetchDetail()
  } finally {
    submittingDelivery.value = false
  }
}

const openViewDelivery = (item = null) => {
  selectedDelivery.value = item || deliveries.value[0] || null
  showViewDialog.value = true
}

const formatFileSize = value => {
  const bytes = Number(value || 0)
  if (!bytes) return '未知大小'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const handleDownloadFile = async file => {
  if (!order.value || !selectedDelivery.value || !file?.id) return
  downloadingFileId.value = file.id
  try {
    const response = await downloadDeliveryFile(order.value.id, selectedDelivery.value.id, file.id)
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = file.file_name || '交付文件'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } finally {
    downloadingFileId.value = null
  }
}

const openRevisionDialog = () => {
  revisionInstructions.value = ''
  revisionFiles.value = []
  showRevisionDialog.value = true
}

const resetRevisionForm = () => {
  revisionInstructions.value = ''
  revisionFiles.value = []
}

const submitRevision = async () => {
  const instructions = revisionInstructions.value.trim()
  if (!instructions) {
    ElMessage.warning('请填写具体修改说明')
    return
  }
  submittingRevision.value = true
  try {
    const formData = new FormData()
    formData.append('instructions', instructions)
    formData.append('idempotency_key', `revision-${order.value.id}-${Date.now()}-${Math.random().toString(16).slice(2)}`)
    revisionFiles.value.forEach(file => formData.append('files', file.raw))
    await requestDeliveryRevision(order.value.id, formData)
    ElMessage.success('修改申请已提交，自动验收已暂停')
    showRevisionDialog.value = false
    fetchDetail()
  } finally {
    submittingRevision.value = false
  }
}

const openRevisionScheduleDialog = (revision) => {
  schedulingRevision.value = revision
  expectedRedeliveryAt.value = null
  showRevisionScheduleDialog.value = true
}

const resetRevisionScheduleForm = () => {
  schedulingRevision.value = null
  expectedRedeliveryAt.value = null
}

const submitRevisionSchedule = async () => {
  if (!expectedRedeliveryAt.value || !schedulingRevision.value) {
    ElMessage.warning('请选择预计重新交付时间')
    return
  }
  submittingRevisionSchedule.value = true
  try {
    await acknowledgeDeliveryRevision(
      order.value.id,
      schedulingRevision.value.id,
      expectedRedeliveryAt.value,
    )
    ElMessage.success('返修排期已确认')
    showRevisionScheduleDialog.value = false
    fetchDetail()
  } finally {
    submittingRevisionSchedule.value = false
  }
}

const resetDisputeForm = () => {
  disputeReasonCode.value = ''
  disputeRequestedResolution.value = ''
  disputeDescription.value = ''
  disputeFiles.value = []
}

const submitDispute = async () => {
  if (!disputeReasonCode.value || !disputeRequestedResolution.value || !disputeDescription.value.trim()) {
    ElMessage.warning('请完整填写争议类型、处理诉求和事实说明')
    return
  }
  try {
    await ElMessageBox.confirm(
      '发起争议后将暂停自动验收和资金结算。确认提交给平台审核吗？',
      '确认发起争议',
      { type: 'warning', confirmButtonText: '确认提交', cancelButtonText: '返回检查' },
    )
  } catch { return }
  submittingDispute.value = true
  try {
    const formData = new FormData()
    formData.append('reason_code', disputeReasonCode.value)
    formData.append('requested_resolution', disputeRequestedResolution.value)
    formData.append('description', disputeDescription.value.trim())
    disputeFiles.value.forEach(file => formData.append('files', file.raw))
    await openOrderDispute(order.value.id, formData)
    ElMessage.success('争议已提交，自动验收和结算已暂停')
    showDisputeDialog.value = false
    fetchDetail()
  } finally {
    submittingDispute.value = false
  }
}

const resetEvidenceForm = () => {
  evidenceDescription.value = ''
  evidenceFiles.value = []
}

const submitEvidence = async () => {
  if (!evidenceDescription.value.trim() && !evidenceFiles.value.length) {
    ElMessage.warning('请填写证据说明或选择附件')
    return
  }
  submittingEvidence.value = true
  try {
    const formData = new FormData()
    if (evidenceDescription.value.trim()) formData.append('description', evidenceDescription.value.trim())
    evidenceFiles.value.forEach(file => formData.append('files', file.raw))
    await addOrderDisputeEvidence(order.value.id, activeDispute.value.id, formData)
    ElMessage.success('证据已补充并记录提交时间')
    showEvidenceDialog.value = false
    fetchDetail()
  } finally {
    submittingEvidence.value = false
  }
}

const openReviewDialog = () => {
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
    await reviewOrder(order.value.id, {
      rating: reviewRating.value,
      review_text: reviewText.value || undefined,
    })
    ElMessage.success('评价已提交')
    showReviewDialog.value = false
    fetchDetail()
  } finally {
    submittingReview.value = false
  }
}

const openViewReview = () => {
  showViewReviewDialog.value = true
}

const goRebook = () => {
  if (order.value?.photographer_id) {
    router.push(`/booking/${order.value.photographer_id}`)
  }
}

const contactPhotographer = () => {
  if (order.value?.photographer_id) {
    router.push({
      path: '/messages',
      query: {
        to: order.value.photographer_id,
        orderId: order.value.id,
        orderTitle: order.value.package_name || order.value.package_snapshot,
      },
    })
  }
}

const goOrderChat = () => {
  if (!chatTargetId.value) return
  router.push({
    path: '/messages',
    query: {
      to: chatTargetId.value,
      orderId: order.value.id,
      orderTitle: order.value.package_name || order.value.package_snapshot,
    },
  })
}

const browsePackages = () => {
  router.push('/packages')
}

const stepTimeText = (key) => {
  const match = findStepEvent(key)
  return match ? formatTime(match.created_at) : '等待中'
}

const findStepEvent = (key) => {
  const statusMap = {
    pending: ['created', 'pending'],
    awaiting_payment: ['awaiting_payment'],
    confirmed: ['confirmed', 'reschedule_confirmed'],
    shooting: ['in_progress'],
    delivered: ['delivery_submitted', 'delivery_resubmitted', 'delivered'],
    completed: ['delivery_accepted', 'delivery_auto_accepted', 'completed', 'received', 'reviewed'],
  }
  const candidates = statusMap[key] || []
  return history.value.find(item => candidates.includes(item.event_type) || candidates.includes(item.status))
}

const actorRoleLabel = (role) => ({ customer: '客户', photographer: '摄影师', admin: '管理员', system: '系统' }[role] || role)
const disputeStatusType = (status) => ({ open: 'warning', assigned: 'warning', investigating: 'primary', resolved: 'success', cancelled: 'info' }[status] || 'info')
const disputeStatusLabel = (status) => ({ open: '等待平台分配', assigned: '已分配管理员', investigating: '证据审核中', resolved: '已仲裁', cancelled: '已关闭' }[status] || status)
const resolutionLabel = (value) => ({ continue_fulfillment: '继续履约', partial_refund: '部分退款', full_refund: '全额退款', release_settlement: '直接结算', other: '其他处理' }[value] || value)
const evidenceReferenceLabel = (value) => ({ order_message: '订单聊天', order_event: '订单事件', delivery: '交付版本', payment: '支付记录' }[value] || value)
const autoActionLabel = value => ({ cancel_unconfirmed: '系统自动关闭预约', expire_payment: '关闭支付并释放档期', expire_reschedule: '改期申请失效', mark_delivery_overdue: '标记交付逾期并通知双方', auto_accept_delivery: '无售后请求时自动验收' }[value] || value)
const eventTitle = (item) => ({
  created: '提交预约',
  confirmed: '确认预约',
  in_progress: '开始服务',
  delivered: '交付作品',
  received: '确认接收',
  reviewed: '提交评价',
  delivery_submitted: '提交交付 V1',
  delivery_resubmitted: '重新交付新版本',
  revision_requested: '客户申请修改',
  revision_acknowledged: '摄影师确认返修排期',
  delivery_accepted: '客户确认验收',
  delivery_auto_accepted: '系统自动验收',
  review_submitted: '客户提交评价',
  cancelled: '取消订单',
  reschedule_requested: '申请改期',
  reschedule_accepted: '接受改期',
  reschedule_rejected: '拒绝改期',
  reschedule_withdrawn: '撤回改期',
  reschedule_countered: '反提改期时间',
  reschedule_expired: '改期申请失效',
  awaiting_payment: '等待客户支付',
  payment_succeeded: '支付成功并进入平台担保',
  payment_expired: '支付超时',
  refund_succeeded: '退款完成',
  settlement_succeeded: '平台完成结算',
  dispute_opened: '发起平台争议',
  dispute_evidence_added: '补充争议证据',
  dispute_assigned: '平台分配管理员',
  dispute_investigating: '平台开始审核',
  dispute_resolved: '平台完成仲裁',
  dispute_refund_succeeded: '仲裁退款完成',
}[item.event_type] || item.event_type)
const statusType = (status) => ({ pending: 'warning', awaiting_customer_payment: 'warning', confirmed: 'success', reschedule_requested: 'warning', in_progress: 'success', delivered: 'warning', received: 'success', reviewed: 'success', completed: 'success', cancelled: 'info' }[status] || '')
const statusLabel = (status) => ({ pending: '待确认', awaiting_customer_payment: '待支付', confirmed: '已确认', reschedule_requested: '改期待确认', in_progress: '拍摄中/待交付', delivered: '待验收', received: '已完成', reviewed: '已完成', completed: '已完成', cancelled: '已取消' }[status] || status)
const deliveryStatusType = (status) => ({ submitted: 'warning', accepted: 'success', revision_requested: 'warning', superseded: 'info' }[status] || '')
const deliveryStatusLabel = (status) => ({ submitted: '等待验收', accepted: '已验收', revision_requested: '已申请修改', superseded: '历史版本' }[status] || status)
const paymentPurposeLabel = (purpose) => ({ full: '全款', deposit: '定金', balance: '尾款' }[purpose] || purpose)
const paymentStatusText = (status) => ({ pending: '待支付', succeeded: '支付成功', failed: '支付失败', expired: '已超时', partially_refunded: '部分退款', refunded: '已退款' }[status] || status)

const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const formatCny = (value) => {
  if (value === null || value === undefined || value === '') return '金额待确认'
  const amount = Number(value)
  if (Number.isNaN(amount)) return '金额待确认'
  return `¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

const getFullUrl = (url) => {
  if (!url) return ''
  return url.startsWith('http') ? url : url
}

const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/profile?tab=orders')
  }
}

onMounted(fetchDetail)
</script>

<style scoped>
.order-detail-page {
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 20px 32px;
}

.order-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.order-content > .summary-panel { order: 0; }
.order-content > .detail-grid { order: 1; }
.order-content > .reschedule-panel,
.order-content > .rejection-panel { order: 2; }
.order-content > .timeline-panel { order: 3; }
.order-content > .contract-panel { order: 4; }
.order-content > .payment-panel { order: 5; }
.order-content > .delivery-history-panel { order: 6; }
.order-content > .dispute-panel { order: 7; }
.order-content > .event-panel { order: 8; }

.page-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.page-head h2 {
  margin: 0;
  font-size: var(--text-2xl);
  color: var(--color-ink);
}

.collapse-all-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.collapse-all-actions .el-button + .el-button {
  margin-left: 0;
}

.collapsible-card {
  position: relative;
}

.card-collapse-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  margin: -8px 0 8px;
}

.collapsible-card:not(.is-collapsed) > .card-collapse-bar {
  position: absolute;
  top: 8px;
  right: 14px;
  z-index: 2;
  margin: 0;
}

.card-collapse-bar strong {
  color: var(--color-ink);
  font-size: var(--text-base);
}

.card-collapse-bar .el-button {
  min-width: 44px;
  min-height: 44px;
  margin-left: auto;
}

.collapsible-card.is-collapsed {
  min-height: 58px;
  padding-top: 12px;
  padding-bottom: 12px;
}

.collapsible-card.is-collapsed > :not(.card-collapse-bar) {
  display: none !important;
}

.collapsible-card.is-collapsed > .card-collapse-bar {
  min-height: 32px;
  margin: 0;
}

.timeline-panel.collapsible-card > .card-collapse-bar,
.timeline-panel.collapsible-card:not(.is-collapsed) > .card-collapse-bar {
  position: static;
  inset: auto;
  grid-column: 1 / -1;
  order: -1;
  width: auto;
  margin: 0;
  padding: 4px 16px;
  border-bottom: 1px solid var(--color-divider);
  background: var(--color-paper-light);
}

.loading-wrap {
  padding: 32px 0;
}

:global(.el-main:has(.order-detail-page)) {
  min-height: auto;
}

.summary-panel,
.timeline-panel,
.action-panel,
.event-panel,
.reschedule-panel,
.rejection-panel,
.contract-panel,
.payment-panel {
  background: var(--color-paper-light);
  border: var(--border-default);
  border-radius: var(--radius-md);
}
.summary-panel,
.event-panel,
.reschedule-panel,
.rejection-panel,
.contract-panel,
.payment-panel {
  margin-bottom: 16px;
}

.order-content > .summary-panel,
.order-content > .event-panel,
.order-content > .reschedule-panel,
.order-content > .rejection-panel,
.order-content > .contract-panel,
.order-content > .payment-panel,
.order-content > .delivery-history-panel,
.order-content > .dispute-panel {
  margin-bottom: 0;
}

.summary-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 26px;
  margin-bottom: 0;
  border-left: 4px solid var(--color-brand);
}


.summary-main {
  flex: 1;
  min-width: 0;
}

.order-number {
  font-size: var(--text-sm);
  color: var(--color-ink-tertiary);
  margin-bottom: 4px;
}

.summary-panel h1 {
  margin: 0 0 8px;
  font-size: var(--text-xl);
  color: var(--color-ink);
  line-height: 1.25;
}

.summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  color: var(--color-ink-secondary);
  font-size: 14px;
}

.pending-time {
  color: var(--color-warning);
  font-weight: 600;
}

.order-notes {
  display: -webkit-box;
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: var(--color-paper);
  color: var(--color-ink-secondary);
  line-height: 1.45;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.order-note-sections {
  margin: 8px 0 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.note-section {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.note-section-label {
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--color-brand);
  margin-bottom: 4px;
}

.note-section-content {
  margin: 0;
  color: var(--color-ink);
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.summary-side {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 18px;
}

.counterpart-identity {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 150px;
}

.customer-avatar {
  flex-shrink: 0;
}

.customer-info {
  min-width: 0;
}

.customer-info span,
.customer-info strong {
  display: block;
}

.customer-info span {
  margin-bottom: 2px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.customer-info strong {
  max-width: 130px;
  overflow: hidden;
  color: var(--color-ink);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.summary-actions .el-button {
  width: 96px;
  margin-left: 0;
}

.contract-panel {
  padding: 20px 22px;
}

.contract-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 0;
  border-top: 1px solid var(--color-border-light);
  border-left: 1px solid var(--color-border-light);
}

.contract-item {
  min-width: 0;
  min-height: 76px;
  padding: 14px;
  border-right: 1px solid var(--color-border-light);
  border-bottom: 1px solid var(--color-border-light);
  border-radius: 0;
  background: transparent;
}

.contract-item span,
.contract-clause span {
  display: block;
  margin-bottom: 5px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.contract-item strong {
  color: var(--color-ink);
  font-size: 14px;
  line-height: 1.45;
  word-break: break-word;
}

.contract-item.price-item strong {
  color: var(--color-brand);
  font-size: 18px;
}

.contract-clause {
  margin-top: 10px;
  padding: 12px 14px;
  border-left: 3px solid var(--color-brand);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  background: var(--color-paper);
}

.contract-clause p {
  margin: 0;
  color: var(--color-ink-secondary);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
}

.payment-panel {
  padding: 20px 22px;
}

.payment-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--color-border-light);
}

.payment-summary-grid > div {
  padding: 14px 16px;
  border-right: 1px solid var(--color-border-light);
  border-radius: 0;
  background: transparent;
}

.payment-summary-grid > div:last-child {
  border-right: 0;
}

.payment-summary-grid span {
  display: block;
  margin-bottom: 5px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.payment-summary-grid strong {
  color: var(--color-brand);
  font-size: 17px;
}

.payment-deadline {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: #fff8e8;
  color: var(--color-warning);
  font-size: 14px;
}

.payment-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 14px;
}

.payment-actions span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.financial-records {
  margin-top: 14px;
  border-top: 1px solid var(--color-border-light);
}

.financial-record {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 2px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-ink-secondary);
  font-size: 14px;
}

.refund-record strong {
  color: var(--color-danger);
}

.settlement-record strong {
  color: var(--color-brand);
}

.dispute-panel {
  padding: 20px;
  margin-bottom: 16px;
  border-color: #e8c9c9;
  background: #fffafa;
}

.dispute-panel .section-head > div:first-child {
  display: grid;
  gap: 4px;
}

.dispute-panel > .el-button {
  min-height: 44px;
}

.dispute-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.dispute-summary-grid > div {
  padding: 12px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.dispute-summary-grid span,
.evidence-item span {
  display: block;
  color: var(--color-ink-tertiary);
  font-size: 13px;
}

.dispute-summary-grid strong {
  display: block;
  margin-top: 6px;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}

.dispute-description {
  margin: 0 0 14px;
  padding: 12px 14px;
  border-left: 3px solid var(--color-danger);
  background: var(--color-paper-light);
  color: var(--color-ink-secondary);
  line-height: 1.65;
  white-space: pre-wrap;
}

.resolution-result {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid #b9d8b6;
  border-radius: var(--radius-md);
  background: var(--color-brand-light);
}

.resolution-result strong {
  color: var(--color-ink);
}

.resolution-result span {
  color: var(--color-brand);
  font-weight: 700;
}

.resolution-result p {
  margin: 0;
  color: var(--color-ink-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.evidence-list {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.evidence-item {
  padding: 12px 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-paper);
}

.evidence-item > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.evidence-item p {
  margin: 8px 0;
  color: var(--color-ink-secondary);
  line-height: 1.55;
  white-space: pre-wrap;
}

.evidence-item a {
  color: var(--color-brand);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.evidence-reference {
  margin-top: 8px;
}

.dispute-form {
  margin-top: 16px;
}

.rejection-panel {
  padding: 16px 20px;
  margin-bottom: 16px;
  border-color: #f3d4d4;
  background: #fffafa;
}

.rejection-reason {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-ink);
  line-height: var(--leading-normal);
  white-space: pre-wrap;
  word-break: break-word;
}

.rejection-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.reschedule-panel {
  padding: 16px 20px;
  margin-bottom: 16px;
  border-color: #f1d9a7;
  background: #fffaf0;
}

.change-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.change-grid div {
  padding: 9px 12px;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.change-grid span {
  display: block;
  margin-bottom: 6px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.change-grid strong {
  color: var(--color-ink);
  font-size: 15px;
}

.change-reason {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-ink-secondary);
  line-height: var(--leading-normal);
  white-space: pre-wrap;
  word-break: break-word;
}

.timeline-panel {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  overflow: hidden;
  margin-bottom: 0;
}

.timeline-step {
  min-width: 0;
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  align-items: flex-start;
  gap: 8px;
  padding: 18px 10px;
  border-right: 1px solid var(--color-border-light);
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-paper);
}

.timeline-step:last-child {
  border-right: none;
}

.timeline-step:nth-child(4n) {
  border-right: none;
}

.timeline-step.done {
  background: var(--color-brand-light);
}

.timeline-step.current {
  background: var(--color-paper-light);
}

.timeline-step.disabled {
  background: var(--color-paper);
  opacity: 0.75;
}

.step-marker {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
  background: var(--color-border);
  color: var(--color-ink-secondary);
  font-size: var(--text-sm);
  font-weight: 700;
  flex-shrink: 0;
}

.done .step-marker {
  background: var(--color-brand);
  color: #fff;
}

.current .step-marker {
  background: var(--color-brand);
  color: #fff;
}

.step-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--color-ink);
  line-height: 1.3;
  margin-bottom: 4px;
}

.step-owner,
.step-time {
  color: var(--color-ink-tertiary);
  font-size: 11px;
  line-height: 1.4;
}

.step-body p {
  display: block;
  color: var(--color-ink-secondary);
  font-size: var(--text-xs);
  line-height: var(--leading-normal);
  margin: 6px 0 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.action-panel {
  padding: 22px 24px;
  border-color: var(--color-brand);
  background: var(--color-brand-light);
}

.action-panel .section-head {
  border-bottom-color: rgba(45, 90, 39, 0.2);
}

.action-panel .section-head h3::before {
  content: '待办';
  display: inline-block;
  margin-right: 9px;
  padding: 3px 7px;
  border-radius: var(--radius-sm);
  background: var(--color-brand);
  color: #fff;
  font-size: var(--text-xs);
  vertical-align: 2px;
}

.event-panel {
  padding: 20px 24px;
  margin-top: 0;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 6px 12px;
  padding-right: 72px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-divider);
}

.section-head h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink);
}

.section-head span {
  color: var(--color-ink-tertiary);
  font-size: var(--text-sm);
}

.section-head > .el-tag {
  margin-left: auto;
}

.dispute-panel .section-head > div:first-child,
.delivery-history-panel .section-head > div:first-child {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.next-copy {
  color: var(--color-ink-secondary);
  line-height: 1.55;
  margin: 0 0 12px;
}

.action-deadline-card {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--color-brand-light);
  color: var(--color-ink-secondary);
}

.action-deadline-card strong {
  color: var(--color-brand);
}

.action-deadline-card small {
  width: 100%;
  color: var(--color-ink-tertiary);
}

.action-deadline-card.overdue {
  background: #fef0f0;
}

.action-deadline-card.overdue strong {
  color: var(--color-danger);
}

.event-meta {
  margin-top: 4px;
  color: var(--color-ink-tertiary);
  font-size: var(--text-xs);
}

.event-note {
  margin: 6px 0 0;
  color: var(--color-ink-secondary);
  line-height: var(--leading-normal);
  white-space: pre-wrap;
}

.reschedule-actions {
  margin-top: 12px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

.delivery-download-list {
  display: grid;
  gap: 12px;
  margin: 16px 0;
}

.delivery-download-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
}

.delivery-download-item > div {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.delivery-download-item strong {
  overflow-wrap: anywhere;
}

.delivery-download-item span {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.review-score {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.review-text-content {
  padding: 14px;
  background: var(--color-paper);
  border-radius: var(--radius-md);
  color: var(--color-ink);
  line-height: var(--leading-relaxed);
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

.delivery-history-panel {
  padding: 20px 22px;
  margin-bottom: 0;
  border: var(--border-default);
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
}

.delivery-history-panel .section-head > div:first-child {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.revision-quota {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 14px;
  margin: 14px 0;
  border-radius: var(--radius-md);
  background: var(--color-paper-light);
  color: var(--color-ink-secondary);
}

.revision-quota strong {
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}

.revision-pending {
  color: var(--color-warning, #9a6700);
}

.delivery-version-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.delivery-version-card {
  padding: 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  background: var(--color-paper);
}

.delivery-version-head,
.delivery-version-head > div,
.delivery-version-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.delivery-version-head > div {
  align-items: flex-start;
  flex-direction: column;
}

.delivery-version-head span,
.delivery-version-meta,
.revision-record > span {
  color: var(--color-ink-tertiary);
  font-size: 13px;
}

.revision-record > span {
  display: block;
  margin-top: 4px;
}

.revision-record .el-button {
  min-height: 44px;
  margin-top: 12px;
}

.delivery-version-card p,
.revision-record p {
  margin: 12px 0;
  color: var(--color-ink-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.delivery-version-card .el-button {
  min-height: 44px;
  margin-top: 12px;
}

.revision-records {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.revision-record {
  padding: 12px 14px;
  border-left: 3px solid var(--color-warning, #d69e2e);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  background: var(--color-paper-light);
}

.revision-record > div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.revision-form {
  margin-top: 16px;
}

@media (max-width: 920px) {
  .dispute-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .payment-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .contract-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .timeline-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .timeline-step {
    border-bottom: 1px solid var(--color-border-light);
  }

  .timeline-step:nth-child(2n) {
    border-right: none;
  }

  .payment-summary-grid > div:nth-child(2n) {
    border-right: 0;
  }

}

@media (max-width: 560px) {
  .page-head {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .collapse-all-actions {
    flex: 0 0 100%;
    justify-content: flex-end;
  }
  .dispute-summary-grid {
    grid-template-columns: 1fr;
  }
  .payment-summary-grid {
    grid-template-columns: 1fr;
  }

  .payment-summary-grid > div,
  .timeline-step {
    border-right: 0;
  }

  .payment-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .contract-grid {
    grid-template-columns: 1fr;
  }

  .summary-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-side {
    justify-content: space-between;
  }

  .customer-info strong {
    max-width: 170px;
  }

  .timeline-panel {
    grid-template-columns: 1fr;
  }

  .change-grid {
    grid-template-columns: 1fr;
  }
}
</style>
