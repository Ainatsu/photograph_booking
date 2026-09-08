<template>
  <ion-page>
    <DetailHeader title="订单详情" default-href="/orders">
      <template #action>
        <div class="header-actions">
          <button
            type="button"
            class="header-action pressable"
            aria-label="联系订单对方"
            :disabled="!chatTargetId"
            @click="goConversation"
          >
            <MessageCircle :size="20" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="header-action pressable"
            aria-label="刷新订单详情"
            :disabled="loading || Boolean(processing)"
            @click="loadDetail"
          >
            <RefreshCw :size="20" aria-hidden="true" />
          </button>
        </div>
      </template>
    </DetailHeader>

    <ion-content class="detail-content">
      <ion-refresher slot="fixed" @ion-refresh="refresh">
        <ion-refresher-content pulling-text="下拉刷新订单" refreshing-spinner="crescent" />
      </ion-refresher>

      <main class="detail-shell">
        <FeedSkeleton v-if="loading && !order" :count="5" />
        <StatePanel
          v-else-if="error && !order"
          tone="error"
          title="订单详情加载失败"
          :description="error"
          action-label="重新加载"
          @action="loadDetail"
        />

        <template v-else-if="order">
          <section class="status-hero">
            <div class="status-heading">
              <div>
                <small>订单 #{{ order.id }}</small>
                <h1>{{ getOrderTitle(order) }}</h1>
              </div>
              <span class="status-badge" :class="order.status">
                {{ getOrderStatusLabel(order.status) }}
              </span>
            </div>
            <p>{{ nextActionText }}</p>
            <div class="responsibility-line">
              <ShieldCheck :size="17" aria-hidden="true" />
              <span>{{ currentOwnerText }}</span>
            </div>
          </section>

          <ol class="progress-list" aria-label="订单进度">
            <li
              v-for="(step, index) in progressSteps"
              :key="step.key"
              :class="stepState(index)"
            >
              <span class="step-marker" aria-hidden="true">
                <Check v-if="stepState(index) === 'done'" :size="14" />
                <span v-else>{{ index + 1 }}</span>
              </span>
              <span>
                <strong>{{ step.label }}</strong>
                <small>{{ step.description }}</small>
              </span>
            </li>
          </ol>

          <section v-if="activeReschedule" class="notice-card reschedule-card">
            <div class="notice-heading card-heading" @click="toggleCard('reschedule')">
              <span><CalendarClock :size="20" aria-hidden="true" /></span>
              <div>
                <h2>待处理改期申请</h2>
                <p>{{ activeDispute ? '平台争议处理中，改期申请已暂停。' : canRespondReschedule ? '需要您处理，原预约时间继续有效。' : '等待对方处理，原预约时间继续有效。' }}</p>
              </div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('reschedule')"
                aria-controls="order-card-reschedule"
                aria-label="收起或展开改期申请"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('reschedule')" id="order-card-reschedule" class="card-body">
              <dl class="notice-facts">
                <div><dt>原预约日期</dt><dd>{{ formatDate(activeReschedule.original_appointment_time) }}</dd></div>
                <div><dt>候选日期</dt><dd>{{ formatDate(activeReschedule.requested_appointment_time) }}</dd></div>
                <div><dt>原因</dt><dd>{{ activeReschedule.reason }}</dd></div>
                <div><dt>响应期限</dt><dd>{{ formatDateTime(activeReschedule.expires_at) }}</dd></div>
              </dl>
              <div v-if="!activeDispute" class="inline-actions">
                <template v-if="canRespondReschedule">
                  <button type="button" class="primary pressable" :disabled="Boolean(processing)" @click="acceptRescheduleAction">
                    <ion-spinner v-if="processing === 'accept-reschedule'" name="crescent" />
                    <CheckCheck v-else :size="17" aria-hidden="true" />
                    接受
                  </button>
                  <button type="button" class="secondary pressable" :disabled="Boolean(processing)" @click="openForm('counter')">
                    <CalendarClock :size="17" aria-hidden="true" />
                    反提时间
                  </button>
                  <button type="button" class="danger pressable" :disabled="Boolean(processing)" @click="rejectRescheduleAction">
                    <Ban :size="17" aria-hidden="true" />
                    拒绝
                  </button>
                </template>
                <button v-else type="button" class="secondary pressable" :disabled="Boolean(processing)" @click="withdrawRescheduleAction">
                  <RotateCcw :size="17" aria-hidden="true" />
                  撤回申请
                </button>
              </div>
            </div>
          </section>

          <section v-if="order.status === 'cancelled'" class="notice-card cancellation-card">
            <div class="notice-heading card-heading" @click="toggleCard('cancellation')">
              <span><CircleAlert :size="20" aria-hidden="true" /></span>
              <div>
                <h2>{{ order.cancelled_by === 'photographer' && order.rejection_reason ? '预约未通过' : '订单已取消' }}</h2>
                <p>{{ actorRoleLabel(order.cancelled_by) || '订单参与方' }}已填写原因</p>
              </div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('cancellation')"
                aria-controls="order-card-cancellation"
                aria-label="收起或展开取消原因"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('cancellation')" id="order-card-cancellation" class="card-body">
              <p class="reason-copy">{{ order.cancellation_reason || order.rejection_reason || '未记录具体原因。' }}</p>
            </div>
          </section>

          <section v-if="latestDispute" class="notice-card dispute-card">
            <div class="notice-heading card-heading" @click="toggleCard('dispute')">
              <span><Scale :size="20" aria-hidden="true" /></span>
              <div>
                <h2>{{ activeDispute ? '平台争议处理中' : '平台争议处理结果' }}</h2>
                <p>{{ activeDispute ? '争议期间已暂停自动验收和资金结算。' : '仲裁结果、退款和订单状态均已记录。' }}</p>
              </div>
              <em>{{ disputeStatusLabel(latestDispute.status) }}</em>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('dispute')"
                aria-controls="order-card-dispute"
                aria-label="收起或展开争议信息"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('dispute')" id="order-card-dispute" class="card-body">
              <dl class="notice-facts">
                <div><dt>争议编号</dt><dd>{{ latestDispute.dispute_no }}</dd></div>
                <div><dt>发起方</dt><dd>{{ actorRoleLabel(latestDispute.opened_by_role) }}</dd></div>
                <div><dt>争议类型</dt><dd>{{ disputeReasonLabel(latestDispute.reason_code) }}</dd></div>
                <div><dt>处理诉求</dt><dd>{{ disputeResolutionLabel(latestDispute.requested_resolution) }}</dd></div>
                <div><dt>平台处理人</dt><dd>{{ latestDispute.assigned_admin_name || '等待平台分配' }}</dd></div>
                <div><dt>提交时间</dt><dd>{{ formatDateTime(latestDispute.created_at) }}</dd></div>
              </dl>
              <p class="reason-copy">{{ latestDispute.description }}</p>
              <div v-if="latestDispute.status === 'resolved'" class="resolution-result">
                <strong>平台仲裁：{{ disputeResolutionLabel(latestDispute.resolution) }}</strong>
                <span v-if="Number(latestDispute.refund_amount || 0) > 0">退款 {{ formatCurrency(Number(latestDispute.refund_amount)) }}</span>
                <p>{{ latestDispute.resolution_note || '平台已完成处理。' }}</p>
              </div>
              <div v-if="latestDispute.evidence?.length" class="evidence-list">
                <article v-for="evidence in latestDispute.evidence" :key="evidence.id">
                  <header>
                    <strong>{{ evidence.submitter_name || actorRoleLabel(evidence.submitter_role) }}</strong>
                    <small>{{ formatDateTime(evidence.created_at) }}</small>
                  </header>
                  <p v-if="evidence.description">{{ evidence.description }}</p>
                  <a
                    v-if="evidence.file_url"
                    class="evidence-file pressable"
                    :href="resolveMediaUrl(evidence.file_url)"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Paperclip :size="17" aria-hidden="true" />
                    <span>{{ evidence.file_name || '查看证据附件' }}</span>
                    <small>{{ formatFileSize(evidence.file_size) }}</small>
                  </a>
                </article>
              </div>
              <div v-if="activeDispute" class="inline-actions">
                <button type="button" class="secondary pressable" :disabled="Boolean(processing)" @click="openForm('evidence')">
                  <Paperclip :size="17" aria-hidden="true" />补充证据
                </button>
              </div>
            </div>
          </section>

          <section class="summary-card">
            <div class="counterparty-row card-heading" @click="toggleCard('summary')">
              <AvatarImage :src="counterpartAvatar" :name="counterpartName" :size="52" />
              <div>
                <small>{{ counterpartRole }}</small>
                <strong>{{ counterpartName }}</strong>
              </div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('summary')"
                aria-controls="order-card-summary"
                aria-label="收起或展开订单概览"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('summary')" id="order-card-summary" class="card-body">
              <div class="facts-grid">
                <div><CalendarDays :size="18" /><span>预约日期</span><strong>{{ formatDate(order.appointment_time) }}</strong></div>
                <div><Clock3 :size="18" /><span>服务时长</span><strong>{{ formatDuration(order.duration_minutes) }}</strong></div>
                <div><MapPin :size="18" /><span>服务地点</span><strong>{{ order.service_location || '地点待确认' }}</strong></div>
                <div><WalletCards :size="18" /><span>订单金额</span><strong>{{ orderAmount }}</strong></div>
              </div>
              <div class="payment-row">
                <span>{{ paymentStatusLabel }}</span>
                <small v-if="order.payment_due_at">支付期限 {{ formatDateTime(order.payment_due_at) }}</small>
              </div>
            </div>
          </section>

          <section v-if="order.final_price !== null && order.final_price !== undefined" class="content-card payment-card">
            <div class="section-heading card-heading" @click="toggleCard('payment')">
              <div><h2>支付与平台担保</h2><p>{{ paymentStatusLabel }}</p></div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('payment')"
                aria-controls="order-card-payment"
                aria-label="收起或展开支付信息"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('payment')" id="order-card-payment" class="card-body">
              <div class="payment-summary-grid">
                <div><CreditCard :size="18" aria-hidden="true" /><span>订单金额</span><strong>{{ formatCurrency(Number(order.final_price)) }}</strong></div>
                <div><ShieldCheck :size="18" aria-hidden="true" /><span>担保中</span><strong>{{ formatCurrency(Number(order.escrow_amount || 0)) }}</strong></div>
                <div><Ban :size="18" aria-hidden="true" /><span>已退款</span><strong class="refund-amount">{{ formatCurrency(Number(order.refunded_amount || 0)) }}</strong></div>
                <div><Banknote :size="18" aria-hidden="true" /><span>已结算</span><strong class="settle-amount">{{ formatCurrency(Number(order.settled_amount || 0)) }}</strong></div>
              </div>
              <p v-if="order.status === 'awaiting_customer_payment' && order.payment_due_at" class="deadline-note">
                <TimerReset :size="17" aria-hidden="true" />
                请在 {{ formatDateTime(order.payment_due_at) }} 前完成支付，超时后订单将自动关闭并释放档期。
              </p>
              <div v-if="canPay" class="payment-action-row">
                <button type="button" class="primary pressable" :disabled="Boolean(processing)" @click="runAction('pay')">
                  <CreditCard :size="17" aria-hidden="true" />
                  支付{{ order.payment_status === 'deposit_paid' ? '尾款' : '' }}
                </button>
                <span>支付成功后资金先由平台担保，客户验收后再结算给摄影师。</span>
              </div>
              <div v-if="financialSummary?.payments?.length" class="financial-records">
                <div v-for="payment in financialSummary.payments" :key="payment.id" class="financial-record">
                  <span><Receipt :size="15" aria-hidden="true" />{{ paymentPurposeLabel(payment.purpose) }} · {{ paymentStatusText(payment.status) }}</span>
                  <strong>{{ formatCurrency(Number(payment.amount)) }}</strong>
                </div>
                <div v-for="refund in financialSummary.refunds || []" :key="`refund-${refund.id}`" class="financial-record refund-record">
                  <span><Ban :size="15" aria-hidden="true" />退款 · {{ refund.reason || refund.reason_code || '平台退款' }}</span>
                  <strong>-{{ formatCurrency(Number(refund.amount)) }}</strong>
                </div>
                <div v-if="financialSummary.settlement" class="financial-record settlement-record">
                  <span><Banknote :size="15" aria-hidden="true" />摄影师结算（已扣平台服务费）</span>
                  <strong>{{ formatCurrency(Number(financialSummary.settlement.net_amount)) }}</strong>
                </div>
              </div>
            </div>
          </section>

          <section v-if="canRequestReschedule || canCancel || canOpenDispute" class="management-card">
            <div class="section-heading card-heading" @click="toggleCard('management')">
              <div><h2>订单管理</h2><p>改期期间原档期保留；取消订单必须向对方说明原因。</p></div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('management')"
                aria-controls="order-card-management"
                aria-label="收起或展开订单管理"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('management')" id="order-card-management" class="card-body">
              <div class="management-actions">
                <button v-if="canRequestReschedule" type="button" class="secondary pressable" :disabled="Boolean(processing)" @click="openForm('reschedule')">
                  <CalendarClock :size="18" aria-hidden="true" />申请改期
                </button>
                <button v-if="canCancel" type="button" class="danger pressable" :disabled="Boolean(processing)" @click="cancelOrderAction">
                  <Ban :size="18" aria-hidden="true" />取消订单
                </button>
                <button v-if="canOpenDispute" type="button" class="danger pressable" :disabled="Boolean(processing)" @click="openForm('dispute')">
                  <Scale :size="18" aria-hidden="true" />发起平台争议
                </button>
              </div>
            </div>
          </section>

          <section class="content-card">
            <div class="section-heading card-heading" @click="toggleCard('contract')">
              <div><h2>服务约定</h2><p>以创建订单时保存的合同快照为准</p></div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('contract')"
                aria-controls="order-card-contract"
                aria-label="收起或展开服务约定"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('contract')" id="order-card-contract" class="card-body">
              <dl class="contract-list">
                <div><dt>方案</dt><dd>{{ order.package_name || order.package_snapshot }}</dd></div>
                <div v-if="order.delivery_due_at"><dt>预计交付</dt><dd>{{ formatDateTime(order.delivery_due_at) }}</dd></div>
                <div v-if="order.delivery_formats?.length"><dt>交付格式</dt><dd>{{ order.delivery_formats.join('、') }}</dd></div>
                <div v-if="order.retouched_image_count"><dt>精修数量</dt><dd>{{ order.retouched_image_count }} 张</dd></div>
                <div v-if="order.included_revision_count !== null && order.included_revision_count !== undefined">
                  <dt>免费修改</dt><dd>{{ order.revision_used_count || 0 }} / {{ order.included_revision_count }} 次</dd>
                </div>
                <div><dt>商业授权</dt><dd>{{ order.commercial_license ? '包含' : '不包含或未约定' }}</dd></div>
              </dl>
              <div v-if="order.notes" class="long-copy">
                <strong>客户备注</strong>
                <p>{{ order.notes }}</p>
              </div>
              <div v-if="cancellationPolicyText" class="long-copy">
                <strong>取消规则</strong>
                <p>{{ cancellationPolicyText }}</p>
              </div>
              <div v-if="reschedulePolicyText" class="long-copy">
                <strong>改期规则</strong>
                <p>{{ reschedulePolicyText }}</p>
              </div>
              <div v-if="order.copyright_terms" class="long-copy">
                <strong>版权约定</strong>
                <p>{{ order.copyright_terms }}</p>
              </div>
            </div>
          </section>

          <section class="content-card">
            <div class="section-heading card-heading" @click="toggleCard('delivery')">
              <div><h2>交付与验收</h2><p>{{ deliveries.length ? `共 ${deliveries.length} 个版本` : '摄影师交付后会显示在这里' }}</p></div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('delivery')"
                aria-controls="order-card-delivery"
                aria-label="收起或展开交付与验收"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>

            <div v-show="!isCardCollapsed('delivery')" id="order-card-delivery" class="card-body">
              <div v-if="deliveries.length" class="delivery-list">
                <article v-for="delivery in deliveries" :key="delivery.id" class="delivery-card">
                  <header>
                    <div><strong>交付 V{{ delivery.version }}</strong><small>{{ formatDateTime(delivery.created_at) }}</small></div>
                    <span>{{ deliveryStatusLabel(delivery.status) }}</span>
                  </header>
                  <p v-if="delivery.description">{{ delivery.description }}</p>
                  <div class="delivery-files">
                    <div v-for="file in delivery.files" :key="file.id" class="delivery-file">
                      <img v-if="isImageFile(file)" :src="resolveMediaUrl(file.file_url)" :alt="file.file_name" loading="lazy" />
                      <span v-else class="file-placeholder"><FileArchive :size="23" aria-hidden="true" /></span>
                      <span class="file-copy"><strong>{{ file.file_name }}</strong><small>{{ formatFileSize(file.file_size) }}</small></span>
                      <button type="button" class="download-button pressable" :aria-label="`下载 ${file.file_name}`" :disabled="downloadingFileId === file.id" @click="downloadFile(delivery, file)">
                        <ion-spinner v-if="downloadingFileId === file.id" name="crescent" />
                        <Download v-else :size="18" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                </article>
              </div>
              <div v-else-if="legacyDeliveryImages.length" class="legacy-images">
                <img v-for="url in legacyDeliveryImages" :key="url" :src="resolveMediaUrl(url)" alt="订单交付作品" loading="lazy" />
              </div>
              <p v-else class="empty-copy">当前还没有交付版本。</p>

              <p v-if="order.acceptance_deadline_at" class="deadline-note">
                <TimerReset :size="17" aria-hidden="true" />
                请在 {{ formatDateTime(order.acceptance_deadline_at) }} 前处理，逾期可能自动验收。
              </p>
            </div>
          </section>

          <section v-if="revisionRequests.length" class="content-card">
            <div class="section-heading card-heading" @click="toggleCard('revision')">
              <div><h2>修改记录</h2><p>每次申请和重新交付都会保留记录</p></div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('revision')"
                aria-controls="order-card-revision"
                aria-label="收起或展开修改记录"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('revision')" id="order-card-revision" class="card-body">
              <div class="revision-list">
                <article v-for="revision in revisionRequests" :key="revision.id">
                  <header><strong>第 {{ revision.sequence }} 次修改</strong><span>{{ revisionStatusLabel(revision.status) }}</span></header>
                  <p>{{ revision.instructions }}</p>
                  <small>提交于 {{ formatDateTime(revision.created_at) }}</small>
                  <small v-if="revision.expected_redelivery_at">预计重新交付 {{ formatDateTime(revision.expected_redelivery_at) }}</small>
                </article>
              </div>
            </div>
          </section>

          <section v-if="order.rating" class="content-card review-card">
            <div class="review-score"><Star :size="21" aria-hidden="true" /><strong>{{ order.rating }} / 10</strong></div>
            <div><h2>客户评价</h2><p>{{ order.review_text || '客户已完成评分。' }}</p></div>
          </section>

          <section class="content-card">
            <div class="section-heading card-heading" @click="toggleCard('history')">
              <div><h2>订单记录</h2><p>关键操作均以服务端时间为准</p></div>
              <button
                type="button"
                class="card-toggle pressable"
                :aria-expanded="!isCardCollapsed('history')"
                aria-controls="order-card-history"
                aria-label="收起或展开订单记录"
              >
                <ChevronDown :size="19" aria-hidden="true" />
              </button>
            </div>
            <div v-show="!isCardCollapsed('history')" id="order-card-history" class="card-body">
              <ol class="timeline-list">
                <li v-for="event in history" :key="event.id || `${event.event_type}-${event.created_at}`">
                  <span class="timeline-dot" aria-hidden="true" />
                  <div>
                    <strong>{{ eventTitle(event.event_type) }}</strong>
                    <small>{{ event.actor_name || actorRoleLabel(event.actor_role) || '系统' }} · {{ formatDateTime(event.created_at) }}</small>
                    <p v-if="event.note">{{ event.note }}</p>
                  </div>
                </li>
              </ol>
            </div>
          </section>
        </template>
      </main>

      <ion-toast
        :is-open="Boolean(toastMessage)"
        :message="toastMessage"
        :duration="3000"
        position="bottom"
        @did-dismiss="toastMessage = ''"
      />
    </ion-content>

    <DetailActionBar
      v-if="order && primaryAction"
      :primary-label="primaryAction.label"
      :secondary-label="secondaryAction?.label"
      :primary-disabled="Boolean(processing)"
      :secondary-disabled="Boolean(processing)"
      :primary-loading="processing === primaryAction.id"
      :secondary-loading="processing === secondaryAction?.id"
      @primary="runAction(primaryAction.id)"
      @secondary="runSecondaryAction"
    >
      <template #primary-icon><component :is="primaryAction.icon" :size="18" aria-hidden="true" /></template>
      <template #secondary-icon><component v-if="secondaryAction" :is="secondaryAction.icon" :size="18" aria-hidden="true" /></template>
    </DetailActionBar>

    <ion-modal
      :is-open="Boolean(activeForm)"
      :can-dismiss="!formSubmitting"
      @did-dismiss="closeForm"
    >
      <ion-header>
        <ion-toolbar>
          <ion-title>{{ formTitle }}</ion-title>
          <ion-buttons slot="end">
            <ion-button :disabled="formSubmitting" @click="closeForm">关闭</ion-button>
          </ion-buttons>
        </ion-toolbar>
      </ion-header>
      <ion-content class="modal-content">
        <form class="form-shell" @submit.prevent="submitActiveForm">
          <template v-if="activeForm === 'reschedule' || activeForm === 'counter'">
            <label for="reschedule-date">新的预约日期 <span>必填</span></label>
            <input id="reschedule-date" v-model="formDateTime" type="date" required />
            <p class="field-hint">原预约日期为 {{ formatDate(order?.appointment_time) }}，提交后仍需对方接受。</p>
            <label for="reschedule-reason">改期原因 <span>必填</span></label>
            <textarea id="reschedule-reason" v-model.trim="formText" rows="5" maxlength="500" placeholder="说明行程变化及希望调整的原因" required />
            <span class="character-count">{{ formText.length }}/500</span>
          </template>

          <template v-else-if="activeForm === 'delivery'">
            <label for="delivery-files">交付文件 <span>必填</span></label>
            <input id="delivery-files" :key="fileInputKey" type="file" multiple accept=".jpg,.jpeg,.png,.webp,.avif,.heic,.heif,.tif,.tiff,.zip,.rar,.7z,.psd" @change="selectFiles" />
            <p class="field-hint">支持常见图片、PSD 和压缩包；请确认文件已完成导出。</p>
            <SelectedFileList :files="formFiles" @remove="removeFile" />
            <label for="delivery-description">交付说明 <span>选填</span></label>
            <textarea id="delivery-description" v-model.trim="formText" rows="4" maxlength="500" placeholder="例如：本次交付精修 30 张，压缩包内含原尺寸文件" />
          </template>

          <template v-else-if="activeForm === 'revision'">
            <label for="revision-instructions">修改说明 <span>必填</span></label>
            <textarea id="revision-instructions" v-model.trim="formText" rows="6" maxlength="1000" placeholder="请按图片和问题逐项说明，希望如何调整" required />
            <span class="character-count">{{ formText.length }}/1000</span>
            <label for="revision-files">参考图片 <span>选填</span></label>
            <input id="revision-files" :key="fileInputKey" type="file" multiple accept="image/jpeg,image/png,image/webp" @change="selectFiles" />
            <SelectedFileList :files="formFiles" @remove="removeFile" />
            <p class="field-hint">本次将使用第 {{ (order?.revision_used_count || 0) + 1 }} / {{ order?.included_revision_count || 0 }} 次免费修改。</p>
          </template>

          <template v-else-if="activeForm === 'revision-schedule'">
            <label for="revision-schedule">预计重新交付时间 <span>必填</span></label>
            <input id="revision-schedule" v-model="formDateTime" type="datetime-local" :min="minimumDateTime" required />
            <p class="field-hint">客户会在订单详情中看到该时间，请预留真实可执行的修图周期。</p>
          </template>

          <template v-else-if="activeForm === 'dispute'">
            <div class="form-warning" role="note">
              <CircleAlert :size="19" aria-hidden="true" />
              <p>提交后平台会暂停自动验收和资金结算。请先尝试沟通，并如实提交可核验材料。</p>
            </div>
            <label for="dispute-reason">争议类型 <span>必填</span></label>
            <select id="dispute-reason" v-model="formReasonCode" required>
              <option value="" disabled>请选择争议类型</option>
              <option value="quality_issue">交付质量或内容不符</option>
              <option value="delivery_delay">未按约定时间履约</option>
              <option value="service_failure">服务无法继续</option>
              <option value="cooperation_issue">对方配合问题</option>
              <option value="other">其他争议</option>
            </select>
            <label for="dispute-resolution">希望平台如何处理 <span>必填</span></label>
            <select id="dispute-resolution" v-model="formRequestedResolution" required>
              <option value="" disabled>请选择处理诉求</option>
              <option value="continue_fulfillment">协调后继续履约</option>
              <option value="partial_refund">部分退款</option>
              <option value="full_refund">全额退款并终止订单</option>
              <option value="other">其他处理</option>
            </select>
            <label for="dispute-description">事实说明 <span>必填</span></label>
            <textarea id="dispute-description" v-model.trim="formText" rows="7" maxlength="2000" placeholder="请按时间顺序说明发生了什么、已沟通情况，以及希望平台核查的关键事实" required />
            <span class="character-count">{{ formText.length }}/2000</span>
            <label for="dispute-files">初始证据 <span>选填</span></label>
            <input id="dispute-files" :key="fileInputKey" type="file" multiple accept="image/jpeg,image/png,image/webp" @change="selectFiles" />
            <p class="field-hint">可上传聊天截图、交付对比和合同约定截图。</p>
            <SelectedFileList :files="formFiles" @remove="removeFile" />
          </template>

          <template v-else-if="activeForm === 'evidence'">
            <label for="evidence-description">证据说明 <span>填写说明或上传附件</span></label>
            <textarea id="evidence-description" v-model.trim="formText" rows="5" maxlength="1000" placeholder="说明该材料能够证明什么，以及对应的时间或约定" />
            <span class="character-count">{{ formText.length }}/1000</span>
            <label for="evidence-files">证据附件 <span>选填</span></label>
            <input id="evidence-files" :key="fileInputKey" type="file" multiple accept="image/jpeg,image/png,image/webp" @change="selectFiles" />
            <SelectedFileList :files="formFiles" @remove="removeFile" />
          </template>

          <template v-else-if="activeForm === 'review'">
            <fieldset class="rating-fieldset">
              <legend>服务评分 <span>必填</span></legend>
              <div class="rating-grid" role="radiogroup" aria-label="订单评分">
                <button
                  v-for="score in 10"
                  :key="score"
                  type="button"
                  class="rating-button pressable"
                  :class="{ selected: formRating === score }"
                  role="radio"
                  :aria-checked="formRating === score"
                  @click="formRating = score"
                >
                  {{ score }}
                </button>
              </div>
            </fieldset>
            <label for="review-text">评价内容 <span>选填</span></label>
            <textarea id="review-text" v-model.trim="formText" rows="5" maxlength="1000" placeholder="分享摄影师的沟通、拍摄和交付体验" />
          </template>

          <div v-if="formError" class="form-error" role="alert">
            <CircleAlert :size="18" aria-hidden="true" />{{ formError }}
          </div>

          <button type="submit" class="submit-button pressable" :class="{ danger: activeForm === 'dispute' }" :disabled="formSubmitting">
            <ion-spinner v-if="formSubmitting" name="crescent" aria-hidden="true" />
            {{ formSubmitting ? '提交中…' : formSubmitLabel }}
          </button>
        </form>
      </ion-content>
    </ion-modal>
  </ion-page>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonModal,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonTitle,
  IonToast,
  IonToolbar,
  alertController,
  type RefresherCustomEvent,
} from '@ionic/vue'
import {
  ArrowDownUp,
  BadgeCheck,
  Ban,
  Banknote,
  CalendarClock,
  CalendarDays,
  Camera,
  Check,
  CheckCheck,
  ChevronDown,
  CircleAlert,
  Clock3,
  CreditCard,
  Download,
  FileArchive,
  MapPin,
  MessageCircle,
  Paperclip,
  Receipt,
  RefreshCw,
  RotateCcw,
  Scale,
  ShieldCheck,
  Star,
  TimerReset,
  Upload,
  WalletCards,
} from 'lucide-vue-next'
import AvatarImage from '@/components/AvatarImage.vue'
import DetailActionBar from '@/components/DetailActionBar.vue'
import DetailHeader from '@/components/DetailHeader.vue'
import FeedSkeleton from '@/components/FeedSkeleton.vue'
import SelectedFileList from '@/components/SelectedFileList.vue'
import StatePanel from '@/components/StatePanel.vue'
import { getApiErrorMessage } from '@/api/client'
import {
  acceptOrder,
  acceptOrderReschedule,
  acknowledgeOrderRevision,
  addOrderDisputeEvidence,
  cancelOrder,
  confirmMockPayment,
  confirmOrder,
  counterOrderReschedule,
  createOrderPayment,
  deliverOrderWorks,
  downloadOrderDeliveryFile,
  getOrderDetail,
  getOrderFinancialSummary,
  openOrderDispute,
  rejectOrder,
  rejectOrderReschedule,
  requestOrderReschedule,
  requestOrderRevision,
  reviewOrder,
  startOrder,
  withdrawOrderReschedule,
} from '@/api/orders'
import { useAuthStore } from '@/stores/auth'
import type {
  FinancialSummary,
  OrderDelivery,
  OrderDeliveryFile,
  OrderDispute,
  OrderHistoryItem,
  OrderItem,
  OrderRevisionRequest,
} from '@/types/orders'
import { formatCurrency, formatDuration } from '@/utils/format'
import {
  canAcceptOrderDelivery,
  canStartOrderService,
  getOrderProgressIndex,
  getOrderStatusLabel,
  getOrderTitle,
  hasAvailableOrderRevision,
  isOrderScheduleManageable,
} from '@/utils/order'
import { resolveMediaUrl } from '@/utils/media'
import { trackEvent, AnalyticsEvent } from '@/utils/analytics'

type ActionId = 'confirm' | 'reject' | 'pay' | 'start' | 'deliver' | 'accept' | 'revision' | 'review' | 'revision-schedule'
type FormMode = 'reschedule' | 'counter' | 'delivery' | 'revision' | 'revision-schedule' | 'dispute' | 'evidence' | 'review'
type CardKey =
  | 'reschedule'
  | 'cancellation'
  | 'dispute'
  | 'summary'
  | 'payment'
  | 'management'
  | 'contract'
  | 'delivery'
  | 'revision'
  | 'history'

interface ActionDefinition {
  id: ActionId
  label: string
  icon: Component
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const order = ref<OrderItem | null>(null)
const history = ref<OrderHistoryItem[]>([])
const deliveries = ref<OrderDelivery[]>([])
const revisionRequests = ref<OrderRevisionRequest[]>([])
const disputes = ref<OrderDispute[]>([])
const financialSummary = ref<FinancialSummary | null>(null)
const loading = ref(true)
const error = ref('')
const toastMessage = ref('')
const processing = ref('')
const downloadingFileId = ref<number | null>(null)
const activeForm = ref<FormMode | null>(null)
const formDateTime = ref('')
const formText = ref('')
const formRating = ref(0)
const formFiles = ref<File[]>([])
const formReasonCode = ref('')
const formRequestedResolution = ref('')
const formError = ref('')
const formIdempotencyKey = ref('')
const fileInputKey = ref(0)
const collapsedCards = ref<Partial<Record<CardKey, boolean>>>({})
let detailRequestId = 0

const orderId = computed(() => Number(route.params.orderId))
const userId = computed(() => Number(auth.user?.id || 0))
const isCustomer = computed(() => order.value?.customer_id === userId.value)
const isPhotographer = computed(() => order.value?.photographer_id === userId.value)
const activeReschedule = computed(() => order.value?.active_reschedule_request || null)
const activeRevision = computed(() => revisionRequests.value.find((item) => item.status === 'requested') || null)
const latestDispute = computed(() => disputes.value[0] || null)
const activeDispute = computed(() => disputes.value.find((item) => ['open', 'assigned', 'investigating'].includes(item.status)) || null)
const chatTargetId = computed(() => {
  if (!order.value) return 0
  return isCustomer.value ? order.value.photographer_id : order.value.customer_id
})
const counterpartName = computed(() => isCustomer.value
  ? order.value?.photographer_name || `摄影师 #${order.value?.photographer_id || ''}`
  : order.value?.customer_name || `客户 #${order.value?.customer_id || ''}`)
const counterpartAvatar = computed(() => isCustomer.value ? order.value?.photographer_avatar_url : order.value?.customer_avatar_url)
const counterpartRole = computed(() => isCustomer.value ? '摄影师' : '客户')
const orderAmount = computed(() => {
  const amount = Number(order.value?.final_price ?? order.value?.package_price)
  return Number.isFinite(amount) && amount > 0 ? formatCurrency(amount) : '金额待确认'
})
const legacyDeliveryImages = computed(() => order.value?.delivery?.images || [])
const canPay = computed(() => !activeDispute.value && isCustomer.value && (
  order.value?.status === 'awaiting_customer_payment'
  || (order.value?.status === 'confirmed' && order.value?.payment_status === 'deposit_paid')
))
const canStart = computed(() => Boolean(
  !activeDispute.value && isPhotographer.value && order.value && canStartOrderService(order.value),
))
const canDeliver = computed(() => {
  const currentOrder = order.value
  return Boolean(!activeDispute.value && isPhotographer.value && currentOrder && (
    currentOrder.status === 'in_progress'
    || (currentOrder.status === 'delivered' && currentOrder.after_sales_status === 'revision_requested')
  ))
})
const canAccept = computed(() => Boolean(
  isCustomer.value && order.value && canAcceptOrderDelivery(order.value),
))
const canRequestRevision = computed(() => Boolean(
  canAccept.value && order.value && hasAvailableOrderRevision(order.value),
))
const canReview = computed(() => isCustomer.value
  && ['received', 'completed'].includes(order.value?.status || '')
  && order.value?.rating == null)
const canRequestReschedule = computed(() => Boolean(
  (isCustomer.value || isPhotographer.value)
  && order.value
  && isOrderScheduleManageable(order.value)
  && !activeReschedule.value
  && !activeDispute.value,
))
const canRespondReschedule = computed(() => Boolean(activeReschedule.value)
  && activeReschedule.value?.requested_by !== userId.value)
const canCancel = computed(() => Boolean(
  (isCustomer.value || isPhotographer.value)
  && order.value
  && isOrderScheduleManageable(order.value)
  && !activeDispute.value,
))
const canOpenDispute = computed(() => Boolean(
  (isCustomer.value || isPhotographer.value)
  && order.value
  && ['confirmed', 'in_progress', 'delivered'].includes(order.value.status)
  && !activeDispute.value,
))
const paymentStatusLabel = computed(() => ({
  unpaid: '待支付',
  deposit_paid: '定金已进入平台担保',
  paid_in_escrow: '全款已进入平台担保',
  partially_refunded: '已部分退款',
  refunded: '已退款',
  settled: '已完成结算',
  payment_failed: '支付失败或已超时',
}[order.value?.payment_status || 'unpaid'] || order.value?.payment_status || '待支付'))
const cancellationPolicyText = computed(() => formatPolicy(order.value?.cancellation_policy_snapshot))
const reschedulePolicyText = computed(() => formatPolicy(order.value?.reschedule_policy_snapshot))
const minimumDateTime = computed(() => toLocalDateTimeInput(new Date(Date.now() + 60 * 60 * 1000)))
const formSubmitting = computed(() => processing.value === 'form')

const progressSteps = [
  { key: 'pending', label: '待确认', description: '摄影师确认预约' },
  { key: 'payment', label: '待支付', description: '客户锁定档期' },
  { key: 'confirmed', label: '已确认', description: '双方准备拍摄' },
  { key: 'service', label: '履约中', description: '拍摄与处理作品' },
  { key: 'delivery', label: '待验收', description: '查看交付或申请修改' },
  { key: 'completed', label: '已完成', description: '验收、结算与评价' },
]

const currentStepIndex = computed(() => getOrderProgressIndex(order.value?.status || ''))

const primaryAction = computed<ActionDefinition | null>(() => {
  if (activeReschedule.value || activeDispute.value) return null
  if (canPay.value) return { id: 'pay', label: order.value?.payment_status === 'deposit_paid' ? '支付尾款' : '完成演示支付', icon: markRaw(CreditCard) }
  if (isPhotographer.value && order.value?.status === 'pending') return { id: 'confirm', label: '确认预约', icon: markRaw(BadgeCheck) }
  if (canStart.value) return { id: 'start', label: '开始服务', icon: markRaw(Camera) }
  if (isPhotographer.value && activeRevision.value && !activeRevision.value.expected_redelivery_at) {
    return { id: 'revision-schedule', label: '确认返修排期', icon: markRaw(CalendarClock) }
  }
  if (canDeliver.value) return { id: 'deliver', label: order.value?.status === 'delivered' ? '重新交付' : '交付作品', icon: markRaw(Upload) }
  if (canAccept.value) return { id: 'accept', label: '确认验收', icon: markRaw(CheckCheck) }
  if (canReview.value) return { id: 'review', label: '评价本次服务', icon: markRaw(Star) }
  return null
})

const secondaryAction = computed<ActionDefinition | null>(() => {
  if (activeReschedule.value || activeDispute.value) return null
  if (isPhotographer.value && order.value?.status === 'pending') return { id: 'reject', label: '拒绝预约', icon: markRaw(Ban) }
  if (canRequestRevision.value) return { id: 'revision', label: '申请修改', icon: markRaw(RotateCcw) }
  if (isPhotographer.value && activeRevision.value && !activeRevision.value.expected_redelivery_at && canDeliver.value) {
    return { id: 'deliver', label: '直接重新交付', icon: markRaw(Upload) }
  }
  return null
})

const currentOwnerText = computed(() => {
  if (!order.value) return ''
  if (activeDispute.value) return '当前由平台管理员处理争议'
  if (activeReschedule.value) return canRespondReschedule.value ? '当前需要您处理改期申请' : '当前等待对方处理改期申请'
  if (order.value.status === 'pending') return isPhotographer.value ? '当前需要您确认预约' : '当前等待摄影师确认'
  if (order.value.status === 'awaiting_customer_payment') return isCustomer.value ? '当前需要您完成支付' : '当前等待客户支付'
  if (order.value.status === 'confirmed' && order.value.payment_status === 'deposit_paid') return isCustomer.value ? '当前需要您支付尾款' : '当前等待客户支付尾款'
  if (order.value.status === 'confirmed') return isPhotographer.value ? '当前由您推进拍摄服务' : '当前等待摄影师履约'
  if (order.value.status === 'in_progress') return isPhotographer.value ? '当前需要您交付作品' : '当前等待摄影师交付'
  if (order.value.status === 'delivered' && order.value.after_sales_status === 'revision_requested') return isPhotographer.value ? '当前需要您处理修改并重新交付' : '当前等待摄影师重新交付'
  if (order.value.status === 'delivered') return isCustomer.value ? '当前需要您验收作品' : '当前等待客户验收'
  if (['received', 'reviewed', 'completed'].includes(order.value.status)) return '订单已完成'
  return '订单已结束'
})

const nextActionText = computed(() => {
  if (!order.value) return ''
  if (activeDispute.value) return '平台正在核查双方材料；争议期间履约操作、自动验收和资金结算均已暂停。'
  if (activeReschedule.value) return canRespondReschedule.value
    ? '请接受、拒绝或反提新的时间；处理期间原预约仍然有效。'
    : '改期申请已提交，等待对方处理；处理期间原预约仍然有效。'
  if (order.value.status === 'pending') return isPhotographer.value ? '确认后客户需要完成支付，才会正式锁定档期。' : '摄影师确认后会进入支付环节。'
  if (order.value.status === 'awaiting_customer_payment') return isCustomer.value ? '请在支付期限内完成付款以锁定档期。' : '等待客户完成付款。'
  if (order.value.status === 'confirmed' && order.value.payment_status === 'deposit_paid') return isCustomer.value ? '定金已支付，请完成尾款后开始服务。' : '客户尚未完成尾款，暂时不能开始服务。'
  if (order.value.status === 'confirmed') return '档期已锁定，请按约定时间准备拍摄。'
  if (order.value.status === 'in_progress') return isPhotographer.value ? '拍摄完成后请上传并交付作品。' : '摄影师正在履约和准备交付。'
  if (order.value.status === 'delivered' && order.value.after_sales_status === 'revision_requested') return isPhotographer.value ? '请根据客户说明确认排期并重新交付。' : '修改申请已记录，自动验收已暂停。'
  if (order.value.status === 'delivered') return isCustomer.value ? '请查看交付文件并确认验收，或在额度内申请修改。' : '等待客户验收，逾期可能自动完成。'
  if (['received', 'reviewed', 'completed'].includes(order.value.status)) return order.value.rating ? '订单已完成并评价。' : '订单已完成，客户仍可提交评价。'
  return order.value.cancellation_reason || order.value.rejection_reason || '订单已取消。'
})

const formTitle = computed(() => ({
  reschedule: '申请改期',
  counter: '反提改期时间',
  delivery: order.value?.status === 'delivered' ? '重新交付作品' : '交付作品',
  revision: '申请修改',
  'revision-schedule': '确认返修排期',
  dispute: '发起平台争议',
  evidence: '补充争议证据',
  review: '评价本次服务',
}[activeForm.value || 'reschedule']))

const formSubmitLabel = computed(() => ({
  reschedule: '提交改期申请',
  counter: '提交反提时间',
  delivery: order.value?.status === 'delivered' ? '提交新版本' : '提交交付',
  revision: '提交修改申请',
  'revision-schedule': '确认预计时间',
  dispute: '确认发起争议',
  evidence: '提交证据',
  review: '提交评价',
}[activeForm.value || 'reschedule']))

function stepState(index: number) {
  if (order.value?.status === 'cancelled') return 'disabled'
  if (index < currentStepIndex.value) return 'done'
  if (index === currentStepIndex.value) return 'current'
  return 'waiting'
}

function isCardCollapsed(key: CardKey) {
  return Boolean(collapsedCards.value[key])
}

function toggleCard(key: CardKey) {
  collapsedCards.value[key] = !collapsedCards.value[key]
}

function formatDateTime(value?: string | null) {
  if (!value) return '时间待确认'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间待确认'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function formatDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

function toLocalDateTimeInput(date: Date) {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return shifted.toISOString().slice(0, 16)
}

function createIdempotencyKey(scope: string) {
  const randomPart = typeof globalThis.crypto?.randomUUID === 'function'
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `mobile-${scope}-${order.value?.id || orderId.value}-${randomPart}`
}

function formatPolicy(policy: unknown) {
  if (!policy) return ''
  if (typeof policy === 'string') return policy
  if (typeof policy !== 'object') return ''
  const record = policy as { description?: unknown; rules?: Array<{ description?: unknown }>; response_hours?: unknown }
  if (typeof record.description === 'string') return record.description
  if (Array.isArray(record.rules)) return record.rules.map((item) => item.description).filter((item): item is string => typeof item === 'string').join('；')
  if (record.response_hours) return `需在 ${record.response_hours} 小时内响应，原预约时间继续保留。`
  return ''
}

function actorRoleLabel(role?: string | null) {
  return ({ customer: '客户', photographer: '摄影师', admin: '管理员', system: '系统' } as Record<string, string>)[role || ''] || role || ''
}

function disputeStatusLabel(status: string) {
  return ({ open: '等待平台分配', assigned: '已分配管理员', investigating: '证据审核中', resolved: '已仲裁', cancelled: '已关闭' } as Record<string, string>)[status] || status
}

function disputeReasonLabel(reason: string) {
  return ({ quality_issue: '交付质量或内容不符', delivery_delay: '未按约定时间履约', service_failure: '服务无法继续', cooperation_issue: '对方配合问题', other: '其他争议' } as Record<string, string>)[reason] || reason
}

function disputeResolutionLabel(resolution?: string | null) {
  return ({ continue_fulfillment: '协调后继续履约', partial_refund: '部分退款', full_refund: '全额退款并终止订单', release_settlement: '释放资金并完成结算', other: '其他处理' } as Record<string, string>)[resolution || ''] || resolution || '等待平台处理'
}

function eventTitle(eventType: string) {
  return ({
    created: '提交预约',
    awaiting_payment: '等待客户支付',
    payment_succeeded: '支付成功',
    payment_expired: '支付超时',
    confirmed: '确认预约',
    in_progress: '开始服务',
    delivery_submitted: '提交交付 V1',
    delivery_resubmitted: '重新交付新版本',
    revision_requested: '客户申请修改',
    revision_acknowledged: '确认返修排期',
    delivery_accepted: '客户确认验收',
    delivery_auto_accepted: '系统自动验收',
    review_submitted: '客户提交评价',
    dispute_opened: '发起平台争议',
    dispute_evidence_added: '补充争议证据',
    dispute_assigned: '平台分配管理员',
    dispute_investigating: '平台开始审核',
    dispute_resolved: '平台完成仲裁',
    dispute_refund_succeeded: '仲裁退款完成',
    cancelled: '取消订单',
    reschedule_requested: '申请改期',
    reschedule_accepted: '接受改期',
    reschedule_rejected: '拒绝改期',
    reschedule_withdrawn: '撤回改期',
    reschedule_countered: '反提改期时间',
    reschedule_expired: '改期申请失效',
    refund_succeeded: '退款完成',
    settlement_succeeded: '平台完成结算',
  } as Record<string, string>)[eventType] || eventType
}

function deliveryStatusLabel(status: string) {
  return ({ submitted: '等待验收', accepted: '已验收', revision_requested: '已申请修改', superseded: '历史版本' } as Record<string, string>)[status] || status
}

function paymentPurposeLabel(purpose?: string) {
  return ({ full: '全款', deposit: '定金', balance: '尾款' } as Record<string, string>)[purpose || ''] || purpose || ''
}

function paymentStatusText(status?: string) {
  return ({ pending: '待支付', succeeded: '支付成功', failed: '支付失败', expired: '已超时', partially_refunded: '部分退款', refunded: '已退款' } as Record<string, string>)[status || ''] || status || ''
}

function revisionStatusLabel(status: string) {
  return ({ requested: '处理中', fulfilled: '已重新交付', cancelled: '已取消' } as Record<string, string>)[status] || status
}

function formatFileSize(value?: number | null) {
  const bytes = Number(value || 0)
  if (!bytes) return '大小未知'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function isImageFile(file: OrderDeliveryFile) {
  if (['image/jpeg', 'image/png', 'image/webp', 'image/avif'].includes(file.file_type || '')) return true
  return ['jpg', 'jpeg', 'png', 'webp', 'avif'].includes(file.file_name.split('.').pop()?.toLowerCase() || '')
}

async function loadDetail() {
  const requestId = ++detailRequestId
  const hadOrder = Boolean(order.value)
  if (!hadOrder) loading.value = true
  error.value = ''
  if (!Number.isInteger(orderId.value) || orderId.value <= 0) {
    error.value = '订单编号无效。'
    loading.value = false
    return
  }
  try {
    const [detail, financialRes] = await Promise.all([
      getOrderDetail(orderId.value),
      getOrderFinancialSummary(orderId.value).catch(() => null),
    ])
    if (requestId !== detailRequestId) return
    order.value = detail.order
    history.value = detail.history || []
    deliveries.value = detail.deliveries || []
    revisionRequests.value = detail.revision_requests || []
    disputes.value = detail.disputes || []
    financialSummary.value = financialRes
  } catch (loadError) {
    if (requestId !== detailRequestId) return
    const message = getApiErrorMessage(loadError)
    if (hadOrder) toastMessage.value = message
    else error.value = message
  } finally {
    if (requestId === detailRequestId) loading.value = false
  }
}

async function refresh(event: RefresherCustomEvent) {
  await loadDetail()
  event.target.complete()
}

async function confirmDialog(header: string, message: string, confirmText = '确认') {
  const alert = await alertController.create({
    header,
    message,
    buttons: [{ text: '取消', role: 'cancel' }, { text: confirmText, role: 'confirm' }],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  return result.role === 'confirm'
}

async function promptText(
  header: string,
  message: string,
  placeholder: string,
  confirmText: string,
  required: boolean,
) {
  const alert = await alertController.create({
    header,
    message,
    inputs: [{ name: 'value', type: 'textarea', placeholder, attributes: { maxlength: 500 } }],
    buttons: [{ text: '取消', role: 'cancel' }, { text: confirmText, role: 'confirm' }],
  })
  await alert.present()
  const result = await alert.onDidDismiss()
  if (result.role !== 'confirm') return null
  const value = String(result.data?.values?.value || '').trim()
  if (required && !value) {
    toastMessage.value = '请填写原因后再提交。'
    return null
  }
  return value
}

async function performAction(key: string, successMessage: string, task: () => Promise<unknown>) {
  if (processing.value) return
  processing.value = key
  try {
    await task()
    toastMessage.value = successMessage
    await loadDetail()
  } catch (actionError) {
    toastMessage.value = getApiErrorMessage(actionError)
  } finally {
    processing.value = ''
  }
}

async function runAction(action: ActionId) {
  if (!order.value || processing.value) return
  if (action === 'deliver') return openForm('delivery')
  if (action === 'revision') return openForm('revision')
  if (action === 'review') return openForm('review')
  if (action === 'revision-schedule') return openForm('revision-schedule')

  if (action === 'confirm') {
    if (!(await confirmDialog('确认预约', '确认后客户需要完成支付，支付完成才会正式锁定档期。'))) return
    trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'confirm_order', order_id: order.value.id })
    return performAction('confirm', '预约已确认，等待客户支付。', () => confirmOrder(order.value!.id))
  }
  if (action === 'reject') {
    const reason = await promptText('拒绝预约', '请说明无法接单的原因，客户会在订单中看到。', '例如：该时间已有拍摄安排', '确认拒绝', true)
    if (reason == null) return
    trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'reject_order', order_id: order.value.id })
    return performAction('reject', '预约已拒绝。', () => rejectOrder(order.value!.id, reason))
  }
  if (action === 'pay') {
    if (!(await confirmDialog('演示支付', '这是本地演示支付，不会产生真实扣款。', '确认支付'))) return
    trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'pay_order', order_id: order.value.id })
    const storageKey = `mobile-payment-idempotency:${order.value.id}:${order.value.payment_status || 'unpaid'}`
    let idempotencyKey = localStorage.getItem(storageKey)
    if (!idempotencyKey) {
      idempotencyKey = createIdempotencyKey('payment')
      localStorage.setItem(storageKey, idempotencyKey)
    }
    return performAction('pay', '演示支付成功，资金已进入平台担保。', async () => {
      const payment = await createOrderPayment(order.value!.id, idempotencyKey)
      await confirmMockPayment(payment)
      localStorage.removeItem(storageKey)
    })
  }
  if (action === 'start') {
    if (!(await confirmDialog('开始服务', '确认订单已经进入拍摄或后期处理阶段？'))) return
    trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'start_service', order_id: order.value.id })
    return performAction('start', '订单已进入履约中。', () => startOrder(order.value!.id))
  }
  if (action === 'accept') {
    if (!(await confirmDialog('确认验收', '验收后订单将完成并结算担保资金，请先检查全部交付文件。'))) return
    trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'accept_delivery', order_id: order.value.id })
    return performAction('accept', '作品已验收，订单完成。', () => acceptOrder(order.value!.id))
  }
}

function runSecondaryAction() {
  if (secondaryAction.value) void runAction(secondaryAction.value.id)
}

async function acceptRescheduleAction() {
  if (!order.value || !activeReschedule.value) return
  if (!(await confirmDialog('接受改期', '接受后订单将切换到候选时间，是否继续？'))) return
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'accept_reschedule', order_id: order.value.id })
  await performAction('accept-reschedule', '改期已确认。', () => acceptOrderReschedule(order.value!.id, activeReschedule.value!.id))
}

async function rejectRescheduleAction() {
  if (!order.value || !activeReschedule.value) return
  const note = await promptText('拒绝改期', '可说明原因；拒绝后原预约时间继续有效。', '例如：该时间已有其他安排', '确认拒绝', false)
  if (note == null) return
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'reject_reschedule', order_id: order.value.id })
  await performAction('reject-reschedule', '改期已拒绝，原预约保持不变。', () => rejectOrderReschedule(order.value!.id, activeReschedule.value!.id, note))
}

async function withdrawRescheduleAction() {
  if (!order.value || !activeReschedule.value) return
  if (!(await confirmDialog('撤回改期', '撤回后候选时间将释放，原预约保持不变。'))) return
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'withdraw_reschedule', order_id: order.value.id })
  await performAction('withdraw-reschedule', '改期申请已撤回。', () => withdrawOrderReschedule(order.value!.id, activeReschedule.value!.id))
}

async function cancelOrderAction() {
  if (!order.value) return
  const reason = await promptText('取消订单', '取消可能触发退款规则，请说明原因并确认。', '例如：行程变化，无法按原时间拍摄', '确认取消', true)
  if (reason == null) return
  trackEvent(AnalyticsEvent.BUTTON_CLICK, { button_name: 'cancel_order', order_id: order.value.id })
  await performAction('cancel', '订单已取消。', () => cancelOrder(order.value!.id, reason))
}

function goConversation() {
  if (!order.value || !chatTargetId.value) return
  void router.push({
    name: 'conversation',
    params: { userId: chatTargetId.value },
    query: {
      orderId: order.value.id,
      orderTitle: order.value.package_name || order.value.package_snapshot,
    },
  })
}

function openForm(mode: FormMode) {
  if (processing.value) return
  resetForm()
  activeForm.value = mode
  if (mode === 'delivery' || mode === 'revision') {
    formIdempotencyKey.value = createIdempotencyKey(mode)
  }
}

function closeForm() {
  if (formSubmitting.value) return
  activeForm.value = null
  resetForm()
}

function resetForm() {
  formDateTime.value = ''
  formText.value = ''
  formRating.value = 0
  formFiles.value = []
  formReasonCode.value = ''
  formRequestedResolution.value = ''
  formError.value = ''
  formIdempotencyKey.value = ''
  fileInputKey.value += 1
}

function selectFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const nextFiles = Array.from(input.files || [])
  const uniqueFiles = [...formFiles.value, ...nextFiles].filter((file, index, files) => (
    files.findIndex((candidate) => (
      candidate.name === file.name
      && candidate.size === file.size
      && candidate.lastModified === file.lastModified
    )) === index
  ))
  if (uniqueFiles.length > 18) toastMessage.value = '单次最多选择 18 个文件，超出的文件未加入。'
  formFiles.value = uniqueFiles.slice(0, 18)
  input.value = ''
}

function removeFile(index: number) {
  formFiles.value.splice(index, 1)
}

async function submitActiveForm() {
  if (!order.value || !activeForm.value || processing.value) return
  formError.value = ''
  const mode = activeForm.value

  let appointmentTime = ''
  let appointmentDate = ''
  if (['reschedule', 'counter', 'revision-schedule'].includes(mode)) {
    const date = new Date(formDateTime.value)
    if (!formDateTime.value || Number.isNaN(date.getTime()) || date.getTime() <= Date.now()) {
      formError.value = '请选择晚于当前时间的有效日期。'
      return
    }
    appointmentDate = formDateTime.value
    appointmentTime = date.toISOString()
  }
  if (['reschedule', 'counter'].includes(mode) && !formText.value.trim()) {
    formError.value = '请填写改期原因。'
    return
  }
  if (mode === 'delivery' && !formFiles.value.length) {
    formError.value = '请至少选择一个交付文件。'
    return
  }
  if (mode === 'revision' && !formText.value.trim()) {
    formError.value = '请填写具体修改说明。'
    return
  }
  if (mode === 'review' && !formRating.value) {
    formError.value = '请选择 1–10 分评分。'
    return
  }
  if (mode === 'dispute' && (!formReasonCode.value || !formRequestedResolution.value || !formText.value.trim())) {
    formError.value = '请完整填写争议类型、处理诉求和事实说明。'
    return
  }
  if (mode === 'evidence' && !activeDispute.value) {
    formError.value = '当前没有可补充材料的进行中争议，请刷新订单详情后重试。'
    return
  }
  if (mode === 'evidence' && !formText.value.trim() && !formFiles.value.length) {
    formError.value = '请填写证据说明或选择附件。'
    return
  }
  if (mode === 'dispute' && !(await confirmDialog(
    '确认发起争议',
    '提交后平台将暂停自动验收和资金结算。确认材料已经检查无误？',
    '确认提交',
  ))) return

  processing.value = 'form'
  let submitted = false
  try {
    if (mode === 'reschedule') {
      await requestOrderReschedule(order.value.id, { appointment_date: appointmentDate, reason: formText.value.trim() })
      toastMessage.value = '改期申请已提交。'
    }
    if (mode === 'counter' && activeReschedule.value) {
      await counterOrderReschedule(order.value.id, activeReschedule.value.id, { appointment_date: appointmentDate, reason: formText.value.trim() })
      toastMessage.value = '新的候选时间已提交。'
    }
    if (mode === 'delivery') {
      await deliverOrderWorks(
        order.value.id,
        formFiles.value,
        formText.value.trim(),
        formIdempotencyKey.value || createIdempotencyKey('delivery'),
      )
      toastMessage.value = order.value.status === 'delivered' ? '新版本已重新交付。' : '作品已交付。'
    }
    if (mode === 'revision') {
      await requestOrderRevision(
        order.value.id,
        formText.value.trim(),
        formFiles.value,
        formIdempotencyKey.value || createIdempotencyKey('revision'),
      )
      toastMessage.value = '修改申请已提交，自动验收已暂停。'
    }
    if (mode === 'revision-schedule' && activeRevision.value) {
      await acknowledgeOrderRevision(order.value.id, activeRevision.value.id, appointmentTime)
      toastMessage.value = '返修排期已确认。'
    }
    if (mode === 'dispute') {
      await openOrderDispute(order.value.id, {
        reason_code: formReasonCode.value,
        requested_resolution: formRequestedResolution.value,
        description: formText.value.trim(),
      }, formFiles.value)
      toastMessage.value = '争议已提交，自动验收和资金结算已暂停。'
    }
    if (mode === 'evidence') {
      const disputeId = activeDispute.value?.id
      if (!disputeId) throw new Error('当前争议已结束，无法继续补充证据。')
      await addOrderDisputeEvidence(
        order.value.id,
        disputeId,
        formText.value.trim(),
        formFiles.value,
      )
      toastMessage.value = '证据已补充并记录提交时间。'
    }
    if (mode === 'review') {
      await reviewOrder(order.value.id, { rating: formRating.value, review_text: formText.value.trim() || undefined })
      toastMessage.value = '评价已提交。'
    }
    await loadDetail()
    submitted = true
  } catch (submitError) {
    formError.value = getApiErrorMessage(submitError)
  } finally {
    processing.value = ''
    if (submitted) {
      activeForm.value = null
      resetForm()
    }
  }
}

async function downloadFile(delivery: OrderDelivery, file: OrderDeliveryFile) {
  if (!order.value || downloadingFileId.value) return
  downloadingFileId.value = file.id
  try {
    const blob = await downloadOrderDeliveryFile(order.value.id, delivery.id, file.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.file_name || '交付文件'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (downloadError) {
    toastMessage.value = getApiErrorMessage(downloadError)
  } finally {
    downloadingFileId.value = null
  }
}

onMounted(async () => {
  await auth.initialize()
  await loadDetail()
})
</script>

<style scoped>
.detail-content, .modal-content { --background: var(--paper); }
.detail-shell { width: min(100%, var(--content-max)); margin: 0 auto; padding: var(--space-4) var(--space-4) var(--space-8); }
.header-actions { display: flex; align-items: center; }
.header-action { display: grid; width: var(--touch-target); height: var(--touch-target); place-items: center; border: 0; background: transparent; color: var(--ink); }
.header-action:disabled { opacity: .45; }

.status-hero { padding: var(--space-5); border: 0; border-radius: var(--radius-lg); background: var(--brand-soft); box-shadow: var(--neu-raise-sm); }
.status-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.status-heading small { color: var(--brand); font-size: var(--text-xs); font-weight: 700; }
.status-heading h1 { margin: 4px 0 0; font-family: var(--font-serif); font-size: var(--text-xl); line-height: 1.4; }
.status-hero > p { margin: var(--space-3) 0 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; }
.status-badge { display: inline-flex; min-height: 30px; flex: 0 0 auto; align-items: center; padding: 4px 10px; border-radius: var(--radius-pill); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); font-size: var(--text-2xs); font-weight: 750; }
.status-badge.cancelled { color: var(--danger); }
.responsibility-line { display: flex; align-items: center; gap: var(--space-2); margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--divider); color: var(--brand); font-size: var(--text-xs); font-weight: 700; }

.progress-list { display: grid; gap: 0; margin: var(--space-5) 0 0; padding: 0; list-style: none; }
.progress-list li { position: relative; display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: var(--space-3); min-height: 62px; color: var(--ink-tertiary); }
.progress-list li:not(:last-child)::after { position: absolute; top: 30px; bottom: -2px; left: 16px; width: 2px; background: var(--divider); content: ''; }
.step-marker { z-index: 1; display: grid; width: 34px; height: 34px; place-items: center; border: 0; border-radius: 50%; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); font-size: var(--text-xs); font-weight: 750; }
.progress-list strong { display: block; margin-top: 1px; color: inherit; font-size: var(--text-sm); }
.progress-list small { display: block; margin-top: 3px; font-size: var(--text-xs); line-height: 1.45; }
.progress-list li.done, .progress-list li.current { color: var(--brand); }
.progress-list li.done .step-marker, .progress-list li.current .step-marker { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); border: 0; }
.progress-list li.current strong { color: var(--ink); }
.progress-list li.disabled { opacity: .48; }

.notice-card, .summary-card, .management-card, .content-card { margin-top: var(--space-5); padding: var(--space-4); border: 0; border-radius: var(--radius-lg); background: var(--neu-surface); box-shadow: var(--neu-raise); }
.card-heading { cursor: pointer; -webkit-tap-highlight-color: transparent; }
.card-toggle { display: grid; width: 28px; height: 28px; place-items: center; align-self: center; border: 0; border-radius: 50%; background: transparent; color: var(--ink-tertiary); }
.card-toggle svg { transition: transform var(--motion-normal) ease; }
.card-toggle[aria-expanded='true'] svg { transform: rotate(180deg); }
.card-heading:active .card-toggle { color: var(--brand); }
.notice-heading .card-toggle { align-self: start; }
.reschedule-card { border-color: var(--brand); }
.cancellation-card { border-color: var(--danger); }
.dispute-card { border-color: var(--warning); }
.notice-heading { display: grid; grid-template-columns: 42px minmax(0, 1fr) auto; gap: var(--space-3); }
.dispute-card .notice-heading { grid-template-columns: 42px minmax(0, 1fr) auto auto; }
.notice-heading > span { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 50%; background: var(--brand-soft); color: var(--brand); }
.cancellation-card .notice-heading > span { color: var(--danger); }
.dispute-card .notice-heading > span { background: var(--paper); box-shadow: var(--neu-inset); color: var(--warning); }
.dispute-card .notice-heading > em { align-self: start; padding: 4px 8px; border-radius: var(--radius-pill); background: var(--paper); box-shadow: var(--neu-inset); color: var(--warning); font-size: var(--text-2xs); font-style: normal; font-weight: 750; }
.notice-heading h2, .section-heading h2 { margin: 0; font-family: var(--font-serif); font-size: var(--text-lg); }
.notice-heading p, .section-heading p { margin: 3px 0 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }
.notice-facts, .contract-list { display: grid; gap: var(--space-2); margin: var(--space-4) 0 0; }
.notice-facts div, .contract-list div { display: grid; grid-template-columns: 88px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-3); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); }
.notice-facts dt, .contract-list dt { color: var(--ink-tertiary); font-size: var(--text-xs); }
.notice-facts dd, .contract-list dd { margin: 0; color: var(--ink); font-size: var(--text-sm); line-height: 1.5; word-break: break-word; }
.reason-copy { margin: var(--space-4) 0 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; white-space: pre-wrap; }
.resolution-result { display: grid; gap: 5px; margin-top: var(--space-4); padding: var(--space-3); border-radius: var(--radius-md); background: var(--brand-soft); }
.resolution-result strong { color: var(--brand); font-size: var(--text-sm); }
.resolution-result span { color: var(--ink); font-size: var(--text-xs); font-weight: 700; }
.resolution-result p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; white-space: pre-wrap; }
.evidence-list { display: grid; gap: var(--space-3); margin-top: var(--space-4); }
.evidence-list article { display: grid; gap: var(--space-2); padding: var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); }
.evidence-list header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.evidence-list header strong { font-size: var(--text-xs); }
.evidence-list header small { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.evidence-list article > p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; white-space: pre-wrap; }
.evidence-file { display: grid; grid-template-columns: 20px minmax(0, 1fr) auto; min-height: var(--touch-target); align-items: center; gap: var(--space-2); padding: 0 var(--space-3); border: 0; border-radius: var(--radius-sm); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); text-decoration: none; }
.evidence-file span { overflow: hidden; font-size: var(--text-xs); font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.evidence-file small { color: var(--ink-tertiary); font-size: var(--text-2xs); }

.inline-actions, .management-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.inline-actions button, .management-actions button { display: inline-flex; min-height: var(--touch-target); flex: 1 1 120px; align-items: center; justify-content: center; gap: 6px; padding: 0 var(--space-3); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: 750; }
button.primary { border: 0; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); }
button.secondary { border: 0; background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--brand); }
button.danger { border: 1px solid var(--danger); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--danger); }
.inline-actions button:disabled, .management-actions button:disabled { opacity: .5; }
.inline-actions ion-spinner { width: 18px; height: 18px; }

.counterparty-row { display: grid; grid-template-columns: 52px minmax(0, 1fr) auto; align-items: center; gap: var(--space-3); }
.counterparty-row div { display: grid; gap: 3px; }
.counterparty-row small { color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.counterparty-row strong { font-size: var(--text-base); }
.facts-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin-top: var(--space-4); }
.facts-grid div { display: grid; min-height: 112px; align-content: center; gap: 5px; padding: var(--space-3); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); }
.facts-grid span { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.facts-grid strong { color: var(--ink); font-size: var(--text-sm); line-height: 1.45; word-break: break-word; }
.payment-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-3); color: var(--brand); font-size: var(--text-xs); font-weight: 700; }
.payment-row small { color: var(--ink-tertiary); font-weight: 500; text-align: right; }

.payment-card { margin-top: var(--space-5); }
.payment-summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); margin-top: var(--space-4); }
.payment-summary-grid > div { display: grid; min-height: 98px; align-content: center; justify-items: center; gap: 5px; padding: var(--space-3); border-radius: var(--radius-sm); background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); text-align: center; }
.payment-summary-grid span { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.payment-summary-grid strong { color: var(--ink); font-size: var(--text-base); font-weight: 750; }
.payment-summary-grid .refund-amount { color: var(--danger); }
.payment-summary-grid .settle-amount { color: var(--brand); }
.payment-action-row { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-4); }
.payment-action-row button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: 6px; padding: 0 var(--space-5); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font-size: var(--text-sm); font-weight: 750; }
.payment-action-row button:disabled { opacity: .52; }
.payment-action-row span { color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.5; }
.financial-records { margin-top: var(--space-4); border-top: 1px solid var(--divider); }
.financial-record { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--divider); color: var(--ink-secondary); font-size: var(--text-sm); }
.financial-record:last-child { border-bottom: 0; }
.financial-record span { display: flex; align-items: center; gap: 5px; }
.financial-record strong { font-variant-numeric: tabular-nums; }
.refund-record strong { color: var(--danger); }
.settlement-record strong { color: var(--brand); }

.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-3); }
.long-copy { margin-top: var(--space-4); padding-top: var(--space-4); border-top: 1px solid var(--divider); }
.long-copy strong { font-size: var(--text-sm); }
.long-copy p { margin: var(--space-2) 0 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.7; white-space: pre-wrap; }
.empty-copy { margin: var(--space-4) 0 0; padding: var(--space-5); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink-tertiary); font-size: var(--text-sm); text-align: center; }

.delivery-list, .revision-list { display: grid; gap: var(--space-3); margin-top: var(--space-4); }
.delivery-card, .revision-list article { padding: var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); }
.delivery-card > header, .revision-list header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.delivery-card header div { display: grid; gap: 3px; }
.delivery-card header strong, .revision-list header strong { font-size: var(--text-sm); }
.delivery-card header small, .revision-list small { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.delivery-card header > span, .revision-list header span { color: var(--brand); font-size: var(--text-2xs); font-weight: 700; }
.delivery-card > p, .revision-list p { margin: var(--space-3) 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.65; }
.delivery-files { display: grid; gap: var(--space-2); margin-top: var(--space-3); }
.delivery-file { display: grid; grid-template-columns: 48px minmax(0, 1fr) 48px; min-height: 58px; align-items: center; gap: var(--space-2); padding: 5px; border: 0; border-radius: var(--radius-sm); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); }
.delivery-file img, .file-placeholder { width: 48px; height: 48px; border-radius: var(--radius-sm); object-fit: cover; }
.file-placeholder { display: grid; place-items: center; background: var(--paper); box-shadow: var(--neu-inset); color: var(--brand); }
.file-copy { display: grid; gap: 3px; min-width: 0; }
.file-copy strong { overflow: hidden; font-size: var(--text-xs); text-overflow: ellipsis; white-space: nowrap; }
.file-copy small { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.download-button { display: grid; width: 48px; height: 48px; place-items: center; border: 0; background: transparent; color: var(--brand); }
.download-button:disabled { opacity: .45; }
.download-button ion-spinner { width: 18px; height: 18px; }
.legacy-images { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-2); margin-top: var(--space-4); }
.legacy-images img { width: 100%; aspect-ratio: 1; border-radius: var(--radius-sm); object-fit: cover; }
.deadline-note { display: flex; gap: var(--space-2); margin: var(--space-4) 0 0; padding: var(--space-3); border-radius: var(--radius-md); background: var(--brand-soft); color: var(--brand); font-size: var(--text-xs); line-height: 1.55; }
.deadline-note svg { flex: 0 0 auto; }
.revision-list article { display: grid; gap: 4px; }

.review-card { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--space-3); align-items: start; }
.review-score { display: grid; min-width: 72px; place-items: center; gap: 5px; padding: var(--space-3); border-radius: var(--radius-md); background: var(--brand-soft); color: var(--brand); }
.review-card h2 { margin: 1px 0 5px; font-family: var(--font-serif); font-size: var(--text-lg); }
.review-card p { margin: 0; color: var(--ink-secondary); font-size: var(--text-sm); line-height: 1.65; }

.timeline-list { display: grid; gap: 0; margin: var(--space-4) 0 0; padding: 0; list-style: none; }
.timeline-list li { position: relative; display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: var(--space-3); padding-bottom: var(--space-5); }
.timeline-list li:not(:last-child)::after { position: absolute; top: 14px; bottom: 0; left: 5px; width: 1px; background: var(--divider); content: ''; }
.timeline-dot { z-index: 1; width: 11px; height: 11px; margin-top: 3px; border: 0; border-radius: 50%; background: var(--neu-surface-brand); box-shadow: var(--shadow-1); }
.timeline-list div { display: grid; gap: 4px; }
.timeline-list strong { font-size: var(--text-sm); }
.timeline-list small { color: var(--ink-tertiary); font-size: var(--text-2xs); }
.timeline-list p { margin: 2px 0 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }

ion-modal ion-toolbar { --background: var(--paper); --border-color: var(--divider); }
ion-modal ion-title { font-size: var(--text-base); font-weight: 700; }
.form-shell { display: grid; width: min(100%, 620px); gap: var(--space-2); margin: 0 auto; padding: var(--space-5) var(--space-4) calc(var(--space-8) + env(safe-area-inset-bottom)); }
.form-shell > label, .rating-fieldset legend { margin-top: var(--space-3); color: var(--ink); font-size: var(--text-sm); font-weight: 750; }
.form-shell label span, .rating-fieldset legend span { color: var(--ink-tertiary); font-size: var(--text-xs); font-weight: 500; }
.form-shell input, .form-shell textarea, .form-shell select { width: 100%; min-height: var(--touch-target); padding: var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--ink); font-size: var(--text-base); outline: none; }
.form-shell textarea { min-height: 126px; resize: vertical; line-height: 1.65; }
.form-shell input:focus, .form-shell textarea:focus, .form-shell select:focus { box-shadow: var(--neu-inset-deep), 0 0 0 2px var(--focus-ring); }
.form-warning { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--warning); border-radius: var(--radius-md); background: var(--paper); box-shadow: var(--neu-inset); color: var(--warning); }
.form-warning svg { flex: 0 0 auto; }
.form-warning p { margin: 0; color: var(--ink-secondary); font-size: var(--text-xs); line-height: 1.6; }
.field-hint { margin: 0; color: var(--ink-tertiary); font-size: var(--text-xs); line-height: 1.55; }
.character-count { color: var(--ink-tertiary); font-size: var(--text-2xs); text-align: right; }
.rating-fieldset { margin: 0; padding: 0; border: 0; background: var(--paper); box-shadow: var(--neu-inset); }
.rating-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.rating-button { min-height: var(--touch-target); border: 0; border-radius: var(--radius-md); background: var(--neu-surface); box-shadow: var(--neu-raise-sm); color: var(--ink-secondary); font-weight: 750; }
.rating-button.selected { background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); border: 0; }
.form-error { display: flex; align-items: flex-start; gap: var(--space-2); margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--danger); border-radius: var(--radius-md); color: var(--danger); font-size: var(--text-sm); line-height: 1.55; }
.form-error svg { flex: 0 0 auto; }
.submit-button { display: inline-flex; min-height: var(--touch-target); align-items: center; justify-content: center; gap: var(--space-2); margin-top: var(--space-4); border: 0; border-radius: var(--radius-md); background: var(--neu-surface-brand); box-shadow: var(--shadow-1); color: var(--white); font-weight: 750; }
.submit-button.danger { border-color: var(--danger); background: var(--danger); }
.submit-button:disabled { opacity: .52; }
.submit-button ion-spinner { width: 20px; height: 20px; }

@media (min-width: 680px) {
  .notice-facts, .contract-list { grid-template-columns: repeat(2, 1fr); }
  .notice-facts div, .contract-list div { grid-template-columns: 96px minmax(0, 1fr); }
}

@media (max-width: 420px) {
  .dispute-card .notice-heading { grid-template-columns: 42px minmax(0, 1fr) auto; }
  .dispute-card .notice-heading > em { grid-area: 2 / 2; justify-self: start; }
}
</style>
