import api from '../utils/api'

// 客户下单
export function createOrder(data) {
    return api.post('/orders/', data)
}

// 客户查看自己的订�?
export function getMyCustomerOrders(params = {}) {
    return api.get('/orders/my-customer', { params })
}


// 摄影师查看自己的订单
export function getMyPhotographerOrders(params = {}) {
    return api.get('/orders/my-photographer', { params })
}

// 查看订单详情
export function getOrderDetail(orderId) {
    return api.get(`/orders/${orderId}/detail`)
}

// 创建支付单（后端根据合同决定全款、定金或尾款金额）
export function createOrderPayment(orderId, idempotencyKey) {
    return api.post(`/payments/orders/${orderId}`, { idempotency_key: idempotencyKey })
}

// 开发环境模拟支付网关确认；正式 provider 接入后由支付页面和回调替代
export function confirmMockPayment(paymentId, providerTransactionId) {
    return api.post(`/payments/${paymentId}/mock-confirm`, {
        provider_transaction_id: providerTransactionId || null,
    })
}

export function getOrderFinancialSummary(orderId) {
    return api.get(`/payments/orders/${orderId}`)
}

// 摄影师确认订�?
export function confirmOrder(orderId) {
    return api.put(`/orders/${orderId}/confirm`)
}

// 摄影师开始拍摄/进入待交付
export function startOrder(orderId) {
    return api.put(`/orders/${orderId}/start`)
}

// 摄影师拒绝订�?
export function rejectOrder(orderId, rejectionReason) {
    return api.put(`/orders/${orderId}/reject`, { rejection_reason: rejectionReason })
}

// 客户申请改期
export function requestReschedule(orderId, data) {
    return api.put(`/orders/${orderId}/reschedule/request`, data)
}

// 摄影师确认改期
export function confirmReschedule(orderId) {
    return api.put(`/orders/${orderId}/reschedule/confirm`)
}

export function acceptReschedule(orderId, requestId, responseNote = '') {
    return api.put(`/orders/${orderId}/reschedule/${requestId}/accept`, { response_note: responseNote || null })
}

export function rejectReschedule(orderId, requestId, responseNote = '') {
    return api.put(`/orders/${orderId}/reschedule/${requestId}/reject`, { response_note: responseNote || null })
}

export function withdrawReschedule(orderId, requestId) {
    return api.put(`/orders/${orderId}/reschedule/${requestId}/withdraw`)
}

export function counterReschedule(orderId, requestId, data) {
    return api.put(`/orders/${orderId}/reschedule/${requestId}/counter`, data)
}

// 客户或摄影师取消订单
export function cancelOrder(orderId, cancelReason) {
    return api.put(`/orders/${orderId}/cancel`, { cancel_reason: cancelReason })
}

// 摄影师交付作品（multipart/form-data�?
export function deliverWorks(orderId, formData) {
    return api.post(`/orders/${orderId}/deliver`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export function downloadDeliveryFile(orderId, deliveryId, fileId) {
    return api.get(`/orders/${orderId}/deliveries/${deliveryId}/files/${fileId}/download`, {
        responseType: 'blob',
        timeout: 0,
    })
}

// 客户针对当前交付版本申请修改（可附参考图片）
export function requestDeliveryRevision(orderId, formData) {
    return api.post(`/orders/${orderId}/revision`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export function acknowledgeDeliveryRevision(orderId, revisionId, expectedRedeliveryAt) {
    return api.put(`/orders/${orderId}/revision/${revisionId}/acknowledge`, {
        expected_redelivery_at: expectedRedeliveryAt,
    })
}

export function openOrderDispute(orderId, formData) {
    return api.post(`/orders/${orderId}/disputes`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

export function addOrderDisputeEvidence(orderId, disputeId, formData) {
    return api.post(`/orders/${orderId}/disputes/${disputeId}/evidence`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
    })
}

// 客户接收作品
export function acceptOrder(orderId) {
    return api.put(`/orders/${orderId}/accept`)
}

// 客户评价订单
export function reviewOrder(orderId, data) {
    return api.put(`/orders/${orderId}/review`, data)
}

// 摄影师数据统计
export function getPhotographerStats() {
    return api.get('/orders/stats')
}

// 摄影师行动型仪表盘
export function getPhotographerDashboard(params = {}) {
    return api.get('/orders/dashboard', { params })
}

// 摄影师公开信任面板
export function getPublicPhotographerDashboard(userId) {
    return api.get(`/orders/dashboard/public/${userId}`)
}

// 查看指定摄影师的数据统计（公开）
export function getPhotographerStatsByUser(userId) {
    return api.get(`/orders/stats/${userId}`)
}
