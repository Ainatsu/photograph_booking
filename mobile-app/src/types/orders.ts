export interface AvailableSlot {
  start_at: string
  end_at: string
  label: string
}

export interface AvailabilityDay {
  date: string
  weekday: string
  location?: string | null
  slots: AvailableSlot[]
  unavailable_reason?: string | null
}

export interface AvailabilityResponse {
  photographer_id: number
  timezone: string
  advance_notice_hours: number
  duration_minutes: number
  buffer_minutes: number
  max_booking_date: string
  days: AvailabilityDay[]
}

export interface OrderRescheduleRequest {
  id: number
  order_id: number
  requested_by: number
  original_appointment_time: string
  requested_appointment_time: string
  reason: string
  status: string
  response_note?: string | null
  expires_at: string
  created_at: string
  resolved_at?: string | null
}

export interface OrderDeliveryFile {
  id: number
  file_url: string
  file_name: string
  file_type?: string | null
  file_size?: number | null
  checksum?: string | null
  created_at: string
}

export interface OrderDelivery {
  id: number
  order_id: number
  version: number
  submitted_by: number
  description?: string | null
  file_count: number
  status: string
  acceptance_deadline_at?: string | null
  accepted_at?: string | null
  created_at: string
  files: OrderDeliveryFile[]
}

export interface OrderRevisionRequest {
  id: number
  order_id: number
  delivery_id: number
  sequence: number
  requested_by: number
  instructions: string
  reference_files: Array<Record<string, unknown>>
  counts_as_free: boolean
  status: string
  response_due_at: string
  expected_redelivery_at?: string | null
  created_at: string
  resolved_at?: string | null
}

export interface OrderDisputeEvidence {
  id: number
  dispute_id: number
  submitted_by: number
  submitter_role: string
  submitter_name?: string | null
  description?: string | null
  file_url?: string | null
  file_name?: string | null
  file_type?: string | null
  file_size?: number | null
  checksum?: string | null
  reference_type?: string | null
  reference_id?: string | null
  created_at: string
}

export interface OrderDispute {
  id: number
  dispute_no: string
  order_id: number
  opened_by: number
  opened_by_role: string
  opener_name?: string | null
  reason_code: string
  description: string
  requested_resolution: string
  status: string
  assigned_admin_id?: number | null
  assigned_admin_name?: string | null
  resolution?: string | null
  resolution_note?: string | null
  refund_amount: number | string
  currency: string
  available_escrow_amount: number | string
  evidence: OrderDisputeEvidence[]
  created_at: string
  updated_at?: string | null
  resolved_at?: string | null
}

export interface OrderHistoryItem {
  id?: number | null
  event_type: string
  status: string
  actor_id?: number | null
  actor_role?: string | null
  actor_name?: string | null
  note?: string | null
  created_at: string
}

export interface OrderItem {
  id: number
  customer_id: number
  photographer_id: number
  customer_name?: string | null
  customer_avatar_url?: string | null
  photographer_name?: string | null
  photographer_avatar_url?: string | null
  package_snapshot: string
  source_type?: string
  source_id?: string | null
  source_application_id?: number | null
  package_id?: string | null
  package_name?: string | null
  package_description?: string | null
  package_price?: number | string | null
  final_price?: number | string | null
  currency?: string
  service_location?: string | null
  payment_due_at?: string | null
  deposit_rate?: number | string | null
  escrow_amount?: number | string | null
  refunded_amount?: number | string | null
  settled_amount?: number | string | null
  acceptance_deadline_at?: string | null
  completed_at?: string | null
  completion_type?: string | null
  revision_used_count?: number
  action_deadline_at?: string | null
  auto_action_code?: string | null
  overdue_at?: string | null
  delivery_due_at?: string | null
  original_image_count?: number | null
  retouched_image_count?: number | null
  delivery_formats?: string[] | null
  included_revision_count?: number | null
  commercial_license?: boolean
  copyright_terms?: string | null
  cancellation_policy_snapshot?: unknown
  reschedule_policy_snapshot?: unknown
  deliverables?: unknown
  payment_mode?: string
  fulfillment_mode?: string
  contract_snapshot?: Record<string, unknown> | null
  appointment_time: string
  duration_minutes: number
  notes?: string | null
  rejection_reason?: string | null
  reschedule_requested_time?: string | null
  reschedule_reason?: string | null
  active_reschedule_request?: OrderRescheduleRequest | null
  cancellation_reason?: string | null
  cancelled_by?: string | null
  status: string
  payment_status?: string
  after_sales_status?: string
  action_required_by?: string | null
  next_action_code?: string | null
  delivery?: {
    delivery_id?: number
    version?: number
    images?: string[]
    description?: string | null
  } | null
  rating?: number | null
  review_text?: string | null
  created_at: string
  updated_at?: string | null
}

export interface OrderDetailResponse {
  order: OrderItem
  history: OrderHistoryItem[]
  reschedule_requests: OrderRescheduleRequest[]
  deliveries: OrderDelivery[]
  revision_requests: OrderRevisionRequest[]
  disputes: OrderDispute[]
}

export interface CreateOrderPayload {
  package_id: string
  photographer_id: number
  appointment_time: string
  notes?: string
}

export interface PaymentRecord {
  id: number
  payment_no: string
  order_id?: number
  customer_id?: number
  purpose?: string
  amount?: number | string
  currency?: string
  status: string
}

export interface ReschedulePayload {
  appointment_time: string
  reason: string
}

export interface ReviewPayload {
  rating: number
  review_text?: string
}

export interface OpenDisputePayload {
  reason_code: string
  description: string
  requested_resolution: string
}

export interface PaymentSummaryItem {
  id: number
  purpose: string
  status: string
  amount: number | string
  created_at?: string
}

export interface RefundSummaryItem {
  id: number
  amount: number | string
  reason?: string
  reason_code?: string
  created_at?: string
}

export interface SettlementSummaryItem {
  net_amount: number | string
  gross_amount?: number | string
  fee_amount?: number | string
  settled_at?: string
}

export interface FinancialSummary {
  payments: PaymentSummaryItem[]
  refunds: RefundSummaryItem[]
  settlement: SettlementSummaryItem | null
}
