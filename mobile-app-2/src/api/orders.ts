import api from './client'
import type {
  AvailabilityResponse,
  CreateOrderPayload,
  FinancialSummary,
  OpenDisputePayload,
  OrderDispute,
  OrderDetailResponse,
  OrderItem,
  PaymentRecord,
  ReschedulePayload,
  ReviewPayload,
} from '@/types/orders'

export async function getAvailableSlots(
  photographerId: number,
  params: { days?: number; duration_minutes?: number; buffer_minutes?: number } = {},
): Promise<AvailabilityResponse> {
  const { data } = await api.get<AvailabilityResponse>(
    `/photographers/${photographerId}/available-slots`,
    { params },
  )
  return data
}

export async function createOrder(payload: CreateOrderPayload): Promise<OrderItem> {
  const { data } = await api.post<OrderItem>('/orders/', payload)
  return data
}

export async function getCustomerOrders(params: Record<string, unknown> = {}): Promise<OrderItem[]> {
  const { data } = await api.get<OrderItem[]>('/orders/my-customer', { params })
  return data
}

export async function getPhotographerOrders(params: Record<string, unknown> = {}): Promise<OrderItem[]> {
  const { data } = await api.get<OrderItem[]>('/orders/my-photographer', { params })
  return data
}

export async function getOrderDetail(orderId: number): Promise<OrderDetailResponse> {
  const { data } = await api.get<OrderDetailResponse>(`/orders/${orderId}/detail`)
  return data
}

export async function confirmOrder(orderId: number): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/confirm`)
  return data
}

export async function rejectOrder(orderId: number, rejectionReason: string): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/reject`, {
    rejection_reason: rejectionReason,
  })
  return data
}

export async function requestOrderReschedule(orderId: number, payload: ReschedulePayload): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/reschedule/request`, payload)
  return data
}

export async function acceptOrderReschedule(orderId: number, requestId: number, responseNote = ''): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/reschedule/${requestId}/accept`, {
    response_note: responseNote || null,
  })
  return data
}

export async function rejectOrderReschedule(orderId: number, requestId: number, responseNote = ''): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/reschedule/${requestId}/reject`, {
    response_note: responseNote || null,
  })
  return data
}

export async function withdrawOrderReschedule(orderId: number, requestId: number): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/reschedule/${requestId}/withdraw`)
  return data
}

export async function counterOrderReschedule(
  orderId: number,
  requestId: number,
  payload: ReschedulePayload,
): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/reschedule/${requestId}/counter`, payload)
  return data
}

export async function cancelOrder(orderId: number, cancelReason: string): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/cancel`, {
    cancel_reason: cancelReason,
  })
  return data
}

export async function startOrder(orderId: number): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/start`)
  return data
}

export async function acceptOrder(orderId: number): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/accept`)
  return data
}

export async function deliverOrderWorks(
  orderId: number,
  files: File[],
  description = '',
  idempotencyKey = `mobile-delivery-${orderId}-${Date.now()}`,
): Promise<OrderItem> {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  form.append('description', description)
  form.append('idempotency_key', idempotencyKey)
  const { data } = await api.post<OrderItem>(`/orders/${orderId}/deliver`, form, { timeout: 0 })
  return data
}

export async function downloadOrderDeliveryFile(
  orderId: number,
  deliveryId: number,
  fileId: number,
): Promise<Blob> {
  const { data } = await api.get<Blob>(
    `/orders/${orderId}/deliveries/${deliveryId}/files/${fileId}/download`,
    { responseType: 'blob', timeout: 0 },
  )
  return data
}

export async function requestOrderRevision(
  orderId: number,
  instructions: string,
  files: File[] = [],
  idempotencyKey = `mobile-revision-${orderId}-${Date.now()}`,
): Promise<OrderItem> {
  const form = new FormData()
  form.append('instructions', instructions)
  form.append('idempotency_key', idempotencyKey)
  files.forEach((file) => form.append('files', file))
  const { data } = await api.post<OrderItem>(`/orders/${orderId}/revision`, form, { timeout: 0 })
  return data
}

export async function acknowledgeOrderRevision(
  orderId: number,
  revisionId: number,
  expectedRedeliveryAt: string,
): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/revision/${revisionId}/acknowledge`, {
    expected_redelivery_at: expectedRedeliveryAt,
  })
  return data
}

export async function openOrderDispute(
  orderId: number,
  payload: OpenDisputePayload,
  files: File[] = [],
): Promise<OrderDispute> {
  const form = new FormData()
  form.append('reason_code', payload.reason_code)
  form.append('description', payload.description)
  form.append('requested_resolution', payload.requested_resolution)
  files.forEach((file) => form.append('files', file))
  const { data } = await api.post<OrderDispute>(`/orders/${orderId}/disputes`, form, { timeout: 0 })
  return data
}

export async function addOrderDisputeEvidence(
  orderId: number,
  disputeId: number,
  description: string,
  files: File[] = [],
): Promise<OrderDispute> {
  const form = new FormData()
  if (description) form.append('description', description)
  files.forEach((file) => form.append('files', file))
  const { data } = await api.post<OrderDispute>(
    `/orders/${orderId}/disputes/${disputeId}/evidence`,
    form,
    { timeout: 0 },
  )
  return data
}

export async function reviewOrder(orderId: number, payload: ReviewPayload): Promise<OrderItem> {
  const { data } = await api.put<OrderItem>(`/orders/${orderId}/review`, payload)
  return data
}

export async function createOrderPayment(
  orderId: number,
  idempotencyKey = `mobile-payment-${orderId}-${Date.now()}`,
): Promise<PaymentRecord> {
  const { data } = await api.post<PaymentRecord>(`/payments/orders/${orderId}`, {
    idempotency_key: idempotencyKey,
  })
  return data
}

export async function confirmMockPayment(payment: PaymentRecord): Promise<PaymentRecord> {
  const { data } = await api.post<PaymentRecord>(`/payments/${payment.id}/mock-confirm`, {
    provider_transaction_id: `mobile-${payment.payment_no}`,
  })
  return data
}

export async function getOrderFinancialSummary(orderId: number): Promise<FinancialSummary> {
  const { data } = await api.get<FinancialSummary>(`/payments/orders/${orderId}`)
  return data
}
