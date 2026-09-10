export interface WorkItem {
  id: string
  title?: string
  description?: string
  url?: string
  images?: string[]
  media_type?: 'image' | 'video' | string
  thumbnail_url?: string
  thumbnail_urls?: string[]
  compressed_url?: string
  tag?: string
  tags?: string[]
  duration?: number | null
  photographer_id?: number
  user_id?: number
  user_display_name?: string | null
  user_avatar_url?: string | null
  user_bio?: string | null
  like_count?: number
  recommendation_reason?: string
  candidate_source?: string
}

export interface PackageOffer {
  id: string
  name?: string
  package_name?: string
  price: number
  duration?: number
  buffer_minutes?: number
  image_count?: number
  description?: string
  includes?: string[]
  styles?: string[]
  city?: string
  samples?: string[]
  sample_thumbnails?: string[]
  is_active?: boolean
  service_location?: string | null
  original_image_count?: number
  retouched_image_count?: number
  delivery_formats?: string[]
  included_revision_count?: number
  delivery_days?: number
  commercial_license?: boolean
  terms_rules?: string | null
  copyright_terms?: string | null
  cancellation_policy?: Record<string, unknown> | string | null
  reschedule_policy?: Record<string, unknown> | string | null
  payment_mode?: 'full' | 'deposit_balance' | string
  deposit_rate?: number
  fulfillment_mode?: 'single_delivery' | string
  photographer_id?: number
  photographer_name?: string | null
  photographer_avatar?: string | null
  photographer_location?: string | null
  photographer_bio?: string | null
  recommendation_reason?: string
  candidate_source?: string
}

export type AvailabilityStatus = 'free' | 'busy'

export interface AvailabilityException {
  date: string
  status: AvailabilityStatus
  location?: string
}

export interface PhotographerProfile {
  id: number
  user_id: number
  user_role?: string | null
  user_display_name?: string | null
  username?: string | null
  user_avatar_url?: string | null
  user_bio?: string | null
  public_email?: string | null
  background_url?: string | null
  cover_image_url?: string | null
  location?: string | null
  styles?: string[] | null
  equipment?: string | null
  packages?: PackageOffer[] | null
  availability_exceptions?: AvailabilityException[] | null
  advance_notice?: number | null
  max_daily_bookings?: number | null
  max_booking_date?: string | null
  portfolio?: WorkItem[] | null
  avg_rating?: number | null
  follower_count?: number
  following_count?: number
  created_at?: string
  updated_at?: string | null
}

export interface ProjectBrief {
  id: number
  customer_id: number
  customer_name?: string | null
  customer_avatar_url?: string | null
  title: string
  description: string
  category: string
  style_tags?: string[] | null
  city: string
  location_text?: string | null
  location_name?: string | null
  location_address?: string | null
  location_latitude?: number | null
  location_longitude?: number | null
  location_place_id?: string | null
  location_provider?: string | null
  coordinate_system?: string | null
  location_precision?: string | null
  shoot_date_start?: string | null
  shoot_date_end?: string | null
  duration_minutes?: number | null
  budget_min?: number | null
  budget_max?: number | null
  reference_images?: string[] | null
  deliverables?: unknown
  visibility?: string
  status: string
  selected_application_id?: number | null
  converted_order_id?: number | null
  expires_at?: string | null
  application_count?: number
  created_at: string
  updated_at?: string | null
  match_reason?: string
}

export interface ProjectSummary {
  id: number
  title: string
  category: string
  city: string
  status: string
  budget_min?: number | null
  budget_max?: number | null
  shoot_date_start?: string | null
  converted_order_id?: number | null
}

export interface ProjectPortfolioReference {
  url: string
  title?: string | null
  thumbnail_url?: string | null
}

export interface ProjectApplication {
  id: number
  project_id: number
  photographer_id: number
  photographer_name?: string | null
  photographer_avatar_url?: string | null
  photographer_city?: string | null
  photographer_equipment?: string | null
  photographer_styles?: string[] | null
  photographer_portfolio?: WorkItem[] | null
  status: 'submitted' | 'selected' | 'rejected' | 'withdrawn' | string
  proposal_text: string
  price_quote: number
  package_snapshot?: string | null
  portfolio_refs?: ProjectPortfolioReference[] | null
  revision_note?: string | null
  project?: ProjectSummary | null
  created_at?: string
  updated_at?: string | null
}

export interface ProjectDetailPayload {
  project: ProjectBrief
  applications?: ProjectApplication[]
  my_application?: ProjectApplication | null
  events?: Array<{
    id: number
    event_type: string
    status: string
    note?: string | null
    created_at: string
  }>
}

export interface ProjectApplicationPayload {
  proposal_text: string
  price_quote: number
  package_snapshot?: string | null
  portfolio_refs?: ProjectPortfolioReference[]
  revision_note?: string | null
}

export interface ProjectSelectionResponse {
  project: ProjectBrief
  application: ProjectApplication
  order: { id: number }
}

export interface RecommendationResponse<T> {
  recommendation_id: string
  algorithm_version: string
  next_cursor?: string | null
  items: T[]
}
